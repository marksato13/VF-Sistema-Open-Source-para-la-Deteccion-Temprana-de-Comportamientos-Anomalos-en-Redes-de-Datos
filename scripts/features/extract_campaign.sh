#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../campaign/common.sh
source "$SCRIPT_DIR/../campaign/common.sh"

if (( $# < 1 || $# > 2 )); then
  echo "Uso: $0 ID_CAMPAÑA [DIRECTORIO_SALIDA]" >&2
  exit 2
fi

id="$1"
ppi_validate_id "$id"
campaign_dir="$(ppi_campaign_dir "$id")"
output_dir="${2:-$PPI_ARTIFACTS_ROOT/features/$id}"

[[ -d "$campaign_dir" ]] || ppi_die "campaña inexistente: $id"
[[ "$(jq -r '.status' "$campaign_dir/manifest.json")" == completed ]] ||
  ppi_die "la campaña no tiene estado completed"
[[ "$(jq -r '.evidence.complete' "$campaign_dir/manifest.json")" == true ]] ||
  ppi_die "la evidencia de campaña no está completa"
[[ -n "$(jq -r '.verified_at // empty' "$campaign_dir/pcap-start.json")" ]] ||
  ppi_die "pcap-start.json no posee verified_at; la campaña es anterior al contrato G5"

(
  cd "$campaign_dir"
  sha256sum -c SHA256SUMS >/dev/null
)

mapfile -d '' pcap_files < <(
  find "$campaign_dir/pcap" -maxdepth 1 -type f -name 'capture.pcap*' -print0 | sort -z
)
(( ${#pcap_files[@]} >= 1 )) || ppi_die "la campaña no contiene PCAP"

mkdir -p -m 0700 "$output_dir"
output_csv="$output_dir/multilayer-v1.csv"
report_json="$output_dir/extraction-report.json"

"$SCRIPT_DIR/extract_multilayer.py" \
  --pcap "${pcap_files[@]}" \
  --eve "$campaign_dir/eve-slice.jsonl" \
  --pcap-start-json "$campaign_dir/pcap-start.json" \
  --campaign-id "$id" \
  --output "$output_csv" \
  > "$report_json"

jq -e '.schema_version == "multilayer-v1" and .rows >= 1' "$report_json" >/dev/null
(
  cd "$output_dir"
  sha256sum multilayer-v1.csv extraction-report.json > SHA256SUMS
)

printf 'Features extraídas: %s\nReporte: %s\n' "$output_csv" "$report_json"
