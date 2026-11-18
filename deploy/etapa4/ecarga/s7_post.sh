#!/usr/bin/env bash
# [BASTIÓN gadmin] Paso D4 de E-carga v2: S7 desde las trazas y las muestras. VERSION 2026-11-07.1. Solo lectura en
# srv-dmz y en el relé; escribe únicamente en SALIDA, que no debe existir.
#   s7_post.sh DIR_MUESTREO SALIDA DESDE HASTA
# Copia las mismas trazas que obs_p4_post.sh, conserva el rc de cada copia y deja SALIDA/s7.json, la fuente de
# construir_entrada.py --s7. Una copia fallida no aborta: derivar_s7.py la convierte en un null con su motivo.
# rc: 0 s7.json escrito, con cualquier valor · 2 uso o derivación imposible (sin s7.json, S7 queda null en la entrada).
set -u
set -o pipefail
O=${1:?DIR_MUESTREO}; S=${2:?SALIDA}; D=${3:?DESDE}; A=${4:?HASTA}
AQUI="$(cd "$(dirname "$0")" && pwd)"
SSH=${CF_SSH:-ssh}
K=${CF_LLAVES:-$HOME/.ssh}
T_COPIA=${CF_T_COPIA:-120}
[ ! -e "$S" ] || { echo "ABORTA: $S ya existe"; exit 2; }
mkdir "$S" || exit 2
timeout "$T_COPIA" $SSH -n -o BatchMode=yes -o ConnectTimeout=10 -i "$K/cyberflow-to-srv" adminsrvdmz@10.10.30.10 \
  'sudo -n cat /var/lib/cyberflow/agente/traza.jsonl' > "$S/traza-agente-copia.jsonl" 2> "$S/traza-agente.err"
ra=$?
tr -d '\000' < ~/relay-v2/traza.jsonl > "$S/traza-rele-copia-sin-nul.jsonl" 2> "$S/traza-rele.err"
rr=$?
python3 -I -B "$AQUI/derivar_s7.py" "$S/traza-agente-copia.jsonl" "$S/traza-rele-copia-sin-nul.jsonl" "$O/muestras.txt" \
  "$D" "$A" --rc-agente "$ra" --rc-rele "$rr" > "$S/s7.json.tmp"
r=$?
if [ "$r" != 0 ]; then echo "derivar_s7 rc=$r: sin s7.json"; exit 2; fi
mv "$S/s7.json.tmp" "$S/s7.json"
echo "copias: agente rc=$ra, relé rc=$rr"
python3 -I -B -c 'import json,sys;d=json.load(open(sys.argv[1]));print("S7", json.dumps(d["S7"], ensure_ascii=False))' "$S/s7.json"
exit 0
