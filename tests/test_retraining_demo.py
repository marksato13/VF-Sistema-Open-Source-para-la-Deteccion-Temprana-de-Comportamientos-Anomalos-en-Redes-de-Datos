"""End-to-end dry-run on synthetic data; no sensor, no production model."""

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "configs/features/multilayer-v2.json"
DATASET = ROOT / "scripts/dataset/particionar_linea_base.py"
TRAIN = ROOT / "scripts/modeling/entrenar_preliminar.py"
SCORE = ROOT / "scripts/modeling/puntuar_deteccion.py"
COMPARE = ROOT / "scripts/modeling/comparar_reentrenamiento.py"


class RetrainingDryRun(unittest.TestCase):
    def call(self, *args):
        result = subprocess.run([sys.executable, *map(str, args)], text=True,
                                encoding="utf-8", capture_output=True, timeout=90,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 0, result.stderr + "\n" + result.stdout)
        return result.stdout

    def test_full_cycle_isolated_and_paired(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            features = [f["name"] for f in json.loads(SCHEMA.read_text(encoding="utf-8"))["features"]]
            source, attack = temp / "normal.csv", temp / "attack.csv"
            columns = ["window_end_utc", "entity_ip", "eligible_training", "label", *features]
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            with source.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                for hour in range(6):
                    for n in range(8):
                        row = {"window_end_utc": (start + timedelta(hours=hour, minutes=2 + n)).isoformat(),
                               "entity_ip": "10.10.20.21", "eligible_training": "True", "label": "normal"}
                        row.update({name: str(1 + (hour * 8 + n + i) % 7 / 10) for i, name in enumerate(features)})
                        writer.writerow(row)
            with attack.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                for n in range(8):
                    row = {"window_end_utc": (start + timedelta(days=2, minutes=n)).isoformat(),
                           "entity_ip": "10.10.20.30", "eligible_training": "True", "label": "anomaly"}
                    row.update({name: str(4 + n / 10 + i / 50) for i, name in enumerate(features)})
                    writer.writerow(row)
            split = temp / "partitioned.csv"
            self.call(DATASET, "--entrada", source, "--salida", split,
                      "--informe", temp / "split.json", "--bloque-horas", "1", "--solo-elegibles")
            reports = []
            for label, seed in (("antes", 11), ("despues", 17)):
                model, report = temp / f"{label}.joblib", temp / f"{label}.json"
                self.call(TRAIN, "--entrada", split, "--schema", SCHEMA, "--salida", model,
                          "--informe", report, "--n-estimators", "10", "--semilla", str(seed))
                self.call(SCORE, "--modelo", model, "--csv", split, "--particion", "test",
                          "--tipo", "normal", "--informe", temp / f"fpr-{label}.json")
                self.call(SCORE, "--modelo", model, "--csv", attack, "--tipo", "anomalias",
                          "--informe", temp / f"tpr-{label}.json")
                reports.append(report)
            output = self.call(COMPARE, "--antes", reports[0], "--despues", reports[1],
                               "--fpr-antes", temp / "fpr-antes.json", "--fpr-despues", temp / "fpr-despues.json",
                               "--tpr-antes", temp / "tpr-antes.json", "--tpr-despues", temp / "tpr-despues.json")
            self.assertIn("mismo normal reservado (SHA-256): sí", output)
            self.assertIn("mismos ataques (SHA-256): sí", output)
            self.assertNotIn("EVALUACIÓN INCOMPLETA", output)
            missing = self.call(COMPARE, "--antes", reports[0], "--despues", reports[1])
            self.assertIn("EVALUACIÓN INCOMPLETA — NO PROMOVER", missing)
            changed = json.loads((temp / "tpr-despues.json").read_text(encoding="utf-8"))
            changed["csv_sha256"] = "0" * 64
            (temp / "tpr-despues.json").write_text(json.dumps(changed), encoding="utf-8")
            mismatch = self.call(COMPARE, "--antes", reports[0], "--despues", reports[1],
                                 "--fpr-antes", temp / "fpr-antes.json", "--fpr-despues", temp / "fpr-despues.json",
                                 "--tpr-antes", temp / "tpr-antes.json", "--tpr-despues", temp / "tpr-despues.json")
            self.assertIn("mismos ataques (SHA-256): NO", mismatch)
            self.assertIn("EVALUACIÓN INCOMPLETA — NO PROMOVER", mismatch)

    def test_deployed_pipeline_requires_matching_manifest(self):
        import joblib
        import numpy as np
        from sklearn.ensemble import IsolationForest
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            features = [f["name"] for f in json.loads(SCHEMA.read_text(encoding="utf-8"))["features"]]
            model = temp / "model.joblib"
            pipeline = Pipeline([("scale", StandardScaler()), ("model", IsolationForest(n_estimators=10, random_state=1))])
            pipeline.fit(np.arange(280, dtype=float).reshape(10, 28))
            joblib.dump(pipeline, model)
            digest = hashlib.sha256(model.read_bytes()).hexdigest()
            manifest = temp / "manifest.json"
            manifest.write_text(json.dumps({"detectors": {"active": {
                "model_sha256": digest, "calibration": {"threshold": -0.5}
            }}}), encoding="utf-8")
            csv_path = temp / "normal.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=features)
                writer.writeheader()
                writer.writerow({name: str(i) for i, name in enumerate(features)})
            report = temp / "report.json"
            self.call(SCORE, "--modelo", model, "--manifest", manifest, "--detector-name", "active",
                      "--schema", SCHEMA, "--csv", csv_path, "--tipo", "normal", "--informe", report)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["modelo_tipo"], "pipeline-score_samples")
            manifest.write_text(json.dumps({"detectors": {"active": {
                "model_sha256": "0" * 64, "calibration": {"threshold": -0.5}
            }}}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCORE), "--modelo", str(model), "--manifest", str(manifest),
                                     "--detector-name", "active", "--schema", str(SCHEMA), "--csv", str(csv_path)],
                                    capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256", result.stderr)


if __name__ == "__main__":
    unittest.main()
