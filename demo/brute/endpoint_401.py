#!/usr/bin/env python3
"""Endpoint HTTP que exige Basic Auth y responde 401 a cada intento fallido.

Sirve para demostrar la detección de FUERZA BRUTA (familia B4): cada login
fallido es un HTTP 401 que Suricata registra desde el espejo SPAN; el heurístico
`brute_force` ve la ráfaga (>=5 req/60s con >=80% de fallo de auth) y el motor
emite BLOCK contra la entidad atacante.

HTTP EN CLARO a propósito: el sensor observa por espejo (pasivo) y Suricata solo
puede leer el `status` si el tráfico NO va cifrado. No le pongas TLS.

Credenciales: NO maneja ninguna real. Por defecto NINGÚN usuario/clave es válido
(todo es 401), así que no hay secreto que guardar. Si quieres un momento de
"login correcto" en la demo, exporta DEMO_OK_USER y DEMO_OK_PASS antes de
arrancar (valores de laboratorio, nunca credenciales reales).

Uso en el host DMZ (10.10.30.10):
    python3 endpoint_401.py --port 8081
No necesita sudo (puerto alto). Si el cortafuegos del host no deja entrar al
puerto, ábrelo o usa uno ya permitido con --port.
"""
from __future__ import annotations

import argparse
import base64
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REALM = "CyberFlow-Demo"


def _cred_ok(header: str | None) -> bool:
    """True solo si coincide con el par de laboratorio DEMO_OK_USER/PASS (si existe)."""
    ok_user = os.environ.get("DEMO_OK_USER")
    ok_pass = os.environ.get("DEMO_OK_PASS")
    if not ok_user or not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header[6:]).decode("utf-8", "replace")
    except Exception:
        return False
    user, _, pw = raw.partition(":")
    return user == ok_user and pw == ok_pass


class Handler(BaseHTTPRequestHandler):
    def _responder(self) -> None:
        if _cred_ok(self.headers.get("Authorization")):
            cuerpo = b"OK\n"
            self.send_response(200)
        else:
            cuerpo = b"Unauthorized\n"
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="%s"' % REALM)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    do_GET = _responder
    do_POST = _responder
    do_HEAD = _responder

    def log_message(self, *a):  # silencioso; el registro de verdad lo lleva CyberFlow
        return


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8081)
    a = p.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("endpoint 401 escuchando en http://%s:%d/  (Ctrl-C para parar)" % (a.host, a.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nparado.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
