#!/usr/bin/env bash
# =====================================================================
#  CyberFlow - ciclo de reinstalacion en cyberflow-sensor2 (10.10.60.12)
# ---------------------------------------------------------------------
#  Prueba la guia llave-en-mano: desinstala -> despliega el clon FRESCO
#  de main (99d5005, con todos los fixes) -> configura -> instala offline
#  -> crea auth del panel -> doctor.
#
#  Se ejecuta EN TU TERMINAL (necesita TTY para las contrasenas):
#      bash ~/reinstalar_ciclo.sh
#
#  Te pedira: la contrasena de sudo (una vez, se cachea) y las dos
#  contrasenas del panel (admin y lector). Ninguna se guarda en fichero,
#  argv ni historial: sudo usa su prompt y las del panel van por 'read -s'.
# =====================================================================
set -uo pipefail

ACTUAL=/home/m4rk/cyberflow
NUEVO=/home/m4rk/cyberflow.nuevo
TAR=/home/m4rk/cyberflow-fresh.tgz
RUEDAS=/home/m4rk/bundle/ruedas
IP_PANEL=10.10.60.12
COMMIT=99d5005
STAMP=$(date +%Y%m%d-%H%M%S)

rojo(){ printf '\033[31m%s\033[0m\n' "$*"; }
verde(){ printf '\033[32m%s\033[0m\n' "$*"; }
tit(){ printf '\n\033[1m========== %s ==========\033[0m\n' "$*"; }

# --- 0. Comprobaciones previas --------------------------------------
[[ -f "$TAR" ]]        || { rojo "No encuentro el tarball $TAR"; exit 1; }
[[ -d "$RUEDAS" ]]     || { rojo "No encuentro las ruedas offline en $RUEDAS"; exit 1; }
[[ -x /opt/python3.14/bin/python3.14 ]] || { rojo "Falta /opt/python3.14 (lo necesita el motor)"; exit 1; }

tit "1. Desplegar el clon fresco a un lado ($NUEVO)"
rm -rf "$NUEVO"
mkdir -p "$NUEVO"
tar xzf "$TAR" -C "$NUEVO"
echo "$COMMIT" > "$NUEVO/COMMIT_DESPLEGADO.txt"
verde "  $(tar tzf "$TAR" | wc -l) ficheros extraidos, commit $COMMIT"

tit "2. DRY-RUN del desinstalador (del clon fresco; no ejecuta nada)"
sudo bash "$NUEVO/scripts/setup/desinstalar.sh" --simular
echo
read -r -p ">>> Continuar con el ciclo REAL (desinstala e instala de verdad)? [s/N]: " OK
[[ "$OK" =~ ^[sS]$ ]] || { echo "Cancelado. No se ha tocado nada."; rm -rf "$NUEVO"; exit 0; }

tit "3. Respaldar la linea base acumulada"
if [[ -f "$ACTUAL/artifacts/linea-base/multilayer-v3.csv" ]]; then
    cp "$ACTUAL/artifacts/linea-base/multilayer-v3.csv" /home/m4rk/baseline-v3.bak
    verde "  baseline -> /home/m4rk/baseline-v3.bak ($(wc -l < /home/m4rk/baseline-v3.bak) filas)"
else
    echo "  (no habia baseline que respaldar)"
fi

tit "4. Desinstalar CyberFlow (conserva Suricata)"
sudo bash "$NUEVO/scripts/setup/desinstalar.sh"

tit "5. Cambiar el clon viejo por el fresco"
mv "$ACTUAL" "/home/m4rk/cyberflow.old.$STAMP"
mv "$NUEVO" "$ACTUAL"
verde "  clon viejo guardado en /home/m4rk/cyberflow.old.$STAMP (puedes borrarlo luego)"

tit "6. Restaurar ruedas offline y la linea base en el clon fresco"
cp -r "$RUEDAS" "$ACTUAL/ruedas"
verde "  ruedas: $(ls -1 "$ACTUAL"/ruedas/*.whl 2>/dev/null | wc -l) wheels"
if [[ -f /home/m4rk/baseline-v3.bak ]]; then
    mkdir -p "$ACTUAL/artifacts/linea-base"
    cp /home/m4rk/baseline-v3.bak "$ACTUAL/artifacts/linea-base/multilayer-v3.csv"
    verde "  baseline restaurada"
fi

tit "7. Configurar (asistente en modo auto-deteccion, sin preguntas)"
setsid bash "$ACTUAL/scripts/setup/configurar.sh" < /dev/null
if [[ -f "$ACTUAL/configs/cyberflow.local.toml" ]]; then
    grep -E '^(interfaz|mac_esperada|red_entidades|modo|usuario|raiz|direccion)' \
        "$ACTUAL/configs/cyberflow.local.toml" | sed 's/^/  /'
else
    rojo "  configurar.sh no escribio el .toml; abortando antes de instalar."; exit 1
fi

tit "8. Instalar (offline, desde ruedas/)"
cd "$ACTUAL"
sudo bash "$ACTUAL/scripts/setup/instalar.sh"

tit "9. Auth del panel: clave de sesion + certificado autofirmado"
sudo python3 "$ACTUAL/scripts/setup/cyberflow_usuarios.py" --clave-sesion
sudo python3 "$ACTUAL/scripts/setup/cyberflow_usuarios.py" --certificado --nombre "$IP_PANEL"

tit "10. Cuentas del panel (teclea las contrasenas; minimo 12 caracteres)"
echo "  -- admin (rol admin) --"
read -rs -p "  Contrasena admin: " PW; echo
printf '%s\n' "$PW" | sudo python3 "$ACTUAL/scripts/setup/cyberflow_usuarios.py" --crear admin --rol admin --stdin
echo "  -- lector (rol lector) --"
read -rs -p "  Contrasena lector: " PW; echo
printf '%s\n' "$PW" | sudo python3 "$ACTUAL/scripts/setup/cyberflow_usuarios.py" --crear lector --rol lector --stdin
unset PW
sudo python3 "$ACTUAL/scripts/setup/cyberflow_usuarios.py" --comprobar

tit "11. Reiniciar el panel y comprobar salud del sistema"
sudo systemctl restart ppi-dashboard 2>/dev/null || true
sleep 2
bash "$ACTUAL/scripts/setup/doctor.sh"

tit "FIN DEL CICLO"
verde "Si doctor no muestra FALLOS (solo el aviso 'sin calibrar', que es normal"
verde "hasta recalibrar), la guia queda demostrada como llave-en-mano."
echo "El motor empezara a llenar su historia (~230 s) antes de decidir."
