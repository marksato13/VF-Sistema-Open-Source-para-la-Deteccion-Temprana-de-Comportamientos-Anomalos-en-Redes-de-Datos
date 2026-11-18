#!/usr/bin/env python3
"""Feed de enforcement: la lista firmada que el sensor publica y los hosts aplican.

Modelo "un feed / N agentes (pull)": el sensor NO tiene credenciales de los hosts;
publica una lista **firmada** y cada host la trae, verifica y aplica en su propio
kernel. Ver DISENO-ENFORCEMENT.md §2.

Firma: **ed25519 vía openssl** (asimétrico; el sensor firma con la clave privada,
los hosts verifican con la pública). Se usa openssl y no una librería de Python
para no añadir dependencias al entorno congelado del modelo — mismo criterio que el
certificado del panel.

Formato del feed (JSON canónico, `sort_keys`):
    {
      "version": 1,
      "generado": <epoch>,
      "umbrales": "<version de heuristicos>",
      "entradas": [
        {"ip": "...", "accion": "LIMIT|BLOCK", "hasta": <epoch>,
         "alcance": "all"|["host",...], "motivo": "...", "detector": "..."},
        ...
      ]
    }
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

VERSION_FEED = 1


def construir(entradas: list[dict], ahora: float | None = None,
              umbrales: str = "") -> dict:
    """Ensambla el feed. Cada entrada ya trae ip/accion/hasta/alcance/motivo."""
    return {
        "version": VERSION_FEED,
        "generado": ahora if ahora is not None else time.time(),
        "umbrales": umbrales,
        "entradas": sorted(entradas, key=lambda e: (e["ip"], e.get("accion", ""))),
    }


def serializar(feed: dict) -> bytes:
    """JSON canónico (determinista) — lo que se firma y lo que se verifica."""
    return (json.dumps(feed, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


# --- Firma asimétrica con openssl (ed25519) --------------------------------

def generar_claves(priv_path: str, pub_path: str) -> None:
    """Crea el par ed25519 (privada 0600 en el sensor, pública para los hosts)."""
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv_path],
                   check=True, capture_output=True)
    os.chmod(priv_path, 0o600)
    subprocess.run(["openssl", "pkey", "-in", priv_path, "-pubout", "-out", pub_path],
                   check=True, capture_output=True)


def firmar(datos: bytes, priv_path: str) -> bytes:
    """Firma los bytes canónicos del feed; devuelve la firma cruda."""
    with tempfile.NamedTemporaryFile(delete=False) as fd:
        fd.write(datos)
        tmp = fd.name
    try:
        r = subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", priv_path, "-rawin", "-in", tmp],
            check=True, capture_output=True)
        return r.stdout
    finally:
        os.unlink(tmp)


def verificar(datos: bytes, firma: bytes, pub_path: str) -> bool:
    """True si la firma corresponde a los datos bajo la clave pública."""
    with tempfile.NamedTemporaryFile(delete=False) as fdd, \
            tempfile.NamedTemporaryFile(delete=False) as fds:
        fdd.write(datos); dpath = fdd.name
        fds.write(firma); spath = fds.name
    try:
        r = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", pub_path,
             "-rawin", "-in", dpath, "-sigfile", spath],
            capture_output=True)
        return r.returncode == 0
    finally:
        os.unlink(dpath)
        os.unlink(spath)


# --- Paquete feed + firma (pendiente P4 del cierre 4A, 2026-11-06) ------------
#
# Entregar feed.json y feed.sig con dos renombrados deja un instante en que el destino tiene la firma NUEVA con el
# feed ANTERIOR: un lector que cae ahí ve una pareja que no verifica (13 rechazos firma_invalida en srv-dmz entre
# el 04 y el 06-nov, todos 1–10 ms antes del fin de una entrega del relé). La atomicidad de cada fichero no da la
# coherencia de la pareja. El paquete lleva la generación entera (feed y firma) en UN fichero, que se publica con
# UN solo rename: el lector ve el paquete anterior completo o el nuevo completo. El paquete NO sustituye a la
# firma: el agente sigue verificando ed25519 sobre los bytes del feed. Las huellas sha256 internas solo distinguen
# un paquete dañado o incompleto (``paquete_invalido``) de una firma que no corresponde (``firma_invalida``).

FORMATO_PAQUETE = "cyberflow-feed-paquete/1"


def empaquetar(datos: bytes, firma: bytes) -> bytes:
    import base64
    import hashlib
    obj = {"formato": FORMATO_PAQUETE, "sha256_feed": hashlib.sha256(datos).hexdigest(),
           "sha256_firma": hashlib.sha256(firma).hexdigest(),
           "feed_b64": base64.b64encode(datos).decode("ascii"), "firma_b64": base64.b64encode(firma).decode("ascii")}
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def desempaquetar(paquete: bytes) -> tuple[bytes, bytes]:
    """(feed, firma). ValueError con el motivo si el paquete no es íntegro. No verifica la firma."""
    import base64
    import binascii
    import hashlib
    try:
        obj = json.loads(paquete)
    except ValueError as exc:
        raise ValueError("paquete_no_json") from exc
    if not isinstance(obj, dict) or obj.get("formato") != FORMATO_PAQUETE:
        raise ValueError("paquete_formato")
    try:
        datos = base64.b64decode(obj["feed_b64"], validate=True)
        firma = base64.b64decode(obj["firma_b64"], validate=True)
    except (KeyError, TypeError, binascii.Error) as exc:
        raise ValueError("paquete_base64") from exc
    if hashlib.sha256(datos).hexdigest() != obj.get("sha256_feed") or \
            hashlib.sha256(firma).hexdigest() != obj.get("sha256_firma"):
        raise ValueError("paquete_huella")
    if not datos or not firma:
        raise ValueError("paquete_vacio")
    return datos, firma


# --- Feed v2 (Etapa 2, rama candidata) --------------------------------------
#
# Cambios respecto a v1, todos DENTRO de lo firmado (el JSON canonico entero):
#   - `secuencia` (entero creciente por emisor) y `expira` (epoch): un agente
#     rechaza un feed caducado y uno con secuencia anterior a la ya aplicada
#     (repeticion o fuera de orden). Con la misma secuencia no hace nada: no se
#     renueva una restriccion por releer el mismo feed.
#   - cada entrada lleva `destino` (que agente la aplica) y `alcance` (que
#     trafico restringe), `id` (huella estable de la entrada) y `evento_id` (la
#     decision del motor que la origino). Una misma IP puede tener a la vez una
#     entrada para srv-dmz y otra para DC1.
#
# Contrato de alcance por destino: srv-dmz solo admite "todo" (todo el trafico
# entrante del origen); dc1 solo admite "dns" (UDP/TCP 53). Cualquier otro par
# se rechaza en el agente: un DC no se bloquea entero por una senal DNS y un
# servidor web no aplica una regla pensada para DNS.

VERSION_FEED_V2 = 2
ALCANCES_POR_DESTINO = {"srv-dmz": frozenset({"todo"}), "dc1": frozenset({"dns"})}
ACCIONES = frozenset({"LIMIT", "BLOCK"})
# Mayor caducidad que puede pedir una entrada (escalera: tope 3600 s) + margen.
HASTA_MAXIMO_S = 3600 + 120
TOLERANCIA_RELOJ_S = 30


def id_entrada(ip: str, destino: str, alcance: str, accion: str, evento_id: str) -> str:
    """Huella estable de una entrada: misma decision -> mismo id en todos los feeds."""
    import hashlib
    clave = "|".join((ip, destino, alcance, accion, evento_id)).encode("utf-8")
    return hashlib.sha256(clave).hexdigest()[:16]


def construir_v2(entradas: list[dict], secuencia: int, ahora: float, vigencia_s: float,
                 umbrales: str = "", emisor: str = "sensor1") -> dict:
    return {
        "version": VERSION_FEED_V2,
        "emisor": emisor,
        "secuencia": int(secuencia),
        "generado": ahora,
        "expira": ahora + vigencia_s,
        "umbrales": umbrales,
        "entradas": sorted(entradas, key=lambda e: (e["ip"], e["destino"], e["alcance"], e["accion"])),
    }


def _ipv4_valida(ip) -> bool:
    import ipaddress
    try:
        return isinstance(ip, str) and isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
    except ValueError:
        return False


def validar_v2(feed_obj: dict, destino_local: str, ahora: float,
               ultima_secuencia: int | None, nunca: set[str]) -> dict:
    """Valida un feed v2 YA verificado en firma, para el agente `destino_local`.

    Devuelve {"estado", "motivo", "entradas", "rechazadas", "ajenas"}:
      estado "aceptado": `entradas` son las del destino local, validas y vigentes;
      estado "repetido": misma secuencia ya aplicada -> no se toca nada;
      estado "rechazado": el feed entero se descarta (fail-safe: se conserva lo
      ya aplicado, que caduca solo por el timeout nativo de nftables).
    Las entradas invalidas se rechazan una a una con su motivo; nunca se
    reinterpreta una entrada antigua o desconocida como "todo".
    """
    out = {"estado": "rechazado", "motivo": "", "entradas": [], "rechazadas": [], "ajenas": 0}
    if not isinstance(feed_obj, dict) or feed_obj.get("version") != VERSION_FEED_V2:
        out["motivo"] = "version_no_soportada"
        return out
    if destino_local not in ALCANCES_POR_DESTINO:
        out["motivo"] = "destino_local_desconocido"
        return out
    try:
        secuencia = int(feed_obj["secuencia"])
        expira = float(feed_obj["expira"])
        generado = float(feed_obj["generado"])
        entradas = list(feed_obj["entradas"])
    except (KeyError, TypeError, ValueError):
        out["motivo"] = "campos_obligatorios"
        return out
    if expira <= ahora:
        out["motivo"] = "feed_caducado"
        return out
    if generado > ahora + TOLERANCIA_RELOJ_S:
        out["motivo"] = "feed_del_futuro"
        return out
    if ultima_secuencia is not None:
        if secuencia < ultima_secuencia:
            out["motivo"] = "secuencia_anterior"
            return out
        if secuencia == ultima_secuencia:
            out["estado"] = "repetido"
            out["motivo"] = "misma_secuencia"
            return out
    vistos = set()
    for e in entradas:
        motivo = None
        if not isinstance(e, dict):
            motivo = "entrada_no_objeto"
        else:
            destino, alcance = e.get("destino"), e.get("alcance")
            if destino not in ALCANCES_POR_DESTINO:
                motivo = "destino_desconocido"
            elif destino != destino_local:
                out["ajenas"] += 1
                continue
            elif alcance not in ALCANCES_POR_DESTINO[destino]:
                motivo = "alcance_no_permitido" if isinstance(alcance, str) else "alcance_desconocido"
            elif e.get("accion") not in ACCIONES:
                motivo = "accion_desconocida"
            elif not _ipv4_valida(e.get("ip")):
                motivo = "ip_invalida"
            elif e["ip"] in nunca:
                motivo = "nunca_bloquear"
            else:
                try:
                    hasta = float(e["hasta"])
                except (KeyError, TypeError, ValueError):
                    hasta = None
                if hasta is None:
                    motivo = "hasta_invalido"
                elif hasta <= ahora:
                    motivo = "entrada_caducada"
                elif hasta - ahora > HASTA_MAXIMO_S:
                    motivo = "hasta_excesivo"
                elif e.get("id") != id_entrada(e["ip"], destino, alcance, e["accion"],
                                               str(e.get("evento_id", ""))):
                    motivo = "id_incoherente"
                elif e["id"] in vistos:
                    motivo = "id_duplicado"
        if motivo:
            out["rechazadas"].append({"ip": e.get("ip") if isinstance(e, dict) else None,
                                      "motivo": motivo})
            continue
        vistos.add(e["id"])
        out["entradas"].append(e)
    out["estado"] = "aceptado"
    out["secuencia"] = secuencia
    return out
