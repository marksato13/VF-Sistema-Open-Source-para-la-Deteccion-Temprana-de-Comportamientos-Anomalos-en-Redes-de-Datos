#!/usr/bin/env python3
"""Extrae el vector multicapa-v3 (31 features): las 28 de v2 más 3 de capa 2.

**Por qué esto importa a v2 en vez de reimplementarlo.** El manifiesto del
modelo publicado fija el SHA-256 de los CSV de entrenamiento. Si las 28
primeras columnas se recalcularan aquí, cualquier diferencia de redondeo
rompería la reproducción bit a bit sin que nadie se enterara hasta el próximo
``verificar_reproduccion.py``. Importando ``extract_multilayer_v2`` esas 28
columnas son idénticas **por construcción**: las calcula el mismo código
congelado. Este fichero solo añade columnas.

Las tres nuevas salen de una pasada independiente sobre las tramas Ethernet.
El extractor v2 descarta todo lo que no sea IPv4, así que **nunca ve una trama
ARP**; sin esa pasada, un barrido de la propia VLAN —que no cruza el
enrutador— es sencillamente invisible.

- ``arp_request_rate_10s``: peticiones ARP por segundo cuya dirección de
  protocolo del emisor (SPA) es la entidad.
- ``unique_src_mac_30s``: direcciones MAC de origen distintas en tramas cuyo
  emisor IP es la entidad. En condiciones normales vale 1.
- ``mac_ip_binding_changes_60s``: transiciones de esa MAC en orden temporal.

**La VLAN nativa y por qué hace falta.** El espejo tiene origen en los
troncales del cortafuegos y captura en los dos sentidos, así que un paquete
entre VLAN aparece dos veces: una al entrar al cortafuegos, con la MAC real
del emisor, y otra al salir hacia la VLAN de destino, ya con la MAC del
cortafuegos pero **con la misma IP de origen**. Contar MAC sin filtrar daría
``unique_src_mac_30s = 2`` para todo el tráfico normal entre VLAN, y la
variable no distinguiría nada. Por eso cada entidad se ancla a su *VLAN
nativa* y las tres features se calculan solo dentro de ella. Esa VLAN no puede
ser simplemente la etiqueta más frecuente: las dos copias empatan, y el
desempate acabaría eligiendo la VLAN del interlocutor la mitad de las veces.
Se descartan antes las tramas cuya MAC de origen aparece en más de una VLAN
—la firma de un reenviador— y se mira dónde aparece la entidad con una MAC
que no reenvía. Ver ``native_vlans``.

**Límite del punto de observación.** Las peticiones ARP son difusión y llegan
completas al espejo. Las respuestas ARP son unidifusión: solo llegan las
dirigidas al cortafuegos. Por eso la feature se define sobre peticiones y no
sobre el par petición/respuesta, que desde aquí no se puede cerrar.

**Límite conocido de ``mac_ip_binding_changes_60s``.** Una concesión DHCP
nueva cambia legítimamente el vínculo MAC↔IP. En la VLAN 20 hay DHCP
(``10.10.20.50``-``.200``), así que la línea base **tiene que contener**
rotación normal de arrendamientos; si no, el modelo aprenderá que todo cambio
de vínculo es anómalo y marcará cada renovación como suplantación.
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import math
import socket
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract_multilayer_v2 as v2  # noqa: E402  (tras ajustar sys.path)


FEATURE_NAMES_L2 = (
    "arp_request_rate_10s",
    "unique_src_mac_30s",
    "mac_ip_binding_changes_60s",
)

FEATURE_NAMES = v2.FEATURE_NAMES + FEATURE_NAMES_L2

METADATA_COLUMNS = v2.METADATA_COLUMNS + (
    "native_vlan",
    "arp_request_count_10s",
    "l2_frame_count_30s",
)

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP = 0x0806
ARP_OPCODE_REQUEST = 1


@dataclass(frozen=True)
class L2Observation:
    timestamp: float
    vlan: int          # 0 = trama sin etiqueta
    src_mac: str
    sender_ip: str     # IPv4: dirección de origen. ARP: SPA del emisor.
    arp_request: bool
    # Protocolo IP, o -1 si la trama es ARP. Existe para poder descartar el
    # plano de control igual que hace el motor: sin esto, cada interfaz VLAN
    # del cortafuegos volvería a aparecer como entidad por la puerta de atrás
    # de la capa 2, deshaciendo la exclusión de CARP y pfsync.
    protocol: int = -1


def format_mac(raw: bytes) -> str:
    return ":".join(f"{byte:02x}" for byte in raw)


def parse_ethernet_l2(timestamp: float, frame: bytes) -> L2Observation | None:
    """Devuelve el emisor de la trama, sea IPv4 o ARP, con su MAC y su VLAN."""
    if len(frame) < 14:
        return None
    src_mac = format_mac(frame[6:12])
    ether_type = struct.unpack("!H", frame[12:14])[0]
    offset = 14
    vlan = 0
    while ether_type in (0x8100, 0x88A8):
        if len(frame) < offset + 4:
            return None
        if vlan == 0:
            # La etiqueta exterior es la que conserva el espejo y la que
            # imprime tcpdump como "vlan N". Con QinQ la interior se ignora.
            vlan = struct.unpack("!H", frame[offset : offset + 2])[0] & 0x0FFF
        ether_type = struct.unpack("!H", frame[offset + 2 : offset + 4])[0]
        offset += 4

    if ether_type == ETHERTYPE_IPV4:
        if len(frame) < offset + 20 or frame[offset] >> 4 != 4:
            return None
        sender_ip = socket.inet_ntoa(frame[offset + 12 : offset + 16])
        return L2Observation(
            timestamp, vlan, src_mac, sender_ip, False, frame[offset + 9]
        )

    if ether_type == ETHERTYPE_ARP:
        # htype(2) ptype(2) hlen(1) plen(1) oper(2) sha(6) spa(4) tha(6) tpa(4)
        if len(frame) < offset + 28:
            return None
        _, proto_type, hw_len, proto_len, opcode = struct.unpack(
            "!HHBBH", frame[offset : offset + 8]
        )
        if hw_len != 6 or proto_len != 4 or proto_type != ETHERTYPE_IPV4:
            return None
        sender_ip = socket.inet_ntoa(frame[offset + 14 : offset + 18])
        return L2Observation(
            timestamp, vlan, src_mac, sender_ip, opcode == ARP_OPCODE_REQUEST
        )

    return None


@dataclass(frozen=True)
class FrameContext:
    """Un ``ParsedPacket`` de v2 más los dos campos que v2 no conserva.

    v2 descarta la etiqueta VLAN al saltarla y nunca lee el identificador IP.
    Los dos hacen falta para reconocer una copia del espejo, y **no se añaden
    a v2**: se leen aquí, de la misma trama, sin tocar el parser congelado.
    """
    packet: object
    vlan: int
    ip_id: int


def parse_con_contexto(timestamp: float, frame: bytes) -> FrameContext | None:
    paquete = v2.parse_ethernet_ipv4(timestamp, frame)
    if paquete is None:
        return None
    capa2 = parse_ethernet_l2(timestamp, frame)
    vlan = capa2.vlan if capa2 is not None else 0
    # Recorrer las etiquetas otra vez sale más barato que devolver el
    # desplazamiento desde parse_ethernet_l2 y acoplar las dos funciones.
    offset = 14
    ether_type = struct.unpack("!H", frame[12:14])[0]
    while ether_type in (0x8100, 0x88A8):
        ether_type = struct.unpack("!H", frame[offset + 2 : offset + 4])[0]
        offset += 4
    ip_id = struct.unpack("!H", frame[offset + 4 : offset + 6])[0]
    return FrameContext(paquete, vlan, ip_id)


def deduplicar_espejo(
    contextos: list[FrameContext], ventana_segundos: float = 0.005
) -> tuple[list, int]:
    """Quita la segunda copia de cada trama que el espejo enseña dos veces.

    El espejo duplica por dos vías distintas, las dos medidas en esta red:

    1. **Tráfico entre VLAN.** La sesión captura en los dos sentidos del
       troncal, así que el paquete se ve al entrar al cortafuegos y al salir
       hacia la VLAN de destino. Las dos copias difieren en **exactamente 1 de
       TTL**, porque el enrutador lo decrementa.
    2. **Difusión y multidifusión.** La trama inunda los dos puertos troncales
       y la sesión escucha los dos. Aquí las copias son idénticas byte a byte:
       misma VLAN, mismo TTL, mismas MAC.

    Medido sobre 6396 paquetes del espejo real: 290 pares, con diferencia de
    TTL **0 o 1 y nada más** -bimodal sin una sola excepción-, y separación
    máxima de 512 µs. La ventana por omisión es diez veces eso.

    Por qué importa más de lo que parece: ``tcp_retransmission_ratio_10s``
    marca como retransmisión un segmento cuya tupla (protocolo, origen,
    destino, número de secuencia) ya apareció. Una copia del espejo encaja en
    esa definición, así que sin deduplicar el motor lee artefactos de la
    captura como problemas de la red. Medido: 40 de los 140 pares idénticos
    eran TCP.

    Se conserva la copia de **mayor TTL**, la que aún no ha cruzado el
    enrutador: es la que lleva el TTL que puso el emisor, y es lo que
    ``ttl_mean_10s`` dice medir.

    No toca el extractor congelado: filtra su entrada, que es alcance, no
    fórmula -- el mismo criterio que la exclusión de CARP y pfsync.
    """
    guardados: dict[tuple, int] = {}
    descartados: set[int] = set()
    orden = sorted(range(len(contextos)), key=lambda i: contextos[i].packet.timestamp)

    for indice in orden:
        actual = contextos[indice]
        paquete = actual.packet
        clave = (
            paquete.protocol,
            paquete.src_ip,
            paquete.dst_ip,
            paquete.src_port,
            paquete.dst_port,
            actual.ip_id,
            paquete.ip_length,
            paquete.tcp_seq,
            paquete.icmp_type,
            paquete.icmp_id,
        )
        previo = guardados.get(clave)
        if previo is not None:
            anterior = contextos[previo]
            mismo_frame = (
                paquete.timestamp - anterior.packet.timestamp <= ventana_segundos
                and abs(paquete.ttl - anterior.packet.ttl) <= 1
            )
            if mismo_frame:
                if paquete.ttl > anterior.packet.ttl:
                    descartados.add(previo)
                    guardados[clave] = indice
                else:
                    descartados.add(indice)
                continue
        guardados[clave] = indice

    conservados = [
        contextos[i].packet for i in orden if i not in descartados
    ]
    return conservados, len(descartados)


def load_l2_observations(
    paths: Iterable[Path],
    entity_network: ipaddress.IPv4Network,
    excluded_protocols: frozenset[int] = frozenset(),
) -> list[L2Observation]:
    observations: list[L2Observation] = []
    for path in paths:
        for timestamp, frame in v2.iter_pcap_frames(path):
            parsed = parse_ethernet_l2(timestamp, frame)
            if parsed is None:
                continue
            if parsed.protocol in excluded_protocols:
                continue
            if not v2._in_scope(parsed.sender_ip, entity_network):
                continue
            observations.append(parsed)
    observations.sort(key=lambda item: item.timestamp)
    return observations


def forwarding_macs(observations: Iterable[L2Observation]) -> set[str]:
    """MAC vistas como origen en más de una VLAN: reenviadores entre VLAN.

    Un equipo normal vive en una sola VLAN y su MAC solo aparece ahí, aunque
    tenga varias IP alias. Un cortafuegos con subinterfaces sobre un troncal
    reutiliza la misma MAC en todas, y una VIP CARP igual. Esa es la señal, y
    no "cuántas IP usa la MAC": la máquina de clientes del laboratorio lleva
    seis alias sobre una sola MAC y no es un reenviador.
    """
    por_mac: dict[str, set[int]] = {}
    for item in observations:
        por_mac.setdefault(item.src_mac, set()).add(item.vlan)
    return {mac for mac, vlanes in por_mac.items() if len(vlanes) > 1}


def native_vlans(observations: Iterable[L2Observation]) -> dict[str, int]:
    """VLAN propia de cada entidad; en empate, la etiqueta más baja.

    No vale con la etiqueta más frecuente. El espejo captura en los dos
    sentidos, así que un paquete entre VLAN aparece dos veces con la misma IP
    de origen: una en la VLAN del emisor y otra en la del destino, ya
    reescrita por el cortafuegos. Las dos empatan, y el desempate elegiría la
    VLAN del interlocutor la mitad de las veces. Por eso primero se descartan
    las tramas reenviadas y solo se mira dónde aparece la entidad con una MAC
    que no reenvía; si no queda ninguna, se vuelve al recuento completo.
    """
    items = list(observations)
    reenviadores = forwarding_macs(items)
    propias: dict[str, dict[int, int]] = {}
    todas: dict[str, dict[int, int]] = {}
    for item in items:
        todas.setdefault(item.sender_ip, {})
        todas[item.sender_ip][item.vlan] = todas[item.sender_ip].get(item.vlan, 0) + 1
        if item.src_mac not in reenviadores:
            propias.setdefault(item.sender_ip, {})
            propias[item.sender_ip][item.vlan] = propias[item.sender_ip].get(item.vlan, 0) + 1
    return {
        entity: min(
            (propias.get(entity) or per_entity).items(),
            key=lambda pair: (-pair[1], pair[0]),
        )[0]
        for entity, per_entity in todas.items()
    }


def binding_changes(observations: list[L2Observation]) -> int:
    """Transiciones de MAC en orden temporal. Un ida y vuelta A-B-A son dos."""
    cambios = 0
    anterior = ""
    for item in observations:
        if anterior and item.src_mac != anterior:
            cambios += 1
        anterior = item.src_mac
    return cambios


def zero_l2_columns() -> dict[str, object]:
    return {
        "arp_request_count_10s": 0,
        "l2_frame_count_30s": 0,
        "arp_request_rate_10s": 0.0,
        "unique_src_mac_30s": 0.0,
        "mac_ip_binding_changes_60s": 0.0,
    }


def build_rows(
    campaign_id: str,
    packets: list,
    apps: list,
    l2: list[L2Observation],
    step_seconds: int = 10,
    capture_start: float | None = None,
) -> list[dict[str, object]]:
    base = v2.build_rows(
        campaign_id, packets, apps, step_seconds=step_seconds, capture_start=capture_start
    )

    # v2 toma como inicio de captura la primera observación IP o EVE cuando no
    # se le da una. Se replica aquí -no se recalcula con las tramas de capa 2-
    # para que history_coverage_s signifique lo mismo en todas las filas.
    if capture_start is None:
        marcas = [item.timestamp for item in packets] + [item.timestamp for item in apps]
        if not marcas:
            marcas = [item.timestamp for item in l2]
        capture_start = min(marcas) if marcas else None

    vlans = native_vlans(l2)
    por_entidad: dict[str, list[L2Observation]] = {}
    for item in l2:
        if item.vlan == vlans[item.sender_ip]:
            por_entidad.setdefault(item.sender_ip, []).append(item)

    indice = {(row["entity_ip"], row["window_end_utc"]): row for row in base}
    for row in base:
        row.update(zero_l2_columns())
        row["native_vlan"] = vlans.get(str(row["entity_ip"]), 0)

    extra: list[dict[str, object]] = []
    for entity_ip, items in sorted(por_entidad.items()):
        primer_ancla = (math.floor(items[0].timestamp / step_seconds) + 1) * step_seconds
        ultima_ancla = math.ceil(items[-1].timestamp / step_seconds) * step_seconds
        ancla = primer_ancla
        while ancla <= ultima_ancla:
            v10 = [i for i in items if v2.in_window(i.timestamp, ancla, 10)]
            v30 = [i for i in items if v2.in_window(i.timestamp, ancla, 30)]
            v60 = [i for i in items if v2.in_window(i.timestamp, ancla, 60)]
            peticiones = [i for i in v10 if i.arp_request]

            columnas = {
                "native_vlan": vlans[entity_ip],
                "arp_request_count_10s": len(peticiones),
                "l2_frame_count_30s": len(v30),
                "arp_request_rate_10s": len(peticiones) / 10.0,
                "unique_src_mac_30s": float(len({i.src_mac for i in v30})),
                "mac_ip_binding_changes_60s": float(binding_changes(v60)),
            }

            marca = datetime.fromtimestamp(ancla, timezone.utc).isoformat()
            fila = indice.get((entity_ip, marca))
            if fila is not None:
                fila.update(columnas)
            else:
                # Entidad sin tráfico IP en esta ventana: solo existe en capa 2.
                # Es el caso que las 28 features de v2 no pueden representar.
                cobertura = 0.0
                if capture_start is not None:
                    cobertura = max(0.0, min(60.0, ancla - capture_start))
                nueva: dict[str, object] = {
                    "campaign_id": campaign_id,
                    "entity_ip": entity_ip,
                    "window_end_utc": marca,
                    "history_coverage_s": round(cobertura, 6),
                    "eligible_training": cobertura >= 60.0,
                }
                for nombre in v2.METADATA_COLUMNS[5:]:
                    nueva[nombre] = 0
                for nombre in v2.FEATURE_NAMES:
                    nueva[nombre] = 0.0
                nueva.update(columnas)
                extra.append(nueva)
            ancla += step_seconds

    filas = base + extra
    # window_end_utc siempre es UTC con el mismo formato, así que el orden
    # lexicográfico coincide con el cronológico.
    filas.sort(key=lambda row: (row["entity_ip"], row["window_end_utc"]))
    return filas


def validate_schema(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    features = schema["features"]
    if len(features) != 31:
        raise ValueError(f"el esquema debe tener 31 features, tiene {len(features)}")
    names = tuple(item["name"] for item in sorted(features, key=lambda item: item["order"]))
    if names != FEATURE_NAMES:
        raise ValueError("el orden del esquema no coincide con el extractor")
    if names[:28] != v2.FEATURE_NAMES:
        raise ValueError("las 28 primeras features deben ser las de multilayer-v2")


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METADATA_COLUMNS + FEATURE_NAMES)
        writer.writeheader()
        for row in rows:
            normalized = {
                key: f"{value:.8f}" if isinstance(value, float) else value
                for key, value in row.items()
            }
            writer.writerow(normalized)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcap", type=Path, nargs="+", required=True)
    parser.add_argument("--eve", type=Path, required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=repo_root / "configs/features/multilayer-v3.json",
    )
    # El despliegue real usa 10.10.0.0/16; v2 conserva por historia el
    # 10.20.0.0/24 del laboratorio antiguo. No se comparten valores por defecto
    # a propósito: heredar el de v2 dejaría el CSV vacío sin dar ningún error.
    parser.add_argument("--entity-network", default="10.10.0.0/16")
    # 112 = VRRP/CARP, 240 = pfsync. Sin esto cada interfaz VLAN del
    # cortafuegos vuelve a ser una entidad puntuada por la vía de la capa 2:
    # medido, 14 de 23 entidades eran exactamente eso.
    parser.add_argument("--excluir-protocolos", default="112,240")
    capture_start = parser.add_mutually_exclusive_group()
    capture_start.add_argument("--pcap-start-json", type=Path)
    capture_start.add_argument("--capture-start")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_schema(args.schema)
    entity_network = ipaddress.ip_network(args.entity_network)

    excluidos = frozenset(
        int(t.strip()) for t in args.excluir_protocolos.split(",") if t.strip()
    )

    packets = v2.load_packet_observations(args.pcap, entity_network)
    apps = v2.load_app_observations(args.eve, entity_network)
    l2 = load_l2_observations(args.pcap, entity_network, excluidos)

    capture_start = None
    if args.pcap_start_json:
        start_record = json.loads(args.pcap_start_json.read_text(encoding="utf-8"))
        if "verified_at" not in start_record:
            raise ValueError("pcap-start.json no contiene verified_at")
        capture_start = v2.parse_eve_timestamp(start_record["verified_at"])
    elif args.capture_start:
        capture_start = v2.parse_eve_timestamp(args.capture_start)

    rows = build_rows(args.campaign_id, packets, apps, l2, capture_start=capture_start)
    write_csv(rows, args.output)

    sin_ip = sum(1 for row in rows if row["packet_count_10s"] == 0)
    print(
        json.dumps(
            {
                "schema_version": "multilayer-v3",
                "feature_count": len(FEATURE_NAMES),
                "campaign_id": args.campaign_id,
                "packet_observations": len(packets),
                "application_observations": len(apps),
                "l2_observations": len(l2),
                "native_vlans": native_vlans(l2),
                "rows": len(rows),
                "rows_without_ip_packets": sin_ip,
                "eligible_training_rows": sum(bool(row["eligible_training"]) for row in rows),
                "inputs": {
                    "pcap": [
                        {"path": str(path), "sha256": v2.sha256_file(path)} for path in args.pcap
                    ],
                    "eve": {"path": str(args.eve), "sha256": v2.sha256_file(args.eve)},
                    "schema": {"path": str(args.schema), "sha256": v2.sha256_file(args.schema)},
                },
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
