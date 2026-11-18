#!/usr/bin/env python3
"""Ensayo de la cadena POR EVENTOS con procesos reales (Etapa 2). SOLO banco Docker como root.

Lanza publicar_feed_v2.py --seguir, relay_eventos.py (transporte local) y dos
agente_enforce_v2.py --seguir (perfiles dmz y dns) con el helper y nft reales del
contenedor. Escribe decisiones sinteticas en un motor_decision.log y mide, por
evento, a partir de las trazas:
  logged_at -> leido_en -> publicado_en -> entregado_en -> recibido_en -> aplicado_en -> confirmado_en
Sin red: el rele copia entre directorios, asi que el tramo del rele NO incluye ssh
(en el laboratorio hay que sumar la latencia de ssh medida alli).
Casos adicionales: decision repetida (no renueva), reinicio del agente dmz a mitad,
y fallo de entrega a dc1 (directorio ausente) con reintento.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable


def decision(ip, w, regla, accion):
    t = time.time()
    return {"event": "decision", "entity_ip": ip, "window_end_utc": w, "logged_at": t, "decidido_en": t - 0.05,
            "detector_name": "if_limpio_2026_10", "decision": "PERMIT", "score": -0.5,
            "decision_id": "%s|%s" % (ip, w),
            "heuristicos": [{"heuristico": regla, "accion": accion, "motivo": "ensayo"}]}


def leer(p: Path):
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def main() -> int:
    if os.geteuid() != 0:
        print("solo en el banco Docker como root"); return 2
    d = Path(tempfile.mkdtemp())
    for x in ("sensor", "dmz", "dns"):
        (d / x).mkdir()
    sys.path.insert(0, str(RAIZ / "scripts/engine"))
    import feed
    feed.generar_claves(str(d / "priv.pem"), str(d / "pub.pem"))
    log = d / "motor_decision.log"
    log.write_text("")
    for perfil in ("dmz", "dns"):
        pd = d / ("etc-" + perfil)
        pd.mkdir(mode=0o755)
        os.chmod(d, 0o755)
        (pd / "perfil").write_text(perfil + "\n")
        os.chmod(pd / "perfil", 0o644)

    def helper(perfil):
        return "%s %s %s" % (PY, RAIZ / "deploy/pruebas-aisladas/helper_banco.py", d / ("etc-" + perfil) / "perfil")
    for t in ("cyberflow_dmz", "cyberflow_dns"):
        subprocess.run(["nft", "destroy", "table", "inet", t], capture_output=True)
    pub = subprocess.Popen([PY, str(RAIZ / "scripts/engine/publicar_feed_v2.py"), "--log", str(log),
                            "--estado", str(d / "sensor/estado.json"), "--clave-privada", str(d / "priv.pem"),
                            "--salida-feed", str(d / "sensor/feed.json"), "--salida-firma", str(d / "sensor/feed.sig"),
                            "--traza", str(d / "sensor/traza.jsonl"), "--seguir", "--sondeo-segundos", "0.25",
                            "--refresco-segundos", "20"])
    rele = subprocess.Popen([PY, str(RAIZ / "deploy/enforcement/relay_eventos.py"), "--transporte", "local",
                             "--origen", str(d / "sensor"), "--destino", "srv-dmz=%s" % (d / "dmz"),
                             "--destino", "dc1=%s" % (d / "dns-ausente"), "--traza", str(d / "rele.jsonl"),
                             "--clave-publica", str(d / "pub.pem"), "--sondeo-segundos", "1"])

    def agente(perfil, sub):
        shutil.copy(d / "pub.pem", d / sub / "pub.pem")
        return subprocess.Popen([PY, str(RAIZ / "scripts/enforce/agente_enforce_v2.py"), "--perfil", perfil,
                                 "--feed", str(d / sub / "feed.json"), "--firma", str(d / sub / "feed.sig"),
                                 "--clave-publica", str(d / sub / "pub.pem"), "--estado", str(d / sub / "estado.json"),
                                 "--traza", str(d / sub / "traza.jsonl"), "--helper", helper(perfil), "--aplicar",
                                 "--seguir", "--sondeo-segundos", "0.5", "--observar-segundos", "5"])
    ag = {"dmz": agente("dmz", "dmz"), "dns": agente("dns", "dns")}
    procs = [pub, rele]
    try:
        time.sleep(3)
        enviados = []
        for i in range(20):
            regla, acc = (("dns_entropy", "LIMIT") if i % 2 else ("port_scan", "BLOCK"))
            ip = "10.10.20.%d" % (100 + i)
            dec = decision(ip, "2026-11-01T10:%02d:%02d+00:00" % (i // 6, (i % 6) * 10), regla, acc)
            with log.open("a") as fh:
                fh.write(json.dumps(dec) + "\n")
            enviados.append(dec)
            if i == 4:  # el directorio de dc1 aparece: reintento del rele
                (d / "dns-ausente").symlink_to(d / "dns")
            if i == 10:  # reinicio del agente dmz
                ag["dmz"].terminate(); ag["dmz"].wait(); ag["dmz"] = agente("dmz", "dmz")
            if i == 12:  # la MISMA decision otra vez: no debe renovar
                with log.open("a") as fh:
                    fh.write(json.dumps(enviados[0]) + "\n")
            time.sleep(4)
        time.sleep(6)
    finally:
        for p in procs + list(ag.values()):
            p.terminate()
    tp = leer(d / "sensor/traza.jsonl")
    tr = leer(d / "rele.jsonl")
    ta = {k: leer(d / k / "traza.jsonl") for k in ("dmz", "dns")}
    filas = []
    for dec in enviados:
        eid = [n for p in tp for n in p["nuevos"] if n["decision_id"] == dec["decision_id"]]
        if not eid:
            filas.append({"decision_id": dec["decision_id"], "publicado": False}); continue
        n = eid[0]
        pubreg = next(p for p in tp if any(x["id"] == n["id"] for x in p["nuevos"]))
        perfil = "dns" if n["destino"] == "dc1" else "dmz"
        rel = next((r for r in tr if r["secuencia"] is not None and r["secuencia"] >= pubreg["secuencia"]
                    and "entregado_en" in r["destinos"].get(n["destino"], {})), None)
        apl = next((x for x in ta[perfil] if x["evento"] == "aplicacion"
                    and any(m["id"] == n["id"] for m in x["nuevos"])), None)
        conf = next((x for x in ta[perfil] if x["evento"] == "confirmacion" and n["id"] in x["confirmadas"]), None)
        rec = next((x for x in ta[perfil] if x["evento"] == "recepcion" and n["id"] in x.get("ids", [])), None)
        f = {"decision_id": dec["decision_id"], "destino": n["destino"], "id": n["id"],
             "leido": round(n["leido_en"] - dec["logged_at"], 3),
             "publicado": round(pubreg["publicado_en"] - dec["logged_at"], 3),
             "entregado": round(rel["destinos"][n["destino"]]["entregado_en"] - dec["logged_at"], 3) if rel else None,
             "recibido": round(rec["recibido_en"] - dec["logged_at"], 3) if rec else None,
             "aplicado": round(apl["aplicado_en"] - dec["logged_at"], 3) if apl else None,
             "confirmado": round(conf["confirmado_en"] - dec["logged_at"], 3) if conf else None}
        filas.append(f)
    def q(c):
        v = sorted(f[c] for f in filas if f.get(c) is not None)
        return {"n": len(v), "p50": v[len(v) // 2] if v else None, "max": v[-1] if v else None,
                "media": round(statistics.fmean(v), 3) if v else None}
    repetida = [n for p in tp for n in p["nuevos"] if n["decision_id"] == enviados[0]["decision_id"]]
    res = {"eventos": filas, "resumen_s_desde_logged_at": {c: q(c) for c in
           ("leido", "publicado", "entregado", "recibido", "aplicado", "confirmado")},
           "decision_repetida_genero_nuevos": len(repetida) - 1,
           "rele_errores": sum(1 for r in tr for v in r["destinos"].values() if "error" in v),
           "rele_reintento_dc1_ok": any("entregado_en" in r["destinos"].get("dc1", {}) for r in tr),
           "rechazos_agentes": {k: [x.get("motivo") for x in v if x["evento"] == "rechazo"] for k, v in ta.items()},
           "estado_nft": subprocess.run(["nft", "list", "ruleset"], capture_output=True, text=True).stdout[-1500:]}
    res["pasa"] = (all(f.get("confirmado") is not None for f in filas)
                   and res["decision_repetida_genero_nuevos"] == 0 and res["rele_reintento_dc1_ok"])
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["pasa"] else 1


if __name__ == "__main__":
    sys.exit(main())
