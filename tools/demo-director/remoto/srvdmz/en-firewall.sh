#!/bin/bash
# Imprime BLOCK, LIMIT o NO segun en que set de la tabla cyberflow esta la IP. Solo lectura.
sudo -n /usr/local/sbin/cf-nft-mostrar 2>/dev/null | python3 -c '
import json, sys
ip = sys.argv[1]
try:
    doc = json.load(sys.stdin).get("nftables", [])
except ValueError:
    doc = []
for x in doc:
    s = x.get("set")
    if not s:
        continue
    for el in s.get("elem", []):
        v = el.get("elem", el) if isinstance(el, dict) else {"val": el}
        if v.get("val") == ip:
            print({"cyberflow_bloqueados": "BLOCK", "cyberflow_limitados": "LIMIT"}.get(s["name"], "?"))
            sys.exit()
print("NO")' "${1:?IP}"
