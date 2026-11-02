#!/usr/bin/env python3
"""Etapa 3: evalúa la regla temprana de escaneo sobre la tabla de intentos (extraer_syn.py).

Regla (por par origen→destino, causal): en el instante t, cuenta los puertos destino
DISTINTOS de los intentos con t_syn en (t − W, t] que, a la vista de lo ocurrido hasta t,
han FALLADO: RST del destino recibido en <= t, o sin SYN-ACK cuando han pasado g s.
Dispara la primera vez que ese conteo llega a K. Un SYN-ACK posterior a t no se usa en t.

Para cada combinación (W, K, g) devuelve:
- por episodio de escaneo (marcas): instante de disparo, s desde el inicio de la ráfaga,
  s hasta el último SYN y hasta el fin del proceso, puertos ya intentados al disparar;
- disparos fuera de los episodios de escaneo, separados en origen atacante (Kali) en otro
  episodio y origen legítimo (falsas alarmas), con el par y el instante;
- el máximo conteo alcanzado por cada par legítimo (margen frente a K).

Uso: python evaluar_regla_temprana.py syn.json.gz marcas.jsonl anatomia.json salida.json
"""
from __future__ import annotations

import bisect
import datetime as dt
import gzip
import heapq
import itertools
import json
import sys
from pathlib import Path

ATACANTE = "10.10.20.30"
REFRACTARIO_S = 60.0   # tras un disparo, el mismo par no vuelve a contar como disparo nuevo en 60 s


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(t):
    return None if t is None else dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def fallos_en_el_tiempo(intentos: list, g: float):
    """Eventos (t_fallo, t_syn, puerto): instante en que cada intento pasa a contar como fallido."""
    ev = []
    for t_syn, puerto, t_resp, tipo in intentos:
        if tipo == "R":
            ev.append((t_resp, t_syn, puerto))
        elif tipo == "SA":
            if t_resp - t_syn > g:          # sin respuesta durante g s: contó como fallido entre medias
                ev.append((t_syn + g, t_syn, puerto))
        else:
            ev.append((t_syn + g, t_syn, puerto))
    ev.sort()
    return ev


def disparos(intentos: list, W: float, K: int, g: float, solo_max: bool = False):
    """Instantes de disparo (con refractario) y el conteo al disparar; con solo_max, el maximo.

    En cada evento de fallo t: puertos distintos con fallo vigente y t_syn en (t - W, t].
    Un intento 'SA tardio' cuenta como fallo solo en [t_syn + g, t_resp).
    """
    ev = fallos_en_el_tiempo(intentos, g)
    fin_sa = {}
    for t_syn, puerto, t_resp, tipo in intentos:
        if tipo == "SA" and t_resp - t_syn > g:
            fin_sa[(t_syn, puerto)] = t_resp
    por_syn = []
    por_fin = []
    vivo = {}
    cuenta = {}
    salida, ultimo, maximo = [], -1e18, 0

    def quitar(i):
        pu = vivo.pop(i, None)
        if pu is not None:
            cuenta[pu] -= 1
            if not cuenta[pu]:
                del cuenta[pu]
    for i, (t, t_syn, puerto) in enumerate(ev):
        vivo[i] = puerto
        cuenta[puerto] = cuenta.get(puerto, 0) + 1
        heapq.heappush(por_syn, (t_syn, i))
        f = fin_sa.get((t_syn, puerto))
        if f is not None:
            heapq.heappush(por_fin, (f, i))
        lim = t - W
        while por_syn and por_syn[0][0] <= lim:
            quitar(heapq.heappop(por_syn)[1])
        while por_fin and por_fin[0][0] <= t:
            quitar(heapq.heappop(por_fin)[1])
        n = len(cuenta)
        if n > maximo:
            maximo = n
        if not solo_max and n >= K and t - ultimo >= REFRACTARIO_S:
            salida.append((t, n))
            ultimo = t
    return maximo if solo_max else salida


def main() -> int:
    syn_path, marcas_path, anat_path, out_path = (Path(x) for x in sys.argv[1:5])
    datos = json.load(gzip.open(syn_path, "rt", encoding="utf-8"))
    intentos = {k: sorted(v, key=lambda x: x[0]) for k, v in datos["intentos"].items()}
    # episodios de escaneo (breve y sostenido) y del atacante en general
    ini, fin, dest = {}, {}, {}
    for linea in marcas_path.open(encoding="utf-8"):
        r = json.loads(linea)
        e = r.get("episodio_id")
        if not e:
            continue
        if r.get("evento") == "inicio":
            ini[e] = ts(r["reloj"]["pared_utc"])
            dest[e] = r.get("destino")
        elif r.get("evento") == "fin":
            fin[e] = ts(r["reloj"]["pared_utc"])
    anat = {a["episodio"]: a for a in json.load(anat_path.open(encoding="utf-8"))}
    escaneos = sorted(e for e in ini if e.startswith("escaneo"))

    def episodio_de(t: float, margen: float = 60.0):
        for e in ini:
            if ini[e] - 1 <= t <= fin.get(e, ini[e]) + margen:
                return e
        return None

    W_ = [0.5, 1.0, 2.0, 5.0, 10.0]
    K_ = [5, 6, 8, 10, 12, 15, 20, 30]
    G_ = [0.05, 0.1, 0.2, 0.5, 1.0]
    resultados = []
    for W, K, g in itertools.product(W_, K_, G_):
        fila = {"W": W, "K": K, "g": g, "escaneos": {}, "disparos_kali_fuera_de_escaneo": [],
                "disparos_legitimos": [], "pares_legitimos_disparados": 0}
        for par, lista in intentos.items():
            src, dst = par.split(">")
            for t, n in disparos(lista, W, K, g):
                e = episodio_de(t) if src == ATACANTE else None
                if src == ATACANTE and e and e.startswith("escaneo") and dest.get(e) == dst:
                    if e not in fila["escaneos"]:
                        a = anat.get(e, {}).get("_t", {})
                        r0 = a.get("inicio_rafaga")
                        ult = a.get("ultimo_syn")
                        puertos_t = a.get("puertos_t") or []
                        fila["escaneos"][e] = {
                            "disparo": iso(t), "puertos_fallidos_al_disparar": n,
                            "s_desde_rafaga": round(t - r0, 3) if r0 else None,
                            "s_hasta_ultimo_syn": round(ult - t, 3) if ult else None,
                            "s_hasta_fin_proceso": round(fin[e] - t, 3) if e in fin else None,
                            "puertos_intentados_al_disparar": bisect.bisect_right(puertos_t, t),
                            "s_desde_inicio_marca": round(t - ini[e], 3)}
                elif src == ATACANTE:
                    fila["disparos_kali_fuera_de_escaneo"].append({"par": par, "t": iso(t), "n": n, "episodio": e})
                else:
                    fila["disparos_legitimos"].append({"par": par, "t": iso(t), "n": n})
        fila["pares_legitimos_disparados"] = len({d["par"] for d in fila["disparos_legitimos"]})
        fila["escaneos_detectados"] = len(fila["escaneos"])
        resultados.append(fila)
    # máximo conteo de fallos por par legítimo (W=2, g=1) para ver el margen frente a K
    margen = {}
    for par, lista in intentos.items():
        if par.startswith(ATACANTE + ">"):
            continue
        for W in (1.0, 2.0, 5.0, 10.0):
            for g in (0.05, 0.1, 1.0):
                margen.setdefault(par, {})["W=%s,g=%s" % (W, g)] = disparos(lista, W, 1, g, solo_max=True)
        margen[par]["intentos"] = len(lista)
        margen[par]["puertos_distintos_total"] = len({x[1] for x in lista})
        margen[par]["fallidos_total"] = sum(1 for x in lista if x[3] != "SA")
    out = {"estadisticas_lectura": datos["estadisticas"], "escaneos": escaneos,
           "rejilla": resultados, "max_fallidos_por_par_legitimo_g1": margen}
    out_path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for f in resultados:
        if f["W"] == 2.0 and f["K"] in (6, 8, 10, 12, 15, 20):
            print("W=%s K=%s g=%s escaneos=%d/%d kali_fuera=%d legit=%d (pares %d) | breves s_desde_rafaga=%s" % (
                f["W"], f["K"], f["g"], f["escaneos_detectados"], len(escaneos),
                len(f["disparos_kali_fuera_de_escaneo"]), len(f["disparos_legitimos"]), f["pares_legitimos_disparados"],
                sorted(v["s_desde_rafaga"] for e, v in f["escaneos"].items() if "breve" in e)))
    top = sorted(margen.items(), key=lambda kv: -kv[1]["W=5.0,g=0.05"])[:12]
    for par, m in top:
        print(par, m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
