#!/bin/bash
# Recolector de configuracion de UN equipo Linux del laboratorio CyberFlow.
# Solo lectura: no cambia nada en el equipo. Escribe un .tar.gz por la salida estandar.
# Uso (desde el bastion):  ssh <equipo> 'bash -s' < recolector_linux.sh > equipo.tgz
#
# Nunca copia: claves privadas, /etc/shadow, ficheros .env, keyrings, historiales.
# sudo solo se intenta con -n (sin contrasena) y solo para LEER; si no hay permiso se anota.
set -u
export LC_ALL=C
O=$(mktemp -d)
trap 'rm -rf "$O"' EXIT
mkdir -p "$O"/{sistema,red,paquetes,servicios,etc,app}

c() { # c <fichero_salida> <comando...>  -> guarda salida y error
  local f="$1"; shift
  { "$@" ; } >"$O/$f" 2>&1 || echo "[rc=$?] $*" >>"$O/$f"
}
s() { # s <fichero_salida> <comando...>  -> intenta con sudo -n (solo lectura)
  local f="$1"; shift
  if sudo -n true 2>/dev/null; then c "$f" sudo -n "$@"; else echo "[sin sudo -n] $*" >"$O/$f"; fi
}
copia() { # copia <ruta> -> la copia bajo etc/ o app/ si es legible y no es secreta
  local p
  for p in "$@"; do
    [ -e "$p" ] || continue
    case "$p" in *.key|*priv*.pem|*id_rsa*|*id_ed25519*|*id_ecdsa*|*/shadow*|*gshadow*|*.env|*secret*|*token*|*.p12|*.pfx|*.kdbx) continue;; esac
    if [ -d "$p" ]; then
      find "$p" -xdev \( -name '*.key' -o -name '*priv*.pem' -o -name 'id_*' -o -name '*.env' -o -name '*secret*' \
            -o -name '*token*' -o -name '__pycache__' -o -name '*.pyc' -o -name '*.joblib' -o -name '*.pkl' \
            -o -name '*.pcap*' -o -name '*.log' -o -name '*.gz' -o -name '*.csv' -o -name '.git' -o -name '.venv' \) -prune \
           -o -type f -size -2M -readable -print 2>/dev/null | while read -r f; do
        mkdir -p "$O/files$(dirname "$f")"; cp -p "$f" "$O/files$f" 2>/dev/null
      done
    elif [ -r "$p" ] && [ "$(stat -c %s "$p")" -lt 2097152 ]; then
      mkdir -p "$O/files$(dirname "$p")"; cp -p "$p" "$O/files$p" 2>/dev/null
    fi
  done
}

# --- sistema / especificaciones
c sistema/fecha.txt date -u +%FT%TZ
c sistema/hostnamectl.txt hostnamectl
c sistema/os-release.txt cat /etc/os-release
c sistema/uname.txt uname -a
c sistema/cpu.txt lscpu
c sistema/memoria.txt free -h
c sistema/discos.txt lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
c sistema/df.txt df -hT -x tmpfs -x devtmpfs -x squashfs
c sistema/hora.txt timedatectl
c sistema/usuarios.txt bash -c 'getent passwd | awk -F: "\$3>=1000 && \$3<65534 {print \$1\":\"\$3\":\"\$6\":\"\$7}"'
c sistema/grupos-propios.txt id
c sistema/virtualizacion.txt systemd-detect-virt

# --- red
c red/ip-addr.txt ip -br addr
c red/ip-link.txt ip -br link
c red/ip-route.txt ip route
c red/resolv.txt cat /etc/resolv.conf
c red/hosts.txt cat /etc/hosts
c red/escucha.txt ss -ltnup
c red/networkctl.txt networkctl status --no-pager
s red/nft-ruleset.txt nft list ruleset
s red/iptables-save.txt iptables-save
copia /etc/netplan /etc/network/interfaces /etc/network/interfaces.d /etc/systemd/network
s red/netplan-sudo.txt bash -c 'for f in /etc/netplan/*.yaml; do echo "### $f"; cat "$f"; done'

# --- paquetes
c paquetes/dpkg.txt dpkg-query -W -f '${Package}\t${Version}\n'
c paquetes/apt-manual.txt apt-mark showmanual
c paquetes/pip-sistema.txt python3 -m pip list --format=freeze
c paquetes/python.txt python3 --version
for py in "$HOME"/*/.venv/bin/python "$HOME"/.venv/bin/python /opt/*/.venv/bin/python /opt/*/venv/bin/python; do
  [ -x "$py" ] || continue
  n=$(echo "$py" | sed 's#/#_#g; s#^_##')
  c "paquetes/venv-$n.txt" "$py" -m pip freeze
done
c paquetes/herramientas.txt bash -c 'for t in nmap hping3 curl wget dig tcpdump suricata zeek python3 nft iptables docker chronyc nginx apache2 named smbd samba zabbix_agentd zabbix_agent2 wazuh-agentd; do p=$(command -v $t) && echo "$t $p $($t --version 2>&1 | head -1)"; done'

# --- servicios
c servicios/activos.txt systemctl list-units --type=service --state=running --no-pager --no-legend
c servicios/habilitados.txt systemctl list-unit-files --state=enabled --no-pager --no-legend
c servicios/timers.txt systemctl list-timers --all --no-pager
c servicios/fallidos.txt systemctl --failed --no-pager --no-legend
for u in $(systemctl list-unit-files --no-legend --no-pager 2>/dev/null | awk '{print $1}' | grep -E '^(ppi-|cf-|cyberflow|suricata|zeek|nginx|apache2|bind9|named|chrony|zabbix|wazuh|smbd|samba|docker|ssh)' ); do
  c "servicios/unidad-$u.txt" systemctl cat "$u" --no-pager
done
copia /etc/systemd/system
c servicios/crontab-usuario.txt crontab -l
copia /etc/cron.d /etc/crontab
s servicios/sudoers.txt bash -c 'cat /etc/sudoers.d/* 2>/dev/null'
c servicios/sudo-l.txt sudo -n -l

# --- configuracion de servicios (lo que exista en este equipo)
copia /etc/suricata/suricata.yaml /etc/suricata/threshold.config /etc/suricata/classification.config \
      /etc/default/suricata /etc/suricata/update.yaml /var/lib/suricata/update/disable.conf
s etc/suricata-reglas.txt bash -c 'ls -la /var/lib/suricata/rules/ 2>/dev/null; wc -l /var/lib/suricata/rules/*.rules 2>/dev/null | tail -1'
copia /etc/nginx/nginx.conf /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/apache2/sites-enabled /etc/apache2/ports.conf
copia /etc/chrony/chrony.conf /etc/chrony/conf.d /etc/systemd/timesyncd.conf /etc/ntp.conf
copia /etc/ssh/sshd_config /etc/ssh/sshd_config.d
copia /etc/logrotate.d /etc/rsyslog.d
copia /etc/zabbix/zabbix_agentd.conf /etc/zabbix/zabbix_agent2.conf /var/ossec/etc/ossec.conf
copia /etc/bind/named.conf.options /etc/bind/named.conf.local /etc/samba/smb.conf
copia /usr/local/sbin /usr/local/bin
copia /etc/docker/daemon.json
c etc/docker-ps.txt docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

# --- aplicacion CyberFlow y scripts de laboratorio en el HOME (sin datos, modelos ni registros)
for d in "$HOME"/cyberflow/configs "$HOME"/cyberflow/deploy "$HOME"/cf-demo "$HOME"/cf-b "$HOME"/feed-v2/d5/control \
         "$HOME"/laboratorio "$HOME"/cf-dns "$HOME"/control_dns.sh /opt/cyberflow; do
  copia "$d"
done
for f in "$HOME"/*.sh "$HOME"/*.py "$HOME"/scripts; do copia "$f"; done
c app/home-listado.txt bash -c 'ls -la ~; for d in ~/cyberflow ~/cyberflow-e4; do [ -d "$d" ] && { echo "### $d"; ls -la "$d"; }; done'
c app/artefactos-modelo.txt bash -c 'find ~/cyberflow/artifacts -maxdepth 3 \( -name "*.json" -o -name "*.joblib" \) -printf "%p %s\n" 2>/dev/null | head -100'
c app/cyberflow-e4-sha256.txt bash -c 'cd ~/cyberflow-e4 2>/dev/null && find . -type f -name "*.py" -exec sha256sum {} + | sort -k2'

tar -czf - -C "$O" .
