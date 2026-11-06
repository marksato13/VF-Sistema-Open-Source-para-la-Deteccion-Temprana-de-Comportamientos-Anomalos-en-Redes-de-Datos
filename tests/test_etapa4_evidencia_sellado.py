"""P5: el manifiesto se calcula sobre ficheros finalizados; salida.txt no cambia después de su hash."""
from __future__ import annotations

import os
import shutil
import subprocess
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


def test_patron_antiguo_falla(tmp_path):
    """Reproduce el defecto de cierre4a_*.sh: hash con tee abierto + echo final -> sha256sum -c falla."""
    d = tmp_path / "ev"
    d.mkdir()
    guion = ('exec > >(tee "$2/salida.txt") 2>&1; echo inicio; '
             '( cd "$2" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS ); '
             'echo "== fin"; sleep 0.5')
    subprocess.run(["bash", "-c", guion, "x", str(EV), str(d)], capture_output=True, timeout=60)
    v = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=d, capture_output=True, text=True)
    assert v.returncode != 0 and "salida.txt" in v.stdout


def test_no_sella_si_algo_sigue_escribiendo(tmp_path):
    d = tmp_path / "ev"
    # el escritor NO hereda la tubería de tee (si la heredara, ev_sellar esperaría a que termine: también correcto)
    r = correr('source "$1"; ev_abrir "$2"; ( for i in 1 2 3 4 5 6; do echo x >> "$2/vivo.txt"; sleep 0.3; done ) '
               '> /dev/null 2>&1 & '
               'ev_sellar "$2"; echo rc=$?', d)
    assert "PARADA la evidencia sigue cambiando" in r.stdout and "rc=1" in r.stdout
