set -u
echo "== sudo sin contraseña: $(sudo -n true 2>/dev/null && echo SI || echo NO)"
mkdir -p ~/capturas
rm -rf ~/cyberflow-nuevo && mkdir -p ~/cyberflow-nuevo
tar -xzf ~/cyberflow-main.tgz -C ~/cyberflow-nuevo 2>/dev/null
echo "== B2 · version nueva extraida en ~/cyberflow-nuevo ($(ls ~/cyberflow-nuevo | wc -l) entradas)"
cp -r ~/cyberflow/ruedas ~/cyberflow-nuevo/ruedas
cd ~/cyberflow-nuevo
script -q -c "sha256sum -c docs/dataset/SHA256SUMS" ~/capturas/06-05-sha256.log >/dev/null
echo "== B2 · artefactos: $(grep -c ': OK' ~/capturas/06-05-sha256.log) OK, $(grep -vc ': OK' ~/capturas/06-05-sha256.log) no OK"
grep -v ': OK' ~/capturas/06-05-sha256.log | head -5
