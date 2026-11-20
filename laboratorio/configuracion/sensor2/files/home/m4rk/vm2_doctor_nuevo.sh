set -u
cd ~/cyberflow
cp ~/doctor.sh scripts/setup/doctor-nuevo.sh
bash scripts/setup/doctor-nuevo.sh 2>&1 | sed -e 's/\x1b\[[0-9;]*m//g' | sed -n '/^3\./,/^4\./p;/Resumen/,$p'
rm -f scripts/setup/doctor-nuevo.sh
