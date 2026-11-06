#!/usr/bin/env python3
"""Evaluación de E-carga v2 (estabilidad de la integración en sombra con carga suficiente). SOLO LECTURA.

VERSION 2026-11-06.3. Reglas fijadas en PROTOCOLO-CARGA-v2.md ANTES de cualquier ejecución de E-carga.

  evaluar_ecarga.py perfiles --eve EVE [--eve EVE.1 …] --desde EPOCH --hasta EPOCH
                             [--perfil NOMBRE=IP …] [--erratico IP] [--factor-diseno 0.12] [--ritmo-erratico 5.0]
  evaluar_ecarga.py veredicto --entrada RESULTADOS.json

perfiles
  Flujo = evento EVE con event_type "flow" cuyo src_ip es la IP del perfil (cualquier protocolo). Se asigna al
  instante flow.start (no al de emisión del evento: Suricata lo escribe al expirar el flujo). Cuenta si
  desde <= flow.start < hasta. Un fichero ilegible, una línea de flujo corrupta o un flow.start sin parsear es
  ERROR (rc 2): una lectura fallida nunca cuenta como «sin tráfico».

  K4a (criterio): cada perfil con >= 1 flujo en CADA tramo de 600 s de la ventana.
  K4b (informativo, no decide el resultado; PROTOCOLO-CARGA-v2 §3.4): ráfaga del perfil errático.
    - Intervalos de 8 s desde «desde», TODOS (también los vacíos): n = ceil((hasta − desde) / 8).
    - Tasa de referencia λ_ref = max(media de flujos por intervalo en la ventana, λ_diseño), con
      λ_diseño = 8 × factor_horario / ritmo (generador clientes_lab.py: 8 × 0,12 / 5 = 0,192). La media incluye
      los ceros; la mediana NO se usa (con el ritmo nocturno es 0 y «3 × mediana» no significa nada).
    - Ráfaga = 5 intervalos consecutivos (40 s) con suma >= T = max(6, ceil(3 × λ_ref × 5)) y al menos 3 de esos 5
      intervalos con actividad. Lo segundo separa una ráfaga de actividad aislada (muchos flujos en un solo
      intervalo). Ventanas solapadas que cumplen se funden en un episodio.
    - Estados: sin_trafico | sin_rafaga_detectable | rafaga_detectada.

veredicto
  Separa cuatro dimensiones que NO se deducen unas de otras:
    estabilidad técnica (S1–S15 con K1–K5) · clase de calidad de captura (clasificador vigente, tal cual) ·
    I5 (no se evalúa en E-carga) · admisión en la población principal (solo C0).
"""
import argparse
import datetime as dt
import gzip
import json
import math
import sys
import zlib

VERSION = "2026-11-06.3"
INTERVALO_S = 8.0
TRAMO_S = 600.0
VENTANA_RAFAGA = 5          # intervalos (40 s): >= duración mínima de una ráfaga del generador (20 s) y con margen
ACTIVOS_MIN = 3             # de esos 5, con al menos un flujo
SUMA_MIN = 6
PERFILES = {"ofimatica": "10.10.20.21", "navegacion": "10.10.20.22", "descargas": "10.10.20.23",
            "aplicacion": "10.10.20.24", "ligero": "10.10.20.25", "erratico": "10.10.20.26"}


class ErrorLectura(Exception):
    pass


def ts(s):
    try:
        return dt.datetime.strptime(s[:26] + s[-5:], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except (TypeError, ValueError):
        raise ErrorLectura(f"marca de tiempo no reconocida: {s!r}")


def flujos(rutas, ips, desde, hasta):
    """{ip: [flow.start, …]} dentro de [desde, hasta)."""
    res = {ip: [] for ip in ips}
    for ruta in rutas:
        abrir = gzip.open if ruta.endswith(".gz") else open
        try:
            with abrir(ruta, "rt", encoding="utf-8", errors="strict") as f:
                for n, l in enumerate(f, 1):
                    if '"flow"' not in l:
                        continue
                    try:
                        e = json.loads(l)
                    except ValueError:
                        if l.endswith("\n"):
                            raise ErrorLectura(f"línea corrupta en {ruta}:{n}")
                        continue  # última línea a medio escribir
                    if e.get("event_type") != "flow" or e.get("src_ip") not in res:
                        continue
                    t = ts((e.get("flow") or {}).get("start"))
                    if desde <= t < hasta:
                        res[e["src_ip"]].append(t)
        except ErrorLectura:
            raise
        except (OSError, EOFError, UnicodeDecodeError, zlib.error, gzip.BadGzipFile) as ex:
            raise ErrorLectura(f"no se puede leer {ruta}: {ex}")
    return res


def k4a(por_ip, perfiles, desde, hasta):
    # Tramos completos de 600 s; un resto de menos de 600 s se suma al último tramo (2026-11-06.3: antes era un
    # tramo propio y, en la ventana base de 3 606 s, un tramo de 6 s sin flujos hacía fallar K4a por construcción).
    ntr = max(1, int((hasta - desde) // TRAMO_S))
    tabla, ok = {}, True
    for nombre, ip in perfiles.items():
        c = [0] * ntr
        for t in por_ip.get(ip, []):
            c[min(int((t - desde) // TRAMO_S), ntr - 1)] += 1
        tabla[nombre] = {"ip": ip, "flujos_por_tramo": c, "tramos_sin_flujos": [i for i, x in enumerate(c) if x == 0]}
        ok = ok and all(x > 0 for x in c)
    return {"cumple": ok, "tramos": ntr, "tramo_s": TRAMO_S, "perfiles": tabla}


def k4b(starts, desde, hasta, factor_diseno, ritmo):
    n = math.ceil((hasta - desde) / INTERVALO_S - 1e-9)
    c = [0] * n
    for t in starts:
        c[min(int((t - desde) // INTERVALO_S), n - 1)] += 1
    total = sum(c)
    media = total / n if n else 0.0
    l_dis = INTERVALO_S * factor_diseno / ritmo
    l_ref = max(media, l_dis)
    umbral = max(SUMA_MIN, math.ceil(3 * l_ref * VENTANA_RAFAGA - 1e-9))
    s = sorted(c)
    med = (s[(n - 1) // 2] + s[n // 2]) / 2 if n else 0
    episodios, abierto, max_suma = [], None, 0
    for i in range(0, max(n - VENTANA_RAFAGA + 1, 0)):
        v = c[i:i + VENTANA_RAFAGA]
        max_suma = max(max_suma, sum(v))
        es = sum(v) >= umbral and sum(1 for x in v if x) >= ACTIVOS_MIN
        if es and abierto is not None and i <= abierto[1]:
            abierto[1] = i + VENTANA_RAFAGA - 1
        elif es:
            abierto = [i, i + VENTANA_RAFAGA - 1]
            episodios.append(abierto)
    estado = "sin_trafico" if total == 0 else ("rafaga_detectada" if episodios else "sin_rafaga_detectable")
    return {"estado": estado, "informativo": True, "intervalos": n, "flujos": total,
            "intervalos_con_actividad": sum(1 for x in c if x), "media_por_intervalo": round(media, 4),
            "mediana_por_intervalo": med, "lambda_diseno": round(l_dis, 4), "lambda_ref": round(l_ref, 4),
            "umbral_suma_40s": umbral, "max_suma_40s": max_suma,
            "episodios": [{"desde": round(desde + a * INTERVALO_S, 3), "hasta": round(desde + (b + 1) * INTERVALO_S, 3),
                           "flujos": sum(c[a:b + 1])} for a, b in episodios]}


# ------------------------------------------------------------------ veredicto
RESULTADOS = ("estable con carga suficiente", "no estable", "carga insuficiente", "no demostrable")
K = ("K1", "K2", "K3", "K4a", "K5")
S = tuple(f"S{i}" for i in range(1, 16))
CLASES = ("C0", "C1", "C2", "C3", "no_evaluable")


def veredicto(d):
    k, s, cl = d.get("K") or {}, d.get("S") or {}, d.get("clasificacion") or {}
    clase = cl.get("clase_periodo")
    falta = [x for x in K if x not in k] + [x for x in S if x not in s]
    if falta:
        raise ValueError("faltan criterios en la entrada: " + ", ".join(falta))
    if clase not in CLASES:
        raise ValueError(f"clase de captura no reconocida: {clase!r}")
    k_no = [x for x in K if k[x] is False]
    k_nd = [x for x in K if k[x] is None]
    s_no = [x for x in S if s[x] is False]
    s_nd = [x for x in S if s[x] is None]
    if k_no:
        est = "carga insuficiente"
    elif k_nd or s_nd:
        est = "no demostrable"
    elif s_no:
        est = "no estable"
    else:
        est = "estable con carga suficiente"
    dpm = d.get("descartes_por_millon")
    incoherencias = []
    if clase == "C0" and dpm not in (0, 0.0):
        incoherencias.append(f"clase C0 con descartes por millón {dpm!r}: revisar la clasificación")
    if clase == "C1" and not dpm:
        incoherencias.append("clase C1 sin descartes por millón > 0: revisar la clasificación")
    if incoherencias and est == "estable con carga suficiente":
        est = "no demostrable"
    pobl = {"C0": "cumple la condición de calidad de la población principal (C0) en esta ventana; "
                  "E-carga no produce episodios, así que no admite ninguno",
            "C1": "NO apta para la población principal: C1 (EVE degradado: descartes de Suricata medidos con "
                  "cobertura completa). Se publica aparte con su clase. No es captura sin pérdidas",
            "C2": "NO apta para la población principal: C2 (descartes de tcpdump). Se publica aparte con su clase",
            "C3": "NO apta: C3, no evaluable conforme al clasificador (falta evidencia o hay discontinuidad)",
            "no_evaluable": "NO apta: no evaluable (lectura fallida o insuficiente en el periodo)"}[clase]
    habilita = ("condición (3) del criterio único para el control formal de la 4B"
                if est == "estable con carga suficiente" else "nada: la condición (3) sigue pendiente")
    lim = []
    if est == "estable con carga suficiente" and clase != "C0":
        lim.append(f"estable pero con clase {clase}: la limitación de la clase se conserva en todo uso posterior")
    if dpm:
        lim.append(f"{dpm} descartes por millón: S13 (< 14,95) es un límite técnico; no demuestra C0 ni I5")
    return {"version": VERSION, "estabilidad_tecnica": est, "K_no_cumplen": k_no, "K_sin_medida": k_nd,
            "S_no_cumplen": s_no, "S_sin_medida": s_nd, "hallazgos_S_aunque_carga_insuficiente": s_no if k_no else [],
            "clase_captura": clase, "motivos_clase": cl.get("motivos"), "descartes_por_millon": dpm,
            "i5": "no evaluado: I5 se mide en los 30 min previos al inicio real de la 4C, con lectura propia",
            "poblacion_principal": pobl, "habilita": habilita, "limitaciones": lim, "incoherencias": incoherencias}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    a = sub.add_parser("perfiles")
    a.add_argument("--eve", action="append", required=True)
    a.add_argument("--desde", type=float, required=True)
    a.add_argument("--hasta", type=float, required=True)
    a.add_argument("--perfil", action="append", default=[], help="NOMBRE=IP (por omisión los seis del laboratorio)")
    a.add_argument("--erratico", default=PERFILES["erratico"])
    a.add_argument("--factor-diseno", type=float, default=0.12)
    a.add_argument("--ritmo-erratico", type=float, default=5.0)
    b = sub.add_parser("veredicto")
    b.add_argument("--entrada", required=True)
    x = ap.parse_args(argv)
    if x.orden == "perfiles":
        if x.hasta <= x.desde:
            print(json.dumps({"error": "hasta <= desde"}))
            return 2
        perf = dict(p.split("=", 1) for p in x.perfil) if x.perfil else dict(PERFILES)
        ips = set(perf.values()) | {x.erratico}
        try:
            por_ip = flujos(x.eve, ips, x.desde, x.hasta)
        except ErrorLectura as e:
            print(json.dumps({"version": VERSION, "error": str(e)}, ensure_ascii=False))
            return 2
        r = {"version": VERSION, "desde": x.desde, "hasta": x.hasta, "eve": x.eve,
             "K4a": k4a(por_ip, perf, x.desde, x.hasta),
             "K4b": k4b(por_ip[x.erratico], x.desde, x.hasta, x.factor_diseno, x.ritmo_erratico)}
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["K4a"]["cumple"] else 1
    try:
        with open(x.entrada, encoding="utf-8") as f:
            r = veredicto(json.load(f))
    except (OSError, ValueError) as e:
        print(json.dumps({"version": VERSION, "error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["estabilidad_tecnica"] == "estable con carga suficiente" else 1


if __name__ == "__main__":
    sys.exit(main())
