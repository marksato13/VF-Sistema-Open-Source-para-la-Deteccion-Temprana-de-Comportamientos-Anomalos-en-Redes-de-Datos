#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if (( $# < 2 )); then
  echo "Uso: $0 ID ESCENARIO-F1 [ARGUMENTOS]" >&2
  exit 2
fi

id="$1"
scenario="$2"
shift 2
ppi_validate_id "$id"
case "$scenario" in
  http|https|http-concurrent|http-multi|http-missing|https-sessions|dns-valid|dns-nxdomain|dns-mixed|dns-multi|api-normal|api-auth-fail|ping|tcp-refused|iperf-tcp|iperf-udp|frag-udp|mixed-light) ;;
  *) ppi_die "escenario F1 no permitido: $scenario" ;;
esac
for argument in "$@"; do
  [[ "$argument" =~ ^[A-Za-z0-9._-]+$ ]] || ppi_die "argumento remoto no permitido: $argument"
done

purpose="${PPI_CAMPAIGN_PURPOSE:-experiment}"
phase="${PPI_CAMPAIGN_PHASE:-F1}"
warmup_seconds="${PPI_CAMPAIGN_WARMUP_SECONDS:-1}"
[[ "$warmup_seconds" =~ ^[0-9]+$ ]] && (( warmup_seconds >= 1 && warmup_seconds <= 120 )) ||
  ppi_die "PPI_CAMPAIGN_WARMUP_SECONDS debe estar entre 1 y 120"
"$SCRIPT_DIR/start.sh" "$id" "$phase" "$scenario" benign "$purpose" || exit $?
campaign_dir="$(ppi_campaign_dir "$id")"

campaign_closed=false
stop_rc=0
scenario_rc=1

# Cierra la campaña como máximo una vez, sin importar el resultado del
# primer intento. "campaign_closed" se marca antes de invocar stop.sh (no
# solo cuando tiene éxito) para que un stop.sh fallido no dispare una
# segunda invocación desde el trap EXIT: reintentar ciegamente sobre
# evidencia ya tocada (p. ej. "mkdir" en campaign_dir/pcap) es inseguro.
# El trap EXIT queda como red de seguridad para cualquier salida (normal,
# señal atrapable o un "exit" futuro no previsto) que no haya pasado por
# aquí; no cubre SIGKILL, que ningún shell puede atrapar.
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

# F1 final usa 60 s para completar las ventanas causales; calibración usa 1 s.
sleep "$warmup_seconds"
remote_command="$(printf '%q ' /home/useransible/bin/ppi-run-benign "$scenario" "$@")"
ppi_ssh "$PPI_CLIENT_IP" "$remote_command" \
  > "$campaign_dir/scenario-output.txt" \
  2> "$campaign_dir/scenario-stderr.txt"
scenario_rc=$?

close_campaign "$scenario_rc"
trap - HUP INT TERM EXIT
(( stop_rc == 0 )) || exit "$stop_rc"
exit "$scenario_rc"
