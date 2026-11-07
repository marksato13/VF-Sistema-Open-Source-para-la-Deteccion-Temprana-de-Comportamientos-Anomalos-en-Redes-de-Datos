#!/usr/bin/env python3
"""Construye la entrada de `evaluar_ecarga.py veredicto` (contrato 2026-11-06.4, PROTOCOLO-CARGA-v2 §4.5) a partir de
las salidas REALES de la ventana, con un fichero de trazabilidad por cada valor. SOLO LECTURA de las fuentes.

  construir_entrada.py --desde D --hasta H \
      --clasificacion DIR/clasificacion/clasificacion.json      clasificar_periodo.py --suricata-eve
      --comparar      DIR/comparar.json                         comparar_suricata.py --stats-eve --eve
      --perfiles      DIR/perfiles.json --perfiles-rc N         evaluar_ecarga.py perfiles (y su rc)
      --bastion       DIR/bastion_s.json                        derivar_bastion.py
      --pcap          DIR/pcap_s.json                           derivar_pcap.py 2026-11-06.2
      --s14           DIR/s14.json                              evaluar_s14.py 2026-11-06.2 (r3 §3.6.1, r4 §3.6.1.1)
      --s7            DIR/s7.json                               derivar_s7.py 2026-11-07.1 (regla de r1 §4.3)
      [--manual S11=…] [--manual S15=…]

VERSION 2026-11-07.1: S7 sale de derivar_s7.py y ya no es manual, para que su valor llegue tal cual a la entrada.
VERSION 2026-11-06.3: exige evaluar_s14 2026-11-06.2 (la .1 no contaba el hueco anterior a una saturación y
daba S14 true con un episodio posible de 8 s). VERSION 2026-11-06.2: S14 sale de evaluar_s14.py (ya no es manual); S2/S3 exigen derivar_pcap 2026-11-06.2 (la .1
aprobaba observaciones incompletas) y copian su motivo a la trazabilidad.
      --salida-entrada entrada.json --salida-traza trazabilidad.json

Reglas (no cambian ningún criterio; solo dicen de dónde sale cada valor):
  * Una fuente que falta, no se lee o es de otro periodo deja sus criterios en null (sin medida). Nunca true.
  * Ningún criterio se rellena por defecto: lo que no se deriva ni se da con --manual queda null.
  * --manual solo para S11 y S15, siempre con un fichero de evidencia existente, cuyo sha256 se anota.
  * K4b no entra en la entrada (es informativo); se copia a la trazabilidad.
  * La clasificación debe traer la medida EVE (`suricata.fuente` = eve_stats) del MISMO periodo. Si no, no se construye
    la entrada (rc 2): el bloque `suricata` no se inventa.
  * Ningún valor se ajusta para que cuadre con otro: si la clase y los descartes no cuadran, lo dirá el evaluador.
rc: 0 entrada escrita; 2 no se puede construir (motivo en stderr y en la traza).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

K1_MIN, K2_MIN, K3_MIN = 596_789, 9, 50
UMBRAL_RAFAGA, UMBRAL_FLUJO = 5000, 1000
MEDIDOS = ("cero_explicito", "descartes")
MANUALES = ("S11", "S15")
K = ("K1", "K2", "K3", "K4a", "K5")
S = tuple(f"S{i}" for i in range(1, 16))
VERSION = "construir_entrada 2026-11-07.1"
VERSIONES_FUENTE = {"pcap": "derivar_pcap 2026-11-06.2", "bastion": "derivar_bastion 2026-11-06.2",
                    "s14": "evaluar_s14 2026-11-06.2", "s7": "derivar_s7 2026-11-07.1"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cargar(p, traza, nombre):
    if not p:
        traza["fuentes"][nombre] = {"fichero": None, "estado": "no dada"}
        return None
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        traza["fuentes"][nombre] = {"fichero": str(p), "estado": f"no legible: {e}"}
        return None
    traza["fuentes"][nombre] = {"fichero": str(p), "sha256": sha(p), "estado": "leída"}
    return d


def mismo(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.5


def construir(a):
    tr = {"version": VERSION, "periodo": [a.desde, a.hasta], "fuentes": {}, "campos": {}, "avisos": []}
    ent = {"K": {x: None for x in K}, "S": {x: None for x in S}}

    def pon(grupo, clave, valor, fuente, campo, regla):
        ent[grupo][clave] = valor
        tr["campos"][f"{grupo}.{clave}"] = {"valor": valor, "fuente": fuente, "campo": campo, "regla": regla}

    cl = cargar(a.clasificacion, tr, "clasificacion")
    if cl is None:
        return None, tr, "sin clasificación legible"
    su = cl.get("suricata") or {}
    med = su.get("medida") if su.get("fuente") == "eve_stats" else None
    if med is None:
        return None, tr, "la clasificación no trae la medida EVE (repetir clasificar_periodo con --suricata-eve)"
    per = cl.get("periodo") or {}
    if not (mismo(per.get("desde"), a.desde) and mismo(per.get("hasta"), a.hasta)):
        return None, tr, f"la clasificación es de otro periodo ({per.get('desde')}–{per.get('hasta')})"
    if [round(x, 3) for x in med.get("periodo") or []] != [round(a.desde, 3), round(a.hasta, 3)]:
        return None, tr, "la medida EVE de la clasificación es de otro periodo"
    clase = cl.get("clase_periodo")
    motivos = [f"{n}: {m}" for n in ("captura", "via-rapida") for m in ((cl.get("capturas") or {}).get(n) or {}).get("motivos") or []]
    if cl.get("motivo"):
        motivos.append(str(cl["motivo"]))
    ent["clasificacion"] = {"clase_periodo": clase, "motivos": motivos}
    tr["campos"]["clasificacion"] = {"valor": ent["clasificacion"], "fuente": "clasificacion",
                                     "campo": "clase_periodo; capturas.{captura,via-rapida}.motivos; motivo",
                                     "regla": "copiados tal cual; cada motivo con el nombre de su captura delante"}
    est = med.get("estado")
    medido = est in MEDIDOS
    pq, ds = med.get("paquetes"), med.get("descartes")
    ent["suricata"] = {"estado": est, "paquetes": pq if medido else None, "descartes": ds if medido else None}
    tr["campos"]["suricata"] = {"valor": ent["suricata"], "fuente": "clasificacion", "campo": "suricata.medida.{estado,paquetes,descartes}",
                                "regla": "copiados; sin medida, paquetes y descartes null"}
    dpm = (ds * 1_000_000 / pq) if medido and isinstance(pq, int) and isinstance(ds, int) and pq > 0 else None
    ent["descartes_por_millon"] = dpm
    tr["campos"]["descartes_por_millon"] = {"valor": dpm, "fuente": "clasificacion", "campo": "suricata.medida",
                                            "regla": "descartes × 10⁶ / paquetes, sin redondeo; null sin medida o con 0 paquetes"}
    cob = True if medido else (False if est == "cobertura_insuficiente" else None)
    pon("K", "K5", cob, "clasificacion", "suricata.medida.estado",
        "cero_explicito|descartes -> true; cobertura_insuficiente -> false; otro estado -> null")
    pon("S", "S4", cob, "clasificacion", "suricata.medida.estado", "igual que K5 (O4: sin hueco > 20 s, un proceso)")
    pon("S", "S5", True if medido and clase else (False if clase else None), "clasificacion",
        "clase_periodo; suricata.medida.estado", "O5: clasificación hecha y con estado de Suricata medido")
    pon("S", "S12", medido, "clasificacion", "suricata.medida.estado", "medido -> true; cualquier otro estado -> false")
    s13 = (ds * 1_000_000 * 100 < 1495 * pq) if dpm is not None else None
    pon("S", "S13", s13, "clasificacion", "suricata.medida.{descartes,paquetes}",
        "descartes × 10⁸ < 1 495 × paquetes (< 14,95/M exacto); null sin medida")

    co = cargar(a.comparar, tr, "comparar")
    if co is not None:
        ok = mismo(co.get("desde"), a.desde) and mismo(co.get("hasta"), a.hasta) and co.get("fuente_contadores") == "eve stats"
        if not ok:
            tr["avisos"].append("comparar: otro periodo o fuente distinta de «eve stats»: K1–K3 sin medida")
        pon("K", "K1", (co["paquetes"] >= K1_MIN) if ok and isinstance(co.get("paquetes"), int) else None, "comparar",
            "paquetes", f">= {K1_MIN} (método del comparador con el que se fijó el umbral, O12)")
        pon("K", "K2", (co["rafagas_ge_umbral"] >= K2_MIN) if ok and co.get("umbral_rafaga_paquetes_8s") == UMBRAL_RAFAGA else None,
            "comparar", "rafagas_ge_umbral", f">= {K2_MIN} con umbral_rafaga_paquetes_8s = {UMBRAL_RAFAGA}")
        k3ok = ok and co.get("umbral_flujo_grande") == UMBRAL_FLUJO and (co.get("flujos_eve") or 0) > 0
        pon("K", "K3", (co["flujos_grandes"] >= K3_MIN) if k3ok else None, "comparar", "flujos_grandes",
            f">= {K3_MIN} con umbral_flujo_grande = {UMBRAL_FLUJO}; null si no se leyó ningún flujo (falta --eve)")
        tr["informativo_paquetes_medida_acotada"] = pq
    pf = cargar(a.perfiles, tr, "perfiles")
    if pf is not None:
        ok = a.perfiles_rc in (0, 1) and mismo(pf.get("desde"), a.desde) and mismo(pf.get("hasta"), a.hasta) \
            and pf.get("version") == "2026-11-06.4" and isinstance((pf.get("K4a") or {}).get("cumple"), bool)
        pon("K", "K4a", pf["K4a"]["cumple"] if ok else None, "perfiles", "K4a.cumple",
            "copiado si rc 0/1, mismo periodo y evaluador 2026-11-06.4; si no, null")
        tr["K4b_informativo"] = pf.get("K4b")
    for nombre, ruta, claves in (("bastion", a.bastion, ("S1", "S6", "S8", "S9", "S10")), ("pcap", a.pcap, ("S2", "S3")),
                                 ("s14", a.s14, ("S14",)), ("s7", a.s7, ("S7",))):
        d = cargar(ruta, tr, nombre)
        if d is None:
            continue
        ok = [round(x, 3) for x in d.get("periodo") or []] == [round(a.desde, 3), round(a.hasta, 3)]
        if not ok:
            tr["avisos"].append(f"{nombre}: otro periodo: {', '.join(claves)} sin medida")
        if d.get("version") != VERSIONES_FUENTE[nombre]:
            ok = False
            tr["avisos"].append(f"{nombre}: versión {d.get('version')!r}, se exige {VERSIONES_FUENTE[nombre]!r}: "
                                f"{', '.join(claves)} sin medida")
        for s in claves:
            v = (d.get(s) or {}).get("valor")
            pon("S", s, v if ok and v in (True, False) else None, nombre, f"{s}.valor",
                "copiado; null si falta, es de otro periodo o de otra versión de la herramienta")
            if (d.get(s) or {}).get("motivo"):
                tr["campos"][f"S.{s}"]["motivo_fuente"] = d[s]["motivo"]
            if s == "S14":
                tr["campos"]["S.S14"]["componentes"] = {k: c.get("valor") for k, c in (d.get("componentes") or {}).items()}
    for m in a.manual:
        clave, _, resto = m.partition("=")
        valor, _, fich = resto.partition(":")
        if clave not in MANUALES:
            return None, tr, f"--manual solo admite {', '.join(MANUALES)}, no {clave}"
        if valor not in ("true", "false", "null"):
            return None, tr, f"--manual {clave}: valor {valor!r} (solo true, false o null)"
        if not fich or not Path(fich).is_file():
            return None, tr, f"--manual {clave}: falta el fichero de evidencia {fich!r}"
        tr["fuentes"][f"manual_{clave}"] = {"fichero": fich, "sha256": sha(fich), "estado": "leída"}
        pon("S", clave, {"true": True, "false": False, "null": None}[valor], f"manual_{clave}", "(lectura documentada)",
            "valor dado con --manual a partir de la evidencia indicada")
    sin = [f"{g}.{x}" for g in ("K", "S") for x in ent[g] if ent[g][x] is None]
    tr["sin_medida"] = sin
    return ent, tr, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", type=float, required=True)
    ap.add_argument("--hasta", type=float, required=True)
    ap.add_argument("--clasificacion", required=True)
    ap.add_argument("--comparar")
    ap.add_argument("--perfiles")
    ap.add_argument("--perfiles-rc", type=int)
    ap.add_argument("--bastion")
    ap.add_argument("--pcap")
    ap.add_argument("--s14")
    ap.add_argument("--s7")
    ap.add_argument("--manual", action="append", default=[])
    ap.add_argument("--salida-entrada", required=True)
    ap.add_argument("--salida-traza", required=True)
    a = ap.parse_args(argv)
    for p in (a.salida_entrada, a.salida_traza):
        if Path(p).exists():
            print(f"ABORTA: {p} ya existe (no se sobrescribe)", file=sys.stderr)
            return 2
    ent, tr, err = construir(a)
    if err:
        tr["error"] = err
        Path(a.salida_traza).write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"no se construye la entrada: {err}", file=sys.stderr)
        return 2
    orden = {"K": ent["K"], "S": ent["S"], "clasificacion": ent["clasificacion"], "suricata": ent["suricata"],
             "descartes_por_millon": ent["descartes_por_millon"]}
    Path(a.salida_entrada).write_text(json.dumps(orden, ensure_ascii=False, indent=1), encoding="utf-8")
    tr["entrada_sha256"] = sha(a.salida_entrada)
    Path(a.salida_traza).write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"entrada": a.salida_entrada, "sin_medida": tr["sin_medida"], "avisos": tr["avisos"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
