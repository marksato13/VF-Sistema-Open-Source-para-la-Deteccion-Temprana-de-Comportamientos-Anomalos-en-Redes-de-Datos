"""La tabla de variables del panel: se genera del esquema, se ilustra con datos.

Dos propiedades que importan mas de lo que parece:

  - **La tabla no se escribe a mano.** El texto que habia antes decia "seis de
    red, cinco de transporte y diecisiete de aplicacion" cuando el esquema dice
    nueve, ocho y once. La suma cuadraba -28- asi que nadie lo noto. Generarla
    del esquema hace imposible esa clase de error.

  - **La muestra sale del dataset real o no sale.** Si el CSV no esta, el panel
    lo dice; nunca se rellena con un ejemplo inventado.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard", REPO / "scripts/engine/dashboard.py")
assert SPEC and SPEC.loader
dash = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dash
SPEC.loader.exec_module(dash)

V2 = REPO / "configs/features/multilayer-v2.json"
V3 = REPO / "configs/features/multilayer-v3.json"
TXT = REPO / "configs/features/descripciones.json"


class TablaDesdeElEsquema(unittest.TestCase):
    def test_los_recuentos_por_capa_salen_del_esquema(self):
        r = dash.resumen_variables(V2, V3, TXT, None)
        cuenta = {c["id"]: c["n"] for c in r["capas"]}
        self.assertEqual(cuenta, {"L2": 3, "L3": 9, "L4": 8, "L7": 11})
        self.assertEqual(r["n_motor"], 28)
        self.assertEqual(r["n_total"], 31)

    def test_las_de_capa_2_se_marcan_fuera_del_motor(self):
        # El motor corre con el esquema v2: acumulamos 31 pero puntuamos 28.
        # Ensenarlas como si se puntuaran seria decir que el sistema detecta
        # ARP spoofing hoy, y no lo hace todavia.
        r = dash.resumen_variables(V2, V3, TXT, None)
        por_nombre = {v["name"]: v for v in r["variables"]}
        for n in ("arp_request_rate_10s", "unique_src_mac_30s",
                  "mac_ip_binding_changes_60s"):
            self.assertFalse(por_nombre[n]["en_motor"], n)
        self.assertTrue(por_nombre["packet_rate_10s"]["en_motor"])

    def test_todas_las_variables_tienen_texto(self):
        # Una fila sin descripcion es una fila que el tribunal preguntara.
        r = dash.resumen_variables(V2, V3, TXT, None)
        sin_texto = [v["name"] for v in r["variables"] if not v["que"] or not v["senal"]]
        self.assertEqual(sin_texto, [])

    def test_sin_esquema_extra_solo_salen_las_del_motor(self):
        r = dash.resumen_variables(V2, None, TXT, None)
        self.assertEqual(r["n_total"], 28)
        self.assertTrue(all(v["en_motor"] for v in r["variables"]))


class MuestraDelDataset(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv = Path(self.tmp.name) / "d.csv"

    def escribir(self, filas: int, valor=lambda i: i % 7) -> None:
        with self.csv.open("w", encoding="utf-8", newline="\n") as f:
            f.write("campaign_id,entity_ip,window_end_utc,packet_rate_10s\n")
            for i in range(filas):
                f.write("c,10.10.20.%d,2026-09-24T10:%02d:%02dZ,%s\n"
                        % (21 + i % 6, i // 60 % 60, i % 60, valor(i)))

    def test_estadisticos_basicos(self):
        self.escribir(100, valor=lambda i: i)
        m = dash.muestra_del_dataset(self.csv, ["packet_rate_10s"])
        d = m["por_variable"]["packet_rate_10s"]
        self.assertEqual(d["n"], 100)
        self.assertEqual(d["min"], 0.0)
        self.assertEqual(d["max"], 99.0)

    def test_la_cola_no_parte_una_fila_por_la_mitad(self):
        # Al leer solo los ultimos N bytes, la primera linea suele venir
        # cortada. Si no se descarta, sale una fila con menos columnas -o con
        # un numero truncado- y la estadistica queda mal en silencio.
        self.escribir(5000, valor=lambda i: 1)
        m = dash.muestra_del_dataset(self.csv, ["packet_rate_10s"], max_bytes=4096)
        d = m["por_variable"]["packet_rate_10s"]
        self.assertGreater(d["n"], 10)
        self.assertEqual(d["min"], 1.0)
        self.assertEqual(d["max"], 1.0)
        self.assertLess(d["n"], 5000, "deberia haber leido solo la cola")

    def test_la_cabecera_no_se_cuela_como_fila(self):
        # Encontrado con datos reales: si el CSV cabe entero en la ventana de
        # lectura, la cabecera entraba como fila. Los numeros se salvaban
        # -float("packet_rate_10s") falla y se descarta- pero "entity_ip"
        # contaba como una entidad mas y "window_end_utc" salia como la ultima
        # ventana del rango.
        self.escribir(20, valor=lambda i: 1)
        m = dash.muestra_del_dataset(self.csv, ["packet_rate_10s"], max_bytes=10_000_000)
        meta = m["_meta"]
        self.assertEqual(meta["filas"], 20)
        self.assertEqual(meta["entidades"], 6)
        self.assertNotIn("utc", meta["hasta"][-4:])
        self.assertTrue(meta["hasta"].startswith("2026-"))
        self.assertEqual(m["por_variable"]["packet_rate_10s"]["n"], 20)

    def test_prefiere_ejemplos_distintos_de_cero(self):
        # Un ejemplo con valor 0 no ensena nada de lo que la variable mide.
        self.escribir(300, valor=lambda i: 0 if i % 2 else 5)
        m = dash.muestra_del_dataset(self.csv, ["packet_rate_10s"])
        ej = m["por_variable"]["packet_rate_10s"]["ejemplos"]
        self.assertEqual(len(ej), 3)
        self.assertTrue(all(e["valor"] != 0 for e in ej))
        self.assertTrue(all(e["entidad"].startswith("10.10.20.") for e in ej))

    def test_si_todo_es_cero_lo_dice_en_vez_de_callar(self):
        # Que una variable este a cero en toda la cola es informacion, no un
        # fallo: significa que esta red no ejercita ese comportamiento.
        self.escribir(50, valor=lambda i: 0)
        d = dash.muestra_del_dataset(self.csv, ["packet_rate_10s"])["por_variable"]["packet_rate_10s"]
        self.assertEqual(d["ceros"], d["n"])
        self.assertEqual(len(d["ejemplos"]), 3)

    def test_sin_dataset_no_se_inventa_nada(self):
        m = dash.muestra_del_dataset(Path("/no/existe.csv"), ["packet_rate_10s"])
        self.assertEqual(m, {})
        r = dash.resumen_variables(V2, V3, TXT, Path("/no/existe.csv"))
        self.assertIsNone(r["dataset"])
        self.assertTrue(all(v["muestra"] is None for v in r["variables"]))


if __name__ == "__main__":
    unittest.main()
