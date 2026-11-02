#!/usr/bin/env python3
"""Motor de decision en tiempo real, con enforcement inline opcional.

Reusa directamente las funciones del extractor congelado
``scripts/features/extract_multilayer_v2.py`` (``load_packet_observations``,
``load_app_observations``, ``build_rows``) en vez de reimplementar las 28
formulas de features. Esta es la leccion explicita que se tomo del MVP
anterior, donde el motor y el entrenamiento duplicaron manualmente la logica
de extraccion y podian desincronizarse; ver
docs/fase04-modelado/04-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md.

Arquitectura de entrada, distinta a una campana offline:

- PCAP: ``ppi-motor-capture.service`` mantiene un buffer en anillo de
  archivos rotados por tiempo (``-G 15 -W 16`` => ~240s de historia,
  ampliado desde ~120s tras ``docs/07-mejoras-futuras/01-debilidades-y-mejoras.md``) en
  ``--capture-dir``. Cada ciclo se listan los archivos YA CERRADOS (se
  excluye siempre el mas reciente, que tcpdump todavia esta escribiendo) y
  se pasan tal cual a ``load_packet_observations`` -- sin reimplementar el
  parseo PCAP.
- EVE: Suricata escribe un unico ``eve.json`` continuo. Como
  ``load_app_observations`` espera un archivo completo (no soporta tail
  incremental), este script mantiene en memoria las lineas EVE de los
  ultimos ``--history-seconds`` segundos (por timestamp del propio evento,
  reusando ``parse_eve_timestamp`` del extractor) y las vuelca cada ciclo a
  un archivo temporal que SI se pasa a ``load_app_observations`` sin tocar
  su logica interna.

Limitacion conocida y declarada, no oculta: a diferencia de una campana
offline (PCAP completo desde el primer paquete del episodio),
``attribute_packets`` solo ve el buffer en anillo de ~240s. Un flujo que ya
llevaba mas de ~240s abierto cuando el motor lo observa por primera vez
puede tener su IP iniciadora mal atribuida si el paquete que abrio el flujo
ya rotó fuera del buffer. Para flujos cortos (la inmensa mayoria del trafico
de ataque real medido en la evaluacion bloqueada) esto no aplica.

Enforcement (opcional, ``--enforce``): VM02 (Sensor) ya es el router entre
LAN y DMZ (``ip_forward=1`` + nftables), asi que un ALERT real del modelo
(no del heuristico de ventana vacia) invoca localmente
``sudo -n /usr/local/sbin/ppi-enforce block <ip> <timeout>`` -- sin SSH a
otra maquina, sin credencial nueva entre VMs. Ese helper agrega una tabla
nftables SEPARADA y aditiva (prioridad -300 en el hook forward), con
expiracion nativa del bloqueo (sin cron ni limpieza manual) y su propia
whitelist interna (nunca confia solo en el llamador). Ese enforcement LOCAL es
binario: el motor tiene un solo umbral calibrado y no inventa un segundo. El
nivel intermedio LIMIT existe en el enforcement DISTRIBUIDO (modalidad vigente
por SPAN): publicar_feed.py traduce un ALERT del modelo en LIMIT y el de un
heuristico en la accion de su regla, y el agente del host lo aplica.
"""

from __future__ import annotations

import argparse
import collections
import bisect
import dataclasses
import functools
import json
import math
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "features"))

import extract_multilayer_v2 as extractor  # noqa: E402
import extract_multilayer_v3 as v3  # noqa: E402  (capa 2 y deduplicacion)
import heuristicos  # noqa: E402  (heuristicos deterministas para el feed de enforcement)
import dns_heuristica  # noqa: E402  (vista DNS de los heuristicos, Etapa 3; no toca el IF)
import motor_incremental as incremental  # noqa: E402  (mismo extractor congelado, sin trabajo repetido)

try:
    import joblib
except ImportError as exc:  # pragma: no cover - fallo de despliegue, no de logica
    raise SystemExit(
        "falta joblib/scikit-learn en este interprete; usar el venv congelado "
        "creado por configs/sensor/install-ppi-motor.sh (requirements-model.txt)"
    ) from exc

# Tope FIFO de scored_windows, no una estimacion de trafico real esperado:
# solo acota memoria en un despliegue de muy larga duracion. Ver comentario
# junto a su uso en main() sobre por que no se poda por antiguedad de reloj.
MAX_SCORED_WINDOWS = 20000

# Umbrales del heuristico de fuerza bruta/password-spray (ver uso en main()).
# Elegidos por criterio razonado -- mismo patron que el heuristico SSH del
# MVP anterior (5 intentos en 60s) -- NO calibrados estadisticamente sobre
# datos de validation como el umbral del modelo. Se documenta la diferencia
# explicitamente: esto es una regla de sentido comun, no una calibracion.
AUTH_FAILURE_MIN_REQUESTS = 5
AUTH_FAILURE_MIN_RATIO = 0.8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eve-path", type=Path, default=Path("/var/log/suricata/eve.json"))
    parser.add_argument("--capture-dir", type=Path, default=Path("/var/lib/ppi-motor-capture"))
    parser.add_argument("--capture-glob", default="live-*.pcap")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        help="manifest.json de la calibracion congelada; si se omite, se busca "
        "manifest.json junto a --model-path",
    )
    parser.add_argument("--detector-name", default="ocsvm_scaled")
    parser.add_argument(
        "--schema",
        type=Path,
        default=REPO_ROOT / "configs/features/multilayer-v2.json",
    )
    parser.add_argument("--entity-network", default="10.20.0.0/24")
    parser.add_argument(
        "--excluir",
        default="",
        help="IP o redes separadas por coma que NO se puntuan (gestion propia, "
             "equipos declarados fuera de alcance). Se capturan igual: solo se "
             "excluyen del calculo, para poder medir cuanto se excluyo",
    )
    parser.add_argument(
        "--sin-deduplicar",
        action="store_true",
        help="no quitar las copias que produce el espejo. Solo para medir "
             "cuanto cambia la deduplicacion: en operacion normal sobran, y "
             "sin quitarlas tcp_retransmission_ratio_10s cuenta artefactos "
             "de la captura como retransmisiones de la red",
    )
    parser.add_argument(
        "--excluir-protocolos",
        default="",
        help="numeros de protocolo IP que no son trafico de usuarios y no se "
             "atribuyen a ninguna entidad. Tipico: 112 (VRRP/CARP) y 240 "
             "(pfsync). Sin esto, cada interfaz VLAN del cortafuegos aparece "
             "como una entidad que emite un anuncio por segundo",
    )
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument(
        "--ciclos-path",
        type=Path,
        default=None,
        help="registro de un ciclo por linea (inicio, fin, duracion por etapa, marcas "
             "de disponibilidad y conteos de ventanas). Por omision, ciclos.jsonl en "
             "--state-dir. Va aparte de --log-path para no alterar lo que leen el "
             "panel y el analizador",
    )
    parser.add_argument(
        "--verificar-equivalencia",
        type=Path,
        default=None,
        help="SOLO para validar: en cada ciclo recalcula tambien por la via global "
             "congelada (deduplicacion, atribucion, EVE y build_rows de toda la "
             "historia) y escribe aqui si coincide con la incremental. Cuesta lo "
             "mismo que el motor original; no cambia ninguna decision",
    )
    parser.add_argument("--step-seconds", type=int, default=10)
    parser.add_argument(
        "--disparo",
        choices=("periodico", "eventos"),
        default="periodico",
        help="periodico: un ciclo cada --step-seconds (comportamiento desplegado). "
             "eventos: el ciclo empieza en cuanto se CIERRA un PCAP nuevo (sondeo del "
             "directorio cada --sondeo-segundos) o, como tarde, a los --step-seconds. "
             "No cambia las anclas de las ventanas (siguen cada --step-seconds), ni las "
             "caracteristicas, ni el criterio de ventana completa: solo cuando se mira",
    )
    parser.add_argument("--sondeo-segundos", type=float, default=0.25)
    parser.add_argument(
        "--volcar-caracteristicas",
        type=Path,
        default=None,
        help="SOLO para validar: escribe (entidad, ventana, 28 caracteristicas, score) "
             "de cada ventana puntuada, para comparar configuraciones en el replay",
    )
    parser.add_argument("--history-seconds", type=int, default=110)
    parser.add_argument(
        "--recuperacion-max-segundos",
        type=float,
        default=600.0,
        help="al arrancar, cuanto se retrocede como maximo (ademas de --history-seconds) "
             "para reconstruir el horizonte de la primera ventana no decidida a partir del "
             "anillo de PCAP y de eve.json. Mas alla, las ventanas se marcan "
             "historial_completo=false",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="invocar sudo -n /usr/local/sbin/ppi-enforce block <ip> <timeout> en cada ALERT real",
    )
    parser.add_argument(
        "--enforce-command",
        default="/usr/local/sbin/ppi-enforce",
        help="ruta del helper raiz de enforcement (ver configs/sensor/ppi-enforce)",
    )
    parser.add_argument(
        "--block-timeout-seconds",
        type=int,
        default=120,
        help="expiracion nativa nftables del bloqueo; se renueva si el ALERT se repite",
    )
    return parser.parse_args()


def _ts(observacion) -> float:
    return observacion.timestamp


def apply_enforcement(enforce_command: str, ip: str, timeout_seconds: int) -> dict[str, object]:
    try:
        result = subprocess.run(
            ["sudo", "-n", enforce_command, "block", ip, str(timeout_seconds)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"applied": False, "error": str(exc)}
    if result.returncode != 0:
        return {"applied": False, "error": (result.stderr or result.stdout).strip()[:500]}
    return {"applied": True, "helper_output": result.stdout.strip()}


def load_threshold(manifest_path: Path, detector_name: str) -> float:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    detector = manifest["detectors"][detector_name]
    comparison = detector["calibration"]["comparison"]
    if comparison != "score < threshold":
        raise ValueError(
            f"regla de comparacion inesperada en el manifiesto: {comparison!r}"
        )
    return float(detector["calibration"]["threshold"])


class EveTail:
    """Tail incremental de eve.json con deteccion de rotacion/truncamiento."""

    BLOQUE = 4 * 1024 * 1024
    HOLGURA_S = 30.0  # eve.json no esta estrictamente ordenado por timestamp

    def __init__(self, path: Path, desde: float | None = None, parse_ts=None,
                 max_bytes: int = 512 * 1024 * 1024) -> None:
        self.path = path
        # Arranca en el final del archivo (como "tail -f"), no en el byte 0:
        # eve.json puede llevar dias acumulando lineas. Con ``desde`` (cierre de
        # la Etapa 2) retrocede hasta la primera linea con timestamp >= desde -
        # HOLGURA_S, para que tras un reinicio las variables L7 de 60 s tengan su
        # historia (antes el motor arrancaba sin ella y cambiaba ~50 s de
        # decisiones, r7). Nunca retrocede mas de ``max_bytes``.
        self.recuperacion: dict[str, object] = {"pedido_desde": desde, "completa": desde is None}
        try:
            stat_result = path.stat()
            self._offset = stat_result.st_size
            self._inode = (stat_result.st_dev, stat_result.st_ino)
        except FileNotFoundError:
            self._offset = 0
            self._inode = None
        self._partial = b""
        if desde is not None and parse_ts is not None and self._offset > 0:
            self._rebobinar(desde - self.HOLGURA_S, parse_ts, max_bytes)

    @staticmethod
    def _ts_linea(linea: bytes, parse_ts) -> float | None:
        i = linea.find(b'"timestamp"')
        if i < 0:
            return None
        a = linea.find(b'"', i + 11)
        b = linea.find(b'"', a + 1)
        try:
            return parse_ts(linea[a + 1:b].decode("ascii"))
        except (ValueError, UnicodeDecodeError):
            return None

    def _rebobinar(self, objetivo: float, parse_ts, max_bytes: int) -> None:
        fin = self._offset
        pos = fin
        alcanzado = False
        with self.path.open("rb") as handle:
            # 1) Hacia atras por bloques hasta un bloque cuya primera linea completa es anterior al objetivo.
            while pos > 0 and fin - pos < max_bytes:
                inicio = max(0, pos - self.BLOQUE)
                handle.seek(inicio)
                datos = handle.read(pos - inicio)
                j = 0 if inicio == 0 else datos.find(b"\n") + 1
                k = datos.find(b"\n", j)
                ts = self._ts_linea(datos[j:k if k >= 0 else len(datos)], parse_ts)
                pos = inicio + j if inicio > 0 else 0
                if ts is not None and ts < objetivo:
                    alcanzado = True
                    break
                if inicio == 0:
                    break
            # 2) Hacia delante desde ahi hasta la primera linea >= objetivo.
            handle.seek(pos)
            offset = pos
            primera = None
            for linea in handle:
                if offset >= fin:
                    break
                ts = self._ts_linea(linea, parse_ts)
                if ts is not None and ts >= objetivo:
                    primera = ts
                    break
                offset += len(linea)
        self._offset = offset
        self.recuperacion.update({"offset": offset, "bytes": fin - offset, "primera_linea": primera,
                                  "completa": alcanzado})

    def poll(self) -> list[str]:
        try:
            stat_result = self.path.stat()
        except FileNotFoundError:
            return []
        current_inode = (stat_result.st_dev, stat_result.st_ino)
        if self._inode is not None and current_inode != self._inode:
            self._offset = 0
            self._partial = b""
        self._inode = current_inode
        if stat_result.st_size < self._offset:
            self._offset = 0
            self._partial = b""

        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
            self._offset = handle.tell()

        data = self._partial + chunk
        parts = data.split(b"\n")
        self._partial = parts[-1]
        return [raw.decode("utf-8", errors="replace") for raw in parts[:-1] if raw.strip()]


def list_closed_pcap_files(
    capture_dir: Path,
    pattern: str,
    max_age_seconds: float | None = None,
    now: float | None = None,
) -> list[Path]:
    files = sorted(capture_dir.glob(pattern))
    closed = files[:-1] if len(files) > 1 else []
    if max_age_seconds is None:
        return closed
    # Acota el lookback de PCAP por antiguedad de mtime, igual que el
    # eve_buffer se acota por history_seconds. Sin esto, un PCAP rancio que
    # quedo en el anillo (tcpdump -G solo rota al llegar un paquete; en un
    # tramo ocioso largo un archivo persiste con timestamp viejo, y ademas
    # tcpdump -W no borra archivos de corridas previas) hace que build_rows()
    # genere una ventana por cada paso de 10s desde ese timestamp hasta ahora
    # al reiniciar el motor -> replay de miles de ventanas y re-bloqueo de
    # ALERTs antiguas (MOTOR-OBS-02). Filtrar por mtime deja solo la historia
    # genuinamente reciente (<= history_seconds), coherente con el diseno del
    # anillo. Ver docs/fase05-motor-tiempo-real/02-fp-ventana-sin-paquetes.md.
    reference = time.time() if now is None else now
    fresh: list[Path] = []
    for pcap in closed:
        try:
            if reference - pcap.stat().st_mtime <= max_age_seconds:
                fresh.append(pcap)
        except OSError:
            continue
    return fresh


def hay_pcap_cerrado_nuevo(args, ya_leidos, ahora: float) -> bool:
    """True si ya existe un PCAP CERRADO que el motor aun no ha leido.

    Usa el mismo criterio de cierre que el ciclo (list_closed_pcap_files: nunca el
    ultimo fichero, que tcpdump sigue escribiendo). Un fichero abierto no dispara.
    """
    for pcap in list_closed_pcap_files(args.capture_dir, args.capture_glob,
                                       max_age_seconds=args.history_seconds, now=ahora):
        if pcap.name not in ya_leidos:
            return True
    return False


def esperar_siguiente_ciclo(args, inicio_ciclo: float, ya_leidos) -> str:
    """Espera hasta el siguiente ciclo y devuelve el motivo del disparo.

    periodico: igual que el motor desplegado (sleep hasta completar step_seconds,
    minimo 0,5 s). eventos: sondea el directorio; dispara al aparecer un PCAP
    cerrado no leido ('pcap_cerrado') o al vencer step_seconds desde el inicio del
    ciclo anterior ('plazo'), para que las ventanas que solo dependen de EVE o de la
    expiracion de pendientes sigan avanzando aunque la captura se pare.
    """
    if args.disparo == "periodico":
        elapsed = time.time() - inicio_ciclo
        time.sleep(max(0.5, args.step_seconds - elapsed))
        return "periodo"
    limite = inicio_ciclo + args.step_seconds
    while True:
        time.sleep(args.sondeo_segundos)
        ahora = time.time()
        if hay_pcap_cerrado_nuevo(args, ya_leidos, ahora):
            return "pcap_cerrado"
        if ahora >= limite:
            return "plazo"


def ventana_completa(window_end: float, marca_pcap: float | None) -> bool:
    """La ventana solo se decide cuando los PCAP CERRADOS ya llegan hasta su final.

    build_rows() crea ventanas hasta la observacion mas nueva de la entidad, sea
    un paquete o un evento de eve.json. eve.json se escribe casi en tiempo real,
    pero los paquetes solo se leen de ficheros cerrados (rotacion de 15 s), asi
    que una ventana podia existir por un evento L7 antes de que sus paquetes
    estuvieran en disco. Se decidia con packet_count_10s=0 (o con un conteo a
    medias) y quedaba en scored_windows: nunca se volvia a evaluar. Medido el
    2026-10-28 contra el PCAP completo: 241 de 2 791 ventanas con trafico.
    'Datos aun no disponibles' no es 'cero trafico': la ventana queda pendiente
    hasta que marca_pcap (paquete mas nuevo ya leido de un fichero cerrado) la
    cubre. No es una espera fija: se evalua en el primer ciclo en que esta completa.
    """
    return marca_pcap is not None and window_end <= marca_pcap


def claves_ya_registradas(log_path: Path, max_bytes: int = 16 * 1024 * 1024) -> dict[tuple[str, str], float]:
    """Claves (entidad, window_end_utc) ya escritas en el registro, para no repetirlas al reiniciar.

    Al arrancar, build_rows() vuelve a crear las ventanas de los ultimos
    history_seconds a partir del anillo; sin esto, un reinicio duplicaria en el
    registro decisiones de ventanas ya decididas.
    """
    claves: dict[tuple[str, str], float] = {}
    try:
        with log_path.open("rb") as handle:
            size = handle.seek(0, 2)
            handle.seek(max(0, size - max_bytes))
            data = handle.read().decode("utf-8", errors="replace").split("\n")
    except FileNotFoundError:
        return claves
    if size > max_bytes:
        data = data[1:]
    for line in data:
        if '"window_end_utc"' not in line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("event") in ("decision", "ventana_no_evaluada"):
            key = (str(record["entity_ip"]), str(record["window_end_utc"]))
            claves[key] = extractor.parse_eve_timestamp(key[1])
    return claves


def parse_pcap_to_packets(path: Path) -> list:
    """Decodifica un PCAP a FrameContext (parseo, sin atribucion de flujo).

    Reusa las funciones publicas del extractor congelado -- NO reimplementa la
    decodificacion. Separar el parseo (caro: I/O + decode por frame) de la
    atribucion permite decodificar cada archivo del anillo UNA sola vez y
    bufferear el resultado, en vez de re-decodificar todo el anillo cada ciclo
    (causa del atraso bajo carga medido en F6, docs/fase07-validacion-final/).

    Devuelve FrameContext y no ParsedPacket porque la deduplicacion necesita
    la etiqueta VLAN y el identificador IP, dos campos que el parser congelado
    no conserva. El ParsedPacket que va dentro lo produce ese mismo parser.
    """
    out = []
    for timestamp, frame in extractor.iter_pcap_frames(path):
        contexto = v3.parse_con_contexto(timestamp, frame)
        if contexto is not None:
            out.append(contexto)
    return out


def escribir_registros(log_path: Path, registros: list[dict]) -> float | None:
    """Escribe los registros del ciclo en un solo write y devuelve cuando quedaron visibles.

    ``logged_at`` se asigna aqui, justo antes de escribir, a todos los registros
    del lote: conserva el significado de 7b275b8 (instante de escritura, la hora
    que leen publicar_feed.py y el analizador) aunque las decisiones se hayan
    tomado antes en el ciclo (``decidido_en``). Es una cota inferior de la
    disponibilidad; el valor devuelto, tomado al cerrar el fichero, es la cota
    superior y va a ciclos.jsonl como ``registro_escrito_en``. None si no hay
    nada que escribir.
    """
    if not registros:
        return None
    escrito = time.time()
    lineas = []
    for record in registros:
        record["logged_at"] = escrito
        lineas.append(json.dumps(record, sort_keys=True))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lineas) + "\n")
    disponible = time.time()
    for record, linea in zip(registros, lineas):
        if record.get("decision") == "ALERT":
            print(linea, flush=True)
    return disponible


def main() -> int:
    args = parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    feature_names = tuple(
        item["name"] for item in sorted(schema["features"], key=lambda item: item["order"])
    )
    if feature_names != extractor.FEATURE_NAMES:
        raise SystemExit("el esquema de features no coincide con el extractor importado")

    manifest_path = args.manifest_path or (args.model_path.parent.parent / "manifest.json")
    threshold = load_threshold(manifest_path, args.detector_name)
    pipeline = joblib.load(args.model_path)

    import ipaddress

    entity_network = ipaddress.ip_network(args.entity_network)
    redes_excluidas = [
        ipaddress.ip_network(t.strip(), strict=False)
        for t in args.excluir.split(",") if t.strip()
    ]
    protocolos_excluidos = {
        int(t.strip()) for t in args.excluir_protocolos.split(",") if t.strip()
    }

    def entidad_excluida(ip: str) -> bool:
        try:
            direccion = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(direccion in red for red in redes_excluidas)

    state_dir = args.state_dir or (args.log_path.parent / "_state")
    state_dir.mkdir(parents=True, exist_ok=True)
    # Solo lo usa --verificar-equivalencia: el motor ya no vuelca ni relee la
    # historia de eve.json en cada ciclo (cada linea se lee una vez al llegar).
    eve_slice_path = state_dir / "eve_window.jsonl"
    ciclos_path = args.ciclos_path or (state_dir / "ciclos.jsonl")

    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    # (hora del evento, linea, sus observaciones L7): las observaciones se
    # calculan con la funcion congelada una sola vez, cuando la linea llega.
    eve_buffer: collections.deque[tuple[float, str, list]] = collections.deque()
    # Etapa 3: vista DNS para dns_entropy (sin copias del espejo ni reenvios de DC1/DC2).
    vista_dns = dns_heuristica.VistaDns()
    scored_windows: dict[tuple[str, str], float] = claves_ya_registradas(args.log_path)
    # Horizonte por ventana (cierre de la Etapa 2): la ventana A se calcula con la
    # entrada [A - history_seconds, ...], sin depender de cuando se decide. Las anclas
    # se procesan en orden; ancla_hecha es la ultima ya tratada. Tras un reinicio se
    # continua desde la ultima ventana registrada y se relee su horizonte del anillo
    # de PCAP y de eve.json (si sigue ahi: --recuperacion-max-segundos).
    paso_s = args.step_seconds
    horizonte_s = args.history_seconds
    arranque_s = time.time()
    ancla_hecha: float | None = None
    hueco_arranque = None
    if scored_windows:
        ultima_registrada = max(scored_windows.values())
        if arranque_s - ultima_registrada <= horizonte_s + args.recuperacion_max_segundos:
            ancla_hecha = ultima_registrada
        else:
            hueco_arranque = {"ultima_registrada": ultima_registrada, "arranque": arranque_s}
    desde_recuperacion = ((ancla_hecha + paso_s) if ancla_hecha is not None else arranque_s) - horizonte_s
    tail = EveTail(args.eve_path, desde=desde_recuperacion, parse_ts=extractor.parse_eve_timestamp)
    # Desde cuando hay historia COMPLETA de las dos fuentes en este proceso (se fija
    # en el primer ciclo): una ventana A tiene historial completo si A - horizonte >= esto.
    inicio_historial: float | None = None
    # Ventanas vistas pero aun sin sus paquetes en ficheros cerrados: clave -> primer ciclo en que se vio.
    pendientes: collections.OrderedDict[tuple[str, str], float] = collections.OrderedDict()
    marca_pcap: float | None = None   # paquete mas nuevo leido de un PCAP cerrado
    marca_eve: float | None = None    # evento mas nuevo leido de eve.json (solo se registra)
    # Mas alla de esta antiguedad la historia de 60 s de la ventana ya no esta entera en el buffer
    # (se poda a history_seconds desde el dato mas nuevo): no se puede evaluar bien y se registra como no evaluada.
    limite_pendiente = args.history_seconds - 60
    descartados_plano_control = 0
    ventanas_excluidas = 0
    pcaps_ilegibles = 0
    motivos_ilegibles: dict[str, str] = {}
    duplicados_espejo = 0
    # Buffer incremental de paquetes ya decodificados (ParsedPacket) + set de
    # PCAP ya parseados. Evita re-decodificar todo el anillo cada ciclo: cada
    # archivo se lee de disco UNA vez; la atribucion de flujo se recalcula
    # sobre el buffer en memoria. Corrige el atraso bajo carga (F6 #12).
    packet_buffer: collections.deque = collections.deque()
    # Via por deltas (pendiente 2): contextos llegados (sin plano de control) que el
    # Deduplicador aun no ha recibido, y el corte de la ultima poda EJECUTADA del buffer
    # (la poda quita todo lo anterior a su corte; asi el buffer es exactamente lo llegado
    # con timestamp >= poda_hecha).
    llegados_dedup: list = []
    poda_hecha = float("-inf")
    parsed_pcaps: collections.OrderedDict[str, None] = collections.OrderedDict()
    MAX_PARSED_PCAP_NAMES = 4000
    # Orden de llegada al anillo de cada trama (y de su paquete). Las funciones
    # congeladas ordenan de forma estable por timestamp: (timestamp, llegada)
    # reproduce ese orden aunque se les pase solo una parte del anillo.
    llegada: dict[int, int] = {}
    llegada_paquete: dict[int, int] = {}
    siguiente_llegada = 0
    deduplicador = incremental.Deduplicador(v3.deduplicar_espejo)
    atribuidor = incremental.Atribuidor(extractor.attribute_packets, extractor.canonical_flow_key)

    def orden_paquete(paquete) -> tuple[float, int]:
        return paquete.timestamp, llegada_paquete[id(paquete)]

    verificacion = (args.verificar_equivalencia.open("a", encoding="utf-8")
                    if args.verificar_equivalencia else None)
    volcado = (args.volcar_caracteristicas.open("a", encoding="utf-8")
               if args.volcar_caracteristicas else None)
    ciclo_n = 0
    motivo_disparo = "arranque"

    startup_record = {
        "event": "motor_startup",
        "timestamp": time.time(),
        "model_path": str(args.model_path),
        "manifest_path": str(manifest_path),
        "detector_name": args.detector_name,
        "threshold": threshold,
        "entity_network": str(entity_network),
        "excluidas": [str(r) for r in redes_excluidas],
        "protocolos_excluidos": sorted(protocolos_excluidos),
        "capture_dir": str(args.capture_dir),
        "eve_path": str(args.eve_path),
        "step_seconds": args.step_seconds,
        "history_seconds": args.history_seconds,
        "claves_previas_cargadas": len(scored_windows),
        "horizonte": "por_ventana",
        "ancla_reanudada": ancla_hecha,
        "hueco_arranque": hueco_arranque,
        "recuperacion_eve": tail.recuperacion,
        # Mismas funciones congeladas; ver scripts/engine/motor_incremental.py.
        "procesamiento": "incremental",
        "ciclos_path": str(ciclos_path),
        "disparo": args.disparo,
        "sondeo_segundos": args.sondeo_segundos,
    }
    with args.log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(startup_record, sort_keys=True) + "\n")
    print(json.dumps(startup_record, sort_keys=True), flush=True)

    # Piso fijo de cobertura: el proceso del motor arranca despues de que
    # ppi-motor-capture.service ya esta activo (Requires= en la unidad), asi
    # que este instante es una cota conservadora de cuanto tiempo lleva el
    # anillo de captura observando la red. Sin este piso, build_rows() infiere
    # la cobertura del primer paquete presente en el buffer de ESTE ciclo, lo
    # que marcaria como "sin suficiente historia" cualquier rafaga que llegue
    # despues de un periodo sin trafico -- aunque el motor llevara minutos
    # observando. Se fija una sola vez al arrancar, no se recalcula por ciclo.
    capture_epoch = time.time()
    packets_pendientes: list = []  # ultima atribucion, para la contabilidad de pendientes
    corte_pendientes: float | None = None  # inicio del horizonte de esa atribucion
    # Con que se dio de alta cada pendiente: horizonte y observaciones de la entidad en
    # (A-60, A] segun esa atribucion (evidencia de las cancelaciones).
    origen_pendiente: dict[tuple[str, str], dict] = {}
    # Marca de lectura de cada ciclo (paquete mas nuevo de PCAP cerrado / linea EVE mas nueva)
    # y el ciclo que la alcanzo: el primer ciclo que ya habia leido una observacion.
    lecturas = {"pcap": ([], []), "eve": ([], [])}

    def anotar_lectura(fuente: str, marca, ciclo: float) -> None:
        marcas, ciclos = lecturas[fuente]
        if marca is not None and (not marcas or marca > marcas[-1]):
            marcas.append(marca)
            ciclos.append(ciclo)

    def visto_en(fuente: str, ts: float):
        marcas, ciclos = lecturas[fuente]
        i = bisect.bisect_left(marcas, ts)
        return ciclos[i] if i < len(ciclos) else None

    def podar_lecturas(hasta: float) -> None:
        for marcas, ciclos in lecturas.values():
            i = bisect.bisect_left(marcas, hasta)
            del marcas[:i], ciclos[:i]

    while True:
        cycle_start = time.time()
        t_ciclo = time.perf_counter()
        etapas: dict[str, float] = {}
        marca_pcap_previa = marca_pcap

        def cerrar_etapa(nombre: str, desde: float) -> float:
            ahora = time.perf_counter()
            etapas[nombre] = round(etapas.get(nombre, 0.0) + ahora - desde, 4)
            return ahora

        t = time.perf_counter()
        lineas_eve_nuevas = 0
        for raw_line in tail.poll():
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            timestamp_raw = event.get("timestamp")
            if not timestamp_raw:
                continue
            try:
                event_time = extractor.parse_eve_timestamp(timestamp_raw)
            except ValueError:
                continue
            vista_dns.linea(raw_line)
            eve_buffer.append((event_time, raw_line,
                               incremental.observaciones_de_linea(extractor, raw_line, entity_network)))
            lineas_eve_nuevas += 1
            marca_eve = event_time if marca_eve is None else max(marca_eve, event_time)
        t = cerrar_etapa("eve_lectura", t)

        base_horizonte = (ancla_hecha + paso_s) if ancla_hecha is not None else cycle_start
        cutoff = max(min(base_horizonte, cycle_start) - horizonte_s,
                     cycle_start - horizonte_s - args.recuperacion_max_segundos)
        while eve_buffer and eve_buffer[0][0] < cutoff:
            eve_buffer.popleft()
        vista_dns.podar(cutoff)
        # NO se poda scored_windows por antiguedad de reloj real: se
        # encontro en produccion que un PCAP viejo del anillo (tcpdump con
        # -G solo rota al llegar un paquete nuevo; en tramos ociosos un
        # archivo puede tardar mucho en rotar) puede seguir aportando
        # paquetes con timestamps antiguos ciclo tras ciclo. Podar por
        # "mas viejo que cutoff" borraba esa ventana de la memoria de
        # deduplicacion justo despues de registrarla, permitiendo que se
        # re-puntuara y re-bloqueara la MISMA ventana en cada ciclo,
        # indefinidamente -- bucle real observado bloqueando al cliente sin
        # parar. En vez de podar por edad, se acota por tamano (FIFO): una
        # vez puntuada, una ventana queda recordada durante mucho tiempo sin
        # importar su timestamp.
        while len(scored_windows) > MAX_SCORED_WINDOWS:
            oldest_key = next(iter(scored_windows))
            del scored_windows[oldest_key]
        t = cerrar_etapa("eve_poda", t)

        edad_max = min(max(float(horizonte_s), cycle_start - (base_horizonte - horizonte_s)),
                       horizonte_s + args.recuperacion_max_segundos)
        pcap_files = list_closed_pcap_files(
            args.capture_dir,
            args.capture_glob,
            max_age_seconds=edad_max,
            now=cycle_start,
        )
        if inicio_historial is None:
            # Si hay ficheros cerrados mas viejos que los leidos, todo lo posterior a
            # cycle_start - edad_max esta en los leidos; si no, la historia empieza en
            # el primer paquete leido (no se puede saber si hubo antes).
            hay_anteriores = len(list_closed_pcap_files(args.capture_dir, args.capture_glob)) > len(pcap_files)
            inicio_pcap = (cycle_start - edad_max) if hay_anteriores else None
        # Parseo INCREMENTAL: decodifica de disco solo los PCAP no vistos antes.
        # Equivalente exacto a re-parsear todo el anillo porque
        # attribute_packets() ordena por timestamp internamente.
        pcaps_nuevos = 0
        for pcap in pcap_files:
            if pcap.name in parsed_pcaps:
                continue
            try:
                nuevos = parse_pcap_to_packets(pcap)
                pcaps_nuevos += 1
                for pk in nuevos:
                    llegada[id(pk)] = siguiente_llegada
                    llegada_paquete[id(pk.packet)] = siguiente_llegada
                    siguiente_llegada += 1
                packet_buffer.extend(nuevos)
                llegados_dedup.extend(pk for pk in nuevos if pk.packet.protocol not in protocolos_excluidos)
                if nuevos:
                    mas_nuevo = max(pk.packet.timestamp for pk in nuevos)
                    marca_pcap = mas_nuevo if marca_pcap is None else max(marca_pcap, mas_nuevo)
            except Exception as exc:
                # Se salta, pero SE CUENTA. Tragarse esto en silencio escondio
                # durante meses que el motor descartaba el 5,55 % de su propio
                # anillo: tcpdump con -Z hace chown del primer fichero de cada
                # arranque a tcpdump:tcpdump y el usuario del motor no podia
                # leerlo. Un contador en cada decision lo habria delatado el
                # primer dia. Ver scripts/setup/cyberflow_config.py, CAPTURA.
                pcaps_ilegibles += 1
                if type(exc).__name__ not in motivos_ilegibles:
                    motivos_ilegibles[type(exc).__name__] = str(exc)[:120]
            parsed_pcaps[pcap.name] = None
        while len(parsed_pcaps) > MAX_PARSED_PCAP_NAMES:
            parsed_pcaps.popitem(last=False)
        if inicio_historial is None and (packet_buffer or eve_buffer):
            if inicio_pcap is None:
                inicio_pcap = min((pk.packet.timestamp for pk in packet_buffer), default=cycle_start)
            if tail.recuperacion.get("completa"):
                inicio_eve = tail.recuperacion["pedido_desde"]
            else:
                inicio_eve = min((x[0] for x in eve_buffer), default=cycle_start)
            inicio_historial = max(inicio_pcap, inicio_eve)
        t = cerrar_etapa("pcap_parseo", t)
        # Poda por TIEMPO DEL DATO (no del reloj de pared): se conserva
        # history_seconds hacia atras desde el paquete mas nuevo del buffer.
        # Critico: podar por reloj de pared descartaria paquetes AUN NO
        # procesados cuando el motor va atrasado (buffer con datos viejos vs.
        # wall adelantado), congelando el avance -- bug real observado. Podar
        # relativo al dato mas nuevo mantiene la ventana deslizante sobre lo que
        # el motor todavia debe digerir, y drena cuando la carga cesa.
        if packet_buffer:
            # El paquete mas nuevo del buffer es marca_pcap (el mas nuevo leido: nunca se poda).
            newest_data = marca_pcap
            # El horizonte de la siguiente ancla por tratar, nunca mas alla del dato mas nuevo.
            data_cutoff = min(newest_data, base_horizonte) - args.history_seconds
            if packet_buffer[0].packet.timestamp < data_cutoff:
                for pk in packet_buffer:
                    if pk.packet.timestamp < data_cutoff:
                        del llegada[id(pk)]
                        del llegada_paquete[id(pk.packet)]
                packet_buffer = collections.deque(
                    pk for pk in packet_buffer if pk.packet.timestamp >= data_cutoff
                )
                poda_hecha = max(poda_hecha, data_cutoff)
        t = cerrar_etapa("pcap_poda", t)

        # El plano de control se descarta ANTES de atribuir: un anuncio CARP
        # crea un flujo cuyo iniciador es la interfaz del cortafuegos, y esa
        # interfaz pasa a ser una entidad puntuada. No se toca el extractor
        # congelado: se filtra su entrada, que es alcance, no formula.
        if protocolos_excluidos and packet_buffer:
            paquetes_utiles = [
                pk for pk in packet_buffer
                if pk.packet.protocol not in protocolos_excluidos
            ]
            descartados_plano_control += len(packet_buffer) - len(paquetes_utiles)
        else:
            paquetes_utiles = list(packet_buffer)
        t = cerrar_etapa("filtro_plano_control", t)

        # La sesion SPAN ensena la misma trama dos veces: el trafico entre VLAN
        # se ve al entrar y al salir del cortafuegos (TTL-1), y la difusion
        # inunda los dos puertos troncales que la sesion escucha (identica).
        # Sin quitarlas, tcp_retransmission_ratio_10s lee artefactos de la
        # captura como problemas de la red: medido en este sensor, 0,1488 antes
        # y 0,0000 despues -- las 100 "retransmisiones" eran las 100 copias.
        # Se filtra la ENTRADA del extractor congelado, no su formula, igual
        # que con CARP y pfsync.
        # Misma entrada y mismo resultado que v3.deduplicar_espejo(paquetes_utiles):
        # solo se vuelven a deduplicar las claves que cambiaron en este ciclo.
        # Registros del ciclo, escritos juntos al final (escribir_registros). Tiempos:
        #   decidido_en  momento en que el motor tomo la decision o expiro la ventana;
        #   logged_at    instante de escritura, asignado justo antes del write, igual que
        #                en 7b275b8 (alli cada registro se escribia al decidirlo): es el
        #                significado que usan publicar_feed.py y el analizador;
        #   ciclos.jsonl registro_escrito_en: despues de cerrar el fichero, cuando el
        #                registro ya es visible para los consumidores (cota superior).
        registros_ciclo: list[dict] = []
        cuenta = collections.Counter()
        paquetes: list = []
        packets: list = []
        apps: list = []
        decididas: list[tuple] = []

        def entrada_horizonte(corte: float):
            """Deduplicacion y atribucion (incrementales) sobre [corte, ...] del buffer, y su L7.

            Por omision, por deltas: el horizonte [max(corte, poda_hecha), ...] del buffer son
            los presentes de la llamada anterior con timestamp >= ese corte mas lo llegado
            desde entonces (Deduplicador.deslizar). Mismo resultado que filtrar todo el buffer
            (tests: test_deslizar_igual_a_la_global_con_atribucion). Con --sin-deduplicar o
            --verificar-equivalencia se usa la via por conjunto completo."""
            nonlocal llegados_dedup
            quitados = 0
            if args.sin_deduplicar or verificacion is not None:
                utiles = [pk for pk in paquetes_utiles if pk.packet.timestamp >= corte]
                if args.sin_deduplicar:
                    paq = sorted((pk.packet for pk in utiles), key=orden_paquete)
                else:
                    paq, quitados = deduplicador.actualizar(utiles, llegada)
                obs = atribuidor.actualizar(paq, entity_network, orden_paquete) if paq else []
            else:
                utiles = None
                paq, quitados, entran, salen = deduplicador.deslizar(
                    max(corte, poda_hecha), llegados_dedup, llegada)
                llegados_dedup = []
                obs = atribuidor.deslizar(paq, entran, salen, entity_network, orden_paquete)
            lineas = [x for x in eve_buffer if x[0] >= corte]
            l7 = [o for _, _, lista in lineas for o in lista]
            return utiles, paq, obs, lineas, l7, quitados

        # Anclas completas por tratar: con contenido, posteriores a ancla_hecha y cubiertas
        # por los PCAP cerrados (mas el margen de la deduplicacion del espejo).
        anclas: list[int] = []
        if marca_pcap is not None and (paquetes_utiles or eve_buffer):
            anclas = incremental.anclas_con_contenido(
                (pk.packet.timestamp for pk in paquetes_utiles), (x[0] for x in eve_buffer), paso_s,
                ancla_hecha if ancla_hecha is not None else float("-inf"),
                marca_pcap - incremental.MARGEN_DEDUP_S)
        anotar_lectura("pcap", marca_pcap, cycle_start)
        anotar_lectura("eve", marca_eve, cycle_start)
        quitados = 0
        for ancla in anclas:
            corte = ancla - horizonte_s
            utiles, paquetes, packets, lineas, apps, quitados = entrada_horizonte(corte)
            cuenta["flujos_recalculados"] += atribuidor.flujos_recalculados if paquetes else 0
            # ``packets`` sale de attribute_packets en orden de tiempo (ordena por timestamp de
            # forma estable): su minimo es el primero y (A-60, A] es un tramo contiguo.
            t_min_obs = min(packets[0].timestamp if packets else math.inf,
                            min((x.timestamp for x in apps), default=math.inf))
            capture_start = min(capture_epoch, t_min_obs) if (packets or apps) else capture_epoch
            completo = inicio_historial is not None and corte >= inicio_historial
            lp: dict[str, list] = collections.defaultdict(list)
            la: dict[str, list] = collections.defaultdict(list)
            i0 = bisect.bisect_right(packets, ancla - incremental.REGISTRO_S, key=_ts)
            i1 = bisect.bisect_right(packets, ancla, lo=i0, key=_ts)
            for x in packets[i0:i1]:
                lp[x.entity_ip].append(x)
            for x in apps:
                if ancla - 60 < x.timestamp <= ancla:
                    la[x.entity_ip].append(x)

            def anterior_en_horizonte(entidad: str, packets=packets, apps=apps, i0=i0, ancla=ancla):
                """Una observacion de la entidad anterior a A en el horizonte (solo se busca si
                todo su contenido de (A-60, A] cae justo en A: caso limite de fila_de_ancla)."""
                for x in packets[:i0]:
                    if x.entity_ip == entidad:
                        return x
                for x in apps:
                    if x.entity_ip == entidad and x.timestamp < ancla:
                        return x
                return None
            clave = incremental.clave_ventana(ancla)
            filas_ancla: dict[str, dict] = {}
            excluidas_ancla: set[str] = set()
            for entidad in sorted(set(lp) | set(la)):
                window_key = (entidad, clave)
                cuenta["entidades"] += 1
                if entidad_excluida(entidad):
                    excluidas_ancla.add(entidad)
                    if window_key not in scored_windows:
                        ventanas_excluidas += 1
                        cuenta["excluidas_nuevas"] += 1
                        scored_windows[window_key] = float(ancla)
                    continue
                row = incremental.fila_de_ancla(extractor.build_rows, lp[entidad], la[entidad], ancla,
                                                paso_s, capture_start, dataclasses.replace,
                                                buscar_anterior=functools.partial(anterior_en_horizonte, entidad))
                # Ventana registrable (contenido en (A-60, A] con su horizonte) que no se
                # puede decidir: se registra ya como no evaluada con su motivo, nunca en
                # silencio ni como PERMIT. fila_no_generada: la primera observacion de la
                # entidad en el horizonte cae justo en A y build_rows (congelado) empieza su
                # rejilla en A+paso. no_elegible: historia < 60 s (eligible_training).
                motivo_ne = None
                if row is None:
                    motivo_ne = "fila_no_generada"
                else:
                    filas_ancla[entidad] = row
                    cuenta["filas_construidas"] += 1
                    if window_key in scored_windows:
                        continue
                    if not row["eligible_training"]:
                        cuenta["no_elegibles"] += 1
                        motivo_ne = "no_elegible"
                if motivo_ne is not None:
                    if window_key not in scored_windows:
                        scored_windows[window_key] = float(ancla)
                        visto_ne = pendientes.pop(window_key, None)
                        origen_pendiente.pop(window_key, None)
                        cuenta["no_evaluadas"] += 1
                        registros_ciclo.append({
                            "event": "ventana_no_evaluada", "decidido_en": time.time(),
                            "entity_ip": entidad, "window_end_utc": clave, "motivo": motivo_ne,
                            "pendiente_desde": visto_ne, "inicio_ciclo": cycle_start,
                            "marca_pcap": marca_pcap, "marca_eve": marca_eve,
                            "pcaps_ilegibles": pcaps_ilegibles, "horizonte_s": horizonte_s,
                            "historial_completo": completo,
                        })
                    continue
                # Espera: primer ciclo que ya tenia contenido de la ventana (registro de
                # pendientes o marcas de lectura); None si se decide en ese mismo ciclo.
                vistos = [pendientes.pop(window_key, None)]
                if lp[entidad]:
                    vistos.append(visto_en("pcap", min(x.timestamp for x in lp[entidad])))
                if la[entidad]:
                    vistos.append(visto_en("eve", min(x.timestamp for x in la[entidad])))
                vistos = [v for v in vistos if v is not None and v < cycle_start]
                pendiente_desde = min(vistos) if vistos else None
                scored_windows[window_key] = float(ancla)
                origen_pendiente.pop(window_key, None)
                decididas.append((row, pendiente_desde, ventanas_excluidas, completo))
            # Pendientes de esta ancla que no se decidieron. La regla causal se aplica con el
            # horizonte PROPIO de la ventana ([A - horizonte, ...]): si la entidad no tiene ahi
            # ningun paquete ni evento L7 en (A-60, A], la ventana no es registrable y la
            # pendiente nunca debio existir (se dio de alta con la atribucion de otro
            # horizonte, en el que el flujo tenia otro propietario). Se cancela con su
            # evidencia, sin decision ni PERMIT. Si la entidad SI tiene contenido, la ventana
            # era requerida y ya quedo decidida o no evaluada con su motivo (arriba).
            for window_key in [k for k in pendientes if k[1] == clave]:
                if window_key in scored_windows or window_key[0] in lp or window_key[0] in la:
                    continue
                visto = pendientes.pop(window_key)
                origen = origen_pendiente.pop(window_key, {})
                cuenta["pendientes_canceladas"] += 1
                registros_ciclo.append(incremental.registro_cancelacion(
                    window_key, ancla, corte, packets, apps, visto, origen, cycle_start, time.time()))
            if verificacion is not None:
                verificacion.write(json.dumps(incremental.comprobar_ancla(
                    extractor, v3, ancla, horizonte_s, utiles, args.sin_deduplicar, paquetes, packets,
                    apps, [x[1] for x in lineas], eve_slice_path, entity_network, paso_s, capture_start,
                    {"filas": filas_ancla, "excluidas": excluidas_ancla}, entidad_excluida,
                    puntuar=pipeline.score_samples, feature_names=feature_names)) + "\n")
                verificacion.flush()
            ancla_hecha = float(ancla)
        duplicados_espejo += quitados
        if ancla_hecha is not None:
            podar_lecturas(ancla_hecha - 60 - paso_s)
        t = cerrar_etapa("ventanas_por_ancla", t)

        # Ventanas que ya tienen datos pero cuyos PCAP aun no estan cerrados: quedan
        # pendientes (pendiente_desde mide la espera; expiran como no evaluadas).
        # Solo contabilidad (no cambia ninguna fila ni decision). No se atribuye de nuevo:
        # se usan las observaciones de la ultima atribucion (la de la ultima ancla tratada)
        # y las L7 del buffer, que no necesitan atribucion; cada entidad se recorre una vez.
        # La espera de las ventanas solo de paquetes vistas en ciclos sin anclas no se pierde:
        # pendiente_desde se completa al decidir con las marcas de lectura (visto_en).
        if anclas:
            packets_pendientes = packets
            corte_pendientes = anclas[-1] - horizonte_s
        desde_p = ancla_hecha if ancla_hecha is not None else float("-inf")
        # packets_pendientes esta en orden de tiempo (ver arriba): tramo final por biseccion.
        nuevas_p = packets_pendientes[bisect.bisect_right(packets_pendientes, desde_p - incremental.REGISTRO_S,
                                                          key=_ts):]
        nuevas_a = [o for t_e, _, lista in eve_buffer if t_e > desde_p - 60 for o in lista]
        if nuevas_p or nuevas_a:
            t_min_p = min(packets_pendientes[0].timestamp if packets_pendientes else math.inf,
                          min((x.timestamp for _, _, l in eve_buffer for x in l), default=math.inf))
            cs = min(capture_epoch, t_min_p) if t_min_p != math.inf else capture_epoch
            pp, pa = incremental.agrupar_por_entidad(nuevas_p, nuevas_a)
            for entidad in set(pp) | set(pa):
                if entidad_excluida(entidad):
                    continue
                for ancla in incremental.anclas_con_contenido(
                        (x.timestamp for x in pp.get(entidad, ())), (x.timestamp for x in pa.get(entidad, ())),
                        paso_s, desde_p, float("inf")):
                    if ancla - cs < 60:
                        continue
                    window_key = (entidad, incremental.clave_ventana(ancla))
                    if window_key not in scored_windows and window_key not in pendientes:
                        pendientes[window_key] = cycle_start
                        origen_pendiente[window_key] = {
                            "corte_incorporacion": corte_pendientes,
                            "obs_pcap_incorporacion": sum(
                                ancla - incremental.REGISTRO_S < x.timestamp <= ancla
                                for x in pp.get(entidad, ())),
                            "obs_eve_incorporacion": sum(
                                ancla - 60 < x.timestamp <= ancla for x in pa.get(entidad, ())),
                        }
                        cuenta["pendientes_nuevas"] += 1
        t = cerrar_etapa("pendientes", t)

        if decididas:

            # score_samples puntua cada fila por separado: el lote da los mismos
            # valores que una llamada por fila (comprobado bit a bit en
            # --verificar-equivalencia y en tests/test_motor_incremental.py).
            con_paquetes = [row for row, _, _, _ in decididas if row["packet_count_10s"] != 0]
            puntuaciones: dict[int, float] = {}
            if con_paquetes:
                lote = [[float(row[name]) for name in feature_names] for row in con_paquetes]
                for row, valor in zip(con_paquetes, pipeline.score_samples(lote)):
                    puntuaciones[id(row)] = float(valor)
            cuenta["puntuadas"] = len(con_paquetes)
            if volcado is not None and con_paquetes:
                for row in con_paquetes:
                    volcado.write(json.dumps({
                        "entity_ip": row["entity_ip"], "window_end_utc": row["window_end_utc"],
                        "x": [float(row[name]) for name in feature_names],
                        "score": puntuaciones[id(row)]}, sort_keys=True) + "\n")
                volcado.flush()
            t = cerrar_etapa("puntuacion", t)

            for row, pendiente_desde, excluidas_momento, historial_completo in decididas:

                # Heuristico explicito, no un ajuste silencioso del modelo
                # congelado: ocsvm_scaled nunca vio ventanas "todo ceros" en
                # el entrenamiento offline (las campanas siempre tenian algo
                # de trafico dentro de su ventana de captura), asi que las
                # puntua como fuera de distribucion y alerta en CADA ventana
                # sin trafico -- confirmado en produccion real (774/774
                # alertas iniciales eran ventanas vacias, 0 relacionadas con
                # trafico real). Silencio de red no es un ataque. Decision
                # explicita del usuario, documentada en
                # docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md.
                empty_window = (
                    row["packet_count_10s"] == 0
                    and row["http_request_count_60s"] == 0
                    and row["dns_query_count_60s"] == 0
                    and row["tls_observation_count_60s"] == 0
                )
                # Guard ampliado: ademas del caso "todo cero", CUALQUIER ventana
                # con packet_count_10s == 0 es fuera-de-distribucion para el
                # modelo. ocsvm_scaled se entreno solo con ventanas que tenian
                # paquetes L3/L4 dentro de su ventana de captura, asi que
                # puntua un vector sin paquetes (~todo ceros) como ~0.0, muy
                # por debajo del umbral -> ALERT espurio. Esto ocurre de verdad
                # con trafico legitimo: eve.json (L7) es continuo y se adelanta
                # al anillo de PCAP de tcpdump, que bufferiza antes de escribir
                # a disco; el motor puede ver el evento HTTP de una peticion
                # antes que sus paquetes -> http_request_count_60s>=1 con
                # packet_count_10s=0. Reproducido en produccion (2026-08-18): un
                # GET benigno (200) de 10.20.0.20 provoco ALERT score=0.0
                # pkts10=0 con bloqueo aplicado a un cliente legitimo. Ausencia
                # de paquetes no es un ataque; los paquetes reales de cualquier
                # ataque SI caen en ventanas con pkts10>0, que se siguen
                # puntuando y bloqueando. No se toca el modelo ni el umbral.
                # Ver docs/fase05-motor-tiempo-real/02-fp-ventana-sin-paquetes.md.
                no_live_packets = row["packet_count_10s"] == 0
                detector_name = args.detector_name
                if no_live_packets:
                    # El MODELO no se puntua sin paquetes L3/L4 (seria un ALERT
                    # espurio, ver arriba), pero la senal L7 de eve.json SI es
                    # valida aunque el anillo de PCAP aun no haya volcado los
                    # paquetes -- el heuristico de fuerza bruta, que depende solo
                    # de features L7 de 60s, se evalua igual mas abajo.
                    score = None
                    decision = "PERMIT"
                    detector_name = (
                        "empty_window_heuristic"
                        if empty_window
                        else "no_live_packets_heuristic"
                    )
                else:
                    score = puntuaciones[id(row)]
                    decision = "ALERT" if score < threshold else "PERMIT"

                # Heuristico complementario, no un reemplazo del modelo: la
                # evaluacion bloqueada real midio que ocsvm_scaled es el mas
                # debil de los 7 modelos comparados justo en fuerza
                # bruta/password-spray (50-55% de deteccion, ver
                # docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md). Si la
                # decision vigente es PERMIT pero la ventana ya tiene una firma
                # clara de fuerza bruta (>=5 peticiones HTTP en 60s, >=80% con
                # 401/403), se escala a ALERT sin tocar el score ni el umbral del
                # modelo. Se evalua tanto tras el modelo (pkts10>0) COMO en las
                # ventanas no_live_packets: sus features son L7 (eve.json), que
                # son validas aunque el PCAP aun no haya volcado los paquetes del
                # ataque, asi que una rafaga rapida de 401 se detecta sin esperar
                # al vuelco del anillo. Un GET benigno aislado (http60=1<5) nunca
                # dispara esto, asi que el FP de ventana sin paquetes sigue
                # corregido. Umbrales por criterio razonado (mismo patron que el
                # MVP anterior, 5 intentos en 60s), NO calibrados
                # estadisticamente como el umbral del modelo -- documentado como
                # tal, no se disfraza de rigor que no tiene.
                if (
                    decision == "PERMIT"
                    and row["http_request_count_60s"] >= AUTH_FAILURE_MIN_REQUESTS
                    and row["http_auth_failure_ratio_60s"] >= AUTH_FAILURE_MIN_RATIO
                ):
                    decision = "ALERT"
                    detector_name = "auth_failure_heuristic"

                # Etapa 3: los heuristicos leen una COPIA de la fila con la vista DNS; la
                # fila del IF (y su puntuacion, ya calculada) no cambia.
                campos_dns = vista_dns.campos(
                    row["entity_ip"], extractor.parse_eve_timestamp(row["window_end_utc"]))
                fila_h = dict(row)
                fila_h.update(campos_dns)
                record = {
                    "event": "decision",
                    "excluidas_acumulado": excluidas_momento,
                    "plano_control_descartado": descartados_plano_control,
                    "pcaps_ilegibles": pcaps_ilegibles,
                    "pcaps_ilegibles_motivo": motivos_ilegibles or None,
                    "duplicados_espejo": duplicados_espejo,
                    "decidido_en": time.time(),
                    "entity_ip": row["entity_ip"],
                    "window_end_utc": row["window_end_utc"],
                    "history_coverage_s": row["history_coverage_s"],
                    # Horizonte de entrada fijado por ventana (cierre de la Etapa 2): la
                    # fila usa [ventana - horizonte_s, ventana]. historial_completo=false si
                    # ese horizonte empieza antes de que el proceso tuviera historia
                    # completa de PCAP y EVE (arranque sin recuperacion posible).
                    "horizonte_s": horizonte_s,
                    "historial_completo": historial_completo,
                    "packet_count_10s": row["packet_count_10s"],
                    "detector_name": detector_name,
                    "score": score,
                    "threshold": threshold,
                    "decision": decision,
                    # Veredicto de los heuristicos deterministas (brute-force,
                    # port-scan, http-abuse, dns-entropy). Es ADITIVO: no cambia
                    # `decision` (que sigue siendo ALERT/PERMIT, calibracion
                    # intacta); lo consume publicar_feed.py para derivar LIMIT/BLOCK
                    # sin tocar el modelo. None si ningun heuristico dispara.
                    "heuristico": heuristicos.evaluar(fila_h),
                    # Todas las reglas que disparan (Etapa 2: destinos separados).
                    "heuristicos": heuristicos.evaluar_todas(fila_h),
                    # Etapa 3: magnitudes de la vista DNS usadas por dns_entropy (no son entradas del IF).
                    "dns_vista": campos_dns if (campos_dns["dnsh_consultas_60s"]
                                                or campos_dns["dnsh_reenvios_excluidos_60s"]) else None,
                    # Disponibilidad de las fuentes al decidir. logged_at (lo pone
                    # escribir_registros) sigue siendo el instante de escritura; pendiente_desde (ciclo en que la ventana se vio
                    # por primera vez sin sus paquetes, o null) permite medir la espera.
                    "inicio_ciclo": cycle_start,
                    "marca_pcap": marca_pcap,
                    "marca_eve": marca_eve,
                    "pendiente_desde": pendiente_desde,
                    # Identificadores para la cadena por eventos (Etapa 2): la
                    # decision es unica por (entidad, ventana); el ciclo la situa.
                    "decision_id": "%s|%s" % (row["entity_ip"], row["window_end_utc"]),
                    "ciclo_n": ciclo_n,
                    "disparo": motivo_disparo,
                }
                # decision == "ALERT" solo ocurre por (modelo con pkts10>0) o
                # (heuristico de fuerza bruta sobre L7); ambos son bloqueos
                # legitimos. Las ventanas vacias / sin paquetes son PERMIT salvo
                # que el heuristico dispare, en cuyo caso SI se debe bloquear
                # (rafaga de 401 detectada por L7 antes del vuelco del PCAP).
                if args.enforce and decision == "ALERT":
                    record["enforcement"] = apply_enforcement(
                        args.enforce_command, row["entity_ip"], args.block_timeout_seconds
                    )

                # Se escribe una vez por ciclo (abajo), no abriendo el fichero en cada decision.
                registros_ciclo.append(record)
                cuenta["decididas"] += 1
            t = cerrar_etapa("decision_y_registro", t)

        # Una ventana pendiente nunca desaparece en silencio: si sus paquetes no llegan
        # a tiempo (captura parada, PCAP ilegible...) se registra como no evaluada.
        # Si los PCAP SI la cubren pero build_rows ya no la genera (solo existia por
        # observaciones viejas de la entidad que la poda a history_seconds saco del
        # buffer), el motivo es otro: se distingue para no culpar a la captura.
        for window_key, visto in list(pendientes.items()):
            if window_key in scored_windows:
                del pendientes[window_key]
                origen_pendiente.pop(window_key, None)
                continue
            window_end = extractor.parse_eve_timestamp(window_key[1])
            tratada = ancla_hecha is not None and window_end <= ancla_hecha
            if not tratada and cycle_start - window_end <= limite_pendiente:
                continue
            del pendientes[window_key]
            origen = origen_pendiente.pop(window_key, {})
            # Tras la cancelacion en su ancla, una pendiente tratada solo puede llegar aqui
            # si la entidad tenia contenido y aun asi no hubo registro: seria un fallo real
            # de regeneracion y se sigue registrando como tal (ventana_no_regenerada).
            motivo = ("ventana_no_regenerada" if ventana_completa(window_end, marca_pcap)
                      else "pcap_incompleto")
            scored_windows[window_key] = window_end
            cuenta["no_evaluadas"] += 1
            registros_ciclo.append({
                "event": "ventana_no_evaluada",
                "decidido_en": time.time(),
                "entity_ip": window_key[0],
                "window_end_utc": window_key[1],
                "motivo": motivo,
                "corte_incorporacion": origen.get("corte_incorporacion"),
                "pendiente_desde": visto,
                "inicio_ciclo": cycle_start,
                "marca_pcap": marca_pcap,
                "marca_eve": marca_eve,
                "pcaps_ilegibles": pcaps_ilegibles,
            })
        registro_escrito_en = escribir_registros(args.log_path, registros_ciclo)
        t = cerrar_etapa("expiracion_y_escritura", t)

        # Un registro por ciclo, incluidos los que no deciden nada: distingue un
        # ciclo sin ventanas completas de un procesamiento tardio o de una
        # ventana perdida, cosa que motor_decision.log solo deja inferir.
        fin_ciclo = time.time()
        try:
            with ciclos_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "event": "ciclo",
                    "ciclo_n": ciclo_n,
                    "disparo": motivo_disparo,
                    "inicio_ciclo": cycle_start,
                    "fin_ciclo": fin_ciclo,
                    "registro_escrito_en": registro_escrito_en,
                    "registros_escritos": len(registros_ciclo),
                    "duracion_s": round(time.perf_counter() - t_ciclo, 4),
                    "etapas_s": etapas,
                    "marca_pcap": marca_pcap,
                    "marca_pcap_avanzo": marca_pcap != marca_pcap_previa,
                    "marca_eve": marca_eve,
                    "pcaps_nuevos": pcaps_nuevos,
                    "lineas_eve_nuevas": lineas_eve_nuevas,
                    "paquetes_anillo": len(packet_buffer),
                    "paquetes_deduplicados": len(paquetes),
                    "observaciones_paquete": len(packets),
                    "observaciones_l7": len(apps),
                    "ventanas_pendientes": len(pendientes),
                    **{k: cuenta.get(k, 0) for k in (
                        "entidades", "filas_construidas", "decididas", "puntuadas",
                        "pendientes_nuevas", "pendientes_canceladas", "no_evaluadas", "no_elegibles",
                        "excluidas_nuevas", "flujos_recalculados")},
                }, sort_keys=True) + "\n")
        except OSError:
            pass  # la instrumentacion nunca para el motor

        motivo_disparo = esperar_siguiente_ciclo(args, cycle_start, parsed_pcaps)
        ciclo_n += 1


if __name__ == "__main__":
    raise SystemExit(main())
