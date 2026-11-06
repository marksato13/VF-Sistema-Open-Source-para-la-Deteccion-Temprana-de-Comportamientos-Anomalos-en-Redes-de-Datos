#!/usr/bin/env bash
# [SENSOR1 m4rk] Herramientas de medida 2026-11-06.1 (P1) en un directorio PROPIO, sin sudo y sin tocar servicios.
# El detector congelado ~/cyberflow-e4/ec78ca5 (SHA256SUMS, 87 ficheros) NO se modifica: se comprueba antes y después.
#   bash sensor1_herramientas.sh <PAQ>       -> ~/cyberflow-e4/herramientas-20261106/ (+ SHA256SUMS) y una lectura I5
# Reversión: no hay nada que revertir en servicios; el directorio se puede dejar (no lo usa ningún servicio).
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
source "$AQUI/../comun/evidencia.sh"
P="${1:?paquete}"; D="$HOME/cyberflow-e4/herramientas-20261106"; E4="$HOME/cyberflow-e4/ec78ca5"
EV="$HOME/cf-e4p/sensor1-herramientas-$(date -u +%Y%m%dT%H%M%SZ)"; ev_abrir "$EV"
parar() { echo "PARADA $*"; ev_sellar "$EV" > /dev/null 2>&1; exit 1; }
( cd "$P" && sha256sum -c --quiet SHA256SUMS ) || parar "el paquete no verifica"
( cd "$E4" && sha256sum -c --quiet SHA256SUMS ) || parar "ec78ca5 no verifica ANTES"
[ -e "$D" ] && parar "$D ya existe"
mkdir -p "$D"
for f in scripts/etapa4/salud_captura.py scripts/etapa4/vigia_4c.py deploy/etapa4/sensor1/clasificar_periodo.py \
         deploy/etapa4/comun/evidencia.sh; do install -m 0644 "$P/$f" "$D/"; done
( cd "$D" && sha256sum ./* > SHA256SUMS && cat SHA256SUMS )
( cd "$E4" && sha256sum -c --quiet SHA256SUMS ) || parar "ec78ca5 no verifica DESPUÉS"
echo "OK    ec78ca5 intacto antes y después"
PY="$HOME/cyberflow/.venv/bin/python"
"$PY" -I "$D/salud_captura.py" i5 --eve /var/log/suricata/eve.json > "$EV/i5-instalacion.json"; echo "rc_i5=$?"
"$PY" -c 'import json,sys; r=json.load(open(sys.argv[1])); m=r["medida"]; print("I5:", r["i5"], m["estado"], "paquetes", m.get("paquetes"), "descartes", m.get("descartes"))' "$EV/i5-instalacion.json"
ev_sellar "$EV"
