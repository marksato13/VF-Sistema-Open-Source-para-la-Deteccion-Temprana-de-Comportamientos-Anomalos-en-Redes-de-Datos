import os
import shutil
import tempfile
import unittest

from scripts.engine import feed
from scripts.enforce import agente_enforce as ag

TIENE_OPENSSL = shutil.which("openssl") is not None


def feed_con(entradas, ahora=1000.0):
    return feed.construir(entradas, ahora=ahora)


class Vigentes(unittest.TestCase):
    def test_descarta_caducadas(self):
        f = {"entradas": [{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 900}]}
        self.assertEqual(ag.vigentes(f, ahora=1000.0, nunca=set()), {})

    def test_mantiene_vigentes(self):
        f = {"entradas": [{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 1300}]}
        v = ag.vigentes(f, ahora=1000.0, nunca=set())
        self.assertEqual(v["10.10.20.30"]["accion"], "BLOCK")

    def test_salta_nunca_bloquear(self):
        f = {"entradas": [{"ip": "10.10.60.1", "accion": "BLOCK", "hasta": 1300}]}
        self.assertEqual(ag.vigentes(f, 1000.0, {"10.10.60.1"}), {})

    def test_gana_el_mas_severo_por_ip(self):
        f = {"entradas": [
            {"ip": "10.10.20.30", "accion": "LIMIT", "hasta": 1300},
            {"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 1300}]}
        v = ag.vigentes(f, 1000.0, set())
        self.assertEqual(v["10.10.20.30"]["accion"], "BLOCK")


class PlanNftables(unittest.TestCase):
    def test_crea_sets_sin_vaciarlos(self):
        cmds = ag.plan_nftables({}, ahora=1000.0)
        texto = " ".join(" ".join(c) for c in cmds)
        self.assertIn("add table inet cyberflow", texto)
        self.assertIn(ag.SET_BLOCK, texto)
        self.assertNotIn("flush set inet cyberflow " + ag.SET_BLOCK, texto)
        self.assertNotIn("flush set inet cyberflow " + ag.SET_LIMIT, texto)

    def test_hay_cadena_hook_input_y_reglas_de_drop(self):
        texto = " ".join(" ".join(c) for c in ag.plan_nftables({}, ahora=1000.0))
        self.assertIn("chain inet cyberflow entrada", texto)
        self.assertIn("hook input", texto)
        self.assertIn("policy accept;", texto)   # solo cae lo que esté en los sets
        self.assertIn("saddr @" + ag.SET_BLOCK + " drop", texto)
        self.assertIn("saddr @" + ag.SET_LIMIT + " limit rate over", texto)

    def test_block_va_al_set_con_timeout(self):
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1300}}
        cmds = ag.plan_nftables(vig, ahora=1000.0)
        texto = " ".join(" ".join(c) for c in cmds)
        self.assertIn("10.10.20.30 timeout 300s", texto)
        self.assertIn("element inet cyberflow " + ag.SET_BLOCK, texto)

    def test_limit_va_a_su_set(self):
        vig = {"10.10.20.9": {"accion": "LIMIT", "hasta": 1200}}
        cmds = ag.plan_nftables(vig, ahora=1000.0)
        texto = " ".join(" ".join(c) for c in cmds)
        self.assertIn("element inet cyberflow " + ag.SET_LIMIT, texto)
        self.assertIn("10.10.20.9 timeout 200s", texto)

    def test_reincidencia_amplia_timeout_existente(self):
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 2900}}
        actuales = {ag.SET_BLOCK: {"10.10.20.30": 1300}, ag.SET_LIMIT: {}}
        texto = " ".join(" ".join(c) for c in ag.plan_nftables(
            vig, ahora=1100, actuales=actuales))
        self.assertIn("delete element inet cyberflow " + ag.SET_BLOCK, texto)
        self.assertIn("10.10.20.30 timeout 1800s", texto)

    def test_republicacion_no_acorta_timeout_existente(self):
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1300}}
        actuales = {ag.SET_BLOCK: {"10.10.20.30": 1600}, ag.SET_LIMIT: {}}
        texto = " ".join(" ".join(c) for c in ag.plan_nftables(
            vig, ahora=1100, actuales=actuales))
        self.assertNotIn("element inet cyberflow " + ag.SET_BLOCK + " { 10.10.20.30", texto)

    def test_limit_no_revoca_block_vigente(self):
        vig = {"10.10.20.30": {"accion": "LIMIT", "hasta": 1500}}
        actuales = {ag.SET_BLOCK: {"10.10.20.30": 2900}, ag.SET_LIMIT: {}}
        texto = " ".join(" ".join(c) for c in ag.plan_nftables(
            vig, ahora=1100, actuales=actuales))
        self.assertNotIn("10.10.20.30", texto)

    def test_lote_es_una_transaccion_sin_comandos_shell(self):
        lote = ag._lote_nft(ag.plan_nftables({}, ahora=1000.0))
        self.assertIn("flush chain inet cyberflow entrada\n", lote)
        self.assertNotIn("sudo", lote)


class AlcanceYLiberacion(unittest.TestCase):
    VIG = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1300, "nivel": 0},
           "10.10.50.51": {"accion": "LIMIT", "hasta": 1300, "nivel": 0},
           "10.10.20.24": {"accion": "LIMIT", "hasta": 1300, "nivel": 0}}

    def test_sin_alcance_se_aplica_todo(self):
        aplicar, sombra = ag.filtrar_alcance(self.VIG, None, None)
        self.assertEqual(set(aplicar), set(self.VIG))
        self.assertEqual(sombra, {})

    def test_nunca_por_red(self):
        aplicar, sombra = ag.filtrar_alcance(self.VIG, {"nunca": ["10.10.50.0/24"]}, None)
        self.assertNotIn("10.10.50.51", aplicar)
        self.assertEqual(sombra["10.10.50.51"], "nunca")

    def test_solo_deja_el_resto_en_sombra(self):
        aplicar, sombra = ag.filtrar_alcance(self.VIG, {"solo": ["10.10.20.30"]}, None)
        self.assertEqual(list(aplicar), ["10.10.20.30"])
        self.assertEqual(sombra["10.10.20.24"], "fuera-de-alcance")

    def test_nunca_gana_a_solo(self):
        aplicar, _ = ag.filtrar_alcance(self.VIG, {"solo": ["10.10.0.0/16"], "nunca": ["10.10.20.30/32"]}, None)
        self.assertNotIn("10.10.20.30", aplicar)

    LIB = {"10.10.20.30": {"nivel": 0, "hasta": 1300}}

    def test_liberada_no_se_reaplica_si_es_la_misma_orden(self):
        aplicar, sombra = ag.filtrar_alcance(self.VIG, None, self.LIB)
        self.assertNotIn("10.10.20.30", aplicar)
        self.assertEqual(sombra["10.10.20.30"], "liberada")

    def test_republicacion_dentro_del_margen_sigue_liberada(self):
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1310, "nivel": 0}}
        aplicar, _ = ag.filtrar_alcance(vig, None, self.LIB)
        self.assertNotIn("10.10.20.30", aplicar)

    def test_reincidencia_de_nivel_vuelve_a_aplicar(self):
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1300, "nivel": 1}}
        aplicar, _ = ag.filtrar_alcance(vig, None, self.LIB)
        self.assertIn("10.10.20.30", aplicar)
        self.assertEqual(ag.depurar_liberadas(self.LIB, vig), {})

    def test_ofensa_nueva_que_renueva_la_orden_vuelve_a_aplicar(self):
        vig = {"10.10.20.30": {"accion": "LIMIT", "hasta": 1600, "nivel": 0}}
        aplicar, _ = ag.filtrar_alcance(vig, None, self.LIB)
        self.assertIn("10.10.20.30", aplicar)

    def test_gracia_absorbe_la_cola_del_mismo_episodio(self):
        lib = {"10.10.20.30": {"nivel": 0, "hasta": 1300, "desde": 1000, "gracia": 120}}
        vig = {"10.10.20.30": {"accion": "LIMIT", "hasta": 1400, "nivel": 0}}   # ventana tardía
        aplicar, sombra = ag.filtrar_alcance(vig, None, lib, ahora=1050)
        self.assertNotIn("10.10.20.30", aplicar)
        self.assertEqual(ag.depurar_liberadas(lib, vig, 1050)["10.10.20.30"]["hasta"], 1400)

    def test_tras_la_gracia_una_ofensa_nueva_vuelve_a_aplicar(self):
        lib = {"10.10.20.30": {"nivel": 0, "hasta": 1400, "desde": 1000, "gracia": 120}}
        vig = {"10.10.20.30": {"accion": "LIMIT", "hasta": 1500, "nivel": 0}}
        aplicar, _ = ag.filtrar_alcance(vig, None, lib, ahora=1200)
        self.assertIn("10.10.20.30", aplicar)

    def test_gracia_no_absorbe_una_escalada_de_nivel(self):
        lib = {"10.10.20.30": {"nivel": 0, "hasta": 1300, "desde": 1000, "gracia": 120}}
        vig = {"10.10.20.30": {"accion": "BLOCK", "hasta": 1300, "nivel": 1}}
        aplicar, _ = ag.filtrar_alcance(vig, None, lib, ahora=1010)
        self.assertIn("10.10.20.30", aplicar)

    def test_liberacion_se_olvida_si_sale_del_feed(self):
        self.assertEqual(ag.depurar_liberadas(self.LIB, {}), {})

    def test_vigentes_lleva_el_nivel(self):
        f = {"entradas": [{"ip": "10.10.20.30", "accion": "BLOCK", "hasta": 1300, "nivel": 2}]}
        self.assertEqual(ag.vigentes(f, 1000.0, set())["10.10.20.30"]["nivel"], 2)

    def test_plan_liberar_toca_los_dos_sets(self):
        texto = " ".join(" ".join(c) for c in ag.plan_liberar("10.10.20.30"))
        self.assertIn(ag.SET_BLOCK + " { 10.10.20.30 }", texto)
        self.assertIn(ag.SET_LIMIT + " { 10.10.20.30 }", texto)


@unittest.skipUnless(TIENE_OPENSSL, "requiere openssl")
class VerificacionFirma(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.priv = os.path.join(self.dir, "priv.pem")
        self.pub = os.path.join(self.dir, "pub.pem")
        feed.generar_claves(self.priv, self.pub)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_firma_valida_devuelve_feed(self):
        datos = feed.serializar(feed_con([{"ip": "10.10.20.30", "accion": "BLOCK",
                                           "hasta": 1300}]))
        firma = feed.firmar(datos, self.priv)
        self.assertIsNotNone(ag.verificar_feed(datos, firma, self.pub))

    def test_firma_invalida_devuelve_none_failsafe(self):
        datos = feed.serializar(feed_con([{"ip": "10.10.20.30", "accion": "BLOCK",
                                           "hasta": 1300}]))
        firma = feed.firmar(datos, self.priv)
        manipulado = datos.replace(b"BLOCK", b"PERMIT")
        self.assertIsNone(ag.verificar_feed(manipulado, firma, self.pub))


if __name__ == "__main__":
    unittest.main()
