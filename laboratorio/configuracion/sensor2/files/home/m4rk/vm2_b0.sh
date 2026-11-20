set -u
cd ~
echo "== hash del paquete en la VM2"
sha256sum cyberflow-main.tgz
echo "== ruedas disponibles para la reinstalacion"
R=~/cyberflow/ruedas
if [ -d "$R" ]; then
  echo "$(ls "$R" | wc -l) ficheros en $R"
  mkdir -p /tmp/cf-b0 && tar -xzf cyberflow-main.tgz -C /tmp/cf-b0 requirements-model.txt
  faltan=0
  while read -r linea; do
    p=$(echo "$linea" | sed 's/[#;].*//' | tr -d ' ')
    [ -z "$p" ] && continue
    nombre=$(echo "$p" | cut -d= -f1 | tr 'A-Z-' 'a-z_'); version=$(echo "$p" | cut -d= -f3)
    if ls "$R" | tr 'A-Z-' 'a-z_' | grep -q "^${nombre}-${version}-"; then :; else echo "  FALTA rueda: $p"; faltan=1; fi
  done < /tmp/cf-b0/requirements-model.txt
  [ $faltan = 0 ] && echo "  todas las ruedas de requirements-model.txt estan (cp314)"
else
  echo "NO hay $R"
fi
echo "== foto del antes"
for u in cyberflow-capture-nic ppi-motor-capture ppi-motor ppi-dashboard suricata cyberflow-acumular.timer cyberflow-limpieza.timer; do
  printf '  %-26s %s\n' "$u" "$(systemctl is-active $u 2>/dev/null)"
done
echo "  suricata: $(suricata -V 2>/dev/null | head -1)"
echo "  disco libre: $(df -h / | tail -1 | awk '{print $4}')"
echo "  config actual (referencia): $(grep -E '^(interfaz|red_entidades|modo|detector) *=' ~/cyberflow/configs/cyberflow.local.toml | tr '\n' ' ')"
