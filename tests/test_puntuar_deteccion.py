"""puntuar_deteccion.py: los dos formatos de modelo y el contrato del informe.

Todo con datos sinteticos en un temporal; no toca ningun artefacto del repo.
El punto central es que un informe de PAQUETE y uno de PIPELINE sobre el MISMO
CSV deciden igual (la escala difiere en offset_, la decision no), y que el
informe lleva los campos que comparar_reentrenamiento.py exige para emparejar.
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "modeling"))

import puntuar_deteccion as pd  # noqa: E402

FEATS = ["f0", "f1", "f2", "f3"]
SCHEMA = {"features": [{"name": n, "order": i} for i, n in enumerate(FEATS)]}


def escribir_csv(ruta: Path, X, label: str | None = None):
    cols = FEATS + (["label"] if label else [])
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for fila in X:
            d = {FEATS[j]: "%.6f" % fila[j] for j in range(len(FEATS))}
            if label:
                d["label"] = label
            w.writerow(d)


class Puntuar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="cf-puntuar-"))
        rng = np.random.default_rng(0)
        xtr = rng.normal(size=(400, 4))
        sc = StandardScaler().fit(xtr)
        m = IsolationForest(n_estimators=80, random_state=0).fit(sc.transform(xtr))
        umbral_df = float(np.quantile(m.decision_function(sc.transform(xtr)), 0.1))

        cls.paq = cls.tmp / "paq.joblib"
        joblib.dump({"modelo": m, "escalador": sc, "umbral": umbral_df,
                     "features": FEATS, "schema": "s.json"}, cls.paq)

        cls.pipe = cls.tmp / "pipe.joblib"
        joblib.dump(Pipeline([("scaler", sc), ("model", m)]), cls.pipe)
        umbral_ss = umbral_df + float(m.offset_)
        cls.manifest = cls.tmp / "manifest.json"
        cls.manifest.write_text(json.dumps({"detectors": {"det": {
            "calibration": {"threshold": umbral_ss, "comparison": "score < threshold"},
            "features": FEATS}}}), encoding="utf-8")
        cls.schema = cls.tmp / "s.json"
        cls.schema.write_text(json.dumps(SCHEMA), encoding="utf-8")

        cls.normal = cls.tmp / "normal.csv"
        escribir_csv(cls.normal, rng.normal(size=(200, 4)))
        cls.anom = cls.tmp / "anom.csv"
        escribir_csv(cls.anom, rng.normal(size=(50, 4)) + 6.0, label="anomaly")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _run(self, args):
        inf = self.tmp / "out.json"
        if inf.exists():
            inf.unlink()
        pd.main(args + ["--informe", str(inf)])
        return json.loads(inf.read_text(encoding="utf-8"))

    def test_paquete_normal_emite_los_campos_del_candado(self):
        r = self._run(["--modelo", str(self.paq), "--csv", str(self.normal),
                       "--tipo", "normal", "--particion", "test"])
        self.assertEqual(r["formato"], "paquete")
        self.assertEqual(r["tipo"], "normal")
        self.assertEqual(r["particion"], "test")
        self.assertEqual(len(r["csv_sha256"]), 64)
        self.assertEqual(r["features"], FEATS)
        self.assertEqual(r["fpr"], r["tasa_deteccion"])

    def test_anomalias_da_tpr_y_filtra_por_etiqueta(self):
        r = self._run(["--modelo", str(self.paq), "--csv", str(self.anom),
                       "--tipo", "anomalias", "--etiqueta", "anomaly"])
        self.assertEqual(r["filas"], 50)
        self.assertIn("tpr", r)
        self.assertGreater(r["tpr"], 0.9)

    def test_pipeline_decide_igual_que_el_paquete(self):
        rp = self._run(["--modelo", str(self.paq), "--csv", str(self.anom),
                        "--tipo", "anomalias", "--etiqueta", "anomaly"])
        rpipe = self._run(["--modelo", str(self.pipe), "--manifest", str(self.manifest),
                           "--detector-name", "det", "--schema", str(self.schema),
                           "--csv", str(self.anom), "--tipo", "anomalias", "--etiqueta", "anomaly"])
        self.assertEqual(rpipe["formato"], "pipeline")
        self.assertEqual(rpipe["detector"], "det")
        self.assertEqual(rpipe["detectadas"], rp["detectadas"])   # misma decision, otra escala
        self.assertEqual(rpipe["features"], rp["features"])

    def test_pipeline_sin_manifiesto_aborta(self):
        with self.assertRaises(SystemExit):
            self._run(["--modelo", str(self.pipe), "--csv", str(self.normal)])

    def test_sha256_que_no_coincide_aborta(self):
        with self.assertRaises(SystemExit):
            self._run(["--modelo", str(self.paq), "--csv", str(self.normal), "--sha256", "0" * 64])

    def test_feature_faltante_aborta(self):
        malo = self.tmp / "malo.csv"
        with malo.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["f0", "f1", "f2"])
            w.writeheader()
            w.writerow({"f0": "1", "f1": "2", "f2": "3"})
        with self.assertRaises(SystemExit):
            self._run(["--modelo", str(self.paq), "--csv", str(malo)])

    def test_valor_no_numerico_aborta_sin_imputar(self):
        malo = self.tmp / "nonum.csv"
        with malo.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FEATS)
            w.writeheader()
            w.writerow({"f0": "1", "f1": "x", "f2": "3", "f3": "4"})
        with self.assertRaises(SystemExit):
            self._run(["--modelo", str(self.paq), "--csv", str(malo)])


if __name__ == "__main__":
    unittest.main()
