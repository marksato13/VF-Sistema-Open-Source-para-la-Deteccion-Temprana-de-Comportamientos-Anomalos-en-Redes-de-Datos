set -u
cd ~/cyberflow
echo "== ensayo-if-v2.json:"; python3 -c "
import json;d=json.load(open('artifacts/preliminar/ensayo-if-v2.json'))
print({k:d.get(k) for k in ('generado','filas','fpr_test','entrada_sha256','salida_sha256')})"
echo "== manifiesto vigente (detector if_recalibrado_2026_09):"; python3 -c "
import json;m=json.load(open('artifacts/preliminar/manifest-if-recalibrado.json'))
d=m['detectors'].get('if_recalibrado_2026_09',{}); print({k:d.get(k) for k in ('model_sha256','origen')})"
echo "== dataset: $(wc -l < artifacts/linea-base/multilayer-v3.csv) lineas"
sed -n '336965,336966p' artifacts/linea-base/multilayer-v3.csv | cut -d, -f1-3
echo "== eve.json: $(stat -c '%U:%G %a %s' /var/log/suricata/eve.json) legible_por_m4rk=$( [ -r /var/log/suricata/eve.json ] && echo si || echo no)"
echo "== RAM: $(free -m | awk '/Mem/{print $2" MB total, "$7" MB disponibles"}')"
