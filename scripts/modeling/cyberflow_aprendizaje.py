#!/usr/bin/env python3
"""Reentrenamiento SUPERVISADO: el sistema prepara el modelo nuevo, una persona lo aprueba.

**Por que supervisado.** Un detector que se reentrena y se despliega solo puede
aprender un ataque lento como si fuera normal: basta con que el atacante meta
su trafico poco a poco en la linea base (envenenamiento de datos). Aqui todo lo
automatico ocurre FUERA del modelo en uso; lo unico que cambia el detector del
motor es ``promover``, que lo lanza una persona y deja copia para ``revertir``.

Cuatro defensas, cada una en un paso y con su rastro en disco:

1. **Saneamiento** (``lote``). Cada dia se cierra un lote con las ventanas de la
   linea base de ese dia y se filtra antes de que pueda entrar a entrenar:
   fuera las ventanas de toda IP que el sistema marco (ALERT, LIMIT, BLOCK o
   alerta de Suricata) cerca de ese momento; fuera las filas atipicas frente al
   conjunto de oro; y el lote entero se rechaza si su distribucion se aleja
   demasiado (PSI), porque eso es o un cambio de red o una contaminacion, y en
   los dos casos lo tiene que mirar una persona.
2. **Linaje** (``registro.jsonl``). Cada lote queda con su sha256, su origen y lo
   que se filtro, en un registro encadenado: cada linea lleva el hash de la
   anterior, asi que borrar o retocar un lote rompe la cadena y el candidato se
   niega a entrenar. El candidato lista los lotes exactos que uso.
3. **Limite de influencia** (``candidato``). Los datos nuevos no pasan de
   ``max_fraccion_nueva`` del entrenamiento, y ninguna IP de ``max_fraccion_ip``
   de lo nuevo: un solo equipo inundando la red no puede mover el modelo.
4. **Deriva** (``deriva``). El modelo vigente se mide cada dia contra el
   CONJUNTO DE ORO -fijo, verificado, nunca se mezcla con datos nuevos- y contra
   el lote del dia. Si la deriva se sostiene, toca reentrenar antes de la
   cadencia.

Subordenes (``--config`` apunta al .toml del despliegue):

    oro --desde particionado.csv   crea el conjunto de oro (una vez, tras calibrar)
    lote [--dia AAAA-MM-DD]        cierra y sanea el lote de un dia (por omision, ayer)
    deriva [--dia AAAA-MM-DD]      mide la deriva del modelo vigente
    candidato [--forzar]           entrena y evalua un candidato si toca
    diario                         lote + deriva + candidato: lo que lanza el timer
    promover ID                    apunta el .toml al candidato (con copia)
    revertir                       vuelve al modelo anterior
    estado                         resumen en JSON (lo lee el panel)
    verificar                      comprueba la cadena del registro y los hashes
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

REPO = Path(__file__).resolve().parents[2]
PARTICIONAR = REPO / "scripts/dataset/particionar_linea_base.py"
ENTRENAR = REPO / "scripts/modeling/entrenar_preliminar.py"
ESQUEMA_V2 = REPO / "configs/features/multilayer-v2.json"

# Lo que vale si el .toml no dice nada. Cada clave esta explicada en
# configs/cyberflow.toml, seccion [reentrenamiento].
POLITICA = {
    "activo": False,
    "modo": "supervisado",
    "directorio": "artifacts/aprendizaje",
    "oro": "artifacts/aprendizaje/oro/oro.csv",
    "base": "",
    "ataques": "",
    "cadencia_dias": 30,
    "dias_minimos": 7,
    "filas_minimas_lote": 500,
    "margen_contaminacion_s": 300,
    "usar_alertas_suricata": True,
    "cuantil_referencia": 0.999,
    "tolerancia_atipica": 0.5,
    "max_variables_atipicas": 3,
    "psi_rechazo_lote": 0.5,
    "max_fraccion_nueva": 0.30,
    "max_fraccion_ip": 0.10,
    "psi_alerta": 0.25,
    "tasa_anomala_max": 0.15,
    "dias_deriva": 3,
    "alpha": 0.05,
    "tolerancia_fpr": 0.005,
    "tolerancia_deteccion": 0.0,
    "conservar_modelos": 3,
    "semilla": 20260813,
    # Tramos que se sabe que NO son normales (una rafaga de ataque que se colo en
    # la linea base, una prueba): "IP@ini/fin" en ISO, o "*@ini/fin" para todas.
    # Nunca entran a entrenar, ni desde la base ni desde los lotes.
    "excluir_ventanas": [],
}

ESTADOS_LOTE_UTILES = ("aceptado", "aceptado_a_mano")


# ----------------------------------------------------------------- utilidades

def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def sha_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def marca(valor: str) -> float:
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).timestamp()


def clave(fila: dict) -> tuple[str, str]:
    return (str(fila["entity_ip"]), str(fila["window_end_utc"]))


def elegible(fila: dict) -> bool:
    return str(fila.get("eligible_training", "True")).lower() == "true"


def leer_csv(ruta: Path) -> tuple[list[str], list[dict]]:
    with Path(ruta).open(newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        return list(lector.fieldnames or []), list(lector)


def escribir_csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def leer_jsonl(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    salida = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            salida.append(json.loads(linea))
    return salida


def nombres_v2(esquema: Path = ESQUEMA_V2) -> list[str]:
    contrato = json.loads(Path(esquema).read_text(encoding="utf-8"))
    return [f["name"] for f in sorted(contrato["features"], key=lambda f: f["order"])]


def submuestra(filas: list, n: int) -> list:
    """n elementos repartidos a lo largo de la lista, sin azar.

    Las filas van en orden temporal, asi que tomar una de cada k conserva la
    cobertura del dia entero; tomar las primeras n se quedaria con la madrugada.
    """
    if n >= len(filas):
        return list(filas)
    if n <= 0:
        return []
    paso = len(filas) / n
    return [filas[int(i * paso)] for i in range(n)]


def cuantil(valores: list[float], q: float) -> float:
    if not valores:
        return 0.0
    orden = sorted(valores)
    pos = (len(orden) - 1) * q
    i, frac = int(pos), pos - int(pos)
    if i + 1 < len(orden):
        return orden[i] + (orden[i + 1] - orden[i]) * frac
    return orden[i]


def psi(referencia: list[float], nuevos: list[float], cajas: int = 10) -> float:
    """Population Stability Index de `nuevos` frente a `referencia`.

    Cortes por cuantiles de la referencia. Regla habitual: < 0,1 estable,
    0,1-0,25 cambio moderado, > 0,25 cambio grande. Muchas variables de red son
    cero casi siempre: los cortes repetidos se funden y la variable queda con
    pocas cajas, que es lo correcto (no hay distribucion que comparar).
    """
    if not referencia or not nuevos:
        return 0.0
    cortes = sorted({cuantil(referencia, i / cajas) for i in range(1, cajas)})

    def reparto(vals):
        c = Counter()
        for v in vals:
            c[sum(1 for x in cortes if v > x)] += 1
        return [c[i] / len(vals) for i in range(len(cortes) + 1)]

    eps = 1e-4
    total = 0.0
    for p, q in zip(reparto(referencia), reparto(nuevos)):
        p, q = max(p, eps), max(q, eps)
        total += (q - p) * math.log(q / p)
    return round(total, 6)


# ----------------------------------------------------------- configuracion

def cargar_config(ruta: Path, raiz: Path | None = None) -> dict:
    if tomllib is None:
        raise SystemExit("hace falta Python 3.11+ (tomllib)")
    with Path(ruta).open("rb") as f:
        cfg = tomllib.load(f)
    politica = dict(POLITICA)
    politica.update(cfg.get("reentrenamiento", {}))
    rut, mot = cfg.get("rutas", {}), cfg.get("motor", {})
    base = Path(raiz) if raiz else Path(rut.get("raiz", "."))
    return {
        "toml": Path(ruta),
        "raiz": base,
        "politica": politica,
        "dir": base / politica["directorio"],
        "dataset": base / rut.get("dataset", "artifacts/linea-base/multilayer-v3.csv"),
        "registro_motor": base / rut.get("registro", "logs/motor_decision.log"),
        "eve": Path(rut.get("eve", "/var/log/suricata/eve.json")),
        "modelo": base / rut.get("modelo", ""),
        "manifiesto": base / rut.get("manifiesto", ""),
        "detector": mot.get("detector", "ocsvm_scaled"),
        "esquema": base / rut.get("esquema", "configs/features/multilayer-v2.json"),
    }


def ruta_politica(cfg: dict, clave_: str) -> Path | None:
    valor = cfg["politica"].get(clave_) or ""
    return (cfg["raiz"] / valor) if valor else None


def comprobar_politica(politica: dict) -> list[str]:
    """Lo que hace que la politica no tenga sentido. Lo usa cyberflow_config."""
    fallos = []
    p = dict(POLITICA)
    p.update(politica)
    if p["modo"] != "supervisado":
        fallos.append("reentrenamiento.modo solo admite 'supervisado': un modelo que se "
                      "despliega solo puede aprender un ataque lento como normal")
    for k in ("max_fraccion_nueva", "max_fraccion_ip", "alpha"):
        if not 0 < float(p[k]) < 1:
            fallos.append("reentrenamiento.%s debe estar entre 0 y 1 (es %r)" % (k, p[k]))
    for k in ("cadencia_dias", "dias_minimos", "dias_deriva", "conservar_modelos",
              "filas_minimas_lote", "max_variables_atipicas"):
        if int(p[k]) < 1:
            fallos.append("reentrenamiento.%s debe ser >= 1 (es %r)" % (k, p[k]))
    try:
        tramos_excluidos(p["excluir_ventanas"])
    except (ValueError, TypeError) as e:
        fallos.append("reentrenamiento.excluir_ventanas: %s" % e)
    if float(p["psi_alerta"]) >= float(p["psi_rechazo_lote"]):
        fallos.append("reentrenamiento.psi_alerta (%s) debe ser menor que psi_rechazo_lote "
                      "(%s): la deriva avisa antes de rechazar" % (p["psi_alerta"],
                                                                 p["psi_rechazo_lote"]))
    return fallos


def tramos_excluidos(lista) -> list[tuple[str, float, float]]:
    """["IP@ini/fin", ...] -> [(ip, t_ini, t_fin)]. "*" vale para cualquier IP."""
    tramos = []
    for t in lista or []:
        ip, _, rango = str(t).partition("@")
        ini, _, fin = rango.partition("/")
        if not (ip and ini and fin):
            raise ValueError("%r no tiene la forma IP@ini/fin" % t)
        a, b = marca(ini), marca(fin)
        if b <= a:
            raise ValueError("%r: el fin no es posterior al inicio" % t)
        tramos.append((ip, a, b))
    return tramos


def excluida(fila: dict, tramos) -> bool:
    if not tramos:
        return False
    t = marca(fila["window_end_utc"])
    return any((ip == "*" or ip == fila["entity_ip"]) and a <= t <= b for ip, a, b in tramos)


# ------------------------------------------------------- registro encadenado

def _ruta_registro(cfg: dict) -> Path:
    return cfg["dir"] / "registro.jsonl"


def anotar(cfg: dict, entrada: dict) -> dict:
    """Anade una linea al registro con el hash de la anterior (cadena)."""
    ruta = _ruta_registro(cfg)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    anterior = sha_texto(lineas[-1]) if lineas else "0" * 64
    entrada = dict(entrada, anterior=anterior)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, sort_keys=True, ensure_ascii=False) + "\n")
    return entrada


def verificar_registro(cfg: dict) -> list[str]:
    """Cadena intacta y cada lote con el hash que se anoto."""
    ruta = _ruta_registro(cfg)
    if not ruta.exists():
        return []
    fallos = []
    anterior = "0" * 64
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        e = json.loads(linea)
        if e.get("anterior") != anterior:
            fallos.append("linea %d: la cadena se rompe (registro editado o borrado)" % n)
        anterior = sha_texto(linea)
        if e.get("tipo") == "lote":
            f = cfg["dir"] / "lotes" / e["fichero"]
            if not f.exists():
                fallos.append("linea %d: falta %s" % (n, f.name))
            elif sha256(f) != e["sha256"]:
                fallos.append("linea %d: %s cambio despues de registrarse" % (n, f.name))
    return fallos


def lotes_registrados(cfg: dict) -> list[dict]:
    return [e for e in leer_jsonl(_ruta_registro(cfg)) if e.get("tipo") == "lote"]


# --------------------------------------------------------- conjunto de oro

def crear_oro(cfg: dict, desde: Path, particion: str = "test") -> dict:
    destino = ruta_politica(cfg, "oro")
    if destino.exists():
        raise SystemExit("ya existe %s. El conjunto de oro no se rehace: es la "
                         "referencia fija contra la que se mide todo." % destino)
    columnas, filas = leer_csv(desde)
    if "particion" not in columnas:
        raise SystemExit("%s no tiene columna 'particion': use la salida de "
                         "particionar_linea_base.py" % desde)
    oro = [f for f in filas if f["particion"] == particion and elegible(f)]
    if not oro:
        raise SystemExit("no hay filas elegibles con particion=%s" % particion)
    escribir_csv(destino, [c for c in columnas if c != "particion"], oro)
    destino.chmod(0o444)
    info = {"tipo": "oro", "generado": ahora(), "origen": str(desde),
            "origen_sha256": sha256(desde), "particion": particion,
            "filas": len(oro), "fichero": destino.name, "sha256": sha256(destino),
            "primera_ventana": oro[0]["window_end_utc"],
            "ultima_ventana": oro[-1]["window_end_utc"]}
    destino.with_suffix(".json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    anotar(cfg, info)
    return info


def cargar_oro(cfg: dict) -> list[dict] | None:
    ruta = ruta_politica(cfg, "oro")
    if not ruta or not ruta.exists():
        return None
    info = ruta.with_suffix(".json")
    if info.exists():
        esperado = json.loads(info.read_text(encoding="utf-8"))["sha256"]
        if sha256(ruta) != esperado:
            raise SystemExit("el conjunto de oro cambio desde que se creo (%s): no es "
                             "una referencia fiable" % ruta)
    return leer_csv(ruta)[1]


# ---------------------------------------------------------------- saneamiento

def _abrir(ruta: Path):
    if ruta.suffix == ".gz":
        return gzip.open(ruta, "rt", encoding="utf-8", errors="replace")
    return ruta.open(encoding="utf-8", errors="replace")


def marcadas_por_motor(registro: Path, ini: float, fin: float) -> dict[str, list[float]]:
    """IP -> instantes en que el motor NO dio PERMIT (o salto un heuristico)."""
    marcas = defaultdict(list)
    candidatos = [registro, Path(str(registro) + ".1")]
    candidatos += sorted(registro.parent.glob(registro.name + ".*.gz"))
    for ruta in candidatos:
        if not ruta.exists():
            continue
        with _abrir(ruta) as f:
            for linea in f:
                if '"decision"' not in linea:
                    continue
                try:
                    d = json.loads(linea)
                    t = marca(d["window_end_utc"])
                except (ValueError, KeyError):
                    continue
                if not (ini <= t < fin):
                    continue
                if d.get("decision") not in (None, "PERMIT") or d.get("heuristico"):
                    marcas[str(d.get("entity_ip"))].append(t)
    return marcas


def marcadas_por_suricata(eve: Path, ini: float, fin: float) -> dict[str, list[float]]:
    marcas = defaultdict(list)
    try:
        f = _abrir(eve)
    except OSError:              # no existe o sin permiso: queda el filtro del motor
        return marcas
    with f:
        for linea in f:
            if '"event_type":"alert"' not in linea.replace(" ", ""):
                continue
            try:
                e = json.loads(linea)
                t = marca(e["timestamp"].replace("+0000", "+00:00"))
            except (ValueError, KeyError):
                continue
            if ini <= t < fin:
                for campo in ("src_ip", "dest_ip"):
                    if e.get(campo):
                        marcas[str(e[campo])].append(t)
    return marcas


def limites(referencia: list[dict], nombres: list[str], q: float) -> dict:
    lim = {}
    for n in nombres:
        vals = [float(f[n]) for f in referencia]
        lo, hi = cuantil(vals, 1 - q), cuantil(vals, q)
        lim[n] = (lo, hi, (hi - lo) or 1.0)
    return lim


def atipicas(fila: dict, lim: dict, tolerancia: float) -> int:
    n = 0
    for nombre, (lo, hi, rango) in lim.items():
        v = float(fila[nombre])
        if v > hi + tolerancia * rango or v < lo - tolerancia * rango:
            n += 1
    return n


def cerrar_lote(cfg: dict, dia: date, aceptar: bool = False) -> dict:
    p = cfg["politica"]
    nombre = "lote-%s.csv" % dia.strftime("%Y%m%d")
    destino = cfg["dir"] / "lotes" / nombre
    if any(e["fichero"] == nombre for e in lotes_registrados(cfg)):
        return {"tipo": "lote", "fichero": nombre, "estado": "ya_registrado"}
    if not cfg["dataset"].exists():
        return {"tipo": "lote", "fichero": nombre, "estado": "sin_dataset"}

    prefijo = dia.isoformat()
    with cfg["dataset"].open(newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas = list(lector.fieldnames or [])
        filas = [r for r in lector if str(r.get("window_end_utc", "")).startswith(prefijo)]
    entrada = len(filas)
    filas = [r for r in filas if elegible(r)]
    no_elegibles = entrada - len(filas)

    ini = datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc).timestamp()
    fin = ini + 86400
    margen = float(p["margen_contaminacion_s"])
    marcas = marcadas_por_motor(cfg["registro_motor"], ini - margen, fin + margen)
    if p["usar_alertas_suricata"]:
        for ip, ts in marcadas_por_suricata(cfg["eve"], ini - margen, fin + margen).items():
            marcas[ip].extend(ts)

    limpias, contaminadas = [], Counter()
    for r in filas:
        t = marca(r["window_end_utc"])
        if any(abs(t - m) <= margen for m in marcas.get(r["entity_ip"], ())):
            contaminadas[r["entity_ip"]] += 1
        else:
            limpias.append(r)

    oro = cargar_oro(cfg)
    nombres = nombres_v2()
    descartadas_atipicas, psi_vars = 0, {}
    if oro:
        lim = limites(oro, nombres, float(p["cuantil_referencia"]))
        maximo = int(p["max_variables_atipicas"])
        quedan = []
        for r in limpias:
            if atipicas(r, lim, float(p["tolerancia_atipica"])) >= maximo:
                descartadas_atipicas += 1
            else:
                quedan.append(r)
        limpias = quedan
        if limpias:
            psi_vars = {n: psi([float(f[n]) for f in oro], [float(f[n]) for f in limpias])
                        for n in nombres}
    psi_max = max(psi_vars.values()) if psi_vars else None

    if len(limpias) < int(p["filas_minimas_lote"]):
        estado = "insuficiente"
    elif psi_max is not None and psi_max > float(p["psi_rechazo_lote"]):
        estado = "aceptado_a_mano" if aceptar else "rechazado"
    else:
        estado = "aceptado"

    escribir_csv(destino, columnas, limpias)
    peores = sorted(psi_vars.items(), key=lambda kv: -kv[1])[:5]
    return anotar(cfg, {
        "tipo": "lote", "generado": ahora(), "dia": prefijo, "fichero": nombre,
        "sha256": sha256(destino), "estado": estado,
        "filas": {"entrada": entrada, "no_elegibles": no_elegibles,
                  "contaminadas": sum(contaminadas.values()),
                  "atipicas": descartadas_atipicas, "salida": len(limpias)},
        "ips_marcadas": sorted(contaminadas)[:50],
        "psi_max": psi_max, "psi_peores": peores,
        "referencia": "oro" if oro else "sin conjunto de oro: solo filtro de contaminacion",
        "origen": {"dataset": str(cfg["dataset"]), "detector_vigente": cfg["detector"],
                   "modelo_vigente_sha256": sha256(cfg["modelo"]) if cfg["modelo"].is_file() else None},
    })


# ------------------------------------------------------------------- modelos

def cargar_modelo(modelo: Path, manifiesto: Path, detector: str):
    import joblib
    m = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    cal = m["detectors"][detector]["calibration"]
    if cal.get("comparison") != "score < threshold":
        raise ValueError("regla de comparacion inesperada: %r" % cal.get("comparison"))
    return joblib.load(modelo), float(cal["threshold"])


def puntuar(pipeline, filas: list[dict], nombres: list[str]) -> list[float]:
    import numpy as np
    if not filas:
        return []
    X = np.asarray([[float(f[n]) for n in nombres] for f in filas], dtype=float)
    return [float(s) for s in pipeline.score_samples(X)]


def tasa(puntos: list[float], umbral: float) -> float | None:
    return round(sum(1 for s in puntos if s < umbral) / len(puntos), 6) if puntos else None


# -------------------------------------------------------------------- deriva

def medir_deriva(cfg: dict, dia: date) -> dict:
    p = cfg["politica"]
    oro = cargar_oro(cfg)
    if oro is None:
        return {"tipo": "deriva", "dia": dia.isoformat(), "estado": "sin_oro"}
    ruta = cfg["dir"] / "deriva.jsonl"
    if any(e.get("dia") == dia.isoformat() for e in leer_jsonl(ruta)):
        return {"tipo": "deriva", "dia": dia.isoformat(), "estado": "ya_medida"}
    nombres = nombres_v2()
    pipe, umbral = cargar_modelo(cfg["modelo"], cfg["manifiesto"], cfg["detector"])
    s_oro = puntuar(pipe, oro, nombres)

    lote = cfg["dir"] / "lotes" / ("lote-%s.csv" % dia.strftime("%Y%m%d"))
    s_lote = puntuar(pipe, leer_csv(lote)[1], nombres) if lote.exists() else []

    ini = datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc).timestamp()
    total = alert = 0
    for r in [cfg["registro_motor"], Path(str(cfg["registro_motor"]) + ".1")]:
        if not r.exists():
            continue
        with _abrir(r) as f:
            for linea in f:
                if '"decision"' not in linea:
                    continue
                try:
                    d = json.loads(linea)
                    t = marca(d["window_end_utc"])
                except (ValueError, KeyError):
                    continue
                if ini <= t < ini + 86400:
                    total += 1
                    alert += d.get("decision") != "PERMIT"

    e = {
        "tipo": "deriva", "dia": dia.isoformat(), "generado": ahora(),
        "detector": cfg["detector"],
        "fpr_oro": tasa(s_oro, umbral),
        "psi_puntuaciones": psi(s_oro, s_lote) if s_lote else None,
        "tasa_anomala_lote": tasa(s_lote, umbral),
        "filas_lote": len(s_lote),
        "tasa_alert_motor": round(alert / total, 6) if total else None,
        "decisiones_motor": total,
    }
    e["senal"] = bool((e["psi_puntuaciones"] or 0) > float(p["psi_alerta"]) or
                      (e["tasa_anomala_lote"] or 0) > float(p["tasa_anomala_max"]))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, sort_keys=True) + "\n")
    return e


def deriva_sostenida(cfg: dict) -> bool:
    n = int(cfg["politica"]["dias_deriva"])
    serie = [e for e in leer_jsonl(cfg["dir"] / "deriva.jsonl") if "senal" in e]
    return len(serie) >= n and all(e["senal"] for e in serie[-n:])


# ----------------------------------------------------------------- candidato

def _candidatos(cfg: dict) -> list[dict]:
    salida = []
    for f in sorted((cfg["dir"] / "candidatos").glob("*/candidato.json")):
        salida.append(json.loads(f.read_text(encoding="utf-8")))
    return salida


def _historial(cfg: dict) -> list[dict]:
    return leer_jsonl(cfg["dir"] / "modelos.jsonl")


def motivo_para_entrenar(cfg: dict, hoy: date) -> str | None:
    if deriva_sostenida(cfg):
        return "deriva sostenida %d dias" % int(cfg["politica"]["dias_deriva"])
    fechas = [c["generado"][:10] for c in _candidatos(cfg)]
    oro_info = ruta_politica(cfg, "oro").with_suffix(".json")
    if not fechas and oro_info.exists():
        fechas = [json.loads(oro_info.read_text(encoding="utf-8"))["generado"][:10]]
    if not fechas:
        return None
    ultima = date.fromisoformat(max(fechas))
    if (hoy - ultima).days >= int(cfg["politica"]["cadencia_dias"]):
        return "cadencia de %d dias" % int(cfg["politica"]["cadencia_dias"])
    return None


def lotes_para_entrenar(cfg: dict) -> list[dict]:
    """Lotes aceptados que ningun modelo promovido ha usado todavia."""
    usados = set()
    for h in _historial(cfg):
        if h.get("accion") == "promover":
            usados.update(l["fichero"] for l in h.get("lotes", []))
    return [e for e in lotes_registrados(cfg)
            if e["estado"] in ESTADOS_LOTE_UTILES and e["fichero"] not in usados]


def limitar_influencia(nuevas: list[dict], n_base: int, f_nueva: float,
                       f_ip: float) -> tuple[list[dict], dict]:
    """Recorta lo nuevo: ninguna IP > f_ip de lo nuevo, y lo nuevo <= f_nueva del total."""
    por_ip = defaultdict(list)
    for r in nuevas:
        por_ip[r["entity_ip"]].append(r)
    tope_ip = max(1, int(f_ip * len(nuevas)))
    recortadas = {ip: len(rs) - tope_ip for ip, rs in por_ip.items() if len(rs) > tope_ip}
    nuevas = sorted((r for rs in por_ip.values() for r in submuestra(rs, tope_ip)),
                    key=lambda r: (r["window_end_utc"], r["entity_ip"]))
    tope = int(f_nueva / (1 - f_nueva) * n_base)
    antes = len(nuevas)
    nuevas = submuestra(nuevas, tope)
    return nuevas, {"tope_por_ip": tope_ip, "ips_recortadas": recortadas,
                    "tope_nuevas": tope, "recortadas_por_fraccion": antes - len(nuevas)}


def _py(script: Path, *argumentos: str) -> dict:
    r = subprocess.run([sys.executable, str(script), *argumentos],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("%s fallo:\n%s%s" % (script.name, r.stdout[-2000:], r.stderr[-2000:]))
    texto = r.stdout
    return json.loads(texto[texto.index("{"):texto.rindex("}") + 1])


def veredicto(actual: dict, cand: dict, p: dict) -> tuple[str, str]:
    fa, fc = actual.get("fpr_oro"), cand.get("fpr_oro")
    if fa is None or fc is None:
        return "EVALUACION_INCOMPLETA", "sin conjunto de oro no hay comparacion"
    if fc > fa + float(p["tolerancia_fpr"]):
        return "NO_PROMOVER", "FPR en oro %.2f %% frente a %.2f %% del vigente" % (fc * 100, fa * 100)
    da, dc = actual.get("deteccion"), cand.get("deteccion")
    if da is None or dc is None:
        return ("EVALUACION_INCOMPLETA",
                "FPR no empeora, pero sin conjunto de ataques no se sabe si detecta igual: "
                "configure reentrenamiento.ataques")
    if dc < da - float(p["tolerancia_deteccion"]):
        return "NO_PROMOVER", "deteccion %.1f %% frente a %.1f %%" % (dc * 100, da * 100)
    return "PROMOVIBLE", "FPR <= vigente y deteccion >= vigente sobre los mismos conjuntos"


def generar_candidato(cfg: dict, hoy: date, forzar: bool = False) -> dict:
    p = cfg["politica"]
    motivo = "forzado a mano" if forzar else motivo_para_entrenar(cfg, hoy)
    if not motivo:
        return {"estado": "no_toca"}
    fallos = verificar_registro(cfg)
    if fallos:
        return {"estado": "registro_roto", "fallos": fallos}
    oro = cargar_oro(cfg)
    base_ruta = ruta_politica(cfg, "base")
    if oro is None or base_ruta is None or not base_ruta.exists():
        return {"estado": "falta_referencia",
                "detalle": "hacen falta reentrenamiento.oro y reentrenamiento.base: sin la "
                           "base no hay limite de influencia posible"}
    lotes = lotes_para_entrenar(cfg)
    if len(lotes) < int(p["dias_minimos"]):
        return {"estado": "pocos_datos", "motivo": motivo, "lotes": len(lotes),
                "necesarios": int(p["dias_minimos"])}

    claves_oro = {clave(f) for f in oro}
    tramos = tramos_excluidos(p["excluir_ventanas"])
    columnas, base = leer_csv(base_ruta)
    columnas = [c for c in columnas if c != "particion"]
    base = [r for r in base if r.get("particion") in ("train", "validation")
            and elegible(r) and clave(r) not in claves_oro]
    antes_base = len(base)
    base = [r for r in base if not excluida(r, tramos)]
    excluidas = {"base": antes_base - len(base), "lotes": 0}
    nuevas = []
    for e in lotes:
        for r in leer_csv(cfg["dir"] / "lotes" / e["fichero"])[1]:
            if clave(r) in claves_oro:
                continue
            if excluida(r, tramos):
                excluidas["lotes"] += 1
                continue
            nuevas.append(r)
    nuevas, influencia = limitar_influencia(
        nuevas, len(base), float(p["max_fraccion_nueva"]), float(p["max_fraccion_ip"]))

    ident = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    carpeta = cfg["dir"] / "candidatos" / ident
    carpeta.mkdir(parents=True, exist_ok=False)
    combinado = carpeta / "entrenamiento.csv"
    filas = sorted(base + nuevas, key=lambda r: (r["window_end_utc"], r["entity_ip"]))
    escribir_csv(combinado, columnas, filas)

    particion = _py(PARTICIONAR, "--entrada", str(combinado),
                    "--salida", str(carpeta / "particionado.csv"),
                    "--informe", str(carpeta / "particion.json"), "--solo-elegibles")
    entreno = _py(ENTRENAR, "--entrada", str(carpeta / "particionado.csv"),
                  "--schema", str(ESQUEMA_V2), "--salida", str(carpeta / "paquete.joblib"),
                  "--informe", str(carpeta / "paquete.json"), "--alpha", str(p["alpha"]),
                  "--semilla", str(p["semilla"]))
    # Los dos CSV pesan como la base entera; se reconstruyen del linaje (base +
    # lotes, con sus hashes), asi que solo se guarda el hash del combinado.
    huella_entrenamiento = sha256(combinado)
    (carpeta / "particionado.csv").unlink()
    combinado.unlink()

    sys.path.insert(0, str(REPO / "scripts/modeling"))
    from promover_preliminar import promover
    detector = "if_aprendizaje_%s" % ident.replace("-", "_")
    promo = promover(carpeta / "paquete.joblib", detector, carpeta / "modelo.joblib",
                     carpeta / "manifiesto.json", carpeta / "paquete.json")

    nombres = nombres_v2()
    ataques_ruta = ruta_politica(cfg, "ataques")
    ataques = leer_csv(ataques_ruta)[1] if ataques_ruta and ataques_ruta.exists() else []
    resultados = {}
    for quien, (mod, man, det) in {
            "vigente": (cfg["modelo"], cfg["manifiesto"], cfg["detector"]),
            "candidato": (carpeta / "modelo.joblib", carpeta / "manifiesto.json", detector)}.items():
        pipe, umbral = cargar_modelo(mod, man, det)
        resultados[quien] = {"detector": det, "umbral": umbral,
                             "fpr_oro": tasa(puntuar(pipe, oro, nombres), umbral),
                             "deteccion": tasa(puntuar(pipe, ataques, nombres), umbral)}
    juicio, razon = veredicto(resultados["vigente"], resultados["candidato"], p)

    ficha = {
        "id": ident, "generado": ahora(), "motivo": motivo, "detector": detector,
        "veredicto": juicio, "razon": razon, "resultados": resultados,
        "filas": {"base": len(base), "nuevas": len(nuevas),
                  "fraccion_nueva": round(len(nuevas) / max(1, len(base) + len(nuevas)), 4),
                  "particion": particion.get("reparto")},
        "influencia": influencia,
        "excluidas_por_politica": dict(excluidas, tramos=list(p["excluir_ventanas"])),
        "linaje": {
            "lotes": [{"fichero": e["fichero"], "sha256": e["sha256"]} for e in lotes],
            "base": {"ruta": str(base_ruta), "sha256": sha256(base_ruta)},
            "oro": {"sha256": sha256(ruta_politica(cfg, "oro"))},
            "ataques": ({"ruta": str(ataques_ruta), "sha256": sha256(ataques_ruta)}
                        if ataques else None),
            "registro_cabeza": sha_texto(_ruta_registro(cfg).read_text(
                encoding="utf-8").splitlines()[-1]),
            "entrenamiento_sha256": huella_entrenamiento,
        },
        "artefactos": {"modelo": "modelo.joblib", "modelo_sha256": promo["sha256_modelo"],
                       "manifiesto": "manifiesto.json",
                       "manifiesto_sha256": promo["sha256_manifiesto"]},
        "entrenamiento": {"fpr_validacion": entreno.get("fpr_validacion"),
                          "fpr_test": entreno.get("fpr_test"), "alpha": p["alpha"]},
    }
    (carpeta / "candidato.json").write_text(json.dumps(ficha, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    anotar(cfg, {"tipo": "candidato", "generado": ficha["generado"], "id": ident,
                 "veredicto": juicio, "motivo": motivo})
    return ficha


# --------------------------------------------------------- promover / revertir

def fijar_toml(texto: str, seccion: str, clave_: str, valor: str) -> str:
    """Cambia (o anade) `clave = valor` dentro de [seccion], sin tocar lo demas."""
    lineas = texto.splitlines(keepends=True)
    dentro, ultima = False, None
    for i, l in enumerate(lineas):
        s = l.strip()
        if s.startswith("[") and s.endswith("]"):
            if dentro:
                break
            dentro = s == "[%s]" % seccion
            ultima = i if dentro else ultima
            continue
        if dentro:
            if re.match(r"^\s*%s\s*=" % re.escape(clave_), l):
                lineas[i] = "%s = %s\n" % (clave_, valor)
                return "".join(lineas)
            if s and not s.startswith("#"):
                ultima = i
    if ultima is None:
        sep = "" if texto.endswith("\n") else "\n"
        return texto + sep + "\n[%s]\n%s = %s\n" % (seccion, clave_, valor)
    lineas.insert(ultima + 1, "%s = %s\n" % (clave_, valor))
    return "".join(lineas)


ORDENES_APLICAR = (
    "sudo .venv/bin/python scripts/setup/cyberflow_config.py --config {toml} --escribir",
    "sudo systemctl daemon-reload && sudo systemctl restart ppi-motor ppi-dashboard",
)


def promover_candidato(cfg: dict, ident: str, nota: str = "") -> dict:
    carpeta = cfg["dir"] / "candidatos" / ident
    ficha = json.loads((carpeta / "candidato.json").read_text(encoding="utf-8"))
    if ficha["veredicto"] != "PROMOVIBLE":
        raise SystemExit("el candidato %s es %s (%s): no se promueve."
                         % (ident, ficha["veredicto"], ficha["razon"]))
    for k in ("modelo", "manifiesto"):
        if sha256(carpeta / ficha["artefactos"][k]) != ficha["artefactos"][k + "_sha256"]:
            raise SystemExit("%s cambio despues de evaluarse: no se promueve" % k)

    toml = cfg["toml"]
    copias = cfg["dir"] / "modelos"
    copias.mkdir(parents=True, exist_ok=True)
    copia = copias / ("%s.antes-de-%s" % (toml.name, ident))
    shutil.copy2(toml, copia)

    rel = carpeta.relative_to(cfg["raiz"]).as_posix()
    texto = toml.read_text(encoding="utf-8")
    texto = fijar_toml(texto, "rutas", "modelo", '"%s/modelo.joblib"' % rel)
    texto = fijar_toml(texto, "rutas", "manifiesto", '"%s/manifiesto.json"' % rel)
    texto = fijar_toml(texto, "motor", "detector", '"%s"' % ficha["detector"])
    texto = fijar_toml(texto, "motor", "calibrado_en_esta_red", "true")
    toml.write_text(texto, encoding="utf-8")

    entrada = {"accion": "promover", "fecha": ahora(), "candidato": ident,
               "detector": ficha["detector"], "modelo_sha256": ficha["artefactos"]["modelo_sha256"],
               "anterior": {"detector": cfg["detector"], "copia_toml": copia.name},
               "lotes": ficha["linaje"]["lotes"], "nota": nota}
    with (cfg["dir"] / "modelos.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    anotar(cfg, {"tipo": "promocion", "generado": entrada["fecha"], "id": ident,
                 "detector": ficha["detector"]})
    _podar(cfg)
    return {"promovido": ident, "copia": str(copia), "aplicar": ordenes_aplicar(cfg)}


def revertir(cfg: dict) -> dict:
    hist = _historial(cfg)
    revertidos = {h["candidato"] for h in hist if h.get("accion") == "revertir"}
    pendientes = [h for h in hist if h.get("accion") == "promover"
                  and h["candidato"] not in revertidos]
    if not pendientes:
        raise SystemExit("no hay ninguna promocion que revertir")
    ultima = pendientes[-1]
    copia = cfg["dir"] / "modelos" / ultima["anterior"]["copia_toml"]
    shutil.copy2(copia, cfg["toml"])
    entrada = {"accion": "revertir", "fecha": ahora(), "candidato": ultima["candidato"],
               "vuelve_a": ultima["anterior"]["detector"]}
    with (cfg["dir"] / "modelos.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    anotar(cfg, {"tipo": "reversion", "generado": entrada["fecha"],
                 "id": ultima["candidato"], "vuelve_a": entrada["vuelve_a"]})
    return {"revertido": ultima["candidato"], "vuelve_a": entrada["vuelve_a"],
            "aplicar": ordenes_aplicar(cfg)}


def ordenes_aplicar(cfg: dict) -> list[str]:
    """Lo que hace falta con sudo para que el motor cargue el .toml nuevo."""
    toml = cfg["toml"].resolve()
    try:
        rel = toml.relative_to(Path(cfg["raiz"]).resolve()).as_posix()
    except ValueError:
        rel = str(toml)
    return [o.format(toml=rel) for o in ORDENES_APLICAR]


def _podar(cfg: dict) -> None:
    """Conserva los N ultimos modelos promovidos y los candidatos no promovidos recientes."""
    n = int(cfg["politica"]["conservar_modelos"])
    promovidos = [h["candidato"] for h in _historial(cfg) if h.get("accion") == "promover"]
    vivos = set(promovidos[-n:])
    for c in _candidatos(cfg)[:-n]:
        if c["id"] not in vivos and c["id"] not in promovidos:
            shutil.rmtree(cfg["dir"] / "candidatos" / c["id"], ignore_errors=True)


# --------------------------------------------------------------------- estado

def estado(cfg: dict) -> dict:
    """Todo lo que el panel ensena. Solo lee ficheros: no carga modelos."""
    p = cfg["politica"]
    oro_info = ruta_politica(cfg, "oro").with_suffix(".json")
    lotes = lotes_registrados(cfg)
    cands = _candidatos(cfg)
    hist = _historial(cfg)
    return {
        "politica": {k: p[k] for k in POLITICA if k not in ("directorio",)},
        "oro": json.loads(oro_info.read_text(encoding="utf-8")) if oro_info.exists() else None,
        "registro_integro": not verificar_registro(cfg),
        "lotes": lotes[-30:],
        "lotes_disponibles": len(lotes_para_entrenar(cfg)),
        "deriva": leer_jsonl(cfg["dir"] / "deriva.jsonl")[-30:],
        "deriva_sostenida": deriva_sostenida(cfg),
        "candidatos": [{k: c.get(k) for k in ("id", "generado", "motivo", "veredicto", "razon",
                                               "resultados", "filas", "influencia")}
                       for c in cands[-5:]],
        "historial": hist[-10:],
        "detector_vigente": cfg["detector"],
        "proximo": motivo_para_entrenar(cfg, datetime.now(timezone.utc).date()),
    }


# ----------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--raiz", type=Path, help="sustituye a rutas.raiz (pruebas)")
    sub = ap.add_subparsers(dest="orden", required=True)
    o = sub.add_parser("oro")
    o.add_argument("--desde", type=Path, required=True)
    o.add_argument("--particion", default="test")
    for nombre in ("lote", "deriva"):
        s = sub.add_parser(nombre)
        s.add_argument("--dia", type=date.fromisoformat)
        if nombre == "lote":
            s.add_argument("--aceptar", action="store_true",
                           help="aceptar un lote rechazado por PSI tras revisarlo")
    c = sub.add_parser("candidato")
    c.add_argument("--forzar", action="store_true")
    sub.add_parser("diario")
    pr = sub.add_parser("promover")
    pr.add_argument("id")
    pr.add_argument("--nota", default="")
    sub.add_parser("revertir")
    sub.add_parser("estado")
    sub.add_parser("verificar")
    a = ap.parse_args(argv)

    cfg = cargar_config(a.config, a.raiz)
    ayer = datetime.now(timezone.utc).date() - timedelta(days=1)
    hoy = ayer + timedelta(days=1)

    if a.orden == "oro":
        r = crear_oro(cfg, a.desde, a.particion)
    elif a.orden == "lote":
        r = cerrar_lote(cfg, a.dia or ayer, a.aceptar)
    elif a.orden == "deriva":
        r = medir_deriva(cfg, a.dia or ayer)
    elif a.orden == "candidato":
        r = generar_candidato(cfg, hoy, a.forzar)
    elif a.orden == "diario":
        if not cfg["politica"]["activo"]:
            r = {"estado": "inactivo",
                 "detalle": "reentrenamiento.activo = false en %s" % cfg["toml"].name}
        else:
            r = {"lote": cerrar_lote(cfg, ayer), "deriva": medir_deriva(cfg, ayer)}
            ficha = generar_candidato(cfg, hoy)
            r["candidato"] = ({k: ficha.get(k) for k in ("id", "veredicto", "razon", "motivo")}
                              if "id" in ficha else ficha)
    elif a.orden == "promover":
        r = promover_candidato(cfg, a.id, a.nota)
    elif a.orden == "revertir":
        r = revertir(cfg)
    elif a.orden == "estado":
        r = estado(cfg)
    else:
        fallos = verificar_registro(cfg)
        r = {"registro_integro": not fallos, "fallos": fallos}
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
    if a.orden == "verificar" and not r["registro_integro"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
