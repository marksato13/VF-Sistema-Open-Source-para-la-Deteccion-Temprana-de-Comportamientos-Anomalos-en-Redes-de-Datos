#!/usr/bin/env python3
"""Esquema y validación de la configuración de la campaña (reusado por generar_campana.py y las pruebas).

Valida tipos, valores, destinos, puertos, rutas, dependencias y la ausencia de marcadores sin resolver
(<PUERTO>, <R>, <ZONA_LAB>, null en campos requeridos). No toca la red.
"""
from __future__ import annotations
import re
import shutil

CONFIGS = ("IF_0.05", "IF_0.03", "IF_0.01", "HEUR", "HIB_0.05", "HIB_0.03", "HIB_0.01")   # = analizar.CONFIGS
MARCADOR = re.compile(r"<[^>]+>")          # <PUERTO>, <R>, <ZONA_LAB>, ...
IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
RUTA = re.compile(r"^/[A-Za-z0-9._~/-]*$")
HERRAMIENTAS = {"dig", "curl", "nmap"}


class ErrorConfig(ValueError):
    pass


def _texto_sin_marcador(v, camino, errores):
    if isinstance(v, str) and MARCADOR.search(v):
        errores.append(f"{camino}: marcador sin resolver {v!r}")


def validar(cfg: dict, *, exigir_herramientas: bool = False) -> list[str]:
    """Devuelve la lista de problemas (vacía = válida). No lanza salvo estructura imposible."""
    e: list[str] = []
    if cfg.get("version_esquema") != 2:
        e.append("version_esquema debe ser 2")
    org = cfg.get("origen")
    if not (isinstance(org, str) and IP.match(org)):
        e.append(f"origen inválido: {org!r}")
    blanca = cfg.get("lista_blanca_destinos")
    if not (isinstance(blanca, list) and blanca and all(isinstance(x, str) and IP.match(x) for x in blanca)):
        e.append("lista_blanca_destinos debe ser lista de IPs")
        blanca = blanca or []
    for k in ("semilla", "repeticiones"):
        if not isinstance(cfg.get(k), int) or cfg[k] <= 0:
            e.append(f"{k} debe ser entero positivo")
    t = cfg.get("tiempos_s", {})
    for k in ("calentamiento_inicial", "contexto_antes", "observacion_despues"):
        v = t.get(k)
        if not isinstance(v, (int, float)) or v < 0:
            e.append(f"tiempos_s.{k} debe ser número >= 0")
    if t.get("contexto_antes", 0) < 120:
        e.append("tiempos_s.contexto_antes debe ser >= 120 s (historia previa)")
    if t.get("observacion_despues", 0) < 90:
        e.append("tiempos_s.observacion_despues debe ser >= 90 s (cola)")

    escs = cfg.get("escenarios")
    if not isinstance(escs, list) or not escs:
        e.append("escenarios debe ser lista no vacía")
        return e
    ids = set()
    for i, s in enumerate(escs):
        c = f"escenarios[{i}]({s.get('id','?')})"
        sid = s.get("id")
        if not isinstance(sid, str) or not sid:
            e.append(f"{c}: id inválido")
        elif sid in ids:
            e.append(f"{c}: id duplicado")
        else:
            ids.add(sid)
        if not isinstance(s.get("habilitado"), bool):
            e.append(f"{c}: habilitado debe ser booleano")
        dst = s.get("destino")
        if not (isinstance(dst, str) and IP.match(dst)):
            e.append(f"{c}: destino inválido {dst!r}")
        elif dst not in blanca:
            e.append(f"{c}: destino {dst} fuera de la lista blanca {blanca}")
        herr = s.get("herramienta")
        if herr not in HERRAMIENTAS:
            e.append(f"{c}: herramienta {herr!r} no soportada {sorted(HERRAMIENTAS)}")
        if exigir_herramientas and herr and shutil.which(herr) is None:
            e.append(f"{c}: herramienta {herr!r} no está instalada (which falló)")
        to = s.get("timeout_s")
        if not isinstance(to, (int, float)) or to <= 0:
            e.append(f"{c}: timeout_s debe ser número positivo (no texto)")
        do = s.get("duracion_objetivo_s")
        if not (do is None or (isinstance(do, (int, float)) and do > 0)):
            e.append(f"{c}: duracion_objetivo_s debe ser número positivo o null")
        if isinstance(do, (int, float)) and isinstance(to, (int, float)) and to < do:
            e.append(f"{c}: timeout_s ({to}) menor que duracion_objetivo_s ({do})")
        if not isinstance(s.get("duracion_descripcion"), str):
            e.append(f"{c}: falta duracion_descripcion (texto)")
        p = s.get("params", {})
        if not isinstance(p, dict):
            e.append(f"{c}: params debe ser objeto")
            p = {}
        # marcadores sin resolver en cualquier texto del escenario
        for k, v in list(p.items()) + list(s.items()):
            _texto_sin_marcador(v, f"{c}.{k}", e)
        # validación específica por herramienta (solo si el escenario está habilitado)
        if s.get("habilitado"):
            e += _validar_params(c, sid, p)
    return e


def _num(c, p, k, e, minimo=None):
    v = p.get(k)
    if not isinstance(v, (int, float)) or (minimo is not None and v < minimo):
        e.append(f"{c}.params.{k} debe ser número{' >= %s' % minimo if minimo is not None else ''} (es {v!r})")


def _validar_params(c, sid, p) -> list[str]:
    e: list[str] = []
    if sid == "dns_inusual":
        _num(c, p, "sleep_entre_consultas_s", e, 0)
        if not p.get("zona_dns"):
            e.append(f"{c}.params.zona_dns sin resolver (zona de laboratorio reservada)")
    elif sid == "inundacion_http":
        _num(c, p, "concurrencia", e, 1)
        _num(c, p, "max_time_s", e, 1)
        if not isinstance(p.get("recurso"), str) or not p["recurso"].startswith("http"):
            e.append(f"{c}.params.recurso debe ser URL http")
    elif sid in ("escaneo_breve", "escaneo_sostenido"):
        if not re.match(r"^\d+-\d+$", str(p.get("rango", ""))):
            e.append(f"{c}.params.rango debe ser 'a-b' (es {p.get('rango')!r})")
        if sid == "escaneo_sostenido":
            _num(c, p, "max_rate", e, 1)
    elif sid == "fuerza_bruta_http":
        pt = p.get("brute_puerto")
        if not isinstance(pt, int) or not (1 <= pt <= 65535):
            e.append(f"{c}.params.brute_puerto debe ser puerto 1-65535 (es {pt!r})")
        ruta = p.get("brute_ruta")
        if not (isinstance(ruta, str) and RUTA.match(ruta)):
            e.append(f"{c}.params.brute_ruta debe ser ruta '/...' (es {ruta!r})")
        _num(c, p, "max_time_s", e, 1)
    else:
        e.append(f"{c}: id desconocido {sid!r}")
    return e


def comando_de(cfg: dict, s: dict) -> list[str]:
    """Construye el comando real de un escenario a partir de la config congelada (sin variables de entorno)."""
    dst, p, sid = s["destino"], s["params"], s["id"]
    dur = s.get("duracion_objetivo_s")
    # Los bucles imprimen al final 'intentos=<N>': número de ITERACIONES del bucle (intentos de consulta/petición)
    # producido por el propio comando. NO es "peticiones enviadas" ni "respuestas": eso se mide con PCAP/EVE/servidor.
    # nmap no lleva contador: su evidencia es su stdout + el PCAP.
    # 2026-11-09 (4C, tras la cancelación X3 de las 12:50Z): los dos nmap llevan -n (sin resolución DNS). Sin él, nmap hace una consulta
    # inversa (PTR) del destino a TODOS los servidores de /etc/resolv.conf de la Kali, incluido 10.10.10.21, que no está en la lista blanca
    # del vigía (X3). dig usa @{dst} explícito y los curl van a IP: no consultan DNS del sistema.
    if sid == "dns_inusual":
        zona = p["zona_dns"]
        return ["bash", "-c", f'c=0; fin=$((SECONDS+{int(dur)})); '
                f'while [ $SECONDS -lt $fin ]; do dig +time=1 +tries=1 @{dst} "$(openssl rand -hex 8).{zona}" +short '
                f'>/dev/null 2>&1; c=$((c+1)); sleep {p["sleep_entre_consultas_s"]}; done; echo "intentos=$c"']
    if sid == "inundacion_http":
        rec = p["recurso"]
        return ["bash", "-c", f'fin=$((SECONDS+{int(dur)})); n={int(p["concurrencia"])}; d=$(mktemp -d); '
                f'for i in $(seq $n); do ( c=0; while [ $SECONDS -lt $fin ]; do '
                f'curl -s -o /dev/null --max-time {p["max_time_s"]} {rec} ; c=$((c+1)); done; echo $c > "$d/$i" ) & done; '
                f'wait; echo "intentos=$(cat "$d"/* | awk \'{{s+=$1}} END{{print s+0}}\')"; rm -rf "$d"']
    if sid == "escaneo_breve":
        return ["nmap", "-sT", "-n", p["timing"], "--max-retries", str(p["max_retries"]), "-p", p["rango"], dst]
    if sid == "escaneo_sostenido":
        return ["nmap", "-sT", "-n", p["timing"], "--max-retries", str(p["max_retries"]),
                "--max-rate", str(p["max_rate"]), "-p", p["rango"], dst]
    if sid == "fuerza_bruta_http":
        pt, ruta = p["brute_puerto"], p["brute_ruta"]
        u = p["usuario_ficticio"]
        return ["bash", "-c", f'c=0; fin=$((SECONDS+{int(dur)})); '
                f'while [ $SECONDS -lt $fin ]; do curl -s -o /dev/null -w "%{{http_code}}\\n" '
                f'--max-time {p["max_time_s"]} -u {u}:{u}$RANDOM http://{dst}:{pt}{ruta} ; c=$((c+1)); done; echo "intentos=$c"']
    raise ErrorConfig(f"escenario desconocido: {sid}")
