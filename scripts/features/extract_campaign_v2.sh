#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../campaign/common.sh"
if (( $# < 1 || $# > 2 )); then echo "Uso: $0 ID_CAMPAÑA [DIRECTORIO_SALIDA]" >&2; exit 2; fi
id="$1"; ppi_validate_id "$id"
campaign_dir="$(ppi_campaign_dir "$id")"
output_dir="${2:-$PPI_ARTIFACTS_ROOT/features-v2/$id}"
[[ -d "$campaign_dir" ]] || ppi_die "campaña inexistente: $campaign_dir"
[[ "$(jq -r '.status' "$campaign_dir/manifest.json")" == completed ]] || ppi_die "campaña no completada"
[[ "$(jq -r '.evidence.complete' "$campaign_dir/manifest.json")" == true ]] || ppi_die "evidencia incompleta"
[[ -n "$(jq -r '.verified_at // empty' "$campaign_dir/pcap-start.json")" ]] || ppi_die "falta verified_at"
(
  cd "$campaign_dir"; sha256sum -c SHA256SUMS >/dev/null
)
mapfile -d '' pcap_files < <(find "$campaign_dir/pcap" -maxdepth 1 -type f -name 'capture.pcap*' -print0 | sort -z)
(( ${#pcap_files[@]} >= 1 )) || ppi_die "no hay PCAP"
mkdir -p -m 0700 "$output_dir"
"$SCRIPT_DIR/extract_multilayer_v2.py" --pcap "${pcap_files[@]}" --eve "$campaign_dir/eve-slice.jsonl" \
  --pcap-start-json "$campaign_dir/pcap-start.json" --campaign-id "$id" \
  --output "$output_dir/multilayer-v2.csv" > "$output_dir/extraction-report.json"
jq -e '.schema_version == "multilayer-v2" and .rows >= 1' "$output_dir/extraction-report.json" >/dev/null
( cd "$output_dir"; sha256sum multilayer-v2.csv extraction-report.json > SHA256SUMS )
printf 'Features v2 extraídas: %s\n' "$output_dir/multilayer-v2.csv"
