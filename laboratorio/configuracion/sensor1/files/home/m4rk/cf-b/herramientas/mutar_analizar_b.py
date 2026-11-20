#!/usr/bin/env python3
"""Mutaciones de analizar_b.py: cada una debe hacer fallar al menos una prueba. rc 0 si todas mueren."""
import pathlib
import shutil
import subprocess
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
MUT = [
    ("t_sup + u < t_fin", "t_sup + u <= t_fin"), ("t_sup + u < t_fin", "t_sup < t_fin"),
    ("t_inf - u >= t_fin", "t_inf - u > t_fin"), ("t_inf - u >= t_fin", "t_inf >= t_fin"),
    ("min(ep[\"t_fin_ref\"], obs)", "max(ep[\"t_fin_ref\"], obs)"),
    ("K_BLOCK = 3", "K_BLOCK = 1"), ("K_LIMIT = 5", "K_LIMIT = 2"), ("THETA = 0.5", "THETA = 0.05"),
    ("N_BASE = 10", "N_BASE = 3"), ("BASE_MIN = 5.0", "BASE_MIN = 0.0"), ("HUECOS_MAX = 0.10", "HUECOS_MAX = 0.95"),
    ("INTENTO_MIN = 0.5", "INTENTO_MIN = 0.0"),
    ("if ev[\"violaciones\"]:", "if False:"), ("if not ev[\"hay_traza\"]:", "if False:"),
    ("if not ev[\"aplicaciones\"]:", "if False:"),
    ("if a[\"estado\"] == \"no_confirmada\":", "if False:"),
    ("if a[\"estado\"] == \"sin_confirmacion\" and res == \"cumple\":", "if False:"),
    ("n[\"set\"] != SET_DE.get(accion)", "False"), ("n[\"ip\"] != origen or", "False and"),
    ("if r2[\"resultado\"] in (\"fallo\", \"fallo_experimento\"):", "if False:"),
    ("if r2[\"resultado\"] == \"indeterminado\" and r3[\"resultado\"] == \"cumple\":", "if False:"),
    ("if len(blq) < k:", "if False:"), ("if t_efecto is None and not intento_sostenido:", "if False:"), ("intenta = all(b[\"syn\"] >= umbral_syn for b in run)", "intenta = True"),
    ("if len(previos) < N_BASE:", "if False:"), ("if _huecos(serie, ep[\"t_inicio\"], t_fin) > HUECOS_MAX:", "if False:"),
    ("not c[\"ok\"] and c.get(\"atribuible\")", "not c[\"ok\"]"), ("if not tx:", "if False:"),
    ("t0, t1 = ep[\"t_inicio\"] - 60, t_fin_eval(ep) + 90", "t0, t1 = ep[\"t_inicio\"], t_fin_eval(ep)"),
    ("if ep[\"origen\"] in ultima.get(s, []):", "if False:"), ("if not lect:", "if False:"),
    ("x[\"t\"] >= t_fin and", "x[\"t\"] >= 0 and"), ("max(lect, key=lambda x: x[\"t\"])", "min(lect, key=lambda x: x[\"t\"])"),
    ("alfa / 2)", "alfa)"), ("1 - alfa / 2)", "alfa / 2)"),
    ("if e.get(\"excluido\")", "if False"), ("adm = [e for e in eps if not e.get(\"excluido\")]", "adm = list(eps)"),
    ("b[\"t\"] + BLOQUE <= t_fin]", "b[\"t\"] <= t_fin + 999]"), ("if res == \"cumple\" and desc is None:", "if False:"), ("e.get(\"id\") == r2.get(\"id\")", "True"), ("e.get(\"ip\") == ep[\"origen\"] and t_min", "True and t_min"), ("t_min, t_max = r2[\"t_apl_inf\"],", "t_min, t_max = 0,"),
    ("math.ceil(t_apl)", "math.floor(t_apl) - 5"),
]


def main():
    fuente = (AQUI / "analizar_b.py").read_text(encoding="utf-8")
    vivos = []
    for i, (a, b) in enumerate(MUT):
        if fuente.count(a) < 1:
            print(f"M{i:02d} NO APLICA (texto ausente): {a}")
            vivos.append(i)
            continue
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
            (t / "herramientas").mkdir()
            (t / "tests").mkdir()
            (t / "herramientas" / "analizar_b.py").write_text(fuente.replace(a, b, 1), encoding="utf-8")
            shutil.copy(RAIZ / "tests" / "test_analizar_b.py", t / "tests")
            rc = subprocess.run([sys.executable, "-I", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                                 str(t / "tests")], capture_output=True, cwd=t).returncode
        print(f"M{i:02d} {'MUERTA' if rc != 0 else 'VIVA  '} {a}  ->  {b}")
        if rc == 0:
            vivos.append(i)
    print(f"{len(MUT) - len(vivos)}/{len(MUT)} muertas; vivas: {vivos}")
    return 1 if vivos else 0


if __name__ == "__main__":
    sys.exit(main())
