#!/bin/bash
# El servidor objetivo visto desde dentro: agente de CyberFlow, feed recibido y firewall.
# SOLO LECTURA (cf-nft-mostrar solo lista la tabla). Uso: ~/cf-demo/mira-agente.sh [IP]
IP=${1:-10.10.20.30}
export TZ=America/Lima
while true; do
  sudo -n /usr/local/sbin/cf-nft-mostrar >/tmp/.cf-nft.json 2>/dev/null || echo '{}' >/tmp/.cf-nft.json
  salida=$(
    printf '\033[1;33msrv-dmz 10.10.30.10 · servidor objetivo\033[0m   %s   (refresca cada 2 s)\n' "$(date +%T)"
    printf 'IP vigilada: \033[1m%s\033[0m\n\n' "$IP"
    est=$(systemctl is-active ppi-enforce-agent.timer)
    if [ "$est" = active ]; then printf 'agente CyberFlow : \033[1;32mACTIVO\033[0m · recoge el feed cada 10 s, verifica la firma y aplica\n'
    else printf 'agente CyberFlow : \033[1;33mEN SOMBRA\033[0m (%s: recibe el feed pero no aplica)\n' "$est"; fi
    python3 - "$IP" <<'EOF'
import json, os, subprocess, sys, time
ip = sys.argv[1]; H = os.path.expanduser("~/enforce/")
R, AM, V, B, N = "\033[1;41m", "\033[1;43;30m", "\033[1;32m", "\033[1m", "\033[0m"
try:
    f = json.load(open(H + "feed.json")); edad = int(time.time() - os.path.getmtime(H + "feed.json"))
    print("feed firmado     : recibido hace %d s" % edad)
    e = [x for x in f.get("entradas", []) if x.get("ip") == ip]
    if e:
        x = e[0]
        print("orden del sensor : %s%s%s · %s · caduca %s%s" % (B, x["accion"], N, x.get("motivo", "")[:60],
              time.strftime("%H:%M:%S", time.localtime(x["hasta"])),
              " · reincidencia nivel %d" % x["nivel"] if x.get("nivel") else ""))
    else:
        print("orden del sensor : ninguna para esta IP")
except (OSError, ValueError):
    print("feed firmado     : no recibido")
try:
    lib = json.load(open(H + "liberadas.json"))
except (OSError, ValueError):
    lib = {}
if ip in lib:
    print("liberación humana: %sSÍ%s, desde %s (no se reaplica salvo reincidencia)" % (
        V, N, time.strftime("%H:%M:%S", time.localtime(lib[ip].get("desde", 0)))))
try:
    doc = json.load(open("/tmp/.cf-nft.json")).get("nftables", [])
except ValueError:
    doc = []
sets = {x["set"]["name"]: x["set"].get("elem", []) for x in doc if "set" in x}
print()
if not sets:
    print("FIREWALL nftables: sin tabla cyberflow (nada aplicado)")
else:
    hit = None
    for nombre, etiqueta, col in (("cyberflow_bloqueados", "BLOQUEADA (drop total)", R),
                                  ("cyberflow_limitados", "LIMITADA (máx. 100 paquetes/s)", AM)):
        for el in sets.get(nombre, []):
            v = el.get("elem", el) if isinstance(el, dict) else {"val": el}
            if v.get("val") == ip:
                hit = (etiqueta, col, v.get("expires"))
    if hit:
        print("FIREWALL nftables: %s %s %s%s" % (hit[1], ip, hit[0], N) +
              ("  · se quita sola en %d s" % hit[2] if hit[2] is not None else ""))
    else:
        print("FIREWALL nftables: tabla cyberflow activa · %s%s sin regla%s (pasa libre)" % (V, ip, N))
    otros = [((el.get("elem", el) if isinstance(el, dict) else {"val": el}).get("val"), n[10:])
             for n, l in sets.items() for el in l]
    otros = [o for o in otros if o[0] != ip]
    if otros:
        print("  otras en el firewall: " + ", ".join("%s (%s)" % o for o in otros))
r = subprocess.run(["journalctl", "-u", "ppi-enforce-agent", "-n", "40", "--no-pager", "-o", "cat"],
                   capture_output=True, text=True)
ult = [l for l in r.stdout.splitlines() if l.startswith("{")]
if ult:
    try:
        d = json.loads(ult[-1])
        donde = ("aplica BLOCK" if ip in d.get("block", []) else "aplica LIMIT" if ip in d.get("limit", [])
                 else "la deja en sombra (%s)" % d["sombra"][ip] if ip in d.get("sombra", {}) else "nada para esta IP")
        print("\núltima pasada del agente: %s · %s · errores %s" % (d.get("estado"), donde, d.get("errores")))
    except ValueError:
        pass
EOF
  )
  clear; printf '%s\n' "$salida"
  sleep 2
done
