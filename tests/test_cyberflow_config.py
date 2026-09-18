"""Tests del generador de unidades scripts/setup/cyberflow_config.py.

Cada caso corresponde a un fallo que ocurrio de verdad en un despliegue o que
se habria producido sin la validacion correspondiente.
"""
from __future__ import annotations

import copy
import importlib.util
import tomllib
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "cyberflow_config", RAIZ / "scripts" / "setup" / "cyberflow_config.py")
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

with (RAIZ / "configs" / "cyberflow.toml").open("rb") as _fh:
    BASE = tomllib.load(_fh)


def cfg(**cambios):
    """Copia de la configuracion publicada con cambios 'seccion.clave'."""
    c = copy.deepcopy(BASE)
    for ruta, valor in cambios.items():
        seccion, clave = ruta.split("__")
        c[seccion][clave] = valor
    # las rutas absolutas del sensor no existen en la maquina del test
    c["rutas"]["raiz"] = "/no/existe/cyberflow"
    return c


class ConfiguracionPublicada(unittest.TestCase):
    def test_la_configuracion_de_ejemplo_es_valida(self):
        self.assertEqual(cc.comprobar(cfg()), [])


class Validaciones(unittest.TestCase):
    def fallos(self, **cambios):
        return " | ".join(cc.comprobar(cfg(**cambios)))

    def test_red_invalida(self):
        self.assertIn("red_entidades", self.fallos(red__red_entidades="10.10.0.0/33"))

    def test_exclusion_invalida(self):
        self.assertIn("excluir", self.fallos(red__excluir=["no-es-una-red"]))

    def test_modo_inexistente(self):
        self.assertIn("modo", self.fallos(motor__modo="pasivo"))

    def test_historia_mayor_que_el_anillo(self):
        # 16 x 15 = 240 s: pedir 240 o mas es pedir historia que ya roto.
        self.assertIn("historia_segundos", self.fallos(motor__historia_segundos=240))
        self.assertEqual(self.fallos(motor__historia_segundos=239), "")

    def test_filtro_bpf_sin_vlan(self):
        # Sobre tramas 802.1Q, "ip and ..." no casa con nada y el anillo se
        # queda vacio sin ningun error. Es el fallo mas silencioso del sistema.
        self.assertIn("vlan", self.fallos(captura__filtro_bpf="ip and host 10.10.60.10"))
        self.assertEqual(self.fallos(captura__filtro_bpf="vlan and ip and host 10.10.60.10"), "")

    def test_filtro_vacio_es_valido(self):
        self.assertEqual(self.fallos(captura__filtro_bpf=""), "")


class Generacion(unittest.TestCase):
    def test_unidades_basicas(self):
        u = cc.render(cfg(panel__activo=False))
        self.assertEqual(set(u), {"cyberflow-capture-nic.service",
                                  "ppi-motor-capture.service", "ppi-motor.service"})

    def test_panel_solo_si_activo(self):
        self.assertIn("ppi-dashboard.service", cc.render(cfg(panel__activo=True)))
        self.assertNotIn("ppi-dashboard.service", cc.render(cfg(panel__activo=False)))

    def test_observacion_no_bloquea_y_se_endurece(self):
        m = cc.render(cfg(motor__modo="observacion"))["ppi-motor.service"]
        self.assertNotIn("--enforce", m)
        self.assertIn("NoNewPrivileges=true", m)

    def test_bloqueo_anade_enforce(self):
        m = cc.render(cfg(motor__modo="bloqueo"))["ppi-motor.service"]
        self.assertIn("--enforce --block-timeout-seconds 120", m)
        # sudo necesita escalar al ayudante: con true fallaria en silencio
        self.assertIn("NoNewPrivileges=false", m)

    def test_sin_barras_de_windows(self):
        # Path().parent en Windows genero "\var\log\suricata": unidad invalida.
        for texto in cc.render(cfg()).values():
            self.assertNotIn("\\var", texto)
            self.assertNotIn("\\home", texto)

    def test_nada_cableado_al_laboratorio_anterior(self):
        for texto in cc.render(cfg(panel__activo=True)).values():
            for resto in ("useransible", "ens35", "10.20.0.0", "10.30.0.0"):
                self.assertNotIn(resto, texto)

    def test_el_panel_recibe_el_manifiesto(self):
        # Sin --manifest-path el panel buscaba /home/useransible/... y moria.
        p = cc.render(cfg(panel__activo=True))["ppi-dashboard.service"]
        self.assertIn("--manifest-path /no/existe/cyberflow/artifacts/model/manifest.json", p)

    def test_filtro_bpf_llega_a_tcpdump(self):
        c = cc.render(cfg(captura__filtro_bpf="vlan and ip"))["ppi-motor-capture.service"]
        self.assertIn("vlan and ip", c)

    def test_la_interfaz_llega_a_todas_las_unidades(self):
        u = cc.render(cfg(captura__interfaz="ens99"))
        self.assertIn("ens99", u["cyberflow-capture-nic.service"])
        self.assertIn("-i ens99", u["ppi-motor-capture.service"])


if __name__ == "__main__":
    unittest.main()
