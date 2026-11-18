"""Despliega el panel al Sensor1 en un solo paso: comprueba, copia y reinicia.

Uso:  python desplegar_panel.py [fichero_extra ...]

Lleva scripts/engine/dashboard.py de este repositorio (rama main) al Sensor1
pasando por el bastion, guarda una copia del anterior y reinicia ppi-dashboard.
Los ficheros extra se dan relativos a la raiz del repositorio y se copian a la
misma ruta en el sensor. No lleva credenciales: usa las claves SSH ya instaladas.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

# 18-nov: el panel en uso esta en main; el script vive en tools/despliegue/.
REPO = Path(__file__).resolve().parents[2]
BASTION = "gadmin@10.10.10.30"
SENSOR = "m4rk@10.10.60.11"
CLAVE = "~/.ssh/cyberflow-to-sensor"

REMOTO = r"""set -u
cd ~/cyberflow
SELLO=$(date +%Y%m%d-%H%M%S)
cp -p scripts/engine/dashboard.py "scripts/engine/dashboard.py.bak-$SELLO"
while read -r nombre destino; do
  [ -n "$nombre" ] || continue
  mkdir -p "$(dirname "$destino")"
  cp ~/cf-deploy/"$nombre" "$destino"
done < ~/cf-deploy/panel.lista
.venv/bin/python -c 'import ast,sys; ast.parse(open(sys.argv[1], encoding="utf-8").read())' scripts/engine/dashboard.py || { cp -p "scripts/engine/dashboard.py.bak-$SELLO" scripts/engine/dashboard.py; echo "NO COMPILA: restaurado"; exit 1; }
sudo -n systemctl restart ppi-dashboard && sleep 4
echo "panel: $(systemctl is-active ppi-dashboard) · respaldo dashboard.py.bak-$SELLO"
ls -t scripts/engine/dashboard.py.bak-* | tail -n +6 | xargs -r rm --
"""


def correr(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode:
        sys.exit("FALLO (%d): %s\n%s" % (r.returncode, " ".join(cmd[:3]), r.stderr.strip()))


def main():
    rutas = ["scripts/engine/dashboard.py"] + sys.argv[1:]
    correr([sys.executable, "-m", "py_compile", str(REPO / rutas[0])])
    tmp = Path(tempfile.gettempdir()) / "cf-despliegue"
    tmp.mkdir(exist_ok=True)
    (tmp / "panel.sh").write_text(REMOTO, encoding="utf-8", newline="\n")
    lista, locales = [], [str(tmp / "panel.sh"), str(tmp / "panel.lista")]
    for r in rutas:
        nombre = r.replace("/", "__")
        lista.append("%s %s" % (nombre, r))
        (tmp / nombre).write_bytes((REPO / r).read_bytes())
        locales.append(str(tmp / nombre))
    (tmp / "panel.lista").write_text("\n".join(lista) + "\n", encoding="utf-8", newline="\n")
    correr(["scp", "-q"] + locales + [BASTION + ":cf-stage/"])
    nombres = " ".join("cf-stage/" + Path(p).name for p in locales)
    correr(["ssh", BASTION,
            "scp -q -i %s %s %s:cf-deploy/ && ssh -i %s %s bash cf-deploy/panel.sh"
            % (CLAVE, nombres, SENSOR, CLAVE, SENSOR)])


if __name__ == "__main__":
    main()
