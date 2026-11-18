# shellcheck shell=bash
# Base común de los instaladores P4 (bastion_p4.sh, srvdmz_p4.sh). VERSION p4-instalador 2026-11-06.2. Se usa con «source».
#
# Reglas (corrección pedida tras la revisión de 313f8f8):
#  - Cada operación crítica pasa por «paso»: se comprueba su código de salida real; si falla, NUNCA se escribe OK.
#  - systemd-analyze verify se decide por su código de salida (su texto solo se registra).
#  - RESPALDO inmutable (R) separado de la EVIDENCIA de la instalación (E). R se sella, se verifica en modo estricto
#    (mismo conjunto de ficheros que el manifiesto, todos con su hash) y se deja de solo lectura ANTES del primer cambio.
#    Nada de la instalación se escribe dentro de R.
#  - Fallo ANTES del primer cambio  -> rc 10 «PARADA SIN CAMBIOS».
#    Fallo DESPUÉS (cambio parcial)  -> REVERSIÓN AUTOMÁTICA desde R y verificación de la recuperación:
#        rc 20 «REVERTIDO AUTOMÁTICAMENTE» (estado del respaldo verificado; no se sigue a la fase siguiente);
#        rc 30 «REVERSIÓN AUTOMÁTICA FALLIDA — INTERVENCIÓN MANUAL» (se detiene; se dice qué falta).
#    Éxito -> rc 0 y la única línea «RESULTADO: OK».
#  - Banco: CF_BANCO=1 permite sustituir raíz y órdenes (CF_RAIZ, CF_SUDO, CF_SYSTEMCTL, CF_SYSTEMD_ANALYZE, CF_NFT,
#    CF_SSH). Sin CF_BANCO=1 esas variables se ignoran.

P4_VERSION="p4-instalador 2026-11-06.2"
p4_entorno() {  # $1 = orden sudo por omisión en el host
  RAIZ=""; SUDO="$1"; SYSTEMCTL=systemctl; SYSTEMD_ANALYZE=systemd-analyze; NFT="$1 nft"; SSH=ssh
  if [ "${CF_BANCO:-0}" = 1 ]; then
    RAIZ="${CF_RAIZ:?}"; SUDO="${CF_SUDO:?}"; SYSTEMCTL="${CF_SYSTEMCTL:?}"; SYSTEMD_ANALYZE="${CF_SYSTEMD_ANALYZE:?}"
    NFT="${CF_NFT:-$SUDO nft}"; SSH="${CF_SSH:-ssh}"
  fi
  P4_CAMBIOS=0; P4_FASE_SIGUIENTE=""
}

p4_log() { echo "$(date -u +%FT%TZ) $*"; }

# paso "descripción" orden...   -> OK o fallo controlado
paso() {
  local d="$1"; shift
  "$@"; local rc=$?
  if [ "$rc" -ne 0 ]; then p4_log "FALLO [$d] rc=$rc"; p4_fallo "$d"; fi
  p4_log "ok    $d"
}
# rpaso: igual, pero dentro de la reversión: anota el fallo y sigue intentando el resto (nunca recursivo)
rpaso() {
  local d="$1"; shift
  "$@"; local rc=$?
  if [ "$rc" -ne 0 ]; then p4_log "FALLO-REVERSIÓN [$d] rc=$rc"; P4_REV_FALLOS+=("$d"); return 1; fi
  p4_log "ok    (reversión) $d"
}
cambio() { P4_CAMBIOS=1; }   # se llama JUSTO ANTES de la primera operación que modifica el host

p4_fallo() {
  local d="$1"
  if [ "$P4_CAMBIOS" = 0 ]; then
    echo "RESULTADO: PARADA SIN CAMBIOS — falló «$d» antes de modificar nada. Respaldo: ${R:-ninguno}"
    p4_sellar_e; exit 10
  fi
  echo "RESULTADO PARCIAL: falló «$d» con cambios ya hechos -> REVERSIÓN AUTOMÁTICA desde $R"
  P4_REV_FALLOS=()
  p4_revertir_desde "$R"            # definida por cada instalador; usa rpaso
  if [ "${#P4_REV_FALLOS[@]}" -eq 0 ]; then
    echo "RESULTADO: REVERTIDO AUTOMÁTICAMENTE al respaldo $R (hashes, unidad activa y sombra verificados)."
    echo "NO continuar${P4_FASE_SIGUIENTE:+ a $P4_FASE_SIGUIENTE} ni a la observación hasta revisar la causa: «$d»."
    p4_sellar_e; exit 20
  fi
  echo "RESULTADO: REVERSIÓN AUTOMÁTICA FALLIDA — DETENIDO. INTERVENCIÓN MANUAL NECESARIA."
  echo "  Falló al instalar: «$d». Falló al revertir: ${P4_REV_FALLOS[*]}"
  echo "  Respaldo íntegro y de solo lectura en $R (ficheros originales, modos y hashes en instalados-antes.sha256)."
  echo "  No continuar${P4_FASE_SIGUIENTE:+ a $P4_FASE_SIGUIENTE} ni a la observación."
  p4_sellar_e; exit 30
}

p4_sellar_e() { [ -n "${E:-}" ] && ev_sellar "$E" || true; }

# ---------------------------------------------------------------- respaldo inmutable
# p4_respaldo DIR fichero...   copia (como root, conservando modo y dueño), anota modos y hashes, sella, verifica
# en modo estricto y deja DIR de solo lectura. Todo antes del primer cambio.
p4_respaldo() {
  local dir="$1"; shift
  paso "crear respaldo $dir" mkdir -p "$dir/ficheros"
  local f
  for f in "$@"; do
    paso "respaldar $f" $SUDO cp -p "$f" "$dir/ficheros/$(basename "$f")"
    paso "anotar modo de $f" p4_anotar_modo "$f" "$dir/modos.txt"
  done
  paso "hashes previos" p4_hashes "$dir/instalados-antes.sha256" "$@"
  paso "dueño del respaldo" $SUDO chown -R "$(id -u):$(id -g)" "$dir"
  paso "sellar respaldo" p4_manifiesto "$dir"
  paso "respaldo de solo lectura" chmod -R a-w "$dir"
  paso "verificar respaldo (estricto)" p4_verificar_respaldo "$dir"
}
p4_anotar_modo() { $SUDO stat -c '%a %U %G %n' "$1" >> "$2"; }
p4_hashes() { local out="$1"; shift; $SUDO sha256sum "$@" > "$out"; }
p4_manifiesto() { ( cd "$1" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS ); }
# estricto: todos los hashes verifican Y el conjunto de ficheros es exactamente el del manifiesto
p4_verificar_respaldo() {
  local d="$1"
  [ -f "$d/SHA256SUMS" ] || { echo "sin SHA256SUMS en $d"; return 1; }
  ( cd "$d" && sha256sum -c --strict --quiet SHA256SUMS ) || return 1
  diff <(cd "$d" && find . -type f ! -name SHA256SUMS | LC_ALL=C sort) \
       <(sed -E 's/^[0-9a-f]{64} [ *]//' "$d/SHA256SUMS" | LC_ALL=C sort) > /dev/null \
    || { echo "el respaldo $d tiene ficheros que no están en su manifiesto"; return 1; }
}
# restaura un fichero del respaldo con su modo y dueño originales
p4_restaurar() {
  local f="$1" dir="$2" m u g
  read -r m u g _ < <(grep -F " $f" "$dir/modos.txt" | awk -v f="$f" '$4==f' | tail -1)
  [ -n "${m:-}" ] || { echo "sin modo anotado para $f"; return 1; }
  $SUDO install -o "$u" -g "$g" -m "$m" "$dir/ficheros/$(basename "$f")" "$f"
}
p4_hashes_iguales() {  # $1 = fichero de hashes esperado; resto = rutas
  local esp="$1"; shift
  diff <(awk '{print $1}' "$esp") <($SUDO sha256sum "$@" | awk '{print $1}') > /dev/null
}
p4_hashes_paquete() {  # cada destino tiene el hash de su origen en el paquete: pares origen destino
  while [ $# -ge 2 ]; do
    [ "$(sha256sum < "$1" | cut -d' ' -f1)" = "$($SUDO sha256sum < "$2" | cut -d' ' -f1)" ] || { echo "difiere $2"; return 1; }
    shift 2
  done
}
# systemd-analyze verify: decide el CÓDIGO DE SALIDA; el texto se guarda como evidencia
p4_verify_unidad() {
  local u="$1" out rc
  out=$($SYSTEMD_ANALYZE verify "$u" 2>&1); rc=$?
  [ -n "$out" ] && printf 'systemd-analyze verify %s (rc=%s):\n%s\n' "$u" "$rc" "$out"
  return "$rc"
}
p4_activa() { $SYSTEMCTL is-active --quiet "$1"; }
p4_pid() { $SYSTEMCTL show -p MainPID --value "$1"; }
p4_cmdline() { local p; p=$(p4_pid "$1") && [ -n "$p" ] && [ "$p" != 0 ] && tr '\0' ' ' < "/proc/$p/cmdline"; }
