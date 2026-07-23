#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

usage() {
  echo "uso: archive-failed-attempt.sh ID attempt-NN [--dry-run]" >&2
}

[[ $# -eq 2 || $# -eq 3 ]] || {
  usage
  exit 1
}

campaign_id="$1"
attempt_label="$2"
dry_run=false
if [[ $# -eq 3 ]]; then
  [[ "$3" == "--dry-run" ]] || {
    usage
    exit 1
  }
  dry_run=true
fi

ppi_validate_id "$campaign_id"
[[ "$attempt_label" =~ ^attempt-[0-9]{2}$ ]] ||
  ppi_die "la etiqueta debe tener el formato attempt-NN"

campaign_dir="$PPI_CAMPAIGNS_DIR/$campaign_id"
ledger_path="$PPI_ARTIFACTS_ROOT/g6-ledger/$campaign_id.json"
feature_dir="$PPI_ARTIFACTS_ROOT/features/$campaign_id"
archive_parent="$PPI_ARTIFACTS_ROOT/failed-attempts/$campaign_id"
archive_dir="$archive_parent/$attempt_label"
staging_dir="$archive_parent/.${attempt_label}.partial"
remote_archive_dir="/var/lib/ppi-captures-failed/$campaign_id/$attempt_label"

[[ -d "$campaign_dir" ]] || ppi_die "no existe el bundle activo: $campaign_dir"
[[ -f "$ledger_path" ]] || ppi_die "no existe el ledger activo: $ledger_path"
[[ ! -e "$feature_dir" ]] ||
  ppi_die "existen features activas para el intento fallido; se requiere revisión manual"
[[ ! -e "$PPI_ACTIVE_LOCK" ]] ||
  ppi_die "existe un bloqueo de campaña activa: $PPI_ACTIVE_LOCK"
[[ ! -e "$archive_dir" && ! -e "$staging_dir" ]] ||
  ppi_die "ya existe el destino o un staging parcial: $archive_dir"
[[ -z "$(git -C "$PPI_REPO_ROOT" status --porcelain)" ]] ||
  ppi_die "el repositorio debe estar limpio antes de archivar evidencia"

jq -e --arg id "$campaign_id" '
  .campaign_id == $id
  and .status == "evidence_failed"
  and .purpose == "experiment"
  and .evidence.complete == false
' "$campaign_dir/manifest.json" >/dev/null ||
  ppi_die "el manifest no identifica un experimento fallido e incompleto"

jq -e --arg id "$campaign_id" '
  .campaign_id == $id and .status == "failed"
' "$ledger_path" >/dev/null ||
  ppi_die "el ledger no identifica el mismo intento como fallido"

(
  cd "$campaign_dir"
  /usr/bin/sha256sum --check SHA256SUMS >/dev/null
) || ppi_die "falló la verificación SHA256SUMS del bundle"

local_helper_sha="$(sha256sum "$PPI_REPO_ROOT/configs/sensor/ppi-pcap-control" | awk '{print $1}')"
remote_helper_sha="$(
  ppi_ssh "$PPI_SENSOR_IP" \
    "/usr/bin/sha256sum /usr/local/sbin/ppi-pcap-control" |
    awk '{print $1}'
)"
[[ "$remote_helper_sha" == "$local_helper_sha" ]] ||
  ppi_die "el helper remoto no coincide con el helper versionado"

if "$dry_run"; then
  jq -n \
    --arg campaign_id "$campaign_id" \
    --arg attempt_label "$attempt_label" \
    --arg local_destination "$archive_dir" \
    --arg remote_destination "$remote_archive_dir" \
    --arg helper_sha256 "$local_helper_sha" '
    {
      status: "dry_run_pass",
      campaign_id: $campaign_id,
      attempt_label: $attempt_label,
      local_destination: $local_destination,
      remote_destination: $remote_destination,
      helper_sha256: $helper_sha256
    }'
  exit 0
fi

remote_result="$(
  ppi_ssh "$PPI_SENSOR_IP" \
    "sudo -n /usr/local/sbin/ppi-pcap-control archive '$campaign_id' '$attempt_label'"
)"
jq -e --arg id "$campaign_id" --arg label "$attempt_label" '
  (.status == "archived" or .status == "already_archived")
  and .campaign_id == $id
  and .attempt_label == $label
' <<<"$remote_result" >/dev/null ||
  ppi_die "el Sensor no confirmó el archivado remoto"

ppi_ssh "$PPI_SENSOR_IP" \
  "cd '$remote_archive_dir' && /usr/bin/sha256sum --check -" \
  < "$campaign_dir/pcap-remote-SHA256SUMS" >/dev/null ||
  ppi_die "el PCAP remoto archivado no conserva sus hashes"

manifest_sha="$(sha256sum "$campaign_dir/manifest.json" | awk '{print $1}')"
bundle_sha_list_sha="$(sha256sum "$campaign_dir/SHA256SUMS" | awk '{print $1}')"
ledger_sha="$(sha256sum "$ledger_path" | awk '{print $1}')"
evidence_commit="$(jq -r '.git.commit' "$campaign_dir/manifest.json")"
archive_commit="$(git -C "$PPI_REPO_ROOT" rev-parse HEAD)"
archived_at="$(date --iso-8601=seconds)"

mkdir -p "$archive_parent"
mkdir "$staging_dir"
rollback_required=true

rollback_local() {
  exit_code=$?
  if "$rollback_required"; then
    if [[ -d "$staging_dir/campaign" && ! -e "$campaign_dir" ]]; then
      mv -- "$staging_dir/campaign" "$campaign_dir"
    fi
    if [[ -f "$staging_dir/ledger.json" && ! -e "$ledger_path" ]]; then
      mv -- "$staging_dir/ledger.json" "$ledger_path"
    fi
    rmdir "$staging_dir" 2>/dev/null || true
  fi
  exit "$exit_code"
}
trap rollback_local EXIT

mv -- "$campaign_dir" "$staging_dir/campaign"
mv -- "$ledger_path" "$staging_dir/ledger.json"

(
  cd "$staging_dir/campaign"
  /usr/bin/sha256sum --check SHA256SUMS >/dev/null
) || ppi_die "el bundle cambió durante el archivado local"
[[ "$(sha256sum "$staging_dir/ledger.json" | awk '{print $1}')" == "$ledger_sha" ]] ||
  ppi_die "el ledger cambió durante el archivado local"

jq -n \
  --arg archived_at "$archived_at" \
  --arg campaign_id "$campaign_id" \
  --arg attempt_label "$attempt_label" \
  --arg evidence_commit "$evidence_commit" \
  --arg archive_commit "$archive_commit" \
  --arg manifest_sha256 "$manifest_sha" \
  --arg bundle_sha_list_sha256 "$bundle_sha_list_sha" \
  --arg ledger_sha256 "$ledger_sha" \
  --arg original_campaign_path "$campaign_dir" \
  --arg original_ledger_path "$ledger_path" \
  --argjson remote "$remote_result" '
  {
    schema_version: "failed-attempt-archive-v1",
    status: "archived",
    archived_at: $archived_at,
    campaign_id: $campaign_id,
    attempt_label: $attempt_label,
    evidence_git_commit: $evidence_commit,
    archive_procedure_git_commit: $archive_commit,
    original_paths: {
      campaign: $original_campaign_path,
      ledger: $original_ledger_path
    },
    integrity: {
      manifest_sha256: $manifest_sha256,
      bundle_sha256sums_sha256: $bundle_sha_list_sha256,
      ledger_sha256: $ledger_sha256
    },
    remote: $remote
  }' > "$staging_dir/archive.json"

chmod 0600 "$staging_dir/archive.json"
mv -- "$staging_dir" "$archive_dir"
rollback_required=false
trap - EXIT

jq . "$archive_dir/archive.json"
