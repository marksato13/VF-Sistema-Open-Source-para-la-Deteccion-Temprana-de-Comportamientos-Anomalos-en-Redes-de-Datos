#!/bin/bash
# Ataque por capas contra la red de Franco's para probar Wazuh/Suricata. Laboratorio propio.
# No destructivo: recon, escaneo, HTTP de firma conocida y 6 kinit erroneos contra cuenta SIMULADA.
set +e
TS=$(date -u +%Y%m%d-%H%M%S); LOG=~/ataque-francos-$TS.log
exec > >(tee -a "$LOG") 2>&1
echo "###### ATAQUE DE PRUEBA - $(date -u)Z - origen $(hostname -I) ######"

echo; echo "===== FASE A: RECON Y ESCANEO (L2/L3/L4) ====="
echo "-- A1 arp-scan VLAN20 (L2) --";   sudo arp-scan -I eth0 --localnet 2>/dev/null | grep 10.10.20. | head -20
echo "-- A2 nmap SYN+version a DC1 (alcanzable) --"; sudo nmap -sS -sV -T4 --top-ports 50 -Pn 10.10.10.20 2>/dev/null | grep -E 'PORT|open|Nmap scan'
echo "-- A3 nmap a DMZ 10.10.30.10 (debe bloquear pfSense) --"; sudo nmap -sS -T4 --top-ports 20 -Pn --host-timeout 20s 10.10.30.10 2>/dev/null | grep -E 'Nmap scan|open|filtered|down'
echo "-- A4 nmap a honeypot 10.10.90.10 (debe bloquear pfSense) --"; sudo nmap -sS -T4 --top-ports 20 -Pn --host-timeout 20s 10.10.90.10 2>/dev/null | grep -E 'Nmap scan|open|filtered|down'
echo "-- A5 masscan ruidoso VLAN20 (muchos SYN) --"; sudo masscan 10.10.20.0/24 -p22,80,443,445,3389 --rate 2000 2>/dev/null | head -15

echo; echo "===== FASE B: CAPA 7 WEB (firmas IDS) ====="
echo "-- B1 testmynids: id check returned root (sid 2100498) --"; curl -s -m 10 http://testmynids.org/uid/index.html | head -1
echo "-- B2 nikto contra DC1 web si responde --"; timeout 40 nikto -host 10.10.10.20 -port 443 -ssl -maxtime 35s 2>/dev/null | grep -E '\+ ' | head -8
echo "-- B3 sqlmap User-Agent (ET WEB_SCANNER) --"; curl -s -m 8 -A "sqlmap/1.8" "http://10.10.30.10/?id=1%27" -o /dev/null -w "enviado, http %{http_code}\n" 2>/dev/null

echo; echo "===== FASE C: CAPA 7 IDENTIDAD - fuerza bruta Kerberos cuenta SIMULADA a.marroyo ====="
echo "6 kinit con clave erronea (dispara Wazuh 100124 fuerza bruta y 100123 bloqueo):"
for i in 1 2 3 4 5 6; do
  echo "mala-$i" | kinit a.marroyo@AD.FRANCOS-SAC.COM >/dev/null 2>&1
  echo "  intento $i: rc=$? $(date -u +%H:%M:%S)Z"
  sleep 2
done
kdestroy 2>/dev/null
echo; echo "###### FIN - log en $LOG (manda: cat $LOG) ######"