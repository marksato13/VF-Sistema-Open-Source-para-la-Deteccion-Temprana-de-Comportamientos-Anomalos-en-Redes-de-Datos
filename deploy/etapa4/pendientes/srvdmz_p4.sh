#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] P4 (2026-11-06): entrega coherente feed+firma (paquete feed.par) en SOMBRA. sudo -n (NOPASSWD).
# Nunca --aplicar; el ruleset debe seguir igual (vacío) antes y después. Fases:
#   bash srvdmz_p4.sh respaldo                      -> ~/respaldos-etapa4/srvdmz-p4-<UTC>/ (sellado)
#   bash srvdmz_p4.sh fase-a <PAQ> <RESPALDO>        cf-feed-ssh.sh (admite pareja Y paquete) + código nuevo del
#                                                    agente; la unidad sigue con --feed/--firma (compatibilidad)
#   bash srvdmz_p4.sh fase-c <PAQ> <RESPALDO>        unidad con --paquete (DESPUÉS de que el relé entregue paquete)
#   bash srvdmz_p4.sh revertir <RESPALDO>            ficheros y unidad del respaldo
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../comun/evidencia.sh
source "$AQUI/../comun/evidencia.sh"
parar() { echo "PARADA $*"; ev_sellar "$EV" >/dev/null 2>&1; exit 1; }
ok() { echo "OK    $*"; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
U=ppi-enforce-agent-v2-dmz
UF=/etc/systemd/system/$U.service
FICH=(/opt/cyberflow/agente-v2/agente_enforce_v2.py /opt/cyberflow/agente-v2/feed.py /opt/cyberflow/agente-v2/pub.pem
      /usr/local/bin/cf-feed-ssh.sh /usr/local/sbin/cf-nft-helper "$UF")
norm() { sed -E 's/counter packets [0-9]+ bytes [0-9]+/counter/; s/expires [0-9hms.]+//'; }
sombra() {  # sin --aplicar en la unidad ni en el proceso; tablas nft como en el respaldo
  ! grep -v '^[[:space:]]*#' "$UF" | grep -qE '(^|[[:space:]])--aplicar' || parar "la unidad lleva --aplicar"
  p=$(systemctl show -p MainPID --value $U); [ "$p" != 0 ] || parar "$U sin proceso"
  ! tr '\0' ' ' < /proc/$p/cmdline | grep -q -- '--aplicar' || parar "el proceso lleva --aplicar"
  diff <(sudo -n nft list ruleset | norm) <(norm < "$1/ruleset.nft") > /dev/null || parar "el ruleset cambió"
  ok "sombra: sin --aplicar y ruleset igual al del respaldo"
}
esperar_recepcion() {  # una recepción aceptada/repetida posterior al arranque
  local t0 desde=$1
  for _ in $(seq 1 30); do
    t0=$(sudo -n tail -50 /var/lib/cyberflow/agente/traza.jsonl | python3 -c '
import json,sys
d=float(sys.argv[1]); r=[json.loads(l) for l in sys.stdin if l.strip()]
print(sum(1 for x in r if x["evento"]=="recepcion" and x["t"]>d and x.get("estado") in ("aceptado","repetido")))' "$desde")
    [ "${t0:-0}" -gt 0 ] && { ok "agente recibe ($t0 recepciones válidas desde el arranque)"; return 0; }
    sleep 2
  done
  parar "el agente no recibe nada en 60 s"
}
case "${1:-}" in
respaldo)
  EV="$HOME/respaldos-etapa4/srvdmz-p4-$TS"; ev_abrir "$EV"
  for f in "${FICH[@]}"; do sudo -n cp -a "$f" "$EV/" || parar "no se copia $f"; done
  sudo -n cp -a /var/lib/cyberflow/agente/estado.json "$EV/estado.json"
  sudo -n cp -a /var/lib/cyberflow/agente/traza.jsonl "$EV/traza-agente-antes.jsonl"
  sudo -n chown "$(id -u):$(id -g)" "$EV"/*
  sudo -n nft list ruleset > "$EV/ruleset.nft"; echo "rc=$? $(date -u +%FT%TZ)" > "$EV/ruleset.lectura"
  for f in "${FICH[@]}"; do sudo -n sha256sum "$f"; done | tee "$EV/instalados-antes.sha256"
  systemctl show $U -p ActiveState -p MainPID -p NRestarts -p ExecMainStartTimestamp | tee "$EV/unidad-antes.txt"
  ok "respaldo en $EV"; ev_sellar "$EV" ;;
fase-a)
  P="${2:?paquete}"; R="${3:?respaldo}"; EV="$R/fase-a-$TS"
  ( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
  ev_abrir "$EV"
  ( cd "$P" && sha256sum -c --quiet SHA256SUMS ) || parar "el paquete no verifica"
  sombra "$R"
  sudo -n install -o root -g root -m 0755 "$P/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" /usr/local/bin/cf-feed-ssh.sh
  sudo -n install -o root -g root -m 0644 "$P/scripts/enforce/agente_enforce_v2.py" "$P/scripts/engine/feed.py" /opt/cyberflow/agente-v2/
  t=$(date +%s.%N); sudo -n systemctl restart $U; sleep 3
  systemctl is-active --quiet $U || parar "$U no arranca"
  esperar_recepcion "$t"; sombra "$R"
  for f in "${FICH[@]}"; do sudo -n sha256sum "$f"; done | tee "$EV/instalados.sha256"
  ok "fase A: forzado admite paquete; agente nuevo en modo pareja (siguiente: bastion_p4.sh instalar, lo ejecuta Mark)"
  ev_sellar "$EV" ;;
fase-c)
  P="${2:?paquete}"; R="${3:?respaldo}"; EV="$R/fase-c-$TS"
  ( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
  ev_abrir "$EV"
  ( cd "$P" && sha256sum -c --quiet SHA256SUMS ) || parar "el paquete no verifica"
  m=$(sudo -n stat -c %Y /var/lib/cyberflow/feed/feed.par 2>/dev/null) || parar "no hay feed.par: el relé aún no entrega paquete"
  [ $(( $(date +%s) - m )) -lt 60 ] || parar "feed.par no se actualiza (> 60 s)"
  sudo -n install -o root -g root -m 0644 "$P/deploy/etapa4/unidades/srvdmz/$U.service" "$UF"
  sombra "$R"
  sudo -n systemctl daemon-reload
  systemd-analyze verify $U.service 2>&1 | grep . && parar "systemd-analyze verify"
  t=$(date +%s.%N); sudo -n systemctl restart $U; sleep 3
  systemctl is-active --quiet $U || parar "$U no arranca"
  tr '\0' ' ' < /proc/$(systemctl show -p MainPID --value $U)/cmdline | grep -q -- '--paquete /var/lib/cyberflow/feed/feed.par' \
    || parar "el agente no lee feed.par"
  esperar_recepcion "$t"; sombra "$R"
  for f in "${FICH[@]}"; do sudo -n sha256sum "$f"; done | tee "$EV/instalados.sha256"
  ok "fase C: agente v2 lee el paquete; sombra mantenida"; ev_sellar "$EV" ;;
revertir)
  R="${2:?respaldo}"; EV="$R/revertir-$TS"
  ( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
  ev_abrir "$EV"
  sudo -n install -o root -g root -m 0755 "$R/cf-feed-ssh.sh" /usr/local/bin/cf-feed-ssh.sh
  sudo -n install -o root -g root -m 0644 "$R/agente_enforce_v2.py" "$R/feed.py" /opt/cyberflow/agente-v2/
  sudo -n install -o root -g root -m 0644 "$R/$U.service" "$UF"
  sudo -n systemctl daemon-reload; t=$(date +%s.%N); sudo -n systemctl restart $U; sleep 3
  for f in "${FICH[@]}"; do sudo -n sha256sum "$f"; done > "$EV/instalados.sha256"
  diff <(awk '{print $1}' "$R/instalados-antes.sha256") <(awk '{print $1}' "$EV/instalados.sha256") \
    && ok "hashes iguales a los del respaldo" || parar "los hashes no coinciden con el respaldo"
  echo "NOTA: si el relé sigue en modo paquete, revertir ANTES el bastión (bastion_p4.sh revertir) o el agente no recibe"
  esperar_recepcion "$t"; sombra "$R"; ok "reversión srv-dmz"; ev_sellar "$EV" ;;
*) echo "uso: srvdmz_p4.sh respaldo | fase-a PAQ R | fase-c PAQ R | revertir R"; exit 2 ;;
esac
