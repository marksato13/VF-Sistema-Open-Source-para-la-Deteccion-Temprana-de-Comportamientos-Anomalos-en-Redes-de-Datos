"""El panel de verdad: TLS, login y la frontera de rol sobre un socket real.

`test_panel_auth.py` valida las piezas -firma, caducidad, recorte del HTML-.
Esto valida el sistema: arranca el servidor, inicia sesion con dos cuentas y
comprueba que el lector recibe 403 al pedir a mano lo del administrador.

Se salta si no hay openssl, porque el certificado hace falta y no se puede
generar con la biblioteca estandar. En el sensor lo hay.
"""

from __future__ import annotations

import base64
import http.client
import importlib.util
import json
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard", REPO / "scripts/engine/dashboard.py")
assert SPEC and SPEC.loader
dash = importlib.util.module_from_spec(SPEC)
sys.modules["dashboard"] = dash
SPEC.loader.exec_module(dash)


def _openssl() -> str | None:
    hallado = shutil.which("openssl")
    if hallado:
        return hallado
    # Windows: Git trae el suyo y no suele estar en el PATH.
    candidato = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")
    return str(candidato) if candidato.exists() else None


OPENSSL = _openssl()
PUERTO = 18791

# El certificado es autofirmado y el nombre es 127.0.0.1: no hay CA que
# validar, y el objetivo de la prueba es la autorizacion, no la cadena de
# confianza. Se verifica la huella en la instalacion, no aqui.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _conectar() -> http.client.HTTPSConnection:
    return http.client.HTTPSConnection("127.0.0.1", PUERTO, context=_CTX, timeout=5)


@unittest.skipUnless(OPENSSL, "hace falta openssl para el certificado")
class PanelConLogin(unittest.TestCase):
    CLAVE_ADMIN = "clave-de-admin-larga"
    CLAVE_LECTOR = "clave-de-lector-larga"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.cert, cls.key = d / "p.crt", d / "p.key"
        subprocess.run(
            [OPENSSL, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-days", "2", "-subj", "/CN=127.0.0.1",
             "-addext", "subjectAltName=IP:127.0.0.1",
             "-keyout", str(cls.key), "-out", str(cls.cert)],
            check=True, capture_output=True)

        usuarios = d / "usuarios.json"
        usuarios.write_text(json.dumps({
            "admin": {"rol": "admin", "hash": dash.hash_contrasena(cls.CLAVE_ADMIN)},
            "lector": {"rol": "lector", "hash": dash.hash_contrasena(cls.CLAVE_LECTOR)},
        }), encoding="utf-8")
        clave = d / "clave"
        clave.write_text("a" * 64, encoding="utf-8")
        cls.auditoria = d / "auditoria.jsonl"

        cls.proc = subprocess.Popen(
            [sys.executable, str(REPO / "scripts/engine/dashboard.py"),
             "--log-path", str(d / "no-existe.log"),
             "--manifest-path", str(REPO / "artifacts/model/manifest.json"),
             "--schema", str(REPO / "configs/features/multilayer-v2.json"),
             "--schema-extra", str(REPO / "configs/features/multilayer-v3.json"),
             "--descripciones", str(REPO / "configs/features/descripciones.json"),
             "--usuarios", str(usuarios), "--clave-sesion", str(clave),
             "--tls-cert", str(cls.cert), "--tls-key", str(cls.key),
             "--auditoria", str(cls.auditoria),
             "--host", "127.0.0.1", "--port", str(PUERTO)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for _ in range(80):
            try:
                c = _conectar()
                c.request("GET", "/login")
                c.getresponse().read()
                return
            except Exception:
                time.sleep(0.25)
        cls.proc.terminate()
        raise AssertionError("el panel no arranco: %s"
                             % (cls.proc.stdout.read() if cls.proc.stdout else ""))

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except Exception:
            cls.proc.kill()
        cls.tmp.cleanup()

    def entrar(self, usuario, contrasena):
        c = _conectar()
        c.request("POST", "/login", "usuario=%s&contrasena=%s" % (usuario, contrasena),
                  {"Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        r.read()
        return r.status, r.getheader("Set-Cookie")

    def pedir(self, ruta, cookie=None):
        c = _conectar()
        cab = {"Cookie": cookie.split(";")[0]} if cookie else {}
        c.request("GET", ruta, headers=cab)
        r = c.getresponse()
        return r.status, r.read()

    # ------------------------------------------------------------------ sin sesion
    def test_sin_cookie_no_se_sirve_nada(self):
        self.assertEqual(self.pedir("/")[0], 401)
        self.assertEqual(self.pedir("/api/variables")[0], 401)
        self.assertEqual(self.pedir("/api/status")[0], 401)

    def test_el_login_si_es_publico(self):
        self.assertEqual(self.pedir("/login")[0], 200)

    def test_contrasena_incorrecta(self):
        self.assertEqual(self.entrar("admin", "no-es-esta")[0], 401)

    # ------------------------------------------------------------------ la cookie
    def test_la_cookie_lleva_los_tres_atributos(self):
        _, ck = self.entrar("admin", self.CLAVE_ADMIN)
        for attr in ("HttpOnly", "Secure", "SameSite=Strict"):
            self.assertIn(attr, ck, attr)

    def test_firma_manipulada(self):
        _, ck = self.entrar("lector", self.CLAVE_LECTOR)
        base = ck.split(";")[0]
        falsa = base[:-1] + ("0" if base[-1] != "0" else "1")
        self.assertEqual(self.pedir("/api/status", falsa)[0], 401)

    def test_no_se_puede_ascender_reescribiendo_el_cuerpo(self):
        # El ataque de verdad: el lector se pone rol admin en su propia cookie.
        _, ck = self.entrar("lector", self.CLAVE_LECTOR)
        valor = ck.split(";")[0].split("=", 1)[1]
        cuerpo, _, firma = valor.rpartition(".")
        crudo = base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)).decode()
        nuevo = base64.urlsafe_b64encode(
            crudo.replace("lector|lector", "lector|admin").encode()).decode().rstrip("=")
        self.assertEqual(
            self.pedir("/api/variables", "cyberflow_sesion=%s.%s" % (nuevo, firma))[0],
            401)

    # ------------------------------------------------------------------ los roles
    def test_la_frontera_de_rol(self):
        _, admin = self.entrar("admin", self.CLAVE_ADMIN)
        _, lector = self.entrar("lector", self.CLAVE_LECTOR)
        self.assertEqual(self.pedir("/api/variables", admin)[0], 200)
        self.assertEqual(self.pedir("/api/variables", lector)[0], 403)

    def test_al_lector_no_le_llega_el_marcado_de_desarrollo(self):
        _, lector = self.entrar("lector", self.CLAVE_LECTOR)
        estado, pagina = self.pedir("/", lector)
        self.assertEqual(estado, 200)
        for sec in (b's-variables', b's-topologia', b's-modelo', b's-alcance'):
            self.assertNotIn(b'id="' + sec + b'"', pagina, sec)
        self.assertIn(b'id="s-decisiones"', pagina)
        self.assertNotIn(b'id="modoBtn"', pagina)

    def test_al_admin_si(self):
        _, admin = self.entrar("admin", self.CLAVE_ADMIN)
        _, pagina = self.pedir("/", admin)
        self.assertIn(b'id="s-variables"', pagina)
        self.assertIn(b'id="modoBtn"', pagina)

    # ------------------------------------------------------------------ auditoria
    def test_queda_rastro_de_todo(self):
        self.entrar("admin", self.CLAVE_ADMIN)
        self.entrar("admin", "mal")
        _, lector = self.entrar("lector", self.CLAVE_LECTOR)
        self.pedir("/api/variables", lector)
        eventos = [json.loads(l) for l in
                   self.auditoria.read_text(encoding="utf-8").splitlines() if l.strip()]
        tipos = {e["tipo"] for e in eventos}
        for esperado in ("entrada", "fallo", "denegado"):
            self.assertIn(esperado, tipos, esperado)


if __name__ == "__main__":
    unittest.main()
