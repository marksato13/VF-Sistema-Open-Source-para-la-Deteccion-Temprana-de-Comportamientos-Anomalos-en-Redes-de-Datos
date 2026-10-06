#!/usr/bin/env bash
set -euo pipefail

# Evaluación únicamente contra la DMZ PPI autorizada; no acepta destinos externos.
TARGET="${PPI_TARGET_IP:-10.30.0.10}"
[[ "$TARGET" == 10.30.0.10 || "$TARGET" == 10.30.0.11 || "$TARGET" == 10.30.0.12 ]] || {
  echo "ERROR: destino fuera de la DMZ PPI" >&2; exit 2;
}
scenario="${1:-}"
shift || true
case "$scenario" in
  tcp-syn-rate)
    count="${1:-10}"; case "$count" in 10|25|50) ;; *) echo "ERROR: conteo permitido 10,25,50" >&2; exit 2;; esac
    # nping --tcp requiere sockets crudos (root); useransible no tiene sudo en
    # Kali. Se sustituye por intentos de conexión reales y rápidos (cada uno
    # envía un SYN igual que nping, solo que vía connect() en vez de un
    # paquete crudo) alternando puerto abierto/cerrado, sin privilegios.
    ports=(80 443 65000)
    for ((i=1; i<=count; i++)); do
      port="${ports[$(( (i - 1) % ${#ports[@]} ))]}"
      timeout 1 bash -c "exec 3<>/dev/tcp/$TARGET/$port" 2>/dev/null && result=connected || result=refused_or_timeout
      exec 3<&- 2>/dev/null || true
      exec 3>&- 2>/dev/null || true
      printf '{"scenario":"tcp-syn-rate","attempt":%d,"port":%d,"result":"%s"}\n' "$i" "$port" "$result"
      sleep 0.1
    done
    ;;
  tcp-port-scan)
    exec nmap --max-retries 1 --host-timeout 20s -Pn -p 80,443,65000 "$TARGET" ;;
  udp-probe)
    count="${1:-10}"; case "$count" in 10|25|50) ;; *) echo "ERROR: conteo permitido 10,25,50" >&2; exit 2;; esac
    exec nping --udp -p 53 --count "$count" --rate 5 "$TARGET" ;;
  port-scan-wide)
    range="${1:-1-1000}"; case "$range" in 1-1000|1-5000) ;; *) echo "ERROR: rango permitido 1-1000 o 1-5000" >&2; exit 2;; esac
    exec nmap --max-retries 1 --host-timeout 60s -Pn -p "$range" "$TARGET" ;;
  password-spray)
    attempts="${1:-10}"; case "$attempts" in 10|20|50) ;; *) echo "ERROR: intentos permitidos 10,20,50" >&2; exit 2;; esac
    passwords=(admin123 password123 letmein123 qwerty123 welcome123 changeme123 spring2026 summer2026 test1234 demo12345)
    for ((i=1; i<=attempts; i++)); do
      pw="${passwords[$(( (i - 1) % ${#passwords[@]} ))]}"
      code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        -H 'Content-Type: application/json' -X POST \
        --data "{\"username\":\"demo\",\"password\":\"$pw\"}" \
        "http://$TARGET/api/login")"
      printf '{"scenario":"password-spray","attempt":%d,"http_code":"%s"}\n' "$i" "$code"
      sleep 0.1
    done
    ;;
  dns-entropy)
    count="${1:-20}"; case "$count" in 10|20|50) ;; *) echo "ERROR: conteo permitido 10,20,50" >&2; exit 2;; esac
    for ((i=1; i<=count; i++)); do
      label="$(head -c 16 /dev/urandom | base32 | tr -d '=' | tr 'A-Z' 'a-z' | head -c 12)"
      dig +short "@$TARGET" "${label}.ppi.lab" A || true
    done
    ;;
  *) echo "Uso: $0 {tcp-syn-rate|tcp-port-scan|udp-probe|port-scan-wide|password-spray|dns-entropy} [args]" >&2; exit 2;;
esac
