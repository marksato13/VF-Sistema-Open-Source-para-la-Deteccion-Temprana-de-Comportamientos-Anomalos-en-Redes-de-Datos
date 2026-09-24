#!/usr/bin/env python3
"""Acumula el dataset de la linea base extrayendo sobre la marcha.

**El problema que resuelve.** El anillo de PCAP solo conserva unos minutos
-``captura.retener_minutos``-, porque guardarlo entero no cabe: a 8,6 Mbit/s
espejados, 72 h son unos 280 GB. Pero 20 de las 31 variables salen del PCAP,
asi que sin ellos no hay extraccion posible hacia atras. Al terminar una linea
base de tres dias habria registro de decisiones y quince minutos de captura.

La salida es extraer **periodicamente** y quedarse con las filas, no con los
paquetes: ~155.000 filas para 72 h y seis entidades, unos 78 MB.

    python3 acumular_v3.py --salida artifacts/linea-base/multilayer-v3.csv

Pensado para un temporizador de systemd que lo ejecute cada pocos minutos. Es
idempotente: una fila ya escrita no se repite, identificada por
``(entity_ip, window_end_utc)``.

**Por que se descartan los bordes de cada pasada.** Una ventana necesita hasta
60 s de historia previa para que sus variables de 30 s y 60 s esten completas,
y el anillo solo tiene lo que tiene. Asi que de cada rebanada se conservan
unicamente las ventanas que terminan al menos ``--margen-inicio`` segundos
despues del primer paquete disponible, y al menos ``--margen-final`` antes del
ultimo: las primeras tendrian historia truncada y las ultimas estarian a medio
llenar. El solape entre pasadas sucesivas cubre lo descartado.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract_multilayer_v3 as v3  # noqa: E402

v2 = v3.v2


def pcaps_cerrados(directorio: Path, patron: str) -> list[Path]:
    """Los del anillo menos el ultimo, que tcpdump todavia esta escribiendo."""
    todos = sorted(Path(p) for p in glob.glob(str(directorio / patron)))
    legibles = [p for p in todos[:-1] if os.access(p, os.R_OK)]
    return legibles


def rebanada_eve(eve: Path, desde: float, hasta: float, destino: Path,
                 max_bytes: int = 64 * 1024 * 1024) -> int:
    """Escribe las lineas de eve.json dentro del rango, y devuelve cuantas.

    ``load_app_observations`` espera un fichero completo, no un tail: por eso
    se materializa la rebanada en vez de pasarle el eve.json entero, que crece
    sin limite durante la linea base.
    """
    escritas = 0
    with eve.open("rb") as f:
        tam = f.seek(0, 2)
        f.seek(max(0, tam - max_bytes))
        crudo = f.read().decode("utf-8", errors="replace")
    lineas = crudo.split("\n")
    if tam > max_bytes:
        lineas = lineas[1:]          # la primera puede venir cortada
    with destino.open("w", encoding="utf-8") as salida:
        for linea in lineas:
            if not linea.strip():
                continue
            try:
                marca = v2.parse_eve_timestamp(json.loads(linea)["timestamp"])
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            if desde <= marca <= hasta:
                salida.write(linea + "\n")
                escritas += 1
    return escritas


def claves_ya_escritas(csv_path: Path) -> set[tuple[str, str]]:
    if not csv_path.exists():
        return set()
    vistas = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            vistas.add((fila["entity_ip"], fila["window_end_utc"]))
    return vistas


def main() -> int:
    raiz = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--capture-dir", type=Path, default=Path("/var/lib/ppi-motor-capture"))
    p.add_argument("--capture-glob", default="live-*.pcap")
    p.add_argument("--eve", type=Path, default=Path("/var/log/suricata/eve.json"))
    p.add_argument("--entity-network", default="10.10.0.0/16")
    # Las MISMAS exclusiones que aplica el motor. Sin esto el dataset incluiria
    # entidades que el sistema declara fuera de alcance -el sensor, el bastion,
    # la gestion del generador- y el modelo se entrenaria sobre un conjunto que
    # no describe lo que luego se puntua. Medido en la primera prueba: 279 de
    # 622 filas eran de esas tres.
    p.add_argument("--excluir", default="")
    p.add_argument("--excluir-protocolos", default="112,240")
    p.add_argument("--campaign-id", default="linea-base")
    p.add_argument("--margen-inicio", type=int, default=60,
                   help="segundos del principio de la rebanada cuyas ventanas se "
                        "descartan por tener la historia truncada")
    p.add_argument("--margen-final", type=int, default=30,
                   help="segundos del final cuyas ventanas pueden estar a medio llenar")
    p.add_argument("--sin-deduplicar", action="store_true")
    args = p.parse_args()

    args.salida.parent.mkdir(parents=True, exist_ok=True)

    # Un unico acumulador a la vez. Sin esto, una pasada lenta y la siguiente
    # se solaparian y escribirian filas repetidas o un CSV entrelazado.
    cerrojo = args.salida.with_suffix(args.salida.suffix + ".lock")
    fcerrojo = cerrojo.open("w")
    try:
        fcntl.flock(fcerrojo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"event": "acumular", "estado": "ya_corriendo"}))
        return 0

    t0 = time.time()
    import ipaddress
    red = ipaddress.ip_network(args.entity_network)
    excluidos = frozenset(int(x) for x in args.excluir_protocolos.split(",") if x.strip())

    ficheros = pcaps_cerrados(args.capture_dir, args.capture_glob)
    if not ficheros:
        print(json.dumps({"event": "acumular", "estado": "sin_pcap"}))
        return 0

    contextos = []
    ilegibles = 0
    for ruta in ficheros:
        try:
            for marca, trama in v2.iter_pcap_frames(ruta):
                ctx = v3.parse_con_contexto(marca, trama)
                if ctx is not None and ctx.packet.protocol not in excluidos:
                    contextos.append(ctx)
        except Exception:
            ilegibles += 1

    if not contextos:
        print(json.dumps({"event": "acumular", "estado": "sin_paquetes"}))
        return 0

    marcas = [c.packet.timestamp for c in contextos]
    inicio, fin = min(marcas), max(marcas)

    duplicados = 0
    if args.sin_deduplicar:
        paquetes_ip = [c.packet for c in contextos]
    else:
        paquetes_ip, duplicados = v3.deduplicar_espejo(contextos)

    with tempfile.TemporaryDirectory() as tmp:
        corte = Path(tmp) / "eve.jsonl"
        eventos = rebanada_eve(args.eve, inicio - 90, fin + 5, corte) if args.eve.exists() else 0

        paquetes = v2.attribute_packets(paquetes_ip, red)
        apps = v2.load_app_observations(corte, red) if eventos else []
        capa2 = v3.load_l2_observations(ficheros, red, excluidos)
        filas = v3.build_rows(args.campaign_id, paquetes, apps, capa2,
                              capture_start=inicio)

    # Bordes fuera: por el principio la historia esta truncada, por el final la
    # ventana puede estar a medio llenar. El solape entre pasadas lo cubre.
    minimo = inicio + args.margen_inicio
    maximo = fin - args.margen_final
    redes_fuera = [ipaddress.ip_network(t.strip(), strict=False)
                   for t in args.excluir.split(",") if t.strip()]

    def excluida(ip: str) -> bool:
        try:
            direccion = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(direccion in r for r in redes_fuera)

    def dentro(fila) -> bool:
        return minimo <= v2.parse_eve_timestamp(str(fila["window_end_utc"])) <= maximo

    candidatas = [f for f in filas
                  if dentro(f) and not excluida(str(f["entity_ip"]))]
    fuera_de_alcance = sum(1 for f in filas if excluida(str(f["entity_ip"])))

    ya = claves_ya_escritas(args.salida)
    nuevas = [f for f in candidatas
              if (str(f["entity_ip"]), str(f["window_end_utc"])) not in ya]
    nuevas.sort(key=lambda f: (str(f["window_end_utc"]), str(f["entity_ip"])))

    if nuevas:
        columnas = v3.METADATA_COLUMNS + v3.FEATURE_NAMES
        existe = args.salida.exists()
        with args.salida.open("a", encoding="utf-8", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=columnas)
            if not existe:
                escritor.writeheader()
            for fila in nuevas:
                escritor.writerow({k: (f"{v:.8f}" if isinstance(v, float) else v)
                                   for k, v in fila.items()})

    print(json.dumps({
        "event": "acumular",
        "estado": "ok",
        "pcaps": len(ficheros),
        "pcaps_ilegibles": ilegibles,
        "ventana_s": round(fin - inicio, 1),
        "paquetes": len(contextos),
        "duplicados_espejo": duplicados,
        "eventos_eve": eventos,
        "filas_generadas": len(filas),
        "filas_fuera_de_alcance": fuera_de_alcance,
        "filas_en_margen": len(candidatas),
        "filas_nuevas": len(nuevas),
        "filas_totales": len(ya) + len(nuevas),
        "segundos": round(time.time() - t0, 1),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
