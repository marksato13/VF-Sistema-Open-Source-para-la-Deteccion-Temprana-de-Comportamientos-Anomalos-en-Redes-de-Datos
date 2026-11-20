#!/usr/bin/env bash
# Instalación, aceptación y reversión del lado SENSOR1 de D5 sin reinicio (propuesta; NO ejecutada en el laboratorio). Se ejecuta como `m4rk` en el Sensor1.
# SECO POR OMISIÓN: sin --aplicar solo imprime lo que haría. Las partes que exigen root (drop-in de systemd y logrotate) se escriben con `sudo -n` SOLO con --aplicar
# y --con-sudo (el `sudo` es de Mark); sin --con-sudo se deja el contenido en $CF_PAQUETE/pendiente-sudo/ para que Mark lo instale.
# Uso: cf_d5_sensor1.sh {instalar|aceptar|revertir} [--aplicar] [--con-sudo] [--reiniciar]
# Variables (todas con valor por omisión del Sensor1 real; se cambian solo en el ensayo de banco):
#   CF_FROM     (opcional, recomendado) IP de origen permitida para la clave: `from="10.10.10.30"` (el bastión; es la IP que ve el Sensor1 en auth.log)
#   CF_PAQUETE  carpeta con los artefactos y SHA256SUMS            CF_HOME  /home/m4rk          CF_ETC  /etc
#   CF_PUBKEY   fichero con la clave PÚBLICA dedicada del bastión (obligatorio en instalar)       CF_SIN_SYSTEMD=1  (solo banco: no llama a systemctl)
#   CF_EXECSTART_FILE  (solo banco) fichero con la línea ExecStart= original; en el laboratorio se lee de `systemctl cat`
set -uo pipefail
ACCION="${1:-}"; shift || true
APLICAR=0; SUDO=0; REINICIAR=0
for a in "$@"; do case "$a" in --aplicar) APLICAR=1;; --con-sudo) SUDO=1;; --reiniciar) REINICIAR=1;; *) echo "opción desconocida: $a" >&2; exit 2;; esac; done
CF_HOME="${CF_HOME:-/home/m4rk}"; CF_ETC="${CF_ETC:-/etc}"; PQ="${CF_PAQUETE:-$CF_HOME/cf-b/paquete-despliegue}"
UNIDAD="ppi-publicar-feed-v2.service"
ENGINE="$CF_HOME/cyberflow-e4/ec78ca5/scripts/engine"; HERR="$CF_HOME/cf-b/herramientas"; DER="$CF_HOME/cf-b/d5"      # el derivado va FUERA del árbol candidato (read-only y con SHA256SUMS)
D5="$CF_HOME/feed-v2/d5"; AK="$CF_HOME/.ssh/authorized_keys"
DROPIN="$CF_ETC/systemd/system/$UNIDAD.d/zz-d5-sin-reinicio.conf"; LOGR="$CF_ETC/logrotate.d/cf-d5-auditoria"
RESP="$CF_HOME/cf-b/respaldo-d5"; MARCA="cf-bastion-d5"
ORIG_SHA="5733f17d39bfa5fe667ee13aecd133ea4859834899c5f4f6ea21360ebe4002a2"
run() { if [ "$APLICAR" = 1 ]; then "$@"; else echo "[seco] $*"; fi; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
ok=0; mal=0
c() { if [ "$2" = 0 ]; then echo "OK    $1"; ok=$((ok+1)); else echo "FALLA $1"; mal=$((mal+1)); fi; }
forzado() { echo "${CF_FROM:+from=\"$CF_FROM\",}command=\"/usr/bin/python3 -I $HERR/sensor_control_d5.py --base $D5/control --feed $CF_HOME/feed-v2/feed.json --estado $CF_HOME/feed-v2/estado.json --traza $CF_HOME/feed-v2/traza.jsonl --auditoria $D5/auditoria/d5-auditoria.jsonl --ssh-original\",restrict"; }
verificar_paquete() { ( cd "$PQ" && sha256sum -c SHA256SUMS --quiet ) ; }

instalar() {
  echo "== Sensor1: instalar (aplicar=$APLICAR)"
  [ -n "${CF_PUBKEY:-}" ] && [ -r "$CF_PUBKEY" ] || { echo "falta CF_PUBKEY (clave pública dedicada del bastión)"; exit 2; }
  verificar_paquete || { echo "los artefactos NO coinciden con SHA256SUMS: no se instala nada"; exit 3; }
  [ "$(sha "$ENGINE/publicar_feed_v2.py")" = "$ORIG_SHA" ] || { echo "el publicador original instalado no es 5733f17d…: no se instala"; exit 3; }
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  run mkdir -p "$RESP/$TS" "$HERR" "$D5/control" "$D5/auditoria" "$CF_HOME/.ssh"
  run chmod 700 "$D5/control" "$CF_HOME/.ssh"; run chmod 750 "$D5/auditoria"
  [ -e "$AK" ] && run cp -p "$AK" "$RESP/$TS/authorized_keys" && [ "$APLICAR" = 1 ] && sha256sum "$RESP/$TS/authorized_keys" > "$RESP/$TS/authorized_keys.sha256"
  for f in sensor_control_d5.py adaptador_banco.py adaptador_banco_rot.py auditoria_d5.py d5_control.py; do run install -m 0644 "$PQ/$f" "$HERR/$f"; done
  run chmod 0755 "$HERR/sensor_control_d5.py"
  run mkdir -p "$DER"; run install -m 0644 "$PQ/publicar_feed_v2_d5.py" "$DER/publicar_feed_v2_d5.py"      # FUERA de ec78ca5 (read-only, con SHA256SUMS): el candidato no se toca
  PUB=$(cut -d' ' -f1-2 "$CF_PUBKEY")
  if [ -e "$AK" ] && grep -q "$MARCA" "$AK"; then echo "la clave $MARCA ya está en authorized_keys (no se duplica)"
  else run bash -c "printf '%s %s %s\n' '$(forzado)' '$PUB' '$MARCA' >> '$AK'"; run chmod 600 "$AK"; fi
  # ExecStart derivado del ORIGINAL (se lee, no se inventa) + las tres opciones nuevas
  # el ExecStart original es multilínea (continuaciones con «\»): se une entero antes de derivarlo
  if [ -n "${CF_EXECSTART_FILE:-}" ]; then BRUTO=$(cat "$CF_EXECSTART_FILE"); else BRUTO=$(systemctl cat "$UNIDAD" | awk '/^ExecStart=/{p=1} p{print} p&&!/\\$/{exit}'); fi
  ES=$(printf '%s\n' "$BRUTO" | sed 's/^ExecStart=//; :a; /\\$/{N; s/\\\n[[:space:]]*/ /; ba}' | tr -s ' ' | sed 's/ *$//')
  [ -n "$ES" ] && printf '%s' "$ES" | grep -q "$ENGINE/publicar_feed_v2.py" || { echo "el ExecStart original no contiene $ENGINE/publicar_feed_v2.py: no se deriva"; exit 3; }
  NUEVO=$(printf '%s' "$ES" | sed "s#$ENGINE/publicar_feed_v2\.py#$DER/publicar_feed_v2_d5.py#")" --control-d5 $D5/control/control.json --d5-origen 10.10.20.30 --d5-auditoria $D5/auditoria/d5-auditoria.jsonl"
  CONT_DROPIN=$(printf '[Service]\nEnvironment=PYTHONPATH=%s\nExecStart=\nExecStart=%s\n' "$ENGINE" "$NUEVO")
  CONT_LOGR=$(sed -n '/^\/home\/m4rk\/feed-v2\/d5\/auditoria\//,$p' "$PQ/d5-auditoria.logrotate.propuesta" | sed "s#/home/m4rk/#$CF_HOME/#")
  if [ "$APLICAR" = 0 ]; then echo "--- drop-in previsto ($DROPIN):"; echo "$CONT_DROPIN"; echo "--- logrotate previsto ($LOGR):"; echo "$CONT_LOGR"; fi
  if [ "$SUDO" = 1 ]; then
    run sudo -n install -d -m 0755 "$(dirname "$DROPIN")" "$(dirname "$LOGR")"
    if [ "$APLICAR" = 1 ]; then printf '%s\n' "$CONT_DROPIN" | sudo -n tee "$DROPIN" >/dev/null; printf '%s\n' "$CONT_LOGR" | sudo -n tee "$LOGR" >/dev/null; sudo -n chmod 0644 "$DROPIN" "$LOGR"
    else echo "[seco] escribir $DROPIN y $LOGR con sudo"; fi
    [ "${CF_SIN_SYSTEMD:-0}" = 1 ] || run sudo -n systemctl daemon-reload
  else
    run mkdir -p "$PQ/pendiente-sudo"
    if [ "$APLICAR" = 1 ]; then printf '%s\n' "$CONT_DROPIN" > "$PQ/pendiente-sudo/zz-d5-sin-reinicio.conf"; printf '%s\n' "$CONT_LOGR" > "$PQ/pendiente-sudo/cf-d5-auditoria"
      echo "SUDO PENDIENTE (Mark): instalar $PQ/pendiente-sudo/zz-d5-sin-reinicio.conf -> $DROPIN y $PQ/pendiente-sudo/cf-d5-auditoria -> $LOGR (0644 root), luego: sudo systemctl daemon-reload"
    else echo "[seco] dejar el contenido en $PQ/pendiente-sudo/ (sin --con-sudo)"; fi
  fi
  if [ "$REINICIAR" = 1 ]; then [ "${CF_SIN_SYSTEMD:-0}" = 1 ] || run sudo -n systemctl restart "$UNIDAD"; else echo "NO se reinicia el publicador (hacerlo con --reiniciar, fuera de campaña, un solo reinicio anotado)"; fi
}

aceptar() {
  echo "== Sensor1: aceptación (solo lectura)"
  verificar_paquete; c "artefactos del paquete = SHA256SUMS" $?
  for f in sensor_control_d5.py adaptador_banco.py adaptador_banco_rot.py auditoria_d5.py d5_control.py; do [ "$(sha "$HERR/$f")" = "$(sha "$PQ/$f")" ]; c "instalado $f = paquete" $?; done
  [ "$(sha "$DER/publicar_feed_v2_d5.py")" = "$(sha "$PQ/publicar_feed_v2_d5.py")" ]; c "publicador derivado instalado (en cf-b/d5) = paquete" $?
  [ ! -e "$ENGINE/publicar_feed_v2_d5.py" ]; c "el árbol candidato ec78ca5 NO contiene el derivado" $?
  if [ -r "$CF_HOME/cyberflow-e4/ec78ca5/SHA256SUMS" ] && [ "${CF_SIN_SYSTEMD:-0}" != 1 ]; then ( cd "$CF_HOME/cyberflow-e4/ec78ca5" && sha256sum -c SHA256SUMS --quiet >/dev/null 2>&1 ); c "SHA256SUMS del código candidato ec78ca5 sigue verificando" $?; fi
  [ "$(sha "$ENGINE/publicar_feed_v2.py")" = "$ORIG_SHA" ]; c "publicador ORIGINAL intacto (5733f17d…)" $?
  [ "$(stat -c %a "$D5/control")" = 700 ]; c "control 0700" $?;  [ "$(stat -c %a "$D5/auditoria")" = 750 ]; c "auditoría 0750" $?
  [ "$(stat -c %a "$AK")" = 600 ] && [ "$(grep -c "$MARCA" "$AK")" = 1 ] && grep "$MARCA" "$AK" | grep -q 'restrict' && grep "$MARCA" "$AK" | grep -q 'command="'; c "authorized_keys 0600 con UNA línea $MARCA, comando forzado y restrict" $?
  [ -r "$DROPIN" ] && grep -q 'publicar_feed_v2_d5.py' "$DROPIN" && grep -q -- '--control-d5' "$DROPIN"; c "drop-in de systemd presente (sudo de Mark)" $?
  [ -r "$LOGR" ] && grep -q 'su m4rk m4rk' "$LOGR" && grep -q 'nocopytruncate' "$LOGR"; c "logrotate presente (sudo de Mark)" $?
  # el comando forzado, probado localmente como lo ejecutaría sshd (SSH_ORIGINAL_COMMAND)
  R1=$(SSH_ORIGINAL_COMMAND="resultado --id 00000000000000000000000000000000" /usr/bin/python3 -I "$HERR/sensor_control_d5.py" --base "$D5/control" --feed "$CF_HOME/feed-v2/feed.json" --estado "$CF_HOME/feed-v2/estado.json" --traza "$CF_HOME/feed-v2/traza.jsonl" --auditoria "$D5/auditoria/d5-auditoria.jsonl" --ssh-original)
  echo "$R1" | grep -q '"estado": "desconocida"'; c "comando permitido responde (resultado de un id inexistente = desconocida)" $?
  R2=$(SSH_ORIGINAL_COMMAND="cat /etc/passwd" /usr/bin/python3 -I "$HERR/sensor_control_d5.py" --base "$D5/control" --feed "$CF_HOME/feed-v2/feed.json" --estado "$CF_HOME/feed-v2/estado.json" --traza "$CF_HOME/feed-v2/traza.jsonl" --auditoria "$D5/auditoria/d5-auditoria.jsonl" --ssh-original)
  echo "$R2" | grep -q '"estado": "rechazada"' && ! echo "$R2" | grep -q 'root:'; c "comando fuera de la lista blanca rechazado" $?
  if [ "${CF_SIN_SYSTEMD:-0}" != 1 ]; then
    NR=$(systemctl show "$UNIDAD" -p NRestarts --value); echo "NRestarts actual del publicador: $NR (anotar: no debe aumentar durante la corrida)"
    systemctl is-active "$UNIDAD" | grep -q '^active$'; c "unidad del publicador activa" $?
    PYTHONPATH="$ENGINE" "$CF_HOME/cyberflow/.venv/bin/python" -B "$DER/publicar_feed_v2_d5.py" --help >/dev/null 2>&1; c "el derivado arranca con el python del VENV real (--help; no escribe nada)" $?
    ps -eo args | grep publicar_feed_v2 | grep -v grep | grep -q -- '--aplicar'; [ $? -ne 0 ]; c "publicador SIN --aplicar" $?
  fi
  echo "resumen: $ok OK, $mal FALLAN"; [ "$mal" = 0 ]
}

revertir() {
  echo "== Sensor1: revertir (aplicar=$APLICAR) — la evidencia se archiva, no se borra"
  TS=$(date -u +%Y%m%dT%H%M%SZ)
  if [ -e "$AK" ] && grep -q "$MARCA" "$AK"; then
    run cp -p "$AK" "$RESP/authorized_keys.antes-revertir-$TS"
    if [ "$APLICAR" = 1 ]; then grep -v "$MARCA" "$AK" > "$AK.tmp" && chmod 600 "$AK.tmp" && mv "$AK.tmp" "$AK"; else echo "[seco] quitar la línea $MARCA de $AK"; fi
  fi
  if [ "$SUDO" = 1 ]; then run sudo -n rm -f "$DROPIN" "$LOGR"; [ "${CF_SIN_SYSTEMD:-0}" = 1 ] || run sudo -n systemctl daemon-reload
  else echo "SUDO PENDIENTE (Mark): sudo rm -f $DROPIN $LOGR && sudo systemctl daemon-reload"; fi
  [ -d "$D5" ] && run mv "$D5" "$CF_HOME/feed-v2/d5-archivado-$TS"
  [ "$APLICAR" = 1 ] && [ -d "$CF_HOME/feed-v2/d5-archivado-$TS" ] && ( cd "$CF_HOME/feed-v2/d5-archivado-$TS" && find . -type f -exec sha256sum {} + > "$CF_HOME/feed-v2/d5-archivado-$TS.sha256" )
  [ -e "$DER/publicar_feed_v2_d5.py" ] && run mv "$DER/publicar_feed_v2_d5.py" "$RESP/publicar_feed_v2_d5.py.retirado-$TS"   # el derivado es reproducible; el candidato nunca se tocó
  if [ "$REINICIAR" = 1 ]; then [ "${CF_SIN_SYSTEMD:-0}" = 1 ] || run sudo -n systemctl restart "$UNIDAD"; else echo "el publicador sigue con el ExecStart cargado hasta su próximo reinicio: reiniciar con --reiniciar (anotado como reversión) tras quitar el drop-in"; fi
  return 0
}

case "$ACCION" in instalar) instalar;; aceptar) aceptar;; revertir) revertir;; *) echo "uso: $0 {instalar|aceptar|revertir} [--aplicar] [--con-sudo] [--reiniciar]"; exit 2;; esac
