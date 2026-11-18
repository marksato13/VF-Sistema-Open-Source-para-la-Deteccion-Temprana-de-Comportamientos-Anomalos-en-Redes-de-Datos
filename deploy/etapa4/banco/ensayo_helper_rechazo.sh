#!/usr/bin/env bash
# Banco (4A, 2026-11-04): la comprobación «el helper rechaza un perfil ajeno» de instalar_srvdmz_sombra.sh.
# Defecto encontrado en vivo: el helper rechaza con rc=1 y, con pipefail, «… | grep -q» daba PARADA aunque la
# respuesta fuera {"ok": false, "rechazo": "perfil_no_autorizado"}. Se extrae el bloque marcado del instalador
# y se ejecuta con sudo simulado. Nada real se toca.
#   bash deploy/etapa4/banco/ensayo_helper_rechazo.sh
set -u
AQUI=$(cd "$(dirname "$0")" && pwd); G="$AQUI/../srvdmz/instalar_srvdmz_sombra.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; mkdir -p "$T/bin"
sed -n '/^# >>> comprobacion-helper/,/^# <<< comprobacion-helper/p' "$G" > "$T/bloque.sh"
[ -s "$T/bloque.sh" ] || { echo "FALLO no se encontró el bloque marcado"; exit 1; }
cat > "$T/bin/sudo" <<'EOF'
#!/usr/bin/env bash
cat > /dev/null
case "$HELPER" in
  rechaza)  echo '{"ok": false, "rechazo": "perfil_no_autorizado"}'; exit 1;;
  acepta)   echo '{"estado": {}, "ok": true, "perfil": "dns"}'; exit 0;;
  otro)     echo '{"ok": false, "rechazo": "peticion_invalida"}'; exit 1;;
  sinsudo)  echo 'sudo: a password is required' >&2; exit 1;;
esac
EOF
chmod +x "$T/bin/sudo"; fallos=0
caso() {  # nombre HELPER esperado(pasa|para)
  local out rc
  out=$(PATH="$T/bin:$PATH" HELPER=$2 bash -c 'set -uo pipefail; parar() { echo "PARADA $*"; exit 1; }; . "$1"; echo PASA' _ "$T/bloque.sh" 2>&1); rc=$?
  if { [ "$3" = pasa ] && [ $rc = 0 ]; } || { [ "$3" = para ] && printf '%s' "$out" | grep -q '^PARADA'; }; then
    echo "OK    $1: $(printf '%s' "$out" | tail -1)"
  else echo "FALLO $1 (rc=$rc): $out"; fallos=$((fallos + 1)); fi
}
caso "rechazo explícito con rc=1 (respuesta real del 04-nov)" rechaza pasa
caso "el helper acepta un perfil ajeno"                       acepta  para
caso "rechazo por otro motivo"                                otro    para
caso "sudo no permitido para cfagente"                        sinsudo para
[ "$fallos" = 0 ] && echo "ENSAYO OK (4/4)" || { echo "ENSAYO CON $fallos FALLOS"; exit 1; }
