#!/usr/bin/env python3
"""Ensayo del LIMIT DNS candidato en el banco (Etapa 3). SOLO banco Docker como root.

  docker run --rm --privileged --network none -v <repo>:/src:ro -v <seg-dns>:/seg:ro -v <out>:/out \\
    cyberflow-etapa3-banco:1 bash -c 'cp -a /src /w && cd /w && python3 deploy/pruebas-aisladas/ensayo_limit_dns.py /seg /out'

Para cada segmento ``dns_inusual-r*.pcap`` (scripts/etapa3/segmento_dns_dc1.py: solo
consultas UDP/53 hacia DC1, sin VLAN y sin copias del espejo, del inicio − 60 s al
fin + 60 s):

1. veth vA -> vB; vB tiene la IP de DC1 (10.10.10.20). El kernel no contesta (descarte
   en output), igual que en el ensayo de la vía rápida.
2. El helper REAL (cf_nft_helper vía helper_banco.py, perfil ``dns``) crea la tabla
   ``inet cyberflow_dns`` y añade al set ``limitados`` a TODOS los orígenes del segmento
   que el helper admite (los de NUNCA, como DC1/DC2, los rechaza): el atacante y los
   legítimos, como si todos hubieran sido limitados por error desde el principio.
3. tcpreplay a velocidad original.
4. Lee por origen el contador del elemento en ``limitados`` (paquetes que coinciden con
   la regla, solo UDP/53) y el de ``descartes_limite`` (paquetes descartados por la tasa).

Compara con la simulación de cubeta (politica_limit_dns.py): misma tasa y ráfaga. Un
replay no reintenta: lo que haría la herramienta del atacante ante el descarte NO se
mide aquí (campaña B).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable
DC1 = "10.10.10.20"
ATK = "10.10.20.30"
sys.path.insert(0, str(RAIZ / "scripts" / "enforce"))
import cf_nft_helper  # noqa: E402


def sh(*a, **kw):
    return subprocess.run(list(a), capture_output=True, text=True, **kw)


def red() -> str:
    sh("ip", "link", "del", "vA")
    sh("ip", "link", "add", "vA", "type", "veth", "peer", "name", "vB")
    for i in ("vA", "vB"):
        sh("ip", "link", "set", i, "up")
    sh("ip", "addr", "add", DC1 + "/16", "dev", "vB")
    for k in ("all", "default", "vB", "vA"):
        sh("sysctl", "-w", "net.ipv4.conf.%s.rp_filter=0" % k)
    sh("sysctl", "-w", "net.ipv4.conf.vB.accept_local=1")
    sh("nft", "-f", "-", input="destroy table inet banco\nadd table inet banco\n"
       "add chain inet banco salida { type filter hook output priority 0; policy accept; }\n"
       "add rule inet banco salida oifname \"vB\" drop\n")
    return Path("/sys/class/net/vB/address").read_text().strip()


def helper(pd: Path, peticion: dict) -> dict:
    r = sh(PY, str(RAIZ / "deploy/pruebas-aisladas/helper_banco.py"), str(pd / "perfil"),
           input=json.dumps(peticion))
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"ok": False, "salida": r.stdout[-400:], "error": r.stderr[-400:]}


def contadores(conjunto: str) -> dict:
    r = sh("nft", "-j", "list", "set", "inet", "cyberflow_dns", conjunto)
    out = {}
    if r.returncode != 0:
        return out
    for x in json.loads(r.stdout).get("nftables", []):
        for e in (x.get("set") or {}).get("elem") or []:
            if isinstance(e, dict) and "elem" in e:
                v = e["elem"]
                out[str(v.get("val"))] = (v.get("counter") or {}).get("packets", 0)
    return out


def una(seg: Path, mac: str, salida: Path) -> dict:
    meta = json.loads(Path(str(seg) + ".json").read_text())
    d = Path(tempfile.mkdtemp(prefix="ld-"))
    os.chmod(d, 0o755)
    pd = d / "etc-dns"
    pd.mkdir(mode=0o755)
    (pd / "perfil").write_text("dns\n")
    os.chmod(pd / "perfil", 0o644)
    sh("nft", "destroy", "table", "inet", "cyberflow_dns")
    ops = [{"op": "asegurar"}]
    rechazados = {}
    for i, ip in enumerate(sorted(meta["por_origen"])):
        try:
            cf_nft_helper._ip(ip)
        except cf_nft_helper.Rechazo as e:
            rechazados[ip] = str(e)
            continue
        ops.append({"op": "anadir", "set": "limitados", "ip": ip, "timeout": 900, "id": "%016x" % (i + 1)})
    res = helper(pd, {"perfil": "dns", "operaciones": ops})
    t0 = time.time()
    rep = sh("tcpreplay-edit", "--enet-dmac=%s" % mac, "-i", "vA", str(seg))
    time.sleep(1)
    coin, desc = contadores("limitados"), contadores("descartes_limite")
    regla = sh("nft", "list", "chain", "inet", "cyberflow_dns", "entrada").stdout
    por = {}
    for ip, n in sorted(meta["por_origen"].items()):
        c, x = coin.get(ip), desc.get(ip, 0)
        por[ip] = {"enviadas": n, "coinciden": c, "descartadas": x,
                   "fraccion_descartada": round(x / n, 3) if n else None,
                   "limitado": ip not in rechazados, "rechazo_helper": rechazados.get(ip)}
    leg = {ip: v for ip, v in por.items() if ip != ATK and v["limitado"]}
    fila = {"segmento": seg.stem, "helper_ok": res.get("ok"), "helper": res if not res.get("ok") else None,
            "duracion_replay_s": round(time.time() - t0, 1), "tcpreplay_rc": rep.returncode,
            "tcpreplay": rep.stdout.strip().splitlines()[-6:],
            "tasa": cf_nft_helper.TASA["dns"], "rafaga": cf_nft_helper.RAFAGA["dns"],
            "regla_nft": [l.strip() for l in regla.splitlines() if "limit" in l],
            "atacante": por.get(ATK),
            "legitimos_limitados": len(leg),
            "legitimos_descartadas": sum(v["descartadas"] for v in leg.values()),
            "legitimos_enviadas": sum(v["enviadas"] for v in leg.values()),
            "por_origen": por}
    with salida.open("a") as fh:
        fh.write(json.dumps(fila, sort_keys=True) + "\n")
    sh("nft", "destroy", "table", "inet", "cyberflow_dns")
    return fila


def main() -> int:
    if os.geteuid() != 0:
        print("solo en el banco Docker como root")
        return 2
    seg_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    mac = red()
    salida = out / "ensayo-limit-dns.jsonl"
    tot = {"atk_env": 0, "atk_desc": 0, "leg_env": 0, "leg_desc": 0}
    for seg in sorted(seg_dir.glob("dns_inusual-r*.pcap")):
        f = una(seg, mac, salida)
        a = f["atacante"] or {}
        tot["atk_env"] += a.get("enviadas") or 0
        tot["atk_desc"] += a.get("descartadas") or 0
        tot["leg_env"] += f["legitimos_enviadas"]
        tot["leg_desc"] += f["legitimos_descartadas"]
        print(json.dumps({k: f[k] for k in ("segmento", "helper_ok", "atacante", "legitimos_limitados",
                                             "legitimos_enviadas", "legitimos_descartadas", "regla_nft")}), flush=True)
    tot["atk_fraccion"] = round(tot["atk_desc"] / tot["atk_env"], 3) if tot["atk_env"] else None
    (out / "resumen-limit-dns.json").write_text(json.dumps(tot, indent=1))
    print(json.dumps(tot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
