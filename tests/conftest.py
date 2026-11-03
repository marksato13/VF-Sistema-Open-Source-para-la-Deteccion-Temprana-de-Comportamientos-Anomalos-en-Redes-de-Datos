"""Pruebas que fijan la política de la DEMO (3-nov: A+C, icmp_flood, ráfaga web).

El 3-nov por la noche el sensor volvió al motor de las campañas: el modelo solo
actúa (publicar_feed.MODELO_SOLO_ACTUA = True) y heuristicos.py está en la
versión 2026-10-06.2. Estas pruebas describen la otra política, así que se saltan
mientras rija la de las campañas, y vuelven a correr solas si se reactiva la demo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "engine"))

try:
    import publicar_feed as _pf
    import heuristicos as _h
    _CAMPANAS = bool(_pf.MODELO_SOLO_ACTUA) and _h.VERSION_UMBRALES == "2026-10-06.2"
except Exception:  # pragma: no cover - sin los módulos no se decide nada
    _CAMPANAS = False

_DE_LA_DEMO = {
    "tests/test_publicar_feed.py::DecisionesAEntradas::test_alerta_marginal_del_modelo_no_se_publica",
    "tests/test_publicar_feed.py::DecisionesAEntradas::test_alerta_suelta_del_modelo_no_se_publica",
    "tests/test_publicar_feed.py::DecisionesAEntradas::test_dos_ventanas_claras_no_bastan",
    "tests/test_publicar_feed.py::DecisionesAEntradas::test_politica_a_el_modelo_solo_no_publica",
    "tests/test_heuristico_icmp.py::IcmpFlood::test_el_flood_de_la_demo_bloquea",
    "tests/test_heuristico_icmp.py::IcmpFlood::test_version_subida",
    "tests/test_port_scan_rafaga_web.py::PortScan::test_250_descargas_al_puerto_80_no_son_escaneo",
    "tests/test_port_scan_rafaga_web.py::PortScan::test_cliente_a_una_peticion_por_segundo_no_es_abuso",
    "tests/test_port_scan_rafaga_web.py::PortScan::test_flood_de_la_demo_sigue_siendo_abuso",
    "tests/test_alertas_panel.py::ReglaDeAccion::test_anomalia_del_modelo_solo_queda_para_revision",
    "tests/test_alertas_panel.py::AccionesVigentes::test_contadores_por_accion",
    "tests/test_alertas_panel.py::Simulador::test_cada_ataque_produce_la_accion_del_motor_de_reglas",
    "tests/test_escenario_vivo.py::Marginal::test_borde_del_umbral_es_marginal",
    "tests/test_escenario_vivo.py::Marginal::test_contadores_separan_relevantes",
    "tests/test_historial_acciones.py::Historial::test_una_alerta_suelta_del_modelo_no_es_episodio",
    "tests/test_historial_acciones.py::Historial::test_una_racha_es_un_episodio_y_gana_la_accion_mas_severa",
}


def pytest_collection_modifyitems(config, items):
    if not _CAMPANAS:
        return
    marca = pytest.mark.skip(reason="política de la demo (A+C); rige el motor de las campañas")
    for it in items:
        if it.nodeid.replace("\\", "/") in _DE_LA_DEMO:
            it.add_marker(marca)
