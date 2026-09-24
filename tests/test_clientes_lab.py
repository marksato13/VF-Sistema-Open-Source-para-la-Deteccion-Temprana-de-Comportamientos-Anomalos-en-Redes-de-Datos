"""Las dos acciones cuyo exito no es lo que parece."""

from __future__ import annotations

import importlib.util
import socket
import sys
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUTA = REPO / "scripts/laboratorio/clientes_lab.py"
SPEC = importlib.util.spec_from_file_location("clientes_lab", RUTA)
assert SPEC and SPEC.loader
cl = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cl
SPEC.loader.exec_module(cl)


def puerto_libre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class PuertoCerrado(unittest.TestCase):
    """Un RST es el resultado BUSCADO, no un fallo.

    El codigo original hacia ``except OSError: raise``, asi que contaba como
    fallo justo el caso de exito. En 72 h habria sumado miles de fallos
    inexistentes y el recuento de acciones no significaria nada.
    """

    def _cliente(self, puertos):
        c = cl.Cliente.__new__(cl.Cliente)
        c.servidor = "127.0.0.1"
        c.origen = ""
        c.puerto = 80
        c.puerto_https = 443
        c.espera = 2.0
        # Se fija la lista de puertos para no depender del azar del perfil.
        cl.random.choice = lambda _s, _p=puertos: _p[0]
        return c

    def test_un_puerto_cerrado_no_lanza(self):
        libre = puerto_libre()
        c = self._cliente([libre])
        try:
            c.puerto_cerrado()          # no debe lanzar: el RST es el exito
        except Exception as e:           # noqa: BLE001
            self.fail("un puerto cerrado no deberia fallar: %r" % e)

    def test_un_puerto_ABIERTO_si_es_un_fallo(self):
        # Si el puerto responde, la regla de rechazo apunta a otros puertos y
        # la accion no genera el RST que alimenta rst_ratio_10s.
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        puerto = srv.getsockname()[1]
        aceptados = []

        def aceptar():
            try:
                conn, _ = srv.accept()
                aceptados.append(conn)   # se cierra al final, no al salir el hilo
            except OSError:
                pass

        hilo = threading.Thread(target=aceptar, daemon=True)
        hilo.start()
        try:
            c = self._cliente([puerto])
            with self.assertRaises(RuntimeError):
                c.puerto_cerrado()
        finally:
            hilo.join(timeout=2)
            for conn in aceptados:
                conn.close()
            srv.close()


class DestinoDelPing(unittest.TestCase):
    def test_solo_al_servidor_del_laboratorio(self):
        # El cortafuegos bloquea ICMP hacia la VLAN de administracion. Si el
        # ping volviera a alternar con el DNS, la mitad fallaria en silencio.
        texto = RUTA.read_text(encoding="utf-8")
        inicio = texto.index("def ping(")
        cuerpo = texto[inicio:inicio + 1200]
        self.assertIn("destino = self.servidor", cuerpo)
        self.assertNotIn("self.servidor_dns", cuerpo)


if __name__ == "__main__":
    unittest.main()
