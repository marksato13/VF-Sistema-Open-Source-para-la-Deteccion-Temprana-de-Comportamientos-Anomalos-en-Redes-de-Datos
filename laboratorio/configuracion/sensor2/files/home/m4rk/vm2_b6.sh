set -u
C=~/capturas
cd ~/cyberflow
for f in R-02b-desinstalar 06-02-instalar-comprobar 06-03-instalar 06-07-cuentas-panel; do
  echo "########## $f"; sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\r//g' "$C/$f.log" | grep -v '^Script ' | tail -n 40
done
echo "########## doctor"
script -q -c "bash scripts/setup/doctor.sh" "$C/07-01-doctor.log" >/dev/null 2>&1; echo "doctor rc=$?"
sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\r//g' "$C/07-01-doctor.log" | grep -v '^Script '
echo "########## anillo"
script -q -c "ls -la /var/lib/ppi-motor-capture/" "$C/07-02-anillo.log" >/dev/null 2>&1
cat "$C/07-02-anillo.log" | grep -v '^Script ' | tail -n 15
echo "########## decisiones"
script -q -c "tail -n 8 logs/motor_decision.log" "$C/07-03-decisiones.log" >/dev/null 2>&1
grep -v '^Script ' "$C/07-03-decisiones.log" | cut -c1-220
echo "########## unidades activas desde"
for u in ppi-motor ppi-motor-capture ppi-dashboard; do echo "$u: $(systemctl show -p ActiveEnterTimestamp --value $u)"; done
echo "########## panel"
ss -ltnp 2>/dev/null | grep 8788
curl -sk -o /dev/null -w 'https /api/variables sin sesion -> %{http_code}\n' https://127.0.0.1:8788/api/variables
curl -s -o /dev/null -w 'http plano -> %{http_code}\n' --max-time 3 http://127.0.0.1:8788/ || true
grep -nE '^(interfaz|modo|raiz) *=' configs/cyberflow.local.toml
