#!/usr/bin/env bash
# [SENSOR1 m4rk] Muestreadores de E-carga v2 en Sensor1 (solo lectura, sin sudo). VERSION 2026-11-06.3.
#   salud_captura.py muestrear (10 s)  ~/cyberflow-e4/herramientas-20261106 (VERSION 2026-11-06.1; idéntico al del paquete)
#   muestreo_fino.py (1 s), obs_pcap.py (cada PCAP cerrado), muestreo_s14.py (1 s, S14 r3)  del paquete en el que está
#   este guion: la ruta del paquete se deduce de la ubicación del guion (deploy/etapa4/ecarga/), sin nombres fijos.
#
#   sensor1_muestreadores.sh comprobar DIR FIN_EPOCH FIN_ISO   comprobaciones previas + obs_pcap --en-seco
#   sensor1_muestreadores.sh arrancar  DIR FIN_EPOCH FIN_ISO   lanza los cuatro y CONFIRMA que siguen vivos
#   sensor1_muestreadores.sh parar     DIR                     TERM a los PID de DIR/pids cuya cmdline coincide y confirma
#   sensor1_muestreadores.sh estado    DIR
# rc: 0 bien; 1 alguna comprobación FALLO; 2 uso o DIR ya usado; 3 algún muestreador no arrancó o no se paró.
set -u
set -o pipefail
ORDEN=${1:?orden}; O=${2:?DIR}
E="$(cd "$(dirname "$0")" && pwd)"; P="$(cd "$E/../../.." && pwd)"
H="$HOME/cyberflow-e4/herramientas-20261106"
PY="$HOME/cyberflow/.venv/bin/python"; ANILLO=/var/lib/ppi-motor-capture; EVE=/var/log/suricata/eve.json
EV_ESPERADO=53e9f7bd578123f6499289ebbb92d8d6c71a6e56b7c1c35a59463b98aad5c23f
RETENCION_MIN=900
ok() { echo "OK    $*"; }; no() { echo "FALLO $*"; fallo=1; }
fallo=0
procesos() {  # cmdline de los procesos que coinciden; rc 2 si pgrep falla (no «ninguno»)
  local o rc; o=$(pgrep -af "$1" 2>&1); rc=$?
  case $rc in 0) grep -v pgrep <<<"$o"; return 0;; 1) return 1;; *) echo "pgrep rc $rc: $o" >&2; return 2;; esac
}
comprobar() {
  local FIN=$1 ISO=$2 v libre mem a rc viejo edad
  (cd "$P" && sha256sum -c --strict --quiet SHA256SUMS) && ok "paquete $(basename "$P"): SHA256SUMS verifica" || no "paquete $P"
  [ "$(sha256sum < "$P/deploy/etapa4/sensor1/evaluar_ecarga.py" | cut -c1-64)" = "$EV_ESPERADO" ] \
    && ok "evaluar_ecarga.py sha256 = publicado" || no "evaluar_ecarga.py sha256"
  v=$(python3 -I -B -c 'import importlib.util as u,sys;s=u.spec_from_file_location("e",sys.argv[1]);m=u.module_from_spec(s);s.loader.exec_module(m);print(m.VERSION)' "$P/deploy/etapa4/sensor1/evaluar_ecarga.py")
  [ "$v" = 2026-11-06.4 ] && ok "evaluar_ecarga VERSION $v" || no "evaluar_ecarga VERSION $v"
  (cd "$H" && sha256sum -c --strict --quiet SHA256SUMS) && ok "herramientas-20261106: SHA256SUMS verifica" || no "herramientas-20261106"
  cmp -s "$H/salud_captura.py" "$P/scripts/etapa4/salud_captura.py" && ok "salud_captura.py de herramientas = paquete" \
    || no "salud_captura.py de herramientas distinto del paquete"
  [ -x "$PY" ] && ok "python del venv: $("$PY" -V 2>&1)" || no "python del venv"
  for f in "$P/deploy/etapa4/cierre/muestreo_fino.py" "$P/deploy/etapa4/sensor1/obs_pcap.py" "$P/deploy/etapa4/sensor1/clasificar_periodo.py" \
           "$P/deploy/etapa4/sensor1/comparar_suricata.py" "$P/deploy/etapa4/sensor1/verificar_sensor1.sh" "$E/muestreo_s14.py" "$E/evaluar_s14.py"; do
    [ -r "$f" ] && ok "legible $(basename "$f")" || no "no legible $f"; done
  [ -r "$EVE" ] && ok "eve.json legible ($(stat -c %s "$EVE") B)" || no "eve.json no legible"
  [ -r "$ANILLO" ] && [ -x "$ANILLO" ] && ok "anillo legible ($(ls -1 "$ANILLO" | wc -l) ficheros)" || no "anillo no legible"
  viejo=$(ls -1 "$ANILLO" 2>/dev/null | grep -E '^live-[0-9]{14}\.pcap$' | sort | head -1)
  if [ -n "$viejo" ]; then
    edad=$(( $(date +%s) - $(date -u -d "${viejo:5:8} ${viejo:13:2}:${viejo:15:2}:${viejo:17:2}" +%s) ))
    [ "$edad" -ge $RETENCION_MIN ] && ok "retención del anillo: el fichero más antiguo tiene $edad s (>= $RETENCION_MIN s, la de derivar_pcap)" \
      || no "retención del anillo $edad s < $RETENCION_MIN s: derivar_pcap 2026-11-06.2 usa $RETENCION_MIN s"
  else no "no se pudo medir la retención del anillo"; fi
  for f in /proc/net/softnet_stat /proc/pressure/cpu /proc/pressure/io /proc/pressure/memory /proc/vmstat /proc/diskstats; do
    [ -r "$f" ] && ok "legible $f" || no "no legible $f (S14 r3 lo necesita)"; done
  [ "$(getconf CLK_TCK)" = 100 ] && ok "USER_HZ 100" || echo "INFO  USER_HZ $(getconf CLK_TCK) (muestreo_s14 lo registra)"
  for u in ppi-motor-capture ppi-via-rapida@ens37; do
    n=$(journalctl --no-pager -u "$u" --since "-10min" 2>/dev/null | grep -c "packets captured")
    [ "${n:-0}" -gt 0 ] && ok "journal de $u legible ($n lecturas SIGUSR1 en 10 min)" || no "journal de $u sin lecturas SIGUSR1"; done
  libre=$(df --output=avail -k /home 2>/dev/null | tail -1 | tr -d ' ')
  [[ $libre =~ ^[0-9]+$ ]] && [ "$libre" -ge 2097152 ] && ok "/home libre $((libre/1024)) MiB (>= 2 GiB)" || no "/home libre ${libre:-ilegible} kB"
  mem=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null)
  [[ $mem =~ ^[0-9]+$ ]] && [ "$mem" -ge 1048576 ] && ok "MemAvailable $((mem/1024)) MiB (>= 1 GiB)" || no "MemAvailable ${mem:-ilegible} kB"
  mkdir -p "$(dirname "$O")" && [ -w "$(dirname "$O")" ] && ok "destino de evidencia escribible: $(dirname "$O")" || no "destino $O"
  [ -e "$O" ] && no "DIR $O ya existe (no se reutiliza)" || ok "DIR $O libre"
  if a=$(ps -eo args 2>/dev/null) && [ -n "$a" ]; then
    grep -qE -- "--(enforce|aplicar)( |$)" <<<"$a" && no "hay procesos con --aplicar/--enforce" || ok "0 procesos con --aplicar/--enforce"
  else no "ps no se pudo leer"; fi
  procesos "salud_captura.py muestrear|muestreo_fino.py|obs_pcap.py|muestreo_s14.py"; rc=$?
  case $rc in 1) ok "ningún muestreador en marcha";; 0) no "ya hay muestreadores en marcha";; *) no "pgrep falló";; esac
  echo "== obs_pcap --en-seco"
  python3 -I -B "$P/deploy/etapa4/sensor1/obs_pcap.py" --dir "$ANILLO" --salida "$O-seco-obs_pcap" --hasta-epoch "$FIN" --hasta-iso "$ISO" --en-seco
  rc=$?; [ $rc = 0 ] && ok "obs_pcap --en-seco rc 0" || no "obs_pcap --en-seco rc $rc"
  [ -e "$O-seco-obs_pcap" ] && no "obs_pcap en seco creó $O-seco-obs_pcap" || ok "obs_pcap en seco no creó salida"
  echo "fallo=$fallo"; return $fallo
}
vivo() { [ -r /proc/$1/cmdline ] && tr '\0' ' ' < /proc/$1/cmdline 2>/dev/null | grep -q -- "$2"; }
arrancar() {
  local FIN=$1 ISO=$2 malos=0 pid nombre
  { [ -e "$O/muestras.jsonl" ] || [ -e "$O/pids" ]; } && { echo "ABORTA: $O ya tiene muestras o pids"; exit 2; }
  mkdir -p "$O" || exit 2
  (cd "$H" && sha256sum -c --strict --quiet SHA256SUMS) || { echo "ABORTA: herramientas-20261106"; exit 2; }
  (setsid nohup "$PY" -I "$H/salud_captura.py" muestrear --salida "$O/muestras.jsonl" --suricata-stats /var/log/suricata/stats.log \
     --interfaz ens37 --unidad ppi-motor --unidad ppi-motor-capture --unidad ppi-via-rapida@ens37 --unidad ppi-publicar-feed-v2 \
     --unidad suricata --anillo "$ANILLO" --resumen-rapida "$HOME/feed-v2/via-rapida-resumen.jsonl" \
     --ciclos "$HOME/cyberflow/logs/_state-e4/ciclos.jsonl" --hijos-de-unidad ppi-via-rapida@ens37 --intervalo 10 --hasta "$ISO" \
     > "$O/muestrear.out" 2>&1 < /dev/null & echo "$! salud_captura.py muestrear" >> "$O/pids")
  (setsid nohup python3 -I "$P/deploy/etapa4/cierre/muestreo_fino.py" --salida "$O/fino.jsonl" --intervalo 1 --hasta "$FIN" \
     > "$O/fino.out" 2>&1 < /dev/null & echo "$! muestreo_fino.py" >> "$O/pids")
  (setsid nohup python3 -I "$P/deploy/etapa4/sensor1/obs_pcap.py" --dir "$ANILLO" --salida "$O/obs_pcap" --hasta-epoch "$FIN" \
     --hasta-iso "$ISO" > "$O/obs_pcap.log" 2>&1 < /dev/null & echo "$! obs_pcap.py" >> "$O/pids")
  (setsid nohup python3 -I "$E/muestreo_s14.py" --salida "$O/s14.jsonl" --intervalo 1 --hasta "$FIN" \
     > "$O/s14.out" 2>&1 < /dev/null & echo "$! muestreo_s14.py" >> "$O/pids")
  echo "$(date -u +%FT%TZ) arrancados (fin $FIN = $ISO)" >> "$O/eventos.log"
  sleep 3
  while read -r pid nombre; do
    vivo "$pid" "$nombre" && echo "vivo   $pid $nombre" || { echo "NO ARRANCÓ $pid $nombre"; malos=1; }
  done < "$O/pids"
  [ $malos = 0 ] && { echo "ARRANQUE_CONFIRMADO: 4 muestreadores vivos"; return 0; }
  echo "ARRANQUE_INCOMPLETO: ver $O/*.out y obs_pcap.log"; return 3
}
estado() {
  [ -r "$O/pids" ] || { echo "sin $O/pids"; return 2; }
  while read -r pid nombre; do
    vivo "$pid" "$nombre" && echo "vivo   $pid $nombre" || echo "parado $pid $nombre"
  done < "$O/pids"
  for f in muestras.jsonl fino.jsonl obs_pcap/pcap.jsonl s14.jsonl; do [ -e "$O/$f" ] && echo "fichero $f $(wc -l < "$O/$f") líneas"; done
  return 0
}
parar() {
  local pid nombre quedan=0
  [ -r "$O/pids" ] || { echo "sin $O/pids"; return 2; }
  while read -r pid nombre; do
    vivo "$pid" "$nombre" && { kill -TERM "$pid" && echo "TERM $pid $nombre" || echo "TERM falló $pid $nombre"; }
  done < "$O/pids"
  echo "$(date -u +%FT%TZ) parada manual" >> "$O/eventos.log"; sleep 3
  while read -r pid nombre; do vivo "$pid" "$nombre" && { echo "SIGUE VIVO $pid $nombre"; quedan=1; }; done < "$O/pids"
  [ $quedan = 0 ] && { echo "PARADA_CONFIRMADA: ningún muestreador de $O vivo"; return 0; }
  return 3
}
case "$ORDEN" in
  comprobar) comprobar "${3:?FIN_EPOCH}" "${4:?FIN_ISO}" ;;
  arrancar)  arrancar "${3:?FIN_EPOCH}" "${4:?FIN_ISO}" ;;
  estado)    estado ;;
  parar)     parar ;;
  *) echo "orden no válida"; exit 2 ;;
esac
