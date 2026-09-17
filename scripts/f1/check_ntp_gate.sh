#!/usr/bin/env bash
set -euo pipefail

# LC_ALL=C evita que awk formatee decimales con coma en locales como
# es_ES.UTF-8 (LC_NUMERIC), lo que rompía la validación de offset de
# check_timesyncd() para hosts sin chronyc (Kali) con un falso "offset NTP
# inválido" pese a un NTP realmente sincronizado.
export LC_ALL=C

readonly PPI_SSH_KEY="${PPI_SSH_KEY:-/home/m4rk/.ssh/id_ed25519_ppi_ansible}"
readonly PPI_SSH_USER="${PPI_SSH_USER:-useransible}"
readonly PPI_SENSOR_IP="${PPI_SENSOR_IP:-10.10.10.20}"
readonly PPI_SERVER_IP="${PPI_SERVER_IP:-10.10.10.30}"
readonly PPI_KALI_IP="${PPI_KALI_IP:-10.10.10.40}"
readonly PPI_CLIENT_IP="${PPI_CLIENT_IP:-10.10.10.50}"
readonly MAX_ABS_OFFSET_SECONDS="${PPI_NTP_MAX_ABS_OFFSET_SECONDS:-0.1}"

ssh_options=(
  -F /dev/null
  -i "$PPI_SSH_KEY"
  -o BatchMode=yes
  -o ConnectTimeout=8
)

die() {
  echo "ERROR: $*" >&2
  exit 1
}

remote() {
  local host="$1"
  shift
  ssh "${ssh_options[@]}" "$PPI_SSH_USER@$host" "$@"
}

check_offset() {
  local label="$1"
  local tracking="$2"
  local offset
  offset="$(awk -F: '/^System time/ {gsub(/^[[:space:]]+/, "", $2); print $2}' <<< "$tracking" |
    awk '{print $1}')"
  [[ "$offset" =~ ^[+-]?[0-9]+([.][0-9]+)?$ ]] || die "offset NTP inválido en $label"
  awk -v value="$offset" -v maximum="$MAX_ABS_OFFSET_SECONDS" \
    'BEGIN {if (value < 0) value = -value; exit !(value <= maximum)}' ||
    die "$label supera el offset máximo: $offset s > $MAX_ABS_OFFSET_SECONDS s"
  printf '%s_offset_seconds=%s\n' "$label" "$offset"
}

check_timesyncd() {
  local label="$1"
  local host="$2"
  local expected_source="$3"
  local source
  local status
  local raw_offset
  local value
  local unit
  local seconds

  source="$(remote "$host" 'timedatectl show-timesync --value -p ServerAddress')"
  [[ "$source" == "$expected_source" ]] ||
    die "$label no seleccionó $expected_source como fuente"
  status="$(remote "$host" 'timedatectl timesync-status')"
  grep -q '^[[:space:]]*Leap:[[:space:]]*normal$' <<< "$status" ||
    die "$label no tiene Leap normal"
  raw_offset="$(awk -F: '/^[[:space:]]*Offset:/ {
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2
  }' <<< "$status")"
  [[ "$raw_offset" =~ ^([+-]?[0-9]+([.][0-9]+)?)(ns|us|ms|s)$ ]] ||
    die "offset timesyncd inválido en $label: $raw_offset"
  value="${BASH_REMATCH[1]}"
  unit="${BASH_REMATCH[3]}"
  case "$unit" in
    ns) seconds="$(awk -v value="$value" 'BEGIN {printf "%.12f", value / 1000000000}')" ;;
    us) seconds="$(awk -v value="$value" 'BEGIN {printf "%.12f", value / 1000000}')" ;;
    ms) seconds="$(awk -v value="$value" 'BEGIN {printf "%.12f", value / 1000}')" ;;
    s) seconds="$value" ;;
    *) die "unidad timesyncd no soportada en $label" ;;
  esac
  check_offset "$label" "System time     : $seconds seconds fast of NTP time"
}

[[ -r "$PPI_SSH_KEY" ]] || die "no se puede leer la clave SSH"
[[ "$(timedatectl show --value -p Timezone)" == "America/Lima" ]] ||
  die "VM01 no usa America/Lima"
[[ "$(timedatectl show --value -p NTPSynchronized)" == "yes" ]] ||
  die "VM01 no está sincronizada"
vm01_tracking="$(chronyc tracking)"
grep -q '^Leap status[[:space:]]*:[[:space:]]*Normal$' <<< "$vm01_tracking" ||
  die "VM01 no tiene Leap status Normal"
check_offset vm01 "$vm01_tracking"

declare -A nodes=(
  [sensor]="$PPI_SENSOR_IP"
  [server]="$PPI_SERVER_IP"
  [kali]="$PPI_KALI_IP"
  [client]="$PPI_CLIENT_IP"
)

for node in sensor server kali client; do
  state="$(remote "${nodes[$node]}" \
    'timedatectl show --value -p Timezone; timedatectl show --value -p NTPSynchronized')"
  [[ "$(sed -n '1p' <<< "$state")" == "America/Lima" ]] ||
    die "$node no usa America/Lima"
  [[ "$(sed -n '2p' <<< "$state")" == "yes" ]] ||
    die "$node no está sincronizado"
  if remote "${nodes[$node]}" 'command -v chronyc >/dev/null'; then
    tracking="$(remote "${nodes[$node]}" 'chronyc tracking')"
    grep -q '^Leap status[[:space:]]*:[[:space:]]*Normal$' <<< "$tracking" ||
      die "$node no tiene Leap status Normal"
    check_offset "$node" "$tracking"
  else
    check_timesyncd "$node" "${nodes[$node]}" "$PPI_SENSOR_IP"
  fi
done

sensor_sources="$(remote "$PPI_SENSOR_IP" 'chronyc -n sources')"
awk '$1 == "^*" && $2 == "10.10.10.10" {found=1} END {exit !found}' \
  <<< "$sensor_sources" ||
  die "el Sensor no seleccionó VM01 como fuente"

for node in server kali client; do
  if remote "${nodes[$node]}" 'command -v chronyc >/dev/null'; then
    sources="$(remote "${nodes[$node]}" 'chronyc -n sources')"
    awk '$1 == "^*" && $2 == "10.10.10.20" {found=1} END {exit !found}' \
      <<< "$sources" ||
      die "$node no seleccionó el Sensor como fuente"
  fi
done

echo "NTP_GATE=PASS"
