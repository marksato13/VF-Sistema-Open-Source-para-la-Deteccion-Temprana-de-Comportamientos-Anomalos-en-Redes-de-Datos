#!/usr/bin/env python3
"""Propone qué entidades parecen infraestructura, con evidencia. No excluye.

Excluir automáticamente es una vulnerabilidad: si al sistema le basta con
"parece un router" para dejar de puntuar a alguien, un atacante que imite ese
patrón se auto-excluye de la detección. Así que este detector PROPONE y deja la
decisión —y el porqué— por escrito; excluir de verdad es editar el .toml a mano.

Lee el dataset acumulado y, por entidad, reúne señales que distinguen
infraestructura de un cliente:

  - Presencia: fracción de ventanas en las que aparece. Un router está siempre;
    un cliente, a ratos.
  - unique_dst_ip_ratio_30s alto y sostenido: habla con muchísimos destinos
    (gateway, reenviador), no con unos pocos como un puesto de trabajo.
  - protocol_diversity_30s alto: mezcla muchos protocolos.
  - Último octeto .1/.2/.254: solo corrobora, nunca decide por sí solo.

Cada señal que se cumple queda escrita junto al veredicto. El resultado es un
JSON de candidatos para que un humano decida, no una lista de exclusión.

    python3 detector_alcance.py --entrada multilayer-v3.csv --salida candidatos.json
"""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def _num(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def analizar(filas: list[dict], total_ventanas: int) -> list[dict]:
    por_ip: dict[str, list[dict]] = {}
    for f in filas:
        por_ip.setdefault(f.get("entity_ip", ""), []).append(f)

    salida = []
    for ip, fs in por_ip.items():
        n = len(fs)
        presencia = n / total_ventanas if total_ventanas else 0.0
        dst_ip = statistics.median(_num(f.get("unique_dst_ip_ratio_30s", 0)) for f in fs)
        protos = statistics.median(_num(f.get("protocol_diversity_30s", 0)) for f in fs)

        senales = []
        puntos = 0
        if presencia > 0.9:
            senales.append("presente en el %.0f%% de las ventanas (siempre activa)" % (presencia * 100))
            puntos += 2
        if dst_ip > 0.5:
            senales.append("habla con muchos destinos (unique_dst_ip mediana %.2f)" % dst_ip)
            puntos += 2
        if protos > 0.05:
            senales.append("mezcla protocolos (protocol_diversity mediana %.2f)" % protos)
            puntos += 1
        try:
            ultimo = int(ipaddress.ip_address(ip)) & 0xFF
            if ultimo in (1, 2, 254):
                senales.append("último octeto .%d (típico de gateway/infra)" % ultimo)
                puntos += 1
        except ValueError:
            pass

        veredicto = ("infraestructura_probable" if puntos >= 3
                     else "indeterminado" if puntos >= 1 else "cliente")
        salida.append({
            "ip": ip, "ventanas": n, "presencia": round(presencia, 3),
            "puntos": puntos, "veredicto": veredicto, "senales": senales,
        })
    salida.sort(key=lambda e: (-e["puntos"], -e["presencia"]))
    return salida


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entrada", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    a = p.parse_args()

    with a.entrada.open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        print(json.dumps({"error": "el CSV no tiene filas"}))
        return 1

    total_ventanas = len({f.get("window_end_utc") for f in filas})
    entidades = analizar(filas, total_ventanas)
    sugerencia = [e["ip"] for e in entidades if e["veredicto"] == "infraestructura_probable"]

    informe = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "total_ventanas": total_ventanas,
        "entidades": entidades,
        "sugerencia_excluir": sugerencia,
        "nota": "PROPUESTA con evidencia, no exclusión. Excluir de verdad es "
                "editar [red] excluir en cyberflow.toml a mano, y declararlo.",
    }
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(informe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("entidades: %d · candidatas a infraestructura: %s"
          % (len(entidades), ", ".join(sugerencia) or "ninguna"))
    for e in entidades[:8]:
        print("  %-15s %-22s %s" % (e["ip"], e["veredicto"], "; ".join(e["senales"]) or "—"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
