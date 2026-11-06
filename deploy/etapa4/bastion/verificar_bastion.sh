#!/usr/bin/env bash
# [BASTIÓN gadmin] Verificación de la 4A en el bastión: SOLO lecturas, sin sudo (la puede ejecutar Claude).
# Traza del relé (relay_eventos.py): {"traido_en", "huella", "destinos": {"srv-dmz": {"entregado_en"}}}
# y eventos "pareja_inconsistente" / "lectura_inestable" / "error" con "t".
# 2026-11-06 (pendientes 4A): el relé v1 se retiró en el cierre complementario (04-nov); ahora debe estar inactivo,
# NO habilitado y sin procesos (comun/verif_estado.py). Un error de lectura o de systemctl nunca da OK.
set -uo pipefail
fallo=0
# 4A (2026-11-04): cada comprobación sin pipefail (grep -q corta la tubería: SIGPIPE río arriba daba FALLO falso).
c() { if ( set +o pipefail; eval "$2" ); then echo "OK    $1"; else echo "FALLO $1"; fallo=1; fi; }
# Bloque que imprime OK/FALLO/INFO: FALLO si alguna línea es FALLO, si su código no es 0 o si no imprimió ningún OK.
bloque() { local n="$1" s; shift; s=$("$@" 2>&1); local rc=$?; [ -n "$s" ] && echo "$s"
  if [ $rc -ne 0 ] || grep -q '^FALLO' <<<"$s" || ! grep -q '^OK' <<<"$s"; then
    grep -q '^FALLO' <<<"$s" || echo "FALLO $n (rc=$rc sin resultado)"; fallo=1; fi; }
VE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/comun/verif_estado.py"
T="$HOME/relay-v2/traza.jsonl"
c "relé v2 activo" "systemctl is-active --quiet ppi-relay-eventos"
c "relé v2 solo con destino srv-dmz (sin dc1)" "u=\$(systemctl cat ppi-relay-eventos) && ! grep -q 'dc1=' <<<\"\$u\""
c "relé v2 en modo --entrega paquete" "u=\$(systemctl cat ppi-relay-eventos) && grep -q -- '--entrega paquete' <<<\"\$u\""
bloque "relé v1 retirado" python3 -I "$VE" v1-retirado \
  --unidad ppi-relay-feed.timer --unidad ppi-relay-feed.service --proceso relay-feed.sh
bloque "entregas del relé v2" python3 -I - "$T" <<'EOF'
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
c "reloj sincronizado" "timedatectl show -p NTPSynchronized --value | grep -qx yes"
[ "$fallo" = 0 ] && echo "VERIFICACIÓN BASTIÓN OK" || { echo "VERIFICACIÓN BASTIÓN CON FALLOS"; exit 1; }
