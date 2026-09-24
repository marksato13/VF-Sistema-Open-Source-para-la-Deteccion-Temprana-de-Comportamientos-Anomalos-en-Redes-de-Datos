"""Las unidades del laboratorio: seis perfiles, seis entidades distintas."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUTA = REPO / "scripts/laboratorio/clientes_config.py"
SPEC = importlib.util.spec_from_file_location("clientes_config", RUTA)
assert SPEC and SPEC.loader
cc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cc
SPEC.loader.exec_module(cc)


def args(**cambios):
    base = dict(base="10.10.20.21", servidor="10.10.30.10", dns="10.10.10.20",
                usuario="adminclientes", raiz="/home/adminclientes/laboratorio",
                python="/usr/bin/python3", destino="/etc/systemd/system")
    base.update(cambios)
    return argparse.Namespace(**base)


class Generacion(unittest.TestCase):
    def test_seis_servicios_y_un_target(self):
        u = cc.render(args())
        self.assertEqual(len(u), 7)
        self.assertIn("cyberflow-lab.target", u)
        for perfil in cc.PERFILES:
            self.assertIn("cyberflow-lab-%s.service" % perfil, u)

    def test_cada_perfil_tiene_su_propio_alias(self):
        # Es la razon de ser del montaje: el motor puntua por IP, asi que dos
        # perfiles con el mismo origen serian UNA entidad con la suma de los
        # dos comportamientos, y el modelo aprenderia algo que no existe.
        u = cc.render(args())
        origenes = {}
        for perfil in cc.PERFILES:
            texto = u["cyberflow-lab-%s.service" % perfil]
            m = re.search(r"--origen (\S+)", texto)
            assert m, "el perfil %s no declara --origen" % perfil
            origenes[perfil] = m.group(1)
        self.assertEqual(len(set(origenes.values())), len(cc.PERFILES))
        self.assertEqual(origenes["ofimatica"], "10.10.20.21")
        self.assertEqual(origenes["erratico"], "10.10.20.26")

    def test_la_base_se_puede_mover(self):
        u = cc.render(args(base="10.10.20.100"))
        self.assertIn("--origen 10.10.20.100", u["cyberflow-lab-ofimatica.service"])
        self.assertIn("--origen 10.10.20.105", u["cyberflow-lab-erratico.service"])

    def test_el_target_los_agrupa(self):
        u = cc.render(args())
        for perfil in cc.PERFILES:
            texto = u["cyberflow-lab-%s.service" % perfil]
            self.assertIn("PartOf=cyberflow-lab.target", texto)
            self.assertIn("WantedBy=cyberflow-lab.target", texto)

    def test_el_target_nombra_los_seis_servicios(self):
        # El WantedBy= de cada servicio solo crea el enlace en .wants/ cuando
        # el servicio se habilita. Sin este Wants= explicito en el target,
        # "systemctl start cyberflow-lab.target" arranca el target con NADA
        # colgando: queda active, los seis perfiles parados y ningun error.
        # Ocurrio de verdad la primera vez que se arranco.
        objetivo = cc.render(args())["cyberflow-lab.target"]
        linea = next(l for l in objetivo.splitlines() if l.startswith("Wants="))
        for perfil in cc.PERFILES:
            self.assertIn("cyberflow-lab-%s.service" % perfil, linea)

    def test_la_salida_estandar_se_descarta(self):
        # 1,9 acciones/s durante 72 h son ~272.000 lineas. El journal no es
        # donde se analiza esto: el analisis sale del espejo.
        texto = cc.render(args())["cyberflow-lab-ligero.service"]
        self.assertIn("StandardOutput=null", texto)
        self.assertIn("StandardError=journal", texto)

    def test_no_corre_como_root(self):
        texto = cc.render(args())["cyberflow-lab-descargas.service"]
        self.assertIn("User=adminclientes", texto)
        self.assertIn("NoNewPrivileges=true", texto)

    def test_sin_barras_de_windows(self):
        # El generador puede ejecutarse en Windows; una ruta con "\" produce
        # una unidad invalida que systemd acepta y luego no arranca.
        for texto in cc.render(args()).values():
            self.assertNotIn("\\home", texto)
            self.assertNotIn("\\usr", texto)


class Validaciones(unittest.TestCase):
    def test_base_invalida(self):
        fallos = cc.comprobar(args(base="no-es-una-ip"))
        self.assertTrue(any("--base" in f for f in fallos))

    def test_servidor_invalido(self):
        fallos = cc.comprobar(args(servidor="srv-dmz"))
        self.assertTrue(any("--servidor" in f for f in fallos))

    def test_avisa_si_falta_el_guion(self):
        fallos = cc.comprobar(args(raiz="/ruta/que/no/existe"))
        self.assertTrue(any("clientes_lab.py" in f for f in fallos))


if __name__ == "__main__":
    unittest.main()
