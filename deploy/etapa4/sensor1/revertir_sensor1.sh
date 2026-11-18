#!/usr/bin/env bash
# [SENSOR1 m4rk] Reversión de la Etapa 4 en Sensor1 al estado del RESPALDO. La ejecuta MARK (sudo).
# No depende de git: devuelve las unidades al contenido copiado en el respaldo, el motor al ExecStart
# base (24f8a80 en ~/cyberflow, que la instalación no tocó) y cada unidad a su is-enabled/is-active.
# NO borra evidencia: ~/cyberflow-e4, ~/feed-v2 y logs/_state-e4 se conservan.
#
#   bash revertir_sensor1.sh <RESPALDO_DIR>
#
# Resultado esperado: "REVERSIÓN OK". Parada: cualquier "DIFERENCIA" (se informa y se deja para Mark).
set -uo pipefail
R="${1:?uso: revertir_sensor1.sh <RESPALDO_DIR>}"
( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA el respaldo no verifica"; exit 1; }
dif=0
diferencia() { echo "DIFERENCIA $*"; dif=1; }

# 1. Parar y deshabilitar lo nuevo (si el respaldo dice que no existía o estaba parado).
for u in cf-tcpdump-estadisticas.timer ppi-publicar-feed-v2.service ppi-via-rapida@ens37.service; do
  linea=$(grep "^$u " "$R/unidades-estado.txt")
  case "$linea" in
    *" enabled active") echo "se mantiene $u (ya estaba activo antes)";;
    *) sudo systemctl disable --now "$u" 2>/dev/null; echo "parado $u";;
  esac
done
# 2. Retirar ficheros instalados que no estaban en el respaldo.
for f in ppi-motor.service.d/etapa4.conf ppi-motor-capture.service.d/etapa4.conf ppi-publicar-feed-v2.service \
         'ppi-via-rapida@.service' cf-tcpdump-estadisticas.service cf-tcpdump-estadisticas.timer; do
  base=${f%%/*}
  if [ -e "$R/etc-systemd-system/$base" ]; then echo "se conserva /etc/systemd/system/$f (existía antes)"; continue; fi
  sudo rm -f "/etc/systemd/system/$f"
done
sudo rmdir /etc/systemd/system/ppi-motor.service.d /etc/systemd/system/ppi-motor-capture.service.d 2>/dev/null
sudo rm -f /etc/logrotate.d/cyberflow-etapa4
grep -q ' cf-feed-ssh.sh$' "$R/usr-local.ls" || sudo rm -f /usr/local/bin/cf-feed-ssh.sh
# 3. Las unidades base deben ser las del respaldo, byte a byte.
for u in ppi-motor.service ppi-motor-capture.service; do
  cmp -s "/etc/systemd/system/$u" "$R/etc-systemd-system/$u" || diferencia "$u no es la del respaldo"
done
sudo systemctl daemon-reload
for u in ppi-motor ppi-motor-capture; do
  [ -z "$(systemctl show -p DropInPaths --value "$u")" ] || diferencia "$u conserva drop-ins"
done
# 4. Acceso del relé v2: authorized_keys vuelve a la copia del respaldo.
cmp -s "$R/authorized_keys" "$HOME/.ssh/authorized_keys" || {
  cp -a "$HOME/.ssh/authorized_keys" "$HOME/.ssh/authorized_keys.etapa4-$(date -u +%Y%m%dT%H%M%SZ)"
  install -m 0600 "$R/authorized_keys" "$HOME/.ssh/authorized_keys"; echo "authorized_keys restaurado"; }
# 5. Reiniciar captura y motor con el ExecStart base.
sudo systemctl restart ppi-motor-capture.service ppi-motor.service
sleep 15
# 6. Cada unidad del respaldo vuelve a su estado (solo se corrige lo que difiera).
while read -r u en ac; do
  [ -z "$u" ] && continue
  ahora_en=$(systemctl is-enabled "$u" 2>/dev/null || true); ahora_ac=$(systemctl is-active "$u" 2>/dev/null || true)
  case "$en" in enabled) [ "$ahora_en" = enabled ] || sudo systemctl enable "$u";;
                disabled) [ "$ahora_en" = disabled ] || sudo systemctl disable "$u" 2>/dev/null;; esac
  case "$ac" in active) [ "$ahora_ac" = active ] || sudo systemctl start "$u";;
                inactive|failed) [ "$ahora_ac" = active ] && sudo systemctl stop "$u";; esac
done < "$R/unidades-estado.txt"
# 7. Comprobación.
while read -r u _; do
  printf '%s %s %s\n' "$u" "$(systemctl is-enabled "$u" 2>/dev/null || true)" "$(systemctl is-active "$u" 2>/dev/null || true)"
done < "$R/unidades-estado.txt" > /tmp/e4-unidades-tras-revertir.txt
diff "$R/unidades-estado.txt" /tmp/e4-unidades-tras-revertir.txt || diferencia "estado de unidades distinto del respaldo"
pm=$(systemctl show -p MainPID --value ppi-motor)
esperado=$(grep -A1 '^ppi-motor pid=' "$R/procesos.txt" | tail -1 | sed 's/ *$//')
actual=$(tr '\0' ' ' < "/proc/$pm/cmdline" | sed 's/ *$//')
[ "$actual" = "$esperado" ] || diferencia "cmdline del motor distinta del respaldo"
pc=$(systemctl show -p MainPID --value ppi-motor-capture)
tr '\0' ' ' < "/proc/$pc/cmdline" | grep -q -- '-G 15' || diferencia "la captura no volvió a -G 15"
( cd "$HOME/cyberflow" && sha256sum -c --quiet "$R/cyberflow-codigo.sha256" ) || diferencia "el código de ~/cyberflow cambió"
if [ -s "$R/ruleset.nft" ]; then
  sudo nft list ruleset | diff -q - "$R/ruleset.nft" > /dev/null \
    || echo "AVISO ruleset distinto del respaldo: revisar a mano (pueden variar contadores y elementos con caducidad)"
fi
[ "$dif" = 0 ] && echo "REVERSIÓN OK (evidencia conservada en ~/cyberflow-e4, ~/feed-v2 y logs/_state-e4)" || exit 1
