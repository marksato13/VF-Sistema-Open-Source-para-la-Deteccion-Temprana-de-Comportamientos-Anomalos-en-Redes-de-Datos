"""Consulta NTP no privilegiada, sin cambiar el reloj local.

Uso: python3 08-probar-ntp.py [servidor]
"""

import socket
import struct
import sys
import time


def seconds(packet, start):
    sec, frac = struct.unpack("!II", packet[start : start + 8])
    return sec - 2_208_988_800 + frac / 2**32


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "10.10.60.1"
    request = bytearray(48)
    request[0] = 0x23  # cliente NTP v4
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(3)
        t1 = time.time()
        sock.sendto(request, (host, 123))
        packet, sender = sock.recvfrom(512)
        t4 = time.time()
    if len(packet) < 48 or sender[0] != host:
        raise RuntimeError("Respuesta NTP invalida")
    leap = packet[0] >> 6
    mode = packet[0] & 7
    stratum = packet[1]
    if mode != 4 or leap == 3 or not 1 <= stratum <= 15:
        raise RuntimeError(f"Servidor no sincronizado: leap={leap}, stratum={stratum}, mode={mode}")
    t2 = seconds(packet, 32)
    t3 = seconds(packet, 40)
    offset = ((t2 - t1) + (t3 - t4)) / 2
    delay = (t4 - t1) - (t3 - t2)
    print(f"servidor={host} stratum={stratum} offset_s={offset:+.6f} rtt_s={delay:.6f}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f"NTP no verificado: {exc}", file=sys.stderr)
        sys.exit(1)
