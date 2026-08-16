#!/usr/bin/env bash
set -uo pipefail

# Variante de run-f1.sh que ejecuta el escenario desde Kali (VM04) en vez del
# Cliente (VM05). Script paralelo deliberado: run-f1.sh tiene PPI_CLIENT_IP y
# el generador benigno hardcodeados y lo usan 220+ campañas normales ya
# validadas; no se modifica para no arriesgar ese camino. Esta copia solo
# cambia el host SSH, el binario remoto y la lista blanca de escenarios.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if (( $# < 2 )); then
  echo "Uso: $0 ID ESCENARIO-KALI [ARGUMENTOS]" >&2
  exit 2
fi

id="$1"
scenario="$2"
shift 2
ppi_validate_id "$id"
case "$scenario" in
  tcp-syn-rate|tcp-port-scan|udp-probe|port-scan-wide|password-spray|dns-entropy) ;;
  *) ppi_die "escenario Kali no permitido: $scenario" ;;
esac
for argument in "$@"; do
  [[ "$argument" =~ ^[A-Za-z0-9._-]+$ ]] || ppi_die "argumento remoto no permitido: $argument"
done

purpose="${PPI_CAMPAIGN_PURPOSE:-evaluation}"
phase="${PPI_CAMPAIGN_PHASE:-F2}"
warmup_seconds="${PPI_CAMPAIGN_WARMUP_SECONDS:-60}"
[[ "$warmup_seconds" =~ ^[0-9]+$ ]] && (( warmup_seconds >= 1 && warmup_seconds <= 120 )) ||
  ppi_die "PPI_CAMPAIGN_WARMUP_SECONDS debe estar entre 1 y 120"
"$SCRIPT_DIR/start.sh" "$id" "$phase" "$scenario" anomaly "$purpose" || exit $?
campaign_dir="$(ppi_campaign_dir "$id")"

campaign_closed=false
stop_rc=0
scenario_rc=1

close_campaign() {
  local close_rc="$1"
  [[ "$campaign_closed" == false ]] || return 0
  campaign_closed=true
  [[ -d "$PPI_ACTIVE_LOCK" ]] || return 0
  "$SCRIPT_DIR/stop.sh" "$id" "$close_rc"
  stop_rc=$?
  return "$stop_rc"
}

close_on_exit() {
  local rc=$?
  close_campaign "$rc" || true
  return "$rc"
}

close_on_signal() {
  close_campaign 130
  trap - HUP INT TERM EXIT
  exit 130
}
trap close_on_exit EXIT
trap close_on_signal HUP INT TERM

sleep "$warmup_seconds"
remote_command="$(printf '%q ' /home/useransible/bin/ppi-run-anomaly "$scenario" "$@")"
ppi_ssh "$PPI_KALI_IP" "$remote_command" \
  > "$campaign_dir/scenario-output.txt" \
  2> "$campaign_dir/scenario-stderr.txt"
scenario_rc=$?

close_campaign "$scenario_rc"
trap - HUP INT TERM EXIT
(( stop_rc == 0 )) || exit "$stop_rc"
exit "$scenario_rc"
