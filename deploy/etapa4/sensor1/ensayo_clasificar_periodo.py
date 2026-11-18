#!/usr/bin/env python3
"""Banco de clasificar_periodo.py (cierre 4A). Sin red ni journal: usa ficheros dados.

  ensayo_clasificar_periodo.py SALUD_CAPTURA.py DIR_4A
DIR_4A = evidencia de la observación de la 4A (salud/ con muestras.jsonl y los journals con margen).
P1  datos reales de la 4A: anillo C1 y vía rápida C1 (solo los 7 descartes de Suricata), PID único.
P2  los dos journals juntos en la misma captura -> C3 «varios PID» (por eso se separan).
P3  periodo indicado fuera de las muestras -> no_evaluable, sin recortar.
P4  journal vacío -> no_evaluable (no «0 descartes»).
P5  journal sin margen (empieza después del inicio) -> C3 «sin lecturas que acoten».
P6  reinicio de Suricata dentro de las muestras -> dos segmentos y reinicio contado dentro.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SC, D = Path(sys.argv[1]), Path(sys.argv[2]) / "salud"
YO = Path(__file__).resolve().parent / "clasificar_periodo.py"
fallos = 0


def correr(*extra, muestras=D / "muestras.jsonl"):
    sal = Path(tempfile.mkdtemp())
    r = subprocess.run([sys.executable, "-I", str(YO), "--salud-captura", str(SC), "--muestras", str(muestras),
                        "--salida", str(sal), *extra], capture_output=True, text=True)
    return r.returncode, json.loads((sal / "clasificacion.json").read_text(encoding="utf-8")), r


def ok(nombre, cond, detalle=""):
    global fallos
    print(("OK    " if cond else "FALLO ") + nombre + ("" if cond else "  " + str(detalle)[:600]))
    fallos += 0 if cond else 1


jc, jv = D / "journal-captura-margen.txt", D / "journal-via-rapida-margen.txt"
rc, res, _ = correr("--journal", "captura=%s" % jc, "--journal", "via-rapida=%s" % jv)
cap, via = res["capturas"]["captura"], res["capturas"]["via-rapida"]
ok("P1 anillo C1 por Suricata", cap["clase"] == "C1" and any("Suricata" in m for m in cap["motivos"]), cap.get("motivos"))
ok("P1 vía rápida C1 por Suricata", via["clase"] == "C1", via.get("motivos"))
ok("P1 PID único y 0 descartes del kernel", cap["continuidad"]["pids"] and len(cap["continuidad"]["pids"]) == 1
   and cap["continuidad"]["descartados_kernel"] == 0, cap.get("continuidad"))
ok("P1 clase del periodo C1", res["clase_periodo"] == "C1", res["clase_periodo"])

mezcla = Path(tempfile.mkdtemp()) / "mezcla.txt"
mezcla.write_text(jc.read_text(encoding="utf-8") + jv.read_text(encoding="utf-8"), encoding="utf-8")
rc, res, _ = correr("--journal", "captura=%s" % mezcla, "--journal", "via-rapida=%s" % jv)
ok("P2 journals mezclados = C3 varios PID", res["capturas"]["captura"]["clase"] == "C3"
   and any("varios PID" in m for m in res["capturas"]["captura"]["motivos"]), res["capturas"]["captura"]["motivos"])

m = [json.loads(l) for l in (D / "muestras.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
rc, res, _ = correr("--desde", str(m[0]["t"] - 60), "--hasta", str(m[-1]["t"]),
                    "--journal", "captura=%s" % jc, "--journal", "via-rapida=%s" % jv)
ok("P3 periodo fuera de la cobertura = no_evaluable", rc == 3 and res["clase_periodo"] == "no_evaluable", res.get("motivo"))

vacio = Path(tempfile.mkdtemp()) / "vacio.txt"
vacio.write_text("", encoding="utf-8")
rc, res, _ = correr("--journal", "captura=%s" % vacio, "--journal", "via-rapida=%s" % jv)
ok("P4 journal vacío = no_evaluable", res["capturas"]["captura"]["clase"] == "no_evaluable"
   and res["clase_periodo"] == "no_evaluable", res["capturas"]["captura"])

corto = Path(tempfile.mkdtemp()) / "corto.txt"
lineas = jc.read_text(encoding="utf-8").splitlines()
corto.write_text("\n".join(lineas[len(lineas) // 4:]) + "\n", encoding="utf-8")
rc, res, _ = correr("--journal", "captura=%s" % corto, "--journal", "via-rapida=%s" % jv)
ok("P5 journal sin margen = C3 sin acotar", res["capturas"]["captura"]["clase"] == "C3"
   and any("acoten" in x for x in res["capturas"]["captura"]["motivos"]), res["capturas"]["captura"]["motivos"])

mm = [dict(x) for x in m]
mitad = len(mm) // 2
base = mm[mitad - 1]["suricata"]
for x in mm[mitad:]:
    s = dict(x["suricata"])
    s["uptime_s"] = s["uptime_s"] - base["uptime_s"] + 5
    s["kernel_packets"] -= base["kernel_packets"]
    s["kernel_drops"] -= base["kernel_drops"]
    x["suricata"] = s
fm = Path(tempfile.mkdtemp()) / "muestras.jsonl"
fm.write_text("".join(json.dumps(x) + "\n" for x in mm), encoding="utf-8")
rc, res, _ = correr("--journal", "captura=%s" % jc, "--journal", "via-rapida=%s" % jv, muestras=fm)
segs = res["suricata"]["segmentos"]
ok("P6 reinicio de Suricata = 2 segmentos, 1 dentro y C3", len(segs) == 2
   and res["suricata"]["reinicios_dentro_del_periodo"] == 1 and res["capturas"]["captura"]["clase"] == "C3",
   [len(segs), res["suricata"]["reinicios_dentro_del_periodo"], res["capturas"]["captura"]["motivos"]])
ok("P6 contadores por segmento no negativos", all(g["paquetes"] >= 0 and g["descartes"] >= 0 for g in segs), segs)

print("RESULTADO:", "OK" if not fallos else "%d FALLO(S)" % fallos)
sys.exit(1 if fallos else 0)
