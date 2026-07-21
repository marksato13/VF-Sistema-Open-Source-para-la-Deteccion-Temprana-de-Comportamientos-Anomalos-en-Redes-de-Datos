#!/usr/bin/env bash

readonly CAMPAIGN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PPI_REPO_ROOT="$(cd "$CAMPAIGN_SCRIPT_DIR/../.." && pwd)"
readonly PPI_CAMPAIGNS_DIR="$PPI_REPO_ROOT/artifacts/campaigns"
readonly PPI_ACTIVE_LOCK="$PPI_CAMPAIGNS_DIR/.active"
readonly PPI_SSH_KEY="${PPI_SSH_KEY:-/home/m4rk/.ssh/id_ed25519_ppi_ansible}"
readonly PPI_SSH_USER="${PPI_SSH_USER:-useransible}"
readonly PPI_SENSOR_IP="${PPI_SENSOR_IP:-10.10.10.20}"
readonly PPI_SERVER_IP="${PPI_SERVER_IP:-10.10.10.30}"
readonly PPI_KALI_IP="${PPI_KALI_IP:-10.10.10.40}"
readonly PPI_CLIENT_IP="${PPI_CLIENT_IP:-10.10.10.50}"

PPI_SSH_OPTIONS=(
  -i "$PPI_SSH_KEY"
  -o BatchMode=yes
  -o ConnectTimeout=8
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=3
)

ppi_die() {
  echo "ERROR: $*" >&2
  exit 1
}

ppi_validate_id() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$ ]] ||
    ppi_die "ID inválido; use entre 3 y 64 caracteres alfanuméricos, punto, guion o guion bajo"
}

ppi_ssh() {
  local host="$1"
  shift
  ssh "${PPI_SSH_OPTIONS[@]}" "$PPI_SSH_USER@$host" "$@"
}

ppi_campaign_dir() {
  printf '%s/%s\n' "$PPI_CAMPAIGNS_DIR" "$1"
}
