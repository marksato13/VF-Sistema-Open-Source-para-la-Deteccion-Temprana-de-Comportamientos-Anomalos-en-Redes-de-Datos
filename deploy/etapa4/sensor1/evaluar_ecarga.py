#!/usr/bin/env python3
"""Evaluación de E-carga v2 (estabilidad de la integración en sombra con carga suficiente). SOLO LECTURA.

VERSION 2026-11-06.4. Reglas fijadas en PROTOCOLO-CARGA-v2.md ANTES de cualquier ejecución de E-carga.
(.4: contrato de entrada estricto y contraste de coherencia en «veredicto»; perfiles/K4a/K4b sin cambios.)

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

  Entrada (contrato estricto, PROTOCOLO-CARGA-v2 §4.5). Ningún campo de más ni de menos; claves no duplicadas:
    {"K": {K1, K2, K3, K4a, K5: true|false|null},          null = sin medida; nada más es booleano
     "S": {S1 … S15: true|false|null},
     "clasificacion": {"clase_periodo": C0|C1|C2|C3|no_evaluable, "motivos": [texto, …]},
     "suricata": {"estado": cero_explicito|descartes|ausente|desactualizada|error_lectura|cobertura_insuficiente,
                  "paquetes": entero >= 0, "descartes": entero >= 0},   null solo si el estado no es una medida
     "descartes_por_millon": número finito >= 0}               null solo si el estado no es una medida
  Entrada inválida -> rc 2, JSON con «error» y «campo», sin habilitar nada.

  Coherencia (no se corrige ningún dato; cada contradicción se lista en «incoherencias» y el resultado pasa a «no
  demostrable», salvo «carga insuficiente», que se mantiene):
    S12 frente al estado de Suricata; S13 frente a descartes × 10⁶ / paquetes < 14,95 (exacto, con enteros; 14,95
    no cumple); descartes_por_millon frente a ese cociente (± 0,01); C0 = cero_explicito, 0 descartes y sin motivos;
    C1 = estado «descartes» con descartes > 0 y con motivos; C2/C3 con motivos. C3 y no_evaluable nunca dan
    «estable con carga suficiente». rc 0 solo si «habilita_condicion_3» es true.
"""
import argparse
import datetime as dt
import gzip
import json
import math
import sys
import zlib

VERSION = "2026-11-06.4"
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
# Estados de la medida de Suricata (EVE) de salud_captura.medida_suricata_eve 2026-11-06.1, sin cambios.
ESTADOS_EVE = ("cero_explicito", "descartes", "ausente", "desactualizada", "error_lectura", "cobertura_insuficiente")
MEDIDOS = ("cero_explicito", "descartes")
# S13: descartes por millón < 14,95 (estricto). Se evalúa con enteros: descartes × 10⁸ < 1 495 × paquetes.
S13_NUM, S13_DEN = 1495, 100          # 14,95 = 1 495 / 100
TOL_DPM = 0.01                        # diferencia admitida entre el dpm declarado y descartes × 10⁶ / paquetes
CAMPOS = {"K", "S", "clasificacion", "suricata", "descartes_por_millon"}
NO_HABILITA = "nada: la condición (3) sigue pendiente"


class EntradaInvalida(ValueError):
    """Entrada que no cumple el contrato (PROTOCOLO-CARGA-v2 §4.5). Lleva el campo que falla."""

    def __init__(self, campo, motivo):
        super().__init__(f"{campo}: {motivo}")
        self.campo = campo


def _sin_duplicados(pares):
    claves = [k for k, _ in pares]
    for k in claves:
        if claves.count(k) > 1:
            raise EntradaInvalida(k, "clave duplicada en el JSON")
    return dict(pares)


def _numero(v, campo, entero=False, nulo=False):
    """Número real finito y >= 0. bool no es número; NaN/∞ no valen; null solo si se admite."""
    if v is None:
        if nulo:
            return None
        raise EntradaInvalida(campo, "falta el valor (null): un dato ausente no equivale a cero")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EntradaInvalida(campo, f"debe ser un número, no {type(v).__name__} ({v!r})")
    if entero and not isinstance(v, int):
        raise EntradaInvalida(campo, f"debe ser un entero, no {v!r}")
    if not math.isfinite(v):
        raise EntradaInvalida(campo, f"no es finito ({v!r})")
    if v < 0:
        raise EntradaInvalida(campo, f"no puede ser negativo ({v!r})")
    return v


def validar(d):
    """Contrato de entrada estricto. No convierte nada: "false", 0/1, listas u objetos no son booleanos."""
    if not isinstance(d, dict):
        raise EntradaInvalida("(raíz)", f"debe ser un objeto JSON, no {type(d).__name__}")
    for c in sorted(CAMPOS - set(d)):
        raise EntradaInvalida(c, "campo obligatorio ausente")
    for c in sorted(set(d) - CAMPOS):
        raise EntradaInvalida(c, "campo no reconocido")
    for grupo, claves in (("K", K), ("S", S)):
        g = d[grupo]
        if not isinstance(g, dict):
            raise EntradaInvalida(grupo, f"debe ser un objeto, no {type(g).__name__}")
        for x in claves:
            if x not in g:
                raise EntradaInvalida(f"{grupo}.{x}", "criterio ausente (para «sin medida» se escribe null)")
            if g[x] is not True and g[x] is not False and g[x] is not None:
                raise EntradaInvalida(f"{grupo}.{x}", f"solo admite true, false o null, no {g[x]!r}")
        for x in sorted(set(g) - set(claves)):
            raise EntradaInvalida(f"{grupo}.{x}", "criterio no reconocido")
    cl = d["clasificacion"]
    if not isinstance(cl, dict):
        raise EntradaInvalida("clasificacion", f"debe ser un objeto, no {type(cl).__name__}")
    for c in ("clase_periodo", "motivos"):
        if c not in cl:
            raise EntradaInvalida(f"clasificacion.{c}", "campo obligatorio ausente")
    if not isinstance(cl["clase_periodo"], str) or cl["clase_periodo"] not in CLASES:
        raise EntradaInvalida("clasificacion.clase_periodo", f"clase no reconocida: {cl['clase_periodo']!r}")
    if not isinstance(cl["motivos"], list) or not all(isinstance(m, str) for m in cl["motivos"]):
        raise EntradaInvalida("clasificacion.motivos", "debe ser una lista de textos")
    su = d["suricata"]
    if not isinstance(su, dict):
        raise EntradaInvalida("suricata", f"debe ser un objeto, no {type(su).__name__}")
    for c in ("estado", "paquetes", "descartes"):
        if c not in su:
            raise EntradaInvalida(f"suricata.{c}", "campo obligatorio ausente")
    if not isinstance(su["estado"], str) or su["estado"] not in ESTADOS_EVE:
        raise EntradaInvalida("suricata.estado", f"estado no reconocido: {su['estado']!r}")
    medido = su["estado"] in MEDIDOS
    # Con medida, los tres números son obligatorios; sin medida pueden ser null (y entonces no hay dpm).
    _numero(su["paquetes"], "suricata.paquetes", entero=True, nulo=not medido)
    _numero(su["descartes"], "suricata.descartes", entero=True, nulo=not medido)
    _numero(d["descartes_por_millon"], "descartes_por_millon", nulo=not medido)


def coherencia(d):
    """Contrasta indicadores con métricas y clase. Devuelve contradicciones; no corrige ningún dato."""
    s, su = d["S"], d["suricata"]
    clase, motivos = d["clasificacion"]["clase_periodo"], d["clasificacion"]["motivos"]
    est_eve, pq, ds, dpm = su["estado"], su["paquetes"], su["descartes"], d["descartes_por_millon"]
    medido = est_eve in MEDIDOS
    c = []
    # Medida de Suricata frente a sus propios números
    if est_eve == "cero_explicito" and ds != 0:
        c.append(f"suricata.estado cero_explicito con {ds} descartes")
    if est_eve == "descartes" and ds == 0:
        c.append("suricata.estado descartes con 0 descartes")
    if not medido and any(v is not None for v in (pq, ds, dpm)):
        c.append(f"suricata.estado {est_eve} (sin medida) con números de descartes o paquetes")
    s13_real = None
    if medido:
        if pq == 0:
            c.append("suricata.paquetes = 0: los descartes por millón no están definidos")
        else:
            real = ds * 1_000_000 / pq
            if abs(dpm - real) > TOL_DPM:
                c.append(f"descartes_por_millon {dpm} no coincide con descartes × 10⁶ / paquetes = {real:.6f}")
            s13_real = ds * 1_000_000 * S13_DEN < S13_NUM * pq      # < 14,95 exacto, con enteros
    # S12 (descartes medidos) y S13 (< 14,95/M) frente a las métricas
    if (medido and s["S12"] is not True) or (not medido and s["S12"] is True):
        c.append(f"S12 = {json.dumps(s['S12'])} pero la medida de Suricata es {est_eve}")
    if s13_real is None:
        if s["S13"] is True:
            c.append(f"S13 = true sin descartes por millón medidos (suricata.estado {est_eve})")
    elif s["S13"] is not s13_real:
        c.append(f"S13 = {json.dumps(s['S13'])} pero {ds} descartes de {pq} paquetes "
                 f"({ds * 1_000_000 / pq:.6f}/M) {'<' if s13_real else '>='} 14,95/M")
    # Clase frente a la medida (definiciones y precedencia del clasificador vigente, sin cambios)
    if clase == "C0":
        if est_eve != "cero_explicito" or ds != 0:
            c.append(f"clase C0 con suricata.estado {est_eve} y {ds} descartes: C0 exige cero_explicito y 0 descartes")
        if motivos:
            c.append("clase C0 con motivos de degradación: C0 exige evidencia completa sin motivos")
    elif clase == "C1":
        if est_eve != "descartes" or not ds:
            c.append(f"clase C1 con suricata.estado {est_eve} y {ds} descartes: C1 exige descartes de Suricata "
                     "medidos y > 0")
        if not motivos:
            c.append("clase C1 sin motivos")
    elif clase in ("C2", "C3"):
        if not motivos:
            c.append(f"clase {clase} sin motivos")
    if clase == "C2" and not medido:
        c.append(f"clase {clase} con Suricata {est_eve}: el clasificador da C3 a una medida de Suricata incompleta")
    return c


def veredicto(d):
    validar(d)
    k, s = d["K"], d["S"]
    cl = d["clasificacion"]
    clase = cl["clase_periodo"]
    dpm = d["descartes_por_millon"]
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
    incoherencias = coherencia(d)
    est0, motivos_nd = est, []
    if incoherencias and est0 != "carga insuficiente":
        est = "no demostrable"
        motivos_nd.append("los indicadores contradicen las métricas o la clase (ver «incoherencias»)")
    # Un fallo de S con C3 sigue siendo «no estable» (p. ej. un reinicio); lo que C3 no permite es demostrar estabilidad.
    if clase in ("C3", "no_evaluable") and est0 == "estable con carga suficiente":
        est = "no demostrable"
        motivos_nd.append(f"clase {clase}: la captura no es evaluable y no permite demostrar la estabilidad")
    if est == "no demostrable":
        motivos_nd = ([f"criterios sin medida: {', '.join(k_nd + s_nd)}"] if k_nd or s_nd else []) + motivos_nd
    pobl = {"C0": "cumple la condición de calidad de la población principal (C0) en esta ventana; "
                  "E-carga no produce episodios, así que no admite ninguno",
            "C1": "NO apta para la población principal: C1 (EVE degradado: descartes de Suricata medidos con "
                  "cobertura completa). Se publica aparte con su clase. No es captura sin pérdidas",
            "C2": "NO apta para la población principal: C2 (descartes de tcpdump). Se publica aparte con su clase",
            "C3": "NO apta: C3, no evaluable conforme al clasificador (falta evidencia o hay discontinuidad)",
            "no_evaluable": "NO apta: no evaluable (lectura fallida o insuficiente en el periodo)"}[clase]
    ok = est == "estable con carga suficiente" and not incoherencias and clase not in ("C3", "no_evaluable")
    habilita = "condición (3) del criterio único para el control formal de la 4B" if ok else NO_HABILITA
    lim = []
    if ok and clase != "C0":
        lim.append(f"estable pero con clase {clase}: la limitación de la clase se conserva en todo uso posterior")
    if dpm:
        lim.append(f"{dpm} descartes por millón: S13 (< 14,95) es un límite técnico; no demuestra C0 ni I5")
    return {"version": VERSION, "estabilidad_tecnica": est, "habilita_condicion_3": ok,
            "motivos_no_demostrable": motivos_nd, "K_no_cumplen": k_no, "K_sin_medida": k_nd,
            "S_no_cumplen": s_no, "S_sin_medida": s_nd, "hallazgos_S_aunque_carga_insuficiente": s_no if k_no else [],
            "clase_captura": clase, "motivos_clase": cl["motivos"], "suricata": d["suricata"],
            "descartes_por_millon": dpm,
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
            r = veredicto(json.load(f, object_pairs_hook=_sin_duplicados))
    except EntradaInvalida as e:
        print(json.dumps({"version": VERSION, "error": str(e), "campo": e.campo, "habilita_condicion_3": False,
                          "habilita": NO_HABILITA}, ensure_ascii=False))
        return 2
    except (OSError, ValueError) as e:
        print(json.dumps({"version": VERSION, "error": f"entrada no legible: {e}", "campo": None,
                          "habilita_condicion_3": False, "habilita": NO_HABILITA}, ensure_ascii=False))
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["habilita_condicion_3"] is True else 1


if __name__ == "__main__":
    sys.exit(main())
