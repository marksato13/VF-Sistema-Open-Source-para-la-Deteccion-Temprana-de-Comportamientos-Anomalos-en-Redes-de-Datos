#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] P4: agente v2 que lee el paquete feed.par, en SOMBRA. sudo -n (NOPASSWD en srv-dmz).
# VERSION p4-instalador 2026-11-06.2 (ver p4_comun.sh). Nunca --aplicar; ruleset igual al del respaldo.
#
#   bash srvdmz_p4.sh fase-a <PAQ>          cf-feed-ssh.sh (pareja Y paquete) + código nuevo; unidad sin cambios
#                                           (ya ejecutada el 06-nov 03:51 con la versión .1 de este guion)
#   bash srvdmz_p4.sh fase-c <PAQ>          unidad con --paquete (DESPUÉS de que el relé entregue paquete)
#   bash srvdmz_p4.sh revertir <RESPALDO>   reversión MANUAL a un respaldo de la versión .2
#   bash srvdmz_p4.sh revertir-heredado <RESPALDO_0351>
#                                           reversión MANUAL al estado previo a la fase A (respaldo de la versión .1,
#                                           srvdmz-p4-20261106T035127Z: ficheros en la raíz; ver README)
#
# Códigos: 0 OK · 10 parada sin cambios · 20 revertido automáticamente (verificado) · 30 reversión fallida (manual).
# Respaldo: ~/respaldos-etapa4/srvdmz-p4-<fase>-<UTC>/ (solo lectura). Evidencia: ~/evidencia-etapa4/srvdmz-p4-<fase>-<UTC>/.
set -uo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
source "$AQUI/../comun/evidencia.sh"
source "$AQUI/p4_comun.sh"
p4_entorno "sudo -n"
TS=$(date -u +%Y%m%dT%H%M%SZ)
U=ppi-enforce-agent-v2-dmz
UF="$RAIZ/etc/systemd/system/$U.service"
OPT="$RAIZ/opt/cyberflow/agente-v2"
FS="$RAIZ/usr/local/bin/cf-feed-ssh.sh"
FEED="$RAIZ/var/lib/cyberflow/feed"
TR="$RAIZ/var/lib/cyberflow/agente/traza.jsonl"
FICH=("$OPT/agente_enforce_v2.py" "$OPT/feed.py" "$OPT/pub.pem" "$FS" "$RAIZ/usr/local/sbin/cf-nft-helper" "$UF")

norm() { sed -E 's/counter packets [0-9]+ bytes [0-9]+/counter/; s/expires [0-9hms.]+//'; }
sin_aplicar_unidad() { ! grep -v '^[[:space:]]*#' "$1" | grep -qE '(^|[[:space:]])--aplicar'; }
sin_aplicar_proceso() { local c; c=$(p4_cmdline "$U") || return 1; [[ "$c" != *"--aplicar"* ]]; }
lee_paquete() { local c; c=$(p4_cmdline "$U") || return 1; [[ "$c" == *"--paquete $RAIZ/var/lib/cyberflow/feed/feed.par"* || "$c" == *"--paquete /var/lib/cyberflow/feed/feed.par"* ]]; }
ruleset_igual() { diff <($NFT list ruleset | norm) <(norm < "$1/ruleset.nft") > /dev/null; }
paquete_fresco() { local m; m=$($SUDO stat -c %Y "$FEED/feed.par") || return 1; [ $(( $(date +%s) - m )) -lt 60 ]; }
esperar_recepcion() {  # una recepción aceptada/repetida posterior a $1 (60 s máximo)
  local n
  for _ in $(seq 1 30); do
    n=$($SUDO tail -50 "$TR" | python3 -c '
import json,sys
d=float(sys.argv[1]); n=0
for l in sys.stdin:
    try: x=json.loads(l)
    except ValueError: continue
    if x.get("evento")=="recepcion" and x.get("t",0)>d and x.get("estado") in ("aceptado","repetido"): n+=1
print(n)' "$1") || return 1
    [ "${n:-0}" -gt 0 ] && { echo "recepciones válidas: $n"; return 0; }
    sleep "${CF_ESPERA:-2}"
  done
  echo "el agente no recibe"; return 1
}
reiniciar() { T_REINICIO=$(date +%s.%N); $SUDO systemctl restart "$U" && sleep "${CF_ESPERA:-3}"; }
respaldo_srvdmz() {  # ruleset de referencia + ficheros -> respaldo sellado, estricto y de solo lectura
  paso "crear respaldo $R" mkdir -p "$R"
  paso "leer ruleset para el respaldo" bash -c "$NFT list ruleset > '$R/ruleset.nft'"
  p4_respaldo "$R" "${FICH[@]}"
}
sombra() {
  paso "unidad sin --aplicar" sin_aplicar_unidad "$UF"
  paso "proceso sin --aplicar" sin_aplicar_proceso
  paso "ruleset igual al del respaldo" ruleset_igual "$R"
}
p4_revertir_desde() {
  local r="$1" f t
  rpaso "respaldo íntegro antes de revertir" p4_verificar_respaldo "$r" || return 1
  for f in "${FICH[@]}"; do rpaso "restaurar $f" p4_restaurar "$f" "$r"; done
  rpaso "daemon-reload (reversión)" $SUDO systemctl daemon-reload
  t=$(date +%s.%N)
  rpaso "reiniciar $U (reversión)" $SUDO systemctl restart "$U"
  sleep "${CF_ESPERA:-3}"
  rpaso "$U activo (reversión)" p4_activa "$U"
  rpaso "hashes = respaldo" p4_hashes_iguales "$r/instalados-antes.sha256" "${FICH[@]}"
  rpaso "unidad sin --aplicar (reversión)" sin_aplicar_unidad "$UF"
  rpaso "proceso sin --aplicar (reversión)" sin_aplicar_proceso
  rpaso "ruleset igual al del respaldo (reversión)" ruleset_igual "$r"
  if [ "${P4_REV_AVISO_RELE:-0}" = 1 ]; then
    echo "AVISO: el relé del bastión sigue en modo paquete y el agente revertido lee feed.json: la cadena no recibe"
    echo "       hasta revertir el bastión A MANO (bastion_p4.sh revertir <RESPALDO del bastión>, lo ejecuta Mark)."
  fi
  if [ "${P4_REV_AVISO_RELE:-0}" = 1 ]; then   # informativo: depende del modo del relé, no de esta reversión
    esperar_recepcion "$t" || echo "(sin recepción tras revertir: esperado mientras el relé siga en modo paquete)"
  else
    rpaso "el agente recibe tras revertir" esperar_recepcion "$t"
  fi
}
iniciar() {  # $1 fase
  R="$HOME/respaldos-etapa4/srvdmz-p4-$1-$TS"; E="$HOME/evidencia-etapa4/srvdmz-p4-$1-$TS"
  mkdir -p "$(dirname "$R")" "$(dirname "$E")"
  ev_abrir "$E"
  echo "$P4_VERSION · srvdmz_p4.sh $1 · paquete ${P:-} · respaldo $R · evidencia $E"
}

case "${1:-}" in
fase-a)
  P="${2:?paquete}"; iniciar fase-a; P4_FASE_SIGUIENTE="el paso del bastión"
  paso "paquete verifica" bash -c "cd '$P' && sha256sum -c --quiet SHA256SUMS"
  paso "$U activo" p4_activa "$U"
  respaldo_srvdmz; sombra
  cambio
  paso "instalar cf-feed-ssh.sh" $SUDO install -o root -g root -m 0755 "$P/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" "$FS"
  paso "instalar agente y feed.py" $SUDO install -o root -g root -m 0644 "$P/scripts/enforce/agente_enforce_v2.py" "$P/scripts/engine/feed.py" "$OPT/"
  paso "reiniciar $U" reiniciar
  paso "$U activo" p4_activa "$U"
  paso "el agente recibe" esperar_recepcion "$T_REINICIO"
  sombra
  paso "hashes instalados = paquete" p4_hashes_paquete "$P/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" "$FS" \
    "$P/scripts/enforce/agente_enforce_v2.py" "$OPT/agente_enforce_v2.py" "$P/scripts/engine/feed.py" "$OPT/feed.py"
  $SUDO sha256sum "${FICH[@]}" > "$E/instalados.sha256"
  echo "RESULTADO: OK — fase A. RESPALDO=$R EVIDENCIA=$E"; ev_sellar "$E"; exit 0 ;;
fase-c)
  P="${2:?paquete}"; iniciar fase-c; P4_FASE_SIGUIENTE="la transición en sombra"; P4_REV_AVISO_RELE=1
  NU="$P/deploy/etapa4/unidades/srvdmz/$U.service"
  paso "paquete verifica" bash -c "cd '$P' && sha256sum -c --quiet SHA256SUMS"
  paso "$U activo" p4_activa "$U"
  paso "código de la fase A instalado (hashes = paquete)" p4_hashes_paquete \
    "$P/scripts/enforce/agente_enforce_v2.py" "$OPT/agente_enforce_v2.py" "$P/scripts/engine/feed.py" "$OPT/feed.py" \
    "$P/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" "$FS"
  paso "feed.par existe y se actualiza (relé en modo paquete)" paquete_fresco
  paso "unidad nueva con --paquete" grep -q -- '--paquete /var/lib/cyberflow/feed/feed.par' "$NU"
  paso "unidad nueva sin --aplicar" sin_aplicar_unidad "$NU"
  paso "systemd-analyze verify de la unidad NUEVA (antes de instalarla)" p4_verify_unidad "$NU"
  respaldo_srvdmz; sombra
  cambio
  paso "instalar la unidad" $SUDO install -o root -g root -m 0644 "$NU" "$UF"
  paso "daemon-reload" $SUDO systemctl daemon-reload
  paso "systemd-analyze verify de la unidad instalada" p4_verify_unidad "$U.service"
  paso "reiniciar $U" reiniciar
  paso "$U activo" p4_activa "$U"
  paso "el agente lee feed.par" lee_paquete
  paso "el agente recibe" esperar_recepcion "$T_REINICIO"
  sombra
  paso "hashes instalados = paquete" p4_hashes_paquete "$NU" "$UF" \
    "$P/scripts/enforce/agente_enforce_v2.py" "$OPT/agente_enforce_v2.py" "$P/scripts/engine/feed.py" "$OPT/feed.py" \
    "$P/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" "$FS"
  $SUDO sha256sum "${FICH[@]}" > "$E/instalados.sha256"
  echo "RESULTADO: OK — fase C: el agente v2 lee el paquete; sombra mantenida. RESPALDO=$R EVIDENCIA=$E"
  ev_sellar "$E"; exit 0 ;;
revertir)
  R="${2:?respaldo}"; E="$HOME/evidencia-etapa4/srvdmz-p4-revertir-$TS"; mkdir -p "$(dirname "$E")"; ev_abrir "$E"
  echo "$P4_VERSION · srvdmz_p4.sh revertir (MANUAL) · respaldo $R"
  P4_REV_FALLOS=(); P4_REV_AVISO_RELE=1; p4_revertir_desde "$R"
  [ "${#P4_REV_FALLOS[@]}" -eq 0 ] && { echo "RESULTADO: REVERSIÓN MANUAL OK"; ev_sellar "$E"; exit 0; }
  echo "RESULTADO: REVERSIÓN MANUAL FALLIDA en: ${P4_REV_FALLOS[*]} — DETENIDO, revisar a mano"; ev_sellar "$E"; exit 30 ;;
revertir-heredado)
  # Respaldo de la versión .1: ficheros en la raíz del directorio y, dentro, la evidencia fase-a-* (defecto de
  # la .1, corregido en la .2). Se verifican TODOS los hashes del manifiesto; los ficheros no listados se informan.
  R0="${2:?respaldo .1}"; E="$HOME/evidencia-etapa4/srvdmz-p4-revertir-heredado-$TS"; mkdir -p "$(dirname "$E")"; ev_abrir "$E"
  echo "$P4_VERSION · srvdmz_p4.sh revertir-heredado (MANUAL) · respaldo $R0"
  paso "manifiesto del respaldo .1 verifica" bash -c "cd '$R0' && sha256sum -c --strict --quiet SHA256SUMS"
  echo "no listados en el manifiesto (evidencia de la .1, no se usan): $(cd "$R0" && find . -type f ! -name SHA256SUMS | LC_ALL=C sort | grep -vxF -f <(sed -E 's/^[0-9a-f]{64} [ *]//' SHA256SUMS) | tr '\n' ' ')"
  cambio; R="$R0"
  hmodo() { stat -c %a "$1"; }   # la .1 copió con «cp -a»: el modo original está en la copia
  p4_revertir_desde() {
    local r="$1" t f
    for f in "$FS" "$OPT/agente_enforce_v2.py" "$OPT/feed.py" "$UF"; do
      rpaso "restaurar $f" $SUDO install -o root -g root -m "$(hmodo "$r/$(basename "$f")")" "$r/$(basename "$f")" "$f"
    done
    rpaso "daemon-reload" $SUDO systemctl daemon-reload
    t=$(date +%s.%N); rpaso "reiniciar" $SUDO systemctl restart "$U"; sleep "${CF_ESPERA:-3}"
    rpaso "activo" p4_activa "$U"
    rpaso "hashes = respaldo .1" p4_hashes_iguales "$r/instalados-antes.sha256" "${FICH[@]}"
    rpaso "unidad sin --aplicar" sin_aplicar_unidad "$UF"; rpaso "proceso sin --aplicar" sin_aplicar_proceso
    rpaso "ruleset igual" ruleset_igual "$r"
    echo "AVISO: revertir también el bastión (bastion_p4.sh revertir) para que el agente vuelva a recibir"
  }
  P4_REV_FALLOS=(); p4_revertir_desde "$R0"
  [ "${#P4_REV_FALLOS[@]}" -eq 0 ] && { echo "RESULTADO: REVERSIÓN MANUAL OK (estado previo a la fase A)"; ev_sellar "$E"; exit 0; }
  echo "RESULTADO: REVERSIÓN MANUAL FALLIDA en: ${P4_REV_FALLOS[*]} — DETENIDO, revisar a mano"; ev_sellar "$E"; exit 30 ;;
*) echo "uso: srvdmz_p4.sh fase-a PAQ | fase-c PAQ | revertir R | revertir-heredado R0"; exit 2 ;;
esac
