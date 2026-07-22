#!/usr/bin/env bash
set -euo pipefail

TARGET_IP="${PPI_TARGET_IP:-10.30.0.10}"
[[ "$TARGET_IP" == "10.30.0.10" ]] || {
  echo "ERROR: destino fuera de la topología F1 autorizada" >&2
  exit 2
}

usage() {
  echo "Uso: $0 {http|https|http-concurrent|http-multi|http-missing|https-sessions|dns-valid|dns-nxdomain|dns-mixed|ping|tcp-refused|iperf-tcp|iperf-udp|mixed-light} argumentos" >&2
  exit 2
}

require_count() {
  [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 1000 )) || {
    echo "ERROR: el conteo debe estar entre 1 y 1000" >&2
    exit 2
  }
}

require_duration() {
  case "$1" in 5|10|20|30) ;; *) echo "ERROR: duración permitida: 5, 10, 20 o 30 s" >&2; exit 2;; esac
}

scenario="${1:-}"
shift || true

case "$scenario" in
  http|https)
    size="${1:-}"
    rate="${2:-20M}"
    case "$size" in 10MB|100MB|500MB|1GB) ;; *) echo "ERROR: tamaño permitido: 10MB, 100MB, 500MB o 1GB" >&2; exit 2;; esac
    case "$rate" in 2M|5M|10M|20M) ;; *) echo "ERROR: límite HTTP permitido: 2M, 5M, 10M o 20M bytes/s" >&2; exit 2;; esac
    curl_args=(--fail --silent --show-error --output /dev/null
      --limit-rate "$rate"
      --write-out '{"http_code":%{http_code},"bytes":%{size_download},"seconds":%{time_total},"speed_Bps":%{speed_download}}\n')
    [[ "$scenario" == https ]] && curl_args+=(--insecure)
    curl "${curl_args[@]}" "$scenario://$TARGET_IP/files/$size.bin"
    ;;
  http-concurrent)
    concurrency="${1:-}"
    size="${2:-}"
    rate="${3:-}"
    case "$concurrency:$size:$rate" in
      2:100MB:10M|4:100MB:5M|8:100MB:2M) ;;
      *) echo "ERROR: combinaciones permitidas: 2/100MB/10M, 4/100MB/5M, 8/100MB/2M" >&2; exit 2 ;;
    esac
    temp_dir="$(mktemp -d)"
    trap 'rm -rf -- "$temp_dir"' EXIT
    pids=()
    for ((i=1; i<=concurrency; i++)); do
      curl --fail --silent --show-error --output /dev/null \
        --limit-rate "$rate" \
        --write-out '{"http_code":%{http_code},"bytes":%{size_download},"seconds":%{time_total},"speed_Bps":%{speed_download}}\n' \
        "http://$TARGET_IP/files/$size.bin" > "$temp_dir/result-$i.json" &
      pids+=("$!")
    done
    failed=0
    for pid in "${pids[@]}"; do
      wait "$pid" || failed=$((failed + 1))
    done
    (( failed == 0 )) || { echo "ERROR: fallaron $failed descargas" >&2; exit 1; }
    jq -s --argjson expected "$concurrency" \
      '{scenario:"http-concurrent",expected:$expected,completed:length,results:.}' \
      "$temp_dir"/result-*.json
    ;;
  http-multi)
    requests_per_target="${1:-}"
    case "$requests_per_target" in
      1|5) ;;
      *) echo "ERROR: solicitudes por destino permitidas: 1 o 5" >&2; exit 2 ;;
    esac
    for target in 10.30.0.10 10.30.0.11 10.30.0.12; do
      for ((i=1; i<=requests_per_target; i++)); do
        code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
          "http://$target/health")"
        [[ "$code" == 200 ]] || {
          echo "ERROR: $target devolvió HTTP $code" >&2
          exit 1
        }
        printf '{"target":"%s","request":%d,"http_code":200}\n' "$target" "$i"
        sleep 0.1
      done
    done
    ;;
  http-missing)
    count="${1:-}"
    require_count "$count"
    (( count <= 50 )) || { echo "ERROR: máximo 50 respuestas 404" >&2; exit 2; }
    for ((i=1; i<=count; i++)); do
      code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        "http://$TARGET_IP/recurso-inexistente-$i")"
      [[ "$code" == 404 ]] || { echo "ERROR: se esperaba 404 y se obtuvo $code" >&2; exit 1; }
      printf '{"request":%d,"http_code":404}\n' "$i"
      sleep 0.2
    done
    ;;
  https-sessions)
    count="${1:-}"
    require_count "$count"
    (( count <= 100 )) || { echo "ERROR: máximo 100 sesiones TLS" >&2; exit 2; }
    for ((i=1; i<=count; i++)); do
      code="$(curl --insecure --silent --show-error --output /dev/null --write-out '%{http_code}' \
        "https://$TARGET_IP/health")"
      [[ "$code" == 200 ]] || { echo "ERROR: HTTPS devolvió $code" >&2; exit 1; }
      printf '{"session":%d,"http_code":200}\n' "$i"
      sleep 0.1
    done
    ;;
  dns-valid|dns-nxdomain)
    count="${1:-}"
    require_count "$count"
    for ((i=1; i<=count; i++)); do
      if [[ "$scenario" == dns-valid ]]; then
        dig +short "@$TARGET_IP" server.ppi.lab A
      else
        dig +short "@$TARGET_IP" "inexistente-$i.ppi.lab" A
      fi
    done
    ;;
  dns-mixed)
    valid_count="${1:-}"
    nxdomain_count="${2:-}"
    require_count "$valid_count"
    require_count "$nxdomain_count"
    (( valid_count + nxdomain_count <= 500 )) || { echo "ERROR: máximo 500 consultas mixtas" >&2; exit 2; }
    for ((i=1; i<=valid_count; i++)); do
      dig +short "@$TARGET_IP" server.ppi.lab A
    done
    for ((i=1; i<=nxdomain_count; i++)); do
      dig +short "@$TARGET_IP" "error-legitimo-$i.ppi.lab" A
    done
    ;;
  ping)
    count="${1:-}"
    interval="${2:-}"
    case "$count" in 10|50|100) ;; *) echo "ERROR: ping count permitido: 10, 50 o 100" >&2; exit 2;; esac
    case "$interval" in 0.2|0.5|1) ;; *) echo "ERROR: intervalo ping permitido: 0.2, 0.5 o 1 s" >&2; exit 2;; esac
    ping -n -c "$count" -i "$interval" "$TARGET_IP"
    ;;
  tcp-refused)
    count="${1:-}"
    case "$count" in 3|5|10) ;; *) echo "ERROR: intentos permitidos: 3, 5 o 10" >&2; exit 2;; esac
    refused=0
    for ((i=1; i<=count; i++)); do
      if timeout 2 bash -c "exec 3<>/dev/tcp/$TARGET_IP/65000" 2>/dev/null; then
        echo "ERROR: el puerto de control 65000 respondió" >&2
        exit 1
      else
        refused=$((refused + 1))
      fi
      sleep 0.5
    done
    printf '{"scenario":"tcp-refused","attempts":%d,"expected_refusals":%d}\n' "$count" "$refused"
    ;;
  iperf-tcp)
    rate="${1:-}"
    duration="${2:-}"
    case "$rate" in 10M|25M|50M|100M|200M) ;; *) echo "ERROR: bitrate TCP permitido: 10M, 25M, 50M, 100M o 200M" >&2; exit 2;; esac
    require_duration "$duration"
    iperf3 -c "$TARGET_IP" -b "$rate" -t "$duration" -J
    ;;
  iperf-udp)
    rate="${1:-}"
    duration="${2:-}"
    case "$rate" in 1M|10M|25M|50M) ;; *) echo "ERROR: bitrate UDP permitido: 1M, 10M, 25M o 50M" >&2; exit 2;; esac
    require_duration "$duration"
    iperf3 -c "$TARGET_IP" -u -b "$rate" -t "$duration" -J
    ;;
  mixed-light)
    [[ $# == 0 ]] || { echo "ERROR: mixed-light no acepta argumentos" >&2; exit 2; }
    temp_dir="$(mktemp -d)"
    trap 'rm -rf -- "$temp_dir"' EXIT
    "$0" http 100MB 5M > "$temp_dir/http.json" & http_pid=$!
    "$0" iperf-tcp 50M 10 > "$temp_dir/iperf.json" & iperf_pid=$!
    "$0" dns-valid 20 > "$temp_dir/dns.txt" & dns_pid=$!
    failed=0
    wait "$http_pid" || failed=$((failed + 1))
    wait "$iperf_pid" || failed=$((failed + 1))
    wait "$dns_pid" || failed=$((failed + 1))
    (( failed == 0 )) || { echo "ERROR: fallaron $failed componentes mixtos" >&2; exit 1; }
    dns_answers="$(wc -l < "$temp_dir/dns.txt")"
    jq -n \
      --slurpfile http "$temp_dir/http.json" \
      --slurpfile iperf "$temp_dir/iperf.json" \
      --argjson dns_answers "$dns_answers" \
      '{scenario:"mixed-light",http:$http[0],iperf:$iperf[0],dns_answers:$dns_answers}'
    ;;
  *) usage ;;
esac
