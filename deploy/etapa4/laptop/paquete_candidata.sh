#!/usr/bin/env bash
# [LAPTOP Git Bash] Construye el paquete de la candidata para la Etapa 4. No toca el laboratorio.
#
#   bash deploy/etapa4/laptop/paquete_candidata.sh <salida_dir>
#
# El código que se instala es el de ec78ca5 (cierre técnico de la Etapa 3). El commit que contiene
# este guion solo AÑADE herramientas (scripts/etapa4, deploy/etapa4, tests): el guion lo comprueba
# y aborta si cualquier fichero del motor, extractor, publicador, agente, relé o esquema difiere.
# Salida: cyberflow-e4-ec78ca5.tar.gz, su .sha256 y SHA256SUMS (de cada fichero del paquete).
set -euo pipefail
CAND=ec78ca56a3a8f4bb17fda967a7f0abe0e9a2c742
SALIDA="${1:?uso: paquete_candidata.sh <salida_dir>}"
RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ"
CODIGO=(scripts/engine scripts/features scripts/enforce configs/features deploy/enforcement)
HERRAMIENTAS=(scripts/etapa4 deploy/etapa4)

git cat-file -e "$CAND^{commit}" || { echo "PARADA: no está el commit $CAND"; exit 1; }
git merge-base --is-ancestor "$CAND" HEAD || { echo "PARADA: HEAD no desciende de $CAND"; exit 1; }
if ! git diff --quiet "$CAND" HEAD -- "${CODIGO[@]}"; then
  echo "PARADA: el código difiere de $CAND:"; git diff --stat "$CAND" HEAD -- "${CODIGO[@]}"; exit 1
fi
[ -z "$(git status --porcelain -- "${CODIGO[@]}" "${HERRAMIENTAS[@]}")" ] \
  || { echo "PARADA: hay cambios sin confirmar en el árbol"; git status --short -- "${CODIGO[@]}" "${HERRAMIENTAS[@]}"; exit 1; }

mkdir -p "$SALIDA"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# El código sale de ec78ca5 (no del árbol de trabajo); las herramientas, de HEAD.
git archive --format=tar "$CAND" "${CODIGO[@]}" | tar -x -C "$TMP"
git archive --format=tar HEAD "${HERRAMIENTAS[@]}" | tar -x -C "$TMP"
find "$TMP" -name '__pycache__' -prune -exec rm -rf {} +
printf '%s\n' "candidato=$CAND" "herramientas=$(git rev-parse HEAD)" \
  "construido_utc=$(date -u +%FT%TZ)" > "$TMP/VERSION-ETAPA4"
( cd "$TMP" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
# --force-local: en Git Bash una ruta "C:/..." se tomaría por host remoto
tar --force-local --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-11-02 00:00Z' \
  -C "$TMP" -czf "$SALIDA/cyberflow-e4-ec78ca5.tar.gz" .
cp "$TMP/SHA256SUMS" "$SALIDA/SHA256SUMS"
( cd "$SALIDA" && sha256sum cyberflow-e4-ec78ca5.tar.gz > cyberflow-e4-ec78ca5.tar.gz.sha256 )
echo "paquete: $SALIDA/cyberflow-e4-ec78ca5.tar.gz"
cat "$SALIDA/cyberflow-e4-ec78ca5.tar.gz.sha256"
echo "ficheros: $(wc -l < "$SALIDA/SHA256SUMS")"
