#!/usr/bin/env python3
"""Mutaciones de d5_episodio.py: cada una debe hacer fallar alguna prueba de tests/test_d5.py. rc 0 si todas mueren."""
import pathlib
import shutil
import subprocess
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
MUT = [
    ('k.split("|", 1)[0] == origen', 'k.startswith(origen[:-1])'), ('k.split("@", 1)[0] == origen', 'k.startswith(origen[:-1])'),
    ('del nuevo["vigentes"][k]', 'pass'), ('del nuevo["escalada"][k]', 'pass'),
    ('senal(pid, signal.SIGSTOP)', 'pass'), ('senal(pid, signal.SIGKILL)', 'pass'),
    ('if pid <= 1:', 'if False:'), ('fh.write(crudo)', 'fh.write(b"")'),
    ('os.replace(tmp, ruta)', 'pass'),
    ('"fresco": gen > desde', '"fresco": True'), ('"vigente": exp > ahora()', '"vigente": True'),
    ('"limpio": not propias', '"limpio": True'),
    ('and e.get("ip") == origen]', 'and e.get("ip") != origen]'),
    ('e.get("aplicado_en", 0) > desde', 'e.get("aplicado_en", 0) >= 0'),
    ('if not real:\n        return {"ok": True, "rc": 0, "retirado": False, "seco"', 'if False:\n        return {"ok": True, "rc": 0, "retirado": False, "seco"'),
    ('if n["presente"]:', 'if False:'), ('if not n2.get("ok") or n2["presente"]:', 'if False:'),
    ('if not a.get("ok") or a["aplicaciones_nuevas"]:', 'if False:'),
    ('if not (f2.get("ok") and f2["fresco"] and f2["vigente"] and f2["limpio"]):', 'if False:'),
    ('if not ok:\n            return {"lista": False, "pasos": pasos,', 'if False:\n            return {"lista": False, "pasos": pasos,'),
    ('if a.origen != ORIGEN:', 'if False:'),
    ('if res["lista"]:\n                return', 'if False:\n                return'),
    ('self.dormir(espera_entre)', 'pass'), ('self.dormir(self.espera_agente)', 'pass'),
]


def main():
    fuente = (AQUI / "d5_episodio.py").read_text(encoding="utf-8")
    vivos = []
    for i, (a, b) in enumerate(MUT):
        if fuente.count(a) < 1:
            print(f"M{i:02d} NO APLICA (texto ausente): {a!r}")
            vivos.append(i)
            continue
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
            (t / "herramientas").mkdir()
            (t / "tests").mkdir()
            (t / "herramientas" / "d5_episodio.py").write_text(fuente.replace(a, b, 1), encoding="utf-8")
            shutil.copy(RAIZ / "tests" / "test_d5.py", t / "tests")
            rc = subprocess.run([sys.executable, "-I", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", str(t / "tests")],
                                capture_output=True, cwd=t).returncode
        print(f"M{i:02d} {'MUERTA' if rc != 0 else 'VIVA  '} {a!r:.70}")
        if rc == 0:
            vivos.append(i)
    print(f"{len(MUT) - len(vivos)}/{len(MUT)} muertas; vivas: {vivos}")
    return 1 if vivos else 0


if __name__ == "__main__":
    sys.exit(main())
