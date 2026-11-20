#!/usr/bin/env bash
# Instalación, aceptación y reversión del lado BASTIÓN de D5 sin reinicio (propuesta; NO ejecutada en el laboratorio). Se ejecuta como `gadmin` en el bastión.
# SECO POR OMISIÓN (sin --aplicar solo imprime). No necesita sudo.
# Uso: cf_d5_bastion.sh {instalar|aceptar|revertir|clave} [--aplicar]
#   clave     genera el par DEDICADO ~/.ssh/cyberflow-d5-sensor (si no existe) e imprime la PÚBLICA para instalarla en el Sensor1 (no hace falta ninguna clave existente del laboratorio)
#   instalar  verifica SHA256SUMS, copia los artefactos, deriva d5_episodio_banco.py del d5_episodio.py existente y FIJA la clave de huésped del Sensor1 desde CF_HOSTKEY
#             (clave pública del huésped obtenida FUERA de banda y comparada por huella; nunca `ssh-keyscan` a ciegas)
# Variables: CF_PAQUETE, CF_HOME (/home/gadmin), CF_HOSTKEY (obligatoria en instalar: «ssh-ed25519 AAAA…»), CF_SENSOR_HOSTPORT (por omisión 10.10.60.11)
set -uo pipefail
ACCION="${1:-}"; shift || true
APLICAR=0
for a in "$@"; do case "$a" in --aplicar) APLICAR=1;; *) echo "opción desconocida: $a" >&2; exit 2;; esac; done
CF_HOME="${CF_HOME:-/home/gadmin}"; PQ="${CF_PAQUETE:-$CF_HOME/cf-b/paquete-despliegue}"; HERR="$CF_HOME/cf-b/herramientas"
CLAVE="$CF_HOME/.ssh/cyberflow-d5-sensor"; KH="$CF_HOME/.ssh/known_hosts_d5"; SENSOR="${CF_SENSOR_HOSTPORT:-10.10.60.11}"; RESP="$CF_HOME/cf-b/respaldo-d5"
run() { if [ "$APLICAR" = 1 ]; then "$@"; else echo "[seco] $*"; fi; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
ok=0; mal=0
c() { if [ "$2" = 0 ]; then echo "OK    $1"; ok=$((ok+1)); else echo "FALLA $1"; mal=$((mal+1)); fi; }
ARTEFACTOS="transporte_bastion.py lanzador_puerta_banco.py hacer_d5_episodio_banco.py"

clave() {
  run mkdir -p "$CF_HOME/.ssh"; run chmod 700 "$CF_HOME/.ssh"
  if [ -e "$CLAVE" ]; then echo "la clave dedicada ya existe: $CLAVE (no se sobrescribe)"
  else run ssh-keygen -q -t ed25519 -N "" -C cf-bastion-d5 -f "$CLAVE"; fi
  [ -r "$CLAVE.pub" ] && { echo "CLAVE PÚBLICA para el Sensor1 (CF_PUBKEY):"; cat "$CLAVE.pub"; }
  return 0
}

instalar() {
  echo "== Bastión: instalar (aplicar=$APLICAR)"
  [ -n "${CF_HOSTKEY:-}" ] || { echo "falta CF_HOSTKEY: clave pública del huésped del Sensor1 obtenida fuera de banda"; exit 2; }
  ( cd "$PQ" && sha256sum -c SHA256SUMS --quiet ) || { echo "los artefactos NO coinciden con SHA256SUMS: no se instala nada"; exit 3; }
  [ -e "$HERR/d5_episodio.py" ] && [ -e "$HERR/compuerta_b.py" ] && [ -e "$HERR/orquestar_b.py" ] || { echo "faltan d5_episodio.py / compuerta_b.py / orquestar_b.py en $HERR"; exit 3; }
  TS=$(date -u +%Y%m%dT%H%M%SZ); run mkdir -p "$RESP/$TS" "$HERR"
  [ -e "$KH" ] && run cp -p "$KH" "$RESP/$TS/known_hosts_d5"
  for f in $ARTEFACTOS; do run install -m 0755 "$PQ/$f" "$HERR/$f"; done
  run python3 -I "$HERR/hacer_d5_episodio_banco.py" "$HERR/d5_episodio.py" "$HERR/d5_episodio_banco.py"      # el original d5_episodio.py NO se modifica
  if [ "$APLICAR" = 1 ]; then printf '%s %s\n' "$SENSOR" "$CF_HOSTKEY" > "$KH"; chmod 600 "$KH"; else echo "[seco] fijar la clave de huésped en $KH"; fi
  echo "huella de la clave de huésped fijada (compararla con la que muestra el Sensor1: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub):"
  [ "$APLICAR" = 1 ] && ssh-keygen -lf "$KH" 2>/dev/null
  echo "orden de arranque de la puerta (propuesta, la fija Mark): python3 -I $HERR/lanzador_puerta_banco.py ejecutar --dir <dir> --d5-banco $HERR/d5_episodio_banco.py --sensor m4rk@$SENSOR --clave $CLAVE --known-hosts $KH --herramientas $HERR --espera-fin <15|75> --ssh-sensor-legado '<orden ssh Sensor1>' --ssh-srv-legado '<orden ssh srv-dmz>'"
}

aceptar() {
  echo "== Bastión: aceptación (solo lectura)"
  ( cd "$PQ" && sha256sum -c SHA256SUMS --quiet ); c "artefactos del paquete = SHA256SUMS" $?
  for f in $ARTEFACTOS; do [ "$(sha "$HERR/$f")" = "$(sha "$PQ/$f")" ]; c "instalado $f = paquete" $?; done
  python3 -I "$HERR/hacer_d5_episodio_banco.py" "$HERR/d5_episodio.py" - 2>/dev/null | cmp -s - "$HERR/d5_episodio_banco.py"; c "d5_episodio_banco.py = derivado reproducible del original (sin escribir ficheros)" $?
  [ "$(stat -c %a "$CLAVE")" = 600 ]; c "clave dedicada 0600" $?
  [ "$(stat -c %a "$KH")" = 600 ] && [ "$(wc -l < "$KH")" = 1 ] && grep -q '^'"$SENSOR"' ssh-ed25519 ' "$KH"; c "known_hosts_d5 fija UNA clave ed25519 para el Sensor1" $?
  python3 -I "$HERR/lanzador_puerta_banco.py" ejecutar --help >/dev/null 2>&1; c "el lanzador arranca (--help)" $?
  echo "resumen: $ok OK, $mal FALLAN"; [ "$mal" = 0 ]
}

revertir() {
  echo "== Bastión: revertir (aplicar=$APLICAR) — la evidencia se archiva, no se borra"
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  echo "ANTES: retirar la línea cf-bastion-d5 de authorized_keys del Sensor1 (cf_d5_sensor1.sh revertir)"
  for f in puerta-bloqueo.json puertas-D5.jsonl puerta-banco.jsonl; do echo "archivar con hash: el directorio de la compuerta contiene $f (no se borra)"; done
  [ -e "$CLAVE" ] && run mv "$CLAVE" "$RESP/cyberflow-d5-sensor.retirada-$TS" && run mv "$CLAVE.pub" "$RESP/cyberflow-d5-sensor.pub.retirada-$TS"
  [ -e "$KH" ] && run mv "$KH" "$RESP/known_hosts_d5.retirado-$TS"
  for f in $ARTEFACTOS d5_episodio_banco.py; do [ -e "$HERR/$f" ] && run mv "$HERR/$f" "$RESP/$f.retirado-$TS"; done
  return 0
}

case "$ACCION" in clave) clave;; instalar) instalar;; aceptar) aceptar;; revertir) revertir;; *) echo "uso: $0 {clave|instalar|aceptar|revertir} [--aplicar]"; exit 2;; esac
