set -u
cd ~/cyberflow-nuevo
# interfaz, red, escenario (1 fija el modo), usuario: lo que proponga; raiz: la ubicacion final; s = escribir
printf '\n\n\n\n/home/m4rk/cyberflow\ns\n' | script -q -c "bash scripts/setup/configurar.sh" ~/capturas/06-01-asistente.log >/dev/null 2>&1
sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\r//g' ~/capturas/06-01-asistente.log | grep -v '^Script '
echo "== resultado"
grep -nE '^(interfaz|mac|red_entidades|modo|usuario|raiz|detector) *=' configs/cyberflow.local.toml
