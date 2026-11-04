#!/usr/bin/env bash
# [SENSOR1 m4rk] Respaldo del estado de Sensor1 ANTES de instalar la Etapa 4. No cambia nada del
# laboratorio: solo lee y escribe en ~/respaldos-etapa4/. No copia la clave privada del feed (ni su
# contenido ni su hash; solo sus metadatos): la reversión no la toca.
#
#   bash respaldo_sensor1.sh                 # parte sin privilegios (la puede ejecutar Claude)
#   CON_SUDO=1 bash respaldo_sensor1.sh      # además ruleset nft y sudoers (Mark: sudo con contraseña)
#
# Resultado esperado: la última línea dice "RESPALDO OK <dir>" y <dir>/SHA256SUMS verifica.
# Parada: cualquier "FALLO" (falta una lectura imprescindible) -> no se instala.
set -uo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
D="$HOME/respaldos-etapa4/sensor1-$TS"
mkdir -p "$D" && chmod 0700 "$HOME/respaldos-etapa4" "$D"
fallo=0
nota() { printf '%s\n' "$*" | tee -a "$D/RESPALDO.txt"; }
imprescindible() { if ! eval "$2"; then nota "FALLO $1"; fallo=1; else nota "ok    $1"; fi; }
nota "respaldo Sensor1 $(hostname) $TS por $(id -un)"

UNIDADES="ppi-motor.service ppi-motor-capture.service ppi-publicar-feed.service ppi-publicar-feed.timer
ppi-dashboard.service suricata.service cyberflow-acumular.service cyberflow-acumular.timer
cyberflow-aprendizaje.service cyberflow-aprendizaje.timer cyberflow-limpieza.service cyberflow-limpieza.timer
cyberflow-capture-nic.service cyberflow-panel-acceso.service
ppi-publicar-feed-v2.service ppi-via-rapida@ens37.service cf-tcpdump-estadisticas.service cf-tcpdump-estadisticas.timer"

# 1. Estado de las unidades: referencia EXACTA de la reversión (también las que aún no existen).
for u in $UNIDADES; do
  printf '%s %s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || true)" "$(systemctl is-active "$u" 2>/dev/null || true)"
done > "$D/unidades-estado.txt"
imprescindible "estado de unidades" "grep -q '^ppi-motor.service enabled active$' '$D/unidades-estado.txt'"
for u in $UNIDADES; do
  echo "---- $u"
  systemctl show "$u" -p UnitFileState -p ActiveState -p SubState -p MainPID -p NRestarts \
    -p ExecMainStartTimestamp -p ExecMainStartTimestampMonotonic -p FragmentPath -p DropInPaths 2>&1
done > "$D/unidades-show.txt"
for u in $UNIDADES; do echo "#### $u"; systemctl cat "$u" 2>&1; done > "$D/unidades-cat.txt"

# 2. Copia literal de las unidades y drop-ins de /etc/systemd/system que afectan a la Etapa 4.
mkdir -p "$D/etc-systemd-system"
for f in /etc/systemd/system/ppi-* /etc/systemd/system/cyberflow-* /etc/systemd/system/cf-*; do
  [ -e "$f" ] && cp -a "$f" "$D/etc-systemd-system/"
done
imprescindible "copia de ppi-motor.service" "[ -f '$D/etc-systemd-system/ppi-motor.service' ]"
find /etc/systemd/system -maxdepth 2 \( -name 'ppi-*' -o -name 'cyberflow*' -o -name 'cf-*' \) \
  -printf '%M %u %g %s %TY-%Tm-%Td %TT %p\n' | sort > "$D/etc-systemd-system.ls"
mkdir -p "$D/logrotate.d"; cp -a /etc/logrotate.d/cyberflow /etc/logrotate.d/suricata "$D/logrotate.d/" 2>/dev/null
ls -la /usr/local/bin /usr/local/sbin > "$D/usr-local.ls" 2>&1

# 3. Proceso real del motor y de la captura (lo que de verdad está cargado).
for u in ppi-motor ppi-motor-capture suricata; do
  pid=$(systemctl show -p MainPID --value "$u")
  { echo "$u pid=$pid"; [ "${pid:-0}" -gt 0 ] && tr '\0' ' ' < "/proc/$pid/cmdline" && echo; } >> "$D/procesos.txt"
done
imprescindible "cmdline del motor" "grep -q 'motor_decision.py' '$D/procesos.txt'"

# 4. Código desplegado: no es un checkout de git; se respalda por contenido y hash.
( cd "$HOME/cyberflow" && find scripts configs deploy -type f ! -path '*/__pycache__/*' -print0 | sort -z \
    | xargs -0 sha256sum ) > "$D/cyberflow-codigo.sha256"
imprescindible "hash del código" "[ -s '$D/cyberflow-codigo.sha256' ]"
tar -C "$HOME" --exclude='__pycache__' -czf "$D/cyberflow-codigo.tar.gz" \
  cyberflow/scripts cyberflow/configs cyberflow/deploy
# Artefactos del modelo por hash; de las llaves del feed solo metadatos (la privada no se lee).
( cd "$HOME/cyberflow" && sha256sum artifacts/preliminar/limpio-2026-10/* ) > "$D/artefactos.sha256" 2>&1
ls -la --time-style=full-iso "$HOME/cyberflow/artifacts/feed-keys" > "$D/feed-keys.ls" 2>&1
# Estado del motor 24f8a80 (ancla, claves previas): la candidata usa _state-e4 y no lo toca,
# pero se guarda por si una reversión lo necesitara.
tar -C "$HOME/cyberflow/logs" -czf "$D/logs-_state.tar.gz" _state 2>/dev/null
ls -la --time-style=full-iso "$HOME/cyberflow/logs" "$HOME/cyberflow/logs/_state" > "$D/logs.ls" 2>&1
tar -C "$HOME" -czf "$D/feed-v1.tar.gz" feed 2>/dev/null
[ -d "$HOME/feed-v2" ] && nota "AVISO ~/feed-v2 ya existe (se conserva, no se reutiliza sin revisar)"
[ -d "$HOME/cyberflow-e4" ] && nota "AVISO ~/cyberflow-e4 ya existe"

# 5. Acceso: authorized_keys (copia íntegra; la instalación añade una línea del relé v2) y crontab.
cp -a "$HOME/.ssh/authorized_keys" "$D/authorized_keys" 2>/dev/null
imprescindible "authorized_keys" "[ -f '$D/authorized_keys' ]"
crontab -l > "$D/crontab.txt" 2>&1

# 6. Captura y salud en el instante del respaldo.
ls -la --time-style=full-iso /var/lib/ppi-motor-capture | tail -5 > "$D/anillo.ls" 2>&1
ls /var/lib/ppi-motor-capture | wc -l >> "$D/anillo.ls"
for c in rx_packets rx_dropped rx_missed_errors rx_fifo_errors rx_over_errors; do
  printf '%s %s\n' "$c" "$(cat /sys/class/net/ens37/statistics/$c)"; done > "$D/ens37.txt"
tail -c 20000 /var/log/suricata/stats.log | awk '/^Date:/{b=""} {b=b $0 "\n"} END{printf "%s", b}' > "$D/suricata-stats-ultimo.txt"
tcpdump --version > "$D/versiones.txt" 2>&1
"$HOME/cyberflow/.venv/bin/python" -c 'import sys,sklearn,numpy,joblib; print(sys.version); print(sklearn.__version__, numpy.__version__, joblib.__version__)' >> "$D/versiones.txt" 2>&1
timedatectl show -p NTPSynchronized -p TimeUSec >> "$D/versiones.txt" 2>&1
df -h /home /var/lib /var/log > "$D/disco.txt" 2>&1; free -m >> "$D/disco.txt"

# 7. Parte con privilegios (Mark): reglas y sudoers efectivos.
if [ "${CON_SUDO:-0}" = 1 ]; then
  sudo nft list ruleset > "$D/ruleset.nft"
  imprescindible "ruleset nft (sudo)" "[ -s '$D/ruleset.nft' ]"
  sudo cp -a /etc/sudoers.d "$D/sudoers.d" && sudo chown -R "$(id -u):$(id -g)" "$D/sudoers.d"
  sudo getcap /usr/bin/tcpdump > "$D/getcap.txt" 2>&1
else
  nota "pendiente CON_SUDO=1: ruleset.nft y sudoers.d (Mark)"
fi

# 4A (2026-11-04): la línea final se escribe ANTES del manifiesto. Antes se añadía después a RESPALDO.txt y
# el manifiesto no verificaba nunca (sha256sum -c: RESPALDO.txt FAILED); el instalador habría parado en la fase 0.
if [ "$fallo" = 0 ]; then nota "RESPALDO OK $D"; else nota "RESPALDO INCOMPLETO $D (no instalar)"; fi
( cd "$D" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
[ "$fallo" = 0 ] || exit 1
