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
ppi_validate_id "$id"
[[ "$phase" =~ ^F[0-9]+$ ]] || ppi_die "la fase debe usar el formato F0, F1, ..."
[[ "$traffic_class" =~ ^[a-z][a-z0-9_-]*$ ]] || ppi_die "clase de tráfico inválida"
[[ "$purpose" =~ ^[a-z][a-z0-9_-]*$ ]] || ppi_die "propósito inválido"
[[ -r "$PPI_SSH_KEY" ]] || ppi_die "no se puede leer la clave SSH $PPI_SSH_KEY"

mkdir -p -m 0700 "$PPI_CAMPAIGNS_DIR"
campaign_dir="$(ppi_campaign_dir "$id")"
[[ ! -e "$campaign_dir" ]] || ppi_die "ya existe el directorio de campaña $campaign_dir"
if ! mkdir -m 0700 "$PPI_ACTIVE_LOCK" 2>/dev/null; then
  active_id="$(cat "$PPI_ACTIVE_LOCK/id" 2>/dev/null || echo desconocida)"
  ppi_die "ya existe una campaña activa: $active_id"
fi

sampler_pid=""
cleanup_failed_start() {
  if [[ -n "$sampler_pid" ]] && kill -0 "$sampler_pid" 2>/dev/null; then
    kill "$sampler_pid" 2>/dev/null || true
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
  --argjson git_dirty "$git_dirty" '
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

"$SCRIPT_DIR/sample-sensor.sh" "$PPI_SENSOR_IP" 1 \
  > "$campaign_dir/sensor-timeseries.tsv" \
  2> "$campaign_dir/sensor-timeseries.stderr" &
sampler_pid=$!
printf '%s\n' "$sampler_pid" > "$PPI_ACTIVE_LOCK/sampler_pid"
printf '%s\n' "$campaign_dir" > "$PPI_ACTIVE_LOCK/path"

trap - ERR INT TERM
printf 'Campaña iniciada: %s\nDirectorio: %s\nSampler PID local: %s\n' "$id" "$campaign_dir" "$sampler_pid"
