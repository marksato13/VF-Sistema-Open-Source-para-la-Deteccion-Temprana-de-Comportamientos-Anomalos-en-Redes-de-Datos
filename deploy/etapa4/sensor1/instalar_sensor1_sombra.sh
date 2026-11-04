#!/usr/bin/env bash
# [SENSOR1 m4rk] Instalación de la Etapa 4 en SOMBRA en Sensor1. La ejecuta MARK (sudo con contraseña:
# instala unidades en /etc y reinicia la captura y el motor). NO autorizado hasta que Mark pida la 4A.
#
#   bash instalar_sensor1_sombra.sh <RESPALDO_DIR> <PAQUETE.tar.gz>     # fases 0–5
#   bash instalar_sensor1_sombra.sh llave-rele <RESPALDO_DIR> <cyberflow-feed-v2-sensor.pub>
#
# Cada fase imprime "OK" o "PARADA <motivo>" y se detiene en la primera PARADA. Tras una PARADA en las
# fases 3–5, revertir con revertir_sensor1.sh <RESPALDO_DIR>.
set -uo pipefail
CAND=ec78ca5
E4="$HOME/cyberflow-e4"
DST="$E4/$CAND"
VENV="$HOME/cyberflow/.venv/bin/python"
parar() { echo "PARADA $*"; exit 1; }
ok() { echo "OK    $*"; }

if [ "${1:-}" = llave-rele ]; then
  # Fase 6 (tras generar la llave en el bastión): acceso del relé v2 SOLO a 'servir' feed.json/feed.sig.
  R="${2:?respaldo}"; PUB="${3:?llave pública del relé}"
  [ -f "$R/authorized_keys" ] || parar "sin authorized_keys en el respaldo"
  grep -q 'cf-feed-ssh.sh servir' "$HOME/.ssh/authorized_keys" && parar "ya hay una línea del relé v2"
  [ -x /usr/local/bin/cf-feed-ssh.sh ] || parar "falta /usr/local/bin/cf-feed-ssh.sh (fase 3)"
  read -r tipo clave _ < "$PUB"
  [ "$tipo" = ssh-ed25519 ] || parar "la llave no es ed25519"
  printf 'command="/usr/local/bin/cf-feed-ssh.sh servir /home/m4rk/feed-v2",restrict %s %s cyberflow-feed-v2-rele\n' \
    "$tipo" "$clave" >> "$HOME/.ssh/authorized_keys"
  # >>> comprobacion-authorized-keys (banco: ensayo_comprobaciones_4a.sh)
  # 4A (2026-11-04): diff sale con 1 cuando hay diferencias y, con pipefail, la tubería paraba siempre.
  anad=$(diff "$R/authorized_keys" "$HOME/.ssh/authorized_keys" | grep -c '^>' || true)
  quit=$(diff "$R/authorized_keys" "$HOME/.ssh/authorized_keys" | grep -c '^<' || true)
  [ "$anad" = 1 ] && [ "$quit" = 0 ] || parar "authorized_keys cambió en más de una línea (+$anad −$quit)"
  # <<< comprobacion-authorized-keys
  ok "llave del relé v2 añadida con comando forzado de solo lectura"
  exit 0
fi

R="${1:?uso: instalar_sensor1_sombra.sh <RESPALDO_DIR> <PAQUETE.tar.gz>}"
PAQ="${2:?paquete}"
AQUI="$(cd "$(dirname "$0")" && pwd)"

# ---------------------------------------------------------------- fase 0: comprobaciones previas
[ "$(id -un)" = m4rk ] || parar "ejecutar como m4rk"
( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || parar "el respaldo no verifica"
grep -q '^RESPALDO OK' "$R/RESPALDO.txt" || parar "respaldo incompleto"
[ -s "$R/ruleset.nft" ] || parar "el respaldo no tiene ruleset.nft (CON_SUDO=1)"
( cd "$(dirname "$PAQ")" && sha256sum -c --quiet "$(basename "$PAQ").sha256" ) || parar "el paquete no verifica"
for u in ppi-motor ppi-motor-capture; do
  cmp -s "/etc/systemd/system/$u.service" "$R/etc-systemd-system/$u.service" || parar "$u.service cambió desde el respaldo"
  [ -z "$(systemctl show -p DropInPaths --value "$u")" ] || parar "$u ya tiene drop-ins"
done
grep -qE '^ppi-motor.service enabled active$' "$R/unidades-estado.txt" || parar "ppi-motor no estaba activo en el respaldo"
[ -e "$DST" ] && parar "$DST ya existe"
tcpdump -d -y EN10MB 'tcp or (vlan and tcp)' > /dev/null || parar "el filtro de la vía rápida no compila"
[ "$(df --output=avail -k "$HOME" | tail -1)" -gt 2097152 ] || parar "menos de 2 GB libres en /home"
timedatectl show -p NTPSynchronized --value | grep -qx yes || parar "reloj no sincronizado"
ok "fase 0: respaldo, paquete, unidades base sin cambios, filtro, disco y reloj"

# ---------------------------------------------------------------- fase 1: código candidato (sin sudo)
mkdir -p "$DST"
tar -xzf "$PAQ" -C "$DST" || parar "no se pudo extraer"
( cd "$DST" && sha256sum -c --quiet SHA256SUMS ) || parar "el contenido extraído no verifica"
grep -qx "candidato=ec78ca56a3a8f4bb17fda967a7f0abe0e9a2c742" "$DST/VERSION-ETAPA4" || parar "VERSION-ETAPA4 no es ec78ca5"
chmod -R a-w "$DST"
ok "fase 1: código de ec78ca5 en $DST (solo lectura)"

# ---------------------------------------------------------------- fase 2: importaciones y clave pública
bash "$AQUI/comprobar_importaciones.sh" "$DST" "$VENV" "$HOME/cyberflow" "$HOME/cyberflow/scripts" \
  || parar "las unidades cargarían código que no es el candidato"
K="$HOME/cyberflow/artifacts/feed-keys"
if [ -f "$K/pub.pem" ]; then
  openssl pkey -in "$K/priv.pem" -pubout 2>/dev/null | cmp -s - "$K/pub.pem" || parar "pub.pem no corresponde a priv.pem"
  install -m 0644 "$K/pub.pem" "$E4/pub.pem"
else
  openssl pkey -in "$K/priv.pem" -pubout -out "$E4/pub.pem" 2>/dev/null || parar "no se pudo derivar la clave pública"
  chmod 0644 "$E4/pub.pem"
fi
install -d -m 0750 "$HOME/feed-v2"
ok "fase 2: importaciones desde $DST; clave PÚBLICA en $E4/pub.pem; ~/feed-v2"

# ---------------------------------------------------------------- fase 3: unidades (sudo)
U="$AQUI/../unidades/sensor1"
sudo install -d -o root -g root -m 0755 /etc/systemd/system/ppi-motor.service.d /etc/systemd/system/ppi-motor-capture.service.d
sudo install -o root -g root -m 0644 "$U/ppi-motor.service.d/etapa4.conf" /etc/systemd/system/ppi-motor.service.d/etapa4.conf
sudo install -o root -g root -m 0644 "$U/ppi-motor-capture.service.d/etapa4.conf" /etc/systemd/system/ppi-motor-capture.service.d/etapa4.conf
sudo install -o root -g root -m 0644 "$U/ppi-publicar-feed-v2.service" "$U/ppi-via-rapida@.service" \
  "$U/cf-tcpdump-estadisticas.service" "$U/cf-tcpdump-estadisticas.timer" /etc/systemd/system/
sudo install -o root -g root -m 0644 "$U/cyberflow-etapa4.logrotate" /etc/logrotate.d/cyberflow-etapa4
sudo install -o root -g root -m 0755 "$DST/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" /usr/local/bin/cf-feed-ssh.sh
sudo logrotate -d /etc/logrotate.d/cyberflow-etapa4 > /dev/null 2>&1 || parar "logrotate rechaza cyberflow-etapa4"
sudo systemctl daemon-reload
for u in ppi-motor.service ppi-motor-capture.service ppi-publicar-feed-v2.service ppi-via-rapida@ens37.service \
         cf-tcpdump-estadisticas.service cf-tcpdump-estadisticas.timer; do
  systemd-analyze verify "$u" 2>&1 | grep -v -e '^$' -e 'is marked world-inaccessible' | grep . && parar "systemd-analyze verify $u"
done
systemctl cat ppi-motor | grep -q 'cyberflow-e4/ec78ca5/scripts/engine/motor_decision.py' || parar "el drop-in del motor no se ve"
ok "fase 3: unidades instaladas y verificadas (aún sin reiniciar nada)"

# ---------------------------------------------------------------- fase 4: arranque en sombra (sudo)
antes_motor=$(systemctl show -p MainPID --value ppi-motor)
antes_cap=$(systemctl show -p MainPID --value ppi-motor-capture)
echo "antes: motor=$antes_motor captura=$antes_cap  $(date -u +%FT%TZ)"
sudo systemctl restart ppi-motor-capture.service ppi-motor.service
sudo systemctl enable --now ppi-via-rapida@ens37.service ppi-publicar-feed-v2.service cf-tcpdump-estadisticas.timer
sleep 20
for u in ppi-motor ppi-motor-capture ppi-via-rapida@ens37 ppi-publicar-feed-v2 cf-tcpdump-estadisticas.timer suricata; do
  systemctl is-active --quiet "$u" || parar "$u no está activo"
done
pm=$(systemctl show -p MainPID --value ppi-motor)
[ "$pm" != "$antes_motor" ] || parar "el motor no se reinició"
tr '\0' ' ' < "/proc/$pm/cmdline" | grep -q -- "cyberflow-e4/ec78ca5/scripts/engine/motor_decision.py .*--disparo eventos" \
  || parar "el proceso del motor no es el candidato"
tr '\0' ' ' < "/proc/$pm/cmdline" | grep -q -- '--enforce' && parar "el motor lleva --enforce"
tr '\0' ' ' < "/proc/$(systemctl show -p MainPID --value ppi-motor-capture)/cmdline" | grep -q -- '-G 5' || parar "la captura no rota a 5 s"
ok "fase 4: servicios activos; motor $pm = candidato sin --enforce; anillo -G 5"

# ---------------------------------------------------------------- fase 5: primeras señales de vida (lecturas)
sleep 60
grep '"event": "motor_startup"' "$HOME/cyberflow/logs/motor_decision.log" | tail -1 | grep -q '"disparo": "eventos"' \
  || echo "AVISO motor_startup sin 'disparo: eventos' (revisar a mano el registro de arranque)"
tail -1 "$HOME/cyberflow/logs/motor_decision.log" | grep -q '"decision_if"' || parar "las decisiones no traen decision_if"
[ -s "$HOME/feed-v2/via-rapida-resumen.jsonl" ] || parar "la vía rápida no escribe su resumen"
[ -s "$HOME/feed-v2/traza.jsonl" ] || parar "el publicador v2 no escribe traza"
ls /var/lib/ppi-motor-capture | tail -4
ok "fase 5: el motor decide con el candidato, la vía rápida y el publicador escriben"
echo "SIGUIENTE: verificar_sensor1.sh (lecturas) y, tras el bastión, la fase llave-rele."
