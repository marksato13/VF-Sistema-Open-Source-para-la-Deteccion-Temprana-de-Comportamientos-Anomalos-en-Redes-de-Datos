#!/usr/bin/env bash
# Prueba de instalacion desde cero en la VM2: los pasos que necesitan sudo.
# B0, B2 (version nueva y sha256) y B3 (asistente) ya estan hechos en ~/cyberflow-nuevo.
# Se ejecuta UNA vez, en una sesion interactiva:  bash ~/prueba_sudo.sh
# Pide la contraseña de sudo una vez (queda en cache) y las del panel al final.
set -u
C=~/capturas
mkdir -p "$C"
paso() { printf '\n\033[1;36m=== %s\033[0m\n' "$*"; }
para() { printf '\n\033[1;31mPARADO en %s. Pasale a Claude la salida de arriba.\033[0m\n' "$*"; exit 1; }

[ -d ~/cyberflow-nuevo ] || { echo "Falta ~/cyberflow-nuevo (B2). Avisa a Claude."; exit 1; }
sudo -v || exit 1                      # contraseña una vez

paso "B1 · desinstalar (simulacion y real), con el desinstalador nuevo"
cp ~/cyberflow-nuevo/scripts/setup/desinstalar.sh ~/cyberflow/scripts/setup/desinstalar.sh
cd ~/cyberflow
script -q -c "sudo bash scripts/setup/desinstalar.sh --simular" "$C/R-02a-simular.log"
script -q -c "sudo bash scripts/setup/desinstalar.sh" "$C/R-02b-desinstalar.log" || para B1
systemctl list-unit-files | grep -E 'ppi-|cyberflow' && para "B1 (quedan unidades)"

paso "B2 · version nueva en su sitio (la vieja queda en ~/cyberflow.k-20260929)"
cd ~ && mv ~/cyberflow ~/cyberflow.k-20260929 && mv ~/cyberflow-nuevo ~/cyberflow || para B2
cd ~/cyberflow

paso "B4 · comprobacion previa"
script -q -c "sudo bash scripts/setup/instalar.sh --comprobar" "$C/06-02-instalar-comprobar.log" || para B4

paso "B5 · instalacion"
script -q -c "sudo bash scripts/setup/instalar.sh" "$C/06-03-instalar.log" || para B5

paso "B5 · panel: clave de sesion, certificado y cuentas (teclea las contraseñas; no se ven)"
script -q -c "sudo python3 scripts/setup/cyberflow_usuarios.py --clave-sesion && \
sudo python3 scripts/setup/cyberflow_usuarios.py --certificado --nombre 10.10.60.12 && \
sudo python3 scripts/setup/cyberflow_usuarios.py --crear admin --rol admin && \
sudo python3 scripts/setup/cyberflow_usuarios.py --crear lector --rol lector" "$C/06-07-cuentas-panel.log" || para "B5 cuentas"
sudo systemctl restart ppi-dashboard 2>/dev/null

printf '\n\033[1;32mListo. Dile a Claude "listo": el sigue con doctor, capturas y la nota R.\033[0m\n'
