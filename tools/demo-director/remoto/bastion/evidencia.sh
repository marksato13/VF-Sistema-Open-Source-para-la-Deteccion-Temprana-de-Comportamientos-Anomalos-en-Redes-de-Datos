#!/bin/bash
# CyberFlow - evidencia por fase de la demo. SOLO LECTURA: no cambia nada en ningun host.
# Uso (en el bastion):  bash ~/cf-stage/evidencia.sh <fase> [IP] [minutos]
#   datos            F1  servicios del sensor y edad del ultimo dato
#   ip    <IP> [m]   F3/F4  decisiones de esa IP en los ultimos m minutos (def. 5)
#   feed  [IP]       F5  feed firmado en el sensor y copia del rele (bastion)
#   host  [IP]       F6  agente y reglas nftables en srv-dmz
#   todo  <IP> [m]   las cuatro seguidas
set -uo pipefail
FASE=${1:-}; IP=${2:-10.10.20.30}; MIN=${3:-5}
export TZ=America/Lima
hora() { date +"%H:%M:%S"; }
titulo() { printf "\n\033[1m== %s  (%s, hora Lima)\033[0m\n" "$1" "$(hora)"; }

datos() {
  titulo "F1 - Llegan datos? (Sensor1)"
  timeout 20 ssh -o BatchMode=yes sensor1 'export TZ=America/Lima;
    for u in ppi-motor-capture suricata ppi-motor ppi-publicar-feed.timer ppi-dashboard; do
      printf "  %-24s %s\n" "$u" "$(systemctl is-active $u)"; done
    L=~/cyberflow/logs/motor_decision.log
    ult=$(tail -n 1 $L | jq -r .logged_at)
    ahora=$(date +%s)
    echo "  ultima decision del motor : hace $(( ahora - ${ult%.*} )) s"
    echo "  decisiones en el ultimo min: $(tail -n 3000 $L | jq -r --argjson t $((ahora-60)) "select(.logged_at>\$t)|.entity_ip" | wc -l)"
    echo "  IPs vistas en el ultimo min: $(tail -n 3000 $L | jq -r --argjson t $((ahora-60)) "select(.logged_at>\$t)|.entity_ip" | sort -u | tr "\n" " ")"'
}

ip_dec() {
  titulo "F3/F4 - Decisiones de $IP (ultimos $MIN min)"
  timeout 20 ssh -o BatchMode=yes sensor1 "export TZ=America/Lima;
    desde=\$(( \$(date +%s) - $MIN*60 ))
    tail -n 20000 ~/cyberflow/logs/motor_decision.log | jq -r --arg ip '$IP' --argjson d \$desde '
      select(.entity_ip==\$ip and .logged_at>\$d)
      | [ (.logged_at|localtime|strftime(\"%H:%M:%S\")),
          .decision,
          (if .score then \"score \"+(.score*1000|round/1000|tostring)+\" / umbral \"+(.threshold*1000|round/1000|tostring) else \"sin score (ventana sin modelo)\" end),
          (if .heuristico then \"REGLA \"+.heuristico.heuristico+\" -> \"+.heuristico.accion+\" (\"+.heuristico.motivo+\")\" else \"sin regla\" end)
        ] | @tsv' | tail -n 15 | sed 's/^/  /'
    echo '  (decision ALERT = el modelo la ve anomala; REGLA = heuristico que pide la accion)'"
}

feed() {
  titulo "F5 - Publicacion: feed firmado"
  timeout 20 ssh -o BatchMode=yes sensor1 "export TZ=America/Lima;
    f=~/feed/feed.json
    echo \"  sensor: feed.json generado a las \$(jq -r '.generado|localtime|strftime(\"%H:%M:%S\")' \$f), firma feed.sig de \$(stat -c %s ~/feed/feed.sig) bytes\"
    jq -r '.entradas[] | \"  \"+.ip+\"  \"+.accion+\"  \"+.motivo+\"  hasta \"+(.hasta|localtime|strftime(\"%H:%M:%S\"))+\"  nivel \"+(.nivel|tostring)' \$f
    jq -e --arg ip '$IP' '.entradas[]|select(.ip==\$ip)' \$f >/dev/null && echo \"  >> $IP ESTA en el feed\" || echo \"  >> $IP no esta en el feed ahora\""
  echo "  rele (bastion): copia de las $(TZ=America/Lima date -r ~/relay/feed.json +%H:%M:%S), $(python3 -c "import json;print(len(json.load(open('/home/gadmin/relay/feed.json'))['entradas']))") entradas"
}

host() {
  titulo "F6 - Aplicacion en srv-dmz (10.10.30.10)"
  timeout 20 ssh -o BatchMode=yes srvdmz "export TZ=America/Lima;
    echo \"  agente (timer): \$(systemctl is-active ppi-enforce-agent.timer) / \$(systemctl is-enabled ppi-enforce-agent.timer)\"
    echo \"  feed recibido del rele: \$(TZ=America/Lima date -r ~/enforce/feed.json +%H:%M:%S)\"
    echo '  ultima ejecucion del agente:'
    journalctl -u ppi-enforce-agent -n 40 --no-pager -o short-iso 2>/dev/null | grep -E 'estado|firma|error' | tail -n 2 | cut -c1-220 | sed 's/^/    /'
    echo '  reglas nftables (tabla inet cyberflow):'
    if sudo -n /usr/local/sbin/cf-nft-mostrar >/dev/null 2>&1; then sudo -n /usr/local/sbin/cf-nft-mostrar | jq -c '.nftables[] | select(.set) | .set | {set: .name, elementos: (.elem // [])}' | cut -c1-300 | sed 's/^/    /'; else echo '    (no existe la tabla cyberflow: el agente no ha aplicado nada)'; fi
    sudo -n /usr/local/sbin/cf-nft-mostrar 2>/dev/null | grep -q '\"$IP\"' && echo '  >> $IP TIENE regla aplicada' || echo '  >> $IP sin regla en el host'"
}

case "$FASE" in
  datos) datos ;;
  ip)    ip_dec ;;
  feed)  feed ;;
  host)  host ;;
  todo)  datos; ip_dec; feed; host ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
