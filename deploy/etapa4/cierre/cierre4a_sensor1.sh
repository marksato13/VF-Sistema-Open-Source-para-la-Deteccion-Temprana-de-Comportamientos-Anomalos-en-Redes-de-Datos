#!/bin/bash
# Cierre complementario de la 4A en Sensor1 (4-nov-2026). Lo ejecuta Mark con sudo:
#   sudo bash /home/m4rk/cf-e4/cierre4a/herr/cierre4a_sensor1.sh A   # respaldo + v1 off + PCAP + panel v2
#   sudo bash /home/m4rk/cf-e4/cierre4a/herr/cierre4a_sensor1.sh B   # ensayo del anillo de Suricata
# No pide ni guarda contraseñas. No toca el motor (ppi-motor), ni el modelo, ni umbrales, ni nftables.
# Cada fase deja su evidencia en /home/m4rk/cf-e4/cierre4a/sudo-<fase>-<UTC>/ con SHA256SUMS.
# Se detiene en el primer fallo (set -e) salvo donde el código de salida se captura a propósito.
set -euo pipefail
FASE="${1:-}"
H=/home/m4rk/cf-e4/cierre4a/herr
TS=$(date -u +%Y%m%dT%H%M%SZ)
EV=/home/m4rk/cf-e4/cierre4a/sudo-$FASE-$TS
CAP=/var/lib/ppi-motor-capture
YAML=/etc/suricata/suricata.yaml
CAND=/etc/suricata/suricata.yaml.e4-ring-16384
[ "$(id -u)" = 0 ] || { echo "ejecutar con sudo"; exit 2; }
case "$FASE" in A|B) ;; *) echo "uso: $0 A|B"; exit 2;; esac
mkdir -p "$EV"
exec > >(tee "$EV/salida.txt") 2>&1
echo "== cierre4a fase $FASE  inicio $(date -u +%FT%TZ)  host $(hostname)"
cd "$H"
echo "== integridad de las herramientas"
sha256sum -c SHA256SUMS

anillo() {  # $1 PID: nº y bytes de los mapeos mmap de sockets (anillos AF_PACKET) — mawk no tiene strtonum
  python3 -c 'import sys
n=s=0
for l in open("/proc/%s/maps" % sys.argv[1]):
    if "socket:" in l:
        a, b = l.split()[0].split("-"); n += 1; s += int(b, 16) - int(a, 16)
print("mapeos_socket=%d bytes=%d MiB=%.1f" % (n, s, s / 2**20))' "$1"
}
guardar_unidad() {  # $1 unidad
  systemctl cat "$1" > "$EV/unidad-$1.txt" 2>&1 || true
  systemctl show "$1" -p ActiveState -p SubState -p UnitFileState -p MainPID -p ExecMainStartTimestamp \
     -p NRestarts -p Triggers -p TriggeredBy > "$EV/estado-antes-$1.txt" 2>&1 || true
}

if [ "$FASE" = A ]; then
  echo "== A0 respaldo previo"
  for u in ppi-publicar-feed.timer ppi-publicar-feed.service ppi-motor-capture.service ppi-dashboard.service \
           ppi-motor.service ppi-publicar-feed-v2.service ppi-via-rapida@ens37.service; do guardar_unidad "$u"; done
  systemctl list-timers --all --no-pager > "$EV/timers-antes.txt"
  ps -eo pid,user,lstart,args --sort=pid | grep -E 'publicar_feed|tcpdump|dashboard.py|motor|publicador' \
     | grep -v grep > "$EV/procesos-antes.txt" || true
  ls -la --time-style=full-iso "$CAP" > "$EV/pcap-dir-antes.txt"
  stat -c '%n %U:%G %a %s %y' /home/m4rk/feed/feed.json > "$EV/feed-v1-antes.txt" 2>&1 || true
  mkdir -p "$EV/etc"
  cp -a /etc/systemd/system/ppi-motor-capture.service.d "$EV/etc/" 2>/dev/null || true
  cp -a /etc/systemd/system/ppi-publicar-feed.* "$EV/etc/" 2>/dev/null || true
  nft list ruleset > "$EV/nft-antes.txt"; sha256sum "$EV/nft-antes.txt"

  echo "== A1 retirar la publicación v1 (solo el temporizador y su servicio; ficheros y feed se conservan)"
  systemctl disable --now ppi-publicar-feed.timer
  systemctl stop ppi-publicar-feed.service || true
  systemctl show ppi-publicar-feed.timer ppi-publicar-feed.service -p Id -p ActiveState -p UnitFileState \
     > "$EV/estado-despues-v1.txt"
  cat "$EV/estado-despues-v1.txt"

  echo "== A2 instalar la corrección del primer PCAP"
  install -o root -g root -m 0755 "$H/cf-primer-pcap.sh" /usr/local/sbin/cf-primer-pcap
  install -o root -g root -m 0644 "$H/etapa4-primer-pcap.conf" \
     /etc/systemd/system/ppi-motor-capture.service.d/etapa4-primer-pcap.conf
  echo "== A3 fijar el modo v2 del panel"
  install -d -o root -g root -m 0755 /etc/systemd/system/ppi-dashboard.service.d
  install -o root -g root -m 0644 "$H/modo-panel-v2.conf" /etc/systemd/system/ppi-dashboard.service.d/modo-panel-v2.conf
  sha256sum /usr/local/sbin/cf-primer-pcap /etc/systemd/system/ppi-motor-capture.service.d/etapa4-primer-pcap.conf \
     /etc/systemd/system/ppi-dashboard.service.d/modo-panel-v2.conf | tee "$EV/instalados.sha256"
  systemctl daemon-reload
  systemd-analyze verify ppi-motor-capture.service ppi-dashboard.service > "$EV/verify.txt" 2>&1 || true
  cat "$EV/verify.txt"

  echo "== A4 arranque controlado de la captura (el motor NO se reinicia)"
  date -u +%s.%N > "$EV/t-restart-captura.txt"
  systemctl restart ppi-motor-capture.service
  sleep 3
  systemctl is-active ppi-motor-capture.service
  journalctl --no-pager -o short-iso-precise -u ppi-motor-capture --since "@$(cut -d. -f1 "$EV/t-restart-captura.txt")" \
     > "$EV/journal-captura-arranque.txt"
  grep -E 'primer_pcap' "$EV/journal-captura-arranque.txt" || echo "AVISO: sin línea primer_pcap en el journal"
  ls -la --time-style=full-iso "$CAP" | tail -n 6 | tee "$EV/pcap-dir-despues.txt"
  echo "== A5 reiniciar el panel con el drop-in"
  systemctl restart ppi-dashboard.service
  sleep 4
  systemctl is-active ppi-dashboard.service
  tr '\0' ' ' < "/proc/$(systemctl show -p MainPID --value ppi-dashboard.service)/cmdline" > "$EV/cmdline-panel.txt"
  grep -o -- '--modo-panel v2' "$EV/cmdline-panel.txt"
  nft list ruleset > "$EV/nft-despues.txt"
  cmp -s "$EV/nft-antes.txt" "$EV/nft-despues.txt" && echo "ruleset sin cambios" || { echo "ERROR: ruleset cambió"; exit 1; }
fi

if [ "$FASE" = B ]; then
  echo "== B0 estado y respaldo previo de Suricata"
  suricata -V | tee "$EV/version.txt"
  PID=$(systemctl show -p MainPID --value suricata.service)
  echo "PID $PID"
  systemctl show suricata.service -p ActiveState -p MainPID -p ExecMainStartTimestamp -p NRestarts > "$EV/estado-antes.txt"
  cp -a "$YAML" "$EV/suricata.yaml.antes"
  cp -a "$YAML" "/etc/suricata/suricata.yaml.respaldo-cierre4a-$TS"
  sha256sum "$YAML" "$EV/suricata.yaml.antes" "/etc/suricata/suricata.yaml.respaldo-cierre4a-$TS" | tee "$EV/yaml.sha256"
  E=8e084b7dd9dbc9a1873ba479ce3861047a534742e0daf75c607d018c555efa04
  [ "$(sha256sum "$YAML" | cut -d' ' -f1)" = "$E" ] || { echo "PARADA: suricata.yaml no es el medido ($E)"; exit 1; }
  grep -E '^Date:|capture.kernel_(packets|drops)' /var/log/suricata/stats.log | tail -n 3 > "$EV/contadores-antes.txt"
  cat "$EV/contadores-antes.txt"
  echo "== B1 anillo real ANTES (mapeos mmap de los sockets AF_PACKET)"
  anillo "$PID" | tee "$EV/anillo-antes.txt"
  grep socket: "/proc/$PID/maps" > "$EV/maps-socket-antes.txt" || true
  if grep -q 'mapeos_socket=0 ' "$EV/anillo-antes.txt"; then
     echo "PARADA: Suricata no usa anillo mmap: ring-size no aplicaría. No se cambia nada."; exit 1
  fi
  echo "== B2 candidato: SOLO ring-size: 16384 en el bloque de ens37"
  N=$(grep -c '^  - interface: ens37$' "$YAML")
  [ "$N" = 1 ] || { echo "PARADA: esperaba 1 bloque ens37, hay $N"; exit 1; }
  awk '{print} /^  - interface: ens37$/ && !h {print "    ring-size: 16384   # cierre 4A 4-nov-2026: único cambio del ensayo"; h=1}' \
     "$YAML" > "$CAND"
  chown --reference="$YAML" "$CAND"; chmod --reference="$YAML" "$CAND"
  set +e; diff "$YAML" "$CAND" > "$EV/diff.txt"; set -e
  cat "$EV/diff.txt"
  [ "$(grep -c '^[<>]' "$EV/diff.txt")" = 1 ] || { echo "PARADA: el diff no es de una sola línea"; exit 1; }
  suricata --dump-config -c "$CAND" 2>/dev/null > "$EV/dump-candidato.txt" || true
  grep -E '^af-packet\.0\.' "$EV/dump-candidato.txt"
  grep -q '^af-packet.0.ring-size = 16384$' "$EV/dump-candidato.txt" || { echo "PARADA: ring-size no queda en af-packet.0"; exit 1; }
  echo "== B3 suricata -T del candidato (código de salida real, sin tubería)"
  set +e; suricata -T -c "$CAND" -v > "$EV/test-candidato.txt" 2>&1; RC=$?; set -e
  echo "rc_test_candidato=$RC" | tee -a "$EV/rc.txt"
  tail -n 5 "$EV/test-candidato.txt"
  [ "$RC" = 0 ] || { echo "PARADA: -T falló; no se instala nada"; exit 1; }
  echo "== B4 instalar y volver a probar la ruta real"
  cp -a "$CAND" "$YAML"
  set +e; suricata -T -c "$YAML" -v > "$EV/test-instalado.txt" 2>&1; RC=$?; set -e
  echo "rc_test_instalado=$RC" | tee -a "$EV/rc.txt"
  if [ "$RC" != 0 ]; then
     cp -a "$EV/suricata.yaml.antes" "$YAML"; echo "PARADA: -T falló en la ruta real; respaldo restaurado"; exit 1
  fi
  sha256sum "$YAML" | tee "$EV/yaml-instalado.sha256"
  echo "== B5 reinicio de Suricata"
  date -u +%s.%N > "$EV/t-restart-suricata.txt"
  systemctl restart suricata.service
  for i in $(seq 1 60); do
     grep -q 'Engine started' <(journalctl --no-pager -u suricata --since "@$(cut -d. -f1 "$EV/t-restart-suricata.txt")") \
       && break
     tail -n 50 /var/log/suricata/suricata.log | grep -q 'Engine started' && break
     sleep 2
  done
  systemctl is-active suricata.service
  sleep 15
  PID2=$(systemctl show -p MainPID --value suricata.service)
  echo "PID nuevo $PID2"
  anillo "$PID2" | tee "$EV/anillo-despues.txt"
  grep socket: "/proc/$PID2/maps" > "$EV/maps-socket-despues.txt" || true
  grep -iE 'ring|af-packet|AFP|error|warn' /var/log/suricata/suricata.log | tail -n 40 > "$EV/suricata-log-arranque.txt" || true
  cat "$EV/suricata-log-arranque.txt"
  systemctl show suricata.service -p ActiveState -p MainPID -p ExecMainStartTimestamp -p NRestarts > "$EV/estado-despues.txt"
  grep MemAvailable /proc/meminfo | tee "$EV/memoria-despues.txt"
fi

chown -R m4rk:m4rk "$EV"
( cd "$EV" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "== fin fase $FASE $(date -u +%FT%TZ)  evidencia en $EV"
