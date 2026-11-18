"""Copia los scripts de la demo a ~/cf-demo/ del bastion, Sensor1 y srv-dmz.

Solo escribe en el HOME de cada usuario (sin sudo) y solo scripts de lectura.
Uso: python instalar_remoto.py
"""
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent / "remoto"
BASTION = "gadmin@10.10.10.30"


def sh(*args, entrada=None):
    r = subprocess.run(args, input=entrada, capture_output=True)
    if r.returncode:
        raise SystemExit("falló %s: %s" % (" ".join(args[:3]), r.stderr.decode(errors="replace")))
    return r.stdout.decode(errors="replace")


def lf(p: Path) -> bytes:
    return p.read_bytes().replace(b"\r\n", b"\n")


# bastion: directamente
for f in sorted((AQUI / "bastion").iterdir()):
    sh("ssh", BASTION, "mkdir -p ~/cf-demo && cat > ~/cf-demo/%s && chmod +x ~/cf-demo/%s" % (f.name, f.name), entrada=lf(f))
    print("bastion  ~/cf-demo/%s" % f.name)
# hosts: por el bastion, con su alias
for host in ("sensor1", "srvdmz"):
    for f in sorted((AQUI / host).iterdir()):
        sh("ssh", BASTION, "ssh -o BatchMode=yes %s 'mkdir -p ~/cf-demo && cat > ~/cf-demo/%s && chmod +x ~/cf-demo/%s'"
           % (host, f.name, f.name), entrada=lf(f))
        print("%-8s ~/cf-demo/%s" % (host, f.name))
