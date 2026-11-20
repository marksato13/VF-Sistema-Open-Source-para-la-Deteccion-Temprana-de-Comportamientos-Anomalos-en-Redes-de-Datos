#!/usr/bin/env python3
"""Deriva vigia_4c_b.py del vigia_4c.py 2026-11-06.1 firmado con UNA excepción acotada de X3 (tráfico NTP propio de la Kali).
La excepción solo exime un evento EVE `flow` que cumpla TODO: src = origen del experimento; proto UDP; dest_port 123; destino en
--ntp-permitido (lista cerrada, fijada antes de lanzar); y flujo diminuto (<= 4 paquetes y <= 400 bytes en cada sentido).
Todo lo demás de X3 queda igual (otro destino, otro puerto, TCP, flujo grande, otro tipo de evento). Cada exención queda contada
(`ntp_excepcion_total`) y registrada en la ronda del vigía. Sin --ntp-permitido el comportamiento es idéntico al original.
Cada sustitución debe aplicarse exactamente una vez. Uso: hacer_vigia_b.py <vigia_4c.py> <salida>."""
import sys

SUST = [
    ('VERSION = "2026-11-06.1"  #', 'VERSION = "2026-11-06.1+B-ntp"  # campaña B: excepción X3 acotada al NTP de la Kali (hacer_vigia_b.py);'),
    ('def eve_fuera_lista(eve: Path, cursor: int, origen: str, blanca: set[str], max_bytes: int) -> dict:',
     'NTP_MAX_PAQUETES, NTP_MAX_BYTES = 4, 400   # un cliente NTP: 1 paquete y 76-94 B en cada sentido\n\n\n'
     'def es_ntp_permitido(ev: dict, ntp: set[str]) -> bool:\n'
     '    """Excepción de B: consulta NTP propia (flow UDP/123 diminuto) a un servidor de la lista cerrada `ntp`."""\n'
     '    f = ev.get("flow") or {}\n'
     '    return bool(ntp) and ev.get("event_type") == "flow" and ev.get("proto") == "UDP" and ev.get("dest_port") == 123 \\\n'
     '        and ev.get("dest_ip") in ntp and (f.get("pkts_toserver") or 0) <= NTP_MAX_PAQUETES \\\n'
     '        and (f.get("pkts_toclient") or 0) <= NTP_MAX_PAQUETES and (f.get("bytes_toserver") or 0) <= NTP_MAX_BYTES \\\n'
     '        and (f.get("bytes_toclient") or 0) <= NTP_MAX_BYTES and "pkts_toserver" in f and "bytes_toserver" in f\n\n\n'
     'def eve_fuera_lista(eve: Path, cursor: int, origen: str, blanca: set[str], max_bytes: int,\n'
     '                    ntp: set[str] | None = None) -> dict:'),
    ('    fuera, n = [], 0\n', '    fuera, n, ntp_ex = [], 0, 0\n'),
    ('        if ev.get("src_ip") == origen and ev.get("dest_ip") not in blanca:\n',
     '        if ev.get("src_ip") == origen and ev.get("dest_ip") not in blanca and es_ntp_permitido(ev, ntp or set()):\n'
     '            ntp_ex += 1\n'
     '            continue\n'
     '        if ev.get("src_ip") == origen and ev.get("dest_ip") not in blanca:\n'),
    ('            "fuera_total": len(fuera)}', '            "fuera_total": len(fuera), "ntp_excepcion_total": ntp_ex}'),
    ('    r["eve"] = eve_fuera_lista(Path(a.eve), a.eve_cursor, a.origen, set(a.lista_blanca.split(",")),\n                               a.eve_max_bytes)',
     '    r["eve"] = eve_fuera_lista(Path(a.eve), a.eve_cursor, a.origen, set(a.lista_blanca.split(",")),\n'
     '                               a.eve_max_bytes, {x for x in a.ntp_permitido.split(",") if x})'),
    ('    s.add_argument("--lista-blanca", required=True, help="IPs separadas por comas")\n',
     '    s.add_argument("--lista-blanca", required=True, help="IPs separadas por comas")\n'
     '    s.add_argument("--ntp-permitido", default="", help="B: servidores NTP de la Kali cuyas consultas diminutas UDP/123 no cuentan para X3")\n'),
    ('"eve_fuera": (s.get("eve") or {}).get("fuera_total"),',
     '"eve_fuera": (s.get("eve") or {}).get("fuera_total"), "eve_ntp_excepcion": (s.get("eve") or {}).get("ntp_excepcion_total"),'),
]


def main(origen, salida):
    t = open(origen, encoding="utf-8").read()
    mal = []
    for a, b in SUST:
        if t.count(a) != 1:
            mal.append((t.count(a), a[:70]))
        t = t.replace(a, b, 1)
    open(salida, "w", encoding="utf-8", newline="\n").write(t)
    print("sustituciones: %d, fallidas: %s" % (len(SUST), mal or "ninguna"))
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
