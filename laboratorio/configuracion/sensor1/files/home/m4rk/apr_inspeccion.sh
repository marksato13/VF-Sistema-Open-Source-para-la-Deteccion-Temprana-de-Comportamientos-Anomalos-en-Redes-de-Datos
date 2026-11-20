set -u
cd ~/cyberflow
echo "== sudo permitido sin contrasena:"; sudo -n -l 2>&1 | sed -n '/may run/,$p' | head -20
echo "== particionados / informes de la nota L:"
find artifacts -maxdepth 3 \( -name '*particion*' -o -name '*partic*' -o -name 'if-*.json' -o -name '*.joblib' \) -printf '%TY-%Tm-%Td %10s %p\n' 2>/dev/null | sort | tail -20
echo "== rutas y motor del local.toml:"; sed -n '/^\[rutas\]/,/^\[panel\]/p' configs/cyberflow.local.toml | grep -vE '^\s*#|^\s*$' | head -30
echo "== disco libre:"; df -h ~ | tail -1
echo "== unidad del panel (ExecStart):"; systemctl cat ppi-dashboard 2>/dev/null | grep -E 'config-toml|ExecStart' | head -3
ls -la configs/cyberflow.local.toml
