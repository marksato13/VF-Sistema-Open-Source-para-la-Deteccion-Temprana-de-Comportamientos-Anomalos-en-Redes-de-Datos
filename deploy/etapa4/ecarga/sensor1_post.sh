#!/usr/bin/env bash
# [SENSOR1 m4rk] Análisis posterior de E-carga v2 (solo lecturas). VERSION 2026-11-06.2. No antes de HASTA + 900 s
# (flow-timeouts TCP 600 + 60 s; en la franja propuesta, 04:30Z).
#   sensor1_post.sh DIR DESDE HASTA BASE_DESDE BASE_HASTA
# DIR es la carpeta de los muestreadores (muestras.jsonl, obs_pcap/pcap.jsonl, obs_pcap.log, s14.jsonl). Escribe en
# DIR/post (si existe, aborta). BASE_* = línea base de S14 (los 300 s previos a T_g).
# Salidas: clasificacion/, comparar.json (K1–K3), perfiles.json + perfiles.rc (K4a; K4b informativo), pcap_s.json
# (S2, S3), s14.json (S14), suricata-ls.txt, ruleset-despues.txt, rc.txt (rc de cada paso) y SHA256SUMS.
set -u
set -o pipefail
O=${1:?DIR}; D=${2:?DESDE}; A=${3:?HASTA}; BD=${4:?BASE_DESDE}; BH=${5:?BASE_HASTA}
E="$(cd "$(dirname "$0")" && pwd)"; P="$(cd "$E/../../.." && pwd)"
H="$HOME/cyberflow-e4/herramientas-20261106"; PY="$HOME/cyberflow/.venv/bin/python"; S="$O/post"
[ -e "$S" ] && { echo "ABORTA: $S ya existe"; exit 2; }
mkdir -p "$S" || exit 2
paso() { echo "$1 rc=$2" | tee -a "$S/rc.txt"; }
echo "######## post $(date -u +%FT%TZ) ventana $D–$A base $BD–$BH paquete $(basename "$P")"
if o=$(pgrep -af "salud_captura.py muestrear|muestreo_fino.py|obs_pcap.py|muestreo_s14.py"); then
  echo "AVISO: muestreadores aún vivos:"; grep -v pgrep <<<"$o"; else echo "muestreadores terminados (pgrep rc $?)"; fi
ls -la --time-style=+%FT%T /var/log/suricata/ > "$S/suricata-ls.txt" 2>&1
EVES=(/var/log/suricata/eve.json)
for f in /var/log/suricata/eve.json.1 /var/log/suricata/eve.json.1.gz; do
  [ -f "$f" ] && [ "$(stat -c %Y "$f")" -ge "${D%.*}" ] && EVES=("$f" "${EVES[@]}") && echo "eve rotó en la ventana: $f"
done
SE=(); SV=(); EP=(); for e in "${EVES[@]}"; do SE+=(--suricata-eve "$e"); SV+=(--stats-eve "$e" --eve "$e"); EP+=(--eve "$e"); done
"$PY" -I "$H/clasificar_periodo.py" --salud-captura "$H/salud_captura.py" --muestras "$O/muestras.jsonl" \
  --salida "$S/clasificacion" --desde "$D" --hasta "$A" "${SE[@]}" > "$S/clasificar.out" 2>&1; paso clasificar_periodo $?
python3 -I "$P/deploy/etapa4/sensor1/comparar_suricata.py" "${SV[@]}" --desde "$D" --hasta "$A" --etiqueta ecarga-v2 \
  > "$S/comparar.json" 2> "$S/comparar.err"; paso comparar_suricata $?
python3 -I "$P/deploy/etapa4/sensor1/evaluar_ecarga.py" perfiles "${EP[@]}" --desde "$D" --hasta "$A" > "$S/perfiles.json" 2>&1
r=$?; echo $r > "$S/perfiles.rc"; paso "evaluar_ecarga perfiles" $r
python3 -I "$E/derivar_pcap.py" "$O/obs_pcap/pcap.jsonl" "$D" "$A" --log "$O/obs_pcap.log" > "$S/pcap_s.json" 2> "$S/pcap_s.err"; paso derivar_pcap $?
python3 -I "$E/evaluar_s14.py" "$O/s14.jsonl" --desde "$D" --hasta "$A" --base-desde "$BD" --base-hasta "$BH" \
  > "$S/s14.json" 2> "$S/s14.err"; paso evaluar_s14 $?
python3 -I -c 'import json,sys
for f,k in ((sys.argv[1],("S2","S3")),(sys.argv[2],("S14",))):
    try: d=json.load(open(f))
    except Exception as e: print(f, "ilegible:", e); continue
    for x in k: print(x, d.get(x))' "$S/pcap_s.json" "$S/s14.json"
if r=$(sudo -n nft list ruleset 2>/dev/null | sed -E "s/counter packets [0-9]+ bytes [0-9]+/counter/" | sha256sum | cut -c1-16); then
  echo "$r" > "$S/ruleset-despues.txt"; else echo ERROR > "$S/ruleset-despues.txt"; fi
echo "ruleset después: $(cat "$S/ruleset-despues.txt")"
(cd "$S" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS) && echo "sellado $S/SHA256SUMS"
