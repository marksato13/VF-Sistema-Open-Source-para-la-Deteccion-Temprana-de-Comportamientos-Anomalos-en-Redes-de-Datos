"""Completitud de fuentes en el motor: una ventana sin sus paquetes en PCAP cerrados no se decide.

Caso real (2026-10-28, Sensor1): el motor decidia ventanas que existian por un evento de eve.json antes
de que tcpdump cerrara el fichero con sus paquetes; las registraba con packet_count_10s=0 y no las
volvia a evaluar. Ademas, al reiniciar, repetia decisiones de ventanas ya registradas.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts" / "engine"))

import motor_decision as motor  # noqa: E402


class VentanaCompleta(unittest.TestCase):
    def test_sin_pcap_cerrado_no_esta_completa(self):
        self.assertFalse(motor.ventana_completa(1000.0, None))

    def test_paquetes_aun_en_el_fichero_activo(self):
        # el ultimo paquete de los ficheros cerrados es anterior al final de la ventana
        self.assertFalse(motor.ventana_completa(1000.0, 999.4))

    def test_cubierta_por_los_cerrados(self):
        self.assertTrue(motor.ventana_completa(1000.0, 1000.0))
        self.assertTrue(motor.ventana_completa(1000.0, 1007.2))


class ClavesYaRegistradas(unittest.TestCase):
    def test_carga_decisiones_y_no_evaluadas_y_omite_lo_demas(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "motor_decision.log"
            lineas = [
                {"event": "motor_startup", "timestamp": 1.0},
                {"event": "decision", "entity_ip": "10.10.20.21", "window_end_utc": "2026-10-28T06:58:40+00:00"},
                {"event": "ventana_no_evaluada", "entity_ip": "10.10.20.22",
                 "window_end_utc": "2026-10-28T06:58:50+00:00", "motivo": "pcap_incompleto"},
            ]
            texto = "\n".join(json.dumps(x) for x in lineas) + "\n{roto\n"
            log.write_text(texto, encoding="utf-8")
            claves = motor.claves_ya_registradas(log)
        self.assertEqual(set(claves), {("10.10.20.21", "2026-10-28T06:58:40+00:00"),
                                       ("10.10.20.22", "2026-10-28T06:58:50+00:00")})

    def test_registro_inexistente(self):
        self.assertEqual(motor.claves_ya_registradas(Path(tempfile.gettempdir()) / "no-existe-cf.log"), {})

    def test_cola_recortada_descarta_la_primera_linea_partida(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "motor_decision.log"
            r = {"event": "decision", "entity_ip": "10.10.20.23", "window_end_utc": "2026-10-28T07:00:00+00:00"}
            log.write_text("\n".join(json.dumps(r) for _ in range(50)) + "\n", encoding="utf-8")
            claves = motor.claves_ya_registradas(log, max_bytes=300)
        self.assertEqual(set(claves), {("10.10.20.23", "2026-10-28T07:00:00+00:00")})


if __name__ == "__main__":
    unittest.main()
