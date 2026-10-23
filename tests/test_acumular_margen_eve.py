"""Las observaciones de eve.json anteriores al primer paquete no deben entrar.

El acumulador pide la rebanada de eve.json 90 s antes del primer paquete para
no cortar un evento por la mitad, pero del anillo de PCAP no hay nada de esa
franja. Si una de esas observaciones llega a ``build_rows`` pasan dos cosas, y
las dos son malas:

  - ``v2.build_rows`` aborta, porque ``capture_start`` -el primer paquete- seria
    posterior a la primera observacion. Es como dio la cara: el acumulador
    murio a los pocos minutos de arrancar la linea base y dejo de escribir
    durante horas sin que nada mas fallara.
  - Si en vez de filtrar se bajara el ``capture_start`` para acallar el aborto,
    ``history_coverage`` marcaria como elegibles ventanas cuya historia de
    paquetes esta truncada: filas incompletas entrando al entrenamiento sin que
    ninguna metrica lo delate.

Este fichero fija las dos mitades del contrato.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extract_multilayer_v2", REPO / "scripts/features/extract_multilayer_v2.py")
assert SPEC and SPEC.loader
v2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = v2
SPEC.loader.exec_module(v2)

INICIO = 1_800_000_000.0


def paquete(t: float, ip: str = "10.10.20.21") -> object:
    return v2.PacketObservation(
        timestamp=t, entity_ip=ip, peer_ip="10.10.40.10", ip_length=120,
        protocol=6, target_port=443, flow_attempt=False, outbound=True,
        syn=False, syn_ack=False, rst=False, ttl=64, fragmented=False,
        tcp_payload_length=60, retransmission=False,
        flow_id=(ip, "10.10.40.10", 443, 6), flow_duration_so_far=0.0)


def app(t: float, ip: str = "10.10.20.21") -> object:
    return v2.AppObservation(timestamp=t, entity_ip=ip, kind="dns")


class RebanadaDeEve(unittest.TestCase):
    def test_una_app_anterior_al_primer_paquete_aborta_build_rows(self):
        # Contraste explicito: sin el filtro, esto es exactamente lo que
        # mataba al acumulador cada diez minutos.
        paquetes = [paquete(INICIO + i) for i in range(0, 300, 10)]
        apps = [app(INICIO - 90), app(INICIO + 30)]
        with self.assertRaises(ValueError):
            v2.build_rows("prueba", paquetes, apps, capture_start=INICIO)

    def test_filtrando_las_previas_build_rows_funciona(self):
        paquetes = [paquete(INICIO + i) for i in range(0, 300, 10)]
        apps = [a for a in (app(INICIO - 90), app(INICIO + 30))
                if a.timestamp >= INICIO]
        filas = v2.build_rows("prueba", paquetes, apps, capture_start=INICIO)
        self.assertTrue(filas)

    def test_el_capture_start_no_se_baja_para_acallar_el_aborto(self):
        # Si se pasara capture_start = INICIO - 90 el aborto desapareceria,
        # pero las ventanas del primer minuto quedarian marcadas elegibles con
        # la historia de paquetes a medias. Esta prueba fija que el arranque
        # real manda: con capture_start = INICIO, ninguna ventana de los
        # primeros 60 s es elegible.
        paquetes = [paquete(INICIO + i) for i in range(0, 300, 10)]
        filas = v2.build_rows("prueba", paquetes, [], capture_start=INICIO)
        pronto = [f for f in filas
                  if v2.parse_eve_timestamp(str(f["window_end_utc"])) < INICIO + 60]
        self.assertTrue(pronto, "el caso no se esta ejercitando")
        for f in pronto:
            self.assertFalse(f["eligible_training"],
                             "ventana con historia truncada marcada elegible")


if __name__ == "__main__":
    unittest.main()
