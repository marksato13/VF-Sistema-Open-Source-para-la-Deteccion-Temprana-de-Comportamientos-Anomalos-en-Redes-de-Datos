#!/usr/bin/env python3
"""Servidor web del laboratorio: HTTP y HTTPS con errores controlados.

No es parte del producto. Es el aparato experimental: existe para que el
trafico de fondo ejercite las variables de capa 7 que, sin el, quedarian
constantes.

Que alimenta cada endpoint:

    /                    200 -> http_request_rate_60s
    /estatico/<n>k       200 con cuerpo de n KB -> mean_ip_len, large_ip_ratio,
                         byte_rate, tx_rx_byte_ratio
    /api/ok              200 -> linea base de respuestas correctas
    /api/auth            401 -> http_auth_failure_ratio_60s
    /api/perdido         404 -> http_error_ratio_60s
    /api/fallo           500 -> http_status_5xx_ratio_60s
    /api/lento           200 tras una pausa -> flow_duration_mean_30s

Solo biblioteca estandar, igual que el resto del proyecto: la maquina del
laboratorio puede no tener salida a Internet para instalar paquetes.

Uso:
    python3 servidor_lab.py --puerto 80
    python3 servidor_lab.py --puerto 443 --cert /etc/cyberflow-lab/cert.pem \\
                            --clave /etc/cyberflow-lab/clave.pem
"""
from __future__ import annotations

import argparse
import random
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RELLENO = (b"CyberFlow laboratorio. Cuerpo de relleno para dar tamano a la "
           b"respuesta sin depender de ficheros en disco. ")


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "cyberflow-lab"

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str = "text/plain") -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        try:
            self.wfile.write(cuerpo)
        except (BrokenPipeError, ConnectionResetError):
            pass  # el cliente corto: normal cuando se simulan abandonos

    def do_GET(self) -> None:  # noqa: N802
        ruta = self.path.split("?")[0]

        if ruta == "/":
            self._responder(200, b"<html><body><h1>Laboratorio CyberFlow</h1></body></html>",
                            "text/html")
        elif ruta.startswith("/estatico/"):
            # /estatico/64k -> 64 KB. Tamanos variados mueven las variables de
            # tamano de paquete y de proporcion de bytes en los dos sentidos.
            try:
                kb = int(ruta.rsplit("/", 1)[1].rstrip("kK"))
            except ValueError:
                kb = 8
            kb = max(1, min(kb, 4096))
            self._responder(200, (RELLENO * ((kb * 1024) // len(RELLENO) + 1))[:kb * 1024])
        elif ruta == "/api/ok":
            self._responder(200, b'{"estado":"ok"}', "application/json")
        elif ruta == "/api/auth":
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="laboratorio"')
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif ruta == "/api/perdido":
            self._responder(404, b'{"error":"no existe"}', "application/json")
        elif ruta == "/api/fallo":
            self._responder(500, b'{"error":"fallo interno simulado"}', "application/json")
        elif ruta == "/api/lento":
            time.sleep(random.uniform(1.5, 4.0))
            self._responder(200, b'{"estado":"tarde pero llego"}', "application/json")
        else:
            self._responder(404, b'{"error":"ruta desconocida"}', "application/json")

    def do_POST(self) -> None:  # noqa: N802
        # Los POST mueven la entropia de metodos y la proporcion tx/rx.
        longitud = int(self.headers.get("Content-Length", 0) or 0)
        if longitud:
            self.rfile.read(longitud)
        self._responder(201 if random.random() > 0.1 else 500, b'{"recibido":true}',
                        "application/json")

    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass  # silencioso: el registro util es el de Suricata, no este


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--direccion", default="0.0.0.0")
    p.add_argument("--puerto", type=int, default=8080)
    p.add_argument("--cert", help="certificado PEM; si se indica, sirve HTTPS")
    p.add_argument("--clave", help="clave PEM del certificado")
    args = p.parse_args()

    servidor = ThreadingHTTPServer((args.direccion, args.puerto), Manejador)
    esquema = "http"
    if args.cert and args.clave:
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.load_cert_chain(args.cert, args.clave)
        servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
        esquema = "https"
    print("laboratorio: %s://%s:%d/" % (esquema, args.direccion, args.puerto), flush=True)
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
