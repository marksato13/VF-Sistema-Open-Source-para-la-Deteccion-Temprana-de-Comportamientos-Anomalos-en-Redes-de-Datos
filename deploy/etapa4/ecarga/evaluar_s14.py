#!/usr/bin/env python3
"""S14 de E-carga v2: «sin saturación nueva de CPU, softirq, disco ni memoria; softnet dropped = 0».
Definición operacional publicada en PROTOCOLO-CARGA-v2 r3 §3.6.1 ANTES de cualquier ensayo. No se aplica a
observaciones anteriores. SOLO LECTURA.

  evaluar_s14.py S14.jsonl --desde D --hasta H [--base-desde BD --base-hasta BH]  -> JSON {"S14": {"valor", ...}}

Fuente: muestreo_s14.py (1 s) en Sensor1. Ventana [D, H); línea base [BD, BH) = los 300 s previos a T_g, sin carga.

Utilización elevada NO es saturación. Una componente está SATURADA en un par de muestras consecutivas solo si se
cumple su condición de saturación (capacidad agotada Y espera, o un recurso no compartible al 100 %):
  cpu      CPU del host ocupada >= 95 % (1 − Δ(idle+iowait)/Δtotal, agregado de las 4 CPU)
           Y PSI cpu «some» >= 10 % del intervalo (tareas listas esperando CPU)
  hilos    algún hilo trabajador de Suricata (W#…) >= 95 % de un núcleo (Δticks / (USER_HZ·Δt)); un hilo no puede usar
           más de un núcleo, así que a ese nivel su demanda supera su capacidad
  softirq  alguna CPU con irq+softirq >= 95 % de su tiempo (la CPU que atiende una cola de ens37 no da abasto)
  disco    algún disco con ms de E/S en curso >= 95 % del intervalo (Δio_ticks) Y PSI io «full» >= 10 % (todas las
           tareas no ociosas paradas esperando E/S)
  memoria  PSI memory «some» >= 10 % del intervalo (tareas esperando por reclamación de memoria o swap-in)
Los límites son inclusivos (95,0 % y 10,0 % ya cuentan).
Episodio: pares consecutivos saturados, sin interrupción, que suman >= 8 s. Un par de más de 4 s, un dato ausente
o un contador que retrocede (reinicio) interrumpe el episodio y no cuenta como cubierto.
Incumplimientos inmediatos (sin duración): softnet dropped > 0 entre los bordes de la ventana; oom_kill > 0;
MemAvailable < 1 GiB en alguna muestra (la condición de parada de §3.7).
Cobertura mínima de cada componente: pares válidos (<= 4 s) que cubran >= 99 % de la ventana y ningún hueco > 4 s.
Dato ausente dentro de una saturación: si los pares saturados más los huecos intercalados (desde el último par válido no
saturado) suman >= 8 s, el episodio no se puede negar: la componente queda null («dudoso»), nunca true.

Resultado por componente:
  false  saturación NUEVA demostrada (episodio en la ventana y base evaluable sin episodios de esa componente),
         o incumplimiento inmediato;
  null   cobertura insuficiente; o episodio en la ventana con la base no evaluable o también saturada (no se puede
         atribuir a la carga: «nueva» no es demostrable);
  true   cobertura suficiente y ningún episodio.
S14 = false si alguna componente es false; si no, null si alguna es null; si no, true.
"""
import argparse
import json
import math

VERSION = "evaluar_s14 2026-11-06.1"
D_MIN = 8.0
PAR_MAX = 4.0
COBERTURA_MIN = 0.99
HUECO_MAX = 4.0
U_CPU = 95.0
U_HILO = 95.0
U_SOFTIRQ = 95.0
U_DISCO = 95.0
PSI_MIN = 10.0
MEM_MIN_KB = 1048576


def _d(x, y):
    if x is None or y is None:
        return None
    return y - x


def _psi(a, b, k, dt):
    d = _d((a.get("psi") or {}).get(k), (b.get("psi") or {}).get(k))
    if d is None or d < 0:
        return None
    return 100.0 * d / (dt * 1e6)


def c_cpu(a, b, dt):
    x, y = (a.get("cpu") or {}).get("cpu"), (b.get("cpu") or {}).get("cpu")
    p = _psi(a, b, "cpu_some", dt)
    if not x or not y or p is None:
        return None, {}
    d = [j - i for i, j in zip(x, y)]
    tot = sum(d)
    if min(d) < 0 or tot <= 0:
        return None, {}
    busy = 100.0 * (1 - (d[3] + d[4]) / tot)
    return (busy >= U_CPU and p >= PSI_MIN), {"ocupada_pct": busy, "psi_cpu_some_pct": p}


def c_hilos(a, b, dt):
    sa, sb = a.get("suricata"), b.get("suricata")
    hz = b.get("user_hz") or a.get("user_hz")
    if not sa or not sb or not hz or sa.get("pid") != sb.get("pid"):
        return None, {}
    w = [k for k in (sb.get("hilos") or {}) if k.startswith("W#") and k in (sa.get("hilos") or {})]
    if not w:
        return None, {}
    pct = []
    for k in w:
        d = sb["hilos"][k] - sa["hilos"][k]
        if d < 0:
            return None, {}
        pct.append(100.0 * d / (hz * dt))
    return max(pct) >= U_HILO, {"hilo_max_pct": max(pct)}


def c_softirq(a, b, dt):
    ca, cb = a.get("cpu") or {}, b.get("cpu") or {}
    ks = [k for k in cb if k != "cpu" and k in ca]
    if not ks:
        return None, {}
    pct = []
    for k in ks:
        d = [j - i for i, j in zip(ca[k], cb[k])]
        tot = sum(d)
        if min(d) < 0 or tot <= 0:
            return None, {}
        pct.append(100.0 * (d[5] + d[6]) / tot)
    return max(pct) >= U_SOFTIRQ, {"softirq_cpu_max_pct": max(pct)}


def c_disco(a, b, dt):
    da, db = a.get("disco") or {}, b.get("disco") or {}
    p = _psi(a, b, "io_full", dt)
    ks = [k for k in db if k in da]
    if not ks or p is None:
        return None, {}
    util = []
    for k in ks:
        d = db[k][0] - da[k][0]
        if d < 0:
            return None, {}
        util.append(100.0 * d / (dt * 1000.0))
    return (max(util) >= U_DISCO and p >= PSI_MIN), {"disco_ocupado_max_pct": max(util), "psi_io_full_pct": p}


def c_memoria(a, b, dt):
    p = _psi(a, b, "mem_some", dt)
    if p is None or a.get("mem_disponible_kb") is None or b.get("mem_disponible_kb") is None:
        return None, {}
    return p >= PSI_MIN, {"psi_mem_some_pct": p, "mem_disponible_kb": min(a["mem_disponible_kb"], b["mem_disponible_kb"])}


COMPONENTES = {"cpu": c_cpu, "hilos": c_hilos, "softirq": c_softirq, "disco": c_disco, "memoria": c_memoria}


def analizar(ms, desde, hasta, f):
    """Episodios >= D_MIN, cobertura y máximos de una componente en [desde, hasta)."""
    lon = hasta - desde
    cubiertos, episodios, maximos = [], [], {}
    run_ini = run_fin = None
    run_dur = 0.0
    prev_valido = False
    # Cadena «posible»: pares saturados más los pares no válidos intercalados, desde el último par válido NO saturado.
    # Si suma >= D_MIN y contiene algún dato ausente, la saturación pudo durar lo bastante y el dato que falta la parte:
    # no se puede negar el episodio (dudoso -> la componente queda null, nunca true).
    cad_ini, cad_dur, cad_sat, cad_inv = None, 0.0, 0.0, False
    dudosos = []

    def mirar_cadena():
        if cad_inv and cad_sat > 0 and cad_dur >= D_MIN and (not dudosos or dudosos[-1]["desde"] != round(cad_ini, 3)):
            dudosos.append({"desde": round(cad_ini, 3), "duracion_con_huecos_s": round(cad_dur, 1)})

    def cerrar():
        nonlocal run_ini, run_fin, run_dur
        if run_ini is not None and run_dur >= D_MIN:
            episodios.append({"desde": round(run_ini, 3), "hasta": round(run_fin, 3), "duracion_s": round(run_dur, 1)})
        run_ini, run_fin, run_dur = None, None, 0.0

    for a, b in zip(ms, ms[1:]):
        ini, fin = max(a["t"], desde), min(b["t"], hasta)
        if fin <= ini:
            continue
        dt = b["t"] - a["t"]
        val, det = (None, {}) if dt <= 0 or dt > PAR_MAX else f(a, b, dt)
        if val is None:
            cerrar()
            prev_valido = False
            if cad_ini is not None:
                cad_dur += fin - ini
                cad_inv = True
                mirar_cadena()
            continue
        cubiertos.append((ini, fin))
        for k, v in det.items():
            maximos[k] = v if k not in maximos else (min(maximos[k], v) if k == "mem_disponible_kb" else max(maximos[k], v))
        if val:
            if run_ini is None or not prev_valido:
                cerrar()
                run_ini = ini
            run_fin, run_dur = fin, run_dur + (fin - ini)
            if cad_ini is None:
                cad_ini = ini
            cad_dur += fin - ini
            cad_sat += fin - ini
            mirar_cadena()
        else:
            cerrar()
            cad_ini, cad_dur, cad_sat, cad_inv = None, 0.0, 0.0, False
        prev_valido = True
    cerrar()
    tot = sum(f - i for i, f in cubiertos)
    huecos, cursor = [], desde
    for i, f in cubiertos:
        if i - cursor > 1e-6:
            huecos.append(i - cursor)
        cursor = max(cursor, f)
    if hasta - cursor > 1e-6:
        huecos.append(hasta - cursor)
    cob = {"cubierto_s": round(tot, 1), "fraccion": round(tot / lon, 4) if lon > 0 else 0.0,
           "hueco_max_s": round(max(huecos), 1) if huecos else 0.0}
    cob["ok"] = lon > 0 and tot >= COBERTURA_MIN * lon - 1e-6 and (max(huecos) if huecos else 0.0) <= HUECO_MAX
    return {"episodios": episodios, "dudosos": dudosos, "cobertura": cob,
            "maximos": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in maximos.items()}}


def borde(ms, t, clave):
    """Lectura de un contador a <= PAR_MAX del borde t (la más cercana)."""
    c = [m for m in ms if abs(m["t"] - t) <= PAR_MAX and clave(m) is not None]
    return min(c, key=lambda m: abs(m["t"] - t)) if c else None


def incremento(ms, desde, hasta, clave):
    """Incremento del contador entre los bordes; None si falta un borde o el contador retrocede (reinicio)."""
    a, b = borde(ms, desde, clave), borde(ms, hasta, clave)
    if a is None or b is None:
        return None, "sin lectura a <= 4 s de un borde"
    vals = [clave(m) for m in ms if a["t"] <= m["t"] <= b["t"] and clave(m) is not None]
    if any(y < x for x, y in zip(vals, vals[1:])):
        return None, "el contador retrocede (reinicio)"
    return vals[-1] - vals[0], None


def evaluar(lineas, desde, hasta, base=None):
    ms, malas = [], 0
    for l in lineas:
        if not l.strip():
            continue
        try:
            m = json.loads(l)
        except ValueError:
            malas += 1
            continue
        if isinstance(m, dict) and isinstance(m.get("t"), (int, float)) and math.isfinite(m["t"]):
            ms.append(m)
    ms.sort(key=lambda m: m["t"])
    ms = [m for i, m in enumerate(ms) if i == 0 or m["t"] != ms[i - 1]["t"]]
    res = {"version": VERSION, "periodo": [desde, hasta], "base": list(base) if base else None,
           "muestras": len(ms), "lineas_no_interpretables": malas, "componentes": {}}
    comp = res["componentes"]
    for nombre, f in COMPONENTES.items():
        w = analizar(ms, desde, hasta, f)
        b = analizar(ms, base[0], base[1], f) if base else None
        r = {"ventana": w, "base": b}
        if w["episodios"]:
            if b and b["cobertura"]["ok"] and not b["episodios"] and not b["dudosos"]:
                r["valor"], r["motivo"] = False, f"saturación nueva: {len(w['episodios'])} episodio(s) >= {D_MIN:g} s"
            elif b and b["cobertura"]["ok"]:
                r["valor"], r["motivo"] = None, "saturación también en la línea base: no atribuible a la carga"
            else:
                r["valor"], r["motivo"] = None, "saturación en la ventana con la línea base no evaluable: «nueva» no demostrable"
        elif not w["cobertura"]["ok"]:
            r["valor"], r["motivo"] = None, "cobertura insuficiente (>= 99 % y huecos <= 4 s)"
        elif w["dudosos"]:
            r["valor"], r["motivo"] = None, (f"{len(w['dudosos'])} posible(s) episodio(s) >= {D_MIN:g} s partidos por "
                                             "datos ausentes: no se puede negar la saturación")
        else:
            r["valor"], r["motivo"] = True, "sin episodios de saturación"
        comp[nombre] = r
    # inmediatos
    dr, mot = incremento(ms, desde, hasta, lambda m: (m.get("softnet") or {}).get("dropped"))
    comp["softnet_dropped"] = {"valor": None if dr is None else dr == 0, "incremento": dr,
                               "motivo": mot or ("0 descartes de softnet" if dr == 0 else f"{dr} descartes de softnet")}
    ok, mot = incremento(ms, desde, hasta, lambda m: (m.get("vmstat") or {}).get("oom_kill"))
    comp["oom_kill"] = {"valor": None if ok is None else ok == 0, "incremento": ok,
                        "motivo": mot or ("sin oom_kill" if ok == 0 else f"{ok} oom_kill")}
    bajos = [m["t"] for m in ms if desde <= m["t"] < hasta and isinstance(m.get("mem_disponible_kb"), int)
             and m["mem_disponible_kb"] < MEM_MIN_KB]
    if bajos:
        comp["memoria"]["valor"], comp["memoria"]["motivo"] = False, f"MemAvailable < 1 GiB en {len(bajos)} muestra(s)"
    vals = [c["valor"] for c in comp.values()]
    v = False if False in vals else (None if None in vals else True)
    res["S14"] = {"valor": v,
                  "no_cumplen": [k for k, c in comp.items() if c["valor"] is False],
                  "sin_medida": [k for k, c in comp.items() if c["valor"] is None]}
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("muestras")
    ap.add_argument("--desde", type=float, required=True)
    ap.add_argument("--hasta", type=float, required=True)
    ap.add_argument("--base-desde", type=float)
    ap.add_argument("--base-hasta", type=float)
    a = ap.parse_args()
    base = (a.base_desde, a.base_hasta) if a.base_desde is not None and a.base_hasta is not None else None
    with open(a.muestras, encoding="utf-8") as fh:
        print(json.dumps(evaluar(fh, a.desde, a.hasta, base), ensure_ascii=False, indent=1))
