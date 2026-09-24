#!/usr/bin/env python3
"""Genera el trafico de fondo del laboratorio, con un perfil por IP.

No es parte del producto: es el aparato experimental que produce la linea
base sobre la que se recalibra el modelo.

Tres decisiones de diseno, y las tres importan para que la linea base sirva:

1. UNA IP POR PERFIL. El motor puntua por IP, asi que cada alias es una
   entidad distinta con su propio comportamiento. Seis entidades salen de una
   sola maquina.

2. LLEGADAS EXPONENCIALES, NO TEMPORIZADORES. Si las peticiones salen cada
   segundo exacto, el modelo aprende un metronomo y marca como anomalia
   cualquier variacion normal. El intervalo se sortea de una exponencial.

3. CURVA DIARIA. La intensidad varia con la hora. Sin variacion diaria no se
   puede demostrar que el modelo tolera la variacion normal, y la madrugada
   saldria como anomala.

Y una cuarta, menos obvia: una fraccion de las conexiones FALLA a proposito
-puertos cerrados, cortes a mitad- porque syn_completion_ratio_10s,
rst_ratio_10s y tcp_retransmission_ratio_10s no tienen varianza en una red
donde todo funciona siempre.

Uso:
    python3 clientes_lab.py --perfil ofimatica --origen 10.10.20.21 \\
        --servidor 10.10.30.10 --dns 10.10.10.20
    python3 clientes_lab.py --listar-perfiles
"""
from __future__ import annotations

import argparse
import datetime
import http.client
import random
import socket
import ssl
import struct
import sys
import time

# --- perfiles ---------------------------------------------------------------
# peso: cuantas acciones de cada tipo, relativo. ritmo: segundos medios entre
# acciones en hora punta.
PERFILES = {
    "ofimatica": {
        "ritmo": 3.0,
        "acciones": {"web_pequena": 50, "web_media": 20, "dns": 25, "api_ok": 15,
                     "api_auth": 3, "api_404": 4, "https": 20, "ping": 5},
    },
    "navegacion": {
        "ritmo": 1.5,
        "acciones": {"web_pequena": 40, "web_grande": 25, "https": 35, "dns": 30,
                     "dns_inexistente": 4, "api_ok": 10, "abandono": 6},
    },
    "descargas": {
        "ritmo": 8.0,
        "acciones": {"web_grande": 60, "web_media": 25, "https": 10, "dns": 5},
    },
    "aplicacion": {
        "ritmo": 2.0,
        "acciones": {"api_ok": 45, "api_post": 25, "api_500": 6, "api_lento": 8,
                     "https": 10, "dns": 10},
    },
    "ligero": {
        "ritmo": 12.0,
        "acciones": {"dns": 40, "api_ok": 25, "web_pequena": 20, "ping": 15},
    },
    "erratico": {
        # Rafagas y silencios: ensancha la distribucion normal para que el
        # modelo no aprenda una linea base demasiado estrecha.
        "ritmo": 5.0,
        "acciones": {"web_pequena": 25, "web_grande": 15, "dns": 20, "api_ok": 15,
                     "puerto_cerrado": 10, "abandono": 8, "ping": 7},
        "rafagas": True,
    },
}

DOMINIOS = ["ad.francos-sac.com", "srv.francos-sac.com", "intranet.francos-sac.com",
            "erp.francos-sac.com", "correo.francos-sac.com", "wiki.francos-sac.com"]


def factor_horario(ahora: datetime.datetime) -> float:
    """Curva diaria: laborable activo, noche tranquila, fin de semana flojo."""
    h = ahora.hour + ahora.minute / 60.0
    if 8 <= h < 13:
        base = 1.0
    elif 13 <= h < 15:
        base = 0.55          # pausa de comida
    elif 15 <= h < 19:
        base = 0.9
    elif 19 <= h < 23:
        base = 0.35
    else:
        base = 0.12          # madrugada: poco, pero nunca cero
    if ahora.weekday() >= 5:
        base *= 0.3
    return base


class Cliente:
    def __init__(self, origen: str, servidor: str, dns: str, ficheros: str | None,
                 puerto: int = 80, puerto_https: int = 443):
        self.origen = origen
        self.servidor = servidor
        # OJO: no llamarlo self.dns. El atributo taparia al metodo dns() y
        # cada consulta fallaria con "'str' object is not callable".
        self.servidor_dns = dns
        self.ficheros = ficheros
        self.puerto = puerto
        self.puerto_https = puerto_https
        self.hechas = 0
        self.fallidas = 0

    # -- utilidades -------------------------------------------------------
    def _socket(self, destino: str, puerto: int, espera: float = 5.0) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(espera)
            if self.origen:
                s.bind((self.origen, 0))   # la IP de origen ES la identidad
            s.connect((destino, puerto))
        except BaseException:
            # Sin esto el descriptor queda a merced del recolector. CPython lo
            # cierra enseguida por conteo de referencias, pero este camino es
            # el NORMAL en puerto_cerrado y en los abandonos: se recorre miles
            # de veces en una linea base de 72 h, y depender del recolector
            # para algo que ocurre por diseno es pedir un agotamiento de
            # descriptores a las horas.
            s.close()
            raise
        return s

    def _http(self, ruta: str, metodo: str = "GET", cuerpo: bytes | None = None,
              https: bool = False, leer: bool = True) -> None:
        puerto = self.puerto_https if https else self.puerto
        s = self._socket(self.servidor, puerto, espera=10.0)
        try:
            if https:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE   # certificado propio del laboratorio
                s = ctx.wrap_socket(s, server_hostname=self.servidor)
            c = http.client.HTTPConnection(self.servidor, puerto, timeout=10)
            c.sock = s
            c.request(metodo, ruta, body=cuerpo,
                      headers={"Host": self.servidor, "Connection": "close"})
            r = c.getresponse()
            if leer:
                r.read()
            else:
                # Abandono: se corta sin leer la respuesta entera. Produce RST
                # y retransmisiones, que es justo lo que se quiere medir.
                s.close()
        finally:
            try:
                s.close()
            except OSError:
                pass

    def _consulta_dns(self, nombre: str) -> None:
        # Consulta A minima, construida a mano: evita depender de dnspython.
        tid = random.randint(0, 65535)
        cabecera = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
        pregunta = b"".join(bytes([len(p)]) + p.encode() for p in nombre.split(".")) + b"\x00"
        paquete = cabecera + pregunta + struct.pack("!HH", 1, 1)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3.0)
        try:
            if self.origen:
                s.bind((self.origen, 0))
            s.sendto(paquete, (self.servidor_dns, 53))
            s.recvfrom(2048)
        finally:
            s.close()

    # -- acciones ---------------------------------------------------------
    def web_pequena(self) -> None:
        self._http(random.choice(["/", "/estatico/4k", "/estatico/16k"]))

    def web_media(self) -> None:
        self._http("/estatico/%dk" % random.choice([64, 128, 256]))

    def web_grande(self) -> None:
        self._http("/estatico/%dk" % random.choice([1024, 2048, 4096]))

    def https(self) -> None:
        self._http(random.choice(["/", "/api/ok", "/estatico/32k"]), https=True)

    def dns(self) -> None:
        self._consulta_dns(random.choice(DOMINIOS))

    def dns_inexistente(self) -> None:
        # NXDOMAIN: sin esto, dns_nxdomain_ratio_60s es constante cero.
        self._consulta_dns("%s.francos-sac.com" % random.randbytes(6).hex())

    def api_ok(self) -> None:
        self._http("/api/ok")

    def api_post(self) -> None:
        self._http("/api/enviar", metodo="POST",
                   cuerpo=random.randbytes(random.randint(200, 8000)))

    def api_auth(self) -> None:
        self._http("/api/auth")

    def api_404(self) -> None:
        self._http("/api/perdido")

    def api_500(self) -> None:
        self._http("/api/fallo")

    def api_lento(self) -> None:
        self._http("/api/lento")

    def abandono(self) -> None:
        self._http("/estatico/2048k", leer=False)

    def puerto_cerrado(self) -> None:
        # Un RST -o un SYN sin respuesta- ES el resultado buscado: alimenta
        # rst_ratio_10s y syn_completion_ratio_10s. El codigo anterior hacia
        # "except OSError: raise", asi que contaba como fallo justo el caso de
        # exito: en 72 h habria sumado miles de fallos inexistentes y el
        # recuento de acciones no significaria nada.
        #
        # Lo unico que si es un fallo de verdad es que el puerto este ABIERTO,
        # porque querria decir que la regla de rechazo apunta a otros puertos.
        puerto = random.choice([8081, 9001, 4444, 31337])
        try:
            self._socket(self.servidor, puerto, espera=2.0).close()
        except OSError:
            return
        raise RuntimeError("el puerto %d esta ABIERTO; se esperaba cerrado" % puerto)

    def ping(self) -> None:
        # ICMP sin privilegios no es posible con sockets crudos; se usa el
        # binario del sistema, que si tiene las capacidades necesarias.
        #
        # Los parametros NO son los mismos en Windows y en Linux. Con los de
        # Linux en Windows el comando falla, y como antes no se comprobaba el
        # codigo de salida, la accion decia "ok" sin enviar un solo paquete:
        # icmp_ratio_10s habria quedado plana sin que nadie se enterara.
        import platform
        import subprocess
        # Solo al servidor del laboratorio. Antes alternaba con el servidor DNS,
        # y el cortafuegos bloquea ICMP hacia la VLAN de administracion: la
        # mitad de los pings fallaba en silencio y icmp_ratio_10s recibia la
        # mitad de la senal prevista. Abrir ICMP hacia el DNS seria un agujero
        # mas en un cortafuegos de produccion para no ganar nada: el servidor
        # del laboratorio ya da toda la senal que esta variable necesita.
        destino = self.servidor
        if platform.system() == "Windows":
            orden = ["ping", "-n", "1", "-w", "2000"]
            if self.origen:
                orden += ["-S", self.origen]
        else:
            orden = ["ping", "-c", "1", "-W", "2"]
            if self.origen:
                orden += ["-I", self.origen]
        orden.append(destino)
        r = subprocess.run(orden, capture_output=True, timeout=8)
        if r.returncode != 0:
            raise RuntimeError("ping a %s fallo (%d)" % (destino, r.returncode))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", choices=sorted(PERFILES))
    p.add_argument("--origen", default="", help="IP de origen: es la identidad de la entidad")
    p.add_argument("--servidor", default="10.10.30.10")
    p.add_argument("--dns", default="10.10.10.20")
    p.add_argument("--ficheros", default=None, help="servidor de ficheros, opcional")
    p.add_argument("--puerto", type=int, default=80)
    p.add_argument("--puerto-https", type=int, default=443)
    p.add_argument("--intensidad", type=float, default=1.0,
                   help="multiplica el ritmo; 2.0 = el doble de trafico")
    p.add_argument("--listar-perfiles", action="store_true")
    p.add_argument("--una-vuelta", action="store_true",
                   help="ejecuta una accion de cada tipo y sale; para comprobar")
    args = p.parse_args()

    if args.listar_perfiles:
        for nombre, perfil in sorted(PERFILES.items()):
            print("%-12s ritmo %4.1f s   %s" % (
                nombre, perfil["ritmo"], ", ".join(sorted(perfil["acciones"]))))
        return 0
    if not args.perfil:
        p.error("hace falta --perfil (o --listar-perfiles)")

    perfil = PERFILES[args.perfil]
    cliente = Cliente(args.origen, args.servidor, args.dns, args.ficheros,
                      args.puerto, args.puerto_https)
    acciones = list(perfil["acciones"])
    pesos = [perfil["acciones"][a] for a in acciones]
    print("perfil %s desde %s -> %s" % (args.perfil, args.origen or "por omision",
                                        args.servidor), flush=True)

    if args.una_vuelta:
        for nombre in acciones:
            try:
                getattr(cliente, nombre)()
                print("  %-18s ok" % nombre)
            except Exception as e:                      # noqa: BLE001
                print("  %-18s %s: %s" % (nombre, type(e).__name__, str(e)[:60]))
        return 0

    en_rafaga = False
    fin_rafaga = 0.0
    while True:
        ahora = datetime.datetime.now()
        factor = factor_horario(ahora) * max(args.intensidad, 0.01)

        if perfil.get("rafagas"):
            if en_rafaga and time.time() > fin_rafaga:
                en_rafaga = False
            elif not en_rafaga and random.random() < 0.02:
                en_rafaga = True
                fin_rafaga = time.time() + random.uniform(20, 90)
            if en_rafaga:
                factor *= 6.0

        try:
            getattr(cliente, random.choices(acciones, weights=pesos)[0])()
            cliente.hechas += 1
        except Exception:                               # noqa: BLE001
            # Los fallos son parte del trafico normal: puertos cerrados y
            # abandonos estan ahi a proposito. No se registra cada uno para no
            # inundar el journal.
            cliente.fallidas += 1

        if (cliente.hechas + cliente.fallidas) % 200 == 0:
            print("acciones %d, fallidas %d" % (cliente.hechas, cliente.fallidas),
                  flush=True)

        time.sleep(random.expovariate(1.0 / max(perfil["ritmo"] / factor, 0.05)))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(0)
