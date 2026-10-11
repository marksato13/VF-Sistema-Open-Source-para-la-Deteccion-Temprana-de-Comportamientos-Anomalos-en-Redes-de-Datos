"""Reentrenamiento supervisado: las cuatro defensas y el ciclo promover/revertir.

Todo con datos sinteticos en un directorio temporal: ninguna prueba toca el
modelo publicado ni los artefactos del repositorio.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "modeling"))
sys.path.insert(0, str(REPO / "scripts" / "setup"))

import cyberflow_aprendizaje as ap  # noqa: E402

NOMBRES = ap.nombres_v2()
IPS = ["10.10.20.%d" % i for i in range(21, 26)]


def filas_sinteticas(inicio: datetime, horas: float, paso_s: int, rng, desplazar=0.0,
                     ips=IPS, campana="prueba"):
    filas = []
    n = int(horas * 3600 / paso_s)
    for k in range(n):
        t = (inicio + timedelta(seconds=k * paso_s)).isoformat()
        for ip in ips:
            f = {"campaign_id": campana, "entity_ip": ip, "window_end_utc": t,
                 "history_coverage_s": "60.0", "eligible_training": "True"}
            for j, nombre in enumerate(NOMBRES):
                f[nombre] = "%.6f" % (10 + j + rng.normal() + desplazar)
            filas.append(f)
    return filas


def escribir(ruta: Path, filas: list[dict]):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    columnas = ["campaign_id", "entity_ip", "window_end_utc", "history_coverage_s",
                "eligible_training"] + NOMBRES
    if filas and "particion" in filas[0]:
        columnas.append("particion")
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)


def correr(script: str, *args):
    r = subprocess.run([sys.executable, str(REPO / script), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(r.stdout[-1500:] + r.stderr[-1500:])
    return r.stdout


TOML = """
[motor]
detector = "if_vigente"
calibrado_en_esta_red = true

[rutas]
raiz = "{raiz}"
eve = "{raiz}/no-existe/eve.json"
modelo = "artifacts/model/vigente.joblib"
manifiesto = "artifacts/model/vigente.json"
esquema = "configs/features/multilayer-v2.json"
registro = "logs/motor_decision.log"
dataset = "artifacts/linea-base/multilayer-v3.csv"

[reentrenamiento]
activo = true
base = "artifacts/linea-base/particionado.csv"
ataques = "artifacts/ataques.csv"
dias_minimos = 3
filas_minimas_lote = 100
tolerancia_fpr = 0.05
"""


class Escenario:
    """Una raiz de despliegue completa: base, oro, modelo vigente, lotes, registro."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cf-aprendizaje-"))
        self.rng = np.random.default_rng(7)
        raiz = self.tmp
        (raiz / "configs").mkdir()
        self.toml = raiz / "configs" / "cyberflow.local.toml"
        self.toml.write_text(TOML.format(raiz=raiz.as_posix()), encoding="utf-8")

        lb = raiz / "artifacts" / "linea-base"
        base = filas_sinteticas(datetime(2026, 9, 1, tzinfo=timezone.utc), 12, 60, self.rng)
        escribir(lb / "base.csv", base)
        correr("scripts/dataset/particionar_linea_base.py", "--entrada", str(lb / "base.csv"),
               "--salida", str(lb / "particionado.csv"), "--informe", str(lb / "particion.json"))
        correr("scripts/modeling/entrenar_preliminar.py", "--entrada", str(lb / "particionado.csv"),
               "--schema", str(ap.ESQUEMA_V2), "--salida", str(raiz / "paq.joblib"),
               "--informe", str(raiz / "paq.json"), "--n-estimators", "100")
        from promover_preliminar import promover
        promover(raiz / "paq.joblib", "if_vigente", raiz / "artifacts/model/vigente.joblib",
                 raiz / "artifacts/model/vigente.json", raiz / "paq.json")

        ataques = filas_sinteticas(datetime(2026, 9, 30, tzinfo=timezone.utc), 1, 300, self.rng,
                                   desplazar=8.0)
        escribir(raiz / "artifacts" / "ataques.csv", ataques)

        self.cfg = ap.cargar_config(self.toml)
        ap.crear_oro(self.cfg, lb / "particionado.csv")

    def dia(self, d: date, desplazar=0.0):
        """Anade al dataset el dia d (cada 5 min, 5 IPs)."""
        ruta = self.cfg["dataset"]
        filas = filas_sinteticas(datetime(d.year, d.month, d.day, tzinfo=timezone.utc), 24, 300,
                                 self.rng, desplazar=desplazar)
        previas = ap.leer_csv(ruta)[1] if ruta.exists() else []
        escribir(ruta, previas + filas)

    def alerta(self, ip: str, cuando: datetime):
        ruta = self.cfg["registro_motor"]
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "decision", "decision": "ALERT", "entity_ip": ip,
                                "window_end_utc": cuando.isoformat(), "heuristico": None}) + "\n")

    def cerrar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Politica(unittest.TestCase):
    def test_solo_admite_supervisado(self):
        fallos = ap.comprobar_politica({"modo": "automatico"})
        self.assertTrue(any("supervisado" in f for f in fallos))

    def test_fracciones_fuera_de_rango(self):
        self.assertTrue(ap.comprobar_politica({"max_fraccion_nueva": 1.5}))
        self.assertEqual(ap.comprobar_politica({}), [])

    def test_la_deriva_avisa_antes_de_rechazar(self):
        self.assertTrue(ap.comprobar_politica({"psi_alerta": 0.6, "psi_rechazo_lote": 0.5}))

    def test_la_politica_publicada_es_valida(self):
        import tomllib
        cfg = tomllib.loads((REPO / "configs" / "cyberflow.toml").read_text(encoding="utf-8"))
        self.assertEqual(ap.comprobar_politica(cfg["reentrenamiento"]), [])
        self.assertFalse(cfg["reentrenamiento"]["activo"])


class Unidades(unittest.TestCase):
    def test_timer_solo_si_activo(self):
        import cyberflow_config as cc
        cfg = cc.cargar(REPO / "configs" / "cyberflow.toml")
        self.assertNotIn("cyberflow-aprendizaje.timer", cc.render(cfg))
        cfg["reentrenamiento"]["activo"] = True
        u = cc.render(cfg)
        self.assertIn("cyberflow-aprendizaje.timer", u)
        self.assertIn("--config /home/m4rk/cyberflow/configs/cyberflow.toml diario",
                      u["cyberflow-aprendizaje.service"])
        self.assertIn("Nice=19", u["cyberflow-aprendizaje.service"])


class Piezas(unittest.TestCase):
    def test_psi(self):
        rng = np.random.default_rng(1)
        a = list(rng.normal(size=4000))
        self.assertLess(ap.psi(a, list(rng.normal(size=4000))), 0.05)
        self.assertGreater(ap.psi(a, list(rng.normal(loc=2, size=4000))), 0.5)

    def test_limite_de_influencia(self):
        nuevas = [{"entity_ip": "a", "window_end_utc": "2026-10-01T00:%02d:00" % (i % 60)}
                  for i in range(900)]
        nuevas += [{"entity_ip": ip, "window_end_utc": "2026-10-01T01:00:00"}
                   for ip in "bcdefghij" for _ in range(10)]
        recorte, info = ap.limitar_influencia(nuevas, n_base=700, f_nueva=0.3, f_ip=0.1)
        por_ip = {}
        for r in recorte:
            por_ip[r["entity_ip"]] = por_ip.get(r["entity_ip"], 0) + 1
        self.assertLessEqual(por_ip["a"], info["tope_por_ip"])
        self.assertIn("a", info["ips_recortadas"])
        self.assertLessEqual(len(recorte), int(0.3 / 0.7 * 700))

    def test_fijar_toml_cambia_y_anade_sin_tocar_lo_demas(self):
        t = "# hola\n[motor]\nmodo = \"observacion\"\numbral = 1.0\n\n[rutas]\nmodelo = \"a\"\n"
        t2 = ap.fijar_toml(t, "rutas", "modelo", '"b"')
        t2 = ap.fijar_toml(t2, "motor", "detector", '"x"')
        self.assertIn('modelo = "b"', t2)
        self.assertIn('umbral = 1.0\ndetector = "x"\n', t2)
        self.assertTrue(t2.startswith("# hola\n"))


class CicloCompleto(unittest.TestCase):
    """Un solo escenario para todo: entrenar es lo caro."""

    @classmethod
    def setUpClass(cls):
        cls.e = Escenario()

    @classmethod
    def tearDownClass(cls):
        cls.e.cerrar()

    def test_1_saneamiento_quita_lo_marcado_y_lo_atipico(self):
        e = self.e
        d = date(2026, 10, 1)
        e.dia(d)
        # Una IP alertada a mediodia: sus ventanas a +-5 min no deben entrar.
        e.alerta(IPS[0], datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc))
        # Una fila atipica en todas las variables.
        filas = ap.leer_csv(e.cfg["dataset"])[1]
        for n in NOMBRES:
            filas[10][n] = "9999"
        escribir(e.cfg["dataset"], filas)

        r = ap.cerrar_lote(e.cfg, d)
        self.assertEqual(r["estado"], "aceptado")
        self.assertEqual(r["filas"]["contaminadas"], 3)        # 11:55, 12:00, 12:05
        self.assertEqual(r["filas"]["atipicas"], 1)
        self.assertEqual(r["ips_marcadas"], [IPS[0]])
        lote = ap.leer_csv(e.cfg["dir"] / "lotes" / r["fichero"])[1]
        self.assertFalse(any(f["entity_ip"] == IPS[0] and "T12:00" in f["window_end_utc"]
                             for f in lote))
        # Idempotente: el mismo dia no se registra dos veces.
        self.assertEqual(ap.cerrar_lote(e.cfg, d)["estado"], "ya_registrado")

    def test_2_un_lote_desplazado_se_rechaza(self):
        e = self.e
        d = date(2026, 10, 2)
        e.dia(d, desplazar=2.0)
        r = ap.cerrar_lote(e.cfg, d)
        self.assertEqual(r["estado"], "rechazado")
        self.assertGreater(r["psi_max"], 0.5)

    def test_3_deriva_contra_el_oro(self):
        e = self.e
        r = ap.medir_deriva(e.cfg, date(2026, 10, 1))
        self.assertIsNotNone(r["fpr_oro"])
        self.assertFalse(r["senal"])
        r2 = ap.medir_deriva(e.cfg, date(2026, 10, 2))      # el dia desplazado
        self.assertTrue(r2["senal"])
        self.assertEqual(ap.medir_deriva(e.cfg, date(2026, 10, 2))["estado"], "ya_medida")

    def test_4_candidato_promover_revertir(self):
        e = self.e
        self.assertEqual(ap.generar_candidato(e.cfg, date(2026, 10, 3))["estado"], "no_toca")
        r = ap.generar_candidato(e.cfg, date(2026, 10, 3), forzar=True)
        self.assertEqual(r["estado"], "pocos_datos")         # 1 lote util de 3
        for d in (date(2026, 10, 3), date(2026, 10, 4)):
            e.dia(d)
            self.assertEqual(ap.cerrar_lote(e.cfg, d)["estado"], "aceptado")

        ficha = ap.generar_candidato(e.cfg, date(2026, 10, 5), forzar=True)
        self.assertEqual(ficha["veredicto"], "PROMOVIBLE", ficha.get("razon"))
        self.assertEqual(len(ficha["linaje"]["lotes"]), 3)   # el rechazado no entra
        self.assertLessEqual(ficha["filas"]["fraccion_nueva"], 0.30 + 1e-6)
        self.assertGreater(ficha["resultados"]["candidato"]["deteccion"], 0.9)

        antes = e.toml.read_text(encoding="utf-8")
        p = ap.promover_candidato(e.cfg, ficha["id"])
        despues = e.toml.read_text(encoding="utf-8")
        self.assertIn('detector = "%s"' % ficha["detector"], despues)
        self.assertIn("candidatos/%s/modelo.joblib" % ficha["id"], despues)
        self.assertTrue(any("--escribir" in o for o in p["aplicar"]))
        # Los lotes usados ya no cuentan para el siguiente candidato.
        self.assertEqual(ap.lotes_para_entrenar(ap.cargar_config(e.toml)), [])

        r = ap.revertir(ap.cargar_config(e.toml))
        self.assertEqual(r["vuelve_a"], "if_vigente")
        self.assertEqual(e.toml.read_text(encoding="utf-8"), antes)

        estado = ap.estado(ap.cargar_config(e.toml))
        self.assertTrue(estado["registro_integro"])
        self.assertEqual(estado["candidatos"][-1]["veredicto"], "PROMOVIBLE")
        self.assertEqual([h["accion"] for h in estado["historial"]], ["promover", "revertir"])

    def test_5_no_se_promueve_lo_que_no_paso(self):
        e = self.e
        carpeta = next((e.cfg["dir"] / "candidatos").iterdir())
        ficha = json.loads((carpeta / "candidato.json").read_text(encoding="utf-8"))
        ficha["veredicto"] = "NO_PROMOVER"
        copia = carpeta.parent / "falso"
        shutil.copytree(carpeta, copia)
        (copia / "candidato.json").write_text(json.dumps(ficha), encoding="utf-8")
        with self.assertRaises(SystemExit):
            ap.promover_candidato(e.cfg, "falso")
        shutil.rmtree(copia)

    def test_6_linaje_detecta_un_lote_retocado(self):
        e = self.e
        self.assertEqual(ap.verificar_registro(e.cfg), [])
        lote = e.cfg["dir"] / "lotes" / "lote-20261001.csv"
        original = lote.read_bytes()
        lote.write_bytes(original + b"\n")
        try:
            fallos = ap.verificar_registro(e.cfg)
            self.assertTrue(any("cambio" in f for f in fallos))
            self.assertEqual(ap.generar_candidato(e.cfg, date(2026, 10, 9), True)["estado"],
                             "registro_roto")
        finally:
            lote.write_bytes(original)
        registro = e.cfg["dir"] / "registro.jsonl"
        lineas = registro.read_text(encoding="utf-8").splitlines(keepends=True)
        registro.write_text("".join(lineas[:1] + lineas[2:]), encoding="utf-8")
        try:
            self.assertTrue(any("cadena" in f for f in ap.verificar_registro(e.cfg)))
        finally:
            registro.write_text("".join(lineas), encoding="utf-8")

    def test_8_el_panel_lo_lee(self):
        sys.path.insert(0, str(REPO / "scripts" / "engine"))
        import dashboard
        self.assertFalse(dashboard.estado_aprendizaje(None)["disponible"])
        e = dashboard.estado_aprendizaje(self.e.toml)
        self.assertTrue(e["disponible"], e.get("motivo"))
        self.assertEqual(e["toml"], "cyberflow.local.toml")
        self.assertIn("/api/aprendizaje", dashboard.RUTAS_ADMIN)
        json.dumps(e)                                   # serializable tal cual

    def test_7_el_oro_no_se_rehace(self):
        with self.assertRaises(SystemExit):
            ap.crear_oro(self.e.cfg, self.e.tmp / "artifacts/linea-base/particionado.csv")


if __name__ == "__main__":
    unittest.main()
