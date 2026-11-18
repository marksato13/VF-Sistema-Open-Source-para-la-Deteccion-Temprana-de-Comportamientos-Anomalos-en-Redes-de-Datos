#!/usr/bin/env bash
# [SENSOR1 m4rk] Comprueba de qué ficheros cargaría cada proceso de la Etapa 4 sus módulos propios.
# Solo lee (ejecuta --help); no arranca ni para nada. Lo usa instalar_sensor1_sombra.sh (fase 2) y
# verificar_sensor1.sh, y se puede repetir en cualquier momento.
#
#   bash comprobar_importaciones.sh <DST_candidato> <python_del_venv> <cwd_de_la_unidad> <dir_prohibido>
#   p. ej.  bash comprobar_importaciones.sh /home/m4rk/cyberflow-e4/ec78ca5 \
#             /home/m4rk/cyberflow/.venv/bin/python /home/m4rk/cyberflow /home/m4rk/cyberflow/scripts
#
# Mismo intérprete, mismo WorkingDirectory y ruta absoluta del guion que las unidades. Con -v Python
# escribe una línea "# code object from <ruta>" por módulo cargado (ruta entre comillas si viene de un
# .pyc, sin comillas si se compila del fuente: comprobado en el banco con Python 3.13). Ninguno propio
# puede venir de <dir_prohibido> (el despliegue anterior): publicar_feed_v2 intenta primero
# "from scripts.engine import ..." y solo si falla usa su propio directorio.
# Salida: "OK importaciones" o "PARADA ..." (código 1).
set -uo pipefail
DST="${1:?DST}"; PY="${2:?python}"; CWD="${3:?cwd}"; PROHIBIDO="${4:?dir prohibido}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cd "$CWD" || { echo "PARADA sin $CWD"; exit 1; }
for s in motor_decision publicar_feed_v2 detector_rapido; do
  PYTHONDONTWRITEBYTECODE=1 "$PY" -v "$DST/scripts/engine/$s.py" --help > /dev/null 2> "$TMP/$s.txt" \
    || { echo "PARADA $s.py --help falla"; tail -3 "$TMP/$s.txt"; exit 1; }
  if grep -E "^# code object from '?$PROHIBIDO/" "$TMP/$s.txt"; then echo "PARADA $s carga código de $PROHIBIDO"; exit 1; fi
  n=$(grep -cE "^# code object from '?$DST/scripts/" "$TMP/$s.txt")
  [ "$n" -gt 0 ] || { echo "PARADA $s no carga nada del candidato"; exit 1; }
  echo "$s: $n módulos del candidato: $(grep -oE "^# code object from '?$DST/scripts/[^' ]+" "$TMP/$s.txt" \
        | sed -E "s|.*/scripts/||; s|__pycache__/||; s|\.cpython-[0-9]+\.pyc|.py|" | sort -u | tr '\n' ' ')"
done
"$PY" "$DST/scripts/engine/motor_decision.py" --help | grep -q -- '--disparo' || { echo "PARADA motor sin --disparo"; exit 1; }
echo "OK importaciones"
