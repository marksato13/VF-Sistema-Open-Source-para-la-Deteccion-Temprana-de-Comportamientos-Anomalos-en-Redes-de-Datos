set -u
C=~/capturas; cd ~/cyberflow
s() { script -q -c "$1" "$C/$2.log" >/dev/null 2>&1; echo "== $2 rc=$?"; }
date -u +%FT%TZ
s "bash scripts/setup/doctor.sh" 07-01b-doctor-30min
s "ip -br link; echo; ip -br addr" 03-01-ip-br-link
s "cat /sys/class/net/ens37/statistics/rx_packets; sleep 10; cat /sys/class/net/ens37/statistics/rx_packets" 04-01-rx-packets
s "wc -l /var/log/suricata/eve.json; sleep 60; wc -l /var/log/suricata/eve.json" 05-02-eve-crece
s "python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --comprobar; python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --mostrar | head -n 40" 06-06-config-mostrar
for f in 07-01b-doctor-30min 03-01-ip-br-link 04-01-rx-packets 05-02-eve-crece 06-06-config-mostrar; do
  echo "########## $f"; sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\r//g' "$C/$f.log" | grep -v '^Script ' | head -n 45
done
