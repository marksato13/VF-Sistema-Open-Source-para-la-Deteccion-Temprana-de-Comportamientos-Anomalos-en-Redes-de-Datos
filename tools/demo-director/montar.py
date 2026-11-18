"""Monta en Herdr el espacio «CYBERFLOW DEMO»: 4 maquinas + el director.

  ┌ ORIGEN (Kali / clientes) ┬ SENSOR1 (motor) ─────────┐
  ├ SRV-DMZ (objetivo)       ┼ BASTIÓN · Suricata ──────┤
  └──────────────── DIRECTOR (python director.py) ──────┘

Cada panel entra por SSH al bastion con la llave de siempre y salta con el alias
(ssh kali / sensor1 / srvdmz). No guarda ni escribe contrasenas.
Uso: python montar.py [--focus]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASTION = "gadmin@10.10.10.30"


def h(*args):
    r = subprocess.run(["herdr", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit("herdr %s: %s" % (" ".join(args), r.stderr or r.stdout))
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}


def split(pane, direccion, ratio):
    return h("pane", "split", pane, "--direction", direccion, "--ratio", str(ratio), "--cwd", str(AQUI),
             "--no-focus")["result"]["pane"]["pane_id"]


def esperar(pane, texto, ms=25000):
    r = subprocess.run(["herdr", "pane", "wait-output", pane, "--match", texto, "--source", "recent",
                        "--lines", "40", "--timeout", str(ms)], capture_output=True, text=True)
    return r.returncode == 0


ws = h("workspace", "create", "--label", "CYBERFLOW DEMO", "--cwd", str(AQUI),
       *(["--focus"] if "--focus" in sys.argv else ["--no-focus"]))["result"]
raiz = ws["root_pane"]["pane_id"]
director = split(raiz, "down", 0.30)        # abajo, el director
derecha = split(raiz, "right", 0.5)         # arriba a la derecha
srvdmz = split(raiz, "down", 0.5)           # abajo a la izquierda
bastion = split(derecha, "down", 0.5)       # abajo a la derecha
ids = {"workspace": ws["workspace"]["workspace_id"], "origen": raiz, "sensor": derecha,
       "srvdmz": srvdmz, "bastion": bastion, "director": director, "origen_host": "kali"}

nombres = {"origen": "ORIGEN · KALI", "sensor": "SENSOR1", "srvdmz": "SRV-DMZ", "bastion": "BASTIÓN · Suricata",
           "director": "DIRECTOR"}
for k, n in nombres.items():
    h("pane", "rename", ids[k], n)

saltos = {"origen": ("kali", "kali)-["), "sensor": ("sensor1", "m4rk@cyberflow-sensor"),
          "srvdmz": ("srvdmz", "adminsrvdmz@srv-dmz"), "bastion": (None, "gadmin@VM-GESTION")}
for k, (alias, prompt) in saltos.items():
    h("pane", "run", ids[k], "ssh -t " + BASTION)
for k, (alias, prompt) in saltos.items():
    ok = esperar(ids[k], "gadmin@VM-GESTION")
    if alias:
        h("pane", "run", ids[k], "ssh " + alias)
        ok = esperar(ids[k], prompt)
    print("%-8s %s %s" % (k, ids[k], "conectado" if ok else "SIN RESPUESTA"))

(AQUI / "estado-herdr.json").write_text(json.dumps(ids, indent=1), encoding="utf-8")
h("pane", "run", ids["director"], "python director.py")
print("listo:", ids["workspace"])
