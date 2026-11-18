"""P5: el manifiesto se calcula sobre ficheros finalizados; salida.txt no cambia después de su hash."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
EV = RAIZ / "deploy" / "etapa4" / "comun" / "evidencia.sh"
pytestmark = pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None, reason="bash POSIX (banco)")


def correr(guion: str, d: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", guion, "x", str(EV), str(d)], capture_output=True, text=True, timeout=60)


def test_sellado_verifica_y_salida_completa(tmp_path):
    d = tmp_path / "ev"
    r = correr('source "$1"; ev_abrir "$2"; for i in $(seq 1 2000); do echo "linea $i"; done; '
               'echo dato > "$2/a.txt"; ev_sellar "$2"', d)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELLADO" in r.stdout
    sal = (d / "salida.txt").read_text()
    assert "linea 2000" in sal and "== fin" in sal                   # la última línea está ANTES del hash
    v = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=d, capture_output=True, text=True)
    assert v.returncode == 0, v.stdout


# Escritor que hace el papel de `tee` en el patrón antiguo: mantiene salida.txt ABIERTO y solo escribe cuando se le
# ordena. Cada paso se sincroniza con una barrera explícita (tuberías): nada depende de pausas ni del planificador.
ESCRITOR = r'''
import os, sys
ruta, orden, aviso = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
def esperar(palabra):
    linea = b""
    while not linea.endswith(b"\n"):
        c = os.read(orden, 1)
        if not c:
            sys.exit(f"tubería de órdenes cerrada esperando {palabra}")
        linea += c
    assert linea.decode().strip() == palabra, linea
f = open(ruta, "w")
f.write("inicio\n"); f.flush(); os.fsync(f.fileno())
os.write(aviso, b"escrito-inicio\n")            # barrera 1: salida.txt existe y contiene "inicio"
esperar("sigue")                                 # barrera 2: el manifiesto ya se calculó
f.write("== fin\n"); f.flush(); os.fsync(f.fileno()); f.close()
os.write(aviso, b"escrito-fin\n")               # barrera 3: la línea final ya está en disco y el fichero cerrado
'''

MANIFIESTO_ANTIGUO = ('cd "$1" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum '
                      '> SHA256SUMS')       # orden literal de cierre4a_*.sh (antes de P5)


def _leer_linea(fd: int) -> str:
    b = b""
    while not b.endswith(b"\n"):
        c = os.read(fd, 1)
        assert c, "el escritor terminó sin avisar"
        b += c
    return b.decode().strip()


def test_patron_antiguo_falla(tmp_path):
    """Reproduce, en orden controlado, el defecto de cierre4a_*.sh: el manifiesto se calcula mientras el escritor de
    salida.txt sigue abierto y la última línea llega DESPUÉS del hash -> sha256sum -c lo detecta."""
    d = tmp_path / "ev"
    d.mkdir()
    sal = d / "salida.txt"
    o_r, o_w = os.pipe()     # órdenes  prueba -> escritor
    a_r, a_w = os.pipe()     # avisos   escritor -> prueba
    p = subprocess.Popen([sys.executable, "-c", ESCRITOR, str(sal), str(o_r), str(a_w)], pass_fds=(o_r, a_w))
    os.close(o_r)
    os.close(a_w)
    try:
        assert _leer_linea(a_r) == "escrito-inicio"
        # (1) salida.txt existe antes de calcular el manifiesto
        assert sal.read_text() == "inicio\n"
        r = subprocess.run(["bash", "-c", MANIFIESTO_ANTIGUO, "x", str(d)], capture_output=True, text=True,
                           timeout=60)
        assert r.returncode == 0, r.stderr
        # (2) el manifiesto incluye ese fichero, con el hash de su contenido de ese momento
        manifiesto = (d / "SHA256SUMS").read_text()
        assert hashlib.sha256(b"inicio\n").hexdigest() + "  ./salida.txt" in manifiesto
        assert subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=d, capture_output=True).returncode == 0
        # (3) solo ahora, y por orden explícita, el escritor añade contenido
        os.write(o_w, b"sigue\n")
        assert _leer_linea(a_r) == "escrito-fin"
    finally:
        os.close(o_w)
        os.close(a_r)
        assert p.wait(timeout=60) == 0
    assert sal.read_text() == "inicio\n== fin\n"
    # (4) la verificación detecta el cambio, y solo en salida.txt
    v = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=d, capture_output=True, text=True)
    assert v.returncode != 0
    assert "./salida.txt: FAILED" in v.stdout


def test_sellado_nuevo_hashes_validos_sobre_ficheros_finalizados(tmp_path):
    """Comprobación separada del sellado nuevo: con escritura y línea final, ev_sellar cierra el tee, espera y solo
    entonces calcula; el manifiesto verifica y cubre la última línea."""
    d = tmp_path / "ev"
    r = correr('source "$1"; ev_abrir "$2"; echo inicio; echo dato > "$2/b.txt"; echo "ultima linea"; '
               'ev_sellar "$2"; echo "rc=$?" >&2', d)
    assert "rc=0" in r.stdout + r.stderr, r.stdout + r.stderr
    sal = (d / "salida.txt").read_text()
    assert "inicio" in sal and "ultima linea" in sal
    m = (d / "SHA256SUMS").read_text()
    assert "salida.txt" in m and "b.txt" in m
    for linea in m.splitlines():
        h, nombre = linea.split(None, 1)
        assert hashlib.sha256((d / nombre.lstrip("*").removeprefix("./")).read_bytes()).hexdigest() == h
    v = subprocess.run(["sha256sum", "-c", "--strict", "SHA256SUMS"], cwd=d, capture_output=True, text=True)
    assert v.returncode == 0, v.stdout


def test_no_sella_si_algo_sigue_escribiendo(tmp_path):
    d = tmp_path / "ev"
    # el escritor NO hereda la tubería de tee (si la heredara, ev_sellar esperaría a que termine: también correcto)
    r = correr('source "$1"; ev_abrir "$2"; ( for i in 1 2 3 4 5 6; do echo x >> "$2/vivo.txt"; sleep 0.3; done ) '
               '> /dev/null 2>&1 & '
               'ev_sellar "$2"; echo rc=$?', d)
    assert "PARADA la evidencia sigue cambiando" in r.stdout and "rc=1" in r.stdout
