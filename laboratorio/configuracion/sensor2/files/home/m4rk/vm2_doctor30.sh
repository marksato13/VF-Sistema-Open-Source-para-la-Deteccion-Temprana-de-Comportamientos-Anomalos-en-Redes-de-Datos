set -u
# Corre doctor.sh a las 04:03 UTC (30 min despues de instalar) y guarda la salida.
espera=$(( $(date -u -d '04:03' +%s) - $(date -u +%s) ))
(( espera > 0 )) && sleep "$espera"
cd ~/cyberflow
{ date -u +%FT%TZ
  script -q -c "bash scripts/setup/doctor.sh" ~/capturas/07-01c-doctor-30min.log >/dev/null 2>&1
  sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\r//g' ~/capturas/07-01c-doctor-30min.log | grep -v '^Script '
  echo "anillo: $(ls /var/lib/ppi-motor-capture | wc -l) ficheros, mas viejo $(ls /var/lib/ppi-motor-capture | head -1)"
  echo "dataset: $(wc -l < artifacts/linea-base/multilayer-v3.csv) lineas"
  echo FIN
} > ~/capturas/doctor30.txt 2>&1
