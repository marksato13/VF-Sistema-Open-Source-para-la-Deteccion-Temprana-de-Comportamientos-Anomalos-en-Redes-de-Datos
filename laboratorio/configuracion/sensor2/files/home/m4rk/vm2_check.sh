set -u
echo "== host $(hostname)  $(date -u +%FT%TZ)"
echo "== sudo sin contraseña: $(sudo -n true 2>/dev/null && echo SI || echo NO)"
echo "== carpetas"; ls -d ~/cyberflow ~/cyberflow-nuevo ~/cyberflow.k-* 2>/dev/null
echo "== capturas"; ls -la ~/capturas 2>/dev/null
echo "== unidades"; systemctl list-units --all --no-pager 'ppi-*' 2>/dev/null | head -20
