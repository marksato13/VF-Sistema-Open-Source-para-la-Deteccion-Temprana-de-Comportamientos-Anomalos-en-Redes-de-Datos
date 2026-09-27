"""Autenticacion y separacion de roles del panel.

La propiedad que importa no es "hay un login": es que **el lector no pueda ver
lo del administrador ni pidiendolo a mano**. Ocultar secciones en el navegador
no vale nada -se leen con Ctrl+U o llamando al endpoint-, asi que aqui se
comprueba que el recorte ocurre en el servidor.

La otra mitad es que el login no se pueda rodear: firma, caducidad, atributos
de la cookie y bloqueo por intentos.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dashboard", REPO / "scripts/engine/dashboard.py")
assert SPEC and SPEC.loader
dash = importlib.util.module_from_spec(SPEC)
sys.modules["dashboard"] = dash
SPEC.loader.exec_module(dash)

CLAVE = b"0" * 64
OTRA = b"1" * 64


class Contrasenas(unittest.TestCase):
    def test_verifica_la_correcta_y_rechaza_la_otra(self):
        h = dash.hash_contrasena("una contrasena larga")
        self.assertTrue(dash.verificar_contrasena(h, "una contrasena larga"))
        self.assertFalse(dash.verificar_contrasena(h, "una contrasena larga "))
        self.assertFalse(dash.verificar_contrasena(h, ""))

    def test_la_sal_es_por_cuenta(self):
        # Dos personas con la misma contrasena no comparten hash: si no, una
        # tabla precalculada las rompe a las dos de golpe.
        a = dash.hash_contrasena("la misma de siempre")
        b = dash.hash_contrasena("la misma de siempre")
        self.assertNotEqual(a, b)
        self.assertTrue(dash.verificar_contrasena(a, "la misma de siempre"))
        self.assertTrue(dash.verificar_contrasena(b, "la misma de siempre"))

    def test_un_hash_corrupto_no_revienta(self):
        for basura in ("", "scrypt$", "otro$1$2$3$aa$bb", "scrypt$x$8$1$aa$bb"):
            self.assertFalse(dash.verificar_contrasena(basura, "x"))


class Sesion(unittest.TestCase):
    def cookie(self, usuario="admin", rol="admin", dentro=3600, clave=CLAVE):
        return dash.firmar_sesion(usuario, rol, int(time.time()) + dentro, clave)

    def test_ida_y_vuelta(self):
        s = dash.leer_sesion(self.cookie(), CLAVE)
        self.assertEqual((s["usuario"], s["rol"]), ("admin", "admin"))

    def test_firmada_con_otra_clave_se_rechaza(self):
        self.assertIsNone(dash.leer_sesion(self.cookie(clave=OTRA), CLAVE))

    def test_caducada_se_rechaza_aunque_la_firma_valga(self):
        c = self.cookie(dentro=-1)
        self.assertIsNone(dash.leer_sesion(c, CLAVE))

    def test_no_se_puede_estirar_la_caducidad_ni_cambiar_el_rol(self):
        # La caducidad y el rol van DENTRO de la firma. Reescribir el cuerpo
        # invalida el hmac, asi que el navegador no puede ascenderse solo.
        c = dash.firmar_sesion("lector", "lector", int(time.time()) + 60, CLAVE)
        cuerpo, _, firma = c.rpartition(".")
        crudo = base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)).decode()
        falso = crudo.replace("lector|lector", "lector|admin")
        nuevo = base64.urlsafe_b64encode(falso.encode()).decode().rstrip("=")
        self.assertIsNone(dash.leer_sesion(nuevo + "." + firma, CLAVE))

    def test_basura_no_revienta(self):
        for c in ("", ".", "abc", "a.b", "x" * 200):
            self.assertIsNone(dash.leer_sesion(c, CLAVE))

    def test_un_rol_inventado_se_rechaza(self):
        c = dash.firmar_sesion("x", "superusuario", int(time.time()) + 60, CLAVE)
        self.assertIsNone(dash.leer_sesion(c, CLAVE))


class Bloqueo(unittest.TestCase):
    def test_bloquea_al_quinto_y_no_antes(self):
        c = dash.Cerrojo(maximo=5, minutos=15)
        for i in range(4):
            c.fallo("admin")
            self.assertFalse(c.bloqueado("admin"), "bloqueado al intento %d" % (i + 1))
        c.fallo("admin")
        self.assertTrue(c.bloqueado("admin"))

    def test_un_acierto_limpia_la_cuenta(self):
        c = dash.Cerrojo(maximo=3, minutos=15)
        c.fallo("admin"); c.fallo("admin")
        c.acierto("admin")
        c.fallo("admin")
        self.assertFalse(c.bloqueado("admin"))

    def test_el_bloqueo_expira(self):
        c = dash.Cerrojo(maximo=1, minutos=15)
        ahora = 1000.0
        c.fallo("admin", ahora=ahora)
        self.assertTrue(c.bloqueado("admin", ahora=ahora + 60))
        self.assertFalse(c.bloqueado("admin", ahora=ahora + 16 * 60))

    def test_bloquear_a_uno_no_bloquea_a_otro(self):
        c = dash.Cerrojo(maximo=1, minutos=15)
        c.fallo("admin")
        self.assertTrue(c.bloqueado("admin"))
        self.assertFalse(c.bloqueado("lector"))


class RecorteDelHtml(unittest.TestCase):
    """Lo que el lector no debe ver, no se le envia."""

    DEV = ("s-topologia", "s-variables", "s-modelo", "s-alcance")
    OPERATIVAS = ("s-salud", "s-scores", "s-actividad", "s-bloqueos", "s-decisiones")

    def setUp(self):
        self.admin = dash.html_por_rol(dash.HTML, "admin")
        self.lector = dash.html_por_rol(dash.HTML, "lector")

    def test_el_admin_lo_recibe_todo(self):
        for sec in self.DEV + self.OPERATIVAS:
            self.assertIn('id="%s"' % sec, self.admin, sec)

    def test_el_lector_no_recibe_las_de_desarrollo(self):
        for sec in self.DEV:
            self.assertNotIn('id="%s"' % sec, self.lector, sec)

    def test_el_lector_si_recibe_las_operativas(self):
        for sec in self.OPERATIVAS:
            self.assertIn('id="%s"' % sec, self.lector, sec)

    def test_tampoco_recibe_sus_enlaces_en_la_barra(self):
        for sec in self.DEV:
            self.assertNotIn('data-sec="%s"' % sec, self.lector, sec)

    def test_no_quedan_marcas_sueltas(self):
        for html in (self.admin, self.lector):
            self.assertNotIn(dash.MARCA_INI, html)
            self.assertNotIn(dash.MARCA_FIN, html)

    def test_el_boton_de_modo_es_solo_del_admin(self):
        self.assertIn('id="modoBtn"', self.admin)
        self.assertNotIn('id="modoBtn"', self.lector)


class RutasClasificadas(unittest.TestCase):
    def test_toda_ruta_que_sirve_el_panel_esta_clasificada(self):
        """La prueba que hace que un endpoint nuevo no quede abierto por olvido.

        Se leen las rutas que do_GET despacha de verdad y se exige que cada una
        este en RUTAS_ADMIN o en la lista de operativas de abajo. Anadir un
        endpoint sin decidir quien lo ve hace fallar esto, en vez de publicarlo.
        """
        import re
        fuente = (REPO / "scripts/engine/dashboard.py").read_text(encoding="utf-8")
        cuerpo = fuente.split("def do_GET", 1)[1].split("\n    def ", 1)[0]
        rutas = set(re.findall(r'path == "(/[a-z/-]*)"', cuerpo))

        operativas = {"/", "/login", "/api/status", "/api/decisions",
                      "/api/activity", "/api/score-histogram"}
        sin_clasificar = rutas - dash.RUTAS_ADMIN - operativas
        self.assertEqual(sin_clasificar, set(),
                         "rutas sin decidir quien las ve: %s" % sin_clasificar)
        self.assertTrue(rutas, "no se encontro ninguna ruta: cambio el despacho?")

    def test_variables_es_de_admin(self):
        # Es la que ensena el esquema completo y muestras del dataset.
        self.assertIn("/api/variables", dash.RUTAS_ADMIN)


class LaUnidadDejaEscribirLaAuditoria(unittest.TestCase):
    def test_la_unidad_del_panel_tiene_ReadWritePaths(self):
        """ProtectSystem=strict deja /home en solo lectura.

        El panel nunca escribio nada, asi que nadie lo noto. Con el registro de
        accesos si importa: sin ReadWritePaths la auditoria falla y el panel
        aparenta un rastro que no existe.
        """
        import argparse
        import importlib.util as iu
        ruta = REPO / "scripts/setup/cyberflow_config.py"
        spec = iu.spec_from_file_location("cyberflow_config", ruta)
        cc = iu.module_from_spec(spec)
        sys.modules["cyberflow_config"] = cc
        spec.loader.exec_module(cc)

        cfg = cc.cargar(REPO / "configs/cyberflow.toml")
        unidades = cc.render(cfg)
        panel = unidades["ppi-dashboard.service"]
        self.assertIn("ProtectSystem=strict", panel)
        self.assertIn("ReadWritePaths=", panel)
        self.assertIn("--auditoria", panel)
        # Y que la auditoria caiga DENTRO de la ruta escribible.
        escribible = [l.split("=", 1)[1] for l in panel.splitlines()
                      if l.startswith("ReadWritePaths=")][0]
        aud = [l.strip().split(" ", 1)[1].rstrip(" \\") for l in panel.splitlines()
               if l.strip().startswith("--auditoria ")][0]
        self.assertTrue(aud.startswith(escribible),
                        "la auditoria (%s) cae fuera de %s" % (aud, escribible))


if __name__ == "__main__":
    unittest.main()
