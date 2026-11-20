#!/usr/bin/env bash
# Instalacion unica, idempotente, de la infraestructura del motor de tiempo
# real en VM02 (Sensor). Requiere root real -- NO se ejecuta via el sudoers
# estrecho de useransible (ese solo autoriza ppi-suricata-metrics y
# ppi-pcap-control, sin comodines, a proposito). Ejecutar con acceso root
# temporal, exactamente como se hizo para el fix de /api/error en VM03.
#
# Que hace, en orden, y por que cada paso es seguro de repetir:
#   1. Instala las dos unidades systemd versionadas en este repo.
#   2. Crea el venv de scoring con las mismas versiones congeladas que se
#      usaron para calibrar el modelo (requirements-model.txt), y aborta
#      si la version de Python no coincide con la esperada en vez de
#      instalar en silencio un entorno distinto al que se valido.
#   3. Copia el .joblib y el manifest.json ya pre-cargados en este repo
#      (staged desde VM01 con verificacion SHA-256 antes de tener acceso
#      root -- VM02 esta aislada de /srv/ppi-evidence de VM01, no se puede
#      leer ese volumen directamente desde aqui) a la ruta local que lee
#      el motor.
#   4. Habilita e inicia ppi-motor-capture.service (siempre). NO habilita
#      ppi-motor.service todavia -- eso se hace aparte, a mano, despues de
#      verificar manualmente que la captura y el venv quedaron bien.
#
# No hace falta ninguna linea nueva en useransible-ppi-metrics.sudoers ni
# ninguna ACL: /var/log/suricata/eve.json ya es mundo-legible (root:root,
# modo 644) -- verificado leyendo su contenido real como useransible antes
# de escribir este script, no asumido. ppi-motor-capture corre siempre
# como systemd (root -> tcpdump via -Z) y ppi-motor corre como useransible
# sin sudo, leyendo captura/EVE por permisos ya existentes y su propio log
# en su $HOME.

set -euo pipefail

readonly REPO_ROOT="/home/useransible/vf-sistema-final"
# VM02 confirmado en 2026-08-17 con CPython 3.14.4 (igual que VM01, donde se
# calibro el modelo). Si esto cambia en una reinstalacion futura, el script
# aborta en vez de instalar en silencio un entorno distinto al validado.
readonly EXPECTED_PYTHON_MAJOR_MINOR="3.14"
# VM02 esta aislada de internet (confirmado: pip no resuelve pypi.org).
# Los wheels se descargaron en VM01 con exactamente las versiones de
# requirements-model.txt para cp314-manylinux_2_27/2_28-x86_64 (misma
# Ubuntu 26.04 "resolute", mismo CPython 3.14.4 que VM02) y se
# transfirieron aqui via rsync con verificacion SHA-256.
readonly WHEELS_STAGED="$REPO_ROOT/artifacts/wheels"
readonly MODEL_STAGED="$REPO_ROOT/artifacts/model/ocsvm_scaled.joblib"
readonly MANIFEST_STAGED="$REPO_ROOT/artifacts/model/manifest.json"
# Ambos verificados en VM01 el 2026-08-17 contra SHA256SUMS del propio
# directorio de calibracion y vueltos a verificar tras el rsync a VM02
# (docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md).
readonly MODEL_SHA256_EXPECTED="af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236"
readonly MANIFEST_SHA256_EXPECTED="0a1e8c52dc3282029d9aa1c9a0adbe7cc03c28bbce48bd5b76959e46bdbf5b1b"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ $EUID -eq 0 ]] || die "este script debe ejecutarse como root"
[[ -d "$REPO_ROOT" ]] || die "no existe $REPO_ROOT (¿repo desplegado en useransible?)"

echo "== 1. Unidades systemd =="
install -m 0644 "$REPO_ROOT/configs/sensor/ppi-motor-capture.service" /etc/systemd/system/ppi-motor-capture.service
install -m 0644 "$REPO_ROOT/configs/sensor/ppi-motor.service" /etc/systemd/system/ppi-motor.service
systemctl daemon-reload

echo "== 2. venv de scoring (versiones congeladas de requirements-model.txt) =="
python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$python_version" != "$EXPECTED_PYTHON_MAJOR_MINOR" ]]; then
  die "python3 del Sensor es $python_version, se esperaba $EXPECTED_PYTHON_MAJOR_MINOR (mismatch de version = riesgo real de resultados de scoring distintos a los calibrados; no continuar sin decidir esto explícitamente)"
fi
[[ -d "$WHEELS_STAGED" ]] || die "no se encuentra $WHEELS_STAGED (¿faltó el rsync de artifacts/wheels/ desde VM01?)"
sudo -u useransible python3 -m venv /home/useransible/ppi-motor-venv
sudo -u useransible /home/useransible/ppi-motor-venv/bin/pip install --no-input --no-index --find-links="$WHEELS_STAGED" -r "$REPO_ROOT/requirements-model.txt"
installed_sklearn="$(sudo -u useransible /home/useransible/ppi-motor-venv/bin/python3 -c 'import sklearn; print(sklearn.__version__)')"
[[ "$installed_sklearn" == "1.9.0" ]] || die "scikit-learn instalado ($installed_sklearn) no coincide con el congelado (1.9.0)"

echo "== 3. Modelo congelado =="
[[ -f "$MODEL_STAGED" ]] || die "no se encuentra $MODEL_STAGED (¿faltó el rsync de artifacts/model/ desde VM01?)"
[[ -f "$MANIFEST_STAGED" ]] || die "no se encuentra $MANIFEST_STAGED"
actual_model_sha256="$(sha256sum "$MODEL_STAGED" | awk '{print $1}')"
[[ "$actual_model_sha256" == "$MODEL_SHA256_EXPECTED" ]] || die "hash del modelo no coincide: esperado $MODEL_SHA256_EXPECTED, obtenido $actual_model_sha256"
actual_manifest_sha256="$(sha256sum "$MANIFEST_STAGED" | awk '{print $1}')"
[[ "$actual_manifest_sha256" == "$MANIFEST_SHA256_EXPECTED" ]] || die "hash del manifiesto no coincide: esperado $MANIFEST_SHA256_EXPECTED, obtenido $actual_manifest_sha256"
sudo -u useransible install -d -m 0750 /home/useransible/ppi-motor-model
sudo -u useransible install -m 0640 "$MODEL_STAGED" /home/useransible/ppi-motor-model/ocsvm_scaled.joblib
sudo -u useransible install -m 0640 "$MANIFEST_STAGED" /home/useransible/ppi-motor-model/manifest.json
sudo -u useransible install -d -m 0750 /home/useransible/ppi-motor-logs

echo "== 4. Captura continua =="
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
