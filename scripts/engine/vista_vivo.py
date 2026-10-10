"""Datos en vivo: de la trama y del evento a la variable que alimentan.

Abre la «caja negra» del motor sin reimplementarlo. Toma un tramo reciente del
anillo PCAP y de eve.json y lo pasa por la MISMA cadena que `motor_decision.py`:

    PCAP cerrados -> v3.parse_con_contexto -> sin plano de control
        -> sin copias del espejo (v3.deduplicar_espejo)
        -> v2.attribute_packets (la entidad es quien INICIA el flujo)      ┐
    eve.json -> v2.load_app_observations (solo http, dns y tls)            ├-> v3.build_rows
    PCAP -> v3.l2_en_alcance (capa 2: VLAN, MAC, ARP)                      ┘

y devuelve, por cada trama o evento que aporta a alguna variable, qué variable
actualiza, con qué aporte, en qué ventana y cuánto vale esa variable en la ventana
que lo incorpora (la fila real de build_rows). Las dos fuentes salen de la misma
interfaz de captura: el PCAP es la fuente cruda (tcpdump) y eve.json la
estructurada (Suricata la escribe tras procesar esas mismas tramas).

No escribe nada salvo un temporal con las líneas de eve.json que analiza, y no
ejecuta ninguna acción. Los valores se calculan sobre el tramo reciente: en las
ventanas cuyo inicio queda antes del tramo, el valor es parcial y se marca así.

`flujo()` es la otra mitad: la lista «tipo Wireshark» que el panel pide cada
segundo. Lee solo lo escrito desde un cursor (también el fichero que tcpdump
está escribiendo) y devuelve cada trama y cada evento con lo que se sabe de él
solo; el panel lo confirma después con `calcular()` por la misma clave.
"""
from __future__ import annotations

import collections
import ipaddress
import json
import math
import os
import re
import struct
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ / "scripts" / "features") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts" / "features"))

import extract_multilayer_v2 as v2  # noqa: E402
import extract_multilayer_v3 as v3  # noqa: E402

PASO = 10
PROTO = {1: "ICMP", 6: "TCP", 17: "UDP"}
TCP_FIN, TCP_SYN, TCP_RST, TCP_PSH, TCP_ACK = 0x01, 0x02, 0x04, 0x08, 0x10

# ------------------------------------------------------------------ esquema
def _esquema(nombre: str) -> list[dict]:
    datos = json.loads((RAIZ / "configs" / "features" / nombre).read_text(encoding="utf-8"))
    return sorted(datos["features"], key=lambda f: f["order"])


ESQUEMA_V2 = _esquema("multilayer-v2.json")
ESQUEMA_V3 = _esquema("multilayer-v3.json")
EN_MODELO = {f["name"] for f in ESQUEMA_V2}
INFO = {f["name"]: f for f in ESQUEMA_V3}          # v3 = v2 + capa 2
# Columnas de conteo que no son features del modelo pero que leen los heurísticos.
CONTEOS = {
    "flow_attempt_count_30s": {"layer": "L4", "source": "pcap", "window_seconds": 30},
    "http_request_count_60s": {"layer": "L7", "source": "eve", "window_seconds": 60},
    "dns_query_count_60s": {"layer": "L7", "source": "eve", "window_seconds": 60},
}


def ventana_de(feature: str) -> int:
    return int((INFO.get(feature) or CONTEOS.get(feature) or {}).get("window_seconds", 60))


# Qué registro alimenta cada variable, leído de build_rows (v2 y v3). Es la columna
# «Registro» de la matriz de trazabilidad.
REGISTRO = {
    "packet_rate_10s": "toda trama IPv4 atribuida a la entidad",
    "byte_rate_10s": "toda trama IPv4 atribuida (bytes IP)",
    "mean_ip_len_10s": "toda trama IPv4 atribuida (longitud IP)",
    "large_ip_ratio_10s": "trama de 500 a 1500 bytes IP",
    "unique_dst_ip_ratio_30s": "primer paquete de un flujo (destino)",
    "icmp_ratio_10s": "paquete ICMP",
    "flow_attempt_rate_10s": "primer paquete de un flujo",
    "syn_rate_10s": "TCP SYN sin ACK enviado por la entidad",
    "syn_completion_ratio_10s": "SYN enviado (denominador) y SYN-ACK recibido (numerador)",
    "rst_ratio_10s": "segmento TCP con RST, sobre todos los TCP",
    "unique_dst_port_ratio_30s": "primer paquete de un flujo con puerto destino",
    "ttl_mean_10s": "toda trama IPv4 atribuida (TTL)",
    "fragment_ratio_10s": "paquete IP fragmentado",
    "protocol_diversity_30s": "toda trama IPv4 atribuida (protocolo)",
    "tcp_retransmission_ratio_10s": "segmento TCP con datos cuya secuencia ya se vio",
    "flow_duration_mean_30s": "cualquier paquete de un flujo (duración acumulada)",
    "tx_rx_byte_ratio_30s": "trama atribuida, según sentido (enviada o recibida)",
    "http_error_ratio_60s": "evento http con estado >= 400",
    "dns_nxdomain_ratio_60s": "respuesta dns NXDOMAIN, sobre las consultas",
    "tls_session_rate_60s": "evento tls (sesiones distintas por flow_id)",
    "http_request_rate_60s": "evento http",
    "http_method_entropy_60s": "evento http (método)",
    "http_auth_failure_ratio_60s": "evento http con estado 401 o 403",
    "dns_query_rate_60s": "evento dns de consulta",
    "unique_dns_name_ratio_60s": "evento dns de consulta (nombre)",
    "tls_handshake_failure_ratio_60s": "evento tls sin versión negociada (en la práctica no ocurre)",
    "tls_version_ratio_60s": "evento tls con versión (proporción de TLS 1.3)",
    "http_status_5xx_ratio_60s": "evento http con estado 5xx",
    "arp_request_rate_10s": "trama ARP de petición",
    "unique_src_mac_30s": "trama de la entidad (MAC de origen)",
    "mac_ip_binding_changes_60s": "trama de la entidad (cambio de MAC para su IP)",
    "flow_attempt_count_30s": "primer paquete de un flujo",
    "http_request_count_60s": "evento http",
    "dns_query_count_60s": "evento dns de consulta",
}


def heuristicos_por_feature() -> dict[str, list[str]]:
    """Qué heurístico lee cada columna, sacado del código de heuristicos.py."""
    texto = (RAIZ / "scripts" / "engine" / "heuristicos.py").read_text(encoding="utf-8")
    uso: dict[str, list[str]] = collections.defaultdict(list)
    for m in re.finditer(r"^def _(\w+)\(row.*?(?=^def |\Z)", texto, re.S | re.M):
        for feat in sorted(set(re.findall(r'_n\(row, "([a-z0-9_]+)"\)', m.group(0)))):
            uso[feat].append(m.group(1))
    return dict(uso)


def matriz_trazabilidad() -> list[dict]:
    heur = heuristicos_por_feature()
    filas = []
    for nombre in [f["name"] for f in ESQUEMA_V3] + list(CONTEOS):
        info = INFO.get(nombre) or CONTEOS[nombre]
        fuente = info["source"]
        if fuente == "eve":
            parser = "load_app_observations"
        elif info["layer"] == "L2":
            parser = "l2_en_alcance"
        else:
            # Tras quitar plano de control y copias del espejo (deduplicar_espejo).
            parser = "parse_con_contexto → attribute_packets"
        if nombre in EN_MODELO:
            uso = "modelo"
        elif nombre in CONTEOS:
            uso = "conteo (no va al modelo)"
        else:
            uso = "solo extractor v3 (capa 2, fuera del scoring)"
        filas.append({
            "feature": nombre, "capa": info["layer"],
            "fuente": "eve.json" if fuente == "eve" else "PCAP (SPAN)",
            "registro": REGISTRO.get(nombre, ""), "parser": parser,
            "ventana_s": info["window_seconds"], "uso": uso,
            "heuristicos": heur.get(nombre, []),
        })
    return filas


# ------------------------------------------------------------- configuración
def config(raiz: Path = RAIZ, **explicito) -> dict:
    """Los mismos parámetros que el generador pasa al motor, leídos del mismo .toml."""
    v = {"red_entidades": None, "excluir": [], "excluir_protocolos": [],
         "directorio": "/var/lib/ppi-motor-capture", "anillo_glob": "live-*.pcap",
         "fuente": "valores por omisión"}
    for nombre in ("cyberflow.local.toml", "cyberflow.toml"):
        try:
            d = tomllib.loads((raiz / "configs" / nombre).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        red, cap = d.get("red") or {}, d.get("captura") or {}
        v.update(red_entidades=red.get("red_entidades"),
                 excluir=[str(x) for x in red.get("excluir") or []],
                 excluir_protocolos=[int(x) for x in red.get("excluir_protocolos") or []],
                 directorio=cap.get("directorio", v["directorio"]),
                 anillo_glob=cap.get("anillo_glob", v["anillo_glob"]),
                 fuente=f"configs/{nombre}")
        break
    v.update({k: val for k, val in explicito.items() if val is not None})
    return v


# ------------------------------------------------------------------- lectura
def pcap_recientes(directorio: Path, patron: str, segundos: float, ahora: float | None = None) -> list[Path]:
    """Ficheros CERRADOS del anillo (el último se está escribiendo), recientes."""
    ficheros = sorted(Path(directorio).glob(patron))
    ahora = time.time() if ahora is None else ahora
    recientes = []
    for f in ficheros[:-1]:
        try:
            if ahora - f.stat().st_mtime <= segundos:
                recientes.append(f)
        except OSError:
            continue
    return recientes


def eve_reciente(eve: Path, segundos: float, max_bytes: int = 8 << 20) -> list[tuple[int, str, dict]]:
    """Líneas de eve.json de los últimos `segundos` (por timestamp del evento)."""
    tam = eve.stat().st_size
    inicio = max(0, tam - max_bytes)
    with eve.open("rb") as fh:
        fh.seek(inicio)
        datos = fh.read()
    if inicio > 0:
        corte = datos.find(b"\n") + 1
        datos, inicio = datos[corte:], inicio + corte
    eventos, pos = [], inicio
    for raw in datos.split(b"\n"):
        if raw.strip():
            try:
                ev = json.loads(raw)
                if ev.get("timestamp"):
                    eventos.append((pos, raw.strip().decode("utf-8", "replace"), ev))
            except (ValueError, UnicodeDecodeError):
                pass
        pos += len(raw) + 1
    if not eventos:
        return []
    ultimo = max(v2.parse_eve_timestamp(e["timestamp"]) for _, _, e in eventos)
    return [x for x in eventos if v2.parse_eve_timestamp(x[2]["timestamp"]) >= ultimo - segundos]


# ------------------------------------------------------------------ aportes
def aportes_paquete(o, p) -> list[tuple[str, str]]:
    a = [("packet_rate_10s", "+1"), ("byte_rate_10s", f"+{o.ip_length} B")]
    if o.flow_attempt:
        a += [("flow_attempt_rate_10s", "+1"), ("flow_attempt_count_30s", "+1"),
              ("unique_dst_ip_ratio_30s", f"destino {o.peer_ip}")]
        if o.target_port > 0:
            a.append(("unique_dst_port_ratio_30s", f"puerto {o.target_port}"))
    if o.syn:
        a += [("syn_rate_10s", "+1"), ("syn_completion_ratio_10s", "+1 intento")]
    if o.syn_ack:
        a.append(("syn_completion_ratio_10s", "+1 completado"))
    if o.rst:
        a.append(("rst_ratio_10s", "+1 RST"))
    if o.retransmission:
        a.append(("tcp_retransmission_ratio_10s", "+1 retransmisión"))
    if o.fragmented:
        a.append(("fragment_ratio_10s", "+1"))
    if o.protocol == 1:
        a.append(("icmp_ratio_10s", "+1"))
    if 500 <= o.ip_length <= 1500:
        a.append(("large_ip_ratio_10s", "+1"))
    return a


def notable(o) -> bool:
    return bool(o.flow_attempt or o.syn or o.syn_ack or o.rst or o.retransmission
                or o.fragmented or o.protocol == 1)


def nombre_flags(f: int) -> str:
    return "-".join(n for b, n in ((TCP_SYN, "SYN"), (TCP_FIN, "FIN"), (TCP_RST, "RST"),
                                   (TCP_PSH, "PSH"), (TCP_ACK, "ACK")) if f & b)


def evento_paquete(p, o) -> str:
    if p.protocol == 6:
        nombre = nombre_flags(p.tcp_flags) or "TCP"
        if o.retransmission:
            return f"{nombre} retransmisión"
        return f"{nombre} {p.tcp_payload_length} B datos" if p.tcp_payload_length else nombre
    if p.protocol == 1:
        return f"ICMP tipo {p.icmp_type}"
    return PROTO.get(p.protocol, f"proto {p.protocol}")


def aportes_evento(a) -> tuple[str, list[tuple[str, str]]]:
    if a.kind == "http":
        ap = [("http_request_rate_60s", "+1"), ("http_request_count_60s", "+1"),
              ("http_method_entropy_60s", a.method or "sin método")]
        if a.error:
            ap.append(("http_error_ratio_60s", f"+1 (estado {a.status})"))
        if a.status in (401, 403):
            ap.append(("http_auth_failure_ratio_60s", f"+1 ({a.status})"))
        if 500 <= a.status <= 599:
            ap.append(("http_status_5xx_ratio_60s", f"+1 ({a.status})"))
        return f"HTTP {a.method or '?'} {a.status or ''}".strip(), ap
    if a.kind == "dns_query":
        return f"DNS consulta {a.dns_name}".strip(), [
            ("dns_query_rate_60s", "+1"), ("dns_query_count_60s", "+1"),
            ("unique_dns_name_ratio_60s", a.dns_name or "sin nombre"),
            ("dns_nxdomain_ratio_60s", "+1 consulta (denominador)")]
    if a.kind == "dns_nxdomain":
        return "DNS respuesta NXDOMAIN", [("dns_nxdomain_ratio_60s", "+1 NXDOMAIN")]
    if a.kind == "tls":
        ap = [("tls_session_rate_60s", "sesión " + str(a.event_key))]
        if a.tls_version:
            ap.append(("tls_version_ratio_60s", a.tls_version))
        else:
            ap.append(("tls_handshake_failure_ratio_60s", "+1 sin versión"))
        return f"TLS {a.tls_version or 'sin versión'}", ap
    return a.kind, []


_KIND_DE_EVENTO = {"http": {"http"}, "dns": {"dns_query", "dns_nxdomain"}, "tls": {"tls"}}


def _apps_de(eventos, red) -> list:
    """Pasa las líneas por el parser de eventos del motor (v2.load_app_observations)."""
    if not eventos:
        return []
    fd, tmp = tempfile.mkstemp(prefix="cyberflow-vivo-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            for _, linea, _ in eventos:
                fh.write(linea + "\n")
        return v2.load_app_observations(Path(tmp), red)
    finally:
        os.unlink(tmp)


def _emparejar_eve(eventos, apps):
    """Cada observación con su evento: el parser las emite en el orden del fichero."""
    pares, k, ignorados = [], 0, collections.Counter()
    for pos, _linea, ev in eventos:
        tipo = ev.get("event_type")
        if k < len(apps):
            a = apps[k]
            if (a.kind in _KIND_DE_EVENTO.get(tipo, ())
                    and a.timestamp == v2.parse_eve_timestamp(ev["timestamp"])
                    and a.entity_ip in (ev.get("src_ip"), ev.get("dest_ip"))):
                pares.append((pos, ev, a))
                k += 1
                continue
        ignorados[tipo or "sin tipo"] += 1
    return pares, ignorados


# ----------------------------------------------------------------- cálculo
def _ancla(ts: float) -> float:
    return math.ceil(ts / PASO) * PASO


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _hora(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _features(aportes, fila, ancla, inicio_fuente):
    salida = []
    for feat, aporte in aportes:
        vs = ventana_de(feat)
        valor = fila.get(feat) if fila else None
        salida.append({
            "feature": feat, "aporte": aporte, "ventana_s": vs,
            "valor": None if valor is None else round(float(valor), 6),
            "parcial": inicio_fuente is None or (ancla - vs) < inicio_fuente,
            "uso": ("modelo" if feat in EN_MODELO else
                    "conteo" if feat in CONTEOS else "capa 2 (fuera del scoring)"),
        })
    return salida


def calcular(eve_path: Path, cfg: dict, segundos_pcap: float = 45, segundos_eve: float = 70,
             limite: int = 150, todos: bool = False, ahora: float | None = None) -> dict:
    t0 = time.time()
    red = ipaddress.ip_network(cfg["red_entidades"], strict=False)
    protos = frozenset(int(p) for p in cfg.get("excluir_protocolos") or [])
    redes_excluidas = [ipaddress.ip_network(r, strict=False) for r in cfg.get("excluir") or []]

    def excluida(ip: str) -> bool:
        try:
            return any(ipaddress.ip_address(ip) in r for r in redes_excluidas)
        except ValueError:
            return False

    # --- PCAP: misma cadena que el motor -------------------------------------
    ficheros = pcap_recientes(Path(cfg["directorio"]), cfg["anillo_glob"], segundos_pcap, ahora)
    contextos, meta, l2, l2meta, ilegibles = [], {}, [], {}, []
    c = collections.Counter()
    for f in ficheros:
        try:
            tramas = list(v2.iter_pcap_frames(f))
        except Exception as exc:  # p. ej. el primer fichero de cada arranque, de tcpdump
            ilegibles.append({"fichero": f.name, "motivo": type(exc).__name__})
            continue
        for idx, (ts, frame) in enumerate(tramas, start=1):
            c["tramas"] += 1
            o2 = v3.l2_en_alcance(ts, frame, red, protos)
            if o2 is not None:
                l2.append(o2)
                l2meta[id(o2)] = {"fichero": f.name, "trama": idx,
                                  "mac_dst": v3.format_mac(frame[0:6])}
            ctx = v3.parse_con_contexto(ts, frame)
            if ctx is None:
                c["no_ipv4"] += 1
                continue
            if ctx.packet.protocol in protos:
                c["plano_control"] += 1
                continue
            contextos.append(ctx)
            meta[id(ctx.packet)] = {"fichero": f.name, "trama": idx, "vlan": ctx.vlan,
                                    "mac_src": v3.format_mac(frame[6:12]),
                                    "mac_dst": v3.format_mac(frame[0:6])}
    paquetes, c["duplicados_espejo"] = v3.deduplicar_espejo(contextos)
    obs = v2.attribute_packets(paquetes, red)

    # Emparejar cada observación con su paquete: attribute_packets recorre los
    # paquetes ordenados por tiempo y solo emite los que caen en el alcance.
    pares, j = [], 0
    for p in sorted(paquetes, key=lambda x: x.timestamp):
        if j < len(obs):
            o = obs[j]
            if (o.timestamp == p.timestamp and o.ip_length == p.ip_length
                    and o.protocol == p.protocol and o.ttl == p.ttl
                    and {o.entity_ip, o.peer_ip} == {p.src_ip, p.dst_ip}):
                pares.append((p, o))
                j += 1
                continue
        c["fuera_de_alcance"] += 1
    c["sin_emparejar"] = len(obs) - j

    # --- eve.json -------------------------------------------------------------
    eventos = eve_reciente(eve_path, segundos_eve) if eve_path and eve_path.exists() else []
    apps = _apps_de(eventos, red)
    pares_eve, ignorados = _emparejar_eve(eventos, apps)

    # --- filas reales de features (v3 = v2 + capa 2) --------------------------
    marcas = [o.timestamp for o in obs] + [a.timestamp for a in apps] + [x.timestamp for x in l2]
    filas = {}
    if marcas:
        for fila in v3.build_rows("panel-vivo", obs, apps, l2, step_seconds=PASO,
                                  capture_start=min(marcas)):
            filas[(fila["entity_ip"], fila["window_end_utc"])] = fila
    inicio_pcap = min((p.timestamp for p, _ in pares), default=None)
    if l2:
        inicio_pcap = min(x for x in (inicio_pcap, min(o.timestamp for o in l2)) if x is not None)
    inicio_eve = min((a.timestamp for a in apps), default=None)

    # --- vista B: tramas PCAP -------------------------------------------------
    tramas_vista = []
    for p, o in pares:
        if excluida(o.entity_ip):
            c["entidad_excluida"] += 1
            continue
        if not todos and not notable(o):
            continue
        ancla = _ancla(o.timestamp)
        m = meta.get(id(p), {})
        tramas_vista.append({
            "ts": o.timestamp, "hora": _hora(o.timestamp), "entidad": o.entity_ip,
            "vlan": m.get("vlan"), "mac_src": m.get("mac_src"), "mac_dst": m.get("mac_dst"),
            "ip_src": p.src_ip, "ip_dst": p.dst_ip, "puerto_src": p.src_port,
            "puerto_dst": p.dst_port, "proto": PROTO.get(p.protocol, str(p.protocol)),
            "evento": evento_paquete(p, o), "longitud": p.ip_length, "ttl": p.ttl,
            "sentido": "enviada" if o.outbound else "recibida",
            "ventana_fin": _iso(ancla),
            "features": _features(aportes_paquete(o, p),
                                  filas.get((o.entity_ip, _iso(ancla))), ancla, inicio_pcap),
            "fuente": {"fichero": m.get("fichero"), "trama": m.get("trama")},
        })
    for x in l2:
        if not x.arp_request or excluida(x.sender_ip):
            continue
        ancla = _ancla(x.timestamp)
        m = l2meta.get(id(x), {})
        tramas_vista.append({
            "ts": x.timestamp, "hora": _hora(x.timestamp), "entidad": x.sender_ip,
            "vlan": x.vlan, "mac_src": x.src_mac, "mac_dst": m.get("mac_dst"),
            "ip_src": x.sender_ip, "ip_dst": "", "puerto_src": 0, "puerto_dst": 0,
            "proto": "ARP", "evento": "ARP petición", "longitud": None, "ttl": None,
            "sentido": "enviada", "ventana_fin": _iso(ancla),
            "features": _features([("arp_request_rate_10s", "+1"),
                                   ("unique_src_mac_30s", x.src_mac)],
                                  filas.get((x.sender_ip, _iso(ancla))), ancla, inicio_pcap),
            "fuente": {"fichero": m.get("fichero"), "trama": m.get("trama")},
        })
    tramas_vista.sort(key=lambda r: r["ts"], reverse=True)

    # --- vista A: eventos de eve.json ----------------------------------------
    eventos_vista = []
    for pos, ev, a in pares_eve:
        if excluida(a.entity_ip):
            continue
        ancla = _ancla(a.timestamp)
        titulo, aportes = aportes_evento(a)
        eventos_vista.append({
            "ts": a.timestamp, "hora": _hora(a.timestamp), "entidad": a.entity_ip,
            "evento": titulo, "tipo": ev.get("event_type"),
            "origen": f"{ev.get('src_ip')}:{ev.get('src_port', '')}",
            "destino": f"{ev.get('dest_ip')}:{ev.get('dest_port', '')}",
            "vlan": (ev.get("vlan") or [None])[0] if isinstance(ev.get("vlan"), list) else ev.get("vlan"),
            "ventana_fin": _iso(ancla),
            "features": _features(aportes, filas.get((a.entity_ip, _iso(ancla))), ancla, inicio_eve),
            "fuente": {"fichero": eve_path.name, "byte": pos, "flow_id": ev.get("flow_id")},
        })
    eventos_vista.sort(key=lambda r: r["ts"], reverse=True)

    def tramo(marcas_):
        if not marcas_:
            return None
        return {"desde": _iso(min(marcas_)), "hasta": _iso(max(marcas_)),
                "segundos": round(max(marcas_) - min(marcas_), 1)}

    return {
        "calculado": _iso(time.time()), "segundos_calculo": round(time.time() - t0, 3),
        "config": {"red_entidades": str(red), "excluir": cfg.get("excluir") or [],
                   "excluir_protocolos": sorted(protos), "fuente": cfg.get("fuente"),
                   "anillo": f"{cfg['directorio']}/{cfg['anillo_glob']}"},
        "pcap": {"ficheros": [f.name for f in ficheros], "ilegibles": ilegibles,
                 "tramo": tramo([p.timestamp for p, _ in pares]),
                 "tramas": c["tramas"], "no_ipv4": c["no_ipv4"],
                 "plano_control": c["plano_control"], "duplicados_espejo": c["duplicados_espejo"],
                 "fuera_de_alcance": c["fuera_de_alcance"], "atribuidas": len(pares),
                 "entidad_excluida": c["entidad_excluida"], "sin_emparejar": c["sin_emparejar"],
                 "mostradas": min(len(tramas_vista), limite), "total_filtradas": len(tramas_vista),
                 "filtro": "todas las tramas atribuidas" if todos else
                 "solo tramas con aporte específico (intento de flujo, SYN, SYN-ACK, RST, "
                 "retransmisión, fragmento, ICMP, ARP)"},
        "eve": {"fichero": str(eve_path) if eve_path else None,
                "tramo": tramo([a.timestamp for _, _, a in pares_eve]),
                "eventos": len(eventos), "aportan": len(pares_eve),
                "ignorados": dict(ignorados.most_common()),
                "mostrados": min(len(eventos_vista), limite)},
        "tramas": tramas_vista[:limite],
        "eventos": eventos_vista[:limite],
    }


_CACHE: dict = {}


def calcular_con_cache(eve_path: Path, cfg: dict, todos: bool = False, ttl: float = 8.0,
                       limite: int = 150) -> dict:
    """Evita recalcular en cada refresco del panel: la clave son los ficheros y su tamaño."""
    try:
        firma = (tuple((f.name, f.stat().st_mtime) for f in
                       pcap_recientes(Path(cfg["directorio"]), cfg["anillo_glob"], 45)),
                 eve_path.stat().st_size if eve_path and eve_path.exists() else 0, todos, limite)
    except OSError:
        firma = None
    ahora = time.time()
    previo = _CACHE.get("valor")
    if previo is not None and firma is not None and _CACHE.get("firma") == firma \
            and ahora - _CACHE.get("t", 0) < ttl:
        return previo
    valor = calcular(eve_path, cfg, todos=todos, limite=limite)
    _CACHE.update(valor=valor, firma=firma, t=ahora)
    return valor


# ------------------------------------------------------------------- flujo
# La vista «tipo Wireshark»: cada llamada lee SOLO lo que se ha escrito desde la
# anterior, a partir de un cursor que guarda el navegador (fichero, byte y número
# de trama del anillo; byte de eve.json). El servidor no guarda estado, así que
# dos administradores mirando a la vez no se pisan.
#
# Incluye el fichero del anillo que tcpdump está escribiendo: la unidad lo lanza
# con -U, que vacía cada paquete al disco, así que la trama aparece en cuanto se
# captura. Se lee hasta el último registro completo y el resto queda para la
# siguiente llamada.
#
# Lo que se puede saber trama a trama sin estado se muestra en el acto, marcado
# como PROVISIONAL: la entidad y el aporte según las flags. Lo que necesita
# contexto -quién inició el flujo, si es retransmisión, el valor de la variable
# en su ventana- solo lo sabe la cadena del motor, que trabaja con ficheros
# cerrados; el panel lo cruza después con /api/vivo por la clave fichero#trama
# (PCAP) o por el byte (eve.json), y la fila pasa a «confirmada».

ETHERTYPE = {0x0806: "ARP", 0x86DD: "IPv6", 0x88CC: "LLDP", 0x8809: "LACP", 0x88A8: "QinQ"}
MAX_LECTURA = 8 << 20          # bytes por fuente y llamada
MAX_RETRASO = 32 << 20         # si se acumula más, se salta al presente y se dice
MAX_CAPTURADA = 262144         # snaplen máximo de tcpdump; más es un registro roto


def _leer_registros(f: Path, desde: int, max_bytes: int = MAX_LECTURA):
    """Tramas completas de un PCAP a partir del byte `desde`. Devuelve (tramas, byte siguiente)."""
    with f.open("rb") as fh:
        cab = fh.read(24)
        if len(cab) < 24:
            return [], 0                       # tcpdump aún no escribió la cabecera
        endian, div = v2._pcap_format(cab[:4])
        pos = max(desde, 24)
        fh.seek(pos)
        datos = fh.read(max_bytes)
    reg = struct.Struct(endian + "IIII")
    tramas, i = [], 0
    while i + 16 <= len(datos):
        seg, frac, cap, _ = reg.unpack_from(datos, i)
        if cap > MAX_CAPTURADA:
            raise ValueError("registro PCAP corrupto")
        if i + 16 + cap > len(datos):
            break                              # registro a medio escribir
        tramas.append((seg + frac / div, datos[i + 16:i + 16 + cap]))
        i += 16 + cap
    return tramas, pos + i


def _ethertype(frame: bytes) -> tuple[int, int, int]:
    """(ethertype, VLAN exterior, desplazamiento de la carga)."""
    if len(frame) < 14:
        return 0, 0, 14
    et, off, vlan = struct.unpack("!H", frame[12:14])[0], 14, 0
    while et in (0x8100, 0x88A8) and len(frame) >= off + 4:
        if not vlan:
            vlan = struct.unpack("!H", frame[off:off + 2])[0] & 0x0FFF
        et = struct.unpack("!H", frame[off + 2:off + 4])[0]
        off += 4
    return et, vlan, off


def _feat(feature: str, aporte: str) -> dict:
    return {"feature": feature, "aporte": aporte, "ventana_s": ventana_de(feature),
            "uso": ("modelo" if feature in EN_MODELO else
                    "conteo" if feature in CONTEOS else "capa 2 (fuera del scoring)")}


def _trama_flujo(ts, frame, fichero, n, red, protos, excluida) -> tuple[dict, object]:
    et, vlan, off = _ethertype(frame)
    r = {"k": f"{fichero}#{n}", "fichero": fichero, "trama": n, "ts": ts, "hora": _hora(ts),
         "vlan": vlan or None, "mac_src": v3.format_mac(frame[6:12]),
         "mac_dst": v3.format_mac(frame[0:6]), "capturada": len(frame),
         "ip_src": "", "ip_dst": "", "puerto_src": 0, "puerto_dst": 0, "flags": "",
         "longitud": None, "ttl": None, "entidad": None, "aportes": [], "notable": False}
    ctx = v3.parse_con_contexto(ts, frame) if et == 0x0800 else None
    if ctx is not None:
        p = ctx.packet
        r.update(ip_src=p.src_ip, ip_dst=p.dst_ip, puerto_src=p.src_port, puerto_dst=p.dst_port,
                 proto=PROTO.get(p.protocol, f"IP/{p.protocol}"), longitud=p.ip_length, ttl=p.ttl,
                 ip_id=ctx.ip_id, fragmentada=p.fragmented)
        syn = syn_ack = rst = False
        if p.protocol == 6:
            r.update(flags=nombre_flags(p.tcp_flags), seq=p.tcp_seq, datos=p.tcp_payload_length)
            syn = bool(p.tcp_flags & TCP_SYN) and not p.tcp_flags & TCP_ACK
            syn_ack = bool(p.tcp_flags & TCP_SYN) and bool(p.tcp_flags & TCP_ACK)
            rst = bool(p.tcp_flags & TCP_RST)
            r["info"] = (f"{p.src_port} → {p.dst_port} [{r['flags'] or '—'}]"
                         + (f" {p.tcp_payload_length} B datos" if p.tcp_payload_length else ""))
        elif p.protocol == 17:
            r["info"] = f"{p.src_port} → {p.dst_port}"
        elif p.protocol == 1:
            r["info"] = f"tipo {p.icmp_type}"
        else:
            r["info"] = f"protocolo IP {p.protocol}"
        en_src, en_dst = v2._in_scope(p.src_ip, red), v2._in_scope(p.dst_ip, red)
        if p.protocol in protos:
            r["estado"] = "plano de control"
            return r, None
        if not (en_src or en_dst):
            r["estado"] = "fuera de la red de entidades"
            return r, ctx
        # Sin estado no se sabe quién inició el flujo: el SYN lo inicia quien lo
        # envía y el SYN-ACK lo recibe quien lo inició; en lo demás, la IP de la red.
        entidad = p.dst_ip if (syn_ack and en_dst) or not en_src else p.src_ip
        r["entidad"] = entidad
        if excluida(entidad):
            r["estado"] = "entidad excluida"
            return r, ctx
        a = [_feat("packet_rate_10s", "+1"), _feat("byte_rate_10s", f"+{p.ip_length} B")]
        if syn:
            a += [_feat("flow_attempt_rate_10s", "+1"), _feat("syn_rate_10s", "+1"),
                  _feat("syn_completion_ratio_10s", "+1 intento")]
        if syn_ack:
            a.append(_feat("syn_completion_ratio_10s", "+1 completado"))
        if rst:
            a.append(_feat("rst_ratio_10s", "+1 RST"))
        if p.fragmented:
            a.append(_feat("fragment_ratio_10s", "+1"))
        if p.protocol == 1:
            a.append(_feat("icmp_ratio_10s", "+1"))
        if 500 <= p.ip_length <= 1500:
            a.append(_feat("large_ip_ratio_10s", "+1"))
        r.update(estado="aporta", aportes=a,
                 notable=syn or syn_ack or rst or p.fragmented or p.protocol == 1)
        return r, ctx
    r["proto"] = ETHERTYPE.get(et, f"0x{et:04x}")
    if et == 0x0806 and len(frame) >= off + 28:
        oper = struct.unpack("!H", frame[off + 6:off + 8])[0]
        spa = ".".join(str(b) for b in frame[off + 14:off + 18])
        tpa = ".".join(str(b) for b in frame[off + 24:off + 28])
        r.update(ip_src=spa, ip_dst=tpa, info=(f"¿quién tiene {tpa}? dile a {spa}" if oper == 1
                                               else f"{spa} está en {r['mac_src']}"))
        o2 = v3.l2_en_alcance(ts, frame, red, protos)
        if o2 is None:
            r["estado"] = "fuera de la red de entidades"
        elif excluida(spa):
            r.update(entidad=spa, estado="entidad excluida")
        elif o2.arp_request:
            r.update(entidad=spa, estado="aporta", notable=True,
                     aportes=[_feat("arp_request_rate_10s", "+1"),
                              _feat("unique_src_mac_30s", o2.src_mac)])
        else:
            r.update(entidad=spa, estado="respuesta ARP (no aporta)")
        return r, None
    r.update(info="", estado="sin IPv4 (no aporta)")
    return r, None


def _info_evento(ev: dict) -> str:
    tipo = ev.get("event_type")
    if tipo == "http":
        h = ev.get("http") or {}
        return (f"{h.get('http_method', '?')} {h.get('hostname', '')}{h.get('url', '')}"
                f" → {h.get('status', '—')}")
    if tipo == "dns":
        d = ev.get("dns") or {}
        nombre = v2._dns_query_name(d)
        if d.get("type") == "answer":
            return f"respuesta {d.get('rcode', '')} {nombre}".strip()
        return f"consulta {d.get('rrtype', '')} {nombre}".strip()
    if tipo == "tls":
        t = ev.get("tls") or {}
        return f"{t.get('version') or 'sin versión'} SNI {t.get('sni') or '—'}"
    if tipo == "flow":
        f = ev.get("flow") or {}
        return (f"{ev.get('app_proto', '')} {f.get('pkts_toserver', 0)}+{f.get('pkts_toclient', 0)} pkts, "
                f"{f.get('state', '')}").strip()
    if tipo == "alert":
        return (ev.get("alert") or {}).get("signature", "")
    if tipo == "stats":
        return "estadísticas internas de Suricata"
    return ""


def _flujo_pcap(cfg, cur, red, protos, excluida, todos, max_filas) -> tuple[dict, dict]:
    directorio, patron = Path(cfg["directorio"]), cfg["anillo_glob"]
    ficheros = sorted(directorio.glob(patron))
    salida = {"ficheros": len(ficheros), "activo": None, "tam_activo": 0, "nuevas": 0,
              "bytes": 0, "omitido_bytes": 0, "aportan": 0, "estados": {}, "filas": [],
              "ultimo_ts": None, "ilegibles": []}
    if not ficheros:
        return salida, {}
    nombres = [f.name for f in ficheros]
    activo = ficheros[-1]
    salida["activo"] = activo.name
    try:
        salida["tam_activo"] = activo.stat().st_size
    except OSError:
        pass
    pf, po, pn = cur.get("pf"), int(cur.get("po") or 0), int(cur.get("pn") or 0)
    if pf is None:
        idx, po, pn = len(ficheros) - 1, 0, 0       # primera llamada: el fichero en curso
    elif pf in nombres:
        idx = nombres.index(pf)
    else:                                           # podado: el siguiente que siga existiendo
        idx = next((i for i, n in enumerate(nombres) if n > pf), len(ficheros) - 1)
        po, pn = 0, 0
    try:
        pendiente = sum(f.stat().st_size for f in ficheros[idx:]) - po
    except OSError:
        pendiente = 0
    if pendiente > MAX_RETRASO:                     # demasiado atrás: al presente
        salida["omitido_bytes"] = pendiente
        idx, po, pn = len(ficheros) - 1, 0, 0

    estados = collections.Counter()
    filas, contextos, presupuesto = [], [], MAX_LECTURA
    while idx < len(ficheros) and presupuesto > 0:
        f = ficheros[idx]
        try:
            tramas, nuevo = _leer_registros(f, po, presupuesto)
        except (OSError, ValueError) as exc:
            salida["ilegibles"].append({"fichero": f.name, "motivo": type(exc).__name__})
            tramas, nuevo = [], None
        for ts, frame in tramas:
            pn += 1
            r, ctx = _trama_flujo(ts, frame, f.name, pn, red, protos, excluida)
            filas.append(r)
            if ctx is not None:
                contextos.append((ctx, r))
        if nuevo is not None:
            presupuesto -= max(0, nuevo - max(po, 24))
            salida["bytes"] += max(0, nuevo - max(po, 24))
        if idx == len(ficheros) - 1:
            po = nuevo if nuevo is not None else po
            break
        try:
            completo = nuevo is None or nuevo >= f.stat().st_size
        except OSError:
            completo = True
        if not completo and tramas:                 # se acabó el presupuesto: seguir ahí
            po = nuevo
            break
        # Cerrado y leído entero, o con una cola truncada que nunca se completará.
        idx, po, pn = idx + 1, 0, 0                 # fichero cerrado y leído entero

    # Copias del espejo dentro de lo leído: la misma función del motor.
    if contextos:
        conservados, _ = v3.deduplicar_espejo([c for c, _ in contextos])
        vivos = {id(p) for p in conservados}
        for c, r in contextos:
            if id(c.packet) not in vivos:
                r.update(estado="copia del espejo (descartada)", aportes=[], notable=False)
    for r in filas:
        estados[r["estado"]] += 1
    salida.update(nuevas=len(filas), aportan=estados["aporta"], estados=dict(estados),
                  ultimo_ts=max((r["ts"] for r in filas), default=None))
    elegidas = [r for r in filas if todos or (r["estado"] == "aporta" and r["notable"])]
    salida["filas"] = elegidas[-max_filas:]
    salida["no_enviadas"] = max(0, len(elegidas) - max_filas)
    return salida, {"pf": ficheros[idx].name if idx < len(ficheros) else activo.name,
                    "po": po, "pn": pn}


def _flujo_eve(eve_path, cur, red, excluida, todos, max_filas) -> tuple[dict, dict]:
    salida = {"fichero": str(eve_path) if eve_path else None, "tam": 0, "nuevos": 0,
              "bytes": 0, "omitido_bytes": 0, "aportan": 0, "tipos": {}, "filas": [],
              "ultimo_ts": None}
    if not eve_path or not eve_path.exists():
        return salida, {}
    tam = eve_path.stat().st_size
    salida["tam"] = tam
    eo = cur.get("eo")
    eo = None if eo is None else int(eo)
    alinear = False
    if eo is None:
        eo, alinear = max(0, tam - (128 << 10)), True   # primera llamada: un poco de historia
    elif eo > tam:
        eo = 0                                          # eve.json rotado
    if tam - eo > MAX_RETRASO:
        salida["omitido_bytes"] = tam - eo
        eo, alinear = tam - (1 << 20), True
    with eve_path.open("rb") as fh:
        fh.seek(eo)
        datos = fh.read(MAX_LECTURA)
    if alinear and eo > 0:
        corte = datos.find(b"\n") + 1
        datos, eo = datos[corte:], eo + corte
    fin = datos.rfind(b"\n") + 1                        # la última línea puede ir a medias
    datos = datos[:fin]
    eventos, tipos, pos = [], collections.Counter(), eo
    for raw in datos.split(b"\n"):
        limpia = raw.strip()
        if limpia:
            try:
                ev = json.loads(limpia)
                if ev.get("timestamp"):
                    eventos.append((pos, limpia.decode("utf-8", "replace"), ev))
                    tipos[ev.get("event_type") or "sin tipo"] += 1
            except (ValueError, UnicodeDecodeError):
                pass
        pos += len(raw) + 1
    pares, _ = _emparejar_eve(eventos, _apps_de(eventos, red))
    por_pos = {pos_: a for pos_, _, a in pares}
    filas = []
    for pos_, linea, ev in eventos:
        ts = v2.parse_eve_timestamp(ev["timestamp"])
        a = por_pos.get(pos_)
        r = {"k": str(pos_), "byte": pos_, "ts": ts, "hora": _hora(ts), "tipo": ev.get("event_type"),
             "origen": f"{ev.get('src_ip', '')}:{ev.get('src_port', '')}".rstrip(":"),
             "destino": f"{ev.get('dest_ip', '')}:{ev.get('dest_port', '')}".rstrip(":"),
             "proto": ev.get("proto") or "", "info": _info_evento(ev), "entidad": None,
             "evento": ev.get("event_type"), "aportes": [],
             "crudo": linea if len(linea) <= 1500 else linea[:1500] + " …"}
        if a is not None:
            titulo, aportes = aportes_evento(a)
            r.update(entidad=a.entity_ip, evento=titulo)
            if excluida(a.entity_ip):
                r["estado"] = "entidad excluida"
            else:
                r.update(estado="aporta", aportes=[_feat(f_, ap) for f_, ap in aportes])
        else:
            r["estado"] = ("no lo usa el motor" if ev.get("event_type") not in _KIND_DE_EVENTO
                           else "fuera de la red de entidades o sin aporte")
        filas.append(r)
    elegidas = [r for r in filas if todos or r["estado"] == "aporta"]
    salida.update(nuevos=len(eventos), bytes=len(datos), tipos=dict(tipos.most_common()),
                  aportan=sum(1 for r in filas if r["estado"] == "aporta"),
                  ultimo_ts=max((r["ts"] for r in filas), default=None),
                  filas=elegidas[-max_filas:], no_enviadas=max(0, len(elegidas) - max_filas))
    return salida, {"eo": eo + len(datos)}


def flujo(eve_path: Path | None, cfg: dict, cursor: dict | None = None, todos: bool = False,
          max_filas: int = 300) -> dict:
    """Lo nuevo desde `cursor` en las dos fuentes, y el cursor para la siguiente llamada."""
    t0 = time.time()
    red = ipaddress.ip_network(cfg["red_entidades"], strict=False)
    protos = frozenset(int(p) for p in cfg.get("excluir_protocolos") or [])
    redes_excluidas = [ipaddress.ip_network(r, strict=False) for r in cfg.get("excluir") or []]

    def excluida(ip: str) -> bool:
        try:
            return any(ipaddress.ip_address(ip) in r for r in redes_excluidas)
        except ValueError:
            return False

    cur = dict(cursor or {})
    pcap, cur_p = _flujo_pcap(cfg, cur, red, protos, excluida, todos, max_filas)
    eve, cur_e = _flujo_eve(eve_path, cur, red, excluida, todos, max_filas)
    return {"servidor": time.time(), "segundos_calculo": round(time.time() - t0, 3),
            "cursor": {**cur_p, **cur_e}, "pcap": pcap, "eve": eve}
