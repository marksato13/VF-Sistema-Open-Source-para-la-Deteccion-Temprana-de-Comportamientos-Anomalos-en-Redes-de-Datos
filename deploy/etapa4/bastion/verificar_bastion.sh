#!/usr/bin/env bash
# [BASTIÓN gadmin] Verificación de la 4A en el bastión: SOLO lecturas, sin sudo (la puede ejecutar Claude).
# Traza del relé (relay_eventos.py): {"traido_en", "huella", "destinos": {"srv-dmz": {"entregado_en"}}}
# y eventos "pareja_inconsistente" / "lectura_inestable" / "error" con "t".
set -uo pipefail
fallo=0
# 4A (2026-11-04): cada comprobación sin pipefail (grep -q corta la tubería: SIGPIPE río arriba daba FALLO falso).
c() { if ( set +o pipefail; eval "$2" ); then echo "OK    $1"; else echo "FALLO $1"; fallo=1; fi; }
T="$HOME/relay-v2/traza.jsonl"
c "relé v2 activo" "systemctl is-active --quiet ppi-relay-eventos"
c "relé v2 solo con destino srv-dmz (sin dc1)" "! systemctl cat ppi-relay-eventos | grep -q 'dc1='"
c "relé v1 sigue activo e intacto" "systemctl is-active --quiet ppi-relay-feed.timer"
python3 - "$T" > /tmp/e4-rele.txt <<'EOF'
import json, sys, time
ahora, ent, inc, err, lat = time.time(), [], 0, 0, []
for l in open(sys.argv[1], encoding="utf-8"):
    try:
        r = json.loads(l)
    except ValueError:
        continue
    d = (r.get("destinos") or {}).get("srv-dmz")
    if d and d.get("entregado_en"):
        ent.append(float(d["entregado_en"]))
        if r.get("traido_en"):
            lat.append(float(d["entregado_en"]) - float(r["traido_en"]))
    elif r.get("evento") == "pareja_inconsistente" and ahora - float(r.get("t") or 0) < 3600:
        inc += 1
    elif r.get("evento") == "error" and ahora - float(r.get("t") or 0) < 3600:
        err += 1
ok = bool(ent) and ahora - ent[-1] < 60
print(("OK    " if ok else "FALLO ") + f"entrega reciente a srv-dmz (hace {ahora - ent[-1]:.1f} s)" if ent else "FALLO sin entregas")
print(f"INFO  entregas: {len(ent)}; traído->entregado p50/máx: "
      f"{sorted(lat)[len(lat)//2]:.3f}/{max(lat):.3f} s" if lat else "INFO  sin latencias")
print(f"INFO  última hora: parejas inconsistentes {inc}, errores {err}")
EOF
cat /tmp/e4-rele.txt; grep -q '^FALLO' /tmp/e4-rele.txt && fallo=1
c "reloj sincronizado" "timedatectl show -p NTPSynchronized --value | grep -qx yes"
[ "$fallo" = 0 ] && echo "VERIFICACIÓN BASTIÓN OK" || { echo "VERIFICACIÓN BASTIÓN CON FALLOS"; exit 1; }
