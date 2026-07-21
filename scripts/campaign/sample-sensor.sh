#!/usr/bin/env bash
set -euo pipefail

interval="${1:-1}"
[[ "$interval" =~ ^[1-9][0-9]*$ ]] || exit 64

pid="$(pgrep -o -x Suricata-Main || pgrep -o -f '^/usr/bin/suricata ' || true)"
[[ -n "$pid" ]] || {
  echo "No se encontró el proceso Suricata" >&2
  exit 1
}

ticks_per_second="$(getconf CLK_TCK)"
previous_ticks="$(awk '{print $14 + $15}' "/proc/$pid/stat")"

printf 'timestamp\tpid\tcpu_percent\trss_kib\tmem_available_kib\tload1\n'
while kill -0 "$pid" 2>/dev/null; do
  sleep "$interval"
  current_ticks="$(awk '{print $14 + $15}' "/proc/$pid/stat")"
  delta_ticks=$((current_ticks - previous_ticks))
  cpu_percent="$(awk -v delta="$delta_ticks" -v hz="$ticks_per_second" -v seconds="$interval" \
    'BEGIN {printf "%.2f", (delta / hz / seconds) * 100}')"
  rss_kib="$(awk '/^VmRSS:/ {print $2}' "/proc/$pid/status")"
  mem_available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  load1="$(awk '{print $1}' /proc/loadavg)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date --iso-8601=seconds)" "$pid" "$cpu_percent" "$rss_kib" "$mem_available_kib" "$load1"
  previous_ticks="$current_ticks"
done
