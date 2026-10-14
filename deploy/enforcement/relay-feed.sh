#!/usr/bin/env bash
# Relay del feed firmado: del SENSOR al HOST protegido, pasando por el BASTION.
#
# Modelo "un feed / N agentes (pull)": el sensor NO tiene credenciales de los
# hosts. El bastion es un relay TONTO -solo copia bytes-; no puede forjar nada,
# porque la firma ed25519 la pone el sensor y la verifica el agente del host.
# Lo ejecuta ppi-relay-feed.timer (cada 60 s). Ver INSTALACION.md Seccion 9.3.
#
# AJUSTE A SU DESPLIEGUE (estos son los valores del laboratorio de referencia):
#   - usuario/IP del sensor:  m4rk@10.10.60.11   (origen del feed)
#   - usuario/IP del host:    adminsrvdmz@10.10.30.10   (destino, srv-dmz)
#   - claves SSH del relay:   ~/.ssh/cyberflow-to-sensor  y  ~/.ssh/cyberflow-to-srv
#   - rutas del feed:         /home/m4rk/feed/{feed.json,feed.sig}  en el sensor
#                             ~/enforce/  en el host protegido
# Las claves son de SOLO esta funcion (BatchMode, sin contrasena); no dan shell.
set -uo pipefail
mkdir -p ~/relay
scp -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/cyberflow-to-sensor \
  m4rk@10.10.60.11:/home/m4rk/feed/feed.json m4rk@10.10.60.11:/home/m4rk/feed/feed.sig ~/relay/ 2>/dev/null || exit 0
scp -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/cyberflow-to-srv \
  ~/relay/feed.json ~/relay/feed.sig adminsrvdmz@10.10.30.10:/home/adminsrvdmz/enforce/ 2>/dev/null
