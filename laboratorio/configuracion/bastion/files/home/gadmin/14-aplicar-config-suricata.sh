#!/usr/bin/env bash
# Comparador exclusivamente: instala YAML/reglas validados, sin arrancar el IDS.
set -Eeuo pipefail
[[ $EUID -eq 0 && $(hostname) == suricata-comparator ]] || { echo 'Usar sudo en la VM comparadora'; exit 1; }
[[ $(cat /sys/class/net/ens37/address) == 00:0c:29:c8:ad:ec ]]
[[ -z $(ip -o addr show dev ens37) ]]
systemctl is-active --quiet suricata.service && { echo 'Suricata ya activo: detener y revisar'; exit 1; }
[[ $(systemctl is-enabled suricata.service) == disabled ]]
TRIAL=/home/adminsuricata/suricata-compare-trial-20261002
CONF=/etc/suricata/suricata.yaml
CLASS=/etc/suricata/classification.config
RULE=/var/lib/suricata/rules/suricata.rules
[[ -f $TRIAL/suricata.yaml && -f $TRIAL/classification.config && -f $TRIAL/suricata.rules ]]
[[ ! -s $RULE ]] || { echo 'Ya existen reglas en produccion; no sobrescribir'; exit 1; }
[[ $(sha256sum "$CONF" | cut -d' ' -f1) == b23ef3fb06d8189f383c585b749bb9b0b156dbd7588361b49164df7d12e1f2d9 ]]
[[ $(sha256sum "$TRIAL/suricata.yaml" | cut -d' ' -f1) == f93649b9244beaa5b3c4927fcbeb9849a4d6353aa0453e4847d444c6bd674545 ]]
[[ $(sha256sum "$TRIAL/suricata.rules" | cut -d' ' -f1) == 7b674459975dd56af2d03363b27df4ad6ff53e724e3c04ff65913701ddd5f4e9 ]]
[[ $(sha256sum "$TRIAL/classification.config" | cut -d' ' -f1) == 3924e356b2c645763a058a66607f0612e10e01fe817d0eb7b07c34ede5021d16 ]]
BEFORE_IP=$(ip -4 addr show dev ens34)
BEFORE_ROUTE=$(ip -4 route show default)
BACKUP=$(mktemp -d /root/suricata-compare-backup.XXXXXXXX)
cp -a "$CONF" "$BACKUP/suricata.yaml"
cp -a "$CLASS" "$BACKUP/classification.config"
if [[ -e $RULE ]]; then cp -a "$RULE" "$BACKUP/suricata.rules"; fi
rollback() {
    echo "Fallo: restaurando archivos desde $BACKUP"
    cp -a "$BACKUP/suricata.yaml" "$CONF"
    cp -a "$BACKUP/classification.config" "$CLASS"
    if [[ -e $BACKUP/suricata.rules ]]; then
        cp -a "$BACKUP/suricata.rules" "$RULE"
    else
        rm -f "$RULE"
    fi
    echo 'Revisar salida de suricata -T; no se inicio el servicio.'
}
trap rollback ERR
python3 - "$TRIAL" "$BACKUP/suricata.yaml.new" <<'PY'
import pathlib
import sys

trial, destination = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
content = (trial / 'suricata.yaml').read_text()
for old, new in (
    (f'default-rule-path: {trial}', 'default-rule-path: /var/lib/suricata/rules'),
    (f'classification-file: {trial / "classification.config"}',
     'classification-file: /etc/suricata/classification.config'),
):
    if content.count(old) != 1:
        raise ValueError(f'No se encuentra valor de prueba: {old}')
    content = content.replace(old, new, 1)
if 'af-packet:\n  - interface: ens37' not in content or 'HOME_NET: "[10.10.30.0/24]"' not in content:
    raise ValueError('Interfaz o red protegida incorrectas')
destination.write_text(content)
PY
install -m 644 "$BACKUP/suricata.yaml.new" "$CONF"
install -m 644 "$TRIAL/classification.config" "$CLASS"
install -m 644 "$TRIAL/suricata.rules" "$RULE"
install -d -m 700 "$BACKUP/test-logs"
suricata -T -c "$CONF" -l "$BACKUP/test-logs"
grep -Fq '53013 rules successfully loaded, 0 rules failed' "$BACKUP/test-logs/suricata.log"
[[ $(ip -4 addr show dev ens34) == "$BEFORE_IP" ]]
[[ $(ip -4 route show default) == "$BEFORE_ROUTE" ]]
[[ -z $(ip -o addr show dev ens37) ]]
if systemctl is-active --quiet suricata.service; then
    echo 'Suricata se activo inesperadamente'
    false
fi
trap - ERR
echo "Validacion superada; respaldo: $BACKUP"
sha256sum "$CONF" "$CLASS" "$RULE"
echo 'Servicio aun disabled/inactive. No se realizo ningun ataque.'
