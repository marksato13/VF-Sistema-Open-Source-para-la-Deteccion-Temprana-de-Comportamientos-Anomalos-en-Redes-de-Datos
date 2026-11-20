#!/bin/bash
# Firewall del servidor (tabla v2 inet cyberflow_dmz), solo lectura via helper.
echo "{\"perfil\":\"dmz\",\"operaciones\":[{\"op\":\"listar\"}]}" | sudo -n /usr/local/sbin/cf-nft-helper \
 | python3 -c "import json,sys
e=json.load(sys.stdin).get(\"estado\",{}).get(\"sets\",{})
b=list((e.get(\"bloqueados\") or {}).keys()); l=list((e.get(\"limitados\") or {}).keys())
print(\"  BLOQUEADAS (drop):   \", \", \".join(b) if b else \"— ninguna —\")
print(\"  LIMITADAS (rate):    \", \", \".join(l) if l else \"— ninguna —\")"
