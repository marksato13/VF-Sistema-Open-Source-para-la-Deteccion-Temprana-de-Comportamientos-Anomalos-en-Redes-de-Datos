#!/usr/bin/env python3
"""[SRV-DMZ adminsrvdmz] Estado de SOMBRA de srv-dmz (Etapa 4). Solo lectura.

Sustituye a ``pgrep -af agente_enforce | grep -- --aplicar`` y a ``nft list tables | grep -c cyberflow``, que
fallaban en los dos sentidos:
  - FALSO POSITIVO: el ``bash -c '…agente_enforce…--aplicar…'`` que lanza la propia comprobación (por SSH) contiene
    las dos palabras en su línea de comandos y se contaba como agente aplicando;
  - FALSO NEGATIVO: si ``sudo -n``, ``nft``, ``pgrep`` o la lectura de la traza fallaban, ``grep -c`` daba 0 y eso
    se leía como «cero restricciones».

Aquí:
  - Un AGENTE es un proceso cuyo argv lleva como SCRIPT (primer argumento no opción tras el intérprete python, o
    argv[0] si se ejecuta directo) un fichero llamado exactamente ``agente_enforce.py`` o ``agente_enforce_v2.py``.
    Un shell (``sh -c``/``bash -c``) que solo menciona el nombre en su texto NO es agente; el python que lanza sí.
    Se excluyen este proceso y toda su cadena de ancestros (``/proc/<pid>/stat``, campo ppid).
  - Aplica = ``--aplicar`` (o ``--aplicar=…``) entre los argumentos del agente, o en el ExecStart de la unidad v2.
  - Cualquier lectura que falle (``/proc`` ilegible, ``systemctl``, ``sudo -n nft``, traza) deja el estado en
    DESCONOCIDO: nunca se convierte en 0.

Estados (y código de salida):
  0  sombra       ningún indicio de aplicación y todas las lecturas pedidas hechas, y además lo esperado en la 4C
                  (agente v2 activo, v1 timer inactivo y deshabilitado, v1 servicio inactivo)
  1  aplicando    agente con --aplicar, unidad con --aplicar, tabla cyberflow*, evento ``aplicacion`` en la traza o
                  ruleset distinto del respaldo (salvo contadores): restricción posible o real
  2  desconocido  alguna lectura falló o no se pudo hacer: no se sabe
  3  sombra_no_conforme  sin indicios de aplicación, pero las unidades no están como exige la 4C

Uso:
  python3 -I estado_sombra.py [--alcance procesos|completo] [--respaldo DIR_CON_ruleset.nft] [--json SALIDA]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

VERSION = "2026-11-02.1"
AGENTES = {"agente_enforce.py", "agente_enforce_v2.py"}
SHELLS = {"sh", "bash", "dash", "zsh", "ksh", "busybox"}
TRAZA = "/var/lib/cyberflow/agente/traza.jsonl"
UNIDADES = ("ppi-enforce-agent.timer", "ppi-enforce-agent.service", "ppi-enforce-agent-v2-dmz.service")
_OPC_CON_VALOR = {"-W", "-X", "-c", "-m", "--check-hash-based-pycs"}


def argv_de(raiz: Path, pid: str) -> list[str] | None:
    """argv del proceso; None si terminó entre listar y leer; lanza PermissionError si no es legible."""
    try:
        b = (raiz / pid / "cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return [x.decode("utf-8", "replace") for x in b.split(b"\0") if x != b""] if b else []


def ppid_de(raiz: Path, pid: int) -> int | None:
    try:
        st = (raiz / str(pid) / "stat").read_text()
    except OSError:
        return None
    try:
        return int(st[st.rindex(")") + 2:].split()[1])
    except (ValueError, IndexError):
        return None


def cadena_propia(raiz: Path, pid: int) -> set[int]:
    vistos = set()
    while pid and pid not in vistos and pid > 1:
        vistos.add(pid)
        pid = ppid_de(raiz, pid)
    return vistos


def script_de(argv: list[str]) -> str | None:
    """Fichero que ejecuta el proceso si es un intérprete python (o el propio argv[0] si es un .py)."""
    if not argv:
        return None
    base = os.path.basename(argv[0])
    if base in SHELLS:
        return None
    if base.startswith("python"):
        i = 1
        while i < len(argv) and argv[i].startswith("-"):
            if argv[i] in ("-c", "-m"):
                return None  # código en línea o módulo: no es un fichero de agente
            i += 2 if argv[i] in _OPC_CON_VALOR else 1
        return argv[i] if i < len(argv) else None
    return argv[0]


def es_agente(argv: list[str]) -> tuple[bool, bool]:
    """(es agente, lleva --aplicar)."""
    s = script_de(argv)
    if s is None or os.path.basename(s) not in AGENTES:
        return False, False
    resto = argv[argv.index(s) + 1:]
    return True, any(a == "--aplicar" or a.startswith("--aplicar=") for a in resto)


def procesos(raiz: Path, propio: int) -> dict:
    excl = cadena_propia(raiz, propio)
    agentes, ilegibles = [], []
    try:
        pids = [p for p in os.listdir(raiz) if p.isdigit()]
    except OSError as e:
        return {"ok": False, "motivo": f"{raiz} no legible: {e.__class__.__name__}"}
    for p in sorted(pids, key=int):
        if int(p) in excl:
            continue
        try:
            argv = argv_de(raiz, p)
        except OSError as e:
            ilegibles.append({"pid": int(p), "motivo": e.__class__.__name__})
            continue
        if argv is None:
            continue
        ag, aplica = es_agente(argv)
        if ag:
            agentes.append({"pid": int(p), "aplicar": aplica, "argv": argv})
    r = {"ok": not ilegibles, "agentes": agentes, "excluidos_propios": sorted(excl),
         "con_aplicar": sum(1 for a in agentes if a["aplicar"])}
    if ilegibles:
        r["ilegibles"] = ilegibles
        r["motivo"] = f"{len(ilegibles)} proceso(s) con cmdline ilegible (¿hidepid?): no se puede descartar un agente"
    return r


def correr(cmd: list[str], timeout=20) -> tuple[int | None, str, str]:
    try:
        # stdin cerrado: por SSH no consume la entrada del guion que lo llama, y no hereda un descriptor inválido
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "", f"{e.__class__.__name__}: {e}"


def unidades(systemctl: list[str]) -> dict:
    out = {"ok": True}
    for u in UNIDADES:
        rc, so, se = correr(systemctl + ["show", u, "-p", "ActiveState", "-p", "UnitFileState", "-p", "LoadState",
                                         "-p", "ExecStart"])
        if rc != 0:
            out["ok"] = False
            out[u] = {"ok": False, "motivo": f"systemctl rc={rc} {se.strip()[:120]}"}
            continue
        kv = dict(l.split("=", 1) for l in so.splitlines() if "=" in l)
        if "ActiveState" not in kv:
            out["ok"] = False
            out[u] = {"ok": False, "motivo": "salida de systemctl sin ActiveState"}
            continue
        ex = kv.get("ExecStart", "")
        out[u] = {"ok": True, "activo": kv.get("ActiveState"), "habilitado": kv.get("UnitFileState"),
                  "carga": kv.get("LoadState"),
                  "exec_con_aplicar": bool(re.search(r"(^|[\s;])--aplicar(=|\s|;|$)", ex))}
    return out


def tablas_nft(sudo: list[str], nft: list[str]) -> dict:
    rc, so, se = correr(sudo + nft + ["list", "tables"])
    if rc != 0:
        return {"ok": False, "motivo": f"nft list tables rc={rc} {se.strip()[:120]}"}
    tablas = [l.split()[1:] for l in so.splitlines() if l.startswith("table ")]
    cf = [" ".join(t) for t in tablas if any("cyberflow" in x for x in t)]
    return {"ok": True, "tablas": len(tablas), "cyberflow": cf}


def _norm(txt: str) -> list[str]:
    return [re.sub(r"expires [0-9hms.]+", "", re.sub(r"counter packets \d+ bytes \d+", "counter", l)).rstrip()
            for l in txt.splitlines() if l.strip()]


def ruleset(sudo: list[str], nft: list[str], respaldo: Path) -> dict:
    try:
        ref = (respaldo / "ruleset.nft").read_text(encoding="utf-8")
    except OSError as e:
        return {"ok": False, "motivo": f"respaldo ruleset.nft no legible: {e.__class__.__name__}"}
    rc, so, se = correr(sudo + nft + ["list", "ruleset"])
    if rc != 0:
        return {"ok": False, "motivo": f"nft list ruleset rc={rc} {se.strip()[:120]}"}
    a, b = _norm(ref), _norm(so)
    return {"ok": True, "igual_al_respaldo": a == b, "lineas": [len(a), len(b)]}


def traza(sudo: list[str], ruta: str) -> dict:
    rc, so, se = correr(sudo + ["cat", ruta])
    if rc != 0:
        return {"ok": False, "motivo": f"traza no legible ({ruta}) rc={rc} {se.strip()[:120]}"}
    ev, malas, acept = 0, 0, 0
    for l in so.splitlines():
        if not l.strip():
            continue
        try:
            d = json.loads(l)
        except ValueError:
            malas += 1
            continue
        ev += d.get("evento") == "aplicacion"
        acept += d.get("estado") == "aceptado"
    return {"ok": True, "lineas": len(so.splitlines()), "eventos_aplicacion": ev, "aceptados": acept,
            "lineas_no_json": malas}


def evaluar(alcance: str, raiz: Path, propio: int, systemctl, sudo, nft, ruta_traza: str,
            respaldo: Path | None) -> dict:
    r = {"version": VERSION, "alcance": alcance, "procesos": procesos(raiz, propio), "unidades": unidades(systemctl)}
    if alcance == "completo":
        r["nft"] = tablas_nft(sudo, nft)
        r["traza"] = traza(sudo, ruta_traza)
        if respaldo is not None:
            r["ruleset"] = ruleset(sudo, nft, respaldo)
    indicios, desconocido = [], []
    p, u = r["procesos"], r["unidades"]
    if p.get("con_aplicar"):
        indicios.append(f"{p['con_aplicar']} agente(s) en ejecución con --aplicar")
    if not p["ok"]:
        desconocido.append("procesos: " + p.get("motivo", "?"))
    for nombre in UNIDADES:
        x = u.get(nombre, {})
        if not x.get("ok"):
            desconocido.append(f"{nombre}: {x.get('motivo')}")
    t1, s1, v2 = (u.get(n, {}) for n in UNIDADES)
    # v2 debe estar en sombra: su ExecStart con --aplicar es indicio siempre (cualquier reinicio aplicaría).
    if v2.get("ok") and v2.get("exec_con_aplicar") and v2.get("carga") != "not-found":
        indicios.append("ppi-enforce-agent-v2-dmz.service: ExecStart con --aplicar")
    # v1 lleva --aplicar --sudo por diseño (ESTADO-OBSERVADO §3): es indicio solo si puede ejecutarse, es decir,
    # servicio activo o timer activo o habilitado.
    if s1.get("ok") and t1.get("ok") and s1.get("exec_con_aplicar") and (
            s1["activo"] not in ("inactive", "failed") or t1["activo"] != "inactive"
            or t1["habilitado"] not in ("disabled", "", "masked")):
        indicios.append("agente v1 (ExecStart con --aplicar --sudo) activo o con timer activo/habilitado")
    if alcance == "completo":
        if r["nft"]["ok"] and r["nft"]["cyberflow"]:
            indicios.append("tabla(s) nft cyberflow: " + ", ".join(r["nft"]["cyberflow"]))
        if not r["nft"]["ok"]:
            desconocido.append("nft: " + r["nft"]["motivo"])
        if r["traza"]["ok"] and r["traza"]["eventos_aplicacion"]:
            indicios.append(f"{r['traza']['eventos_aplicacion']} evento(s) 'aplicacion' en la traza")
        if not r["traza"]["ok"]:
            desconocido.append("traza: " + r["traza"]["motivo"])
        if "ruleset" in r:
            if r["ruleset"]["ok"] and not r["ruleset"]["igual_al_respaldo"]:
                indicios.append("ruleset efectivo distinto del respaldo (salvo contadores)")
            if not r["ruleset"]["ok"]:
                desconocido.append("ruleset: " + r["ruleset"]["motivo"])
    conforme = []
    if u.get("ok"):
        t1, s1, v2 = (u[n] for n in UNIDADES)
        if not (t1["activo"] == "inactive" and t1["habilitado"] in ("disabled", "")):
            conforme.append(f"v1 timer {t1['activo']}/{t1['habilitado']} (se espera inactive/disabled)")
        if s1["activo"] != "inactive":
            conforme.append(f"v1 servicio {s1['activo']} (se espera inactive)")
        if v2["activo"] != "active":
            conforme.append(f"v2 {v2['activo']} (se espera active)")
    if indicios:
        estado, rc = "aplicando", 1
    elif desconocido:
        estado, rc = "desconocido", 2
    elif conforme:
        estado, rc = "sombra_no_conforme", 3
    else:
        estado, rc = "sombra", 0
    r.update({"estado": estado, "rc": rc, "indicios_aplicacion": indicios, "lecturas_fallidas": desconocido,
              "no_conforme_4c": conforme})
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alcance", choices=("procesos", "completo"), default="completo",
                    help="procesos: sin sudo (procesos y unidades); completo: además nft y traza con sudo -n")
    ap.add_argument("--respaldo", type=Path, help="directorio del respaldo con ruleset.nft (compara salvo contadores)")
    ap.add_argument("--traza", default=TRAZA)
    ap.add_argument("--json", type=Path, help="escribe el resultado completo aquí")
    # inyección para pruebas offline (banco): rutas y órdenes
    ap.add_argument("--proc", type=Path, default=Path("/proc"))
    ap.add_argument("--propio-pid", type=int, default=os.getpid())
    ap.add_argument("--systemctl", default="systemctl")
    ap.add_argument("--sudo", default="sudo -n")
    ap.add_argument("--nft", default="nft")
    a = ap.parse_args(argv)
    r = evaluar(a.alcance, a.proc, a.propio_pid, shlex.split(a.systemctl), shlex.split(a.sudo), shlex.split(a.nft),
                a.traza, a.respaldo)
    if a.json:
        a.json.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    p = r["procesos"]
    print(f"estado={r['estado']} alcance={r['alcance']} agentes={len(p.get('agentes', []))} "
          f"con_aplicar={p.get('con_aplicar', '?')} "
          f"tablas_cyberflow={len(r['nft']['cyberflow']) if r.get('nft', {}).get('ok') else '?'} "
          f"eventos_aplicacion={r['traza']['eventos_aplicacion'] if r.get('traza', {}).get('ok') else '?'}")
    for k in ("indicios_aplicacion", "lecturas_fallidas", "no_conforme_4c"):
        for x in r[k]:
            print(f"  {k}: {x}")
    return r["rc"]


if __name__ == "__main__":
    sys.exit(main())
