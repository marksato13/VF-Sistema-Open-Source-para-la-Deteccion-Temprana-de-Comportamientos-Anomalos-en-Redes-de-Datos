#!/usr/bin/env bash
# Instalacion unica, idempotente, de la infraestructura del motor de tiempo
# real en VM02 (Sensor). Requiere root real -- NO se ejecuta via el sudoers
# estrecho de useransible (ese solo autoriza ppi-suricata-metrics y
# ppi-pcap-control, sin comodines, a proposito). Ejecutar con acceso root
# temporal, exactamente como se hizo para el fix de /api/error en VM03.
#
# Que hace, en orden, y por que cada paso es seguro de repetir:
#   1. Instala las dos unidades systemd versionadas en este repo.
#   2. Da a useransible permiso de lectura sobre /var/log/suricata (ACL,
#      sin tocar el dueno/grupo real de los archivos de Suricata).
#   3. Crea el venv de scoring con las mismas versiones congeladas que se
#      usaron para calibrar el modelo (requirements-model.txt), y aborta
#      si la version de Python no coincide con la esperada en vez de
#      instalar en silencio un entorno distinto al que se valido.
#   4. Copia el .joblib congelado desde /srv/ppi-evidence a la ruta local
#      que lee el motor.
#   5. Habilita e inicia ppi-motor-capture.service (siempre). NO habilita
#      ppi-motor.service todavia -- eso se hace aparte, a mano, despues de
#      verificar manualmente que la captura y el venv quedaron bien.
#
# No hace falta ninguna linea nueva en useransible-ppi-metrics.sudoers:
# una vez instalado, ppi-motor-capture corre siempre como systemd
# (root -> tcpdump via -Z) y ppi-motor corre como useransible sin sudo,
# leyendo capture/EVE por ACL y su propio log en su $HOME.

set -euo pipefail

readonly REPO_ROOT="/home/useransible/vf-sistema-final"
# VM01 (donde se calibro el modelo) usa CPython 3.14.4. Antes de ejecutar
# este script en VM02, correr "python3 --version" ahi y confirmar que
# coincide en major.minor -- no se asume, se verifica en cada instalacion.
readonly EXPECTED_PYTHON_MAJOR_MINOR="3.14"
readonly MODEL_SOURCE="/srv/ppi-evidence/artifacts/models/pm-multilayer-v2-v1-calibration-7models/models/ocsvm_scaled.joblib"
# Verificado en VM01 el 2026-08-17 contra SHA256SUMS del propio directorio de
# calibracion (docs/06-features-modelado/08-modelo-final-congelado-ocsvm.md).
readonly MODEL_SHA256_EXPECTED="af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ $EUID -eq 0 ]] || die "este script debe ejecutarse como root"
[[ -d "$REPO_ROOT" ]] || die "no existe $REPO_ROOT (¿repo desplegado en useransible?)"
[[ -n "$MODEL_SHA256_EXPECTED" ]] || die "completa MODEL_SHA256_EXPECTED con el hash real antes de ejecutar (ver docs/06-features-modelado/08-modelo-final-congelado-ocsvm.md)"

echo "== 1. Unidades systemd =="
install -m 0644 "$REPO_ROOT/configs/sensor/ppi-motor-capture.service" /etc/systemd/system/ppi-motor-capture.service
install -m 0644 "$REPO_ROOT/configs/sensor/ppi-motor.service" /etc/systemd/system/ppi-motor.service
systemctl daemon-reload

echo "== 2. ACL de lectura sobre /var/log/suricata para useransible =="
command -v setfacl >/dev/null 2>&1 || die "falta el paquete acl (setfacl no encontrado)"
setfacl -R -m u:useransible:rX /var/log/suricata
setfacl -d -R -m u:useransible:rX /var/log/suricata

echo "== 3. venv de scoring (versiones congeladas de requirements-model.txt) =="
python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$python_version" != "$EXPECTED_PYTHON_MAJOR_MINOR" ]]; then
  die "python3 del Sensor es $python_version, se esperaba $EXPECTED_PYTHON_MAJOR_MINOR (mismatch de version = riesgo real de resultados de scoring distintos a los calibrados; no continuar sin decidir esto explícitamente)"
fi
sudo -u useransible python3 -m venv /home/useransible/ppi-motor-venv
sudo -u useransible /home/useransible/ppi-motor-venv/bin/pip install --no-input -r "$REPO_ROOT/requirements-model.txt"
installed_sklearn="$(sudo -u useransible /home/useransible/ppi-motor-venv/bin/python3 -c 'import sklearn; print(sklearn.__version__)')"
[[ "$installed_sklearn" == "1.9.0" ]] || die "scikit-learn instalado ($installed_sklearn) no coincide con el congelado (1.9.0)"

echo "== 4. Modelo congelado =="
[[ -f "$MODEL_SOURCE" ]] || die "no se encuentra $MODEL_SOURCE (¿volumen de evidencia montado?)"
actual_sha256="$(sha256sum "$MODEL_SOURCE" | awk '{print $1}')"
[[ "$actual_sha256" == "$MODEL_SHA256_EXPECTED" ]] || die "hash del modelo de origen no coincide: esperado $MODEL_SHA256_EXPECTED, obtenido $actual_sha256"
sudo -u useransible install -d -m 0750 /home/useransible/ppi-motor-model
sudo -u useransible install -m 0640 "$MODEL_SOURCE" /home/useransible/ppi-motor-model/ocsvm_scaled.joblib
sudo -u useransible install -d -m 0750 /home/useransible/ppi-motor-logs

echo "== 5. Captura continua =="
systemctl enable --now ppi-motor-capture.service
sleep 3
systemctl is-active --quiet ppi-motor-capture.service || die "ppi-motor-capture.service no quedo activo"
echo "captura activa. Verificar manualmente unos segundos con:"
echo "  ls -la /var/lib/ppi-motor-capture/"
echo "  sudo -u useransible test -r /var/lib/ppi-motor-capture/\$(ls /var/lib/ppi-motor-capture | head -1) && echo useransible-puede-leer"
echo
echo "Cuando esto se vea bien, iniciar el motor a mano (no automatico todavia):"
echo "  systemctl enable --now ppi-motor.service"
echo "  journalctl -u ppi-motor.service -f"
