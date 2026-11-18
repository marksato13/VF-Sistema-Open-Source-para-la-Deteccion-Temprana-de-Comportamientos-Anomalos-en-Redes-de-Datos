"""Etapa 4: estado de sombra de srv-dmz (deploy/etapa4/srvdmz/estado_sombra.py), offline.

/proc falso + órdenes falsas (systemctl, sudo, nft) para cubrir: la propia comprobación y sus envoltorios (bash -c
con las palabras «agente_enforce» y «--aplicar»), agentes reales en sombra y con --aplicar (también bajo sh -c),
procesos ilegibles, y fallos de sudo/nft/traza/systemctl que NO pueden leerse como cero.
Las pruebas con procesos reales, shell y SSH simulado están en deploy/etapa4/banco/ensayo_estado_sombra.sh.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "deploy" / "etapa4" / "srvdmz"))
import estado_sombra as es  # noqa: E402

PY = sys.executable
AG2 = ["/usr/bin/python3", "-I", "/opt/cyberflow/agente-v2/agente_enforce_v2.py", "--perfil", "dmz", "--feed",
       "/var/lib/cyberflow/feed/feed.json", "--seguir"]
COMPROBACION = ("echo v2=$(systemctl is-active ppi-enforce-agent-v2-dmz) "
                "aplicar_en_procesos=$(pgrep -af agente_enforce | grep -c -- --aplicar)")


def proc(tmp: Path, procs: dict) -> Path:
    """procs: pid -> (ppid, argv | 'ilegible')."""
    raiz = tmp / "proc"
    for pid, (ppid, argv) in procs.items():
        d = raiz / str(pid)
        d.mkdir(parents=True)
        (d / "stat").write_text(f"{pid} (x y) S {ppid} 1 1 0\n")
        if argv == "ilegible":
            (d / "cmdline").mkdir()  # leerlo como fichero da IsADirectoryError/PermissionError (OSError)
        else:
            (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + (b"\0" if argv else b""))
    return raiz


FAKE = r'''
import json, os, subprocess, sys
d = sys.argv[1]; kind = sys.argv[2]; args = sys.argv[3:]
cfg = json.load(open(os.path.join(d, "cfg.json")))
if kind == "systemctl":
    if cfg.get("systemctl_rc"):
        sys.stderr.write("Failed to connect to bus\n"); sys.exit(cfg["systemctl_rc"])
    u = args[1]; s = cfg["unidades"][u]
    print(f"ActiveState={s[0]}\nUnitFileState={s[1]}\nLoadState=loaded\nExecStart={s[2]}")
elif kind == "sudo":
    if cfg.get("sudo_falla"):
        sys.stderr.write("sudo: a password is required\n"); sys.exit(1)
    if args[0] == "cat":
        if cfg.get("traza") is None:
            sys.stderr.write("cat: no such file\n"); sys.exit(1)
        sys.stdout.write(cfg["traza"]); sys.exit(0)
    sys.exit(subprocess.run(args).returncode)
elif kind == "nft":
    if cfg.get("nft_rc"):
        sys.stderr.write("netlink: Error\n"); sys.exit(cfg["nft_rc"])
    if args == ["list", "tables"]:
        print("\n".join(cfg.get("tablas", [])))
    else:
        sys.stdout.write(cfg.get("ruleset", ""))
'''

EXEC_SOMBRA = "{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I /opt/cyberflow/agente-v2/agente_enforce_v2.py --perfil dmz --seguir ; }"
EXEC_V1 = "{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 /home/adminsrvdmz/enforce/agente_enforce.py --aplicar --sudo ; }"
SANO = {"unidades": {"ppi-enforce-agent.timer": ["inactive", "disabled", ""],
                     "ppi-enforce-agent.service": ["inactive", "static", EXEC_V1],
                     "ppi-enforce-agent-v2-dmz.service": ["active", "enabled", EXEC_SOMBRA]},
        "tablas": ["table inet filter", "table ip nat"],
        "traza": '{"evento": "recepcion", "estado": "aceptado"}\n{"evento": "recepcion", "estado": "rechazado"}\n',
        "ruleset": "table inet filter {\n counter packets 5 bytes 300\n}\n"}


def ordenes(tmp: Path, cfg: dict) -> dict:
    d = tmp / "fake"
    d.mkdir(exist_ok=True)
    (d / "fake.py").write_text(FAKE)
    (d / "cfg.json").write_text(json.dumps(cfg))
    f = f'"{Path(PY).as_posix()}" "{(d / "fake.py").as_posix()}" "{d.as_posix()}"'  # shlex: sin barras invertidas
    return {"systemctl": f"{f} systemctl", "sudo": f"{f} sudo", "nft": f"{f} nft"}


def con(extra: dict) -> dict:
    return {**PROPIOS, **extra}


def correr(tmp, procs, cfg, propio=900, alcance="completo", respaldo=None):
    o = ordenes(tmp, cfg)
    raiz = proc(tmp, procs)
    argv = ["--alcance", alcance, "--proc", str(raiz), "--propio-pid", str(propio), "--systemctl", o["systemctl"],
            "--sudo", o["sudo"], "--nft", o["nft"], "--json", str(tmp / "r.json")]
    if respaldo:
        argv += ["--respaldo", str(respaldo)]
    rc = es.main(argv)
    return rc, json.loads((tmp / "r.json").read_text(encoding="utf-8"))


# cadena de la propia comprobación: sshd -> bash -c "<comprobación con las dos palabras>" -> python3 -I - (900)
PROPIOS = {800: (1, ["sshd: adminsrvdmz@notty"]), 850: (800, ["bash", "-c", COMPROBACION + " --aplicar"]),
           870: (850, ["bash", "-c", COMPROBACION]), 900: (870, ["python3", "-I", "-"])}


def test_sombra_con_la_propia_comprobacion_presente(tmp_path):
    procs = con({300: (1, AG2)})
    rc, r = correr(tmp_path, procs, SANO)
    assert rc == 0 and r["estado"] == "sombra", r
    assert [a["pid"] for a in r["procesos"]["agentes"]] == [300]
    assert {850, 870, 900} <= set(r["procesos"]["excluidos_propios"])


def test_regresion_patron_antiguo_se_contaba_a_si_mismo():
    """Lo que hacía g01: pgrep -af agente_enforce | grep -c -- --aplicar sobre el bash -c de la comprobación."""
    lineas = [" ".join(argv) for _, argv in PROPIOS.values()] + [" ".join(AG2)]
    antiguo = sum(1 for l in lineas if "agente_enforce" in l and "--aplicar" in l)
    assert antiguo >= 1  # el patrón antiguo daba «aplicando» sin ningún agente aplicando
    assert es.es_agente(PROPIOS[850][1]) == (False, False)


def test_shell_ajeno_que_menciona_el_nombre_no_es_agente(tmp_path):
    procs = con({300: (1, AG2), 400: (1, ["bash", "-c", "grep agente_enforce --aplicar log"]),
                             401: (1, ["less", "/opt/cyberflow/agente-v2/agente_enforce_v2.py"])})
    rc, r = correr(tmp_path, procs, SANO)
    assert rc == 0 and len(r["procesos"]["agentes"]) == 1


def test_agente_real_con_aplicar_bajo_sh_c(tmp_path):
    hijo = ["/usr/bin/python3", "/home/adminsrvdmz/enforce/agente_enforce.py", "--aplicar", "--sudo"]
    procs = con({300: (1, AG2), 500: (1, ["/bin/sh", "-c", " ".join(hijo)]), 501: (500, hijo)})
    rc, r = correr(tmp_path, procs, SANO)
    assert rc == 1 and r["estado"] == "aplicando"
    assert [a["pid"] for a in r["procesos"]["agentes"] if a["aplicar"]] == [501]


def test_agente_v2_con_aplicar_igual(tmp_path):
    procs = con({300: (1, AG2 + ["--aplicar=si"])})
    assert correr(tmp_path, procs, SANO)[0] == 1


def test_proceso_ilegible_es_desconocido(tmp_path):
    procs = con({300: (1, AG2), 600: (1, "ilegible")})
    rc, r = correr(tmp_path, procs, SANO)
    assert rc == 2 and r["estado"] == "desconocido"


def test_sudo_falla_no_es_cero(tmp_path):
    rc, r = correr(tmp_path, con({300: (1, AG2)}), dict(SANO, sudo_falla=True))
    assert rc == 2 and any("nft" in x for x in r["lecturas_fallidas"]) and any("traza" in x for x in r["lecturas_fallidas"])


def test_nft_falla_no_es_cero(tmp_path):
    rc, r = correr(tmp_path, con({300: (1, AG2)}), dict(SANO, nft_rc=1))
    assert rc == 2 and r["estado"] == "desconocido"


def test_traza_ausente_no_es_cero(tmp_path):
    rc, r = correr(tmp_path, con({300: (1, AG2)}), dict(SANO, traza=None))
    assert rc == 2


def test_systemctl_falla_no_es_cero(tmp_path):
    rc, r = correr(tmp_path, con({300: (1, AG2)}), dict(SANO, systemctl_rc=1))
    assert rc == 2


def test_tabla_cyberflow_y_evento_aplicacion(tmp_path):
    cfg = dict(SANO, tablas=SANO["tablas"] + ["table inet cyberflow_dmz"])
    assert correr(tmp_path, con({300: (1, AG2)}), cfg)[0] == 1
    cfg = dict(SANO, traza=SANO["traza"] + '{"evento": "aplicacion", "ip": "10.10.20.30"}\n')
    t2 = tmp_path / "b"
    t2.mkdir()
    assert correr(t2, con({300: (1, AG2)}), cfg)[0] == 1


def test_unidad_v2_con_aplicar_en_execstart(tmp_path):
    u = dict(SANO["unidades"], **{"ppi-enforce-agent-v2-dmz.service": ["active", "enabled",
                                                                       EXEC_SOMBRA.replace("--seguir", "--seguir --aplicar")]})
    assert correr(tmp_path, con({300: (1, AG2)}), dict(SANO, unidades=u))[0] == 1


def test_v1_inactivo_con_aplicar_en_su_unidad_no_cuenta_mientras_esta_inactiva(tmp_path):
    # la unidad v1 SIEMPRE lleva --aplicar (ESTADO-OBSERVADO §3); lo que importa es que esté inactiva/deshabilitada
    rc, r = correr(tmp_path, con({300: (1, AG2)}), SANO)
    assert rc == 0


def test_no_conforme_si_v2_inactivo_o_v1_activo(tmp_path):
    u = dict(SANO["unidades"], **{"ppi-enforce-agent-v2-dmz.service": ["inactive", "enabled", EXEC_SOMBRA]})
    assert correr(tmp_path, con({}), dict(SANO, unidades=u))[0] == 3


def test_ruleset_contra_respaldo(tmp_path):
    resp = tmp_path / "resp"
    resp.mkdir()
    (resp / "ruleset.nft").write_text("table inet filter {\n counter packets 1 bytes 60\n}\n")
    assert correr(tmp_path, con({300: (1, AG2)}), SANO, respaldo=resp)[0] == 0  # solo contadores
    t2 = tmp_path / "b"
    t2.mkdir()
    cfg = dict(SANO, ruleset=SANO["ruleset"] + "table inet cf {\n}\n")
    assert correr(t2, con({300: (1, AG2)}), cfg, respaldo=resp)[0] == 1
    t3 = tmp_path / "c"
    t3.mkdir()
    assert correr(t3, con({300: (1, AG2)}), SANO, respaldo=tmp_path / "no-existe")[0] == 2


def test_alcance_procesos_sin_sudo(tmp_path):
    rc, r = correr(tmp_path, con({300: (1, AG2)}), dict(SANO, sudo_falla=True), alcance="procesos")
    assert rc == 0 and "nft" not in r
