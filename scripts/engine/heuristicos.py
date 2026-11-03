#!/usr/bin/env python3
"""Heurísticos deterministas: complemento del modelo, no su reemplazo.

Por qué existen. El modelo *one-class* aprende "lo normal" y marca lo que se
desvía, pero mide flojo justo en algunos patrones de ataque muy concretos
—fuerza bruta, y sobre todo DNS de alta entropía, donde en la corrida real
(nota M) detectó 0 %—. Estos heurísticos cubren esos huecos con **reglas
explícitas** sobre las mismas variables L3/L4/L7 de la ventana.

Honestidad metodológica: sus umbrales son **criterio razonado**, versionados y
configurables, **NO** calibrados estadísticamente como el umbral del modelo. Se
declara así; no se disfraza de un rigor que no tienen.

Contrato: `evaluar(row, umbrales=None)` recibe el dict de features de UNA ventana
y devuelve el veredicto MÁS severo que dispare, o `None` si ninguno.

    {"heuristico": "brute_force", "accion": "BLOCK", "motivo": "..."}

`accion` es "LIMIT" (degradar la tasa, reversible) o "BLOCK" (cortar). La decisión
LIMIT↔BLOCK es por heurístico: los de alta confianza (fuerza bruta, escaneo)
cortan; los ambiguos (volumen HTTP, entropía DNS) limitan. Ver
01-arquitectura/DISENO-ENFORCEMENT.md (orquestación).
"""
from __future__ import annotations

# Subir esta versión cada vez que cambien los umbrales; queda en el registro y en
# el feed para poder reproducir por qué se tomó una decisión.
VERSION_UMBRALES = "2026-11-03.2"
# 2026-11-03.2: nueva regla icmp_flood. Desde esta version el modelo solo ya no
# publica acciones (las deja para revision humana: ver publicar_feed.py), y la
# inundacion ICMP era el unico escenario que dependia de el. Calibrada sobre
# 3 119 148 ventanas reales (multilayer-v3, 3-nov): en ventanas con >= 50 % ICMP,
# lo legitimo llega como mucho a 43,6 paquetes/s (.21) y el ping normal de la Kali
# a 25-30; el flood de la demo L3 da 318-3998. Umbral 200 paquetes/s con >= 80 %
# ICMP: 4,6 veces lo legitimo mas alto y ninguna IP salvo la Kali lo alcanza.
# 2026-11-03.1: la rama de ráfaga de port_scan bloqueaba a un cliente legítimo
# (250 descargas HTTP al puerto 80 en 30 s): el espejo SPAN no atribuye el
# SYN-ACK, así que «0 % completados» sale también en tráfico web sano. Un escaneo
# toca MUCHOS puertos (ratio ~0,45 por el espejo); una ráfaga web, uno (~0,004).
# La rama exige ahora un mínimo de variedad de puertos (0,2), con margen de sobra
# bajo el 0,45 del escaneo. Medido 3-nov: 9 BLOCK falsos a 10.10.20.21 -> 0.
# Además, http_abuse contaba doble: el espejo entrega cada evento HTTP dos veces
# (VLAN 20 y 30). Un cliente a 1 petición/s (60/min reales) daba 111-122 «req/60s»
# y recibía LIMIT. El umbral se expresa ahora en eventos del espejo: 200 = 100
# peticiones reales por minuto. El flood de la demo (250 en ~10 s) cuenta ~470.
# 2026-10-06.1: el espejo SPAN duplica cada trama, así que los ratios "todo único"
# (puertos de un escaneo, nombres de un DGA) topan en ~0,5, no en 1,0. Los umbrales
# de unicidad se bajan de 0,9/0,5 a 0,45. Validado: dns_entropy en el ataque, con
# FPR 0/527 sobre la línea base. Ver notas 23/24/26 de orquestación.
# 2026-10-06.2: port_scan disparaba solo 1/3 (nota 26): en un escaneo corto el
# unique_dst_port_ratio queda bordeando 0,45-0,50 (tope del espejo) y a veces cae.
# Se añade una rama OR para la ráfaga inequívoca (>=200 intentos/30s con <=10 %
# completados) que NO depende del ratio. FPR validado offline: +5 disparos en
# 712 450 ventanas de línea base (0,011 %->0,012 %, neutro). Ver docs/MEJORA-PORT-SCAN.md.

# Umbrales por defecto. Se pueden sobreescribir por config (.toml [heuristicos]).
UMBRALES_POR_DEFECTO: dict[str, dict] = {
    # Fuerza bruta / password-spray: ráfaga de peticiones con casi todas fallando
    # la autenticación (401/403). Señal muy clara -> BLOCK. (Igual que el
    # auth_failure_heuristic previo: 5 en 60 s, >=80 % de fallo.)
    "brute_force": {
        "min_http_req_60s": 5,
        "min_auth_fail_ratio_60s": 0.8,
        "accion": "BLOCK",
    },
    # Escaneo de puertos: muchos intentos de flujo a muchos puertos distintos con
    # pocas conexiones completadas. Reconocimiento claro -> BLOCK.
    "port_scan": {
        "min_flow_attempt_30s": 20,
        "min_unique_dst_port_ratio_30s": 0.45,
        "max_syn_completion_ratio_10s": 0.3,
        # Rama OR: ráfaga masiva de baja completitud (independiente del ratio de
        # unicidad, que el espejo distorsiona). Inequívocamente un escaneo.
        "min_flow_attempt_burst_30s": 200,
        "max_syn_completion_burst_10s": 0.1,
        "min_unique_dst_port_ratio_burst_30s": 0.2,
        "accion": "BLOCK",
    },
    # Abuso HTTP (flood / scraping): volumen alto de peticiones SIN que sea fuerza
    # bruta (poca tasa de fallo de auth). Ambiguo (puede ser uso pesado legítimo)
    # -> LIMIT (degradar, no cortar).
    "http_abuse": {
        "min_http_req_60s": 200,          # eventos del espejo = 100 peticiones reales/min
        "max_auth_fail_ratio_60s": 0.8,
        "accion": "LIMIT",
    },
    # DNS de alta entropía (DGA / túnel): muchas consultas con casi todos los
    # nombres únicos o con mucho NXDOMAIN. Es el hueco donde el modelo sacó 0 %
    # (nota M). Ambiguo -> LIMIT.
    "dns_entropy": {
        "min_dns_query_60s": 20,
        "min_nxdomain_ratio_60s": 0.5,
        "min_unique_dns_name_ratio_60s": 0.45,
        "accion": "LIMIT",
    },
    # Inundacion ICMP (capa 3): cientos de paquetes por segundo casi todos ICMP.
    # Un ping normal son 1-30 paquetes/s; esto es denegacion de servicio -> BLOCK.
    "icmp_flood": {
        "min_packet_rate_10s": 200,
        "min_icmp_ratio_10s": 0.8,
        "accion": "BLOCK",
    },
}

_SEVERIDAD = {"BLOCK": 2, "LIMIT": 1}


def _n(row: dict, clave: str) -> float:
    """Lee una feature como float; ausente o no numérica -> 0.0."""
    try:
        v = row.get(clave, 0)
        return float(v) if v not in ("", None) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _brute_force(row: dict, u: dict) -> str | None:
    if (_n(row, "http_request_count_60s") >= u["min_http_req_60s"]
            and _n(row, "http_auth_failure_ratio_60s") >= u["min_auth_fail_ratio_60s"]):
        return "%.0f req HTTP/60s con %.0f%% de fallo de auth" % (
            _n(row, "http_request_count_60s"),
            100 * _n(row, "http_auth_failure_ratio_60s"))
    return None


def _port_scan(row: dict, u: dict) -> str | None:
    fa = _n(row, "flow_attempt_count_30s")
    up = _n(row, "unique_dst_port_ratio_30s")
    sc = _n(row, "syn_completion_ratio_10s")
    # Regla normal: muchos puertos distintos y pocas conexiones completadas.
    normal = (fa >= u["min_flow_attempt_30s"]
              and up >= u["min_unique_dst_port_ratio_30s"]
              and sc <= u["max_syn_completion_ratio_10s"])
    # Rama OR: ráfaga masiva de baja completitud. No depende del ratio de unicidad
    # (el espejo SPAN lo topa en ~0,5 y lo deja bordeando 0,45, de ahí el 1/3).
    # Exige variedad de puertos: cientos de conexiones al MISMO puerto (descargas
    # web) no son un escaneo aunque el espejo las vea «sin completar».
    rafaga = (fa >= u.get("min_flow_attempt_burst_30s", 200)
              and sc <= u.get("max_syn_completion_burst_10s", 0.1)
              and up >= u.get("min_unique_dst_port_ratio_burst_30s", 0.2))
    if normal or rafaga:
        return "%.0f intentos/30s a %.0f puertos distintos, %.0f%% completados" % (
            fa, round(fa * up), 100 * sc)
    return None


def _http_abuse(row: dict, u: dict) -> str | None:
    if (_n(row, "http_request_count_60s") >= u["min_http_req_60s"]
            and _n(row, "http_auth_failure_ratio_60s") < u["max_auth_fail_ratio_60s"]):
        return "%.0f req HTTP/60s (volumen alto, sin patrón de fuerza bruta)" % (
            _n(row, "http_request_count_60s"))
    return None


def _dns_entropy(row: dict, u: dict) -> str | None:
    if _n(row, "dns_query_count_60s") >= u["min_dns_query_60s"] and (
            _n(row, "dns_nxdomain_ratio_60s") >= u["min_nxdomain_ratio_60s"]
            or _n(row, "unique_dns_name_ratio_60s") >= u["min_unique_dns_name_ratio_60s"]):
        # Los ratios son por definicion <=1; el espejo SPAN puede duplicar
        # respuestas y dejarlos rozando o pasando 1 (se vio "103% NXDOMAIN"),
        # asi que se acotan a 100% para no mostrar un porcentaje incoherente.
        return "%.0f consultas DNS/60s, %.0f%% NXDOMAIN, %.0f%% nombres únicos" % (
            _n(row, "dns_query_count_60s"),
            100 * min(1.0, _n(row, "dns_nxdomain_ratio_60s")),
            100 * min(1.0, _n(row, "unique_dns_name_ratio_60s")))
    return None


def _icmp_flood(row: dict, u: dict) -> str | None:
    pr, ic = _n(row, "packet_rate_10s"), _n(row, "icmp_ratio_10s")
    if pr >= u["min_packet_rate_10s"] and ic >= u["min_icmp_ratio_10s"]:
        return "%.0f paquetes/s, %.0f%% ICMP (inundación)" % (pr, 100 * min(1.0, ic))
    return None


_REGLAS = (
    ("brute_force", _brute_force),
    ("port_scan", _port_scan),
    ("icmp_flood", _icmp_flood),
    ("http_abuse", _http_abuse),
    ("dns_entropy", _dns_entropy),
)


def evaluar(row: dict, umbrales: dict | None = None) -> dict | None:
    """Devuelve el veredicto MÁS severo (BLOCK > LIMIT) que dispare, o None.

    Ante empate de severidad, gana el orden de `_REGLAS` (fuerza bruta antes que
    abuso HTTP, etc.), que va de la señal más específica a la más genérica.
    """
    cfg = umbrales or UMBRALES_POR_DEFECTO
    mejor = None
    for nombre, regla in _REGLAS:
        u = cfg.get(nombre)
        if not u:
            continue
        motivo = regla(row, u)
        if motivo is None:
            continue
        accion = u["accion"]
        if mejor is None or _SEVERIDAD[accion] > _SEVERIDAD[mejor["accion"]]:
            mejor = {"heuristico": nombre, "accion": accion, "motivo": motivo}
    return mejor
