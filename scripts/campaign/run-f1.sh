#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if (( $# < 2 )); then
  echo "Uso: $0 ID {http|https|dns-valid|dns-nxdomain|iperf-tcp|iperf-udp} [ARGUMENTOS]" >&2
  exit 2
fi

id="$1"
scenario="$2"
shift 2
ppi_validate_id "$id"
case "$scenario" in
  http|https|dns-valid|dns-nxdomain|iperf-tcp|iperf-udp) ;;
  *) ppi_die "escenario F1 no permitido: $scenario" ;;
esac
for argument in "$@"; do
  [[ "$argument" =~ ^[A-Za-z0-9._-]+$ ]] || ppi_die "argumento remoto no permitido: $argument"
done

purpose="${PPI_CAMPAIGN_PURPOSE:-experiment}"
warmup_seconds="${PPI_CAMPAIGN_WARMUP_SECONDS:-1}"
[[ "$warmup_seconds" =~ ^[0-9]+$ ]] && (( warmup_seconds >= 1 && warmup_seconds <= 120 )) ||
  ppi_die "PPI_CAMPAIGN_WARMUP_SECONDS debe estar entre 1 y 120"
"$SCRIPT_DIR/start.sh" "$id" F1 "$scenario" benign "$purpose" || exit $?
campaign_dir="$(ppi_campaign_dir "$id")"
campaign_closed=false

close_on_signal() {
  if [[ "$campaign_closed" == false && -d "$PPI_ACTIVE_LOCK" ]]; then
    "$SCRIPT_DIR/stop.sh" "$id" 130 || true
  fi
  exit 130
}
trap close_on_signal HUP INT TERM

# F1 final usa 60 s para completar las ventanas causales; calibración usa 1 s.
sleep "$warmup_seconds"
remote_command="$(printf '%q ' /home/useransible/bin/ppi-run-benign "$scenario" "$@")"
ppi_ssh "$PPI_CLIENT_IP" "$remote_command" \
  > "$campaign_dir/scenario-output.txt" \
  2> "$campaign_dir/scenario-stderr.txt"
scenario_rc=$?

"$SCRIPT_DIR/stop.sh" "$id" "$scenario_rc"
stop_rc=$?
(( stop_rc == 0 )) && campaign_closed=true
trap - HUP INT TERM
(( stop_rc == 0 )) || exit "$stop_rc"
exit "$scenario_rc"
