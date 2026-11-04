#!/usr/bin/env python3
"""Clasificación de calidad de captura de un periodo, con las comprobaciones integradas (cierre 4A).

Envuelve ``scripts/etapa4/salud_captura.py`` del paquete congelado (ec78ca5) SIN modificarlo y fija
en el guion lo que en la 4A hubo que hacer a mano:

1. Periodo = cobertura REALMENTE medida. Sin --desde/--hasta: primera y última muestra (+/-0,01 s:
   ``t`` va redondeado a ms). Con --desde/--hasta: deben caer dentro de las muestras; si no, el
   periodo es ``no_evaluable`` (no se recorta para que encaje ni para excluir incidentes).
2. Anillo y vía rápida se clasifican POR SEPARADO (cada tcpdump con su propio journal): mezclar los
   dos da C3 «varios PID» aunque ninguno se haya reiniciado.
3. Journal exportado con margen (--margen, 35 s por omisión > 30 s del timer + 2 s de tolerancia)
   antes y después, para que existan las lecturas SIGUSR1 que acotan el periodo.
4. Continuidad y PID: un solo PID por tcpdump en el periodo, sin huecos entre lecturas (lo comprueba
   ``cobertura_tcpdump``); se informan los PID y la cobertura.
5. Lectura fallida o insuficiente = ``no_evaluable`` (nunca «0 descartes»): journal que no se puede
   exportar, sin lecturas SIGUSR1, o ``clasificar`` sin muestras que acoten el periodo.
6. Suricata segmentado por proceso: cada bajada de uptime o de contador es un reinicio; se informan
   los contadores de cada segmento por separado y si algún reinicio cae dentro del periodo.

La clase de cada captura es la de ``salud_captura.clasificar`` (C0..C3, criterios congelados).
La clase del periodo es la peor de las capturas evaluadas; ``no_evaluable`` domina a todas.
No cambia I5 ni la población C0: solo decide con qué datos se clasifica.

Uso (Sensor1, m4rk; ``journalctl --no-pager`` está permitido):
  clasificar_periodo.py --salud-captura ~/cyberflow-e4/ec78ca5/scripts/etapa4/salud_captura.py \
      --muestras DIR/muestras.jsonl --salida DIR/clasificacion [--desde T --hasta T]
Sin acceso al journal (pruebas): --journal captura=FICHERO --journal via-rapida=FICHERO.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

CAPTURAS = {"captura": "ppi-motor-capture", "via-rapida": "ppi-via-rapida@ens37"}
ORDEN = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "no_evaluable": 4}


def cargar_salud(ruta: Path):
    spec = importlib.util.spec_from_file_location("salud_captura", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def leer_jsonl(p: Path) -> list[dict]:
    out = []
    for l in p.read_text(encoding="utf-8").splitlines():
        l = l.strip()
        if l:
            out.append(json.loads(l))
    return out


def segmentos_suricata(muestras: list[dict]) -> list[dict]:
    """Segmentos de proceso de Suricata (un reinicio = uptime o contador que decrece)."""
    segs, cur, prev = [], None, None
    for m in muestras:
        s = m.get("suricata") or {}
        if not s.get("ok"):
            continue
        reinicio = prev is not None and (s["uptime_s"] < prev["uptime_s"]
                                         or s["kernel_packets"] < prev["kernel_packets"]
                                         or s["kernel_drops"] < prev["kernel_drops"])
        if cur is None or reinicio:
            cur = {"desde_t": m["t"], "arranque_aprox_t": round(s["t"] - s["uptime_s"], 1),
                   "paquetes_ini": s["kernel_packets"], "descartes_ini": s["kernel_drops"]}
            segs.append(cur)
        cur.update({"hasta_t": m["t"], "paquetes_fin": s["kernel_packets"], "descartes_fin": s["kernel_drops"]})
        prev = s
    for g in segs:
        g["paquetes"] = g["paquetes_fin"] - g["paquetes_ini"]
        g["descartes"] = g["descartes_fin"] - g["descartes_ini"]
        g["descartes_por_millon"] = round(1e6 * g["descartes"] / g["paquetes"], 3) if g["paquetes"] else None
    return segs


def exportar_journal(unidad: str, desde: float, hasta: float, margen: float, destino: Path) -> dict:
    cmd = ["journalctl", "--no-pager", "-o", "short-iso-precise", "-u", unidad,
           "--since", "@%d" % int(desde - margen), "--until", "@%d" % int(hasta + margen + 1)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    destino.write_text(r.stdout, encoding="utf-8")
    n = r.stdout.count("packets captured")
    return {"ok": r.returncode == 0 and n > 0, "rc": r.returncode, "lecturas_sigusr1": n,
            "orden": " ".join(cmd), "error": r.stderr.strip()[:300]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salud-captura", type=Path, required=True)
    p.add_argument("--muestras", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--desde", type=float)
    p.add_argument("--hasta", type=float)
    p.add_argument("--margen", type=float, default=35.0)
    p.add_argument("--rotacion", type=float, default=5.0)
    p.add_argument("--journal", action="append", default=[], help="NOMBRE=FICHERO ya exportado (pruebas)")
    a = p.parse_args(argv)
    sc = cargar_salud(a.salud_captura)
    a.salida.mkdir(parents=True, exist_ok=True)
    muestras = leer_jsonl(a.muestras)
    res = {"version": "clasificar_periodo 2026-11-04.1", "salud_captura": sc.VERSION, "capturas": {}}
    if len(muestras) < 2:
        res.update(clase_periodo="no_evaluable", motivo="menos de dos muestras")
        return _fin(a, res, 3)
    t0, t1 = muestras[0]["t"], muestras[-1]["t"]
    desde = t0 + 0.01 if a.desde is None else a.desde
    hasta = t1 - 0.01 if a.hasta is None else a.hasta
    res.update(muestras={"n": len(muestras), "primera_t": t0, "ultima_t": t1},
               periodo={"desde": desde, "hasta": hasta, "duracion_s": round(hasta - desde, 1),
                        "origen": "muestras" if a.desde is None and a.hasta is None else "indicado"})
    if desde < t0 or hasta > t1 or hasta <= desde:
        res.update(clase_periodo="no_evaluable",
                   motivo="el periodo indicado no está dentro de la cobertura medida [%s, %s]; no se recorta" % (t0, t1))
        return _fin(a, res, 3)
    incs = sc.incrementos(muestras)
    with (a.salida / "incrementos.jsonl").open("w", encoding="utf-8") as fh:
        for x in incs:
            fh.write(json.dumps(x, sort_keys=True) + "\n")
    segs = segmentos_suricata(muestras)
    dentro = [g for g in segs[1:] if desde < g["desde_t"] <= hasta]
    res["suricata"] = {"segmentos": segs, "reinicios_dentro_del_periodo": len(dentro)}
    crit = dict(sc.CRITERIOS, rotacion_s=a.rotacion)
    dados = dict(x.split("=", 1) for x in a.journal)
    peor = "C0"
    for nombre, unidad in CAPTURAS.items():
        dest = a.salida / ("journal-%s.txt" % nombre)
        if nombre in dados:
            texto = Path(dados[nombre]).read_text(encoding="utf-8")
            dest.write_text(texto, encoding="utf-8")
            exp = {"ok": texto.count("packets captured") > 0, "lecturas_sigusr1": texto.count("packets captured"),
                   "orden": "fichero dado: " + dados[nombre]}
        else:
            exp = exportar_journal(unidad, desde, hasta, a.margen, dest)
        r = {"unidad": unidad, "journal": exp}
        if not exp["ok"]:
            r.update(clase="no_evaluable", motivos=["journal no exportado o sin lecturas SIGUSR1 (no es «0 descartes»)"])
        else:
            c = sc.clasificar(incs, sc.leer_tcpdump_log(dest), desde, hasta, crit)
            r.update(clase=c["clase"] if c["clase"] in ORDEN else "no_evaluable", motivos=c.get("motivos", []),
                     info=c.get("info"), acotado_por=c.get("acotado_por"))
            if c["clase"] == "insuficiente":
                r["motivos"] = ["clasificar: insuficiente"] + r["motivos"]
            tc = (c.get("info") or {}).get("tcpdump") or {}
            r["continuidad"] = {"pids": tc.get("pids"), "lecturas": tc.get("lecturas"),
                                "cobertura_tcpdump_ok": tc.get("ok"), "descartados_kernel": tc.get("descartados_kernel")}
        res["capturas"][nombre] = r
        if ORDEN[r["clase"]] > ORDEN[peor]:
            peor = r["clase"]
    res["clase_periodo"] = peor
    return _fin(a, res, 0 if peor != "no_evaluable" else 3)


def _fin(a, res: dict, rc: int) -> int:
    (a.salida / "clasificacion.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({"clase_periodo": res.get("clase_periodo"), "motivo": res.get("motivo"),
                      "capturas": {k: [v.get("clase"), v.get("motivos")] for k, v in res.get("capturas", {}).items()},
                      "suricata_reinicios_dentro": (res.get("suricata") or {}).get("reinicios_dentro_del_periodo")},
                     ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
