set -u
cd ~/cyberflow
echo "== particion.json:"; python3 -c "import json;d=json.load(open('artifacts/preliminar/particion.json'));print(d.get('reparto'), d.get('primera_ventana'), d.get('ultima_ventana'), d.get('salida_sha256','')[:16])"
echo "== if-v2.json:"; python3 -c "import json;d=json.load(open('artifacts/preliminar/if-v2.json'));print(d.get('filas'), d.get('fpr_test'), d.get('entrada_sha256','')[:16])"
echo "sha particionado: $(sha256sum artifacts/preliminar/particionado.csv | cut -c1-16)"
echo "== manifiesto del vigente, origen:"; python3 -c "
import json;m=json.load(open('artifacts/preliminar/manifest-if-recalibrado.json'))
d=list(m['detectors'].values())[0]; print(d.get('origen') or {k:d[k] for k in d if k!='features'})" 2>&1 | head -5
echo "== acumulador:"; systemctl cat cyberflow-acumular.service 2>/dev/null | grep -E -- '--salida|--campaign'; ls -la artifacts/linea-base/ 2>/dev/null | tail -4
echo "== linger (timers de usuario sin sesion): $(ls /var/lib/systemd/linger 2>/dev/null | tr '\n' ' ')"
echo "== kali/ataques etiquetados (nota M):"; find artifacts -maxdepth 3 -iname '*kali*' -o -maxdepth 3 -iname '*ataque*' -o -maxdepth 3 -iname '*anomal*' 2>/dev/null | head
