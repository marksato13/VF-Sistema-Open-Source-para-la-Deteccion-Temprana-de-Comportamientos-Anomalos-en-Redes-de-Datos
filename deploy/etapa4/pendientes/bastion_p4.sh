#!/usr/bin/env bash
# [BASTIÓN gadmin] P4: relé v2 con --entrega paquete, en SOMBRA. Lo ejecuta MARK (sudo CON contraseña: la pide sudo
# en la terminal; nunca se escribe ni se guarda). VERSION p4-instalador 2026-11-06.2 (ver p4_comun.sh).
# Requiere la fase A de srv-dmz hecha (cf-feed-ssh.sh admite el paquete).
#
#   bash bastion_p4.sh instalar <PAQ>        respaldo inmutable -> instalación -> verificación; reversión automática
#                                            si algo falla tras el primer cambio
#   bash bastion_p4.sh revertir <RESPALDO>   reversión MANUAL al respaldo indicado (entrega por pareja)
#
# Códigos: 0 OK · 10 parada sin cambios · 20 revertido automáticamente (verificado) · 30 reversión fallida (manual).
# Respaldo: ~/respaldos-etapa4/bastion-p4-<UTC>/ (solo lectura). Evidencia: ~/evidencia-etapa4/bastion-p4-<UTC>/.
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
source "$AQUI/../comun/evidencia.sh"
source "$AQUI/p4_comun.sh"
p4_entorno sudo
TS=$(date -u +%Y%m%dT%H%M%SZ)
U=ppi-relay-eventos
UF="$RAIZ/etc/systemd/system/$U.service"
OPT="$RAIZ/opt/cyberflow/relay-v2"
T="$HOME/relay-v2/traza.jsonl"
FICH=("$OPT/relay_eventos.py" "$OPT/feed.py" "$OPT/pub.pem" "$UF")
P4_FASE_SIGUIENTE="la fase C de srv-dmz"

entrega_reciente() {  # al menos una entrega a srv-dmz en el modo $2 posterior a $1 (60 s máximo)
  local n
  for _ in $(seq 1 30); do
    n=$(tail -40 "$T" 2>/dev/null | tr -d '\000' | python3 -c '
import json,sys
d,m=float(sys.argv[1]),sys.argv[2]; n=0
for l in sys.stdin:
    try: r=json.loads(l)
    except ValueError: continue
    e=(r.get("destinos") or {}).get("srv-dmz") or {}
    if e.get("entregado_en",0)>d and r.get("entrega","pareja")==m: n+=1
print(n)' "$1" "$2") || return 1
    [ "${n:-0}" -gt 0 ] && { echo "entregas en modo $2: $n"; return 0; }
    sleep "${CF_ESPERA:-2}"
  done
  echo "sin entregas en modo $2"; return 1
}
v1_estado() { echo "$($SYSTEMCTL is-enabled ppi-relay-feed.timer 2>&1) $($SYSTEMCTL is-active ppi-relay-feed.timer 2>&1)"; }
unidad_ok() {  # contenido de la unidad: paquete, sin dc1
  grep -v '^[[:space:]]*#' "$1" | grep -q -- '--entrega paquete' || { echo "sin --entrega paquete"; return 1; }
  ! grep -q 'dc1=' "$1" || { echo "lleva destino dc1"; return 1; }
}
proceso_paquete() { local c; c=$(p4_cmdline "$U") || return 1; [[ "$c" == *"--entrega paquete"* ]]; }
reiniciar() { T_REINICIO=$(date +%s.%N); $SUDO systemctl restart "$U" && sleep "${CF_ESPERA:-3}"; }

p4_revertir_desde() {  # automática (desde p4_fallo) o manual (orden revertir). Usa rpaso: anota fallos.
  local r="$1" f t
  rpaso "respaldo íntegro antes de revertir" p4_verificar_respaldo "$r" || return 1
  for f in "${FICH[@]}"; do rpaso "restaurar $f" p4_restaurar "$f" "$r"; done
  rpaso "daemon-reload (reversión)" $SUDO systemctl daemon-reload
  t=$(date +%s.%N)
  rpaso "reiniciar $U (reversión)" $SUDO systemctl restart "$U"
  sleep "${CF_ESPERA:-3}"
  rpaso "$U activo (reversión)" p4_activa "$U"
  rpaso "hashes = respaldo" p4_hashes_iguales "$r/instalados-antes.sha256" "${FICH[@]}"
  rpaso "entrega por pareja tras revertir" entrega_reciente "$t" pareja
}

case "${1:-}" in
instalar)
  P="${2:?paquete}"
  R="$HOME/respaldos-etapa4/bastion-p4-$TS"; E="$HOME/evidencia-etapa4/bastion-p4-$TS"
  mkdir -p "$(dirname "$R")" "$(dirname "$E")"
  ev_abrir "$E"
  echo "$P4_VERSION · bastion_p4.sh instalar · paquete $P · respaldo $R · evidencia $E"
  # --- comprobaciones previas (ningún cambio)
  paso "paquete verifica" bash -c "cd '$P' && sha256sum -c --quiet SHA256SUMS"
  paso "relé v2 activo" p4_activa "$U"
  v1_antes=$(v1_estado); echo "relé v1 antes: $v1_antes"
  paso "unidad nueva: --entrega paquete y sin dc1" unidad_ok "$P/deploy/etapa4/unidades/bastion/$U.service"
  paso "systemd-analyze verify de la unidad NUEVA (antes de instalarla)" \
    p4_verify_unidad "$P/deploy/etapa4/unidades/bastion/$U.service"
  paso "srv-dmz admite el paquete (fase A hecha)" $SSH -n -o BatchMode=yes -i "$HOME/.ssh/cyberflow-feed-v2-srv" \
    cffeed@10.10.30.10 "cat > /var/lib/cyberflow/feed/.feed.par.tmp"
  p4_respaldo "$R" "${FICH[@]}"
  # --- cambios
  cambio
  paso "instalar relay_eventos.py y feed.py" $SUDO install -o root -g root -m 0644 \
    "$P/deploy/enforcement/relay_eventos.py" "$P/scripts/engine/feed.py" "$OPT/"
  paso "instalar la unidad" $SUDO install -o root -g root -m 0644 "$P/deploy/etapa4/unidades/bastion/$U.service" "$UF"
  paso "daemon-reload" $SUDO systemctl daemon-reload
  paso "systemd-analyze verify de la unidad instalada" p4_verify_unidad "$U.service"
  paso "reiniciar $U" reiniciar
  paso "$U activo" p4_activa "$U"
  paso "proceso con --entrega paquete" proceso_paquete
  paso "entrega a srv-dmz en modo paquete" entrega_reciente "$T_REINICIO" paquete
  paso "hashes instalados = paquete" p4_hashes_paquete \
    "$P/deploy/enforcement/relay_eventos.py" "$OPT/relay_eventos.py" "$P/scripts/engine/feed.py" "$OPT/feed.py" \
    "$P/deploy/etapa4/unidades/bastion/$U.service" "$UF"
  paso "relé v1 sin cambios" test "$(v1_estado)" = "$v1_antes"
  $SUDO sha256sum "${FICH[@]}" > "$E/instalados.sha256"
  echo "RESULTADO: OK — relé en modo paquete. RESPALDO=$R EVIDENCIA=$E"
  echo "Siguiente (Claude): srvdmz_p4.sh fase-c"
  ev_sellar "$E"; exit 0 ;;
revertir)
  R="${2:?respaldo}"; E="$HOME/evidencia-etapa4/bastion-p4-revertir-$TS"; mkdir -p "$(dirname "$E")"
  ev_abrir "$E"
  echo "$P4_VERSION · bastion_p4.sh revertir (MANUAL) · respaldo $R"
  P4_REV_FALLOS=()
  p4_revertir_desde "$R"
  if [ "${#P4_REV_FALLOS[@]}" -eq 0 ]; then
    echo "RESULTADO: REVERSIÓN MANUAL OK — relé en modo pareja (después: srvdmz_p4.sh revertir para el agente)"
    ev_sellar "$E"; exit 0
  fi
  echo "RESULTADO: REVERSIÓN MANUAL FALLIDA en: ${P4_REV_FALLOS[*]} — DETENIDO, revisar a mano"; ev_sellar "$E"; exit 30 ;;
*) echo "uso: bastion_p4.sh instalar PAQ | revertir RESPALDO"; exit 2 ;;
esac
