#!/usr/bin/env python3
"""S2 y S3 de E-carga v2 (= O2 y O3 de CRITERIOS-FIJADOS §4) desde obs_pcap/pcap.jsonl de obs_pcap.py. SOLO LECTURA.

VERSION 2026-11-06.2. Sustituye a la 2026-11-06.1 (evaluacion-e83f4be6), que solo miraba los ficheros cuyo nombre caía
en la ventana: con dos PCAP en T+2 s y T+7 s de una hora daba S2 = S3 = true y «faltan_nombres» 718.

  derivar_pcap.py PCAP.jsonl DESDE HASTA [--log obs_pcap.log] [--salto-max 7] [--retencion 900] -> JSON

Datos de cada línea (obs_pcap.py 2026-11-06.2): fichero live-AAAAMMDDhhmmss.pcap (hora de inicio, UTC), registros,
primero/ultimo (instantes del primer y último paquete), error (si lo hubo) y leido_en (hora de la pasada que lo leyó).
obs_pcap solo lee ficheros CERRADOS (existe uno más nuevo), cada 30 s, y escribe el fin normal en su log
({"terminado_en": …, "fin_epoch": …}).

Constantes (no cambian ningún criterio publicado):
  salto-max 7 s   el de O3. La rotación nominal es de 5 s (tcpdump -G 5); el 06-nov el salto máximo fue 6,0 s.
                  No se exige un número fijo de ficheros: la cadencia real se informa (mediana) y solo cuenta el salto.
  retencion 900 s tiempo mínimo que un fichero cerrado sigue en el anillo. Medido: 186 ficheros (≈ 930 s a 5 s) el
                  06-nov 08:10Z, y la primera pasada del 06-nov leyó ficheros de 1 059 s antes. `sensor1_muestreadores
                  comprobar` lo vuelve a medir en P0. Una pasada separada de la anterior menos de (retencion − salto)
                  no puede haber perdido ningún fichero sin leer.

Ficheros que importan: la CADENA desde el fichero en el que cae DESDE (el último que empieza <= DESDE) hasta el primero
que empieza >= HASTA. Los que cruzan los bordes se tratan explícitamente:
  - el que contiene DESDE (empieza antes) tiene paquetes de la ventana: entra en S2 y en S3;
  - el primero que empieza >= HASTA solo prueba que el que contiene HASTA se cerró (y fue leído): entra en S3, no en S2.

Lectura completa de la observación (sin ella, lo que falta podría ser un fichero no leído, no uno no escrito):
  a) primera pasada <= DESDE + retencion − salto-max (el anillo aún tenía el fichero de DESDE);
  b) última pasada (o terminado_en del log) >= HASTA + 2 × salto-max (el fichero de HASTA y el siguiente ya cerrados);
  c) ningún hueco entre pasadas > retencion − salto-max, salvo que el log pruebe un fin normal (el bucle no se paró).

S2 (O2, legibilidad). DEMUESTRA: todos los ficheros del anillo con paquetes de [DESDE, HASTA) que existieron se
   leyeron completos (cabecera global y todos los registros) sin error de formato.
     false  algún fichero de la cadena tiene error de formato (incumplimiento demostrado, aunque falte lo demás);
     null   evidencia insuficiente: lectura incompleta o truncada, fichero no comprobado (error de lectura del sistema,
            sin campo «registros»), líneas no interpretables, duplicados contradictorios, o ningún fichero;
     true   lectura completa, cadena no vacía y ningún error.
   No demuestra continuidad: que no falte ningún fichero lo dice S3.
S3 (O3, continuidad del anillo). DEMUESTRA: el anillo escribió sin huecos todo [DESDE, HASTA]: hay fichero que contiene
   DESDE, hay fichero que empieza >= HASTA, ningún salto entre inicios consecutivos de la cadena > salto-max, y ningún
   fichero de la ventana sin registros.
     false  con la lectura completa: falta el borde de inicio o de fin, hay un salto > salto-max o un fichero vacío
            (incumplimiento demostrado: lo que no está no lo escribió el anillo);
     null   lectura incompleta o truncada, ficheros no comprobados, líneas no interpretables o duplicados
            contradictorios;
     true   todo lo anterior se cumple.
   No demuestra la legibilidad (S2) ni la ausencia de pérdidas de captura (eso es la clase y S12/S13).
Duplicados idénticos y líneas desordenadas se informan como avisos: el análisis usa los ficheros ordenados por su
nombre y sin repetir, así que no ocultan huecos. La rotación de eve.json se informa aparte (suricata-ls.txt).
"""
import argparse
import datetime as dt
import json

VERSION = "derivar_pcap 2026-11-06.2"
SALTO_MAX = 7.0
RETENCION = 900.0


def t_nombre(nombre):
    if not (isinstance(nombre, str) and nombre.startswith("live-") and nombre.endswith(".pcap") and len(nombre) == 24):
        raise ValueError(f"nombre no reconocido: {nombre!r}")
    return dt.datetime.strptime(nombre[5:19], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc).timestamp()


def leer_log(lineas):
    fin = None
    for l in lineas or []:
        l = l.strip()
        if l.startswith("{"):
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if isinstance(d, dict) and "terminado_en" in d:
                fin = d
    return fin


def derivar(lineas, desde, hasta, log=None, salto_max=SALTO_MAX, retencion=RETENCION):
    res = {"version": VERSION, "periodo": [desde, hasta], "salto_max_s": salto_max, "retencion_s": retencion,
           "avisos": []}
    malas, por_nombre, orden, conflictos, duplicados = [], {}, [], [], []
    for i, l in enumerate(lineas, 1):
        if not l.strip():
            continue
        try:
            r = json.loads(l)
            t = t_nombre(r.get("fichero"))
        except (ValueError, AttributeError, TypeError) as e:
            malas.append(f"línea {i}: {str(e)[:80]}")
            continue
        orden.append(t)
        clave = {k: v for k, v in r.items() if k != "leido_en"}
        if r["fichero"] in por_nombre:
            previo = {k: v for k, v in por_nombre[r["fichero"]].items() if k != "leido_en"}
            (duplicados if previo == clave else conflictos).append(r["fichero"])
            continue
        por_nombre[r["fichero"]] = r
    desorden = sum(1 for a, b in zip(orden, orden[1:]) if b < a)
    recs = sorted(por_nombre.values(), key=lambda r: t_nombre(r["fichero"]))
    ts = [t_nombre(r["fichero"]) for r in recs]
    if duplicados:
        res["avisos"].append(f"{len(duplicados)} fichero(s) repetidos con el mismo contenido (se cuentan una vez)")
    if desorden:
        res["avisos"].append(f"{desorden} línea(s) fuera de orden (se analizan ordenadas por nombre)")

    # --- lectura completa de la observación
    fin_log = leer_log(log)
    pas = sorted(r["leido_en"] for r in recs if isinstance(r.get("leido_en"), (int, float)))
    sin_leido = sum(1 for r in recs if not isinstance(r.get("leido_en"), (int, float)))
    ultima = max(pas[-1] if pas else float("-inf"),
                 fin_log["terminado_en"] if fin_log and isinstance(fin_log.get("terminado_en"), (int, float)) else float("-inf"))
    fin_normal = bool(fin_log and isinstance(fin_log.get("fin_epoch"), (int, float)) and fin_log["fin_epoch"] >= hasta
                      and isinstance(fin_log.get("terminado_en"), (int, float)))
    hueco_pas = max((b - a for a, b in zip(pas, pas[1:])), default=None)
    lim = retencion - salto_max
    lec = {"primera_pasada": pas[0] if pas else None, "ultima_pasada": None if ultima == float("-inf") else ultima,
           "hueco_max_entre_pasadas_s": round(hueco_pas, 1) if hueco_pas is not None else None,
           "fin_normal_en_log": fin_normal, "lineas_sin_leido_en": sin_leido}
    motivos_lec = []
    if not pas:
        motivos_lec.append("ninguna pasada registrada (sin leido_en)")
    else:
        if pas[0] > desde + lim:
            motivos_lec.append(f"primera pasada {pas[0] - desde:.0f} s después de DESDE (> {lim:.0f} s): el fichero de "
                               "DESDE pudo salir del anillo sin leerse")
        if hueco_pas is not None and hueco_pas > lim and not fin_normal:
            motivos_lec.append(f"hueco entre pasadas de {hueco_pas:.0f} s (> {lim:.0f} s) sin fin normal en el log")
    if ultima < hasta + 2 * salto_max:
        motivos_lec.append("observación truncada: la última pasada no llega a HASTA + 2 × salto-max "
                           f"({'sin pasadas' if ultima == float('-inf') else f'{ultima - hasta:+.0f} s respecto a HASTA'})")
    if sin_leido and not fin_normal:
        motivos_lec.append(f"{sin_leido} línea(s) sin leido_en")
    lec["completa"] = not motivos_lec
    lec["motivos"] = motivos_lec
    res["lectura"] = lec

    # --- cadena de ficheros
    i0 = max((i for i, t in enumerate(ts) if t <= desde), default=None)
    i1 = min((i for i, t in enumerate(ts) if t >= hasta), default=None)
    a = i0 if i0 is not None else next((i for i, t in enumerate(ts) if t >= desde), len(ts))
    b = i1 if i1 is not None else len(ts) - 1
    cadena = recs[a:b + 1] if a <= b and a < len(ts) else []
    tc = [t_nombre(r["fichero"]) for r in cadena]
    en_ventana = [r for r, t in zip(cadena, tc) if t < hasta]        # los que tienen paquetes de [DESDE, HASTA)
    saltos = [(cadena[k]["fichero"], cadena[k + 1]["fichero"], round(tc[k + 1] - tc[k], 1))
              for k in range(len(tc) - 1) if tc[k + 1] - tc[k] > salto_max]
    gaps = sorted(y - x for x, y in zip(tc, tc[1:]))
    err_formato = [r["fichero"] for r in en_ventana if r.get("error") and not str(r["error"]).startswith("lectura")]
    no_comprob = [r["fichero"] for r in cadena if (r.get("error") and str(r["error"]).startswith("lectura"))
                  or (not r.get("error") and not isinstance(r.get("registros"), int))]
    vacios = [r["fichero"] for r in en_ventana if not r.get("error") and r.get("registros") == 0]
    huecos_paq = [y["primero"] - x["ultimo"] for x, y in zip(cadena, cadena[1:])
                  if isinstance(x.get("ultimo"), (int, float)) and isinstance(y.get("primero"), (int, float))]
    res["cadena"] = {
        "ficheros_en_ventana": len(en_ventana), "ficheros_cadena": len(cadena),
        "fichero_de_desde": recs[i0]["fichero"] if i0 is not None else None,
        "desde_menos_inicio_s": round(desde - ts[i0], 1) if i0 is not None else None,
        "primero_tras_hasta": recs[i1]["fichero"] if i1 is not None else None,
        "inicio_cubierto": i0 is not None, "fin_cubierto": i1 is not None,
        "hueco_inicio_s": None if i0 is not None else (round(tc[0] - desde, 1) if tc else round(hasta - desde, 1)),
        "hueco_fin_s": None if i1 is not None else (round(hasta - tc[-1], 1) if tc else round(hasta - desde, 1)),
        "saltos_mayores": saltos[:20], "n_saltos_mayores": len(saltos),
        "salto_max_s": round(gaps[-1], 1) if gaps else None,
        "cadencia_mediana_s": round(gaps[len(gaps) // 2], 2) if gaps else None,
        "esperados_aprox": round((tc[-1] - tc[0]) / gaps[len(gaps) // 2]) + 1 if gaps and gaps[len(gaps) // 2] > 0 else None,
        "errores_formato": err_formato[:20], "no_comprobados": no_comprob[:20], "vacios": vacios[:20],
        "registros": sum(r.get("registros") or 0 for r in en_ventana),
        "hueco_max_paquetes_s": round(max(huecos_paq), 3) if huecos_paq else None,
        "lineas_no_interpretables": malas[:20], "duplicados_contradictorios": conflictos[:20],
        "duplicados_identicos": len(duplicados), "lineas_desordenadas": desorden}

    contradiccion = []
    if malas:
        contradiccion.append(f"{len(malas)} línea(s) no interpretables")
    if conflictos:
        contradiccion.append(f"{len(conflictos)} fichero(s) repetidos con contenido distinto")

    # S2
    if contradiccion:
        s2 = (None, "evidencia contradictoria o no interpretable: " + "; ".join(contradiccion))
    elif err_formato:
        s2 = (False, f"{len(err_formato)} fichero(s) con error de formato")
    elif not lec["completa"]:
        s2 = (None, "lectura incompleta: " + "; ".join(motivos_lec))
    elif no_comprob:
        s2 = (None, f"{len(no_comprob)} fichero(s) no comprobados")
    elif not en_ventana:
        s2 = (None, "ningún fichero con paquetes de la ventana")
    else:
        s2 = (True, f"{len(en_ventana)} ficheros leídos sin error, incluidos los de los bordes")
    # S3
    fallos3 = []
    if i0 is None:
        fallos3.append("no hay fichero que contenga DESDE")
    if i1 is None:
        fallos3.append("no hay fichero que empiece >= HASTA (el de HASTA no consta cerrado)")
    if saltos:
        fallos3.append(f"{len(saltos)} salto(s) > {salto_max:g} s")
    if vacios:
        fallos3.append(f"{len(vacios)} fichero(s) sin registros")
    if contradiccion:
        s3 = (None, "evidencia contradictoria o no interpretable: " + "; ".join(contradiccion))
    elif not lec["completa"]:
        s3 = (None, "lectura incompleta: " + "; ".join(motivos_lec)
              + (f" (además: {'; '.join(fallos3)}; no se puede atribuir al anillo)" if fallos3 else ""))
    elif no_comprob:
        s3 = (None, f"{len(no_comprob)} fichero(s) no comprobados")
    elif fallos3:
        s3 = (False, "; ".join(fallos3))
    else:
        s3 = (True, f"cadena continua de {len(cadena)} ficheros, salto máximo {gaps[-1] if gaps else 0:.1f} s")
    res["S2"] = {"valor": s2[0], "motivo": s2[1]}
    res["S3"] = {"valor": s3[0], "motivo": s3[1]}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcap")
    ap.add_argument("desde", type=float)
    ap.add_argument("hasta", type=float)
    ap.add_argument("--log")
    ap.add_argument("--salto-max", type=float, default=SALTO_MAX)
    ap.add_argument("--retencion", type=float, default=RETENCION)
    a = ap.parse_args()
    lg = None
    if a.log:
        try:
            with open(a.log, encoding="utf-8", errors="replace") as fh:
                lg = fh.readlines()
        except OSError:
            lg = None
    with open(a.pcap, encoding="utf-8") as fh:
        print(json.dumps(derivar(fh, a.desde, a.hasta, lg, a.salto_max, a.retencion), ensure_ascii=False, indent=1))
