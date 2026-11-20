set -u
cd ~/cyberflow
echo "== R1 · entorno Python desde ruedas locales"
sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\r//g' ~/capturas/06-03-instalar.log | grep -niE 'rueda|wheel|pip|internet|7\. ' | head
.venv/bin/python -V; .venv/bin/python -c "import sklearn, numpy, scapy; print('sklearn', sklearn.__version__, 'numpy', numpy.__version__)" 2>&1
echo "== R8 · contraseñas fuera de historial y ficheros"
grep -c -iE 'contrase|password|--clave ' ~/.bash_history 2>/dev/null || echo "0 lineas sospechosas en .bash_history"
ls -l /etc/cyberflow 2>&1
echo "== R9 · captura sin descartes (ultimo stats de eve.json)"
tail -n 4000 /var/log/suricata/eve.json | grep '"event_type":"stats"' | tail -1 | python3 -c "import json,sys; s=json.loads(sys.stdin.read())['stats']['capture']; print(s)"
echo "== R9 · anillo: ficheros live-*.pcap ahora: $(ls /var/lib/ppi-motor-capture/ | wc -l)"
echo "== demo en la misma VM (puerto 8790)"
cp ~/demo.sh scripts/demo-prueba.sh
PUERTO=8790 timeout 25 bash scripts/demo-prueba.sh > /tmp/demo.out 2>&1 &
sleep 12
curl -s -o /tmp/demo.html -w 'demo / -> %{http_code}, %{size_download} bytes\n' http://127.0.0.1:8790/
curl -s http://127.0.0.1:8790/api/decisions 2>/dev/null | head -c 300; echo
wait; rm -f scripts/demo-prueba.sh
head -5 /tmp/demo.out
grep -o '<title>[^<]*' /tmp/demo.html
