"""Checks that the served GUI represents the active detector and protects source files."""

import importlib.util
import json
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dashboard_under_test", REPO / "scripts/engine/dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardGuiContract(unittest.TestCase):
    def test_served_script_parses_and_uses_active_detector(self):
        html = dashboard.html_por_rol(dashboard.HTML, "admin")
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        subprocess.run(["node", "--check", "-"], input=script, text=True, encoding="utf-8",
                       check=True, capture_output=True, timeout=15)
        self.assertIn("DETECTOR_LABEL[m.detector_name]", script)
        self.assertNotIn("card('Detector', 'OCSVM')", script)
        self.assertIn("#topoVista", script)
        self.assertIn("#pruebasPrevias", script)
        self.assertIn("#topoArchivosBtn", script)
        self.assertNotIn("Un One-Class SVM entrenado", script)

    def test_reader_cannot_receive_developer_view(self):
        html = dashboard.html_por_rol(dashboard.HTML, "lector")
        self.assertNotIn('id="topoVista"', html)
        self.assertNotIn('id="pruebasPrevias"', html)
        self.assertIn("/api/archivo", dashboard.RUTAS_ADMIN)

    def test_model_artifact_comes_from_active_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "artifacts/preliminar/manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"detectors": {
                "if_recalibrado_2026_09": {"model_path": "artifacts/preliminar/if_recalibrado_desplegable.joblib"}
            }}), encoding="utf-8")
            model = root / "artifacts/preliminar/if_recalibrado_desplegable.joblib"
            self.assertEqual(dashboard.ruta_modelo_activo(manifest, "if_recalibrado_2026_09", root), model)
            mapping = dashboard.estado_artefactos(root / "eve.json", None, manifest, root / "motor.log",
                                                   None, root / "descripciones.json", raiz=root,
                                                   capture_dir=root / "pcap", detector_name="if_recalibrado_2026_09")
            self.assertEqual(mapping["modelo"][0]["ruta"], str(model))
            self.assertNotIn("ocsvm_scaled.joblib", mapping["modelo"][0]["ruta"])

    def test_served_demo_denies_outside_whitelist_and_serves_allowed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            manifest = temp / "manifest.json"
            manifest.write_text(json.dumps({"evaluation": {"if_recalibrado_2026_09": {
                "threshold_used": -0.568892, "test": {"fpr": 0.0445},
                "anomalies": {"detection_rate": 0.69, "kali_real_detection_rate": 0.69}
            }}}), encoding="utf-8")
            secret = temp / "outside-allowlist.txt"
            secret.write_text("no se debe servir", encoding="utf-8")
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            proc = subprocess.Popen([
                "python", str(REPO / "scripts/engine/dashboard.py"), "--demo",
                "--host", "127.0.0.1", "--port", str(port), "--manifest-path", str(manifest),
                "--detector-name", "if_recalibrado_2026_09", "--log-path", str(temp / "log.jsonl"),
                "--eve-path", str(temp / "eve.json")
            ], cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(40):
                    try:
                        with urllib.request.urlopen(base + "/", timeout=2) as response:
                            page = response.read().decode("utf-8")
                        break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.1)
                else:
                    self.fail("Panel demo no arrancó")
                self.assertIn('id="topoVista"', page)
                self.assertIn("Pruebas previas", page)
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(base + "/api/archivo?ruta=" +
                                           urllib.parse.quote(str(secret)), timeout=2)
                self.assertEqual(rejected.exception.code, 403)
                rejected.exception.close()
                allowed = str(REPO / "scripts/engine/motor_decision.py")
                with urllib.request.urlopen(base + "/api/archivo?ruta=" + urllib.parse.quote(allowed), timeout=2) as response:
                    payload = json.load(response)
                self.assertIn("contenido", payload)
                self.assertIn("Motor de decision", payload["contenido"])
            finally:
                proc.terminate()
                try:
                    proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
