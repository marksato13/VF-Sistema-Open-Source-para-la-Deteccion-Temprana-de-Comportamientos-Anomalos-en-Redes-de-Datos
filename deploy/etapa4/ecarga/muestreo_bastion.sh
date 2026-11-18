#!/usr/bin/env bash
# [BASTIÓN gadmin] Muestreo de E-carga v2 cada 30 s (criterio <= 60 s) en bastión, Sensor1, srv-dmz y clientes, con la
# guardia de §3.7 tras cada muestra. VERSION 2026-11-07.1 (la 2026-11-06.2 podía salir del bucle sin intentar la parada
# y trataba «confirmada» como definitiva aunque después arrancaran los generadores).
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
#   reabierta   una parada confirmada deja de valer: `estado` lee generadores vivos, o la comprobación final no confirma.
#               Vuelve a fallida y sigue el mismo límite de intentos
# Un intento por muestra (cada 30 s), hasta MAX_INTENTOS (6, unos 3 min). Si la parada sigue pendiente al llegar a FIN,
# se siguen haciendo intentos (sin muestrear) hasta confirmarla o agotarlos.
# Salida del bucle (2026-11-07.1): FIN >= PARADA, así que al salir ya se llegó a la hora de parada. Si no hay parada
# confirmada, se intenta aquí con el mismo camino; si la hay, se comprueba con `comprobar-parado`.
# Modo seco: mismas lecturas y guardia; NUNCA lanza parar ni arrancar (solo «SECO: se pararían», una vez).
#
# Coordinación con arrancar_c1.sh, en DIR:
#   PARADA-SOLICITADA  se escribe ANTES de cualquier orden y no se borra nunca: arrancar_c1.sh lo lee antes y después de
#                      arrancar, y sus motivos también llegan aquí
#   ordenes.lock       cerrojo flock: arrancar y parar nunca se solapan
# Resultado para el operador: DIR/RESULTADO-PARADA, una línea JSON escrita al terminar. Si no existe, el proceso sigue en
# marcha o murió sin poder escribirla. Nunca se interpreta como parada hecha.
#
# rc: 0 fin normal con parada confirmada y comprobada (modo seco: sin ninguna orden); 4 parada NO confirmada;
#     2 uso o DIR existente; 143 interrumpido por una señal.
set -u
set -o pipefail
VERSION=2026-11-07.1
O=${1:?DIR}; FIN=${2:?FIN_EPOCH}; PARADA=${3:?PARADA_EPOCH}; MODO=${4:?real|seco}
case "$MODO" in real|seco) ;; *) echo "modo $MODO no válido"; exit 2;; esac
[[ $FIN =~ ^[0-9]+$ ]] && [[ $PARADA =~ ^[0-9]+$ ]] && [ "$PARADA" -le "$FIN" ] \
  || { echo "ABORTA: se exige PARADA_EPOCH <= FIN_EPOCH, en epoch ($PARADA, $FIN)"; exit 2; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
SSH=${CF_SSH:-ssh}
INTERVALO=${CF_INTERVALO:-30}
MAX_INTENTOS=${CF_MAX_INTENTOS:-6}
T_PARADA=${CF_T_PARADA:-90}          # s máximos de un intento (ssh + confirmación remota de hasta 20 s)
T_CERROJO=${CF_T_CERROJO:-120}       # s máximos esperando a que termine un arranque en curso antes de pedir la parada
K=${CF_LLAVES:-$HOME/.ssh}
[ -e "$O/muestras.txt" ] && { echo "ABORTA: $O/muestras.txt ya existe (no se sobrescribe)"; exit 2; }
mkdir -p "$O" || exit 2
R="-o BatchMode=yes -o ConnectTimeout=10"
SEN="$SSH $R -i $K/cyberflow-to-sensor m4rk@10.10.60.11"
SRV="$SSH $R -i $K/cyberflow-to-srv adminsrvdmz@10.10.30.10"
CLI="$SSH $R -i $K/cyberflow-to-clientes adminclientes@10.10.20.20"
log() { echo "$(date -u +%FT%TZ) $(date +%s) $*" | tee -a "$O/eventos.log"; }
q() { local o; o=$("$@" 2>/dev/null) && [ -n "$o" ] && printf %s "$o" || printf ERROR; }

PARADA_ESTADO=ninguna; INTENTOS=0; SECO_AVISADO=0; MOTIVO_PARADA=""; GEN_VIVOS=0; COMPROBACION_FINAL=null
ORDEN_SALIDA=""
registrar() {  # registrar RESULTADO RC RC_COMPROBACION
  printf '{"t": %s, "intento": %s, "motivo": "%s", "resultado": "%s", "rc": %s, "rc_comprobacion": %s}\n' \
    "$(date +%s)" "$INTENTOS" "${MOTIVO_PARADA//\"/\'}" "$1" "$2" "${3:-null}" >> "$O/parada.jsonl"
}
orden() {  # orden parar|comprobar-parado -> deja ORDEN_SALIDA y devuelve el rc; 125 si el cerrojo sigue ocupado
  local rc
  exec 9>>"$O/ordenes.lock"
  if ! flock -w "$T_CERROJO" 9; then
    exec 9>&-; ORDEN_SALIDA="cerrojo ordenes.lock ocupado más de $T_CERROJO s"; return 125
  fi
  ORDEN_SALIDA=$(timeout "$T_PARADA" $CLI "bash -s $1" < "$AQUI/generadores.sh" 2>&1 9>&-); rc=$?
  exec 9>&-
  return $rc
}
agotar() {  # agotar RC RC_COMPROBACION DETALLE
  PARADA_ESTADO=agotada
  log "INTERVENCIÓN NECESARIA: parada NO confirmada tras $INTENTOS intentos; no se reintenta más"
  echo "$(date -u +%FT%TZ) parada no confirmada tras $INTENTOS intentos (último rc $1: $3). Ver eventos.log" > "$O/PARADA-NO-CONFIRMADA"
  registrar agotada "$1" "$2"
}
reabrir_parada() {  # $1 = motivo; la confirmación anterior deja de valer, con el mismo límite de intentos
  PARADA_ESTADO=fallida
  log "PARADA reabierta: $1"; registrar reabierta null
  [ "$INTENTOS" -lt "$MAX_INTENTOS" ] || agotar null null "$1"
}
intentar_parada() {  # $1 = motivo (solo se guarda el primero)
  case "$PARADA_ESTADO" in confirmada|agotada) return ;; esac
  [ -n "$MOTIVO_PARADA" ] || MOTIVO_PARADA=$1
  if [ "$MODO" = seco ]; then
    [ $SECO_AVISADO = 1 ] || log "SECO: se pararían los generadores ($1); no se ejecuta nada"
    SECO_AVISADO=1; return
  fi
  echo "$(date +%s) $1" >> "$O/PARADA-SOLICITADA"      # antes de esperar al cerrojo: arrancar_c1.sh lo ve dentro de él
  INTENTOS=$((INTENTOS + 1)); PARADA_ESTADO=solicitada
  log "PARADA solicitada (intento $INTENTOS/$MAX_INTENTOS): $1"; registrar solicitada null
  local rc rc2=null
  orden parar; rc=$?
  printf '%s\n' "$ORDEN_SALIDA" | sed "s/^/  [parar intento $INTENTOS] /" >> "$O/eventos.log"
  if [ $rc = 0 ]; then
    PARADA_ESTADO=confirmada; log "PARADA confirmada (intento $INTENTOS)"; registrar confirmada 0; return
  fi
  if [ $rc = 3 ]; then  # el stop devolvió error: se comprueba aparte si aun así quedó parado
    orden comprobar-parado; rc2=$?
    printf '%s\n' "$ORDEN_SALIDA" | sed "s/^/  [comprobar-parado intento $INTENTOS] /" >> "$O/eventos.log"
    if [ $rc2 = 0 ]; then
      PARADA_ESTADO=confirmada; log "PARADA confirmada por comprobar-parado (el stop devolvió rc 3)"; registrar confirmada 3 0; return
    fi
  fi
  local d
  case $rc in 255) d="error de ssh";; 124) d="tiempo agotado ($T_PARADA s)";; 3) d="systemctl stop con error";;
              4) d="estado leído y NO parado";; 5) d="estado desconocido";; 125) d="arranque en curso: cerrojo ocupado";;
              *) d="rc remoto $rc";; esac
  PARADA_ESTADO=fallida; log "PARADA FALLIDA (intento $INTENTOS, rc $rc: $d)"; registrar fallida "$rc" "$rc2"
  [ "$INTENTOS" -lt "$MAX_INTENTOS" ] || agotar "$rc" "$rc2" "$d"
}
cerrar_parada() {  # tras el bucle: en modo real no se sale sin parada confirmada y comprobada, o sin agotar los intentos
  local r
  if [ "$PARADA_ESTADO" = ninguna ]; then
    log "PARADA pendiente al salir del bucle: ahora $(date +%s), PARADA_EPOCH $PARADA, FIN $FIN, sin intento previo"
  fi
  while :; do
    case "$PARADA_ESTADO" in
      agotada) return ;;
      confirmada)
        orden comprobar-parado; r=$?; COMPROBACION_FINAL=$r
        printf '%s\n' "$ORDEN_SALIDA" | sed "s/^/  [comprobación final] /" >> "$O/eventos.log"
        registrar comprobacion_final "$r"
        [ "$r" != 0 ] || return
        reabrir_parada "la comprobación final no confirma la parada (rc $r)" ;;
      *) intentar_parada "fin previsto; detectado al salir del bucle (PARADA_EPOCH $PARADA)"
         [ "$PARADA_ESTADO" = fallida ] && sleep "$INTERVALO" ;;
    esac
  done
}
escribir_resultado() {  # escribir_resultado RESULTADO RC INTERVENCION(true|false): sustitución atómica
  local m=${MOTIVO_PARADA//\\/\/}
  printf '{"version": "%s", "modo": "%s", "resultado": "%s", "rc": %s, "intentos": %s, "comprobacion_final_rc": %s, "intervencion_necesaria": %s, "motivo": "%s", "t": %s}\n' \
    "$VERSION" "$MODO" "$1" "$2" "$INTENTOS" "$COMPROBACION_FINAL" "$3" "${m//\"/\'}" "$(date +%s)" > "$O/.RESULTADO-PARADA.tmp" \
    && mv -f "$O/.RESULTADO-PARADA.tmp" "$O/RESULTADO-PARADA"
}
interrumpido() {
  log "muestreo interrumpido por una señal: parada=$PARADA_ESTADO intentos=$INTENTOS; NO consta una parada comprobada"
  escribir_resultado interrumpido 143 true
  exit 143
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
  GEN_VIVOS=0                                      # solo una lectura completa decide; un fallo lo resuelve el cierre
  if [ $rc = 0 ]; then case "$co" in *"target=inactive "*"procesos=0 "*) ;; *) GEN_VIVOS=1 ;; esac; fi
}

trap interrumpido TERM INT
echo "$$ $(date -u +%FT%TZ) inicio muestreo v$VERSION modo=$MODO fin=$FIN parada=$PARADA intentos_max=$MAX_INTENTOS" >> "$O/muestreo.pid"
while [ "$(date +%s)" -le "$FIN" ]; do
  muestra >> "$O/muestras.txt" 2>&1
  # La lectura va antes de cualquier intento de esta vuelta: se tomó después de la confirmación anterior.
  if [ "$PARADA_ESTADO" = confirmada ] && [ "$GEN_VIVOS" = 1 ]; then reabrir_parada "generadores vivos tras una parada confirmada"; fi
  g=$(python3 -I "$AQUI/guardia.py" "$O/muestras.txt"); echo "$g" >> "$O/guardia.jsonl"
  case "$g" in *'"parar": true'*) intentar_parada "guardia: $(python3 -c 'import json,sys;print("; ".join(json.loads(sys.argv[1])["motivos"])[:400])' "$g")";; esac
  if [ "$(date +%s)" -ge "$PARADA" ]; then intentar_parada "fin previsto (PARADA_EPOCH $PARADA)"
  elif [ -e "$O/PARADA-SOLICITADA" ] && [ "$PARADA_ESTADO" = ninguna ]; then intentar_parada "$(tail -1 "$O/PARADA-SOLICITADA" | cut -c1-300)"
  elif [ "$PARADA_ESTADO" = fallida ]; then intentar_parada "reintento"; fi
  sleep $(( INTERVALO - $(date +%s) % INTERVALO ))
done
if [ "$MODO" = real ]; then cerrar_parada; fi
echo "$(date -u +%FT%TZ) fin muestreo; parada=$PARADA_ESTADO intentos=$INTENTOS" >> "$O/muestreo.pid"
log "fin del muestreo: parada=$PARADA_ESTADO intentos=$INTENTOS"
trap - TERM INT
if [ "$MODO" = seco ]; then escribir_resultado seco_sin_orden 0 false; exit 0; fi
if [ "$PARADA_ESTADO" = confirmada ]; then escribir_resultado confirmada 0 false; exit 0; fi
escribir_resultado "$PARADA_ESTADO" 4 true
log "RESULTADO: parada NO confirmada; INTERVENCIÓN NECESARIA (ver RESULTADO-PARADA)"
exit 4
