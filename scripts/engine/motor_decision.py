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
whitelist interna (nunca confia solo en el llamador). Solo hay UN umbral
calibrado (PM-multilayer-v2-v1); no existe un nivel intermedio tipo LIMIT
todavia porque eso exigiria un segundo umbral sin calibrar -- se documenta
como limitacion, no se inventa un numero.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "features"))

import extract_multilayer_v2 as extractor  # noqa: E402

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
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--step-seconds", type=int, default=10)
    parser.add_argument("--history-seconds", type=int, default=110)
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

    def __init__(self, path: Path) -> None:
        self.path = path
        # Arranca en el final del archivo (como "tail -f"), no en el byte 0.
        # eve.json de Suricata es un unico archivo continuo que puede llevar
        # horas/dias acumulando lineas; empezar en offset 0 releeria todo su
        # historial en el primer ciclo (costoso e irrelevante, ya que
        # build_rows solo usa la ventana reciente igualmente).
        try:
            stat_result = path.stat()
            self._offset = stat_result.st_size
            self._inode = (stat_result.st_dev, stat_result.st_ino)
        except FileNotFoundError:
            self._offset = 0
            self._inode = None
        self._partial = b""

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


def list_closed_pcap_files(capture_dir: Path, pattern: str) -> list[Path]:
    files = sorted(capture_dir.glob(pattern))
    return files[:-1] if len(files) > 1 else []


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

    state_dir = args.state_dir or (args.log_path.parent / "_state")
    state_dir.mkdir(parents=True, exist_ok=True)
    eve_slice_path = state_dir / "eve_window.jsonl"

    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    tail = EveTail(args.eve_path)
    eve_buffer: collections.deque[tuple[float, str]] = collections.deque()
    scored_windows: dict[tuple[str, str], float] = {}

    startup_record = {
        "event": "motor_startup",
        "timestamp": time.time(),
        "model_path": str(args.model_path),
        "manifest_path": str(manifest_path),
        "detector_name": args.detector_name,
        "threshold": threshold,
        "entity_network": str(entity_network),
        "capture_dir": str(args.capture_dir),
        "eve_path": str(args.eve_path),
        "step_seconds": args.step_seconds,
        "history_seconds": args.history_seconds,
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

    while True:
        cycle_start = time.time()

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
            eve_buffer.append((event_time, raw_line))

        cutoff = cycle_start - args.history_seconds
        while eve_buffer and eve_buffer[0][0] < cutoff:
            eve_buffer.popleft()
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

        with eve_slice_path.open("w", encoding="utf-8") as handle:
            for _, raw_line in eve_buffer:
                handle.write(raw_line + "\n")

        pcap_files = list_closed_pcap_files(args.capture_dir, args.capture_glob)

        if pcap_files or eve_buffer:
            packets = extractor.load_packet_observations(pcap_files, entity_network) if pcap_files else []
            apps = (
                extractor.load_app_observations(eve_slice_path, entity_network)
                if eve_buffer
                else []
            )
            observation_timestamps = [item.timestamp for item in packets] + [
                item.timestamp for item in apps
            ]
            if observation_timestamps:
                # capture_epoch es un piso fijo (arranque del proceso), pero el
                # anillo de captura sigue corriendo aunque el motor se
                # reinicie -- puede haber paquetes reales mas viejos que ese
                # piso. build_rows() exige capture_start <= primera
                # observacion real; usar el minimo respeta esa invariante Y
                # aprovecha historia genuina ya existente en vez de
                # descartarla en cada reinicio del proceso de scoring.
                effective_capture_start = min(capture_epoch, min(observation_timestamps))
                rows = extractor.build_rows(
                    "motor-live",
                    packets,
                    apps,
                    step_seconds=args.step_seconds,
                    capture_start=effective_capture_start,
                )
            else:
                rows = []

            for row in rows:
                window_key = (str(row["entity_ip"]), str(row["window_end_utc"]))
                if window_key in scored_windows:
                    continue
                if not row["eligible_training"]:
                    continue
                scored_windows[window_key] = extractor.parse_eve_timestamp(row["window_end_utc"])

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
                detector_name = args.detector_name
                if empty_window:
                    score = None
                    decision = "PERMIT"
                    detector_name = "empty_window_heuristic"
                else:
                    feature_vector = [[float(row[name]) for name in feature_names]]
                    score = float(pipeline.score_samples(feature_vector)[0])
                    decision = "ALERT" if score < threshold else "PERMIT"

                    # Heuristico complementario, no un reemplazo del modelo: la
                    # evaluacion bloqueada real midio que ocsvm_scaled es el
                    # mas debil de los 7 modelos comparados justo en fuerza
                    # bruta/password-spray (50-55% de deteccion, ver
                    # docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md).
                    # Si el modelo dice PERMIT pero la ventana ya tiene una
                    # firma clara de fuerza bruta (>=5 peticiones HTTP en 60s,
                    # >=80% con 401/403), se escala a ALERT sin tocar el score
                    # ni el umbral del modelo. Umbrales elegidos por criterio
                    # razonado (mismo patron que el MVP anterior, 5 intentos
                    # en 60s), NO calibrados estadisticamente como el umbral
                    # del modelo -- documentado como tal, no se disfraza de
                    # rigor que no tiene.
                    if (
                        decision == "PERMIT"
                        and row["http_request_count_60s"] >= AUTH_FAILURE_MIN_REQUESTS
                        and row["http_auth_failure_ratio_60s"] >= AUTH_FAILURE_MIN_RATIO
                    ):
                        decision = "ALERT"
                        detector_name = "auth_failure_heuristic"

                record = {
                    "event": "decision",
                    "logged_at": time.time(),
                    "entity_ip": row["entity_ip"],
                    "window_end_utc": row["window_end_utc"],
                    "history_coverage_s": row["history_coverage_s"],
                    "packet_count_10s": row["packet_count_10s"],
                    "detector_name": detector_name,
                    "score": score,
                    "threshold": threshold,
                    "decision": decision,
                }
                if args.enforce and decision == "ALERT" and not empty_window:
                    record["enforcement"] = apply_enforcement(
                        args.enforce_command, row["entity_ip"], args.block_timeout_seconds
                    )

                with args.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                if decision == "ALERT":
                    print(json.dumps(record, sort_keys=True), flush=True)

        elapsed = time.time() - cycle_start
        time.sleep(max(0.5, args.step_seconds - elapsed))


if __name__ == "__main__":
    raise SystemExit(main())
