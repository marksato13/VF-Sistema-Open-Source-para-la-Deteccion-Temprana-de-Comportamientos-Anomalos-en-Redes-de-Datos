#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if (( $# < 4 || $# > 5 )); then
  echo "Uso: $0 ID FASE ESCENARIO CLASE [PROPOSITO]" >&2
  exit 2
fi

id="$1"
phase="$2"
scenario="$3"
traffic_class="$4"
purpose="${5:-experiment}"
warmup_seconds="${PPI_CAMPAIGN_WARMUP_SECONDS:-1}"
matrix_sha256="${PPI_CAMPAIGN_MATRIX_SHA256:-}"
matrix_profile="${PPI_CAMPAIGN_MATRIX_PROFILE:-}"
matrix_repetition="${PPI_CAMPAIGN_MATRIX_REPETITION:-}"
campaign_partition="${PPI_CAMPAIGN_PARTITION:-unassigned}"
scenario_args_sha256="${PPI_CAMPAIGN_ARGS_SHA256:-}"
ppi_validate_id "$id"
[[ "$phase" =~ ^F[0-9]+$ ]] || ppi_die "la fase debe usar el formato F0, F1, ..."
[[ "$traffic_class" =~ ^[a-z][a-z0-9_-]*$ ]] || ppi_die "clase de tráfico inválida"
[[ "$purpose" =~ ^[a-z][a-z0-9_-]*$ ]] || ppi_die "propósito inválido"
case "$campaign_partition" in
  train|validation|test|excluded_calibration|unassigned) ;;
  *) ppi_die "partición de campaña inválida" ;;
esac
[[ "$warmup_seconds" =~ ^[0-9]+$ ]] && (( warmup_seconds >= 1 && warmup_seconds <= 120 )) ||
  ppi_die "PPI_CAMPAIGN_WARMUP_SECONDS debe estar entre 1 y 120"
if [[ -n "$matrix_sha256$matrix_profile$matrix_repetition$scenario_args_sha256" ]]; then
  [[ "$matrix_sha256" =~ ^[a-f0-9]{64}$ ]] || ppi_die "hash SHA-256 de matriz inválido"
  [[ "$matrix_profile" =~ ^[A-Z0-9][A-Z0-9-]{2,47}$ ]] || ppi_die "perfil de matriz inválido"
  [[ "$matrix_repetition" =~ ^[0-9]+$ ]] && (( matrix_repetition >= 1 && matrix_repetition <= 99 )) ||
    ppi_die "repetición de matriz inválida"
  [[ "$scenario_args_sha256" =~ ^[a-f0-9]{64}$ ]] || ppi_die "hash de argumentos de escenario inválido"
fi
[[ -r "$PPI_SSH_KEY" ]] || ppi_die "no se puede leer la clave SSH $PPI_SSH_KEY"

mkdir -p -m 0700 "$PPI_CAMPAIGNS_DIR"
local_available_kib="$(df -Pk "$PPI_CAMPAIGNS_DIR" | awk 'NR == 2 {print $4}')"
(( local_available_kib >= 3145728 )) || ppi_die "se requieren al menos 3 GiB libres en VM01"
campaign_dir="$(ppi_campaign_dir "$id")"
[[ ! -e "$campaign_dir" ]] || ppi_die "ya existe el directorio de campaña $campaign_dir"
if ! mkdir -m 0700 "$PPI_ACTIVE_LOCK" 2>/dev/null; then
  active_id="$(cat "$PPI_ACTIVE_LOCK/id" 2>/dev/null || echo desconocida)"
  ppi_die "ya existe una campaña activa: $active_id"
fi

sampler_pid=""
pcap_attempted=false
cleanup_failed_start() {
  if [[ -n "$sampler_pid" ]] && kill -0 "$sampler_pid" 2>/dev/null; then
    kill "$sampler_pid" 2>/dev/null || true
  fi
  if [[ "$pcap_attempted" == true ]]; then
    pcap_state="$(ppi_ssh "$PPI_SENSOR_IP" "sudo -n /usr/local/sbin/ppi-pcap-control status '$id'" 2>/dev/null |
      jq -r '.status' 2>/dev/null || true)"
    if [[ "$pcap_state" == capturing ]]; then
      ppi_ssh "$PPI_SENSOR_IP" "sudo -n /usr/local/sbin/ppi-pcap-control stop '$id'" >/dev/null 2>&1 || true
    fi
  fi
  rm -rf -- "$PPI_ACTIVE_LOCK"
  echo "ERROR: no se pudo iniciar la campaña $id; se conservó la evidencia parcial en $campaign_dir" >&2
}
trap cleanup_failed_start ERR
trap 'cleanup_failed_start; exit 130' INT TERM

mkdir -m 0700 "$campaign_dir"
printf '%s\n' "$id" > "$PPI_ACTIVE_LOCK/id"

started_at="$(date --iso-8601=seconds)"
started_at_utc="$(date --utc --iso-8601=seconds)"
git_commit="$(git -C "$PPI_REPO_ROOT" rev-parse HEAD)"
if [[ -n "$(git -C "$PPI_REPO_ROOT" status --porcelain)" ]]; then
  git_dirty=true
else
  git_dirty=false
fi

jq -n \
  --arg id "$id" \
  --arg phase "$phase" \
  --arg scenario "$scenario" \
  --arg traffic_class "$traffic_class" \
  --arg purpose "$purpose" \
  --arg started_at "$started_at" \
  --arg started_at_utc "$started_at_utc" \
  --arg git_commit "$git_commit" \
  --arg matrix_sha256 "$matrix_sha256" \
  --arg matrix_profile "$matrix_profile" \
  --arg matrix_repetition "$matrix_repetition" \
  --arg campaign_partition "$campaign_partition" \
  --arg scenario_args_sha256 "$scenario_args_sha256" \
  --argjson git_dirty "$git_dirty" \
  --argjson warmup_seconds "$warmup_seconds" '
  {
    schema_version: 1,
    campaign_id: $id,
    phase: $phase,
    scenario: $scenario,
    traffic_class: $traffic_class,
    purpose: $purpose,
    status: "running",
    started_at: $started_at,
    started_at_utc: $started_at_utc,
    git: {commit: $git_commit, dirty: $git_dirty},
    partition: $campaign_partition,
    campaign_plan: (
      if $matrix_sha256 == "" then null else {
        matrix_sha256: $matrix_sha256,
        profile: $matrix_profile,
        repetition: ($matrix_repetition | tonumber),
        scenario_args_sha256: $scenario_args_sha256
      } end
    ),
    warmup_seconds: $warmup_seconds,
    topology: {
      sensor_mgmt: "10.10.10.20",
      server_service: "10.30.0.10",
      client_service: "10.20.0.20",
      sensor_capture_interface: "ens35"
    }
  }' > "$campaign_dir/manifest.json"

declare -A nodes=(
  [sensor]="$PPI_SENSOR_IP"
  [server]="$PPI_SERVER_IP"
  [kali]="$PPI_KALI_IP"
  [client]="$PPI_CLIENT_IP"
)
for node in sensor server kali client; do
  {
    printf 'node=%s\nmanagement_ip=%s\n' "$node" "${nodes[$node]}"
    ppi_ssh "${nodes[$node]}" '
      printf "hostname="; hostname
      printf "timestamp="; date --iso-8601=seconds
      printf "kernel="; uname -r
      timedatectl show -p Timezone -p NTPSynchronized
      ip -brief address
      ip route show
    '
  } > "$campaign_dir/inventory-$node.txt"
done

ppi_ssh "$PPI_SENSOR_IP" 'sudo -n /usr/local/sbin/ppi-suricata-metrics' \
  > "$campaign_dir/sensor-before.json"
jq -e '.suricata.service_state == "active"' "$campaign_dir/sensor-before.json" >/dev/null

pcap_attempted=true
if ! ppi_ssh "$PPI_SENSOR_IP" "sudo -n /usr/local/sbin/ppi-pcap-control start '$id'" \
  > "$campaign_dir/pcap-start.json"; then
  cleanup_failed_start
  trap - ERR INT TERM
  exit 1
fi

"$SCRIPT_DIR/sample-sensor.sh" "$PPI_SENSOR_IP" 1 \
  > "$campaign_dir/sensor-timeseries.tsv" \
  2> "$campaign_dir/sensor-timeseries.stderr" &
sampler_pid=$!
printf '%s\n' "$sampler_pid" > "$PPI_ACTIVE_LOCK/sampler_pid"
printf '%s\n' "$campaign_dir" > "$PPI_ACTIVE_LOCK/path"

trap - ERR INT TERM
printf 'Campaña iniciada: %s\nDirectorio: %s\nSampler PID local: %s\n' "$id" "$campaign_dir" "$sampler_pid"
