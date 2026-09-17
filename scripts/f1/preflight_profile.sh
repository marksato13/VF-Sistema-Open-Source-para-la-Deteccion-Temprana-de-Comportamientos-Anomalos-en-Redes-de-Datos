#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
readonly ARTIFACTS_ROOT="${PPI_ARTIFACTS_ROOT:-/srv/ppi-evidence/artifacts}"
readonly PYTHON="${PPI_PYTHON:-$REPO/.venv/bin/python}"
readonly SSH_KEY="${PPI_SSH_KEY:-/home/m4rk/.ssh/id_ed25519_ppi_ansible}"
readonly SSH_USER="${PPI_SSH_USER:-useransible}"
readonly PREFLIGHT_DIR="$ARTIFACTS_ROOT/preflight"
readonly PREFLIGHT_LOCK="$PREFLIGHT_DIR/.active"

readonly SENSOR_IP=10.10.10.20
readonly SERVER_IP=10.10.10.30
readonly KALI_IP=10.10.10.40
readonly CLIENT_IP=10.10.10.50

usage() {
  echo "Uso: $0 PERFIL REPETICION" >&2
  exit 2
}

(( $# == 2 )) || usage
readonly PROFILE="$1"
readonly REPETITION="$2"
[[ "$PROFILE" =~ ^[A-Z0-9][A-Z0-9-]{2,47}$ ]] || {
  echo "ERROR: perfil inválido" >&2
  exit 2
}
[[ "$REPETITION" =~ ^[1-5]$ ]] || {
  echo "ERROR: repetición inválida" >&2
  exit 2
}
[[ "$ARTIFACTS_ROOT" == /* ]] || {
  echo "ERROR: PPI_ARTIFACTS_ROOT debe ser absoluto" >&2
  exit 2
}
[[ -x "$PYTHON" ]] || { echo "ERROR: intérprete ausente: $PYTHON" >&2; exit 2; }
[[ -r "$SSH_KEY" ]] || { echo "ERROR: clave SSH ilegible: $SSH_KEY" >&2; exit 2; }

readonly CAMPAIGN_ID="F1N-$PROFILE-R$(printf '%02d' "$REPETITION")"
readonly FINAL_LOG="$PREFLIGHT_DIR/$CAMPAIGN_ID.log"
install -d -m 0700 "$PREFLIGHT_DIR"
[[ ! -e "$FINAL_LOG" ]] || {
  echo "ERROR: el preflight oficial ya existe: $FINAL_LOG" >&2
  exit 3
}
if ! mkdir -m 0700 "$PREFLIGHT_LOCK" 2>/dev/null; then
  echo "ERROR: ya existe otro preflight activo: $PREFLIGHT_LOCK" >&2
  exit 3
fi
temporary_log="$(mktemp "$PREFLIGHT_DIR/.$CAMPAIGN_ID.XXXXXX")"
chmod 0600 "$temporary_log"
completed=false

exec 3>&1 4>&2

emit() {
  printf '%s\n' "$*" | tee -a "$temporary_log" >&3
}

timestamp() {
  date --iso-8601=ns
}

finalize() {
  local rc=$?
  trap - EXIT
  if [[ ! -f "$temporary_log" ]]; then
    rmdir "$PREFLIGHT_LOCK" 2>/dev/null || true
    printf 'ERROR: desapareció el log temporal del preflight\n' >&4
    exit 1
  fi
  if [[ "$completed" == true && $rc -eq 0 ]]; then
    if ! rmdir "$PREFLIGHT_LOCK"; then
      failed_log="$PREFLIGHT_DIR/$CAMPAIGN_ID.failed-$(date +%Y%m%dT%H%M%S%N).log"
      mv -- "$temporary_log" "$failed_log"
      chmod 0600 "$failed_log"
      printf 'ERROR: no se pudo liberar el lock; log=%s\n' "$failed_log" >&4
      exit 1
    fi
    mv -- "$temporary_log" "$FINAL_LOG"
    chmod 0600 "$FINAL_LOG"
    printf 'PREFLIGHT_LOG=%s\nPREFLIGHT_SHA256=%s\n' \
      "$FINAL_LOG" "$(sha256sum "$FINAL_LOG" | awk '{print $1}')" >&3
    exit 0
  fi
  failed_log="$PREFLIGHT_DIR/$CAMPAIGN_ID.failed-$(date +%Y%m%dT%H%M%S%N).log"
  mv -- "$temporary_log" "$failed_log"
  chmod 0600 "$failed_log"
  rmdir "$PREFLIGHT_LOCK" 2>/dev/null || true
  printf 'PREFLIGHT_FAILED_LOG=%s\n' "$failed_log" >&4
  exit "${rc:-1}"
}
trap finalize EXIT

fail() {
  emit "$(timestamp) FAIL ${current_gate:-UNKNOWN}: $*"
  return 1
}

ssh_options=(
  -i "$SSH_KEY"
  -o BatchMode=yes
  -o ConnectTimeout=8
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=3
)

remote() {
  local host="$1"
  shift
  ssh "${ssh_options[@]}" "$SSH_USER@$host" "$@"
}

run_gate() {
  current_gate="$1"
  shift
  "$@"
  emit "$(timestamp) PASS $current_gate"
}

gate_git() {
  [[ -z "$(git -C "$REPO" status --porcelain)" ]] || fail "árbol Git sucio"
  local counts behind ahead
  counts="$(git -C "$REPO" rev-list --left-right --count HEAD...@{upstream})" ||
    fail "no se pudo comparar upstream"
  read -r behind ahead <<< "$counts"
  [[ "$behind" == 0 && "$ahead" == 0 ]] || fail "rama no sincronizada: behind=$behind ahead=$ahead"
  emit "GIT_COMMIT=$(git -C "$REPO" rev-parse HEAD)"
}

plan_json=""
gate_contract_storage() {
  plan_json="$(
    PPI_ARTIFACTS_ROOT="$ARTIFACTS_ROOT" "$PYTHON" \
      "$SCRIPT_DIR/run_matrix_profile.py" \
      --profile "$PROFILE" --repetition "$REPETITION" --dry-run
  )" || fail "dry-run rechazado"
  jq -e \
    --arg id "$CAMPAIGN_ID" \
    --argjson repetition "$REPETITION" '
      .campaign_id == $id and
      .repetition == $repetition and
      .purpose == "experiment" and
      .partition == ({"1":"train","2":"train","3":"train","4":"validation","5":"test"}[($repetition|tostring)]) and
      .matrix_storage_gate_pass == true and
      .official_storage.gate_pass == true and
      .pre_capture_quiet_seconds == 70 and
      .warmup_seconds == 60 and
      .settle_seconds == 9 and
      .cooldown_seconds == 30
    ' <<< "$plan_json" >/dev/null || fail "plan fuera del contrato"
  for path in \
    "$ARTIFACTS_ROOT/campaigns/$CAMPAIGN_ID" \
    "$ARTIFACTS_ROOT/features/$CAMPAIGN_ID" \
    "$ARTIFACTS_ROOT/g6-ledger/$CAMPAIGN_ID.json"; do
    [[ ! -e "$path" ]] || fail "ya existe salida: $path"
  done
  [[ ! -e "$ARTIFACTS_ROOT/campaigns/.active" ]] || fail "existe lock de campaña"
  emit "PARTITION=$(jq -r .partition <<< "$plan_json")"
  emit "MATRIX_SHA256=$(jq -r .matrix_sha256 <<< "$plan_json")"
  emit "ARGS_SHA256=$(jq -r .scenario_args_sha256 <<< "$plan_json")"
}

gate_capacity_ntp() {
  local available ntp_output
  available="$(df --output=avail -B1 "$ARTIFACTS_ROOT" | awk 'NR == 2 {print $1}')"
  [[ "$available" =~ ^[0-9]+$ && "$available" -ge 3221225472 ]] ||
    fail "menos de 3 GiB disponibles"
  ntp_output="$($SCRIPT_DIR/check_ntp_gate.sh)" || fail "gate NTP rechazado"
  grep -q '^NTP_GATE=PASS$' <<< "$ntp_output" || fail "NTP_GATE no pasó"
  emit "$ntp_output"
  emit "AVAILABLE_BYTES=$available"
}

declare -A node_ips=(
  [sensor]="$SENSOR_IP"
  [server]="$SERVER_IP"
  [kali]="$KALI_IP"
  [client]="$CLIENT_IP"
)
declare -A external_macs=(
  [sensor]="00:0c:29:f7:15:80"
  [server]="00:0c:29:15:ad:a7"
  [kali]="00:0c:29:52:db:60"
  [client]="00:0c:29:c5:ed:66"
)

gate_ids_ssh() {
  local node identity
  for node in sensor server kali client; do
    identity="$(remote "${node_ips[$node]}" 'id -un')" || fail "SSH falló en $node"
    [[ "$identity" == "$SSH_USER" ]] || fail "identidad inesperada en $node: $identity"
    emit "SSH_$node=$identity@${node_ips[$node]}"
  done
}

gate_isolation_bypass() {
  local node links mac external_ip
  for node in sensor server kali client; do
    mac="${external_macs[$node]}"
    links="$(remote "${node_ips[$node]}" 'ip -j link')" || fail "no se pudo leer links de $node"
    jq -e --arg mac "$mac" '
      any(.[];
        ((.address // "") | ascii_downcase) == ($mac | ascii_downcase) and
        .operstate == "DOWN" and
        ((.flags // []) | index("LOWER_UP")) == null)
      ' <<< "$links" >/dev/null || fail "NIC externa conectada/no coincide en $node"
    emit "EXTERNAL_NIC_$node=$mac DOWN"
  done
  for external_ip in 172.17.25.111 172.17.25.112 172.17.25.113 172.17.25.114; do
    if ping -n -c 1 -W 1 "$external_ip" >/dev/null 2>&1; then
      fail "bypass ICMP alcanzable: $external_ip"
    fi
    if timeout 2 bash -c "exec 3<>/dev/tcp/$external_ip/22" >/dev/null 2>&1; then
      fail "bypass TCP/22 alcanzable: $external_ip"
    fi
  done
}

gate_routes() {
  local output
  output="$(remote "$CLIENT_IP" 'ip route get 10.30.0.10')" || fail "ruta Cliente falló"
  grep -q 'via 10.20.0.1' <<< "$output" || fail "Cliente no enruta DMZ por Sensor"
  output="$(remote "$KALI_IP" 'ip route get 10.30.0.10')" || fail "ruta Kali falló"
  grep -q 'via 10.20.0.1' <<< "$output" || fail "Kali no enruta DMZ por Sensor"
  output="$(remote "$SERVER_IP" 'ip route get 10.20.0.20')" || fail "retorno Servidor falló"
  grep -q 'via 10.30.0.1' <<< "$output" || fail "Servidor no retorna por Sensor"
  [[ "$(remote "$SENSOR_IP" 'sysctl -n net.ipv4.ip_forward')" == 1 ]] ||
    fail "ip_forward desactivado en Sensor"
}

gate_suricata_capture() {
  local metrics pcap_status tcpdump_rc
  metrics="$(remote "$SENSOR_IP" 'sudo -n /usr/local/sbin/ppi-suricata-metrics')" ||
    fail "métricas Suricata fallaron"
  jq -e '
    .suricata.service_state == "active" and
    .suricata.capture.kernel_drops == 0 and
    .suricata.capture.kernel_ifdrops == 0 and
    .suricata.decoder_invalid == 0 and
    .suricata.alert_queue_overflow == 0
    ' <<< "$metrics" >/dev/null || fail "Suricata no está limpio"
  if remote "$SENSOR_IP" 'pgrep -x tcpdump' >/dev/null 2>&1; then
    fail "tcpdump ya está activo"
  else
    tcpdump_rc=$?
    [[ "$tcpdump_rc" == 1 ]] || fail "no se pudo verificar tcpdump en Sensor: rc=$tcpdump_rc"
  fi
  printf -v quoted_id '%q' "$CAMPAIGN_ID"
  pcap_status="$(remote "$SENSOR_IP" "sudo -n /usr/local/sbin/ppi-pcap-control status $quoted_id")" ||
    fail "no se pudo consultar captura"
  [[ "$(jq -r .status <<< "$pcap_status")" == inactive ]] || fail "captura no inactiva"
  remote "$SENSOR_IP" "test ! -e /var/lib/ppi-captures/$quoted_id" ||
    fail "ya existe PCAP remoto para el ID"
  emit "SURICATA_COUNTERS=clean"
}

gate_services_listener() {
  local services client_iperf server_iperf listener_count kali_probe_rc
  services="$(remote "$SERVER_IP" '
    for unit in nginx dnsmasq ppi-server-firewall ppi-iperf3; do
      printf "%s=" "$unit"; systemctl is-active "$unit"
    done
  ')" || fail "servicios del Servidor no están activos"
  grep -q '^nginx=active$' <<< "$services" || fail "nginx no activo"
  grep -q '^dnsmasq=active$' <<< "$services" || fail "dnsmasq no activo"
  grep -q '^ppi-server-firewall=active$' <<< "$services" || fail "firewall no activo"
  grep -q '^ppi-iperf3=active$' <<< "$services" || fail "iperf3 no activo"
  listener_count="$(remote "$SERVER_IP" "ss -H -ltn 'sport = :5201' | wc -l")" ||
    fail "no se pudo contar listener iperf3"
  [[ "$listener_count" == 1 ]] || fail "se esperaba un listener iperf3, observado=$listener_count"
  if remote "$KALI_IP" "timeout 2 bash -c 'exec 3<>/dev/tcp/10.30.0.10/5201'" >/dev/null 2>&1; then
    fail "Kali alcanzó iperf3, firewall inválido"
  else
    kali_probe_rc=$?
    [[ "$kali_probe_rc" == 1 || "$kali_probe_rc" == 124 ]] ||
      fail "no se pudo verificar el bloqueo Kali→iperf3: rc=$kali_probe_rc"
  fi
  remote "$CLIENT_IP" "timeout 2 bash -c 'exec 3<>/dev/tcp/10.30.0.10/5201'" >/dev/null 2>&1 ||
    fail "Cliente no alcanza iperf3"
  client_iperf="$(remote "$CLIENT_IP" 'iperf3 --version | head -n1')" || fail "iperf Cliente ausente"
  server_iperf="$(remote "$SERVER_IP" 'iperf3 --version | head -n1')" || fail "iperf Servidor ausente"
  [[ "$client_iperf" == "$server_iperf" ]] || fail "versiones iperf distintas"
  emit "$services"
  emit "CLIENT_IPERF=$client_iperf"
  emit "SERVER_IPERF=$server_iperf"
}

gate_probes_generator() {
  local http_code dns_answer local_sha remote_sha
  http_code="$(remote "$CLIENT_IP" \
    "curl -sS -o /dev/null -w '%{http_code}' http://10.30.0.10/health")" ||
    fail "probe HTTP falló"
  [[ "$http_code" == 200 ]] || fail "probe HTTP=$http_code"
  dns_answer="$(remote "$CLIENT_IP" 'dig +short @10.30.0.10 server.ppi.lab A')" ||
    fail "probe DNS falló"
  [[ "$dns_answer" == 10.30.0.10 ]] || fail "probe DNS inesperado: $dns_answer"
  remote "$CLIENT_IP" 'ping -n -c 2 -W 2 10.30.0.10' >/dev/null || fail "probe ICMP falló"
  local_sha="$(sha256sum "$SCRIPT_DIR/run-benign.sh" | awk '{print $1}')"
  remote_sha="$(remote "$CLIENT_IP" 'sha256sum /home/useransible/bin/ppi-run-benign' | awk '{print $1}')" ||
    fail "hash remoto del generador falló"
  [[ "$local_sha" == "$remote_sha" ]] || fail "generador remoto no coincide"
  emit "PROBES=HTTP200 DNS10.30.0.10 ICMP2/2"
  emit "GENERATOR_SHA256=$local_sha"
}

emit "PREFLIGHT_STARTED_AT=$(timestamp)"
run_gate GIT gate_git
run_gate CONTRACT_STORAGE gate_contract_storage
run_gate CAPACITY_NTP gate_capacity_ntp
run_gate IDS_SSH gate_ids_ssh
run_gate ISOLATION_BYPASS gate_isolation_bypass
run_gate ROUTES gate_routes
run_gate SURICATA_CAPTURE gate_suricata_capture
run_gate SERVICES_LISTENER gate_services_listener
run_gate PROBES_GENERATOR gate_probes_generator
emit "PREFLIGHT_ENDED_AT=$(timestamp)"
emit "FULL_CONTIGUOUS_PREFLIGHT=PASS"
completed=true
