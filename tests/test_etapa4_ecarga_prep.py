"""Banco aislado de la preparación de E-carga v2 (deploy/etapa4/ecarga). SIN acceso al laboratorio: systemctl, sudo, ssh,
curl, nft y pgrep son dobles (tests/ecarga_banco/bin) y /proc de los generadores es un directorio simulado (CF_PROC).
Nada de lo que se ejecuta aquí arranca, para ni consulta un host real.

  ECARGA_DIRS=dir1:dir2   versión a probar (por defecto deploy/etapa4/ecarga). Para la versión ANTERIOR:
                          ECARGA_DIRS=<guiones-c7f24510>:<evaluacion-e83f4be6> pytest -k regresion
  EVALUADOR=…             evaluar_ecarga.py (por defecto deploy/etapa4/sensor1/evaluar_ecarga.py, 2026-11-06.4)
  OBS06=…/evidencia/06-observacion   datos de la observación del 06-nov (solo para probar las herramientas)

Las pruebas cuyo nombre contiene «regresion» reproducen un defecto de la versión anterior: deben FALLAR con ella y pasar
con la corregida. Las que dependen de una herramienta que la versión anterior no tenía se omiten con ese motivo explícito.
"""
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DIRS = [Path(d) for d in (os.environ.get("ECARGA_DIRS") or str(REPO / "deploy" / "etapa4" / "ecarga")).split(":") if d]
EVAL = os.environ.get("EVALUADOR") or str(REPO / "deploy" / "etapa4" / "sensor1" / "evaluar_ecarga.py")
BANCO = Path(__file__).resolve().parent / "ecarga_banco" / "bin"
OBS = Path(os.environ["OBS06"]) if os.environ.get("OBS06") else None
PERFILES = [("ofimatica", "10.10.20.21"), ("navegacion", "10.10.20.22"), ("descargas", "10.10.20.23"),
            ("aplicacion", "10.10.20.24"), ("ligero", "10.10.20.25"), ("erratico", "10.10.20.26")]
D = 1794194100.0            # ventana de la franja propuesta (NO programada): 1794194100–1794197700
H = D + 3600.0
BD, BH = D - 1200.0, D - 900.0   # línea base de 300 s (en la franja: los 300 s previos a T_g)


def ruta(nombre, obligatorio=True):
    for d in DIRS:
        if (d / nombre).is_file():
            return d / nombre
    if obligatorio:
        pytest.skip(f"{nombre} no existe en {':'.join(map(str, DIRS))} (la versión probada no tiene esta herramienta)")
    return None


def modulo(nombre):
    p = ruta(nombre + ".py")
    s = importlib.util.spec_from_file_location(nombre + "_" + hashlib.md5(str(p).encode()).hexdigest()[:6], p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


# =============================================================================================== banco de clientes
class Lab:
    def __init__(self, tmp):
        self.tmp = tmp
        self.fake = tmp / "fake"
        self.home = tmp / "home"
        self.bin = tmp / "bin"
        self.pkg = tmp / "pkg"
        for d in (self.fake / "units", self.fake / "proc", self.home / "laboratorio", self.bin, self.pkg):
            d.mkdir(parents=True)
        self.gen = self.home / "laboratorio" / "clientes_lab.py"
        self.gen.write_text("# generador simulado del banco\n")
        self.hash = hashlib.sha256(self.gen.read_bytes()).hexdigest()
        for f in BANCO.iterdir():
            shutil.copy(f, self.bin / f.name)
            (self.bin / f.name).chmod(0o755)
        for p, ip in PERFILES:
            exe = (f"{{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 {self.gen} --perfil {p} --origen {ip} "
                   "--servidor 10.10.30.10 --dns 10.10.10.20 ; ignore_errors=no ; start_time=[n/a] ; pid=0 }")
            self.unidad(f"cyberflow-lab-{p}.service", LoadState="loaded", ActiveState="inactive", SubState="dead",
                        MainPID="0", NRestarts="0", PartOf="cyberflow-lab.target", ExecStart=exe, UnitFileState="static")
        self.unidad("cyberflow-lab.target", LoadState="loaded", ActiveState="inactive", SubState="dead", MainPID="0",
                    NRestarts="0", UnitFileState="static", PartOf="", ExecStart="")
        self.config()
        # paquete: generadores.sh con el hash del generador simulado (misma longitud que el original), guardia y muestreo
        for n in ("generadores.sh", "muestreo_bastion.sh", "guardia.py"):
            src = ruta(n, obligatorio=False)
            if src is None:
                continue
            txt = src.read_text(encoding="utf-8")
            if n == "generadores.sh":
                lineas = []
                for l in txt.splitlines():
                    if l.startswith("HASH_ESPERADO="):
                        largo = len(l.split("=", 1)[1].strip())
                        l = "HASH_ESPERADO=" + self.hash[:largo]
                    lineas.append(l)
                txt = "\n".join(lineas) + "\n"
            (self.pkg / n).write_text(txt, encoding="utf-8")
        self.env = {"PATH": f"{self.bin}:/usr/local/bin:/usr/bin:/bin", "HOME": str(self.home), "FAKE_DIR": str(self.fake),
                    "CF_PROC": str(self.fake / "proc"), "CF_ESPERA": "0.2", "CF_ESPERA_MAX": "2", "CF_ESTABLE": "1",
                    "CF_INTERVALO": "1", "CF_T_PARADA": "40", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}

    def unidad(self, u, **kw):
        p = self.fake / "units" / (u + ".json")
        d = json.loads(p.read_text()) if p.exists() else {}
        d.update(kw)
        p.write_text(json.dumps(d))

    def leer(self, u):
        return json.loads((self.fake / "units" / (u + ".json")).read_text())

    def config(self, **kw):
        (self.fake / "config.json").write_text(json.dumps(kw))

    def marca(self, nombre, contenido="1"):
        (self.fake / nombre).write_text(contenido)

    def procesos(self):
        return sorted(p.name for p in (self.fake / "proc").iterdir())

    def gen_sh(self, *args, timeout=120):
        r = subprocess.run(["bash", str(self.pkg / "generadores.sh"), *args], capture_output=True, text=True,
                           env=self.env, timeout=timeout)
        return r.returncode, r.stdout + r.stderr

    def arrancar_directo(self):  # deja los generadores «en marcha» en el doble, sin pasar por el guion
        r = subprocess.run(["systemctl", "start", "cyberflow-lab.target"], env=self.env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        (self.fake / "arrancado").unlink()

    def llamadas(self):
        p = self.fake / "llamadas.log"
        return p.read_text() if p.exists() else ""

    def parado(self):
        return (self.leer("cyberflow-lab.target")["ActiveState"] == "inactive" and not self.procesos()
                and all(self.leer(f"cyberflow-lab-{p}.service")["MainPID"] == "0" for p, _ in PERFILES))


@pytest.fixture
def lab(tmp_path):
    ruta("generadores.sh")
    return Lab(tmp_path)


# ------------------------------------------------------------------------------------------------ generadores.sh
def test_regresion_hash_completo_en_el_guion():
    txt = ruta("generadores.sh").read_text(encoding="utf-8")
    h = [l.split("=", 1)[1].strip() for l in txt.splitlines() if l.startswith("HASH_ESPERADO=")]
    assert len(h) == 1 and len(h[0]) == 64 and all(c in "0123456789abcdef" for c in h[0]), h
    assert h[0] == "ae5134a778e66d90f5c3fbcd47323e328f3422cf4ba8d5197649f402c1d4cdc3"


def test_hash_distinto_aborta_sin_arrancar(lab):
    lab.gen.write_text("# generador alterado\n")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 2 and "ABORTA" in out
    assert " start " not in lab.llamadas() + " "


def test_regresion_arranque_fallido_da_rc_distinto_de_cero(lab):
    lab.config(start="fail")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 3, out
    assert "ARRANQUE_FALLIDO" in out and "start rc=1" in out
    assert not lab.procesos()


def test_regresion_arranque_parcial(lab):
    lab.config(start="parcial")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 4, out
    assert "ARRANQUE_PARCIAL" in out and "ligero failed" in out


def test_regresion_consulta_fallida_tras_arrancar_es_desconocido(lab):
    lab.config(fail_show="tras_start")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 5, out
    assert "ARRANQUE_NO_CONFIRMADO" in out and "consulta fallida" in out


def test_regresion_argv_de_la_unidad_no_corresponde(lab):
    lab.config(start="argv_malo")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 4, out
    assert "argv inesperado" in out


def test_regresion_sin_partof_no_arranca(lab):
    lab.unidad("cyberflow-lab-erratico.service", PartOf="")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 2, out
    assert "sin PartOf" in out and "systemctl start" not in lab.llamadas()


def test_regresion_no_arranca_con_procesos_previos(lab):
    d = lab.fake / "proc" / "4242"
    d.mkdir()
    (d / "cmdline").write_bytes(b"/usr/bin/python3\0" + str(lab.gen).encode() + b"\0--perfil\0ligero\0")
    rc, out = lab.gen_sh("arrancar")
    assert rc == 2 and "parado confirmado" in out, out
    assert "systemctl start" not in lab.llamadas()


def test_arranque_confirmado(lab):
    rc, out = lab.gen_sh("arrancar")
    assert rc == 0, out
    assert "ARRANQUE_CONFIRMADO" in out and len(lab.procesos()) == 6
    rc, out = lab.gen_sh("estado")
    assert rc == 0 and "consulta=ok" in out and out.count("active/running") == 6


def test_regresion_estado_con_consulta_fallida_no_parece_inactivo(lab):
    lab.config(fail_show="siempre")
    rc, out = lab.gen_sh("estado")
    assert rc == 5, out
    assert "consulta=ERROR" in out and "ESTADO_DESCONOCIDO" in out


def test_parada_confirmada(lab):
    lab.arrancar_directo()
    rc, out = lab.gen_sh("parar")
    assert rc == 0 and "PARADA_CONFIRMADA" in out, out
    assert lab.parado()


def test_regresion_parada_fallida(lab):
    lab.arrancar_directo()
    lab.config(stop="fail")
    rc, out = lab.gen_sh("parar")
    assert rc == 3, out
    assert "PARADA_FALLIDA" in out and "confirmado=no" in out
    assert not lab.parado()


def test_regresion_parada_sin_efecto(lab):
    lab.arrancar_directo()
    lab.config(stop="sin_efecto")
    rc, out = lab.gen_sh("parar")
    assert rc == 4, out
    assert "PARADA_NO_CONFIRMADA" in out


def test_parada_con_error_pero_parado(lab):
    lab.arrancar_directo()
    lab.config(stop="fail_pero_para")
    rc, out = lab.gen_sh("parar")
    assert rc == 3 and "confirmado=si" in out, out
    rc, out = lab.gen_sh("comprobar-parado")
    assert rc == 0 and "PARADO_CONFIRMADO" in out


def test_regresion_parada_con_consulta_fallida_no_se_confirma(lab):
    lab.arrancar_directo()
    lab.config(fail_show="siempre")
    rc, out = lab.gen_sh("parar")
    assert rc == 5, out
    assert "PARADA_NO_CONFIRMADA" in out


def test_regresion_parada_detecta_proceso_huerfano(lab):
    lab.arrancar_directo()
    d = lab.fake / "proc" / "4243"           # proceso fuera de las unidades: la parada del target no lo toca
    d.mkdir()
    (d / "cmdline").write_bytes(b"/usr/bin/python3\0" + str(lab.gen).encode() + b"\0--perfil\0erratico\0")
    rc, out = lab.gen_sh("parar")
    assert rc == 4 and "procesos clientes_lab.py vivos: 4243" in out, out


def test_configuracion(lab):
    rc, out = lab.gen_sh("configuracion")
    assert rc == 0 and out.count("OK cyberflow-lab-") == 6, out
    lab.unidad("cyberflow-lab-ligero.service", LoadState="not-found")
    rc, out = lab.gen_sh("configuracion")
    assert rc == 4 and "NO_CORRESPONDE cyberflow-lab-ligero.service LoadState=not-found" in out
    lab.config(fail_show="siempre")
    rc, out = lab.gen_sh("configuracion")
    assert rc == 5 and "CONSULTA_FALLIDA" in out


# ------------------------------------------------------------------------------------------------ muestreo_bastion.sh
def muestreo(lab, modo, fin_s, parada_s=-1, **env):
    ruta("muestreo_bastion.sh")
    e = dict(lab.env, **{k: str(v) for k, v in env.items()})
    ahora = int(time.time())
    o = lab.tmp / "obs"
    r = subprocess.run(["bash", str(lab.pkg / "muestreo_bastion.sh"), str(o), str(ahora + fin_s), str(ahora + parada_s), modo],
                       capture_output=True, text=True, env=e, timeout=400)
    leer = lambda n: (o / n).read_text(encoding="utf-8") if (o / n).exists() else ""
    jl = [json.loads(l) for l in leer("parada.jsonl").splitlines() if l.strip()]
    return r.returncode, o, leer, jl, r.stdout + r.stderr


def ssh_log(lab):
    p = lab.fake / "ssh.log"
    return p.read_text() if p.exists() else ""


def test_regresion_ssh_falla_en_parada_agota_sin_confirmar(lab):
    lab.arrancar_directo()
    lab.marca("ssh_falla_parar", "99")
    rc, o, leer, jl, out = muestreo(lab, "real", 2, CF_MAX_INTENTOS=3)
    assert rc == 4, out
    assert (o / "PARADA-NO-CONFIRMADA").exists()
    assert "INTERVENCIÓN NECESARIA" in leer("eventos.log")
    assert [x["resultado"] for x in jl if x["resultado"] != "solicitada"] == ["fallida", "fallida", "fallida", "agotada"]
    assert all(x["rc"] == 255 for x in jl if x["resultado"] == "fallida")
    assert "confirmada" not in {x["resultado"] for x in jl}
    assert ssh_log(lab).count("bash -s parar") == 3          # acotado: ni uno más
    assert not lab.parado()


def test_regresion_parada_fallida_y_recuperacion(lab):
    lab.arrancar_directo()
    lab.marca("ssh_falla_parar", "1")
    rc, o, leer, jl, out = muestreo(lab, "real", 5)
    assert rc == 0, out
    assert [x["resultado"] for x in jl if x["resultado"] != "solicitada"] == ["fallida", "confirmada"]
    assert not (o / "PARADA-NO-CONFIRMADA").exists()
    assert lab.parado()


def test_parada_rc3_confirmada_por_comprobar_parado(lab):
    lab.arrancar_directo()
    lab.config(stop="fail_pero_para")
    rc, o, leer, jl, out = muestreo(lab, "real", 3)
    assert rc == 0, out
    conf = [x for x in jl if x["resultado"] == "confirmada"]
    assert len(conf) == 1 and conf[0]["rc"] == 3 and conf[0]["rc_comprobacion"] == 0
    assert "comprobar-parado" in ssh_log(lab)


def test_regresion_parada_no_confirmada_rc_remoto_4(lab):
    lab.arrancar_directo()
    lab.config(stop="sin_efecto")
    rc, o, leer, jl, out = muestreo(lab, "real", 2, CF_MAX_INTENTOS=2)
    assert rc == 4, out
    assert [x["rc"] for x in jl if x["resultado"] == "fallida"] == [4, 4]
    assert (o / "PARADA-NO-CONFIRMADA").exists()


def test_seco_no_muta_nada(lab):
    lab.arrancar_directo()
    antes = lab.llamadas()
    rc, o, leer, jl, out = muestreo(lab, "seco", 3)
    assert rc == 0, out
    nuevas = lab.llamadas()[len(antes):]
    assert " start " not in nuevas and " stop " not in nuevas and "systemctl start" not in nuevas and "systemctl stop" not in nuevas
    assert "parar" not in ssh_log(lab) and "arrancar" not in ssh_log(lab)
    assert "SECO: se pararían" in leer("eventos.log") and leer("eventos.log").count("SECO:") == 1
    assert jl == [] and not lab.parado()


def test_regresion_lecturas_fallidas_se_escriben_error(lab):
    lab.marca("ejecutar_remoto")             # las lecturas de Sensor1 y srv-dmz se ejecutan en el banco
    lab.marca("sudo_falla")                  # sudo -n sin permiso: nft y grep de la traza fallan
    lab.unidad("ppi-enforce-agent-v2-dmz.service", LoadState="loaded", ActiveState="active", SubState="running",
               MainPID="999999", NRestarts="0")   # PID ilegible
    rc, o, leer, jl, out = muestreo(lab, "seco", 0)
    m = leer("muestras.txt")
    assert "S ruleset=ERROR" in m, m
    assert "ruleset=ERROR" in [l for l in m.splitlines() if l.startswith("D aplicacion")][0]
    assert "D aplicacion=ERROR" in m and "aplicar_cmd=ERROR" in m
    assert "e3b0c44298fc1c14" not in m       # el hash de la salida vacía ya no aparece como ruleset


def test_agente_sin_proceso_da_aplicar_cero(lab):
    lab.marca("ejecutar_remoto")
    rc, o, leer, jl, out = muestreo(lab, "seco", 0)
    m = leer("muestras.txt")
    assert "aplicar_cmd=0" in m and "enforce_aplicar=" in m and "enforce_aplicar=ERROR" not in m, m


def test_ssh_caido_en_lectura_se_registra(lab):
    lab.marca("ssh_falla_clientes")
    rc, o, leer, jl, out = muestreo(lab, "seco", 0)
    assert "C ERROR rc=255" in leer("muestras.txt")


# ------------------------------------------------------------------------------------------------ derivar_bastion
@pytest.mark.skipif(OBS is None, reason="OBS06 no definido")
def test_regresion_bastion_lectura_error_no_es_false():
    import re
    db = modulo("derivar_bastion")
    txt = (OBS / "bastion" / "muestras.txt").read_text(encoding="utf-8", errors="replace")
    D06, H06 = 1793940600.0, 1793944200.0
    p = txt.split("### ")
    for i in range(61, len(p)):
        p[i] = re.sub(r"^S suricata pid=(\d+) nr=(\d+) active$", r"S suricata pid=\1 nr=\2 ERROR", p[i], flags=re.M)
        p[i] = re.sub(r"^S v1 inactive/inactive", "S v1 ERROR/ERROR", p[i], flags=re.M)
    r = db.derivar("### ".join(p), D06, H06)
    vals = {s: r[s]["valor"] for s in ("S1", "S6", "S8", "S9", "S10")}
    assert False not in vals.values(), vals
    assert None in vals.values(), vals


# ------------------------------------------------------------------------------------------------ derivar_pcap
def nombre(t):
    return "live-" + time.strftime("%Y%m%d%H%M%S", time.gmtime(t)) + ".pcap"


def serie(t0, t1, pasos=(5,)):
    ts, t, i = [], t0, 0
    while t <= t1:
        ts.append(t)
        t += pasos[i % len(pasos)]
        i += 1
    return ts


def pasada(t, paso=5):  # obs_pcap lee cada 30 s los ficheros cerrados (el siguiente ya existe)
    return math.ceil((t + paso + 1) / 30.0) * 30.0


def lineas(ts, leido=pasada, **extra):
    out = []
    for t in ts:
        d = {"fichero": nombre(t), "bytes": 80000, "registros": 800, "primero": t + 0.01, "ultimo": t + 4.9,
             "leido_en": leido(t)}
        d.update(extra.get(nombre(t), {}))
        out.append(json.dumps(d))
    return out


def log_fin(fin):
    return ['{"inicio": 1}', json.dumps({"terminado_en": fin, "fin_epoch": fin})]


def pcap(ls, desde=D, hasta=H, log=None):
    m = modulo("derivar_pcap")
    if log is not None and "log" in inspect.signature(m.derivar).parameters:
        return m.derivar(ls, desde, hasta, log=log)
    return m.derivar(ls, desde, hasta)


def v(r):
    return r["S2"]["valor"], r["S3"]["valor"]


def test_regresion_pcap_dos_ficheros_al_inicio_de_la_hora():
    ls = lineas([D + 2, D + 7], leido=lambda t: D + 40)
    r = pcap(ls)
    assert v(r) != (True, True), r
    assert r["S3"]["valor"] is not True
    # con la lectura completa (fin normal pasada la ventana) lo que falta no se escribió: S3 false demostrado
    r = pcap(ls, log=log_fin(H + 60))
    assert r["S3"]["valor"] is False and "HASTA" in r["S3"]["motivo"], r["S3"]


def test_regresion_pcap_falta_el_inicio():
    r = pcap(lineas(serie(D + 20, H + 20)))
    assert r["S3"]["valor"] is False and "DESDE" in r["S3"]["motivo"], r["S3"]


def test_regresion_pcap_falta_el_final():
    ts = serie(D - 3, H - 60)
    r = pcap(lineas(ts), log=log_fin(H + 60))
    assert r["S3"]["valor"] is False and "HASTA" in r["S3"]["motivo"], r["S3"]
    r = pcap(lineas(ts))                     # sin fin normal: la observación pudo truncarse -> sin evidencia
    assert r["S3"]["valor"] is None and r["S2"]["valor"] is None, r


def test_regresion_pcap_observacion_truncada():
    ts = serie(D - 3, H - 5)                 # obs_pcap se paró a H+5: no consta que el fichero de HASTA se cerrara
    r = pcap(lineas(ts, leido=lambda t: min(pasada(t), H + 5)))
    assert v(r) == (None, None), r
    assert "truncada" in r["S2"]["motivo"]


def test_regresion_pcap_primera_pasada_tardia():
    ts = serie(D - 3, H + 20)
    r = pcap(lineas(ts, leido=lambda t: max(pasada(t), D + 1000)))
    assert v(r) == (None, None), r


def test_pcap_hueco_interior():
    ts = [t for t in serie(D - 3, H + 20) if not (D + 1000 < t < D + 1030)]
    r = pcap(lineas(ts))
    assert r["S3"]["valor"] is False and "salto" in r["S3"]["motivo"], r["S3"]
    assert r["S2"]["valor"] is True        # S2 no habla de continuidad


def test_regresion_pcap_fichero_ilegible_es_sin_evidencia():
    ts = serie(D - 3, H + 20)
    x = nombre(ts[300])
    r = pcap(lineas(ts, **{x: {"error": "lectura: [Errno 13] Permission denied", "registros": None}}))
    assert v(r) == (None, None), r
    assert "no comprobados" in r["S2"]["motivo"]


def test_pcap_error_de_formato_es_incumplimiento():
    ts = serie(D - 3, H + 20)
    x = nombre(ts[300])
    r = pcap(lineas(ts, **{x: {"error": "registro truncado en 51234"}}))
    assert r["S2"]["valor"] is False and r["S3"]["valor"] is True, r


def test_pcap_fichero_vacio_es_incumplimiento_de_s3():
    ts = serie(D - 3, H + 20)
    r = pcap(lineas(ts, **{nombre(ts[200]): {"registros": 0}}))
    assert r["S3"]["valor"] is False and "sin registros" in r["S3"]["motivo"], r["S3"]


def test_pcap_duplicados_y_desorden_no_ocultan_huecos():
    ts = serie(D - 3, H + 20)
    ls = lineas(ts)
    ls2 = ls[:100] + ls[150:160] + ls[100:] + ls[400:405]          # duplicados idénticos y líneas fuera de orden
    r = pcap(ls2)
    assert v(r) == (True, True), r
    assert any("repetidos" in a for a in r["avisos"]) and any("fuera de orden" in a for a in r["avisos"])
    sin = [l for l in ls2 if json.loads(l)["fichero"] not in {nombre(t) for t in ts[500:505]}]   # hueco de 25 s
    sin = sin + [ls[499], ls[505], ls[499]]                       # los vecinos repetidos no tapan el hueco
    assert pcap(sin)["S3"]["valor"] is False


def test_regresion_pcap_duplicado_contradictorio():
    ts = serie(D - 3, H + 20)
    ls = lineas(ts)
    d = json.loads(ls[300])
    d["registros"] = 1
    r = pcap(ls + [json.dumps(d)])
    assert v(r) == (None, None), r


def test_pcap_valida_con_variacion_de_rotacion():
    ts = serie(D - 3, H + 20, pasos=(4, 5, 6, 5, 5, 6, 4))
    r = pcap(lineas(ts, leido=lambda t: pasada(t, 6)))
    assert v(r) == (True, True), r
    c = r["cadena"]
    assert c["salto_max_s"] == 6.0 and c["cadencia_mediana_s"] == 5.0 and c["inicio_cubierto"] and c["fin_cubierto"]
    assert r["lectura"]["completa"]


@pytest.mark.skipif(OBS is None, reason="OBS06 no definido")
def test_pcap_reproduce_06nov_con_log():
    D06, H06 = 1793940600.0, 1793944200.0
    ls = (OBS / "sensor1" / "pcap.jsonl").read_text(encoding="utf-8").splitlines()
    lg = (OBS / "sensor1" / "obs_pcap.log").read_text(encoding="utf-8", errors="replace").splitlines()
    r = pcap(ls, D06, H06, log=lg)
    assert v(r) == (True, True), {k: r[k] for k in ("S2", "S3", "lectura")}
    assert r["cadena"]["salto_max_s"] == 6.0


# ------------------------------------------------------------------------------------------------ S14
def s14_muestras(t0, t1, f=None, paso=1.0, quitar=(), extra=None):
    """Muestras acumuladas a 1 s. f(t) da las tasas del intervalo [t, t+paso): cpu (% ocupada), psi_cpu, softirq (cpu0),
    hilo (% de un núcleo), disco (% ocupado), psi_io_full, psi_mem, mem_kb, dropped (+), oom (+), pid."""
    f = f or (lambda t: {})
    acc = {"cpu": [0] * 8, "cpus": [[0] * 8 for _ in range(4)], "psi": {"cpu_some": 0, "io_some": 0, "io_full": 0,
           "mem_some": 0, "mem_full": 0}, "disco": [0, 0], "hilo": 0, "dropped": 0, "oom": 0}
    out, t = [], t0
    while t <= t1:
        r = dict({"cpu": 5.0, "psi_cpu": 0.2, "softirq": 2.0, "hilo": 2.0, "disco": 1.0, "psi_io_full": 0.0,
                  "psi_mem": 0.0, "mem_kb": 5_200_000, "dropped": 0, "oom": 0, "pid": 1351}, **f(t))
        m = {"t": round(t, 3), "psi": dict(acc["psi"]), "cpu": {"cpu": list(acc["cpu"])},
             "softnet": {"dropped": acc["dropped"], "time_squeeze": 0}, "disco": {"sda": list(acc["disco"])},
             "mem_disponible_kb": r["mem_kb"], "vmstat": {"pswpin": 0, "pswpout": 0, "oom_kill": acc["oom"]},
             "suricata": {"pid": r["pid"], "hilos": {"W#01-ens37#1400": acc["hilo"], "W#02-ens37#1401": 0}},
             "user_hz": 100}
        for i in range(4):
            m["cpu"][f"cpu{i}"] = list(acc["cpus"][i])
        if extra:
            extra(t, m)
        if not any(a <= t < b for a, b in quitar):
            out.append(json.dumps(m))
        # avanzar contadores con las tasas de [t, t+paso)
        tot = 400 * paso
        idle = round(tot * (1 - r["cpu"] / 100))
        acc["cpu"][0] += tot - idle
        acc["cpu"][3] += idle
        for i in range(4):
            s = round(100 * paso * (r["softirq"] if i == 0 else 1.0) / 100)
            acc["cpus"][i][6] += s
            acc["cpus"][i][3] += round(100 * paso) - s
        acc["psi"]["cpu_some"] += round(r["psi_cpu"] / 100 * 1e6 * paso)
        acc["psi"]["io_full"] += round(r["psi_io_full"] / 100 * 1e6 * paso)
        acc["psi"]["io_some"] += round(r["psi_io_full"] / 100 * 1e6 * paso)
        acc["psi"]["mem_some"] += round(r["psi_mem"] / 100 * 1e6 * paso)
        acc["disco"][0] += round(r["disco"] / 100 * 1000 * paso)
        acc["hilo"] += round(r["hilo"] / 100 * 100 * paso)
        acc["dropped"] += r["dropped"]
        acc["oom"] += r["oom"]
        t += paso
    return out


def s14(ls, base=(BD, BH), desde=D, hasta=H):
    return modulo("evaluar_s14").evaluar(ls, desde, hasta, base)


def completo(f=None, **kw):
    return s14_muestras(BD - 5, H + 5, f, **kw)


def entre(a, b, **tasas):
    return lambda t: tasas if D + a <= t < D + b else {}


def test_s14_carga_normal_cumple():
    r = s14(completo())
    assert r["S14"]["valor"] is True, r["S14"]
    assert all(c["valor"] is True for c in r["componentes"].values())


def test_s14_cpu_por_debajo_en_y_por_encima_del_limite():
    assert s14(completo(entre(100, 130, cpu=94.75, psi_cpu=50)))["componentes"]["cpu"]["valor"] is True   # < 95 %
    r = s14(completo(entre(100, 130, cpu=95.0, psi_cpu=10.0)))                                         # = límite
    assert r["componentes"]["cpu"]["valor"] is False and r["S14"]["valor"] is False
    assert s14(completo(entre(100, 130, cpu=100, psi_cpu=40)))["componentes"]["cpu"]["valor"] is False   # por encima
    assert s14(completo(entre(100, 130, cpu=99, psi_cpu=9.9)))["componentes"]["cpu"]["valor"] is True    # PSI < 10


def test_s14_utilizacion_alta_no_es_saturacion():
    r = s14(completo(entre(100, 400, cpu=100, psi_cpu=0.5, disco=100, psi_io_full=0.0)))
    assert r["componentes"]["cpu"]["valor"] is True and r["componentes"]["disco"]["valor"] is True, r["componentes"]


def test_s14_duracion_insuficiente_y_suficiente():
    assert s14(completo(entre(100, 107, cpu=100, psi_cpu=50)))["componentes"]["cpu"]["valor"] is True   # 7 s
    r = s14(completo(entre(100, 108, cpu=100, psi_cpu=50)))                                            # 8 s
    assert r["componentes"]["cpu"]["valor"] is False
    assert r["componentes"]["cpu"]["ventana"]["episodios"][0]["duracion_s"] == 8.0


def test_s14_hilo_softirq_disco_memoria():
    assert s14(completo(entre(50, 70, hilo=100)))["componentes"]["hilos"]["valor"] is False
    assert s14(completo(entre(50, 70, hilo=94)))["componentes"]["hilos"]["valor"] is True
    assert s14(completo(entre(50, 70, softirq=96)))["componentes"]["softirq"]["valor"] is False
    assert s14(completo(entre(50, 70, disco=100, psi_io_full=20)))["componentes"]["disco"]["valor"] is False
    assert s14(completo(entre(50, 70, psi_mem=15)))["componentes"]["memoria"]["valor"] is False
    r = s14(completo(entre(50, 51, mem_kb=1_000_000)))
    assert r["componentes"]["memoria"]["valor"] is False and "1 GiB" in r["componentes"]["memoria"]["motivo"]


def test_s14_inmediatos_softnet_y_oom():
    r = s14(completo(entre(500, 501, dropped=1)))
    assert r["componentes"]["softnet_dropped"]["valor"] is False and r["componentes"]["softnet_dropped"]["incremento"] == 1
    assert s14(completo(entre(500, 501, oom=1)))["componentes"]["oom_kill"]["valor"] is False

    def reinicio(t, m):
        if t >= D + 600:
            m["softnet"]["dropped"] = -1 + 0 * m["softnet"]["dropped"]
    assert s14(completo(extra=reinicio))["componentes"]["softnet_dropped"]["valor"] is None


def test_s14_datos_ausentes_y_cobertura():
    r = s14(completo(quitar=[(D + 1000, D + 1010)]))           # hueco de 10 s > 4 s
    assert r["S14"]["valor"] is None and all(r["componentes"][k]["valor"] is None
                                             for k in ("cpu", "hilos", "softirq", "disco", "memoria"))
    r = s14(s14_muestras(BD - 5, H - 120))                       # el muestreador se paró 2 min antes de HASTA
    assert r["S14"]["valor"] is None and "softnet_dropped" in r["S14"]["sin_medida"]
    r = s14(completo(quitar=[(D + 1000, D + 1002)]))            # 2 s sueltos: cobertura suficiente
    assert r["S14"]["valor"] is True, r["S14"]


def test_s14_lectura_fallida_dentro_de_una_saturacion_no_da_true():
    def fallo(t, m):
        if D + 104 <= t < D + 106:
            m["psi"] = None
            m["errores"] = ["psi: [Errno 5]"]
    r = s14(completo(entre(100, 110, cpu=100, psi_cpu=50), extra=fallo))
    assert r["componentes"]["cpu"]["valor"] is None, r["componentes"]["cpu"]
    assert r["S14"]["valor"] is None


def test_s14_reinicio_de_suricata_no_inventa_saturacion():
    r = s14(completo(lambda t: {"pid": 1351 if t < D + 900 else 2222}))
    assert r["componentes"]["hilos"]["valor"] is True, r["componentes"]["hilos"]


def test_s14_base_saturada_o_ausente():
    f = lambda t: {"cpu": 100, "psi_cpu": 50} if (BD + 10 <= t < BD + 30 or D + 100 <= t < D + 130) else {}
    r = s14(completo(f))
    assert r["componentes"]["cpu"]["valor"] is None and "línea base" in r["componentes"]["cpu"]["motivo"]
    r = s14(completo(entre(100, 130, cpu=100, psi_cpu=50)), base=None)
    assert r["componentes"]["cpu"]["valor"] is None and "no evaluable" in r["componentes"]["cpu"]["motivo"]


# ------------------------------------------------------------------------------------------------ de punta a punta
def _cli(script, *args):
    r = subprocess.run([sys.executable, "-I", str(script), *map(str, args)], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def fuentes(tmp, pcap_lineas, s14_lineas=None, pcap_log=None):
    """Escribe fuentes sintéticas coherentes de una ventana C0 con carga suficiente y devuelve los argumentos."""
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "clas.json").write_text(json.dumps({
        "periodo": {"desde": D, "hasta": H}, "clase_periodo": "C0", "capturas": {}, "motivo": None,
        "suricata": {"fuente": "eve_stats", "medida": {"periodo": [D, H], "estado": "cero_explicito",
                                                       "paquetes": 700_000, "descartes": 0}}}))
    (tmp / "comp.json").write_text(json.dumps({"desde": D, "hasta": H, "fuente_contadores": "eve stats", "paquetes": 700_000,
                                               "rafagas_ge_umbral": 12, "umbral_rafaga_paquetes_8s": 5000, "flujos_eve": 900,
                                               "flujos_grandes": 60, "umbral_flujo_grande": 1000}))
    (tmp / "perf.json").write_text(json.dumps({"version": "2026-11-06.4", "desde": D, "hasta": H, "K4a": {"cumple": True},
                                               "K4b": {"estado": "informativo"}}))
    bas = {"version": "derivar_bastion 2026-11-06.2", "periodo": [D, H]}
    bas.update({s: {"valor": True} for s in ("S1", "S6", "S8", "S9", "S10")})
    (tmp / "bas.json").write_text(json.dumps(bas))
    (tmp / "pcap.jsonl").write_text("\n".join(pcap_lineas) + "\n")
    args = ["--desde", D, "--hasta", H, "--clasificacion", tmp / "clas.json", "--comparar", tmp / "comp.json",
            "--perfiles", tmp / "perf.json", "--perfiles-rc", 0, "--bastion", tmp / "bas.json"]
    pa = ["--log", pcap_log] if pcap_log else []
    if pcap_log:
        Path(pcap_log).write_text("\n".join(log_fin(H + 60)) + "\n")
    rc, out, err = _cli(ruta("derivar_pcap.py"), tmp / "pcap.jsonl", D, H, *(pa if "--log" in ruta("derivar_pcap.py").read_text() else []))
    assert rc == 0, err
    (tmp / "pcap.json").write_text(out)
    args += ["--pcap", tmp / "pcap.json"]
    ev = tmp / "ev.txt"
    ev.write_text("evidencia sintética del banco (no es un resultado de E-carga)\n")
    manual = ["S7", "S11", "S15"]
    ce_txt = ruta("construir_entrada.py").read_text(encoding="utf-8")
    if "--s14" in ce_txt and s14_lineas is not None:
        (tmp / "s14.jsonl").write_text("\n".join(s14_lineas) + "\n")
        rc, out, err = _cli(ruta("evaluar_s14.py"), tmp / "s14.jsonl", "--desde", D, "--hasta", H,
                            "--base-desde", BD, "--base-hasta", BH)
        assert rc == 0, err
        (tmp / "s14.json").write_text(out)
        args += ["--s14", tmp / "s14.json"]
    elif "--s14" not in ce_txt:
        manual.append("S14")                  # versión anterior: S14 era manual
    for s in manual:
        args += ["--manual", f"{s}=true:{ev}"]
    args += ["--salida-entrada", tmp / "entrada.json", "--salida-traza", tmp / "traza.json"]
    return args


def e2e(tmp, *a, **kw):
    args = fuentes(tmp, *a, **kw)
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    assert rc == 0, err
    rc, out, err = _cli(EVAL, "veredicto", "--entrada", tmp / "entrada.json")
    r = json.loads(out)
    return rc, r, json.loads((tmp / "entrada.json").read_text()), json.loads((tmp / "traza.json").read_text())


def test_e2e_evidencia_completa_habilita(tmp_path):
    rc, r, e, t = e2e(tmp_path, lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp_path / "obs_pcap.log")
    assert rc == 0 and r["habilita_condicion_3"] is True, (r, t["sin_medida"])
    assert e["S"]["S2"] is True and e["S"]["S3"] is True and e["S"]["S14"] is True
    assert t["campos"]["S.S14"]["fuente"] == "s14" and t["campos"]["S.S3"]["motivo_fuente"]


def test_regresion_e2e_dos_pcap_no_habilita(tmp_path):
    rc, r, e, t = e2e(tmp_path, lineas([D + 2, D + 7], leido=lambda t: D + 40), completo())
    assert r["habilita_condicion_3"] is False and rc == 1, r
    assert not (e["S"]["S2"] is True and e["S"]["S3"] is True)


def test_regresion_e2e_pcap_falta_el_final_no_habilita(tmp_path):
    rc, r, e, t = e2e(tmp_path, lineas(serie(D - 3, H - 60)), completo(), pcap_log=tmp_path / "obs_pcap.log")
    assert r["habilita_condicion_3"] is False and e["S"]["S3"] is False, (r, e["S"])
    assert r["estabilidad_tecnica"] == "no estable"


def test_e2e_s14_incompleto_no_habilita(tmp_path):
    rc, r, e, t = e2e(tmp_path, lineas(serie(D - 3, H + 20)), s14_muestras(BD - 5, H - 120),
                      pcap_log=tmp_path / "obs_pcap.log")
    assert e["S"]["S14"] is None and r["habilita_condicion_3"] is False and r["estabilidad_tecnica"] == "no demostrable", r


def test_e2e_s14_saturado_no_habilita(tmp_path):
    rc, r, e, t = e2e(tmp_path, lineas(serie(D - 3, H + 20)), completo(entre(100, 130, cpu=100, psi_cpu=50)),
                      pcap_log=tmp_path / "obs_pcap.log")
    assert e["S"]["S14"] is False and r["habilita_condicion_3"] is False and r["estabilidad_tecnica"] == "no estable", r


def test_e2e_pcap_de_version_anterior_queda_sin_medida(tmp_path):
    ce = ruta("construir_entrada.py").read_text(encoding="utf-8")
    if "VERSIONES_FUENTE" not in ce:
        pytest.skip("la versión anterior de construir_entrada no comprueba la versión de las fuentes")
    args = fuentes(tmp_path, lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp_path / "obs_pcap.log")
    p = json.loads((tmp_path / "pcap.json").read_text())
    p["version"] = "derivar_pcap 2026-11-06.1"
    (tmp_path / "pcap.json").write_text(json.dumps(p))
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    e = json.loads((tmp_path / "entrada.json").read_text())
    assert e["S"]["S2"] is None and e["S"]["S3"] is None
    rc, out, err = _cli(EVAL, "veredicto", "--entrada", tmp_path / "entrada.json")
    assert json.loads(out)["habilita_condicion_3"] is False


def test_s14_manual_ya_no_se_admite(tmp_path):
    ce = ruta("construir_entrada.py").read_text(encoding="utf-8")
    if "--s14" not in ce:
        pytest.skip("la versión anterior trataba S14 como manual")
    args = fuentes(tmp_path, lineas(serie(D - 3, H + 20)), None, pcap_log=tmp_path / "obs_pcap.log")
    i = args.index("--salida-entrada")
    ev = tmp_path / "ev.txt"
    args[i:i] = ["--manual", f"S14=true:{ev}"]
    rc, out, err = _cli(ruta("construir_entrada.py"), *args)
    assert rc == 2 and "S14" in err
