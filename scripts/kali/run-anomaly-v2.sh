#!/usr/bin/env bash
set -euo pipefail

# Evaluación únicamente contra la DMZ PPI autorizada; no acepta destinos externos.
TARGET="${PPI_TARGET_IP:-10.30.0.10}"
[[ "$TARGET" == 10.30.0.10 || "$TARGET" == 10.30.0.11 || "$TARGET" == 10.30.0.12 ]] || {
  echo "ERROR: destino fuera de la DMZ PPI" >&2; exit 2;
}
scenario="${1:-}"
case "$scenario" in
  tcp-syn-rate)
    count="${2:-10}"; case "$count" in 10|25|50) ;; *) echo "ERROR: conteo permitido 10,25,50" >&2; exit 2;; esac
    exec nping --tcp --flags syn -p 80,443 --count "$count" --rate 10 "$TARGET" ;;
  tcp-port-scan)
    exec nmap --max-retries 1 --host-timeout 20s -Pn -p 80,443,65000 "$TARGET" ;;
  udp-probe)
    count="${2:-10}"; case "$count" in 10|25|50) ;; *) echo "ERROR: conteo permitido 10,25,50" >&2; exit 2;; esac
    exec nping --udp -p 53 --count "$count" --rate 5 "$TARGET" ;;
  *) echo "Uso: $0 {tcp-syn-rate|tcp-port-scan|udp-probe} [count]" >&2; exit 2;;
esac
