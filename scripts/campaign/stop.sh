#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

if (( $# < 1 || $# > 2 )); then
  echo "Uso: $0 ID [CODIGO_SALIDA]" >&2
  exit 2
fi

id="$1"
scenario_exit_code="${2:-0}"
ppi_validate_id "$id"
[[ "$scenario_exit_code" =~ ^[0-9]+$ ]] || ppi_die "código de salida inválido"
[[ -d "$PPI_ACTIVE_LOCK" ]] || ppi_die "no existe una campaña activa"
active_id="$(cat "$PPI_ACTIVE_LOCK/id")"
[[ "$active_id" == "$id" ]] || ppi_die "la campaña activa es $active_id, no $id"

campaign_dir="$(ppi_campaign_dir "$id")"
[[ -d "$campaign_dir" ]] || ppi_die "no existe $campaign_dir"

settle_seconds="${PPI_CAMPAIGN_SETTLE_SECONDS:-9}"
[[ "$settle_seconds" =~ ^[0-9]+$ ]] && (( settle_seconds <= 15 )) ||
  ppi_die "PPI_CAMPAIGN_SETTLE_SECONDS debe estar entre 0 y 15"
sleep "$settle_seconds"

ppi_ssh "$PPI_SENSOR_IP" "sudo -n /usr/local/sbin/ppi-pcap-control stop '$id'" \
  > "$campaign_dir/pcap-stop.json"
ppi_ssh "$PPI_SENSOR_IP" "cd '/var/lib/ppi-captures/$id' && sha256sum ./capture.pcap*" \
  > "$campaign_dir/pcap-remote-SHA256SUMS"
mkdir -m 0700 "$campaign_dir/pcap"
ppi_ssh "$PPI_SENSOR_IP" "tar -C '/var/lib/ppi-captures/$id' -cf - ." |
  tar -C "$campaign_dir/pcap" -xf -

pcap_transfer_verified=false
if (
  cd "$campaign_dir/pcap"
  sha256sum -c ../pcap-remote-SHA256SUMS
) > "$campaign_dir/pcap-transfer-verification.txt" 2>&1; then
  pcap_transfer_verified=true
fi

pcap_validation_failures=0
pcap_file_count=0
pcap_total_bytes=0
: > "$campaign_dir/pcap-validation.stderr"
mapfile -d '' pcap_files < <(
  find "$campaign_dir/pcap" -maxdepth 1 -type f -name 'capture.pcap*' -print0 | sort -z
)
for pcap_file in "${pcap_files[@]}"; do
  pcap_file_count=$((pcap_file_count + 1))
  pcap_size="$(stat -c '%s' "$pcap_file")"
  pcap_total_bytes=$((pcap_total_bytes + pcap_size))
  if ! tcpdump -n -r "$pcap_file" -w /dev/null 2>> "$campaign_dir/pcap-validation.stderr"; then
    pcap_validation_failures=$((pcap_validation_failures + 1))
  fi
done
"$SCRIPT_DIR/../analysis/pcap-ip-length-summary.sh" "${pcap_files[@]}" \
  > "$campaign_dir/pcap-ip-length-summary.json"
pcap_parsed_packets="$(jq -r '.total_ipv4_packets' "$campaign_dir/pcap-ip-length-summary.json")"
pcap_captured_packets="$(jq -r '.tcpdump.packets_captured' "$campaign_dir/pcap-stop.json")"
pcap_remote_file_count="$(jq -r '.files.count' "$campaign_dir/pcap-stop.json")"
pcap_remote_total_bytes="$(jq -r '.files.total_bytes' "$campaign_dir/pcap-stop.json")"
pcap_limit_reached=false
(( pcap_total_bytes < 1945600000 )) || pcap_limit_reached=true

sampler_pid="$(cat "$PPI_ACTIVE_LOCK/sampler_pid" 2>/dev/null || true)"
if [[ "$sampler_pid" =~ ^[0-9]+$ ]] && kill -0 "$sampler_pid" 2>/dev/null; then
  sampler_command="$(ps -p "$sampler_pid" -o args= || true)"
  [[ "$sampler_command" == *"$PPI_SENSOR_IP"* ]] || ppi_die "el PID $sampler_pid no corresponde al sampler esperado"
  kill "$sampler_pid"
  for _ in 1 2 3 4 5; do
    kill -0 "$sampler_pid" 2>/dev/null || break
    sleep 1
  done
  kill -0 "$sampler_pid" 2>/dev/null &&
    ppi_die "el sampler PID $sampler_pid no se detuvo; la campaña permanece abierta"
fi

ppi_ssh "$PPI_SENSOR_IP" 'sudo -n /usr/local/sbin/ppi-suricata-metrics' \
  > "$campaign_dir/sensor-after.json"

before_inode="$(jq -r '.eve.inode' "$campaign_dir/sensor-before.json")"
after_inode="$(jq -r '.eve.inode' "$campaign_dir/sensor-after.json")"
before_lines="$(jq -r '.eve.lines' "$campaign_dir/sensor-before.json")"
after_lines="$(jq -r '.eve.lines' "$campaign_dir/sensor-after.json")"
if [[ "$before_inode" == "$after_inode" ]]; then
  if (( after_lines > before_lines )); then
    first_line=$((before_lines + 1))
    ppi_ssh "$PPI_SENSOR_IP" "sed -n '${first_line},${after_lines}p' /var/log/suricata/eve.json" \
      > "$campaign_dir/eve-slice.jsonl"
  else
    : > "$campaign_dir/eve-slice.jsonl"
  fi
  eve_slice_status="complete_same_inode"
else
  : > "$campaign_dir/eve-slice.jsonl"
  eve_slice_status="unavailable_log_rotated"
fi

sensor_sample_rows="$(awk 'END {print (NR > 0 ? NR - 1 : 0)}' "$campaign_dir/sensor-timeseries.tsv")"
sensor_sampler_stderr_bytes="$(stat -c '%s' "$campaign_dir/sensor-timeseries.stderr")"
eve_slice_records="$(wc -l < "$campaign_dir/eve-slice.jsonl")"
if [[ "$before_inode" == "$after_inode" ]] && (( after_lines >= before_lines )); then
  expected_eve_records=$((after_lines - before_lines))
else
  expected_eve_records=-1
fi
evidence_complete=true
(( sensor_sample_rows >= 1 )) || evidence_complete=false
(( sensor_sampler_stderr_bytes == 0 )) || evidence_complete=false
(( pcap_file_count >= 1 )) || evidence_complete=false
(( pcap_validation_failures == 0 )) || evidence_complete=false
(( pcap_parsed_packets == pcap_captured_packets )) || evidence_complete=false
(( pcap_file_count == pcap_remote_file_count )) || evidence_complete=false
(( pcap_total_bytes == pcap_remote_total_bytes )) || evidence_complete=false
[[ "$pcap_transfer_verified" == true ]] || evidence_complete=false
[[ "$pcap_limit_reached" == false ]] || evidence_complete=false
pcap_kernel_drops="$(jq -r '.tcpdump.packets_dropped_by_kernel' "$campaign_dir/pcap-stop.json")"
(( pcap_kernel_drops == 0 )) || evidence_complete=false
[[ "$eve_slice_status" == "complete_same_inode" ]] || evidence_complete=false
(( eve_slice_records == expected_eve_records )) || evidence_complete=false

ended_at="$(date --iso-8601=seconds)"
ended_at_utc="$(date --utc --iso-8601=seconds)"
if (( scenario_exit_code != 0 )); then
  final_status="scenario_failed"
elif [[ "$evidence_complete" == true ]]; then
  final_status="completed"
else
  final_status="evidence_failed"
fi

jq -n \
  --slurpfile before "$campaign_dir/sensor-before.json" \
  --slurpfile after "$campaign_dir/sensor-after.json" \
  --arg eve_slice_status "$eve_slice_status" \
  --argjson eve_slice_records "$eve_slice_records" '
  def delta($a; $b):
    if ($a | type) == "number" and ($b | type) == "number" and $b >= $a then $b - $a else null end;
  {
    schema_version: 1,
    counter_reset_detected: (
      $after[0].suricata.capture.kernel_packets < $before[0].suricata.capture.kernel_packets
    ),
    capture: {
      kernel_packets: delta($before[0].suricata.capture.kernel_packets; $after[0].suricata.capture.kernel_packets),
      kernel_drops: delta($before[0].suricata.capture.kernel_drops; $after[0].suricata.capture.kernel_drops),
      kernel_ifdrops: delta($before[0].suricata.capture.kernel_ifdrops; $after[0].suricata.capture.kernel_ifdrops)
    },
    decoder_invalid: delta($before[0].suricata.decoder_invalid; $after[0].suricata.decoder_invalid),
    alert_queue_overflow: delta($before[0].suricata.alert_queue_overflow; $after[0].suricata.alert_queue_overflow),
    eve: {
      records: delta($before[0].eve.lines; $after[0].eve.lines),
      slice_records: $eve_slice_records,
      slice_matches_checkpoint: (
        delta($before[0].eve.lines; $after[0].eve.lines) == $eve_slice_records
      ),
      slice_status: $eve_slice_status
    }
  }' > "$campaign_dir/deltas.json"

manifest_tmp="$campaign_dir/manifest.json.tmp"
jq \
  --arg ended_at "$ended_at" \
  --arg ended_at_utc "$ended_at_utc" \
  --arg status "$final_status" \
  --argjson scenario_exit_code "$scenario_exit_code" \
  --arg eve_slice_status "$eve_slice_status" \
  --argjson settle_seconds "$settle_seconds" \
  --argjson sensor_sample_rows "$sensor_sample_rows" \
  --argjson sensor_sampler_stderr_bytes "$sensor_sampler_stderr_bytes" \
  --argjson pcap_file_count "$pcap_file_count" \
  --argjson pcap_total_bytes "$pcap_total_bytes" \
  --argjson pcap_validation_failures "$pcap_validation_failures" \
  --argjson pcap_parsed_packets "$pcap_parsed_packets" \
  --argjson pcap_captured_packets "$pcap_captured_packets" \
  --argjson pcap_kernel_drops "$pcap_kernel_drops" \
  --argjson pcap_remote_file_count "$pcap_remote_file_count" \
  --argjson pcap_remote_total_bytes "$pcap_remote_total_bytes" \
  --argjson pcap_transfer_verified "$pcap_transfer_verified" \
  --argjson pcap_limit_reached "$pcap_limit_reached" \
  --argjson eve_slice_records "$eve_slice_records" \
  --argjson expected_eve_records "$expected_eve_records" \
  --argjson evidence_complete "$evidence_complete" '
  . + {
    status: $status,
    ended_at: $ended_at,
    ended_at_utc: $ended_at_utc,
    scenario_exit_code: $scenario_exit_code,
    settle_seconds: $settle_seconds,
    eve_slice_status: $eve_slice_status,
    evidence: {
      complete: $evidence_complete,
      sensor_sample_rows: $sensor_sample_rows,
      sensor_sampler_stderr_bytes: $sensor_sampler_stderr_bytes,
      pcap_file_count: $pcap_file_count,
      pcap_total_bytes: $pcap_total_bytes,
      pcap_validation_failures: $pcap_validation_failures,
      pcap_parsed_packets: $pcap_parsed_packets,
      pcap_captured_packets: $pcap_captured_packets,
      pcap_kernel_drops: $pcap_kernel_drops,
      pcap_remote_file_count: $pcap_remote_file_count,
      pcap_remote_total_bytes: $pcap_remote_total_bytes,
      pcap_transfer_verified: $pcap_transfer_verified,
      pcap_limit_reached: $pcap_limit_reached,
      eve_slice_records: $eve_slice_records,
      expected_eve_records: $expected_eve_records
    }
  }' "$campaign_dir/manifest.json" > "$manifest_tmp"
mv "$manifest_tmp" "$campaign_dir/manifest.json"

(
  cd "$campaign_dir"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
rm -rf -- "$PPI_ACTIVE_LOCK"

printf 'Campaña cerrada: %s\nEstado: %s\nDirectorio: %s\n' "$id" "$final_status" "$campaign_dir"
[[ "$final_status" != "evidence_failed" ]] || exit 3
