#!/usr/bin/env bash
# [SRV-DMZ adminsrvdmz] Agente v2 perfil dmz en SOMBRA (sin --aplicar), Etapa 4. Lo ejecuta MARK: crea
# cuentas e instala en /usr/local, /opt, /etc, /var/lib y sudoers. Mismos pasos que el procedimiento
# revisado de la Etapa 2 (P1–P8, probados en el banco :3), con el código de ec78ca5.
# El agente v1 (ppi-enforce-agent.timer, hoy disabled/inactive) y ppi-brute-lab NO se tocan.
#
#   bash instalar_srvdmz_sombra.sh <RESPALDO_DIR> <DST_PAQUETE> <pub.pem del sensor> <cyberflow-feed-v2-srv.pub>
set -uo pipefail
parar() { echo "PARADA $*"; exit 1; }
ok() { echo "OK    $*"; }
R="${1:?respaldo}"; DST="${2:?paquete extraído}"; PUB="${3:?pub.pem}"; RELE="${4:?llave pública del relé}"
( cd "$R" && sha256sum -c --quiet SHA256SUMS ) || parar "el respaldo no verifica"
[ -s "$R/ruleset.nft" ] || parar "el respaldo no tiene ruleset.nft (CON_SUDO=1)"
grep -qiE 'requiretty' "$R/sudoers-defaults.txt" && parar "sudo exige tty: el helper no funcionaría"
( cd "$DST" && sha256sum -c --quiet SHA256SUMS ) || parar "el paquete no verifica"
getent passwd cffeed cfagente > /dev/null && parar "las cuentas ya existen"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || parar "python3 < 3.11"
read -r tipo _ _ < "$RELE"; [ "$tipo" = ssh-ed25519 ] || parar "la llave del relé no es ed25519"
openssl pkey -pubin -in "$PUB" -noout 2>/dev/null || parar "pub.pem no es una clave pública"
ok "fase 0"

E="$DST/deploy/enforcement/candidato-etapa2"
sudo useradd -r -m -d /var/lib/cyberflow/cffeed-home -s /bin/sh cffeed && sudo passwd -l cffeed
sudo useradd -r -M -d /nonexistent -s /usr/sbin/nologin cfagente
sudo usermod -aG cfagente cffeed
sudo install -d -o root -g root -m 0755 /opt/cyberflow/agente-v2 /etc/cyberflow /var/lib/cyberflow
sudo install -d -o cffeed -g cfagente -m 2750 /var/lib/cyberflow/feed
sudo install -d -o cfagente -g cfagente -m 0700 /var/lib/cyberflow/agente
sudo install -o root -g root -m 0644 "$DST/scripts/enforce/agente_enforce_v2.py" "$DST/scripts/engine/feed.py" /opt/cyberflow/agente-v2/
sudo install -o root -g root -m 0644 "$PUB" /opt/cyberflow/agente-v2/pub.pem
sudo install -o root -g root -m 0755 "$DST/scripts/enforce/cf_nft_helper.py" /usr/local/sbin/cf-nft-helper
sudo install -o root -g root -m 0755 "$E/cf-feed-ssh.sh" /usr/local/bin/cf-feed-ssh.sh
echo dmz | sudo tee /etc/cyberflow/nft-helper.perfil > /dev/null && sudo chmod 0644 /etc/cyberflow/nft-helper.perfil
sudo install -o root -g root -m 0440 "$E/cf-nft-helper.sudoers" /etc/sudoers.d/cf-nft-helper
sudo visudo -c > /dev/null || { sudo rm -f /etc/sudoers.d/cf-nft-helper; parar "visudo -c falla: sudoers retirado"; }
sudo install -d -o cffeed -g cffeed -m 0700 /var/lib/cyberflow/cffeed-home/.ssh
printf 'command="/usr/local/bin/cf-feed-ssh.sh recibir /var/lib/cyberflow/feed",restrict %s\n' "$(cut -d' ' -f1,2 "$RELE") cyberflow-feed-v2-rele" \
  | sudo install -o cffeed -g cffeed -m 0600 /dev/stdin /var/lib/cyberflow/cffeed-home/.ssh/authorized_keys
ok "fase 1: cuentas, rutas, helper, sudoers y llave del relé (solo 'recibir')"

# El helper NO aplica nada sin petición; en sombra el agente solo pide 'listar'. Antes de arrancar se
# comprueba que el perfil impuesto por el host rechaza otro perfil.
echo '{"perfil":"dns","operaciones":[{"op":"listar"}]}' | sudo -u cfagente sudo -n /usr/local/sbin/cf-nft-helper \
  | grep -q perfil_no_autorizado || parar "el helper no rechaza un perfil ajeno"
sudo install -o root -g root -m 0644 "$DST/deploy/etapa4/unidades/srvdmz/ppi-enforce-agent-v2-dmz.service" /etc/systemd/system/
grep -q -- '--aplicar' /etc/systemd/system/ppi-enforce-agent-v2-dmz.service && parar "la unidad lleva --aplicar"
sudo systemctl daemon-reload
systemd-analyze verify ppi-enforce-agent-v2-dmz.service 2>&1 | grep . && parar "systemd-analyze verify"
sudo systemctl enable --now ppi-enforce-agent-v2-dmz.service
ok "fase 2: agente v2 en SOMBRA arrancado; siguiente: instalar_bastion_sombra.sh instalar y verificar_srvdmz.sh"
