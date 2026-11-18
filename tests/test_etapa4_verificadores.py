"""Banco de los verificadores de la 4A (verif_estado.py 2026-11-06.1, verificar_bastion.sh, verificar_sensor1.sh).

Cada caso monta un estado FALSO pero completo (systemctl falso que imprime «systemctl show», raíz /proc falsa con
mountinfo, btime, stat y cmdline de cada proceso, registros del motor actuales y rotados .1/.N.gz y un manifiesto)
y comprueba el código de salida y la línea OK/FALLO. Los valores del motor son los REALES del Sensor1 (PID 1384,
inicio 1793923142.37, motor_startup en motor_decision.log.1 a 1793923143.83743, arranques antiguos en .2.gz a
1793758269.35 y 1793772769.39): así se reproducen como regresión los tres FALLO falsos publicados (docs da4c3a0,
evidencia/06-observacion/verif-post.txt).

Principio que se comprueba en todos los casos de error: una lectura fallida nunca da OK.
Requiere Linux (os.sysconf, /proc propio); en Windows se omite.
"""
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[1]
E4 = RAIZ_REPO / "deploy" / "etapa4"
VE = E4 / "comun" / "verif_estado.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32" or shutil.which("bash") is None,
                                reason="banco Linux (os.sysconf, /proc, bash)")

UMBRAL = -0.5693969936322356
BTIME = 1793900000
INICIO_MOTOR = 1793923142.37            # inicio real del PID 1384 (05-nov 23:59:02Z)
T_ARRANQUE = 1793923143.83743           # su motor_startup (en motor_decision.log.1 tras la rotación)
T_ANTIGUOS = (1793758269.35, 1793772769.39)  # arranques de procesos anteriores (en .2.gz)
PID_MOTOR = 1384

# ------------------------------------------------------------------ systemctl falso
SYSTEMCTL = r'''#!/usr/bin/env python3
import json, os, sys
cfg = json.load(open(os.environ["CF_FAKE_SC"]))
a = sys.argv[1:]
with open(os.environ["CF_FAKE_SC"] + ".log", "a") as f:
    f.write(" ".join(a) + "\n")
orden = a[0] if a else ""
uni = [x for x in a[1:] if not x.startswith("-") and (a[a.index(x) - 1] != "-p")]
nombre = uni[0] if uni else ""
if nombre in cfg.get("falla", []) or orden in cfg.get("falla_orden", []):
    sys.stderr.write("Failed to connect to bus: No such file or directory\n"); sys.exit(1)
u = cfg["unidades"].get(nombre) or cfg["unidades"].get(nombre + ".service") or {
    "LoadState": "not-found", "ActiveState": "inactive", "SubState": "dead", "UnitFileState": "", "MainPID": "0"}
if orden == "show":
    if nombre in cfg.get("salida_vacia", []):
        sys.exit(0)
    for k in ("LoadState", "ActiveState", "SubState", "UnitFileState", "MainPID"):
        if k in u:
            print(f"{k}={u[k]}")
    sys.exit(0)
if orden == "is-active":
    sys.exit(0 if u.get("ActiveState") == "active" else 3)
if orden == "cat":
    if "cat" not in u:
        sys.exit(1)
    print(u["cat"]); sys.exit(0)
sys.exit(2)
'''

TIMEDATECTL = "#!/bin/sh\necho yes\n"


def unidad(activo, fichero, pid=0, carga="loaded", **extra):
    d = {"LoadState": carga, "ActiveState": "active" if activo else "inactive",
         "SubState": "running" if activo else "dead", "UnitFileState": fichero, "MainPID": str(pid)}
    d.update(extra)
    return d


class Banco:
    def __init__(self, tmp):
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir()
        for n, txt in (("systemctl", SYSTEMCTL), ("timedatectl", TIMEDATECTL)):
            p = self.bin / n
            p.write_text(txt)
            p.chmod(0o755)
        self.sc = tmp / "systemctl.json"
        self.cfg = {"unidades": {}, "falla": []}
        self.proc = tmp / "proc"
        (self.proc / "self").mkdir(parents=True)
        self.montaje("rw,nosuid,nodev,noexec,relatime")
        (self.proc / "stat").write_text(f"cpu  1 2 3\nbtime {BTIME}\nprocesses 9\n")
        self.proceso(1, ["/sbin/init"], BTIME + 1.0)
        self.log = tmp / "home" / "cyberflow" / "logs" / "motor_decision.log"
        self.manifiesto = tmp / "manifest-if-limpio-2026-10.json"

    def montaje(self, opciones):
        (self.proc / "self" / "mountinfo").write_text(
            f"22 28 0:5 / /proc {opciones} shared:12 - proc proc rw\n"
            "23 28 0:21 / /sys rw,nosuid shared:2 - sysfs sysfs rw\n")

    def proceso(self, pid, argv, inicio):
        d = self.proc / str(pid)
        d.mkdir(exist_ok=True)
        tic = round((inicio - BTIME) * os.sysconf("SC_CLK_TCK"))
        campos = ["S"] + ["0"] * 18 + [str(tic)] + ["0"] * 5
        (d / "stat").write_text(f"{pid} ({os.path.basename(argv[0])[:15]}) " + " ".join(campos) + "\n")
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")

    def entorno(self):
        self.sc.write_text(json.dumps(self.cfg))
        return dict(os.environ, CF_BANCO="1", CF_VERIF_SYSTEMCTL=str(self.bin / "systemctl"),
                    CF_VERIF_PROC=str(self.proc), CF_FAKE_SC=str(self.sc),
                    PATH=f"{self.bin}:{os.environ['PATH']}", HOME=str(self.tmp / "home"))

    def ve(self, *args):
        r = subprocess.run([sys.executable, "-I", str(VE), *args], capture_output=True, text=True,
                           env=self.entorno(), timeout=60)
        return r.returncode, r.stdout + r.stderr


@pytest.fixture
def banco(tmp_path):
    return Banco(tmp_path)


# ------------------------------------------------------------------ v1 retirado
V1_S1 = ("v1-retirado", "--unidad", "ppi-publicar-feed.timer", "--unidad", "ppi-publicar-feed.service",
         "--proceso", "publicar_feed.py")
V1_B = ("v1-retirado", "--unidad", "ppi-relay-feed.timer", "--unidad", "ppi-relay-feed.service",
        "--proceso", "relay-feed.sh")


def v1_retirado_real(b, timer="ppi-publicar-feed.timer", servicio="ppi-publicar-feed.service"):
    """Estado observado el 06-nov en Sensor1 y bastión: timer disabled/inactive, servicio static/inactive, PID 0."""
    b.cfg["unidades"][timer] = unidad(False, "disabled")
    b.cfg["unidades"][servicio] = unidad(False, "static")


def test_v1_retirado_correctamente_sensor1(banco):
    v1_retirado_real(banco)
    banco.proceso(1386, ["/home/m4rk/cyberflow/.venv/bin/python",
                         "/home/m4rk/cyberflow-e4/ec78ca5/scripts/engine/publicar_feed_v2.py"], BTIME + 10)
    rc, out = banco.ve(*V1_S1)
    assert rc == 0, out
    assert out.count("OK    ") == 3 and "FALLO" not in out
    assert "sin procesos v1 en ejecución" in out  # publicar_feed_v2.py NO es v1


def test_v1_retirado_correctamente_bastion(banco):
    v1_retirado_real(banco, "ppi-relay-feed.timer", "ppi-relay-feed.service")
    banco.proceso(70246, ["/usr/bin/python3", "/opt/cyberflow/relay_eventos.py", "--entrega", "paquete"], BTIME + 5)
    rc, out = banco.ve(*V1_B)
    assert rc == 0, out


def test_v1_unidades_no_instaladas_cuentan_como_retiradas(banco):
    rc, out = banco.ve(*V1_S1)  # sin unidades: LoadState=not-found
    assert rc == 0, out
    assert out.count("unidad no instalada") == 2


@pytest.mark.parametrize("estado", [
    {"ActiveState": "active", "UnitFileState": "enabled"},    # timer reactivado del todo
    {"ActiveState": "inactive", "UnitFileState": "enabled"},  # habilitado: volvería en el próximo arranque
    {"ActiveState": "active", "UnitFileState": "disabled"},   # arrancado a mano
])
def test_v1_timer_reactivado(banco, estado):
    v1_retirado_real(banco)
    banco.cfg["unidades"]["ppi-publicar-feed.timer"].update(estado)
    rc, out = banco.ve(*V1_S1)
    assert rc == 1, out
    assert "FALLO v1 ppi-publicar-feed.timer" in out
    # con el timer no retirado, el servicio static ya no se puede dar por retirado
    assert "FALLO v1 ppi-publicar-feed.service" in out


def test_v1_servicio_reactivado(banco):
    v1_retirado_real(banco)
    banco.cfg["unidades"]["ppi-publicar-feed.service"] = unidad(True, "static", pid=4242)
    rc, out = banco.ve(*V1_S1)
    assert rc == 1 and "FALLO v1 ppi-publicar-feed.service" in out, out


def test_v1_servicio_habilitado(banco):
    v1_retirado_real(banco, "ppi-relay-feed.timer", "ppi-relay-feed.service")
    banco.cfg["unidades"]["ppi-relay-feed.service"] = unidad(False, "enabled")
    rc, out = banco.ve(*V1_B)
    assert rc == 1 and "FALLO v1 ppi-relay-feed.service" in out, out


def test_v1_proceso_residual_con_timer_apagado(banco):
    v1_retirado_real(banco)
    banco.proceso(5151, ["/home/m4rk/cyberflow/.venv/bin/python", "scripts/engine/publicar_feed.py", "--salida", "x"],
                  BTIME + 99)
    rc, out = banco.ve(*V1_S1)
    assert rc == 1, out
    assert "OK    v1 ppi-publicar-feed.timer" in out  # las unidades sí están bien...
    assert "FALLO sin procesos v1 en ejecución: PID 5151" in out  # ...pero el proceso sigue vivo


def test_v1_proceso_residual_rele_bastion(banco):
    v1_retirado_real(banco, "ppi-relay-feed.timer", "ppi-relay-feed.service")
    banco.proceso(6161, ["/bin/bash", "/home/gadmin/relay-feed.sh"], BTIME + 50)
    rc, out = banco.ve(*V1_B)
    assert rc == 1 and "PID 6161" in out, out


@pytest.mark.parametrize("modo", ["falla", "salida_vacia"])
def test_v1_error_al_consultar_estado(banco, modo):
    v1_retirado_real(banco)
    banco.cfg[modo] = ["ppi-publicar-feed.timer"]
    rc, out = banco.ve(*V1_S1)
    assert rc == 1, out
    assert "FALLO v1 ppi-publicar-feed.timer retirado (no demostrable" in out
    assert "FALLO v1 ppi-publicar-feed.service" in out  # static sin timer demostrado no vale
    assert "OK    v1 ppi-publicar-feed.timer" not in out


def test_v1_systemctl_inexistente(banco):
    v1_retirado_real(banco)
    env = banco.entorno()
    env["CF_VERIF_SYSTEMCTL"] = str(banco.tmp / "no-existe" / "systemctl")
    r = subprocess.run([sys.executable, "-I", str(VE), *V1_S1], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "no demostrable" in r.stdout and "OK    v1" not in r.stdout, r.stdout


def test_v1_proc_con_hidepid_no_demuestra(banco):
    v1_retirado_real(banco)
    banco.montaje("rw,nosuid,nodev,noexec,relatime,hidepid=invisible")
    rc, out = banco.ve(*V1_S1)
    assert rc == 1 and "FALLO sin procesos v1 en ejecución (no demostrable: /proc montado con hidepid" in out, out


def test_v1_proc_ilegible_no_demuestra(banco):
    v1_retirado_real(banco)
    (banco.proc / "self" / "mountinfo").unlink()
    rc, out = banco.ve(*V1_S1)
    assert rc == 1 and "FALLO sin procesos v1 en ejecución (no demostrable" in out, out


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="como root chmod 000 no impide leer")
def test_v1_cmdline_ilegible_no_demuestra(banco):
    v1_retirado_real(banco)
    banco.proceso(777, ["/usr/bin/x"], BTIME + 1)
    (banco.proc / "777" / "cmdline").chmod(0)
    rc, out = banco.ve(*V1_S1)
    assert rc == 1 and "ilegibles" in out, out


# ------------------------------------------------------------------ motor_startup del proceso vigente
EXCLUIR = "10.10.60.11/32,10.10.60.12/32,10.10.10.30/32"


def argv_motor(b, **cambio):
    o = {"--eve-path": "/var/log/suricata/eve.json", "--capture-dir": "/var/lib/ppi-motor-capture",
         "--model-path": "/home/m4rk/cyberflow/artifacts/preliminar/limpio-2026-10/if_limpio_2026_10_desplegable.joblib",
         "--manifest-path": str(b.manifiesto), "--detector-name": "if_limpio_2026_10",
         "--schema": "/home/m4rk/cyberflow/configs/features/multilayer-v2.json", "--entity-network": "10.10.0.0/16",
         "--excluir": EXCLUIR, "--excluir-protocolos": "112,240", "--log-path": str(b.log),
         "--state-dir": "/home/m4rk/cyberflow/logs/_state-e4", "--step-seconds": "10", "--history-seconds": "230",
         "--disparo": "eventos"}
    o.update(cambio)
    a = ["/home/m4rk/cyberflow/.venv/bin/python", "/home/m4rk/cyberflow-e4/ec78ca5/scripts/engine/motor_decision.py"]
    for k, v in o.items():
        if v is not None:
            a += [k, v]
    return a


def evento(b, t, **cambio):
    e = {"ancla_reanudada": False, "capture_dir": "/var/lib/ppi-motor-capture", "ciclos_path": "x",
         "claves_previas_cargadas": 0, "detector_name": "if_limpio_2026_10", "disparo": "eventos",
         "entity_network": "10.10.0.0/16", "eve_path": "/var/log/suricata/eve.json", "event": "motor_startup",
         "excluidas": EXCLUIR.split(","), "history_seconds": 230, "horizonte": 0, "hueco_arranque": 0,
         "manifest_path": str(b.manifiesto),
         "model_path": "/home/m4rk/cyberflow/artifacts/preliminar/limpio-2026-10/if_limpio_2026_10_desplegable.joblib",
         "procesamiento": "incremental", "protocolos_excluidos": [112, 240], "recuperacion_eve": None,
         "sondeo_segundos": 1.0, "step_seconds": 10, "threshold": UMBRAL, "timestamp": t}
    e.update(cambio)
    return json.dumps(e, sort_keys=True)


def decision(t):
    return json.dumps({"event": "decision", "timestamp": t, "decision_if": {}, "auth_failure": {},
                       "http_vista": {}, "dns_vista": {}})


def preparar_motor(b, actual=(), uno=(), dos_gz=(), umbral_manifiesto=UMBRAL, argv=None, inicio=INICIO_MOTOR):
    """Registros como los del Sensor1: actual, .1 (sin comprimir, delaycompress) y .2.gz."""
    logs = b.log.parent
    logs.mkdir(parents=True, exist_ok=True)
    b.manifiesto.write_text(json.dumps({"detectors": {"if_limpio_2026_10": {
        "calibration": {"threshold": umbral_manifiesto, "comparison": "score < threshold"}}}}))
    b.log.write_text("".join(l + "\n" for l in actual) + decision(inicio + 90000) + "\n")
    if uno is not None:
        (logs / "motor_decision.log.1").write_text("".join(l + "\n" for l in uno) + decision(inicio + 3600) + "\n")
        os.utime(logs / "motor_decision.log.1", (inicio + 86400, inicio + 86400))
    if dos_gz is not None:
        with gzip.open(logs / "motor_decision.log.2.gz", "wt") as f:
            f.writelines(l + "\n" for l in dos_gz)
        os.utime(logs / "motor_decision.log.2.gz", (inicio - 600, inicio - 600))
    b.cfg["unidades"]["ppi-motor"] = unidad(True, "enabled", pid=PID_MOTOR)
    b.proceso(PID_MOTOR, argv or argv_motor(b), inicio)


def motor(b, *extra):
    return b.ve("motor-arranque", "--unidad", "ppi-motor", "--registro", str(b.log), "--umbral", str(UMBRAL),
                "--disparo", "eventos", "--procesamiento", "incremental", *extra)


def antiguos(b):
    return [evento(b, t) for t in T_ANTIGUOS]


def test_arranque_vigente_en_registro_actual(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=antiguos(banco), dos_gz=None)
    rc, out = motor(banco)
    assert rc == 0, out
    assert "OK    motor_startup del proceso vigente (PID 1384" in out and "en motor_decision.log;" in out


def test_arranque_vigente_en_registro_rotado_estado_real(banco):
    """Regresión del FALLO falso del 06-nov: el arranque vigente está en .1 y el actual no tiene ninguno."""
    preparar_motor(banco, actual=[], uno=[evento(banco, T_ARRANQUE)], dos_gz=antiguos(banco))
    rc, out = motor(banco)
    assert rc == 0, out
    assert "+1.47 s en motor_decision.log.1" in out
    # el criterio antiguo (solo el registro actual) daba FALLO sobre este mismo estado
    assert '"motor_startup"' not in banco.log.read_text()


def test_arranque_vigente_en_rotado_comprimido(banco):
    preparar_motor(banco, actual=[], uno=[], dos_gz=[evento(banco, T_ARRANQUE)])
    os.utime(banco.log.parent / "motor_decision.log.2.gz", (INICIO_MOTOR + 7200,) * 2)
    rc, out = motor(banco)
    assert rc == 0 and "en motor_decision.log.2.gz" in out, out


def test_solo_arranque_antiguo_correcto_pero_ajeno(banco):
    """Un arranque histórico con la MISMA configuración no prueba nada del proceso vigente."""
    preparar_motor(banco, actual=[], uno=antiguos(banco), dos_gz=None)
    rc, out = motor(banco)
    assert rc == 1, out
    assert "FALLO motor_startup del proceso vigente (no demostrable: solo hay arranques anteriores" in out


def test_solo_arranque_antiguo_en_gz_de_antes_del_inicio(banco):
    preparar_motor(banco, actual=[], uno=[], dos_gz=antiguos(banco))
    rc, out = motor(banco)
    assert rc == 1 and "no hay ningún motor_startup" in out, out  # .2.gz es anterior al inicio: no puede contenerlo


@pytest.mark.parametrize("cambio,texto", [
    ({"threshold": -0.55}, "threshold del evento"),
    ({"disparo": "periodico"}, "disparo"),
    ({"procesamiento": "completo"}, "procesamiento"),
    ({"detector_name": "if_senal"}, "detector_name"),
    ({"step_seconds": 5}, "step_seconds"),
    ({"history_seconds": 300}, "history_seconds"),
    ({"model_path": "/home/m4rk/cyberflow/artifacts/otro.joblib"}, "model_path"),
    ({"excluidas": ["10.10.60.11/32"]}, "excluidas"),
    ({"protocolos_excluidos": [112]}, "protocolos_excluidos"),
    ({"eve_path": "/tmp/eve.json"}, "eve_path"),
])
def test_arranque_con_configuracion_incorrecta(banco, cambio, texto):
    preparar_motor(banco, actual=[], uno=[], dos_gz=None)
    banco.log.write_text(evento(banco, T_ARRANQUE, **cambio) + "\n")
    rc, out = motor(banco)
    assert rc == 1, out
    assert "FALLO motor_startup del proceso vigente con configuración distinta" in out and texto in out


def test_ejecucion_con_otro_disparo(banco):
    preparar_motor(banco, actual=[], uno=[], dos_gz=None)
    banco.proceso(PID_MOTOR, argv_motor(banco, **{"--disparo": "periodico"}), INICIO_MOTOR)
    banco.log.write_text(evento(banco, T_ARRANQUE, disparo="periodico") + "\n")
    rc, out = motor(banco)
    assert rc == 1 and "disparo 'periodico' ≠ esperado 'eventos'" in out, out


def test_manifiesto_con_otro_umbral(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE, threshold=-0.6)], uno=[], dos_gz=None,
                   umbral_manifiesto=-0.6)
    rc, out = motor(banco)
    assert rc == 1 and "≠ congelado" in out, out


def test_manifiesto_ilegible(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=[], dos_gz=None)
    banco.manifiesto.write_text("{no es json")
    rc, out = motor(banco)
    assert rc == 1 and "umbral del manifiesto" in out and "no demostrable" in out, out


def test_registro_ausente(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=None, dos_gz=None)
    banco.log.unlink()
    rc, out = motor(banco)
    assert rc == 1 and "registro actual ausente" in out, out


def test_rotado_comprimido_corrupto(banco):
    preparar_motor(banco, actual=[], uno=[evento(banco, T_ARRANQUE)], dos_gz=None)
    gz = banco.log.parent / "motor_decision.log.2.gz"
    gz.write_bytes(b"\x1f\x8b\x08\x00basura")
    os.utime(gz, (INICIO_MOTOR + 10, INICIO_MOTOR + 10))
    rc, out = motor(banco)
    assert rc == 1 and "no se puede leer" in out and "OK    motor_startup" not in out, out


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="como root chmod 000 no impide leer")
def test_rotado_ilegible_por_permisos(banco):
    preparar_motor(banco, actual=[], uno=[evento(banco, T_ARRANQUE)], dos_gz=None)
    (banco.log.parent / "motor_decision.log.1").chmod(0)
    rc, out = motor(banco)
    assert rc == 1 and "no se puede leer" in out, out


def test_linea_de_arranque_corrupta(banco):
    preparar_motor(banco, actual=[], uno=[], dos_gz=None)
    banco.log.write_text('{"event": "motor_startup", "timestamp": 17939231\n' + evento(banco, T_ARRANQUE) + "\n")
    rc, out = motor(banco)
    assert rc == 1 and "línea de arranque corrupta" in out, out


def test_arranque_sin_marca_de_tiempo(banco):
    preparar_motor(banco, actual=[], uno=[], dos_gz=None)
    e = json.loads(evento(banco, T_ARRANQUE))
    del e["timestamp"]
    banco.log.write_text(json.dumps(e) + "\n")
    rc, out = motor(banco)
    assert rc == 1 and "sin marca de tiempo" in out, out


def test_dos_arranques_compatibles_ambiguo(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE), evento(banco, T_ARRANQUE + 5)], uno=[], dos_gz=None)
    rc, out = motor(banco)
    assert rc == 1 and "ambiguo" in out, out


def test_arranque_posterior_al_proceso_vigente(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE + 3600)], uno=[evento(banco, T_ARRANQUE)], dos_gz=None)
    rc, out = motor(banco)
    assert rc == 1 and "posteriores" in out, out


def test_motor_parado(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=[], dos_gz=None)
    banco.cfg["unidades"]["ppi-motor"] = unidad(False, "enabled")
    rc, out = motor(banco)
    assert rc == 1 and "no está activo" in out, out


def test_motor_systemctl_falla(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=[], dos_gz=None)
    banco.cfg["falla"] = ["ppi-motor"]
    rc, out = motor(banco)
    assert rc == 1 and "no demostrable: systemctl show ppi-motor rc=1" in out, out


def test_proceso_del_motor_ilegible(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=[], dos_gz=None)
    (banco.proc / str(PID_MOTOR) / "stat").unlink()
    rc, out = motor(banco)
    assert rc == 1 and "inicio del proceso 1384 ilegible" in out, out


def test_btime_ausente(banco):
    preparar_motor(banco, actual=[evento(banco, T_ARRANQUE)], uno=[], dos_gz=None)
    (banco.proc / "stat").write_text("cpu 1 2 3\n")
    rc, out = motor(banco)
    assert rc == 1 and "btime ausente" in out, out


def test_arranque_demasiado_tardio(banco):
    """Un arranque registrado más de 60 s después del inicio no se atribuye al proceso."""
    preparar_motor(banco, actual=[evento(banco, INICIO_MOTOR + 400)], uno=[], dos_gz=None)
    rc, out = motor(banco)
    assert rc == 1 and "no demostrable" in out, out


# ------------------------------------------------------------------ guiones completos
def test_bastion_estado_real_ok_y_regresion_v1(banco):
    """verificar_bastion.sh sobre el estado real del 06-nov: relé v1 retirado, v2 activo en modo paquete."""
    home = banco.tmp / "home"
    (home / "relay-v2").mkdir(parents=True)
    import time
    ahora = time.time()
    (home / "relay-v2" / "traza.jsonl").write_text(
        json.dumps({"traido_en": ahora - 5, "destinos": {"srv-dmz": {"entregado_en": ahora - 4.9}}}) + "\n")
    v1_retirado_real(banco, "ppi-relay-feed.timer", "ppi-relay-feed.service")
    banco.cfg["unidades"]["ppi-relay-eventos"] = unidad(
        True, "enabled", pid=70246, cat="[Service]\nExecStart=/usr/bin/python3 relay_eventos.py --origen sensor "
                                        "--destino srv-dmz=10.10.30.10 --entrega paquete")
    env = banco.entorno()
    r = subprocess.run(["bash", str(E4 / "bastion" / "verificar_bastion.sh")], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERIFICACIÓN BASTIÓN OK" in r.stdout
    # el criterio antiguo («relé v1 sigue activo») daba FALLO sobre este mismo estado
    viejo = subprocess.run(["bash", "-c", "systemctl is-active --quiet ppi-relay-feed.timer"], env=env)
    assert viejo.returncode != 0

    # v2 parada -> FALLO
    banco.cfg["unidades"]["ppi-relay-eventos"]["ActiveState"] = "inactive"
    r = subprocess.run(["bash", str(E4 / "bastion" / "verificar_bastion.sh")], capture_output=True, text=True,
                       env=banco.entorno())
    assert r.returncode == 1 and "FALLO relé v2 activo" in r.stdout, r.stdout


def test_bastion_v2_sin_modo_paquete(banco):
    home = banco.tmp / "home"
    (home / "relay-v2").mkdir(parents=True)
    import time
    (home / "relay-v2" / "traza.jsonl").write_text(
        json.dumps({"traido_en": time.time(), "destinos": {"srv-dmz": {"entregado_en": time.time()}}}) + "\n")
    v1_retirado_real(banco, "ppi-relay-feed.timer", "ppi-relay-feed.service")
    banco.cfg["unidades"]["ppi-relay-eventos"] = unidad(True, "enabled", pid=7, cat="ExecStart=relay_eventos.py")
    r = subprocess.run(["bash", str(E4 / "bastion" / "verificar_bastion.sh")], capture_output=True, text=True,
                       env=banco.entorno())
    assert r.returncode == 1 and "FALLO relé v2 en modo --entrega paquete" in r.stdout, r.stdout


def test_bastion_traza_ilegible_es_fallo(banco):
    """Antes, si el bloque Python se rompía (traza ausente) no imprimía FALLO y el guion podía terminar en OK."""
    v1_retirado_real(banco, "ppi-relay-feed.timer", "ppi-relay-feed.service")
    banco.cfg["unidades"]["ppi-relay-eventos"] = unidad(True, "enabled", pid=7, cat="--entrega paquete")
    (banco.tmp / "home").mkdir()
    r = subprocess.run(["bash", str(E4 / "bastion" / "verificar_bastion.sh")], capture_output=True, text=True,
                       env=banco.entorno())
    assert r.returncode == 1 and "FALLO entregas del relé v2 (rc=1 sin resultado)" in r.stdout, r.stdout


def test_bastion_v1_reactivado_es_fallo(banco):
    home = banco.tmp / "home"
    (home / "relay-v2").mkdir(parents=True)
    import time
    (home / "relay-v2" / "traza.jsonl").write_text(
        json.dumps({"traido_en": time.time(), "destinos": {"srv-dmz": {"entregado_en": time.time()}}}) + "\n")
    banco.cfg["unidades"]["ppi-relay-feed.timer"] = unidad(True, "enabled")
    banco.cfg["unidades"]["ppi-relay-feed.service"] = unidad(False, "static")
    banco.cfg["unidades"]["ppi-relay-eventos"] = unidad(True, "enabled", pid=7, cat="--entrega paquete")
    r = subprocess.run(["bash", str(E4 / "bastion" / "verificar_bastion.sh")], capture_output=True, text=True,
                       env=banco.entorno())
    assert r.returncode == 1 and "FALLO v1 ppi-relay-feed.timer" in r.stdout, r.stdout


def test_sensor1_guion_usa_las_comprobaciones_nuevas():
    """verificar_sensor1.sh: el publicador v1 ya no se exige activo; v1-retirado y motor-arranque se llaman con el
    umbral congelado; el resto de comprobaciones se conservan."""
    s = (E4 / "sensor1" / "verificar_sensor1.sh").read_text(encoding="utf-8")
    bucle = s.split("for u in ", 1)[1].split("done", 1)[0]
    assert "ppi-publicar-feed.timer" not in bucle and "ppi-publicar-feed-v2" in bucle
    assert "v1-retirado" in s and "--unidad ppi-publicar-feed.timer" in s and "--proceso publicar_feed.py" in s
    assert "motor-arranque --unidad ppi-motor" in s and "--umbral -0.5693969936322356" in s
    assert "--disparo eventos --procesamiento incremental" in s
    for conservada in ("motor SIN --enforce", "captura con -G 5", "SHA256SUMS", "importaciones desde el candidato",
                       "decisiones con decision_if y auth_failure", "decisiones con http_vista y dns_vista",
                       "resumen de la vía rápida avanza", "feed v2 reciente", "firma del feed v2 verifica",
                       "SIGUSR1 periódico del anillo", "SIGUSR1 periódico de la vía rápida", "reloj sincronizado",
                       "logrotate de feed-v2 instalado"):
        assert conservada in s, conservada
    r = subprocess.run(["bash", "-n", str(E4 / "sensor1" / "verificar_sensor1.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_bloque_de_sensor1_propaga_errores(tmp_path):
    """La función bloque() de verificar_sensor1.sh: rc≠0 o ningún OK es FALLO aunque no se imprima FALLO."""
    s = (E4 / "sensor1" / "verificar_sensor1.sh").read_text(encoding="utf-8")
    funcion = s.split("bloque() {", 1)[1].split("\nVE=", 1)[0]
    guion = "fallo=0\nbloque() {" + funcion + "\n" + \
        'bloque A printf "OK    a\\n"; echo "f=$fallo"\n' + \
        'bloque B sh -c "exit 3"; echo "f=$fallo"\n'
    r = subprocess.run(["bash", "-c", guion], capture_output=True, text=True)
    assert "OK    a\nf=0" in r.stdout and "FALLO B (rc=3 sin resultado)\nf=1" in r.stdout, r.stdout
    guion2 = "fallo=0\nbloque() {" + funcion + '\nbloque C sh -c "echo INFO  x"; echo "f=$fallo"\n'
    r = subprocess.run(["bash", "-c", guion2], capture_output=True, text=True)
    assert "FALLO C (rc=0 sin resultado)" in r.stdout and "f=1" in r.stdout, r.stdout
