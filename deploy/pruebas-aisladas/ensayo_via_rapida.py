#!/usr/bin/env python3
"""Ensayo de la vía rápida de escaneo en tiempo real (Etapa 3). SOLO banco Docker como root.

  docker run --rm --privileged --network none -v <repo>:/src:ro -v <seg>:/seg:ro -v <out>:/out \\
    cyberflow-etapa3-banco:1 bash -c 'cp -a /src /w && cd /w && python3 deploy/pruebas-aisladas/ensayo_via_rapida.py /seg /out'

Para cada escaneo breve (segmento del archivo del 3B: todo el tráfico, 12 s antes de la
ráfaga hasta 4 s después del fin), cada alternativa y cada condición de carga:

1. tcpreplay-edit reproduce el segmento a velocidad original por la veth vA -> vB. La MAC
   de destino se reescribe a la de vB y vB tiene 10.10.30.10: lo dirigido a srv-dmz llega
   a la pila del contenedor y pasa por el hook input de nftables (donde el agente bloquea).
   Las respuestas del kernel (RST) se descartan en output para no alterar el escenario
   (srv-dmz real no responde a puertos cerrados).
2. Alternativas (todas alimentan el MISMO publicador -> relé -> agente dmz -> helper -> nft):
   A1 capturas de 1 s (tcpdump -G 1) + detector_rapido --ficheros
   A2 capturas de 2 s (tcpdump -G 2) + detector_rapido --ficheros
   C  lectura continua (tcpdump -U -w -) + detector_rapido --flujo
   B  Suricata en vivo (af-packet) con cf-escaneo-temprano.rules + suricata_a_senal
3. Carga: sin carga, o con la inundación HTTP r3 reproducida en bucle por la misma veth y
   4 procesos de CPU al 100 %.
4. Fase: en A1/A2 se espera U(0, R) entre arrancar tcpdump y reproducir.

Mide en reloj de pared del banco (todas las marcas, incluidas las de los paquetes
capturados, son del mismo reloj): inicio de ráfaga y último SYN (captura completa),
t_evidencia, disponible_en, emitido_en, leido_en, publicado_en, entregado_en,
recibido_en, aplicado_en, confirmado_en y el primer paquete DESCARTADO por la regla
(contador del elemento en el set ``bloqueados``, sondeado cada ~20 ms). Y cuántos SYN
del escaneo llegaron antes y después de la aplicación.

Un replay abierto NO reacciona al bloqueo: los descartes medidos son de paquetes grabados;
no prueban que el atacante real se detenga (eso es de la campaña B).
"""
from __future__ import annotations

import json
import os
import random
import shutil
import signal
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PY = sys.executable
ATK, SRV = "10.10.20.30", "10.10.30.10"
REGLAS = RAIZ / "deploy/etapa3/suricata/cf-escaneo-temprano.rules"


def sh(*a, **kw):
    return subprocess.run(list(a), capture_output=True, text=True, **kw)


def red() -> str:
    sh("ip", "link", "del", "vA")
    sh("ip", "link", "add", "vA", "type", "veth", "peer", "name", "vB")
    for i in ("vA", "vB"):
        sh("ip", "link", "set", i, "up")
    sh("ip", "addr", "add", SRV + "/16", "dev", "vB")
    for k in ("all", "default", "vB", "vA"):
        sh("sysctl", "-w", "net.ipv4.conf.%s.rp_filter=0" % k)
    sh("sysctl", "-w", "net.ipv4.conf.vB.accept_local=1")
    # el kernel del banco no debe contestar (srv-dmz real descarta en silencio)
    sh("nft", "-f", "-", input="destroy table inet banco\nadd table inet banco\n"
       "add chain inet banco salida { type filter hook output priority 0; policy accept; }\n"
       "add rule inet banco salida oifname \"vB\" drop\n")
    return Path("/sys/class/net/vB/address").read_text().strip()


def leer(p: Path):
    if not p.exists():
        return []
    out = []
    for l in p.read_text(errors="replace").splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def pcap_iter(p: Path):
    with p.open("rb") as fh:
        cab = fh.read(24)
        if len(cab) < 24:
            return
        e = "<" if cab[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        div = 1e9 if cab[:4] in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d") else 1e6
        while True:
            h = fh.read(16)
            if len(h) < 16:
                return
            s, us, incl, _ = struct.unpack(e + "IIII", h)
            fr = fh.read(incl)
            if len(fr) < incl:
                return
            yield s + us / div, fr


def linea_temporal(p: Path) -> dict:
    """Ráfaga y último SYN del atacante hacia srv-dmz en la captura completa (reloj del banco)."""
    sys.path.insert(0, str(RAIZ / "scripts/engine"))
    from detector_rapido import tcp_de_trama
    syn = []
    for t, fr in pcap_iter(p):
        x = tcp_de_trama(fr)
        if x and x[0] == ATK and x[1] == SRV and x[4] & 0x02 and not x[4] & 0x10:
            syn.append((t, x[3]))
    syn.sort()
    puertos, orden = set(), []
    for t, pu in syn:
        if pu not in puertos:
            puertos.add(pu)
            orden.append(t)
    import bisect
    r0 = None
    for i, t in enumerate(orden):
        if bisect.bisect_right(orden, t + 1.0) - i >= 10:
            r0 = t
            break
    return {"syn": syn, "inicio_rafaga": r0, "ultimo_syn": syn[-1][0] if syn else None,
            "puertos": len(puertos)}


def cadena(d: Path):
    sys.path.insert(0, str(RAIZ / "scripts/engine"))
    import feed
    for x in ("sensor", "dmz"):
        (d / x).mkdir(parents=True, exist_ok=True)
    feed.generar_claves(str(d / "priv.pem"), str(d / "pub.pem"))
    (d / "motor_decision.log").write_text("")
    (d / "rapidas.jsonl").write_text("")
    pd = d / "etc-dmz"
    pd.mkdir(mode=0o755, exist_ok=True)
    os.chmod(d, 0o755)
    (pd / "perfil").write_text("dmz\n")
    os.chmod(pd / "perfil", 0o644)
    sh("nft", "destroy", "table", "inet", "cyberflow_dmz")
    pub = subprocess.Popen([PY, str(RAIZ / "scripts/engine/publicar_feed_v2.py"), "--log", str(d / "motor_decision.log"),
                            "--senales-rapidas", str(d / "rapidas.jsonl"),
                            "--estado", str(d / "sensor/estado.json"), "--clave-privada", str(d / "priv.pem"),
                            "--salida-feed", str(d / "sensor/feed.json"), "--salida-firma", str(d / "sensor/feed.sig"),
                            "--traza", str(d / "sensor/traza.jsonl"), "--seguir", "--sondeo-segundos", "0.25",
                            "--refresco-segundos", "20"])
    rele = subprocess.Popen([PY, str(RAIZ / "deploy/enforcement/relay_eventos.py"), "--transporte", "local",
                             "--origen", str(d / "sensor"), "--destino", "srv-dmz=%s" % (d / "dmz"),
                             "--traza", str(d / "rele.jsonl"), "--clave-publica", str(d / "pub.pem"),
                             "--sondeo-segundos", "1"])
    shutil.copy(d / "pub.pem", d / "dmz" / "pub.pem")
    helper = "%s %s %s" % (PY, RAIZ / "deploy/pruebas-aisladas/helper_banco.py", pd / "perfil")
    ag = subprocess.Popen([PY, str(RAIZ / "scripts/enforce/agente_enforce_v2.py"), "--perfil", "dmz",
                           "--feed", str(d / "dmz/feed.json"), "--firma", str(d / "dmz/feed.sig"),
                           "--clave-publica", str(d / "dmz/pub.pem"), "--estado", str(d / "dmz/estado.json"),
                           "--traza", str(d / "dmz/traza.jsonl"), "--helper", helper, "--aplicar",
                           "--seguir", "--sondeo-segundos", "0.5", "--observar-segundos", "5"])
    return [pub, rele, ag]


def sondeo_descartes(salida: Path, dur: float):
    """Proceso aparte: primer instante en que el elemento del atacante tiene paquetes descartados."""
    codigo = r'''
import json, subprocess, sys, time
fin = time.time() + %f
prim = {}
while time.time() < fin:
    r = subprocess.run(["nft", "-j", "list", "set", "inet", "cyberflow_dmz", "bloqueados"], capture_output=True, text=True)
    t = time.time()
    if r.returncode == 0:
        for x in json.loads(r.stdout).get("nftables", []):
            for e in (x.get("set") or {}).get("elem", []) or []:
                el = e.get("elem", e) if isinstance(e, dict) else {}
                ip = el.get("val") if isinstance(el, dict) else None
                c = (el.get("counter") or {}) if isinstance(el, dict) else {}
                if ip and ip not in prim and c.get("packets", 0) > 0:
                    prim[ip] = {"primer_descarte_visto": t, "paquetes": c.get("packets")}
                if ip and ip in prim:
                    prim[ip]["paquetes_ultimo_sondeo"] = c.get("packets", 0)
                if ip and "presente_" + ip not in prim:
                    prim["presente_" + ip] = t
    time.sleep(0.02)
open(%r, "w").write(json.dumps(prim))
''' % (dur, str(salida))
    return subprocess.Popen([PY, "-c", codigo])


def suricata(d: Path) -> subprocess.Popen:
    (d / "suri").mkdir(exist_ok=True)
    p = subprocess.Popen(["suricata", "--af-packet=vB", "-S", str(REGLAS), "-l", str(d / "suri"), "-k", "none",
                          "--set", "vars.address-groups.HOME_NET=[10.10.0.0/16]",
                          "--set", "outputs.1.eve-log.types=[alert]" ],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 60:
        log = d / "suri" / "suricata.log"
        if log.exists() and "engine started" in log.read_text(errors="replace"):
            break
        time.sleep(0.2)
    return p


def una(seg: Path, alt: str, carga: bool, mac: str, salida: Path, rep: int) -> dict:
    d = Path(tempfile.mkdtemp(prefix="vr-"))
    procs = cadena(d)
    extra = []
    cap = d / "cap"
    cap.mkdir()
    todo = subprocess.Popen(["tcpdump", "-Z", "root", "-i", "vB", "-Q", "in", "-n", "-s", "128", "--immediate-mode",
                             "-w", str(d / "todo.pcap")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    extra.append(todo)
    R = {"A1": 1, "A2": 2}.get(alt)
    if R:
        extra.append(subprocess.Popen(["tcpdump", "-Z", "root", "-i", "vB", "-Q", "in", "-n", "-U", "--immediate-mode", "-G", str(R),
                                       "-w", str(cap / "r-%Y%m%d%H%M%S.pcap")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        extra.append(subprocess.Popen([PY, str(RAIZ / "scripts/engine/detector_rapido.py"), "--ficheros", str(cap),
                                       "--patron", "r-*.pcap", "--salida", str(d / "rapidas.jsonl"),
                                       "--resumen", str(d / "det-resumen.jsonl"), "--sondeo", "0.02"]))
    elif alt == "C":
        tcpd = subprocess.Popen(["tcpdump", "-Z", "root", "-i", "vB", "-Q", "in", "-n", "-U", "--immediate-mode", "-w", "-", "tcp"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        extra.append(tcpd)
        extra.append(subprocess.Popen([PY, str(RAIZ / "scripts/engine/detector_rapido.py"), "--flujo",
                                       "--salida", str(d / "rapidas.jsonl"), "--resumen", str(d / "det-resumen.jsonl"),
                                       "--tic", "0.02"], stdin=tcpd.stdout))
    elif alt == "B":
        extra.append(suricata(d))
        extra.append(subprocess.Popen([PY, str(RAIZ / "scripts/engine/suricata_a_senal.py"), "--eve",
                                       str(d / "suri" / "eve.json"), "--salida", str(d / "rapidas.jsonl")]))
    if carga:
        extra.append(subprocess.Popen(["tcpreplay-edit", "--enet-vlan=del", "--enet-dmac=%s" % mac, "-i", "vA", "--loop=0",
                                       "--srcipmap=10.10.20.30/32:10.10.20.99/32",
                                       "--dstipmap=10.10.20.30/32:10.10.20.99/32", "--fixcsum",
                                       str(seg.parent / "carga-inundacion_http-r3.pcap")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(4):
            extra.append(subprocess.Popen([PY, "-c", "while True: pass"]))
    sond = sondeo_descartes(d / "descartes.json", 40)
    time.sleep(2.5 + (random.uniform(0, R) if R else 0.0))
    t_rep = time.time()
    sh("tcpreplay-edit", "--enet-vlan=del", "--enet-dmac=%s" % mac, "-i", "vA", str(seg))
    time.sleep(4)
    nft_final = sh("nft", "-j", "list", "set", "inet", "cyberflow_dmz", "bloqueados").stdout
    for p in extra + procs:
        try:
            p.send_signal(signal.SIGINT if p.args[0] in ("tcpdump", "suricata") else signal.SIGTERM)
        except Exception:
            pass
    for p in extra + procs:
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()
    sond.wait(timeout=60)
    lt = linea_temporal(d / "todo.pcap")
    senales = [s for s in leer(d / "rapidas.jsonl") if s.get("origen") == ATK and s.get("destino") == SRV]
    s0 = senales[0] if senales else None
    tp = leer(d / "sensor/traza.jsonl")
    nuevo = next((n for p in tp for n in p.get("nuevos", []) if s0 and (n.get("senal_rapida") or {}).get("id") == s0["id"]), None)
    pubreg = next((p for p in tp if nuevo and any(x.get("evento_id") == nuevo["evento_id"] for x in p.get("nuevos", []))), None)
    tr = leer(d / "rele.jsonl")
    rel = next((r for r in tr if pubreg and r.get("secuencia") is not None and r["secuencia"] >= pubreg["secuencia"]
                and "entregado_en" in r["destinos"].get("srv-dmz", {})), None)
    ta = leer(d / "dmz/traza.jsonl")
    idn = nuevo.get("id") if nuevo else None
    rec = next((x for x in ta if x.get("evento") == "recepcion" and idn in x.get("ids", [])), None)
    apl = next((x for x in ta if x.get("evento") == "aplicacion" and any(m.get("id") == idn for m in x.get("nuevos", []))), None)
    conf = next((x for x in ta if x.get("evento") == "confirmacion" and idn in x.get("confirmadas", [])), None)
    desc = json.loads((d / "descartes.json").read_text()) if (d / "descartes.json").exists() else {}
    r0, ult = lt["inicio_rafaga"], lt["ultimo_syn"]

    def rel_(x):
        return None if x is None or r0 is None else round(x - r0, 3)
    t_apl = apl.get("aplicado_en") if apl else None
    t_drop = (desc.get(ATK) or {}).get("primer_descarte_visto")
    fila = {
        "alternativa": alt, "carga": carga, "repeticion": rep, "segmento": seg.stem,
        "rafaga_s": round(ult - r0, 3) if r0 and ult else None, "puertos_capturados": lt["puertos"],
        "s_desde_rafaga": {
            "evidencia": rel_(s0.get("t_evidencia") if s0 else None),
            "disponible": rel_(s0.get("disponible_en") if s0 else None),
            "emitida": rel_(s0.get("emitido_en") if s0 else None),
            "leida_publicador": rel_(nuevo.get("leido_en") if nuevo else None),
            "publicada": rel_(pubreg.get("publicado_en") if pubreg else None),
            "entregada": rel_(rel["destinos"]["srv-dmz"]["entregado_en"] if rel else None),
            "recibida_agente": rel_(rec.get("recibido_en") if rec else None),
            "aplicada": rel_(t_apl),
            "confirmada": rel_(conf.get("confirmado_en") if conf else None),
            "primer_descarte_visto": rel_(t_drop),
            "ultimo_syn": rel_(ult)},
        "margen_s_aplicada_a_ultimo_syn": round(ult - t_apl, 3) if ult and t_apl else None,
        "syn_escaneo_total": len(lt["syn"]),
        "syn_tras_aplicacion": sum(1 for t, _ in lt["syn"] if t_apl and t > t_apl),
        # contador del elemento del atacante en el primer sondeo con descartes, y en el último sondeo
        "paquetes_descartados_contador": (desc.get(ATK) or {}).get("paquetes"),
        "paquetes_descartados_final": (desc.get(ATK) or {}).get("paquetes_ultimo_sondeo"),
        "senales": len(senales), "tipo_publicacion": nuevo.get("tipo") if nuevo else None,
        "det_resumen_cpu_max_s": max((x.get("cpu_s", 0) for x in leer(d / "det-resumen.jsonl")), default=None),
        "t_inicio_replay": t_rep,
        "nft_final": nft_final[-800:] if os.environ.get("DEPURAR") else None,
    }
    with salida.open("a") as fh:
        fh.write(json.dumps(fila, sort_keys=True) + "\n")
    shutil.rmtree(d, ignore_errors=True)
    return fila


def main() -> int:
    if os.geteuid() != 0:
        print("solo en el banco Docker como root")
        return 2
    seg_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    alts = (sys.argv[3].split(",") if len(sys.argv) > 3 else ["A1", "A2", "C", "B"])
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    random.seed(20261102)
    mac = red()
    salida = out / "ensayo-via-rapida.jsonl"
    segs = sorted(seg_dir.glob("escaneo_breve-r*.pcap"))
    for rep in range(reps):
        for carga in (False, True):
            for alt in alts:
                for seg in segs:
                    f = una(seg, alt, carga, mac, salida, rep)
                    print(json.dumps({k: f[k] for k in ("alternativa", "carga", "segmento", "s_desde_rafaga",
                                                         "margen_s_aplicada_a_ultimo_syn", "syn_tras_aplicacion",
                                                         "syn_escaneo_total")}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
