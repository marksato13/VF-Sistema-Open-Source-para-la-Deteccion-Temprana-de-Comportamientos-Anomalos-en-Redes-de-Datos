"""La particion debe garantizar que no hay fuga temporal entre conjuntos."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUTA = REPO / "scripts/dataset/particionar_linea_base.py"
SPEC = importlib.util.spec_from_file_location("particionar", RUTA)
assert SPEC and SPEC.loader
pt = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pt
SPEC.loader.exec_module(pt)

INICIO = datetime(2026, 9, 24, 8, 0, 0, tzinfo=timezone.utc)


def filas(horas: float, paso_s: int = 10, entidades: int = 2) -> list[dict]:
    salida = []
    n = int(horas * 3600 / paso_s)
    for i in range(n):
        t = INICIO + timedelta(seconds=i * paso_s)
        for e in range(entidades):
            salida.append({"window_end_utc": t.isoformat(),
                           "entity_ip": "10.10.20.%d" % (21 + e),
                           "eligible_training": "True"})
    return salida


class SinFugaTemporal(unittest.TestCase):
    def test_ninguna_ventana_de_conjuntos_distintos_esta_cerca(self):
        # Es la propiedad que hace defendible el umbral calibrado: si dos
        # ventanas de train y validation estan a 10 s, comparten 50 s de los
        # mismos paquetes y la validacion deja de ser independiente.
        f, _ = pt.particionar(filas(12), bloque_s=3600, guarda_s=60)
        self.assertEqual(pt.comprobar(f, 60), [])

    def test_la_guarda_descarta_justo_la_frontera(self):
        f, informe = pt.particionar(filas(6), bloque_s=3600, guarda_s=60)
        # 6 bloques, 5 fronteras interiores, 60 s de guarda cada una, 10 s de
        # paso y 2 entidades: 5 x 6 x 2 = 60 ventanas descartadas.
        self.assertEqual(informe["descartadas_por_guarda"], 60)

    def test_una_particion_por_filas_SI_tendria_fuga(self):
        # Contraste explicito: asi se ve que la comprobacion detecta de verdad
        # el problema, y no que siempre devuelva vacio.
        f = filas(2)
        for i, fila in enumerate(f):
            fila["particion"] = "train" if i % 2 else "validation"
        self.assertNotEqual(pt.comprobar(f, 60), [])


class RepartoPorBloques(unittest.TestCase):
    def test_los_tres_conjuntos_cubren_el_ciclo_diario(self):
        # Con bloques de 2 h sobre 24 h, cada conjunto toca varias franjas
        # horarias distintas. Una particion en tres tramos contiguos daria a
        # cada conjunto una sola franja, y la diferencia medida entre ellos
        # seria la curva diaria y no el modelo.
        f, _ = pt.particionar(filas(24), bloque_s=7200, guarda_s=60)
        horas = {}
        for fila in f:
            if fila["particion"] == "descartada_guarda":
                continue
            h = int(fila["window_end_utc"][11:13])
            horas.setdefault(fila["particion"], set()).add(h)
        for conjunto in ("train", "validation", "test"):
            self.assertGreaterEqual(len(horas.get(conjunto, ())), 4,
                                    "%s cubre muy pocas horas" % conjunto)

    def test_el_reparto_es_deterministico(self):
        a, _ = pt.particionar(filas(8), bloque_s=3600, guarda_s=60)
        b, _ = pt.particionar(filas(8), bloque_s=3600, guarda_s=60)
        self.assertEqual([x["particion"] for x in a], [x["particion"] for x in b])

    def test_hay_de_los_tres_conjuntos(self):
        _, informe = pt.particionar(filas(10), bloque_s=3600, guarda_s=60)
        for conjunto in ("train", "validation", "test"):
            self.assertGreater(informe["reparto"].get(conjunto, 0), 0)
        self.assertEqual(informe["conjuntos_vacios"], "ninguno")

    def test_avisa_si_no_salen_los_tres_conjuntos(self):
        # Con menos bloques que posiciones del patron nunca se llega a "test".
        # Sin este aviso la particion saldria coja y el umbral se calibraria
        # sin conjunto de prueba, cosa que no delata ninguna metrica.
        _, informe = pt.particionar(filas(3), bloque_s=3600, guarda_s=60)
        self.assertEqual(informe["conjuntos_vacios"], ["test"])
        self.assertIn("--bloque-horas", informe["motivo_probable"])


if __name__ == "__main__":
    unittest.main()
