"""Reproducción de los tres hallazgos de la revisión de E-carga v2 (07-nov), con dobles y reloj simulado. Sin hosts.
  ECARGA_DIRS=<versión> OBS_P4=<obs_p4_post.sh> python3 tests/reproducir_ecarga_guardia_s7.py
Imprime lo que hace la versión indicada: antes con 975e715, después con la corregida. No aprueba nada.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_etapa4_ecarga_guardia_s7 as t                                                        # noqa: E402
from test_etapa4_ecarga_prep import (D, EVAL, H, Lab, _cli, completo, fuentes, lineas, ruta, s7_fuente, s7_trazas,  # noqa: E402
                                     serie)

VERSION = "nueva" if ruta("arrancar_c1.sh", obligatorio=False) else "975e715"


def lab():
    return Lab(Path(tempfile.mkdtemp(prefix="repro-")))


def h1():
    print("\n## H1. Arranque con la guardia ya parada, y cruce con la parada\n")
    print("| Caso | rc C1 | Órdenes de start | Vivos tras C1 | Vivos al final | rc muestreo | Parada |")
    print("|---|---:|---:|---:|---:|---:|---|")
    l = lab()
    r = t.caso_parada_previa(l)
    print(f"| Parada confirmada antes de T_g | {r['c1_rc']} | {r['ordenes_arrancar']} | {r['vivos_tras_c1']} | {r['vivos_al_final']} | "
          f"{r['rc_muestreo']} | {' '.join(t.resultados(r['x']))} |")
    if VERSION != "975e715":
        print("\nMotivo verificable: `" + t.lee(r["x"] / "manual" / "RESULTADO-C1").strip() + "`\n")
    l = lab()
    r = t.caso_cruce_lento(l)
    print("| Parada durante un start lento | " + f"{r['c1_rc']} | {t.starts(l)} | "
          f"{r['vivos_tras_c1']} | {r['vivos_al_final']} | {r['rc_muestreo']} | {' '.join(t.resultados(r['x']))} |")
    print("\nOrden de las órdenes al host: " + " -> ".join(o.split()[-1] for o in r["ordenes"]))


def h1b():
    print("\n## H1b. T_g superado después de la comprobación inicial, reloj y ssh simulados\n")
    print("Reloj en T_g - 1, muestreador vivo, lectura válida, sin solicitud de parada, parada en T_g + 40.\n")
    print("| Caso | rc C1 | Órdenes de arranque | Start | Vivos | RESULTADO-C1 |")
    print("|---|---:|---:|---:|---:|---|")
    for nombre, kw in (("Salto en la espera a T_g + 45", {"salto_espera": 45}), ("Salto en la espera a T_g + 1", {"salto_espera": 1}),
                       ("Salto al evaluar la puerta a T_g + 45", {"salto_puerta": 45}), ("Salto al evaluar la puerta a T_g + 1", {"salto_puerta": 1}),
                       ("Control: llega exactamente a T_g", {})):
        r = t.caso_c1_tardio(lab(), **kw)
        f = r["resultado"]
        print(f"| {nombre} | {r['rc']} | {r['ordenes']} | {r['starts']} | {r['vivos']} | {f.get('resultado')}: {f.get('motivo')} |")


def h2():
    print("\n## H2. Parada al salir del bucle, reloj simulado\n")
    print("T0 = 1794193200, PARADA = T0+60, FIN = T0+120, intervalo 30 s. El salto ocurre en la primera espera: de T0 a T0+125.\n")
    print("| Caso | Órdenes de parada | Estado final | rc | Parados | RESULTADO-PARADA |")
    print("|---|---:|---|---:|---|---|")
    casos = [("Parada normal", {}, {}), ("Salto de reloj", {}, {"salto": (1, 125)}),
             ("Parada ya confirmada", {"memdisp": "500000"}, {}),
             ("Salto + fallo transitorio", {"ssh_falla_parar": "1"}, {"salto": (1, 125)}),
             ("Salto + intentos agotados", {"ssh_falla_parar": "99"}, {"salto": (1, 125), "CF_MAX_INTENTOS": 3}),
             ("Salto en modo seco", {}, {"salto": (1, 125), "modo": "seco"})]
    for nombre, marcas, kw in casos:
        l = lab()
        l.arrancar_directo()
        for k, v in marcas.items():
            l.marca(k, v)
        r = t.reloj(l, **kw)
        res = r["resultado"]["resultado"] if r["resultado"] else "no existe"
        print(f"| {nombre} | {r['ordenes_parar']} | {r['estado']} | {r['rc']} | {'sí' if r['parado'] else 'no'} | {res} |")


def s7_antes(tmp):
    """obs_p4_post.sh tal como se usa en D4 y el valor que su salida permite registrar."""
    obs = Path(os.environ["OBS_P4"])
    l = Lab(tmp / "lab")
    ag, re_, _ = s7_trazas(entregas=[100], d=D, a=H)
    (l.home / "relay-v2").mkdir()
    (l.home / "relay-v2" / "traza.jsonl").write_text(re_)
    l.marca("traza_agente", ag)
    o = tmp / "obs"
    o.mkdir()
    bloque = "S feed_seq=ERROR\nS home_libre_kb=12455468 carga=0.1 0.1 0.1 memdisp_kb=6769344\n"
    (o / "muestras.txt").write_text("".join(f"### x {D - 30 + 30 * i:.0f}\nB panel_https=401\n{bloque}" for i in range(124)))
    txt = obs.read_text(encoding="utf-8")
    der = tmp / "obs_p4_post.derivado.sh"
    der.write_text("\n".join(f"O={o}" if x.startswith("O=") else x for x in txt.splitlines()) + "\n")
    r = subprocess.run(["bash", str(der), str(int(D)), str(int(H))], capture_output=True, text=True, env=l.env, timeout=60)
    return r.returncode, r.stdout + r.stderr


def h3():
    print("\n## H3. S7 sin secuencia del publicador\n")
    with tempfile.TemporaryDirectory(prefix="repro-") as td:
        tmp = Path(td)
        rc, out = s7_antes(tmp)
        print(f"`obs_p4_post.sh`, sellado y sin cambios: rc {rc}")
        for x in out.splitlines():
            if any(k in x for k in ("entregas del relé", "aceptadas en orden", "entregadas NO aceptadas", "publicador:")):
                print("    " + x.strip())
        print()
        args = None
        (tmp / "e2e").mkdir()
        if VERSION == "975e715":
            args = fuentes(tmp / "e2e", lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp / "e2e" / "obs_pcap.log")
            print("Con esa salida, la regla escrita de D4 permite `--manual S7=true`, que `construir_entrada.py` acepta:")
        else:
            args = fuentes(tmp / "e2e", lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp / "e2e" / "obs_pcap.log",
                           s7=dict(entregas=[100, 101], feed=lambda i: "ERROR"))
            print("`derivar_s7.py` con los mismos datos, y con una segunda entrega para aislar la secuencia del publicador:")
            print("    una entrega:  " + json.dumps(s7_fuente(tmp, entregas=[100], feed=lambda i: "ERROR")["S7"], ensure_ascii=False))
            print("    dos entregas: " + json.dumps(json.loads((tmp / "e2e" / "s7.json").read_text())["S7"], ensure_ascii=False))
        rc, o, err = _cli(ruta("construir_entrada.py"), *args)
        e = json.loads((tmp / "e2e" / "entrada.json").read_text())
        rc, o, err = _cli(EVAL, "veredicto", "--entrada", tmp / "e2e" / "entrada.json")
        v = json.loads(o)
        print(f"\nEntrada: S7 = {json.dumps(e['S']['S7'])}. Veredicto: «{v['estabilidad_tecnica']}», "
              f"habilita_condicion_3 = {json.dumps(v['habilita_condicion_3'])}, rc {rc}")
        if VERSION != "975e715":
            (tmp / "e2e2").mkdir()
            args2 = fuentes(tmp / "e2e2", lineas(serie(D - 3, H + 20)), completo(), pcap_log=tmp / "e2e2" / "obs_pcap.log")
            i = args2.index("--salida-entrada")
            args2[i:i] = ["--manual", f"S7=true:{tmp / 'e2e2' / 'ev.txt'}"]
            rc, o, err = _cli(ruta("construir_entrada.py"), *args2)
            print(f"`--manual S7=true`: rc {rc}, {err.strip()}")


if __name__ == "__main__":
    print(f"# Reproducción con la versión {VERSION}. Dobles y reloj simulado; sin hosts. {time.strftime('%FT%TZ', time.gmtime())}")
    a = ruta("arrancar_c1.sh", obligatorio=False)
    print("# arrancar_c1.sh: " + (a.read_text(encoding="utf-8").splitlines()[1].split("VERSION ")[-1] if a else "bloque manual"))
    h1()
    h1b()
    h2()
    h3()
