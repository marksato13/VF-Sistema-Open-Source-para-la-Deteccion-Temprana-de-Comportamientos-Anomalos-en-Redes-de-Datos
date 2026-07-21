#!/usr/bin/env bash
set -euo pipefail

TARGET_IP="${PPI_TARGET_IP:-10.30.0.10}"

usage() {
  echo "Uso: $0 {http|https|dns-valid|dns-nxdomain|iperf-tcp|iperf-udp} argumentos" >&2
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
  *) usage ;;
esac
