"""Corre EN Sensor1 (por stdin). Hitos de una IP desde t0: deteccion y publicacion. Solo lectura.

Misma politica que el publicador y el panel (politica A, 3-nov tarde):
  - una regla actua desde su primera ventana;
  - el modelo SOLO ya no actua: su anomalia clara y sostenida (score < umbral - 0,05,
    3 ventanas en 120 s) se cuenta como «revision» y acompana a la regla («modelo y
    regla») cuando coinciden. Una anomalia marginal o suelta se cuenta en «marginales».
"""
import json, sys, time
from datetime import datetime
from collections import deque

ip, t0 = sys.argv[1], float(sys.argv[2])
MARGEN, SOSTENIDA_S, MIN_CLARAS = 0.0, 120, 1   # motor de las campañas (demo: 0.05, 120, 3)
MODELO_SOLO_ACTUA = True    # = publicar_feed.MODELO_SOLO_ACTUA (política A = False)
ventanas, marginales, primera, peor, modelo, regla = 0, 0, None, None, False, False
revision = 0
detectores = set()
claras_t: list[float] = []


def fin_ventana(d):
    try:
        return datetime.fromisoformat(d["window_end_utc"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return d.get("logged_at", 0)


def clara(d):
    s, u = d.get("score"), d.get("threshold")
    return d.get("decision") == "ALERT" and s is not None and u is not None and s < u - MARGEN


SEV = {"BLOCK": 2, "LIMIT": 1}
filas = []
with open("/home/m4rk/cyberflow/logs/motor_decision.log", encoding="utf-8") as fh:
    for linea in deque(fh, maxlen=8000):
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        if d.get("event") != "decision" or d.get("entity_ip") != ip or fin_ventana(d) <= t0:
            continue
        filas.append(d)
filas.sort(key=fin_ventana)
for d in filas:
    ventanas += 1
    h = d.get("heuristico") if isinstance(d.get("heuristico"), dict) else None
    acc = h["accion"] if h and h.get("accion") in SEV else None
    del_modelo = False
    if d.get("decision") == "ALERT":
        if clara(d):
            t = fin_ventana(d)
            claras_t.append(t)
            if sum(1 for x in claras_t if t - x <= SOSTENIDA_S) >= MIN_CLARAS:
                del_modelo = True
                if not h:
                    revision += 1
                if MODELO_SOLO_ACTUA:
                    acc = acc or "LIMIT"
            elif not h:
                marginales += 1
        elif not h:
            marginales += 1
    if not acc:
        continue
    modelo |= del_modelo
    regla |= bool(h)
    if h:
        detectores.add(h.get("heuristico"))
    if del_modelo:
        detectores.add(d.get("model_name") or "modelo")
    fila = {"t": d["logged_at"], "accion": acc, "regla": h.get("heuristico") if h else None,
            "motivo": h.get("motivo") if h else "anomalía sostenida del modelo", "score": d.get("score"),
            "umbral": d.get("threshold")}
    if primera is None or fila["t"] < primera["t"]:
        primera = fila
    if peor is None or SEV[acc] > SEV[peor["accion"]]:
        peor = fila
feed = None
try:
    f = json.load(open("/home/m4rk/feed/feed.json", encoding="utf-8"))
    e = [x for x in f.get("entradas", []) if x.get("ip") == ip]
    feed = {"generado": f.get("generado"), "entrada": e[0] if e else None}
except (OSError, ValueError):
    pass
quien = "modelo y regla" if modelo and regla else ("regla" if regla else ("modelo" if modelo else None))
print(json.dumps({"ahora": time.time(), "ventanas": ventanas, "marginales": marginales, "revision": revision,
                  "primera": primera,
                  "peor": peor, "quien": quien, "feed": feed, "detectores": sorted(x for x in detectores if x)}))
