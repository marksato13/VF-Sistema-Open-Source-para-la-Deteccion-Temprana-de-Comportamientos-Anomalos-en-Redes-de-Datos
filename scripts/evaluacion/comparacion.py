#!/usr/bin/env python3
"""Comparacion CyberFlow frente a Suricata, con un protocolo que no mezcla cosas.

Reglas del protocolo (las mismas que muestra la figura del panel):

1. **Entrada comun.** El mismo PCAP reproducido a todas las condiciones, con los
   mismos intervalos y la configuracion congelada.
2. **Referencia independiente.** Que es un ataque y cuando empieza y acaba lo
   dicen el guion y los registros del orquestador, nunca las alertas de
   Suricata ni las decisiones de CyberFlow.
3. **Unidad: el episodio.** Un episodio esta detectado por una condicion si
   produce al menos una deteccion dentro de su intervalo. Nunca se cuentan
   alertas como si fueran ataques.
4. **Cuatro condiciones**: Suricata (alertas por firma), solo modelo (ALERT del
   Isolation Forest), solo heuristicos (reglas sobre eventos EVE y conteos del
   PCAP) y combinado (CyberFlow completo). CyberFlow consume los EVENTOS de EVE
   (http, dns, tls), no las alertas de Suricata: lo declara la entrada y lo
   comprueba la prueba.
5. **Falsos positivos en su propia unidad**: sobre trafico normal, ventanas con
   accion (CyberFlow) o alertas por hora (Suricata). No se combinan con los
   episodios en una precision ni en un F1.
6. **Latencia** = primera deteccion dentro del episodio - inicio del episodio
   segun la referencia. Un valor no medido se dice «no medido», no 0.

    python3 scripts/evaluacion/comparacion.py docs/evaluacion/comparacion-suricata.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

CONDICIONES = ("suricata", "modelo", "heuristicos", "combinado")
NOMBRE = {"suricata": "Suricata", "modelo": "Solo modelo",
          "heuristicos": "Solo heurísticos", "combinado": "CyberFlow (combinado)"}
FAMILIAS = {"escaneo": "Escaneo de puertos", "dns": "DNS de alta entropía",
            "flood": "Flood HTTP", "fuerza-bruta": "Fuerza bruta", "nikto": "Nikto"}


class EntradaInvalida(ValueError):
    pass


def validar(datos: dict) -> None:
    prot = datos.get("protocolo") or {}
    for clave in ("entrada", "referencia", "unidad"):
        if not prot.get(clave):
            raise EntradaInvalida("falta protocolo.%s" % clave)
    if prot["unidad"] != "episodio":
        raise EntradaInvalida("la unidad de evaluacion debe ser el episodio")
    consume = str((prot.get("cyberflow") or {}).get("consume", ""))
    if "alerta" in consume.lower() and "no alerta" not in consume.lower():
        raise EntradaInvalida("CyberFlow no debe consumir alertas de Suricata")
    ids = set()
    for ep in datos.get("episodios", []):
        if ep["id"] in ids:
            raise EntradaInvalida("episodio repetido: %s" % ep["id"])
        ids.add(ep["id"])
        det = ep.get("detecciones") or {}
        for c in det:
            if c not in CONDICIONES:
                raise EntradaInvalida("%s: condicion desconocida %r" % (ep["id"], c))
            v = det[c]
            if v not in (None, "no medido") and not (isinstance(v, (int, float)) and v >= 0):
                raise EntradaInvalida("%s/%s: la latencia debe ser segundos >= 0, null o "
                                      "'no medido'" % (ep["id"], c))


def _estado(v) -> str:
    """'detectado', 'no detectado' o 'no medido' para una latencia de la entrada."""
    if v == "no medido":
        return "no medido"
    return "no detectado" if v is None else "detectado"


def resumen_celda(latencias: list) -> dict:
    medidos = [v for v in latencias if v != "no medido"]
    detectados = [float(v) for v in medidos if v is not None]
    celda = {"n": len(medidos), "detectados": len(detectados), "no_medidos": len(latencias) - len(medidos)}
    if detectados:
        celda["latencia_mediana_s"] = round(statistics.median(detectados), 1)
        celda["latencia_min_s"] = round(min(detectados), 1)
        celda["latencia_max_s"] = round(max(detectados), 1)
    return celda


def evaluar(datos: dict) -> dict:
    validar(datos)
    eps = datos.get("episodios", [])
    familias = []
    for ep in eps:
        if ep["familia"] not in familias:
            familias.append(ep["familia"])
    tabla = []
    for fam in familias:
        de_fam = [e for e in eps if e["familia"] == fam]
        fila = {"familia": fam, "nombre": FAMILIAS.get(fam, fam),
                "con_firma": any(e.get("con_firma") for e in de_fam), "episodios": len(de_fam)}
        for c in CONDICIONES:
            fila[c] = resumen_celda([(e.get("detecciones") or {}).get(c, "no medido") for e in de_fam])
        tabla.append(fila)

    def total(con_firma: bool) -> dict:
        sel = [e for e in eps if bool(e.get("con_firma")) == con_firma]
        return {c: resumen_celda([(e.get("detecciones") or {}).get(c, "no medido") for e in sel])
                for c in CONDICIONES}

    ben = datos.get("benigno") or {}
    falsos = {}
    for c in CONDICIONES:
        v = (ben.get("falsos") or {}).get(c, "no medido")
        if c == "suricata":
            falsos[c] = {"unidad": "alertas por hora de tráfico normal", "valor": v,
                         "horas": ben.get("horas")}
        else:
            ventanas = ben.get("ventanas")
            falsos[c] = {"unidad": "ventanas normales con acción", "valor": v, "de": ventanas,
                         "tasa": (round(v / ventanas, 4) if isinstance(v, (int, float)) and ventanas else None)}
    return {
        "protocolo": datos["protocolo"],
        "por_familia": tabla,
        "sin_firma": total(False),
        "con_firma": total(True),
        "falsos_positivos": falsos,
        "notas": datos.get("notas", []),
        "fuente": datos.get("fuente", ""),
    }


def _num(v: float) -> str:
    return ("%g" % v).replace(".", ",")


def _celda_md(c: dict) -> str:
    if c["n"] == 0:
        return "no medido"
    txt = "%d/%d" % (c["detectados"], c["n"])
    if c["detectados"]:
        if c["latencia_min_s"] == c["latencia_max_s"]:
            txt += " · %s s" % _num(c["latencia_mediana_s"])
        else:
            txt += " · %s s [%s–%s]" % (_num(c["latencia_mediana_s"]), _num(c["latencia_min_s"]),
                                         _num(c["latencia_max_s"]))
    if c["no_medidos"]:
        txt += " (+%d no medido)" % c["no_medidos"]
    return txt


def markdown(r: dict) -> str:
    cab = "| Familia | " + " | ".join(NOMBRE[c] for c in CONDICIONES) + " |"
    lineas = [cab, "|---|" + "---|" * len(CONDICIONES)]
    for f in r["por_familia"]:
        lineas.append("| %s%s | %s |" % (f["nombre"], " *(con firma)*" if f["con_firma"] else "",
                                        " | ".join(_celda_md(f[c]) for c in CONDICIONES)))
    lineas.append("| **Total sin firma** | %s |" % " | ".join(_celda_md(r["sin_firma"][c]) for c in CONDICIONES))
    lineas.append("")
    lineas.append("Celda: episodios detectados / medidos · latencia mediana [mín–máx] desde el inicio "
                  "del episodio según la referencia.")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", type=Path)
    ap.add_argument("--markdown", action="store_true", help="tabla en markdown en vez de JSON")
    a = ap.parse_args(argv)
    try:
        r = evaluar(json.loads(a.entrada.read_text(encoding="utf-8")))
    except EntradaInvalida as e:
        print("entrada invalida: %s" % e, file=sys.stderr)
        return 2
    print(markdown(r) if a.markdown else json.dumps(r, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
