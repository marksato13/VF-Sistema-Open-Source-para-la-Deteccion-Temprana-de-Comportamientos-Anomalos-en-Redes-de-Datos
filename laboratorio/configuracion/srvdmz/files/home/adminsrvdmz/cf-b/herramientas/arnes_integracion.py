#!/usr/bin/env python3
"""Ensayo de integración SIN tráfico de ataque y SIN agente: el generador REAL (original firmado, o la variante mínima por episodio)
corre su bucle y su compuerta de permiso tal cual; solo se sustituyen el cuerpo del episodio (marcas inicio/fin, sin lanzar nada) y
`esq.validar/comando_de` (no hay herramientas de ataque). Los tiempos se escalan 1/60 (ronda del vigía 60 s -> 1 s, validez del permiso
150 s -> 2,5 s, observación 90 s -> 1,5 s, contexto 120 s -> 2 s). El vigía es un modelo fiel de su bucle (permiso cada ronda, por el
filtro REAL `compuerta_b.filtrar`, instalado de forma atómica en un fichero como hace la orden de la Kali); la puerta es el proceso REAL
`compuerta_b.paso_puerta` con una puerta D5 simulada (duración y fallos inyectables).
Invariante (por episodio k, evaluada con los instantes registrados, no con la intención):
  I1  hubo una puerta liberada L_k posterior al fin del episodio k-1 (o al arranque) y anterior al inicio de k;
  I2  el permiso leído por el generador al lanzar k fue DECIDIDO por el filtro después de L_k (no es un permiso anterior);
  I3  cada puerta liberada se usa para un solo episodio.
Uso: arnes_integracion.py <variante: original|por_episodio> <escenario> <n_ensayos> -> imprime violaciones. rc 0 si 0 violaciones."""
import importlib.util
import json
import os
import random
import sys
import tempfile
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
import compuerta_b as cb  # noqa: E402

E = 1 / 60                                                    # escala de tiempo
RONDA, VALIDEZ, OBS, CTX, WARM = 60 * E, 150 * E, 90 * E, 120 * E, 60 * E
ESCENARIOS = {
    "base":        dict(gate=0.4, falla=0, lat=0.05, atasco=0, largo=1.5, jitter=0.0),
    "puerta_lenta": dict(gate=5.0, falla=0, lat=0.05, atasco=0, largo=1.5, jitter=0.0),       # más que la holgura entre episodios
    "puerta_falla": dict(gate=0.4, falla=2, lat=0.05, atasco=0, largo=1.5, jitter=0.0),       # 2 intentos fallidos por episodio
    "vigia_atascado": dict(gate=0.4, falla=0, lat=0.05, atasco=4.0, largo=1.5, jitter=0.0),   # una ronda tarda más que la validez
    "ssh_lento":   dict(gate=0.4, falla=0, lat=0.9, atasco=0, largo=1.5, jitter=0.0),          # latencia del canal ~ 54 s a escala real
    "jitter":      dict(gate=0.4, falla=1, lat=0.3, atasco=0, largo=1.5, jitter=0.5),
    # rondas del vigía que se alargan (el sensor o srv-dmz tardan: `correr` espera hasta 60 s por orden): 60..180 s a escala real
    "ronda_larga": dict(gate=0.4, falla=0, lat=0.05, atasco=0, largo=1.5, jitter=2.0),
    "ronda_larga_con_fallos": dict(gate=0.6, falla=1, lat=0.2, atasco=0, largo=1.5, jitter=2.0),
}


def cargar_generador(variante):
    ruta = RAIZ / "generador" / ("generar_campana_b.py" if variante == "por_episodio" else "generar_campana_original.py")
    sys.path.insert(0, str(RAIZ / "generador"))
    spec = importlib.util.spec_from_file_location("gen_" + variante, ruta)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def ensayo(variante, nombre, semilla):
    p = ESCENARIOS[nombre]
    rnd = random.Random(semilla)
    tmp = Path(tempfile.mkdtemp(prefix="arnes_"))
    gate_dir, corr = str(tmp / "compuerta"), tmp / "corrida"
    corr.mkdir()
    permiso_p = tmp / "permiso.json"
    g = cargar_generador(variante)
    g.esq.validar = lambda cfg, exigir_herramientas=False: []
    g.esq.comando_de = lambda cfg, s: ["true", s["id"]]
    lanzados, lock = [], threading.Lock()

    def episodio(cfg, s, rep, salida_dir, marcas, autorizado):
        ep = f"{s['id']}-r{rep}"
        try:
            leido = json.loads(permiso_p.read_text())
        except (OSError, ValueError):
            leido = None
        g.jsonl(marcas, {"evento": "inicio", "episodio_id": ep, "escenario": s["id"], "reloj": g.reloj()})
        with lock:
            lanzados.append({"ep": ep, "t": time.time(), "permiso": leido})
        time.sleep(0.05 if s["id"] == "escaneo_breve" else p["largo"])
        g.jsonl(marcas, {"evento": "fin", "episodio_id": ep, "estado": "completo", "reloj": g.reloj()})
        with lock:
            lanzados[-1]["fin"] = time.time()
        return "completo"
    g.correr_episodio = episodio
    esc = [{"id": i, "habilitado": True, "destino": "x", "servicio": "y", "timeout_s": 5}
           for i in ("escaneo_breve", "inundacion_http", "escaneo_sostenido", "fuerza_bruta_http")]
    cfg = {"semilla": semilla, "repeticiones": 2, "escenarios": esc, "tiempos_s": {
        "calentamiento_inicial": WARM, "contexto_antes": CTX, "observacion_despues": OBS}}
    (tmp / "cfg.json").write_text(json.dumps(cfg))
    parar = threading.Event()
    liberadas, estado_gen = [], {}

    def correr_generador():
        args = ["--config", str(tmp / "cfg.json"), "--salida-dir", str(corr), "--autorizado", "--permiso", str(permiso_p),
                "--nonce", "N", "--permiso-sondeo", "0.05", "--permiso-max-espera", "60"]
        if variante == "por_episodio":
            args.append("--permiso-por-episodio")
        estado_gen["rc"] = g.main(args)
        parar.set()

    def ssh_falso(orden, input=None, **kw):
        if p["atasco"] and rnd.random() < 0.25:
            time.sleep(p["atasco"])                           # ronda que se atasca más que la validez
        time.sleep(p["lat"])
        tmpf = str(permiso_p) + ".tmp"
        open(tmpf, "w").write(input)
        os.replace(tmpf, permiso_p)                           # instalación atómica, como la orden de la Kali
        try:
            marcas = (corr / "marcas.jsonl").read_text().splitlines()
        except OSError:
            marcas = []
        import subprocess
        return subprocess.CompletedProcess(orden, 0, stdout="0.0\n" + "".join(l + "\n" for l in marcas[estado_gen.get("n", 0):]), stderr="")

    def vigia():
        seq = 0
        time.sleep(rnd.random() * RONDA)                      # fase arbitraria respecto del generador
        while not parar.is_set():
            t0 = time.time()
            seq += 1
            perm = {"nonce": "N", "estado": "continuar", "causas": [], "secuencia": seq, "emitido_epoch": t0, "valido_hasta_epoch": t0 + VALIDEZ}
            rc, out, _e = cb.filtrar(gate_dir, ["ssh", "kali"], json.dumps(perm), run=ssh_falso, por_episodio=(variante == "por_episodio"))
            estado_gen["n"] = estado_gen.get("n", 0) + max(0, len(out.splitlines()) - 1)
            time.sleep(max(0.0, RONDA - (time.time() - t0) + p["jitter"] * rnd.random()))

    def puerta():
        fallos = {}

        def fn():
            with cb.Estado(gate_dir) as st:
                clave = st["n_inicios"]
            time.sleep(p["gate"])
            fallos[clave] = fallos.get(clave, 0) + 1
            return {"lista": fallos[clave] > p["falla"], "intentos": 1}
        while not parar.is_set():
            r = cb.paso_puerta(gate_dir, fn, espera_fin=0.25)
            if r == "liberada":
                liberadas.append(time.time())
            time.sleep(0.05)

    hilos = [threading.Thread(target=f, daemon=True) for f in (vigia, puerta)]
    for h in hilos:
        h.start()
    g_t = threading.Thread(target=correr_generador, daemon=True)
    g_t.start()
    g_t.join(timeout=300)
    parar.set()
    for h in hilos:
        h.join(timeout=10)
    return evaluar(lanzados, liberadas, estado_gen.get("rc"), len(esc) * 2, variante, nombre, semilla)


def evaluar(lanzados, liberadas, rc, esperados, variante, nombre, semilla):
    v, usadas = [], set()
    prev_fin = None
    for i, l in enumerate(lanzados):
        L = [j for j, t in enumerate(liberadas) if j not in usadas and (prev_fin is None or t > prev_fin) and t < l["t"]]
        if not L:
            v.append(f"I1 {l['ep']}: lanzado sin puerta liberada posterior al fin del anterior")
        else:
            j = L[-1] if len(L) == 1 else L[0]
            usadas.add(j)
            dec = ((l["permiso"] or {}).get("compuerta_b") or {}).get("decidido_en")
            if dec is None or dec < liberadas[j]:
                v.append(f"I2 {l['ep']}: lanzado con un permiso decidido {('%.2f s ANTES' % (liberadas[j] - dec)) if dec else 'sin sello'} de la puerta liberada")
        prev_fin = l.get("fin", prev_fin)
    return {"variante": variante, "escenario": nombre, "semilla": semilla, "lanzados": len(lanzados), "esperados": esperados,
            "generador_rc": rc, "violaciones": v}


def _tarea(a):
    return ensayo(*a)


def main(variante, nombre, n):
    nombres = list(ESCENARIOS) if nombre == "todos" else [nombre]
    tareas = [(variante, e, s) for e in nombres for s in range(1, int(n) + 1)]
    with ProcessPoolExecutor(max_workers=min(8, len(tareas))) as ex:
        res = list(ex.map(_tarea, tareas))
    mal = 0
    for e in nombres:
        rr = [r for r in res if r["escenario"] == e]
        viol = sum(len(r["violaciones"]) for r in rr)
        incompletos = sum(1 for r in rr if r["lanzados"] != r["esperados"])
        mal += viol
        print("%-15s %-12s ensayos=%d episodios_lanzados=%d violaciones=%d ensayos_incompletos=%d" % (
            e, variante, len(rr), sum(r["lanzados"] for r in rr), viol, incompletos))
        for r in rr:
            for x in r["violaciones"][:2]:
                print("     seed %d: %s" % (r["semilla"], x))
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
