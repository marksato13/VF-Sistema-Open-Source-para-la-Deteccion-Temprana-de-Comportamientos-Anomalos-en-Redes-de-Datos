#!/usr/bin/env python3
"""Generador de la campaña (corre en la Kali del laboratorio autorizado).

Valida la configuración congelada, ordena los episodios con la semilla fija, respeta calentamiento,
contexto previo y observación posterior, y registra inicio y fin por separado (reloj de pared + monotónico),
con la salida COMPLETA de cada episodio.

SEGURO POR DEFECTO: sin --autorizado solo simula (no lanza tráfico). Aborta si la config no valida o quedan
marcadores/valores sin resolver en un escenario habilitado. Las variables de entorno NO cambian parámetros.

Uso (cuando se autorice la campaña A):
    python3 generar_campana.py --config ../escenarios/escenarios.json --salida-dir ./corrida --autorizado

COMPUERTA DE PERMISO (Etapa 4, --permiso): antes del contexto previo de cada episodio y otra vez justo antes de
lanzarlo se lee un fichero de permiso que escribe la vigilancia del bastión (vigia_4c.py). Solo se lanza con un
permiso VÁLIDO: JSON legible, nonce de esta corrida, emitido después del arranque, no caducado y estado
"continuar". Cualquier otra cosa (pausa, fichero ausente, caducado, de otra corrida) es PAUSA: el episodio no se
lanza y se espera. "cancelar", o más de --permiso-max-espera s sin permiso válido, detiene la batería. Al reanudar se
rehace el contexto previo y se lanza el SIGUIENTE episodio del orden publicado (no se repite ni se reordena).
Sin --permiso el comportamiento es el de antes (campañas 2026-10 y 3B).
"""
from __future__ import annotations
import argparse, json, os, random, signal, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import esquema_campana as esq  # noqa: E402


def reloj() -> dict:
    return {"pared_utc": datetime.now(timezone.utc).isoformat(), "monotonico": round(time.monotonic(), 6)}


def jsonl(fh, obj):
    fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def plan_orden(cfg: dict) -> list[tuple[dict, int]]:
    plan = [(s, r) for r in range(1, cfg["repeticiones"] + 1) for s in cfg["escenarios"]]
    random.Random(cfg["semilla"]).shuffle(plan)
    return plan


def leer_permiso(ruta: Path, nonce: str, arranque: float, ahora: float) -> tuple[str, str]:
    """(estado, motivo). estado: 'continuar' solo si el permiso es válido; 'cancelar'; o 'pausa' en otro caso."""
    try:
        p = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "pausa", "sin fichero de permiso"
    except (OSError, ValueError) as ex:
        return "pausa", f"permiso ilegible: {ex.__class__.__name__}"
    if not isinstance(p, dict) or p.get("nonce") != nonce:
        return "pausa", "permiso de otra corrida (nonce distinto)"
    try:
        emitido, valido = float(p["emitido_epoch"]), float(p["valido_hasta_epoch"])
    except (KeyError, TypeError, ValueError):
        return "pausa", "permiso sin emitido_epoch/valido_hasta_epoch"
    causas = "; ".join(str(c) for c in p.get("causas") or [])
    if p.get("estado") == "cancelar":            # una cancelación vale aunque haya caducado
        return "cancelar", causas or "cancelada por la vigilancia"
    if emitido < arranque - 5:
        return "pausa", "permiso emitido antes del arranque de esta corrida"
    if ahora > valido:
        return "pausa", f"permiso caducado hace {ahora - valido:.0f} s (vigilancia sin renovar)"
    if p.get("estado") != "continuar":
        return "pausa", causas or f"estado {p.get('estado')!r}"
    return "continuar", ""


class Compuerta:
    """Espera hasta tener permiso válido. Registra pausa/reanudación/cancelación en marcas.jsonl."""

    def __init__(self, ruta: Path, nonce: str, max_espera: float, sondeo: float, marcas, arranque: float):
        self.ruta, self.nonce, self.max_espera, self.sondeo = ruta, nonce, max_espera, sondeo
        self.marcas, self.arranque = marcas, arranque

    def esperar(self, siguiente: str, punto: str) -> tuple[str, bool]:
        """('continuar'|'cancelar', hubo_pausa). Sin permiso válido no devuelve 'continuar'."""
        inicio_pausa, motivo_ant = None, None
        while True:
            ahora = time.time()
            estado, motivo = leer_permiso(self.ruta, self.nonce, self.arranque, ahora)
            if estado == "continuar":
                if inicio_pausa is not None:
                    jsonl(self.marcas, {"evento": "reanudacion", "siguiente": siguiente, "punto": punto,
                                        "pausa_s": round(ahora - inicio_pausa, 3), "reloj": reloj()})
                    print(f"REANUDA tras {ahora - inicio_pausa:.0f} s; siguiente {siguiente}", flush=True)
                return "continuar", inicio_pausa is not None
            if estado == "cancelar":
                jsonl(self.marcas, {"evento": "cancelacion", "siguiente_no_lanzado": siguiente, "punto": punto,
                                    "causa": motivo, "reloj": reloj()})
                print(f"CANCELADA por la vigilancia: {motivo}", flush=True)
                return "cancelar", inicio_pausa is not None
            if inicio_pausa is None:
                inicio_pausa = ahora
            if motivo != motivo_ant:
                jsonl(self.marcas, {"evento": "pausa", "siguiente": siguiente, "punto": punto, "motivo": motivo,
                                    "reloj": reloj()})
                print(f"PAUSA antes de {siguiente} ({punto}): {motivo}", flush=True)
                motivo_ant = motivo
            if ahora - inicio_pausa > self.max_espera:
                causa = f"sin permiso válido durante más de {self.max_espera:.0f} s (último motivo: {motivo})"
                jsonl(self.marcas, {"evento": "cancelacion", "siguiente_no_lanzado": siguiente, "punto": punto,
                                    "causa": causa, "reloj": reloj()})
                print(f"CANCELADA: {causa}", flush=True)
                return "cancelar", True
            time.sleep(self.sondeo)


def correr_episodio(cfg, s, rep, salida_dir: Path, marcas, autorizado: bool) -> str:
    sid = s["id"]
    ep_id = f"{sid}-r{rep}"
    cmd = esq.comando_de(cfg, s)
    (salida_dir / "salidas").mkdir(exist_ok=True)
    out_p = salida_dir / "salidas" / f"{ep_id}.out"
    err_p = salida_dir / "salidas" / f"{ep_id}.err"
    # inicio: se escribe INMEDIATAMENTE y por separado del fin
    jsonl(marcas, {"evento": "inicio", "campana": cfg.get("_campana", "deteccion-respuesta-2026-10-26"),
                   "episodio_id": ep_id, "escenario": sid, "repeticion": rep,
                   "destino": s["destino"], "servicio": s["servicio"], "comando": cmd,
                   "timeout_s": s["timeout_s"], "reloj": reloj()})
    if not autorizado:
        return "simulado"
    estado, cod = "completo", None
    kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
            try:
                proc = subprocess.Popen(cmd, stdout=fo, stderr=fe, **kw)
            except OSError as ex:                       # fallo al INICIAR el proceso
                jsonl(marcas, {"evento": "fin", "episodio_id": ep_id, "estado": "error_inicio",
                               "error": str(ex), "reloj": reloj()})
                return "error_inicio"
            pgid = None if os.name == "nt" else os.getpgid(proc.pid)   # se captura AL CREAR, no al matar
            try:
                proc.wait(timeout=s["timeout_s"])
            except subprocess.TimeoutExpired:
                estado = "incompleto_timeout"
            except KeyboardInterrupt:
                estado = "incompleto_interrumpido"
            finally:
                _terminar(proc, pgid)
                if not _grupo_terminado(proc, pgid):
                    estado = (estado if estado != "completo" else "incompleto") + "+grupo_no_terminado"
        cod = proc.poll()
    except KeyboardInterrupt:
        estado = "incompleto_interrumpido"
        _terminar(proc, pgid)
        if not _grupo_terminado(proc, pgid):
            estado += "+grupo_no_terminado"
        cod = proc.poll()
    if estado == "completo" and cod not in (0, None):   # un comando con código != 0 NO es 'completo'
        estado = f"incompleto_error_rc_{cod}"
    intentos = _leer_intentos(out_p)
    jsonl(marcas, {"evento": "fin", "episodio_id": ep_id, "estado": estado, "codigo_salida": cod,
                   "reloj": reloj(), "bytes_stdout": out_p.stat().st_size, "bytes_stderr": err_p.stat().st_size,
                   "intentos_generador": intentos,
                   "intentos_fuente": ("contador de iteraciones del bucle (INTENTOS, no peticiones enviadas ni "
                                       "respuestas)" if intentos is not None else "nmap: su stdout"),
                   "medida_real_en": "peticiones/respuestas/errores/timeouts se miden con PCAP/EVE/servidor",
                   "salida_stdout": str(out_p), "salida_stderr": str(err_p)})
    return estado


def _leer_intentos(out_p: Path):
    """Lee 'intentos=<N>' (iteraciones del bucle) que imprime el comando. None si no lo produce (p.ej. nmap)."""
    try:
        for linea in reversed(out_p.read_text(encoding="utf-8", errors="replace").splitlines()):
            if linea.startswith("intentos="):
                return int(linea.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    return None


def _terminar(proc, pgid):
    """Termina el proceso y TODO su grupo, aunque el padre ya haya terminado (usa el pgid capturado al crear)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):        # SIGKILL no se puede ignorar
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            break
        time.sleep(0.5 if sig == signal.SIGTERM else 1.5)
    try:
        proc.wait(timeout=10)                            # recoge al padre (evita zombie)
    except subprocess.TimeoutExpired:
        pass


def _grupo_terminado(proc, pgid) -> bool:
    """True si no queda ningún proceso vivo en el grupo. En Windows, aproxima con el padre."""
    if os.name == "nt":
        return proc.poll() is not None
    try:
        os.killpg(pgid, 0)        # señal 0: solo comprueba existencia de procesos en el grupo
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--salida-dir", default="corrida")
    ap.add_argument("--autorizado", action="store_true", help="lanza tráfico real; sin esto, simula")
    ap.add_argument("--solo-habilitados", action="store_true",
                    help="omite (sin abortar) los escenarios con habilitado:false; sin esto, un escenario "
                         "deshabilitado o no resuelto aborta")
    ap.add_argument("--permiso", type=Path, help="fichero de permiso de la vigilancia (Etapa 4); exige --nonce")
    ap.add_argument("--nonce", help="identificador de ESTA corrida; un permiso con otro nonce no vale")
    ap.add_argument("--permiso-max-espera", type=float, default=1800.0,
                    help="s seguidos sin permiso válido tras los que se cancela (pérdida de la vigilancia)")
    ap.add_argument("--permiso-sondeo", type=float, default=5.0, help="s entre lecturas del permiso en pausa")
    a = ap.parse_args(argv)
    if a.permiso and not a.nonce:
        print("--permiso exige --nonce", file=sys.stderr)
        return 2
    arranque = time.time()
    cfg = json.load(open(a.config, encoding="utf-8"))

    problemas = esq.validar(cfg, exigir_herramientas=a.autorizado)
    activos = [s for s in cfg["escenarios"] if s.get("habilitado")]
    pendientes = [s for s in cfg["escenarios"] if not s.get("habilitado")]
    if pendientes and not a.solo_habilitados:
        problemas += [f"escenario {s['id']} deshabilitado: {s.get('motivo_deshabilitado','?')} "
                      f"(usa --solo-habilitados para omitirlo)" for s in pendientes]
    if problemas:
        print("CONFIG INVÁLIDA — abortando. Problemas:", file=sys.stderr)
        for p in problemas:
            print("  -", p, file=sys.stderr)
        return 2

    sd = Path(a.salida_dir)
    sd.mkdir(parents=True, exist_ok=True)
    # registra la config EFECTIVA tal como se usó (solo los habilitados que se correrán)
    efectiva = dict(cfg)
    efectiva["escenarios"] = activos
    efectiva["_efectiva_utc"] = datetime.now(timezone.utc).isoformat()
    efectiva["_autorizado"] = a.autorizado
    (sd / "config-efectiva.json").write_text(json.dumps(efectiva, ensure_ascii=False, indent=1), encoding="utf-8")

    plan = [(s, r) for (s, r) in plan_orden(cfg) if s.get("habilitado")]
    modo = "AUTORIZADO (lanza tráfico)" if a.autorizado else "SIMULACIÓN (no lanza tráfico)"
    t = cfg["tiempos_s"]
    print(f"{modo} · {len(plan)} episodios · calentamiento {t['calentamiento_inicial']} s · "
          f"contexto previo {t['contexto_antes']} s · observación {t['observacion_despues']} s")
    marcas = open(sd / "marcas.jsonl", "a", encoding="utf-8")
    jsonl(marcas, {"evento": "campana_inicio", "modo": modo, "orden": [f"{s['id']}-r{r}" for s, r in plan],
                   "nonce": a.nonce, "permiso": str(a.permiso) if a.permiso else None, "reloj": reloj()})
    comp = (Compuerta(a.permiso, a.nonce, a.permiso_max_espera, a.permiso_sondeo, marcas, arranque)
            if a.permiso else None)
    if a.autorizado:
        time.sleep(t["calentamiento_inicial"])
    fin_estado = "completa"
    contexto_hecho = False   # el contexto previo del primer episodio se hace dentro del bucle (tras la compuerta)
    try:
        for n, (s, rep) in enumerate(plan, 1):
            ep = f"{s['id']}-r{rep}"
            if comp is not None:
                # 1) antes del contexto previo; 2) justo antes de lanzar. Tras una pausa se rehace el contexto.
                while True:
                    if not contexto_hecho:
                        r, _ = comp.esperar(ep, "antes_del_contexto")
                        if r == "cancelar":
                            break
                        if a.autorizado:
                            time.sleep(t["contexto_antes"])
                    r, pausado = comp.esperar(ep, "antes_del_lanzamiento")
                    if r == "cancelar" or not pausado:
                        break
                    contexto_hecho = False   # hubo pausa justo antes de lanzar: contexto nuevo
                if r == "cancelar":
                    fin_estado = "cancelada"
                    break
            elif a.autorizado and not contexto_hecho:
                time.sleep(t["contexto_antes"])
            contexto_hecho = False
            print(f"[{n}/{len(plan)}] {ep}: {' '.join(esq.comando_de(cfg, s)[:3])}…")
            estado = correr_episodio(cfg, s, rep, sd, marcas, a.autorizado)
            print(f"        -> {estado}")
            if "grupo_no_terminado" in estado:
                # no se pudo asegurar la terminación: NO iniciar otro episodio con un generador quizá vivo
                fin_estado = "abortada_grupo_no_terminado"
                print("ABORTA: no se aseguró la terminación del grupo; no se inicia el siguiente episodio", flush=True)
                break
            if estado == "incompleto_interrumpido":
                # tras una interrupción: detener la campaña y recoger registros; NO seguir con el siguiente
                fin_estado = "interrumpida"
                break
            if a.autorizado:
                time.sleep(t["observacion_despues"])        # cola/observación del episodio actual
                # la historia previa del siguiente se hace al principio de su vuelta (tras la compuerta, si la hay)
    except KeyboardInterrupt:
        fin_estado = "interrumpida"
        print("interrumpida: se detiene la campaña y se recogen los registros", flush=True)
    jsonl(marcas, {"evento": "campana_fin", "estado": fin_estado, "reloj": reloj()})
    marcas.close()
    return 0 if fin_estado == "completa" else (3 if fin_estado == "cancelada" else 130)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("interrumpido", file=sys.stderr)
        raise SystemExit(130)
