#!/usr/bin/env bash
# [BASTIÓN gadmin] P4 (2026-11-06): relé v2 con --entrega paquete. Lo ejecuta MARK (sudo CON contraseña; nunca se
# guarda ni se pide por escrito). Requiere la fase A de srv-dmz hecha (cf-feed-ssh.sh admite el paquete).
#   bash bastion_p4.sh instalar <PAQ>          respaldo (sellado) + relé nuevo + unidad con --entrega paquete
#   bash bastion_p4.sh revertir <RESPALDO>     relé y unidad del respaldo (entrega por pareja)
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../comun/evidencia.sh
source "$AQUI/../comun/evidencia.sh"
parar() { echo "PARADA $*"; ev_sellar "$EV" >/dev/null 2>&1; exit 1; }
ok() { echo "OK    $*"; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
U=ppi-relay-eventos; UF=/etc/systemd/system/$U.service; T="$HOME/relay-v2/traza.jsonl"
FICH=(/opt/cyberflow/relay-v2/relay_eventos.py /opt/cyberflow/relay-v2/feed.py /opt/cyberflow/relay-v2/pub.pem "$UF")
entrega_reciente() {  # una entrega a srv-dmz con la marca de modo esperada después de $1
  for _ in $(seq 1 30); do
    n=$(tail -40 "$T" | tr -d '\000' | python3 -c '
import json,sys
d,m=float(sys.argv[1]),sys.argv[2]; n=0
for l in sys.stdin:
    try: r=json.loads(l)
    except ValueError: continue
    e=(r.get("destinos") or {}).get("srv-dmz") or {}
    if e.get("entregado_en",0)>d and r.get("entrega","pareja")==m: n+=1
print(n)' "$1" "$2")
    [ "${n:-0}" -gt 0 ] && { ok "relé entrega en modo $2 ($n entregas)"; return 0; }
    sleep 2
  done
  parar "sin entregas en modo $2 en 60 s"
}
case "${1:-}" in
instalar)
  P="${2:?paquete}"; R="$HOME/respaldos-etapa4/bastion-p4-$TS"; EV="$R"
  ev_abrir "$R"
  ( cd "$P" && sha256sum -c --quiet SHA256SUMS ) || parar "el paquete no verifica"
  systemctl is-active --quiet $U || parar "el relé v2 no está activo"
  for f in "${FICH[@]}"; do cp -a "$f" "$R/" || parar "no se copia $f"; done
  sha256sum "${FICH[@]}" | tee "$R/instalados-antes.sha256"
  systemctl is-enabled ppi-relay-feed.timer > "$R/v1-antes.txt" 2>&1; systemctl is-active ppi-relay-feed.timer >> "$R/v1-antes.txt" 2>&1
  # el forzado de srv-dmz debe admitir ya el paquete (fase A): un .tmp vacío no es visible para el agente
  ssh -n -o BatchMode=yes -i "$HOME/.ssh/cyberflow-feed-v2-srv" cffeed@10.10.30.10 "cat > /var/lib/cyberflow/feed/.feed.par.tmp" \
    || parar "srv-dmz no admite el paquete: falta la fase A (srvdmz_p4.sh fase-a)"
  sudo install -o root -g root -m 0644 "$P/deploy/enforcement/relay_eventos.py" "$P/scripts/engine/feed.py" /opt/cyberflow/relay-v2/
  sudo install -o root -g root -m 0644 "$P/deploy/etapa4/unidades/bastion/$U.service" "$UF"
  grep -v '^[[:space:]]*#' "$UF" | grep -q -- '--entrega paquete' || parar "la unidad no lleva --entrega paquete"
  grep -q 'dc1=' "$UF" && parar "la unidad lleva destino dc1"
  sudo systemctl daemon-reload
  systemd-analyze verify $U.service 2>&1 | grep . && parar "systemd-analyze verify"
  t=$(date +%s.%N); sudo systemctl restart $U; sleep 3
  systemctl is-active --quiet $U || parar "el relé no arranca"
  entrega_reciente "$t" paquete
  sha256sum "${FICH[@]}" | tee "$R/instalados.sha256"
  systemctl is-enabled ppi-relay-feed.timer > "$R/v1-despues.txt" 2>&1; systemctl is-active ppi-relay-feed.timer >> "$R/v1-despues.txt" 2>&1
  diff -q "$R/v1-antes.txt" "$R/v1-despues.txt" > /dev/null || parar "cambió el estado del relé v1"
  ok "relé en modo paquete. RESPALDO=$R  (siguiente: srvdmz_p4.sh fase-c, lo ejecuta Claude)"
  ev_sellar "$R" ;;
revertir)
  R="${2:?respaldo}"; EV="$R-revertir-$TS"
  ( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
  ev_abrir "$EV"
  sudo install -o root -g root -m 0644 "$R/relay_eventos.py" "$R/feed.py" /opt/cyberflow/relay-v2/
  sudo install -o root -g root -m 0644 "$R/$U.service" "$UF"
  sudo systemctl daemon-reload; t=$(date +%s.%N); sudo systemctl restart $U; sleep 3
  sha256sum "${FICH[@]}" > "$EV/instalados.sha256"
  diff <(awk '{print $1}' "$R/instalados-antes.sha256") <(awk '{print $1}' "$EV/instalados.sha256") \
    && ok "hashes iguales al respaldo" || parar "los hashes no coinciden"
  entrega_reciente "$t" pareja
  echo "NOTA: después, srvdmz_p4.sh revertir (el agente vuelve a feed.json/feed.sig)"
  ev_sellar "$EV" ;;
*) echo "uso: bastion_p4.sh instalar PAQ | revertir RESPALDO"; exit 2 ;;
esac
