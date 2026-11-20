#!/bin/sh
# /usr/local/sbin/cf-primer-pcap  (0755 root:root) — cierre complementario de la 4A (4-nov-2026).
# Devuelve al grupo del directorio (setgid) el PRIMER fichero de cada arranque de tcpdump.
# Causa (reproducida con strace en Ubuntu 24.04 / tcpdump 4.99.4, igual que Sensor1): con -Z,
# tcpdump abre el primer fichero como root y le hace chown(<uid de tcpdump>, <gid PRIMARIO de
# tcpdump>) ANTES de soltar privilegios; los siguientes los crea ya como tcpdump y heredan el grupo
# del directorio setgid (m4rk). Con UMask=0027 (0640) y grupo tcpdump, el motor (m4rk) no puede
# leer ese primer fichero: PermissionError y pcaps_ilegibles=1 en cada arranque de la captura.
# Uso: cf-primer-pcap DIRECTORIO GRUPO   (desde ExecStartPost de ppi-motor-capture, como root)
# Solo toca live-*.pcap de ESE directorio con propietario tcpdump y grupo tcpdump (chgrp): no
# cambia modos ni propietarios ni concede permisos nuevos. Espera como máximo 10 s; nunca hace
# fallar la unidad (si no encuentra el fichero lo dice en el journal y sale 0).
D="$1"; G="$2"; i=0
while [ $i -lt 100 ]; do
  if find "$D" -maxdepth 1 -name 'live-*.pcap' -user tcpdump -group tcpdump 2>/dev/null | grep -q .; then
    find "$D" -maxdepth 1 -name 'live-*.pcap' -user tcpdump -group tcpdump -print -exec chgrp "$G" {} + \
      | sed 's#^#primer_pcap: grupo corregido en #'
    exit 0
  fi
  i=$((i + 1)); sleep 0.1
done
echo "primer_pcap: AVISO: en 10 s no apareció ningún live-*.pcap tcpdump:tcpdump en $D"
exit 0
