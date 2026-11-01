#!/usr/bin/env python3
"""Ensayo aislado del perfil DNS (DC1) y del perfil DMZ con netns (Etapa 2).

SOLO en el banco Docker (``--network none``, NET_ADMIN y SYS_ADMIN dentro del
contenedor): crea su propia topologia de espacios de red y no toca ningun host
del laboratorio. Topologia (un puente ``br0`` en el netns ``red``):

  srv   10.10.10.99  servidor: DNS de prueba en UDP/TCP 53 y servicio TCP 389
  ata   10.10.20.30  origen senalado (ensayo)
  leg   10.10.20.40  cliente legitimo
  fwd   10.10.40.9   "reenviador" DNS al que srv consulta (trafico saliente)

Casos, cada uno con el helper restringido (cf_nft_helper.py) en el netns srv:
  C0 sin reglas: linea base de respuestas por segundo.
  C1 LIMIT dns sobre ata a 20 consultas/s: ata pasa ~tasa; leg intacto; 389 de ata intacto.
  C2 BLOCK dns sobre ata: ata 0 respuestas DNS; 389 de ata intacto; leg intacto.
  C3 srv consulta al reenviador con ata bloqueado: no afectado (hook input, dport 53).
  C4 caducidad nativa: tras el timeout, ata vuelve a resolver sin intervencion.
  C5 retirar_origen y desinstalar: tabla fuera, ruleset vacio de CyberFlow.
  C6 perfil dmz BLOCK sobre ata: cae el 389 de ata, leg intacto; LIMIT por origen
     (dos origenes limitados no comparten cubo).
  C7 agente_enforce_v2 completo: feed v2 firmado con destino dc1 -> aplica solo la
     entrada dc1; entrada srv-dmz de la misma ip queda como ajena.
Salida: JSON con cada caso y PASA/FALLA; codigo != 0 si algo falla.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
HELPER = [sys.executable, str(RAIZ / "scripts/enforce/cf_nft_helper.py")]
NS = {"srv": "10.10.10.99", "ata": "10.10.20.30", "leg": "10.10.20.40", "fwd": "10.10.40.9"}


def sh(*a, check=True, **k):
    return subprocess.run(list(a), check=check, capture_output=True, text=True, **k)


def nsx(ns, *a, **k):
    return sh("ip", "netns", "exec", ns, *a, **k)


def montar():
    for ns in list(NS) + ["red"]:
        sh("ip", "netns", "del", ns, check=False)
        sh("ip", "netns", "add", ns)
    nsx("red", "ip", "link", "add", "br0", "type", "bridge")
    nsx("red", "ip", "link", "set", "br0", "up")
    for ns, ip in NS.items():
        sh("ip", "link", "add", "v-" + ns, "type", "veth", "peer", "name", "p-" + ns)
        sh("ip", "link", "set", "v-" + ns, "netns", ns)
        sh("ip", "link", "set", "p-" + ns, "netns", "red")
        nsx("red", "ip", "link", "set", "p-" + ns, "master", "br0")
        nsx("red", "ip", "link", "set", "p-" + ns, "up")
        nsx(ns, "ip", "addr", "add", ip + "/8", "dev", "v-" + ns)
        nsx(ns, "ip", "link", "set", "v-" + ns, "up")
        nsx(ns, "ip", "link", "set", "lo", "up")


SERVIDOR = r'''
import socket, threading, struct, sys
ip = sys.argv[1]
def resp(q):
    return q[:2] + b"\x81\x80" + q[4:6] + b"\x00\x01\x00\x00\x00\x00" + q[12:] + b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04\x0a\x00\x00\x01"
def udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind((ip, 53))
    while True:
        q, a = s.recvfrom(512); s.sendto(resp(q), a)
def tcp(port, dns):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((ip, port)); s.listen(64)
    while True:
        c, _ = s.accept()
        try:
            if dns:
                n = struct.unpack("!H", c.recv(2))[0]; q = c.recv(n); r = resp(q); c.sendall(struct.pack("!H", len(r)) + r)
            else:
                c.sendall(b"ok\n")
        except Exception: pass
        c.close()
threading.Thread(target=udp, daemon=True).start()
threading.Thread(target=tcp, args=(53, True), daemon=True).start()
if len(sys.argv) > 2: threading.Thread(target=tcp, args=(389, False), daemon=True).start()
threading.Event().wait()
'''

CLIENTE = r'''
import socket, sys, time, json, random, struct
srv, tasa, dur, modo = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
ok = env = 0
fin = time.time() + dur
while time.time() < fin:
    t = time.time(); env += 1
    try:
        if modo == "udp":
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.3)
            q = struct.pack("!H", random.randint(0, 65535)) + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x01a\x00\x00\x01\x00\x01"
            s.sendto(q, (srv, 53)); s.recvfrom(512); ok += 1; s.close()
        else:
            c = socket.create_connection((srv, 389), timeout=0.5); c.recv(8); c.close(); ok += 1
    except OSError:
        pass
    time.sleep(max(0, 1 / tasa - (time.time() - t)))
print(json.dumps({"enviadas": env, "respondidas": ok, "dur": dur}))
'''


def cliente(ns, destino, tasa, dur, modo="udp"):
    r = nsx(ns, sys.executable, "-c", CLIENTE, destino, str(tasa), str(dur), modo)
    return json.loads(r.stdout)


def helper(ns, perfil, ops):
    r = nsx(ns, *HELPER, input=json.dumps({"perfil": perfil, "operaciones": ops}), check=False)
    return json.loads(r.stdout)


def main() -> int:
    if os.geteuid() != 0:
        print("solo en el banco Docker como root"); return 2
    montar()
    procs = [subprocess.Popen(["ip", "netns", "exec", "srv", sys.executable, "-c", SERVIDOR, NS["srv"], "389"]),
             subprocess.Popen(["ip", "netns", "exec", "fwd", sys.executable, "-c", SERVIDOR, NS["fwd"]])]
    time.sleep(1.0)
    res = {}
    S = NS["srv"]
    try:
        c0 = {"ata": cliente("ata", S, 20, 4), "leg": cliente("leg", S, 20, 4)}
        res["C0_linea_base"] = {"datos": c0, "pasa": c0["ata"]["respondidas"] >= 70 and c0["leg"]["respondidas"] >= 70}

        helper("srv", "dns", [{"op": "asegurar"}, {"op": "anadir", "set": "limitados", "ip": NS["ata"], "timeout": 60}])
        out = {}
        hilos = [threading.Thread(target=lambda k=k, ns=ns: out.__setitem__(k, cliente(ns, S, 20, 6)))
                 for k, ns in (("ata", "ata"), ("leg", "leg"))]
        [h.start() for h in hilos]; [h.join() for h in hilos]
        out["ata_389"] = cliente("ata", S, 10, 3, "tcp")
        est = helper("srv", "dns", [{"op": "listar"}])["estado"]
        tasa_ata = out["ata"]["respondidas"] / 6
        res["C1_limit_dns"] = {"datos": out, "contadores": est, "respuestas_por_s_ata": round(tasa_ata, 2),
                               "pasa": 4 <= tasa_ata <= 9 and out["leg"]["respondidas"] >= 105
                               and out["ata_389"]["respondidas"] >= 28
                               and est["sets"]["limitados"][NS["ata"]]["paquetes"] > 0}

        helper("srv", "dns", [{"op": "quitar", "set": "limitados", "ip": NS["ata"]},
                              {"op": "anadir", "set": "bloqueados", "ip": NS["ata"], "timeout": 6}])
        t_apl = time.time()
        out = {"ata": cliente("ata", S, 10, 2), "leg": cliente("leg", S, 10, 2),
               "ata_389": cliente("ata", S, 10, 2, "tcp")}
        res["C2_block_dns"] = {"datos": out, "pasa": out["ata"]["respondidas"] == 0
                               and out["leg"]["respondidas"] >= 19 and out["ata_389"]["respondidas"] >= 19}

        out = cliente("srv", NS["fwd"], 10, 1)
        res["C3_saliente_reenviador"] = {"datos": out, "pasa": out["respondidas"] >= 9}

        espera = max(0, t_apl + 6.5 - time.time()); time.sleep(espera)
        out = cliente("ata", S, 10, 1)
        res["C4_caducidad_nativa"] = {"datos": out, "pasa": out["respondidas"] >= 9}

        helper("srv", "dns", [{"op": "anadir", "set": "bloqueados", "ip": NS["ata"], "timeout": 600}])
        r1 = helper("srv", "dns", [{"op": "retirar_origen", "ip": NS["ata"]}])
        out = cliente("ata", S, 10, 1)
        r2 = helper("srv", "dns", [{"op": "desinstalar"}])
        tablas = nsx("srv", "nft", "list", "tables").stdout
        res["C5_retirada_y_reversion"] = {"datos": out, "retirar": r1, "desinstalar": r2, "tablas": tablas,
                                         "pasa": out["respondidas"] >= 9 and "cyberflow" not in tablas}

        helper("srv", "dmz", [{"op": "asegurar"}, {"op": "anadir", "set": "bloqueados", "ip": NS["ata"], "timeout": 60}])
        out = {"ata_389": cliente("ata", S, 10, 2, "tcp"), "leg_389": cliente("leg", S, 10, 2, "tcp")}
        helper("srv", "dmz", [{"op": "retirar_origen", "ip": NS["ata"]},
                              {"op": "anadir", "set": "limitados", "ip": NS["ata"], "timeout": 60},
                              {"op": "anadir", "set": "limitados", "ip": NS["leg"], "timeout": 60}])
        lim = {}
        hilos = [threading.Thread(target=lambda ns=ns: lim.__setitem__(ns, cliente(ns, S, 150, 4)))
                 for ns in ("ata", "leg")]
        [h.start() for h in hilos]; [h.join() for h in hilos]
        helper("srv", "dmz", [{"op": "desinstalar"}])
        # Cubo por origen: cada uno conserva ~su cupo (100/s + rafaga), no la mitad.
        res["C6_dmz_block_y_limit_por_origen"] = {
            "datos": out, "limit": lim,
            "pasa": out["ata_389"]["respondidas"] == 0 and out["leg_389"]["respondidas"] >= 19
            and min(lim["ata"]["respondidas"], lim["leg"]["respondidas"]) >= 0.6 * min(
                lim["ata"]["enviadas"], lim["leg"]["enviadas"])}

        res["C7_agente_v2"] = ensayo_agente()
    finally:
        for p in procs:
            p.kill()
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if all(v.get("pasa") for v in res.values()) else 1


def ensayo_agente() -> dict:
    sys.path.insert(0, str(RAIZ / "scripts/engine"))
    import feed
    d = Path(tempfile.mkdtemp())
    feed.generar_claves(str(d / "p.pem"), str(d / "pub.pem"))
    ahora = time.time()
    ents = []
    for dest, alc, acc in (("dc1", "dns", "BLOCK"), ("srv-dmz", "todo", "BLOCK")):
        e = {"ip": NS["ata"], "destino": dest, "alcance": alc, "accion": acc, "hasta": round(ahora + 30),
             "evento_id": "ensayo|" + dest}
        e["id"] = feed.id_entrada(e["ip"], dest, alc, acc, e["evento_id"])
        ents.append(e)
    datos = feed.serializar(feed.construir_v2(ents, 1, ahora, 60))
    (d / "feed.json").write_bytes(datos)
    (d / "feed.sig").write_bytes(feed.firmar(datos, str(d / "p.pem")))
    r = nsx("srv", sys.executable, str(RAIZ / "scripts/enforce/agente_enforce_v2.py"), "--perfil", "dns",
            "--feed", str(d / "feed.json"), "--firma", str(d / "feed.sig"), "--clave-publica", str(d / "pub.pem"),
            "--estado", str(d / "st.json"), "--traza", str(d / "traza.jsonl"),
            "--helper", " ".join(HELPER), "--aplicar", check=False)
    salida = json.loads(r.stdout)
    out = {"dns": cliente("ata", NS["srv"], 10, 1), "389": cliente("ata", NS["srv"], 10, 1, "tcp")}
    traza = [json.loads(x)["evento"] for x in (d / "traza.jsonl").read_text().splitlines()]
    helper("srv", "dns", [{"op": "desinstalar"}])
    return {"salida": salida, "trafico": out, "traza": traza,
            "pasa": salida.get("ajenas") == 1 and out["dns"]["respondidas"] == 0
            and out["389"]["respondidas"] >= 9 and traza[:3] == ["recepcion", "aplicacion", "confirmacion"]}


if __name__ == "__main__":
    sys.exit(main())
