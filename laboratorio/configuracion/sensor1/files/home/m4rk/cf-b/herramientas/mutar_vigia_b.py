#!/usr/bin/env python3
"""Mutaciones de la excepción NTP de vigia_4c_b.py: cada una debe hacer fallar alguna prueba de tests/test_vigia_b.py."""
import pathlib
import shutil
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MUT = [
    ('ev.get("event_type") == "flow" and', 'True and'), ('ev.get("proto") == "UDP" and', 'True and'),
    ('and ev.get("dest_port") == 123', 'and True'), ('ev.get("dest_ip") in ntp and', 'True and'),
    ('(f.get("pkts_toserver") or 0) <= NTP_MAX_PAQUETES', 'True'), ('(f.get("pkts_toclient") or 0) <= NTP_MAX_PAQUETES', 'True'),
    ('(f.get("bytes_toserver") or 0) <= NTP_MAX_BYTES', 'True'), ('(f.get("bytes_toclient") or 0) <= NTP_MAX_BYTES', 'True'),
    ('"pkts_toserver" in f and "bytes_toserver" in f', 'True'),
    ('NTP_MAX_PAQUETES, NTP_MAX_BYTES = 4, 400', 'NTP_MAX_PAQUETES, NTP_MAX_BYTES = 4000, 400000'),
    ('and es_ntp_permitido(ev, ntp or set()):\n            ntp_ex += 1\n            continue', 'and False:\n            ntp_ex += 1\n            continue'),
    ('            ntp_ex += 1\n', '            pass\n'),
]


def main():
    fuente = (RAIZ / "generador" / "vigia_4c_b.py").read_text(encoding="utf-8")
    vivos = []
    for i, (a, b) in enumerate(MUT):
        if fuente.count(a) < 1:
            print(f"M{i:02d} NO APLICA: {a!r}")
            vivos.append(i)
            continue
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
            (t / "generador").mkdir()
            (t / "tests").mkdir()
            shutil.copy(RAIZ / "generador" / "vigia_4c_original.py", t / "generador")
            (t / "generador" / "vigia_4c_b.py").write_text(fuente.replace(a, b, 1), encoding="utf-8")
            shutil.copy(RAIZ / "tests" / "test_vigia_b.py", t / "tests")
            rc = subprocess.run([sys.executable, "-I", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", str(t / "tests")],
                                capture_output=True, cwd=t).returncode
        print(f"M{i:02d} {'MUERTA' if rc else 'VIVA  '} {a[:60]!r}")
        if not rc:
            vivos.append(i)
    print(f"{len(MUT) - len(vivos)}/{len(MUT)} muertas; vivas: {vivos}")
    return 1 if vivos else 0


if __name__ == "__main__":
    sys.exit(main())
