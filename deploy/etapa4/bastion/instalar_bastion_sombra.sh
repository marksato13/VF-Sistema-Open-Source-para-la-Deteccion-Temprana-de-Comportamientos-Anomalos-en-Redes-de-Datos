#!/usr/bin/env bash
# [BASTIÓN gadmin] Relé v2 por eventos (Sensor1 -> srv-dmz), Etapa 4 en SOMBRA. Lo ejecuta MARK (sudo
# con contraseña: /opt y /etc/systemd). El relé v1 (ppi-relay-feed.timer) NO se toca. DC1 NO se incluye.
#
#   bash instalar_bastion_sombra.sh llaves                      # fase 1 (sin sudo): genera las 2 llaves
#   bash instalar_bastion_sombra.sh instalar <RESPALDO_DIR> <DST_PAQUETE> <pub.pem del sensor>
#                                                               # fase 2 (sudo), después de que Sensor1
#                                                               # (llave-rele) y srv-dmz (cffeed) acepten
# Paradas: "PARADA <motivo>". Resultado esperado: "OK ..." y entregas en ~/relay-v2/traza.jsonl.
set -uo pipefail
parar() { echo "PARADA $*"; exit 1; }
ok() { echo "OK    $*"; }
K="$HOME/.ssh"
case "${1:-}" in
llaves)
  for n in cyberflow-feed-v2-sensor cyberflow-feed-v2-srv; do
    [ -e "$K/$n" ] && parar "$K/$n ya existe"
    ssh-keygen -q -t ed25519 -N '' -C "$n" -f "$K/$n" || parar "ssh-keygen $n"
    ssh-keygen -lf "$K/$n.pub"
  done
  ok "llaves nuevas; la PÚBLICA cyberflow-feed-v2-sensor.pub va a Sensor1 (instalar_sensor1_sombra.sh llave-rele)"
  ok "y la PÚBLICA cyberflow-feed-v2-srv.pub a srv-dmz (instalar_srvdmz_sombra.sh ... <pub>)"
  ;;
instalar)
  R="${2:?respaldo}"; DST="${3:?directorio del paquete extraído}"; PUB="${4:?pub.pem del sensor}"
  ( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || parar "el respaldo no verifica"
  ( cd "$DST" && sha256sum -c --quiet SHA256SUMS ) || parar "el paquete no verifica"
  [ -f "$K/cyberflow-feed-v2-sensor" ] && [ -f "$K/cyberflow-feed-v2-srv" ] || parar "faltan las llaves (fase llaves)"
  # El acceso con las llaves nuevas debe estar ya limitado por el comando forzado en ambos extremos:
  # una orden cualquiera tiene que ser rechazada.
  # >>> comprobacion-llaves-limitadas (banco: ensayo_comprobaciones_4a.sh)
  # 4A (2026-11-04): el comando forzado rechaza con rc=1 y, con pipefail, «ssh … | grep -q» paraba siempre.
  rs=$(ssh -n -o BatchMode=yes -i "$K/cyberflow-feed-v2-sensor" m4rk@10.10.60.11 id 2>&1) || true
  printf '%s\n' "$rs" | grep -q 'orden no permitida' && ! printf '%s\n' "$rs" | grep -q 'uid=' \
    || parar "Sensor1 no limita la llave del relé (falta la línea command=... en authorized_keys): $rs"
  rd=$(ssh -n -o BatchMode=yes -i "$K/cyberflow-feed-v2-srv" cffeed@10.10.30.10 id 2>&1) || true
  printf '%s\n' "$rd" | grep -q 'orden no permitida' && ! printf '%s\n' "$rd" | grep -q 'uid=' \
    || parar "srv-dmz no limita la llave del relé (cffeed sin command=...): $rd"
  # <<< comprobacion-llaves-limitadas
  ssh -o BatchMode=yes -i "$K/cyberflow-feed-v2-sensor" m4rk@10.10.60.11 "cat /home/m4rk/feed-v2/feed.json" > /dev/null \
    || parar "el relé no puede leer el feed v2 del sensor"
  sudo install -d -o root -g root -m 0755 /opt/cyberflow /opt/cyberflow/relay-v2
  sudo install -o root -g root -m 0644 "$DST/deploy/enforcement/relay_eventos.py" "$DST/scripts/engine/feed.py" /opt/cyberflow/relay-v2/
  sudo install -o root -g root -m 0644 "$PUB" /opt/cyberflow/relay-v2/pub.pem
  install -d -m 0700 "$HOME/relay-v2"
  sudo install -o root -g root -m 0644 "$DST/deploy/etapa4/unidades/bastion/ppi-relay-eventos.service" /etc/systemd/system/
  sudo systemctl daemon-reload
  systemd-analyze verify ppi-relay-eventos.service 2>&1 | grep . && parar "systemd-analyze verify"
  sudo systemctl enable --now ppi-relay-eventos.service
  sleep 10
  systemctl is-active --quiet ppi-relay-eventos || parar "el relé v2 no está activo"
  systemctl is-active --quiet ppi-relay-feed.timer || parar "el relé v1 dejó de estar activo (no debía tocarse)"
  tail -3 "$HOME/relay-v2/traza.jsonl"
  grep -q '"entregado_en"' "$HOME/relay-v2/traza.jsonl" || parar "sin entregas en la traza"
  ok "relé v2 entregando a srv-dmz; relé v1 intacto"
  ;;
*) echo "uso: instalar_bastion_sombra.sh llaves | instalar <RESPALDO_DIR> <DST_PAQUETE> <pub.pem>"; exit 2;;
esac
