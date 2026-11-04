#!/usr/bin/env bash
# Banco (4A, 2026-11-04): los tres guiones de respaldo terminan con un manifiesto que VERIFICA, también cuando
# RESPALDO.txt ya tenía líneas (avisos, «pendiente CON_SUDO», notas de Sensor1). Defecto encontrado en vivo:
# respaldo_sensor1.sh añadía «RESPALDO OK» a RESPALDO.txt después de calcular SHA256SUMS.
# Se ejecuta en un contenedor desechable (raíz propia; systemctl, sudo, nft, etc. simulados):
#   docker run --rm -v "$PWD:/r:ro" debian:trixie-slim bash /r/deploy/etapa4/banco/ensayo_respaldos.sh
set -u
[ -f /.dockerenv ] || { echo "ejecutar dentro de un contenedor desechable (escribe en /etc y /home)"; exit 2; }
R=/r/deploy/etapa4
B=/tmp/bin; mkdir -p $B
cat > $B/systemctl <<'EOF'
#!/usr/bin/env bash
case "$1" in
  is-enabled) case "$2" in ppi-motor.service|ppi-relay-feed.timer) echo enabled;; *) echo disabled; exit 1;; esac;;
  is-active)  case "$2" in ppi-motor.service|ppi-relay-feed.timer) echo active;; *) echo inactive; exit 3;; esac;;
  show) [ "$2" = -p ] && [ "$3" = MainPID ] && { cat /tmp/motor.pid; exit 0; }; echo "Id=$2";;
  cat) echo "# $2";;
  --version) echo "systemd 257";;
esac
EOF
printf '#!/usr/bin/env bash\n[ "$1" = -n ] && shift\nexec "$@"\n' > $B/sudo
printf '#!/usr/bin/env bash\n[ "$1 $2" = "list ruleset" ] && [ "${NFT_VACIO:-0}" = 1 ] && exit 0\necho "table inet x {}"\n' > $B/nft
for c in getcap tcpdump crontab openssl; do printf '#!/usr/bin/env bash\necho "%s simulado"\n' "$c" > $B/$c; done
printf '#!/usr/bin/env bash\necho NTPSynchronized=yes\n' > $B/timedatectl
printf '#!/usr/bin/env bash\necho "256 SHA256:x %s (ED25519)"\n' > $B/ssh-keygen
chmod +x $B/*; export PATH="$B:$PATH"
mkdir -p /etc/systemd/system /etc/sudoers.d /etc/logrotate.d /var/log/suricata
echo "[Service]" > /etc/systemd/system/ppi-motor.service; echo "Defaults env_reset" > /etc/sudoers
bash -c 'exec -a /x/motor_decision.py sleep 300' & echo $! > /tmp/motor.pid
fallos=0
comprobar() {  # nombre dir_padre
  local d; d=$(ls -d "$2"/* 2>/dev/null | tail -1)
  if [ -n "$d" ] && ( cd "$d" && sha256sum -c --quiet SHA256SUMS ) && tail -1 "$d/RESPALDO.txt" | grep -q '^RESPALDO OK'; then
    echo "OK    $1: manifiesto verifica y RESPALDO.txt termina en RESPALDO OK"
  else echo "FALLO $1"; fallos=$((fallos + 1)); fi
}
# Sensor1 (con notas previas en RESPALDO.txt por diseño)
useradd -m m4rk 2>/dev/null; H=/home/m4rk
mkdir -p $H/cyberflow/{scripts,configs,deploy,logs/_state,artifacts/preliminar/limpio-2026-10,artifacts/feed-keys} $H/.ssh $H/feed
echo x > $H/cyberflow/scripts/a.py; echo k > $H/.ssh/authorized_keys
HOME=$H CON_SUDO=1 bash $R/sensor1/respaldo_sensor1.sh > /tmp/s1.out 2>&1; comprobar "Sensor1 CON_SUDO=1" $H/respaldos-etapa4
rm -rf $H/respaldos-etapa4
HOME=$H bash $R/sensor1/respaldo_sensor1.sh > /tmp/s1b.out 2>&1; comprobar "Sensor1 sin sudo (línea «pendiente» previa)" $H/respaldos-etapa4
# srv-dmz: con CON_SUDO=1 y ruleset vacío (estado tras P0), y sin CON_SUDO (línea «pendiente» previa)
H2=/home/adminsrvdmz; mkdir -p $H2/.ssh $H2/enforce; echo k > $H2/.ssh/authorized_keys
HOME=$H2 NFT_VACIO=1 CON_SUDO=1 bash $R/srvdmz/respaldo_srvdmz.sh > /tmp/srv.out 2>&1; comprobar "srv-dmz CON_SUDO=1, ruleset vacío" $H2/respaldos-etapa4
d=$(ls -d $H2/respaldos-etapa4/* | tail -1); grep -q '^rc=0 bytes=0 ' "$d/ruleset.lectura" && echo "OK    srv-dmz: ruleset.lectura rc=0 bytes=0" || { echo "FALLO srv-dmz ruleset.lectura"; fallos=$((fallos + 1)); }
rm -rf $H2/respaldos-etapa4
HOME=$H2 bash $R/srvdmz/respaldo_srvdmz.sh > /tmp/srv2.out 2>&1; comprobar "srv-dmz sin sudo (línea «pendiente» previa)" $H2/respaldos-etapa4
# Bastión con AVISO previo (~/relay-v2 ya existe)
H3=/home/gadmin; mkdir -p $H3/.ssh $H3/relay-v2; echo '#!/bin/sh' > $H3/relay-feed.sh; echo "ssh-ed25519 AAAA x" > $H3/.ssh/a.pub
HOME=$H3 bash $R/bastion/respaldo_bastion.sh > /tmp/b.out 2>&1; comprobar "bastión con AVISO previo" $H3/respaldos-etapa4
kill "$(cat /tmp/motor.pid)" 2>/dev/null
[ "$fallos" = 0 ] && echo "ENSAYO OK (6/6)" || { echo "ENSAYO CON $fallos FALLOS"; for f in /tmp/*.out; do echo "== $f"; tail -5 "$f"; done; exit 1; }
