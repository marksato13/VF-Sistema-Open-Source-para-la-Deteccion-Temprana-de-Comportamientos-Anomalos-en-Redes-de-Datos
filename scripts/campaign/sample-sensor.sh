#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

sensor_ip="${1:-$PPI_SENSOR_IP}"
interval="${2:-1}"
[[ "$sensor_ip" =~ ^[0-9.]+$ ]] || ppi_die "IP de Sensor inválida"
[[ "$interval" =~ ^[1-9][0-9]*$ ]] || ppi_die "intervalo inválido"

remote_snapshot() {
  ppi_ssh "$sensor_ip" '
    pid="$(pgrep -o -x Suricata-Main || pgrep -o -f "^/usr/bin/suricata " || true)"
    [[ -n "$pid" ]] || exit 1
    ticks="$(awk "{print \$14 + \$15}" "/proc/$pid/stat")"
    rss_kib="$(awk "/^VmRSS:/ {print \$2}" "/proc/$pid/status")"
    mem_available_kib="$(awk "/^MemAvailable:/ {print \$2}" /proc/meminfo)"
    load1="$(awk "{print \$1}" /proc/loadavg)"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$(date --iso-8601=seconds)" "$(date +%s%N)" "$pid" "$ticks" "$(getconf CLK_TCK)" \
      "$rss_kib" "$mem_available_kib:$load1"
  '
}

IFS=$'\t' read -r previous_timestamp previous_epoch_ns previous_pid previous_ticks ticks_per_second \
  previous_rss previous_memory_and_load < <(remote_snapshot)

printf 'timestamp\tpid\tcpu_percent\trss_kib\tmem_available_kib\tload1\n'
while sleep "$interval"; do
  IFS=$'\t' read -r timestamp epoch_ns pid ticks current_hz rss_kib memory_and_load < <(remote_snapshot)
  [[ "$pid" == "$previous_pid" && "$current_hz" == "$ticks_per_second" ]] || {
    echo "El proceso Suricata cambió durante la campaña" >&2
    exit 1
  }
  mem_available_kib="${memory_and_load%%:*}"
  load1="${memory_and_load#*:}"
  delta_ticks=$((ticks - previous_ticks))
  delta_epoch_ns=$((epoch_ns - previous_epoch_ns))
  cpu_percent="$(awk -v delta_ticks="$delta_ticks" -v hz="$ticks_per_second" -v delta_ns="$delta_epoch_ns" \
    'BEGIN {printf "%.2f", (delta_ticks / hz) / (delta_ns / 1000000000) * 100}')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$timestamp" "$pid" "$cpu_percent" "$rss_kib" "$mem_available_kib" "$load1"
  previous_timestamp="$timestamp"
  previous_epoch_ns="$epoch_ns"
  previous_ticks="$ticks"
done
