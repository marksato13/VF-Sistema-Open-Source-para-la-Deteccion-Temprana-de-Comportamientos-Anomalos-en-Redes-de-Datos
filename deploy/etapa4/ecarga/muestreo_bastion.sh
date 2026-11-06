#!/usr/bin/env bash
# [BASTIÓN gadmin] Muestreo de E-carga v2 cada 30 s (criterio <= 60 s) en bastión, Sensor1, srv-dmz y clientes, con la
# guardia de §3.7 tras cada muestra. VERSION 2026-11-06.2 (sustituye a la de guiones-c7f24510, que marcaba la parada
# como hecha aunque el intento remoto fallara).
#
#   muestreo_bastion.sh DIR FIN_EPOCH PARADA_EPOCH real|seco
#
# Lecturas: las mismas claves que obs_muestreo.sh del 06-nov (líneas B, S, D) más la línea C (generadores.sh estado).
# Una lectura que falla se escribe como ERROR (o la línea «<X> ERROR ssh_rc=N»), nunca como un valor válido: con
# pipefail, un `sudo nft` fallido ya no produce el hash de la cadena vacía, y un PID ilegible ya no da «0 con --aplicar».
#
# Parada (solo en modo real; la pide la guardia o la hora PARADA_EPOCH). Estados, en parada.jsonl y eventos.log:
#   solicitada  se ha lanzado `generadores.sh parar` en clientes
#   fallida     el intento no se confirmó: error de ssh (rc 255), tiempo agotado (124) o rc remoto 3/4/5. Se conserva
#               la salida completa. Tras un rc 3 (stop con error) se pide `comprobar-parado`: si confirma, cuenta como
#               confirmada (con la nota)
#   confirmada  generadores.sh devolvió 0 (target, seis unidades y procesos comprobados) o comprobar-parado dio 0
#   agotada     MAX_INTENTOS intentos fallidos: se deja de intentar, se crea DIR/PARADA-NO-CONFIRMADA y se escribe
#               «INTERVENCIÓN NECESARIA». El muestreo sigue hasta FIN para conservar la medida.
# Un intento por muestra (cada 30 s), hasta MAX_INTENTOS (6, unos 3 min). Si la parada sigue pendiente al llegar a FIN,
# se siguen haciendo intentos (sin muestrear) hasta confirmarla o agotarlos.
# Modo seco: mismas lecturas y guardia; NUNCA lanza parar ni arrancar (solo «SECO: se pararían», una vez).
#
# rc: 0 fin normal (y, si se pidió una parada, confirmada); 4 parada pedida y NO confirmada (fallida o agotada);
#     2 uso o DIR existente.
set -u
set -o pipefail
VERSION=2026-11-06.2
O=${1:?DIR}; FIN=${2:?FIN_EPOCH}; PARADA=${3:?PARADA_EPOCH}; MODO=${4:?real|seco}
case "$MODO" in real|seco) ;; *) echo "modo $MODO no válido"; exit 2;; esac
AQUI="$(cd "$(dirname "$0")" && pwd)"
SSH=${CF_SSH:-ssh}
INTERVALO=${CF_INTERVALO:-30}
MAX_INTENTOS=${CF_MAX_INTENTOS:-6}
T_PARADA=${CF_T_PARADA:-90}          # s máximos de un intento (ssh + confirmación remota de hasta 20 s)
K=${CF_LLAVES:-$HOME/.ssh}
[ -e "$O/muestras.txt" ] && { echo "ABORTA: $O/muestras.txt ya existe (no se sobrescribe)"; exit 2; }
mkdir -p "$O" || exit 2
R="-o BatchMode=yes -o ConnectTimeout=10"
SEN="$SSH $R -i $K/cyberflow-to-sensor m4rk@10.10.60.11"
SRV="$SSH $R -i $K/cyberflow-to-srv adminsrvdmz@10.10.30.10"
CLI="$SSH $R -i $K/cyberflow-to-clientes adminclientes@10.10.20.20"
log() { echo "$(date -u +%FT%TZ) $(date +%s) $*" | tee -a "$O/eventos.log"; }
q() { local o; o=$("$@" 2>/dev/null) && [ -n "$o" ] && printf %s "$o" || printf ERROR; }

PARADA_ESTADO=ninguna; INTENTOS=0; SECO_AVISADO=0; MOTIVO_PARADA=""
registrar() {  # registrar RESULTADO RC RC_COMPROBACION
  printf '{"t": %s, "intento": %s, "motivo": "%s", "resultado": "%s", "rc": %s, "rc_comprobacion": %s}\n' \
    "$(date +%s)" "$INTENTOS" "${MOTIVO_PARADA//\"/\'}" "$1" "$2" "${3:-null}" >> "$O/parada.jsonl"
}
intentar_parada() {  # $1 = motivo (solo se guarda el primero)
  case "$PARADA_ESTADO" in confirmada|agotada) return ;; esac
  [ -n "$MOTIVO_PARADA" ] || MOTIVO_PARADA=$1
  if [ "$MODO" = seco ]; then
    [ $SECO_AVISADO = 1 ] || log "SECO: se pararían los generadores ($1); no se ejecuta nada"
    SECO_AVISADO=1; return
  fi
  INTENTOS=$((INTENTOS + 1)); PARADA_ESTADO=solicitada
  log "PARADA solicitada (intento $INTENTOS/$MAX_INTENTOS): $1"; registrar solicitada null
  local out rc out2 rc2=null
  out=$(timeout "$T_PARADA" $CLI 'bash -s parar' < "$AQUI/generadores.sh" 2>&1); rc=$?
  printf '%s\n' "$out" | sed "s/^/  [parar intento $INTENTOS] /" >> "$O/eventos.log"
  if [ $rc = 0 ]; then
    PARADA_ESTADO=confirmada; log "PARADA confirmada (intento $INTENTOS)"; registrar confirmada 0; return
  fi
  if [ $rc = 3 ]; then  # el stop devolvió error: se comprueba aparte si aun así quedó parado
    out2=$(timeout "$T_PARADA" $CLI 'bash -s comprobar-parado' < "$AQUI/generadores.sh" 2>&1); rc2=$?
    printf '%s\n' "$out2" | sed "s/^/  [comprobar-parado intento $INTENTOS] /" >> "$O/eventos.log"
    if [ $rc2 = 0 ]; then
      PARADA_ESTADO=confirmada; log "PARADA confirmada por comprobar-parado (el stop devolvió rc 3)"; registrar confirmada 3 0; return
    fi
  fi
  case $rc in 255) d="error de ssh";; 124) d="tiempo agotado ($T_PARADA s)";; 3) d="systemctl stop con error";;
              4) d="estado leído y NO parado";; 5) d="estado desconocido";; *) d="rc remoto $rc";; esac
  PARADA_ESTADO=fallida; log "PARADA FALLIDA (intento $INTENTOS, rc $rc: $d)"; registrar fallida "$rc" "$rc2"
  if [ "$INTENTOS" -ge "$MAX_INTENTOS" ]; then
    PARADA_ESTADO=agotada
    log "INTERVENCIÓN NECESARIA: parada NO confirmada tras $INTENTOS intentos; no se reintenta más"
    echo "$(date -u +%FT%TZ) parada no confirmada tras $INTENTOS intentos (último rc $rc: $d). Ver eventos.log" > "$O/PARADA-NO-CONFIRMADA"
    registrar agotada "$rc" "$rc2"
  fi
}

muestra() {
  echo "### $(date -u +%FT%TZ) $(date +%s)"
  echo "B relay pid=$(q systemctl show -p MainPID --value ppi-relay-eventos) nr=$(q systemctl show -p NRestarts --value ppi-relay-eventos) $(q systemctl show -p ActiveState --value ppi-relay-eventos) v1timer=$(q systemctl show -p ActiveState --value ppi-relay-feed.timer) v1=$(q systemctl show -p ActiveState --value ppi-relay-feed)"
  local pc crc
  pc=$(curl -sk -m 6 -o /dev/null -w '%{http_code}' https://10.10.60.11:8788/); crc=$?
  echo "B panel_https=${pc:-000} curl_rc=$crc ultima_traza=$(tail -1 ~/relay-v2/traza.jsonl 2>/dev/null | tr -d '\000' | cut -c1-220)"
  local rc
  $SEN bash -s <<'SENSOR1' 2>&1
set -o pipefail
q() { local o; o=$("$@" 2>/dev/null) && [ -n "$o" ] && printf %s "$o" || printf ERROR; }
for u in ppi-motor ppi-motor-capture ppi-via-rapida@ens37 suricata ppi-publicar-feed-v2 ppi-dashboard; do
  printf "S %s pid=%s nr=%s %s\n" $u "$(q systemctl show -p MainPID --value $u)" "$(q systemctl show -p NRestarts --value $u)" "$(q systemctl show -p ActiveState --value $u)"
done
# grep -c da rc 1 con 0 coincidencias: el error se decide por la lectura de ps, no por el rc de grep
if a=$(ps -eo args 2>/dev/null) && [ -n "$a" ]; then n=$(grep -cE -- "--(enforce|aplicar)( |$)" <<<"$a"); else n=ERROR; fi
echo "S v1 $(q systemctl show -p ActiveState --value ppi-publicar-feed.timer)/$(q systemctl show -p ActiveState --value ppi-publicar-feed) enforce_aplicar=$n"
echo "S feed_seq=$(python3 -c "import json;print(json.load(open('/home/m4rk/feed-v2/feed.json'))['secuencia'])" 2>/dev/null || echo ERROR)"
h=$(df --output=avail -k /home 2>/dev/null | tail -1 | tr -d " "); [[ $h =~ ^[0-9]+$ ]] || h=ERROR
c=$(cut -d" " -f1-3 /proc/loadavg 2>/dev/null) || c="ERROR ERROR ERROR"
m=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null); [[ $m =~ ^[0-9]+$ ]] || m=ERROR
echo "S home_libre_kb=$h carga=$c memdisp_kb=$m"
r=$(sudo -n nft list ruleset 2>/dev/null | sed -E "s/counter packets [0-9]+ bytes [0-9]+/counter/" | sha256sum | cut -c1-16) || r=ERROR
echo "S ruleset=$r"
e=$(tail -c 300000 /var/log/suricata/eve.json 2>/dev/null | grep '"event_type":"stats"' | tail -1 | python3 -c 'import json,sys;e=json.load(sys.stdin);c=e["stats"]["capture"];print(e["timestamp"],e["stats"]["uptime"],c.get("kernel_packets"),c.get("kernel_drops"))' 2>/dev/null) || e=ERROR
echo "S eve_ultimo_stats=$e"
echo "S anillo_ultimo=$(ls -t /var/lib/ppi-motor-capture 2>/dev/null | head -1)"
exit 0
SENSOR1
  rc=$?; [ $rc = 0 ] || echo "S ERROR ssh_rc=$rc"
  $SRV bash -s <<'SRVDMZ' 2>&1
set -o pipefail
q() { local o; o=$("$@" 2>/dev/null) && [ -n "$o" ] && printf %s "$o" || printf ERROR; }
cuenta() { local o; o=$(sudo -n grep -c "$1" "$2" 2>/dev/null); [[ $o =~ ^[0-9]+$ ]] && echo "$o" || echo ERROR; }
u=ppi-enforce-agent-v2-dmz; p=$(q systemctl show -p MainPID --value $u)
if [ "$p" = 0 ]; then ac=0                                   # sin proceso no hay ningún --aplicar
elif [[ $p =~ ^[0-9]+$ ]] && a=$(tr "\0" " " < /proc/$p/cmdline 2>/dev/null) && [ -n "$a" ]; then ac=$(grep -c -- --aplicar <<<"$a")
else ac=ERROR; fi
echo "D agente pid=$p nr=$(q systemctl show -p NRestarts --value $u) $(q systemctl show -p ActiveState --value $u) aplicar_cmd=$ac v1=$(q systemctl show -p ActiveState --value ppi-enforce-agent.timer)"
T=/var/lib/cyberflow/agente/traza.jsonl
r=$(sudo -n nft list ruleset 2>/dev/null | sha256sum | cut -c1-16) || r=ERROR
echo "D aplicacion=$(cuenta '"evento": "aplicacion"' $T) firma_invalida=$(cuenta firma_invalida $T) paquete_invalido=$(cuenta paquete_invalido $T) ruleset=$r"
echo "D ultima=$(sudo -n tail -1 $T 2>/dev/null | cut -c1-200)"
exit 0
SRVDMZ
  rc=$?; [ $rc = 0 ] || echo "D ERROR ssh_rc=$rc"
  local co
  co=$($CLI 'bash -s estado' < "$AQUI/generadores.sh" 2>&1); rc=$?
  printf '%s\n' "$co" | sed 's/^/C /'
  [ $rc = 0 ] || echo "C ERROR rc=$rc"
}

echo "$$ $(date -u +%FT%TZ) inicio muestreo v$VERSION modo=$MODO fin=$FIN parada=$PARADA intentos_max=$MAX_INTENTOS" >> "$O/muestreo.pid"
while [ "$(date +%s)" -le "$FIN" ]; do
  muestra >> "$O/muestras.txt" 2>&1
  g=$(python3 -I "$AQUI/guardia.py" "$O/muestras.txt"); echo "$g" >> "$O/guardia.jsonl"
  case "$g" in *'"parar": true'*) intentar_parada "guardia: $(python3 -c 'import json,sys;print("; ".join(json.loads(sys.argv[1])["motivos"])[:400])' "$g")";; esac
  if [ "$(date +%s)" -ge "$PARADA" ]; then intentar_parada "fin previsto (PARADA_EPOCH $PARADA)"
  elif [ "$PARADA_ESTADO" = fallida ]; then intentar_parada "reintento"; fi
  sleep $(( INTERVALO - $(date +%s) % INTERVALO ))
done
while [ "$PARADA_ESTADO" = fallida ]; do        # parada pendiente al llegar a FIN: se sigue intentando, acotado
  intentar_parada "reintento tras FIN"
  [ "$PARADA_ESTADO" = fallida ] && sleep "$INTERVALO"
done
echo "$(date -u +%FT%TZ) fin muestreo; parada=$PARADA_ESTADO intentos=$INTENTOS" >> "$O/muestreo.pid"
log "fin del muestreo: parada=$PARADA_ESTADO intentos=$INTENTOS"
case "$PARADA_ESTADO" in fallida|agotada|solicitada) exit 4 ;; *) exit 0 ;; esac
