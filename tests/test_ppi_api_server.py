from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "configs/server/ppi-api.py"


def load_api_module(log_path: Path):
    """Carga ppi-api.py como módulo aislado con PPI_API_LOG_PATH ya fijado.

    LOG se lee una sola vez al importar (línea 7 de ppi-api.py), por lo que la
    variable de entorno debe existir antes de ejecutar el módulo, no después.
    """
    import os

    previous = os.environ.get("PPI_API_LOG_PATH")
    os.environ["PPI_API_LOG_PATH"] = str(log_path)
    try:
        spec = importlib.util.spec_from_file_location("ppi_api", MODULE_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            os.environ.pop("PPI_API_LOG_PATH", None)
        else:
            os.environ["PPI_API_LOG_PATH"] = previous
    return module


class PpiApiServerTests(unittest.TestCase):
    """Ejerce ppi-api.py localmente, sin privilegios ni /var/log real.

    Bloqueo documentado: en producción LOG es /var/log/ppi-api/auth.jsonl,
    escrito por systemd con User=www-data y ReadWritePaths=/var/log/ppi-api
    (configs/server/ppi-api.service). Un usuario sin privilegios no puede
    crear /var/log/ppi-api. PPI_API_LOG_PATH permite apuntar el log a un
    directorio temporal propio del proceso de prueba sin tocar ese contrato
    de producción (el valor por defecto no cambia si la variable no está
    definida).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        log_path = Path(cls.tempdir.name) / "ppi-api-log" / "auth.jsonl"
        cls.api = load_api_module(log_path)
        cls.log_path = log_path
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.api.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tempdir.cleanup()

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())

    def _log_lines(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]

    def test_health_and_profile_ok_without_recording(self) -> None:
        before = len(self._log_lines())
        status, body = self._request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok", "service": "ppi-api"})
        status, _ = self._request("GET", "/api/profile")
        self.assertEqual(status, 200)
        # Las rutas válidas no deben inflar auth.jsonl (solo se registran fallos).
        self.assertEqual(len(self._log_lines()), before)

    def test_login_success_matches_api_normal_scenario(self) -> None:
        # Mismas credenciales que scripts/f1/run-benign.sh caso api-normal (índice 4).
        status, body = self._request(
            "POST", "/api/login", {"username": "demo", "password": "demo-pass-2026"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["authenticated"])
        last = self._log_lines()[-1]
        self.assertEqual(last["result"], "success")
        self.assertEqual(last["username"], "demo")

    def test_login_failure_matches_api_auth_fail_scenario(self) -> None:
        # Mismas credenciales que scripts/f1/run-benign.sh caso api-auth-fail.
        status, body = self._request(
            "POST", "/api/login", {"username": "demo", "password": "wrong-lab-credential"}
        )
        self.assertEqual(status, 401)
        self.assertFalse(body["authenticated"])
        last = self._log_lines()[-1]
        self.assertEqual(last["result"], "failure")

    def test_put_profile_204_has_no_body(self) -> None:
        # RFC 9110 §15.3.5: 204 No Content no debe llevar cuerpo de mensaje.
        # Un cliente HTTP estricto (como urllib) falla al parsear JSON si el
        # servidor envía un body junto con 204; este caso lo cubre en directo.
        url = f"http://127.0.0.1:{self.port}/api/profile"
        data = json.dumps({"display_name": "lab"}).encode()
        request = urllib.request.Request(
            url, data=data, method="PUT", headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.read(), b"")

    def test_delete_profile_403(self) -> None:
        status, body = self._request("DELETE", "/api/profile")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "forbidden")

    def test_error_endpoint_produces_deterministic_5xx(self) -> None:
        # Sin esta ruta, http_status_5xx_ratio_60s nunca podía ser distinto de
        # cero en ningún escenario del laboratorio (ver hallazgo de revisión).
        status, body = self._request("GET", "/api/error")
        self.assertEqual(status, 500)
        self.assertEqual(body["error"], "internal_error")
        last = self._log_lines()[-1]
        self.assertEqual(last["result"], "server_error")
        self.assertEqual(last["path"], "/api/error")

    def test_unknown_path_is_404_and_recorded(self) -> None:
        status, body = self._request("GET", "/api/does-not-exist")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "not_found")
        last = self._log_lines()[-1]
        self.assertEqual(last["result"], "not_found")

    def test_bad_json_login_is_400(self) -> None:
        url = f"http://127.0.0.1:{self.port}/api/login"
        request = urllib.request.Request(
            url, data=b"{not-json", method="POST", headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(request, timeout=5)
            self.fail("se esperaba HTTPError 400")
        except urllib.error.HTTPError as exc:
            with exc:
                self.assertEqual(exc.code, 400)
        last = self._log_lines()[-1]
        self.assertEqual(last["result"], "bad_request")

    def test_api_normal_rotation_reaches_every_case_at_count_20(self) -> None:
        # Reproduce en Python la rotación de scripts/f1/run-benign.sh (caso
        # api-normal, módulo 6) para confirmar que count=20 (perfil
        # API-NORMAL-20) visita las seis ramas, incluida /api/error.
        expected_paths = {
            0: ("/api/health", 200),
            1: ("/api/profile", 200),
            2: ("/api/profile", 204),
            3: ("/api/profile", 403),
            4: ("/api/login", 200),
            5: ("/api/error", 500),
        }
        seen_indices = {(i - 1) % 6 for i in range(1, 21)}
        self.assertEqual(seen_indices, set(expected_paths))


if __name__ == "__main__":
    unittest.main()
