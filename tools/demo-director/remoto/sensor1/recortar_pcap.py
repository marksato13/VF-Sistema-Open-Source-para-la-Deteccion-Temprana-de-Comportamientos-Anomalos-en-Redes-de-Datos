"""Deja en cada PCAP (formato clásico de tcpdump) solo los paquetes con hora en [desde, hasta].
Uso: python3 recortar_pcap.py <desde_epoch> <hasta_epoch> fichero.pcap [...]   (reescribe en sitio)
Sin dependencias: el anillo del sensor no tiene editcap."""
import struct
import sys

desde, hasta = float(sys.argv[1]), float(sys.argv[2])
total = quedan = 0
for ruta in sys.argv[3:]:
    with open(ruta, "rb") as fh:
        datos = fh.read()
    if len(datos) < 24:
        continue
    magia = datos[:4]
    if magia in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        e = "<"
    elif magia in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        e = ">"
    else:
        continue                                   # no es pcap clásico: se deja tal cual
    div = 1e9 if magia in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d") else 1e6
    out = [datos[:24]]
    i = 24
    while i + 16 <= len(datos):
        seg, frac, incl, _ = struct.unpack(e + "IIII", datos[i:i + 16])
        fin = i + 16 + incl
        total += 1
        if desde <= seg + frac / div <= hasta:
            out.append(datos[i:fin])
            quedan += 1
        i = fin
    with open(ruta, "wb") as fh:
        fh.write(b"".join(out))
print("  paquetes en el intervalo exacto: %d de %d" % (quedan, total), file=sys.stderr)
