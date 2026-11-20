# shellcheck shell=bash
# Evidencia con manifiesto sobre ficheros FINALIZADOS (pendiente P5 del cierre 4A, 2026-11-06). Se usa con «source».
#
# Fallo que corrige: cierre4a_*.sh hacía «exec > >(tee "$EV/salida.txt")» y calculaba SHA256SUMS mientras tee seguía
# abierto; el «echo == fin …» posterior (y lo que tee aún tenía en búfer) cambiaba salida.txt DESPUÉS de su hash, y
# «sha256sum -c» fallaba. Aquí: ev_abrir redirige a tee; ev_sellar devuelve la salida al terminal, CIERRA la tubería,
# ESPERA a que tee termine, comprueba que nada cambia durante 1 s y solo entonces escribe SHA256SUMS y lo verifica.
# Después de ev_sellar no se escribe nada más en $EV.
#
#   source evidencia.sh; ev_abrir DIR; ...; ev_sellar DIR

ev_abrir() {
  EV_DIR="$1"; mkdir -p "$EV_DIR"
  exec 3>&1 4>&2
  exec > >(tee "$EV_DIR/salida.txt") 2>&1
  EV_TEE=$!
}

ev_sellar() {
  local d="${1:-$EV_DIR}" a b
  echo "== fin $(date -u +%FT%TZ) evidencia en $d"
  exec 1>&3 2>&4 3>&- 4>&-
  [ -n "${EV_TEE:-}" ] && wait "$EV_TEE" 2>/dev/null
  a=$(cd "$d" && find . -type f ! -name SHA256SUMS -printf '%p %s %T@\n' | LC_ALL=C sort)
  sleep 1
  b=$(cd "$d" && find . -type f ! -name SHA256SUMS -printf '%p %s %T@\n' | LC_ALL=C sort)
  if [ "$a" != "$b" ]; then echo "PARADA la evidencia sigue cambiando: no se sella"; return 1; fi
  ( cd "$d" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum > SHA256SUMS \
      && sha256sum -c --quiet SHA256SUMS ) || { echo "PARADA SHA256SUMS no verifica"; return 1; }
  echo "SELLADO $d ($(wc -l < "$d/SHA256SUMS") ficheros)"
}
