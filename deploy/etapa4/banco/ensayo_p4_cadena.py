#!/usr/bin/env python3
"""Ensayo de banco P4 (2026-11-06): cadena publicador -> relé -> agente con firma ed25519 real, en ambos modos.

Solo banco aislado (contenedor sin red). Nada del laboratorio. El agente corre como PROCESO aparte con su bucle real
(``agente_enforce_v2.py --seguir``, sondeo 0,5 s como en srv-dmz, sin --aplicar, helper que no hace nada); el relé
corre en este proceso con TransporteLocal. Para acercarse al laboratorio, la confirmación de la pareja deja
``--hueco-ms`` entre los dos mv (en srv-dmz son dos procesos mv lanzados por ssh) y el publicador publica cada
``--periodo`` s. Mide, por modo:

  - rechazos firma_invalida / paquete_invalido del agente;
  - secuencias publicadas, entregadas y aceptadas (ninguna aceptada fuera de orden; ninguna perdida entre las
    entregadas salvo las que el diseño «último estado» sustituye antes de que el agente las lea);
  - retraso publicación -> recepción del agente (p50/p95/máx) y retraso de recuperación tras cada rechazo.

  python3 ensayo_p4_cadena.py --modo pareja --generaciones 300 --salida /tmp/p4-pareja.json
  python3 ensayo_p4_cadena.py --modo paquete --generaciones 300 --salida /tmp/p4-paquete.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))
sys.path.insert(0, str(RAIZ / "deploy" / "enforcement"))
import feed  # noqa: E402
import relay_eventos as rele  # noqa: E402


class TransporteHueco(rele.TransporteLocal):
    def __init__(self, hueco_s: float):
        self.hueco_s = hueco_s

    def confirmar(self, destino):
        d = Path(destino["dir"])
        shutil.move(str(d / ".feed.sig.tmp"), str(d / "feed.sig"))
        time.sleep(self.hueco_s)
        shutil.move(str(d / ".feed.json.tmp"), str(d / "feed.json"))
        return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--modo", choices=("pareja", "paquete"), required=True)
    p.add_argument("--generaciones", type=int, default=300)
    p.add_argument("--periodo", type=float, default=0.05)
    p.add_argument("--hueco-ms", type=float, default=3.0)
    p.add_argument("--salida", type=Path, required=True)
    a = p.parse_args(argv)
    w = Path(tempfile.mkdtemp(prefix="p4-"))
    o, d = w / "origen", w / "destino"
    o.mkdir(); d.mkdir()
    priv, pub = w / "priv.pem", w / "pub.pem"
    feed.generar_claves(str(priv), str(pub))
    traza_ag = w / "agente.jsonl"
    cmd = [sys.executable, "-I", str(RAIZ / "scripts/enforce/agente_enforce_v2.py"), "--perfil", "dmz",
           "--clave-publica", str(pub), "--estado", str(w / "estado.json"), "--traza", str(traza_ag),
           "--helper", "%s -c pass" % sys.executable, "--seguir", "--sondeo-segundos", "0.5"]
    cmd += (["--paquete", str(d / "feed.par")] if a.modo == "paquete"
            else ["--feed", str(d / "feed.json"), "--firma", str(d / "feed.sig")])
    agente = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    r = rele.Rele({"dir": str(o), "host": None, "identidad": None}, [{"nombre": "srv-dmz", "dir": str(d)}],
                  TransporteHueco(a.hueco_ms / 1000), w / "rele.jsonl", rele.verificador(str(pub)), entrega=a.modo)
    publicadas, entregadas = {}, {}
    try:
        for s in range(1, a.generaciones + 1):
            ahora = time.time()
            datos = feed.serializar(feed.construir_v2([], s, ahora, 600))
            firma = feed.firmar(datos, str(priv))
            for nombre, b in (("feed.sig", firma), ("feed.json", datos)):   # como publicar_feed_v2
                tmp = o / (".%s.tmp" % nombre)
                tmp.write_bytes(b)
                os.replace(tmp, o / nombre)
            publicadas[s] = ahora
            reg = r.paso()
            if reg and "entregado_en" in (reg.get("destinos", {}).get("srv-dmz") or {}):
                entregadas[s] = reg["destinos"]["srv-dmz"]["entregado_en"]
            time.sleep(a.periodo)
        time.sleep(1.5)                                  # el agente lee la última
    finally:
        agente.terminate()
        agente.wait(10)
    ev = [json.loads(l) for l in traza_ag.read_text().splitlines()] if traza_ag.exists() else []
    rech = [e for e in ev if e["evento"] == "rechazo"]
    rec = [e for e in ev if e["evento"] == "recepcion"]
    acept = [e for e in rec if e["estado"] == "aceptado"]
    seqs = [e["secuencia"] for e in acept]
    retrasos = sorted(e["recibido_en"] - publicadas[e["secuencia"]] for e in acept if e["secuencia"] in publicadas)
    recup = []
    for x in rech:
        sig = next((e for e in acept if e["recibido_en"] > x.get("recibido_en", x["t"])), None)
        if sig:
            recup.append(round(sig["recibido_en"] - x.get("recibido_en", x["t"]), 3))
    q = lambda v, f: v[min(len(v) - 1, int(len(v) * f))] if v else None   # noqa: E731
    res = {"modo": a.modo, "generaciones": a.generaciones, "periodo_s": a.periodo, "hueco_ms": a.hueco_ms,
           "publicadas": len(publicadas), "entregadas": len(entregadas), "recepciones": len(rec),
           "aceptadas": len(acept), "rechazos": {m: sum(1 for x in rech if x["motivo"] == m)
                                                 for m in sorted({x["motivo"] for x in rech})},
           "aceptadas_en_orden": seqs == sorted(seqs) and len(seqs) == len(set(seqs)),
           "ultima_publicada": a.generaciones, "ultima_aceptada": seqs[-1] if seqs else None,
           "aceptada_no_entregada": sorted(set(seqs) - set(entregadas)),
           "retraso_pub_rec_s": {"p50": q(retrasos, .5), "p95": q(retrasos, .95), "max": retrasos[-1] if retrasos else None},
           "recuperacion_tras_rechazo_s": recup, "agente_stderr": agente.stderr.read().decode()[-300:]}
    a.salida.write_text(json.dumps(res, indent=1, sort_keys=True))
    print(json.dumps({k: res[k] for k in ("modo", "publicadas", "entregadas", "aceptadas", "rechazos",
                                          "aceptadas_en_orden", "ultima_aceptada", "retraso_pub_rec_s")}))
    shutil.rmtree(w, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
