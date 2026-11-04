#!/bin/bash
# Reversión específica del cierre complementario de la 4A (4-nov-2026). Una pieza por llamada:
#   [Sensor1]  sudo bash revertir_cierre4a.sh suricata  RESPALDO   # yaml previo (ruta del respaldo de la fase B)
#   [Sensor1]  sudo bash revertir_cierre4a.sh pcap                 # quita el drop-in del primer PCAP
#   [Sensor1]  sudo bash revertir_cierre4a.sh panel                # quita el drop-in --modo-panel v2 (el defecto sigue v2)
#   [Sensor1]  sudo bash revertir_cierre4a.sh publicador-v1        # vuelve a habilitar SOLO ppi-publicar-feed.timer
#   [Bastión]  sudo bash revertir_cierre4a.sh rele-v1              # vuelve a habilitar SOLO ppi-relay-feed.timer
# Ninguna pieza arranca ni habilita el agente v1 de srv-dmz (ppi-enforce-agent.timer, con --aplicar),
# ni carga restricciones de la demo, ni toca nftables. Nada se borra: los ficheros retirados se mueven
# a /root/cierre4a-revertido-<UTC>/.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "ejecutar con sudo"; exit 2; }
TS=$(date -u +%Y%m%dT%H%M%SZ); G=/root/cierre4a-revertido-$TS
case "${1:-}" in
  suricata)
    R="${2:?falta la ruta del respaldo /etc/suricata/suricata.yaml.respaldo-cierre4a-*}"
    [ "$(sha256sum "$R" | cut -d' ' -f1)" = 8e084b7dd9dbc9a1873ba479ce3861047a534742e0daf75c607d018c555efa04 ] \
      || { echo "el respaldo no tiene el hash medido; no se restaura"; exit 1; }
    mkdir -p "$G"; cp -a /etc/suricata/suricata.yaml "$G/suricata.yaml.ensayo"
    cp -a "$R" /etc/suricata/suricata.yaml
    set +e; suricata -T -c /etc/suricata/suricata.yaml > "$G/test.txt" 2>&1; RC=$?; set -e
    echo "rc_test=$RC"; [ "$RC" = 0 ] || { echo "PARADA: -T falló con el respaldo"; exit 1; }
    systemctl restart suricata.service; sleep 20; systemctl is-active suricata.service ;;
  pcap)
    mkdir -p "$G"; mv /etc/systemd/system/ppi-motor-capture.service.d/etapa4-primer-pcap.conf "$G/"
    systemctl daemon-reload; systemctl restart ppi-motor-capture.service; systemctl is-active ppi-motor-capture.service
    echo "OJO: vuelve el primer fichero ilegible en cada arranque de la captura" ;;
  panel)
    mkdir -p "$G"; mv /etc/systemd/system/ppi-dashboard.service.d/modo-panel-v2.conf "$G/"
    systemctl daemon-reload; systemctl restart ppi-dashboard.service; systemctl is-active ppi-dashboard.service ;;
  publicador-v1)
    systemctl enable --now ppi-publicar-feed.timer; systemctl is-active ppi-publicar-feed.timer ;;
  rele-v1)
    systemctl enable --now ppi-relay-feed.timer; systemctl is-active ppi-relay-feed.timer ;;
  *) echo "uso: $0 suricata RESPALDO|pcap|panel|publicador-v1|rele-v1"; exit 2 ;;
esac
echo "revertido ${1} $(date -u +%FT%TZ)"
