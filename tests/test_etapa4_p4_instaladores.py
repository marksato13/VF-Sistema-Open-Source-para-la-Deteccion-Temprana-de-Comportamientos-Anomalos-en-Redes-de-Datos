"""Banco de los instaladores P4 (p4-instalador 2026-11-06.2) con ERRORES DELIBERADOS en cada paso crítico.

Se ejecutan bastion_p4.sh y srvdmz_p4.sh de verdad (bash), sobre una raíz temporal (CF_RAIZ) y con órdenes falsas
(sudo, systemctl, systemd-analyze, nft, ssh) que fallan cuando se les pide:
  CF_BANCO_FALLA=<regex>                 la orden que coincide falla SIEMPRE (rc 1, sin texto)
  CF_BANCO_FALLA_EN=<regex> + _NUM=<n>   falla solo la n-ésima orden que coincide
  CF_BANCO_NO_ENTREGA=paquete            el servicio arranca en modo paquete pero no entrega/recibe nada
  CF_BANCO_ANALYZE_TEXTO=1               systemd-analyze imprime avisos con rc 0 (no debe tomarse como fallo)
  CF_BANCO_RULESET_CAMBIA=1              al reiniciar el agente aparece una tabla nft (violación de la sombra)
Cada caso comprueba: código de salida (0/10/20/30), que «RESULTADO: OK» aparece SOLO si rc=0, que el respaldo
verifica en modo estricto y no contiene evidencia, que tras rc 10/20 los ficheros instalados vuelven a tener los
hashes de antes, que el servicio sigue activo sin --aplicar, que nft solo se usó para «list ruleset», y que la
evidencia queda sellada fuera del respaldo.
Requiere Linux y root (install -o root); en Windows se omite.
"""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[1]
PEND = RAIZ_REPO / "deploy" / "etapa4" / "pendientes"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or not hasattr(os, "geteuid") or os.geteuid() != 0 or shutil.which("bash") is None,
    reason="banco Linux como root",
)

# ------------------------------------------------------------------ órdenes falsas
FALLO_PY = r'''
import os, re, sys
def fallar(nombre):
    linea = " ".join([nombre] + sys.argv[1:])
    with open(os.path.join(os.environ["CF_BANCO_DIR"], "ordenes.log"), "a") as f:
        f.write(linea + "\n")
    r = os.environ.get("CF_BANCO_FALLA")
    if r and re.search(r, linea):
        return True
    r = os.environ.get("CF_BANCO_FALLA_EN")
    if r and re.search(r, linea):
        c = os.path.join(os.environ["CF_BANCO_DIR"], "contador")
        n = int(open(c).read()) + 1 if os.path.exists(c) else 1
        open(c, "w").write(str(n))
        return n == int(os.environ.get("CF_BANCO_FALLA_NUM", "1"))
    return False
'''

SUDO = r'''#!/usr/bin/env python3
''' + FALLO_PY + r'''
if fallar("sudo"):
    sys.exit(1)
args = sys.argv[1:]
if args and args[0] == "-n":
    args = args[1:]
os.execvp(args[0], args)
'''

SYSTEMCTL = r'''#!/usr/bin/env python3
''' + FALLO_PY + r'''
import json, shlex, subprocess, time
if fallar("systemctl"):
    sys.exit(1)
D = os.environ["CF_BANCO_DIR"]; RAIZ = os.environ["CF_RAIZ"]
a = [x for x in sys.argv[1:] if x != "--quiet"]
def pid(u):
    p = os.path.join(D, u + ".pid")
    return int(open(p).read()) if os.path.exists(p) else 0
def vivo(p):
    try:
        return p > 0 and open("/proc/%d/stat" % p).read().split(")")[-1].split()[0] not in ("Z", "X")
    except OSError:
        return False
def unidad(u):
    return u[:-8] if u.endswith(".service") else u
if a[0] == "daemon-reload":
    sys.exit(0)
if a[0] in ("is-enabled", "is-active") and a[1].endswith(".timer"):
    print("disabled" if a[0] == "is-enabled" else "inactive"); sys.exit(1)
u = unidad(a[-1])
if a[0] == "is-active":
    sys.exit(0 if vivo(pid(u)) else 3)
if a[0] == "show":
    print(pid(u) if vivo(pid(u)) else 0); sys.exit(0)
if a[0] == "restart":
    viejo = pid(u)
    if vivo(viejo):
        os.kill(viejo, 9)
    txt = open(os.path.join(RAIZ, "etc/systemd/system", u + ".service")).read().replace("\\\n", " ")
    ex = [l.split("=", 1)[1] for l in txt.splitlines() if l.startswith("ExecStart=")][0]
    args = shlex.split(ex)
    p = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(60)"] + args,
                         start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    open(os.path.join(D, u + ".pid"), "w").write(str(p.pid))
    ahora = time.time() + 0.01
    modo = "paquete" if "--paquete" in args else "pareja"
    if "--entrega" in args:
        modo = args[args.index("--entrega") + 1]
    if os.environ.get("CF_BANCO_NO_ENTREGA") == modo:
        sys.exit(0)
    if u == "ppi-relay-eventos":
        t = os.path.join(os.environ["HOME"], "relay-v2/traza.jsonl")
        r = {"t": ahora, "seq": 1, "destinos": {"srv-dmz": {"entregado_en": ahora}}}
        if modo == "paquete":
            r["entrega"] = "paquete"
    else:
        t = os.path.join(RAIZ, "var/lib/cyberflow/agente/traza.jsonl")
        r = {"evento": "recepcion", "t": ahora, "estado": "aceptado", "seq": 1}
        if os.environ.get("CF_BANCO_RULESET_CAMBIA") == "1":
            with open(os.path.join(D, "ruleset"), "a") as f:
                f.write("table inet cf_intruso {\n}\n")
    with open(t, "a") as f:
        f.write(json.dumps(r) + "\n")
    sys.exit(0)
sys.exit(2)
'''

ANALYZE = r'''#!/usr/bin/env python3
''' + FALLO_PY + r'''
if fallar("systemd-analyze"):
    sys.exit(1)
if os.environ.get("CF_BANCO_ANALYZE_TEXTO") == "1":
    print("aviso: Unknown key name 'X' in section 'Unit', ignoring.")
sys.exit(0)
'''

NFT = r'''#!/usr/bin/env python3
''' + FALLO_PY + r'''
if fallar("nft"):
    sys.exit(1)
if sys.argv[1:] != ["list", "ruleset"]:
    sys.exit(2)
sys.stdout.write(open(os.path.join(os.environ["CF_BANCO_DIR"], "ruleset")).read())
'''

SSH = r'''#!/usr/bin/env python3
''' + FALLO_PY + r'''
if fallar("ssh"):
    sys.exit(255)
sys.exit(0)
'''

RULESET = "table inet filter {\n\tchain input {\n\t\ttype filter hook input priority 0; policy accept;\n\t}\n}\n"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Banco:
    def __init__(self, tmp, host):
        self.tmp = tmp
        self.host = host
        self.raiz = tmp / "raiz"
        self.home = tmp / "home"
        self.dir = tmp / "banco"
        self.bin = tmp / "bin"
        for d in (self.raiz, self.home, self.dir, self.bin):
            d.mkdir()
        for nombre, txt in (("sudo", SUDO), ("systemctl", SYSTEMCTL), ("systemd-analyze", ANALYZE),
                            ("nft", NFT), ("ssh", SSH)):
            (self.bin / nombre).write_text(txt)
            (self.bin / nombre).chmod(0o755)
        (self.dir / "ruleset").write_text(RULESET)
        self.paq = self._paquete()
        if host == "bastion":
            self.u = "ppi-relay-eventos"
            opt = self.raiz / "opt/cyberflow/relay-v2"
            self.fich = {opt / "relay_eventos.py": (0o644, "# relé viejo\n"),
                         opt / "feed.py": (0o644, "# feed viejo\n"),
                         opt / "pub.pem": (0o640, "PEM\n")}
            (self.home / "relay-v2").mkdir()
            unidad = ("[Service]\nExecStart=/usr/bin/python3 -I /opt/cyberflow/relay-v2/relay_eventos.py \\\n"
                      "    --traza /home/gadmin/relay-v2/traza.jsonl --sondeo-segundos 1\n")
        else:
            self.u = "ppi-enforce-agent-v2-dmz"
            opt = self.raiz / "opt/cyberflow/agente-v2"
            self.fich = {opt / "agente_enforce_v2.py": (0o644, "# agente viejo\n"),
                         opt / "feed.py": (0o644, "# feed viejo\n"),
                         opt / "pub.pem": (0o640, "PEM\n"),
                         self.raiz / "usr/local/bin/cf-feed-ssh.sh": (0o755, "#!/bin/sh\n# viejo\n"),
                         self.raiz / "usr/local/sbin/cf-nft-helper": (0o750, "#!/bin/sh\n# helper\n")}
            (self.raiz / "var/lib/cyberflow/agente").mkdir(parents=True)
            (self.raiz / "var/lib/cyberflow/feed").mkdir(parents=True)
            unidad = ("[Service]\nExecStart=/usr/bin/python3 -I /opt/cyberflow/agente-v2/agente_enforce_v2.py \\\n"
                      "    --perfil dmz --feed /var/lib/cyberflow/feed/feed.json \\\n"
                      "    --firma /var/lib/cyberflow/feed/feed.sig --seguir\n")
        self.uf = self.raiz / "etc/systemd/system" / (self.u + ".service")
        self.fich[self.uf] = (0o644, unidad)
        for p, (m, txt) in self.fich.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(txt)
            p.chmod(m)
        self.antes = {p: sha(p) for p in self.fich}
        self.run_tool(["systemctl", "restart", self.u])
        (self.dir / "ordenes.log").write_text("")

    def _paquete(self):
        p = self.tmp / "paquete"
        rel = ["deploy/enforcement/relay_eventos.py", "scripts/engine/feed.py",
               "deploy/etapa4/unidades/bastion/ppi-relay-eventos.service",
               "deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh", "scripts/enforce/agente_enforce_v2.py",
               "deploy/etapa4/unidades/srvdmz/ppi-enforce-agent-v2-dmz.service"]
        for r in rel:
            (p / r).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ_REPO / r, p / r)
        (p / "SHA256SUMS").write_text("".join(f"{sha(p / r)}  {r}\n" for r in rel))
        return p

    def env(self, **extra):
        e = dict(os.environ)
        e.update(CF_BANCO="1", CF_RAIZ=str(self.raiz), CF_SUDO="sudo -n" if self.host == "srvdmz" else "sudo",
                 CF_SYSTEMCTL="systemctl", CF_SYSTEMD_ANALYZE="systemd-analyze", CF_BANCO_DIR=str(self.dir),
                 CF_ESPERA="0.05", HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}")
        for k in ("CF_BANCO_FALLA", "CF_BANCO_FALLA_EN", "CF_BANCO_FALLA_NUM", "CF_BANCO_NO_ENTREGA",
                  "CF_BANCO_ANALYZE_TEXTO", "CF_BANCO_RULESET_CAMBIA"):
            e.pop(k, None)
        e.update({k: str(v) for k, v in extra.items()})
        return e

    def run_tool(self, args, **extra):
        subprocess.run(args, env=self.env(**extra), check=True, timeout=30)

    def ejecutar(self, *args, **extra):
        script = PEND / ("bastion_p4.sh" if self.host == "bastion" else "srvdmz_p4.sh")
        r = subprocess.run(["bash", str(script), *args], env=self.env(**extra), capture_output=True, text=True,
                           timeout=180, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout + r.stderr

    # ---------------------------------------------------------- comprobaciones
    def pid(self):
        return int((self.dir / (self.u + ".pid")).read_text())

    def cmdline(self):
        return Path(f"/proc/{self.pid()}/cmdline").read_bytes().replace(b"\0", b" ").decode()

    def activo(self):
        return subprocess.run(["systemctl", "is-active", "--quiet", self.u], env=self.env()).returncode == 0

    def respaldos(self):
        d = self.home / "respaldos-etapa4"
        return sorted(d.iterdir()) if d.exists() else []

    def evidencias(self):
        d = self.home / "evidencia-etapa4"
        return sorted(d.iterdir()) if d.exists() else []

    def instalados(self):
        return {p: sha(p) for p in self.fich}

    def cerrar(self):
        for f in self.dir.glob("*.pid"):
            try:
                os.kill(int(f.read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass


@pytest.fixture
def banco_b(tmp_path):
    b = Banco(tmp_path, "bastion")
    yield b
    b.cerrar()


@pytest.fixture
def banco_s(tmp_path):
    b = Banco(tmp_path, "srvdmz")
    yield b
    b.cerrar()


def respaldo_estricto(r):
    """Mismo criterio que p4_verificar_respaldo: hashes del manifiesto y conjunto exacto de ficheros."""
    lineas = (r / "SHA256SUMS").read_text().splitlines()
    listado = {}
    for l in lineas:
        h, nombre = l.split(maxsplit=1)
        listado[nombre.lstrip("*").removeprefix("./")] = h
    presentes = {str(p.relative_to(r)) for p in r.rglob("*") if p.is_file() and p.name != "SHA256SUMS"}
    assert presentes == set(listado), f"conjunto distinto: {presentes ^ set(listado)}"
    for n, h in listado.items():
        assert sha(r / n) == h, f"{n} no verifica"
    assert not any(n.endswith("salida.txt") for n in listado), "evidencia dentro del respaldo"
    assert not os.access(r / "SHA256SUMS", os.W_OK) or os.geteuid() == 0
    assert (r / "SHA256SUMS").stat().st_mode & 0o222 == 0, "el respaldo no quedó de solo lectura"


def evidencia_sellada(e):
    assert (e / "salida.txt").exists()
    assert subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=e).returncode == 0


def comunes(b, rc, salida):
    assert ("RESULTADO: OK" in salida) == (rc == 0), salida
    assert "--aplicar" not in b.uf.read_text().replace("SIN --aplicar", "")
    nft = [l for l in (b.dir / "ordenes.log").read_text().splitlines() if l.startswith("nft")]
    assert all(l == "nft list ruleset" for l in nft), nft
    for e in b.evidencias():
        evidencia_sellada(e)
        for r in b.respaldos():
            assert not str(e).startswith(str(r))


def sin_cambios(b):
    assert b.instalados() == b.antes
    assert b.activo()
    assert "--aplicar" not in b.cmdline()


# ================================================================== bastión
FALLOS_PREVIOS_B = [
    ("respaldo cp", {"CF_BANCO_FALLA": r"^sudo cp -p .*relay_eventos"}),
    ("ssh srv-dmz", {"CF_BANCO_FALLA": r"^ssh "}),
    ("verify unidad nueva (solo rc)", {"CF_BANCO_FALLA": r"^systemd-analyze verify .*/unidades/"}),
    ("relé inactivo", {"CF_BANCO_FALLA": r"^systemctl is-active --quiet ppi-relay"}),
]


def test_bastion_paquete_corrupto_para_sin_cambios(banco_b):
    (banco_b.paq / "scripts/engine/feed.py").write_text("# alterado\n")
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq))
    assert rc == 10 and "PARADA SIN CAMBIOS" in s
    comunes(banco_b, rc, s)
    sin_cambios(banco_b)
    assert banco_b.respaldos() == []


@pytest.mark.parametrize("nombre,falla", FALLOS_PREVIOS_B, ids=[x[0] for x in FALLOS_PREVIOS_B])
def test_bastion_fallo_previo_para_sin_cambios(banco_b, nombre, falla):
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq), **falla)
    assert rc == 10, s
    assert "PARADA SIN CAMBIOS" in s and "REVERSIÓN" not in s
    comunes(banco_b, rc, s)
    sin_cambios(banco_b)
    assert not any("install" in l for l in (banco_b.dir / "ordenes.log").read_text().splitlines()
                   if l.startswith("sudo install"))


FALLOS_TRAS_CAMBIO_B = [
    ("install py", {"CF_BANCO_FALLA_EN": r"^sudo install .*paquete/deploy/enforcement/relay_eventos.py"}),
    ("install unidad", {"CF_BANCO_FALLA_EN": r"^sudo install .*paquete/deploy/etapa4/unidades/bastion"}),
    ("daemon-reload", {"CF_BANCO_FALLA_EN": r"^sudo systemctl daemon-reload"}),
    ("verify unidad instalada (solo rc)", {"CF_BANCO_FALLA_EN": r"^systemd-analyze verify ppi-relay-eventos.service"}),
    ("restart", {"CF_BANCO_FALLA_EN": r"^sudo systemctl restart"}),
    ("is-active tras reiniciar", {"CF_BANCO_FALLA_EN": r"^systemctl is-active --quiet ppi-relay",
                                  "CF_BANCO_FALLA_NUM": 2}),
    ("sin entrega en modo paquete", {"CF_BANCO_NO_ENTREGA": "paquete"}),
]


@pytest.mark.parametrize("nombre,falla", FALLOS_TRAS_CAMBIO_B, ids=[x[0] for x in FALLOS_TRAS_CAMBIO_B])
def test_bastion_fallo_tras_cambio_revierte_y_verifica(banco_b, nombre, falla):
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq), **falla)
    assert rc == 20, s
    assert "REVERTIDO AUTOMÁTICAMENTE" in s and "NO continuar a la fase C de srv-dmz" in s
    comunes(banco_b, rc, s)
    sin_cambios(banco_b)
    assert "--entrega paquete" not in banco_b.cmdline()
    [r] = banco_b.respaldos()
    respaldo_estricto(r)
    modos = (r / "modos.txt").read_text()
    assert "640" in modos   # pub.pem restaurado con su modo propio
    assert oct((banco_b.raiz / "opt/cyberflow/relay-v2/pub.pem").stat().st_mode & 0o777) == "0o640"


def test_bastion_reversion_fallida_detiene_y_pide_intervencion(banco_b):
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq), CF_BANCO_FALLA=r"^sudo systemctl restart")
    assert rc == 30, s
    assert "REVERSIÓN AUTOMÁTICA FALLIDA" in s and "INTERVENCIÓN MANUAL" in s
    assert "No continuar a la fase C de srv-dmz ni a la observación" in s
    comunes(banco_b, rc, s)
    [r] = banco_b.respaldos()
    respaldo_estricto(r)          # el respaldo sigue íntegro para la reversión manual
    # los ficheros se restauraron aunque el reinicio no: la parada se debe a que no se pudo VERIFICAR el servicio
    assert banco_b.instalados() == banco_b.antes


def test_bastion_verify_con_texto_y_rc0_no_es_fallo(banco_b):
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq), CF_BANCO_ANALYZE_TEXTO=1)
    assert rc == 0, s
    assert "Unknown key name" in s


def test_bastion_exito_y_reversion_manual(banco_b):
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq))
    assert rc == 0, s
    assert s.count("RESULTADO: OK") == 1
    comunes(banco_b, rc, s)
    assert "--entrega paquete" in banco_b.cmdline()
    assert sha(banco_b.uf) == sha(banco_b.paq / "deploy/etapa4/unidades/bastion/ppi-relay-eventos.service")
    [r] = banco_b.respaldos()
    respaldo_estricto(r)
    [e] = banco_b.evidencias()
    assert (e / "instalados.sha256").exists()
    rc2, s2 = banco_b.ejecutar("revertir", str(r))
    assert rc2 == 0 and "REVERSIÓN MANUAL OK" in s2, s2
    sin_cambios(banco_b)
    assert "--entrega paquete" not in banco_b.cmdline()
    respaldo_estricto(r)          # revertir no escribe dentro del respaldo


def test_bastion_reversion_manual_respaldo_alterado_falla(banco_b):
    rc, s = banco_b.ejecutar("instalar", str(banco_b.paq))
    assert rc == 0, s
    [r] = banco_b.respaldos()
    f = r / "ficheros" / "relay_eventos.py"
    f.chmod(0o644)
    f.write_text("# manipulado\n")
    rc2, s2 = banco_b.ejecutar("revertir", str(r))
    assert rc2 == 30 and "REVERSIÓN MANUAL FALLIDA" in s2, s2
    assert "--entrega paquete" in banco_b.cmdline()   # no tocó nada con un respaldo que no verifica


# ================================================================== srv-dmz fase C
def preparar_fase_c(b, fase_a=True):
    """Estado de srv-dmz tras la fase A (código nuevo, unidad vieja) y relé ya en modo paquete (feed.par fresco)."""
    if fase_a:
        for org, dst in (("scripts/enforce/agente_enforce_v2.py", "opt/cyberflow/agente-v2/agente_enforce_v2.py"),
                         ("scripts/engine/feed.py", "opt/cyberflow/agente-v2/feed.py"),
                         ("deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh", "usr/local/bin/cf-feed-ssh.sh")):
            (b.raiz / dst).write_bytes((b.paq / org).read_bytes())
        b.antes = {p: sha(p) for p in b.fich}
    par = b.raiz / "var/lib/cyberflow/feed/feed.par"
    par.write_text("{}")
    return par


def test_srvdmz_fase_c_sin_fase_a_para_sin_cambios(banco_s):
    preparar_fase_c(banco_s, fase_a=False)
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq))
    assert rc == 10 and "código de la fase A instalado" in s, s
    comunes(banco_s, rc, s)
    sin_cambios(banco_s)


FALLOS_PREVIOS_S = [
    ("feed.par ausente", {}, None),
    ("respaldo cp", {"CF_BANCO_FALLA": r"^sudo -n cp -p .*agente_enforce_v2"}, True),
    ("ruleset ilegible", {"CF_BANCO_FALLA": r"^nft "}, True),
    ("verify unidad nueva (solo rc)", {"CF_BANCO_FALLA": r"^systemd-analyze verify .*/unidades/"}, True),
]


@pytest.mark.parametrize("nombre,falla,par", FALLOS_PREVIOS_S, ids=[x[0] for x in FALLOS_PREVIOS_S])
def test_srvdmz_fase_c_fallo_previo_para_sin_cambios(banco_s, nombre, falla, par):
    p = preparar_fase_c(banco_s)
    if par is None:
        p.unlink()
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq), **falla)
    assert rc == 10, s
    assert "PARADA SIN CAMBIOS" in s
    comunes(banco_s, rc, s)
    sin_cambios(banco_s)


def test_srvdmz_fase_c_feed_par_viejo_para(banco_s):
    par = preparar_fase_c(banco_s)
    viejo = time.time() - 600
    os.utime(par, (viejo, viejo))
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq))
    assert rc == 10 and "feed.par existe y se actualiza" in s, s
    sin_cambios(banco_s)


FALLOS_TRAS_CAMBIO_S = [
    ("install unidad", {"CF_BANCO_FALLA_EN": r"^sudo -n install .*paquete/deploy/etapa4/unidades/srvdmz"}),
    ("daemon-reload", {"CF_BANCO_FALLA_EN": r"^sudo -n systemctl daemon-reload"}),
    ("verify unidad instalada (solo rc)",
     {"CF_BANCO_FALLA_EN": r"^systemd-analyze verify ppi-enforce-agent-v2-dmz.service"}),
    ("restart", {"CF_BANCO_FALLA_EN": r"^sudo -n systemctl restart"}),
    ("is-active tras reiniciar", {"CF_BANCO_FALLA_EN": r"^systemctl is-active --quiet ppi-enforce",
                                  "CF_BANCO_FALLA_NUM": 2}),
    ("sin recepción en modo paquete", {"CF_BANCO_NO_ENTREGA": "paquete"}),
]


@pytest.mark.parametrize("nombre,falla", FALLOS_TRAS_CAMBIO_S, ids=[x[0] for x in FALLOS_TRAS_CAMBIO_S])
def test_srvdmz_fase_c_fallo_tras_cambio_revierte(banco_s, nombre, falla):
    preparar_fase_c(banco_s)
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq), **falla)
    assert rc == 20, s
    assert "REVERTIDO AUTOMÁTICAMENTE" in s and "NO continuar a la transición en sombra ni a la observación" in s
    assert "revertir el bastión A MANO" in s     # se distingue lo automático de lo que queda manual
    comunes(banco_s, rc, s)
    sin_cambios(banco_s)
    assert "--paquete" not in banco_s.cmdline()
    [r] = banco_s.respaldos()
    respaldo_estricto(r)
    assert oct((banco_s.raiz / "usr/local/sbin/cf-nft-helper").stat().st_mode & 0o777) == "0o750"


def test_srvdmz_fase_c_ruleset_cambiado_no_se_da_por_revertido(banco_s):
    """Si aparece una tabla nft (violación de la sombra) la reversión de ficheros no la deshace: rc 30, nunca 20."""
    preparar_fase_c(banco_s)
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq), CF_BANCO_RULESET_CAMBIA=1)
    assert rc == 30, s
    assert "ruleset igual al del respaldo" in s and "INTERVENCIÓN MANUAL" in s
    comunes(banco_s, rc, s)
    [r] = banco_s.respaldos()
    respaldo_estricto(r)


def test_srvdmz_fase_c_reversion_fallida(banco_s):
    preparar_fase_c(banco_s)
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq), CF_BANCO_FALLA=r"^sudo -n systemctl daemon-reload")
    assert rc == 30 and "REVERSIÓN AUTOMÁTICA FALLIDA" in s, s
    comunes(banco_s, rc, s)


def test_srvdmz_fase_c_exito_y_reversion_manual(banco_s):
    preparar_fase_c(banco_s)
    rc, s = banco_s.ejecutar("fase-c", str(banco_s.paq), CF_BANCO_ANALYZE_TEXTO=1)
    assert rc == 0, s
    assert s.count("RESULTADO: OK") == 1
    comunes(banco_s, rc, s)
    assert "--paquete /var/lib/cyberflow/feed/feed.par" in banco_s.cmdline()
    assert "--aplicar" not in banco_s.cmdline()
    [r] = banco_s.respaldos()
    respaldo_estricto(r)
    rc2, s2 = banco_s.ejecutar("revertir", str(r))
    assert rc2 == 0 and "REVERSIÓN MANUAL OK" in s2, s2
    sin_cambios(banco_s)


def test_srvdmz_fase_a_exito(banco_s):
    rc, s = banco_s.ejecutar("fase-a", str(banco_s.paq))
    assert rc == 0, s
    comunes(banco_s, rc, s)
    assert sha(banco_s.raiz / "usr/local/bin/cf-feed-ssh.sh") == sha(
        banco_s.paq / "deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh")
    assert sha(banco_s.uf) == banco_s.antes[banco_s.uf]       # la fase A no toca la unidad


def test_srvdmz_revertir_heredado(banco_s):
    """Respaldo con el formato de la versión .1 (ficheros en la raíz + evidencia fase-a-* dentro, sin listar)."""
    r0 = banco_s.home / "respaldos-etapa4" / "srvdmz-p4-20261106T035127Z"
    r0.mkdir(parents=True)
    for p in banco_s.fich:
        shutil.copy2(p, r0 / p.name)
    (r0 / "ruleset.nft").write_text(RULESET)
    (r0 / "instalados-antes.sha256").write_text("".join(f"{banco_s.antes[p]}  {p}\n" for p in banco_s.fich))
    subprocess.run("find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS",
                   shell=True, cwd=r0, check=True)
    (r0 / "fase-a-20261106T035128Z").mkdir()
    (r0 / "fase-a-20261106T035128Z" / "salida.txt").write_text("evidencia .1\n")
    rc, s = banco_s.ejecutar("fase-a", str(banco_s.paq))
    assert rc == 0, s
    assert banco_s.instalados() != banco_s.antes
    rc2, s2 = banco_s.ejecutar("revertir-heredado", str(r0))
    assert rc2 == 0 and "REVERSIÓN MANUAL OK (estado previo a la fase A)" in s2, s2
    assert "fase-a-20261106T035128Z/salida.txt" in s2      # se informa lo no listado, no se usa
    sin_cambios(banco_s)
    assert oct((banco_s.raiz / "usr/local/bin/cf-feed-ssh.sh").stat().st_mode & 0o777) == "0o755"
