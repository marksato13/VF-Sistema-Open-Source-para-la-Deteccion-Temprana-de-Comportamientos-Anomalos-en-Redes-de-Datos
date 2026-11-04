#!/usr/bin/env bash
# Banco (reconciliación 2026-11-03): la condición previa de instalar_srvdmz_sombra.sh frente a la cadena v1.
# Sustituye systemctl, sudo y nft por simulaciones en un PATH temporal; no instala ni toca nada real.
# Cada caso debe PARAR con el motivo esperado, salvo «limpio», que pasa la condición y para después en la
# verificación del respaldo (directorio vacío), lo que demuestra que la condición no bloquea de más.
#   bash deploy/etapa4/banco/ensayo_precondicion_v1.sh
set -u
AQUI=$(cd "$(dirname "$0")" && pwd); G="$AQUI/../srvdmz/instalar_srvdmz_sombra.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/vacio"
cat > "$T/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
q=0; a=()
for x in "$@"; do [ "$x" = --quiet ] && q=1 || a+=("$x"); done
set -- "${a[@]}"
case "$1 $2" in
  "is-active ppi-enforce-agent.timer") r=$TIMER_AC;;
  "is-enabled ppi-enforce-agent.timer") r=$TIMER_EN;;
  "is-active ppi-enforce-agent.service") r=$SERV_AC;;
  *) r=unknown;;
esac
[ $q = 1 ] || echo "$r"; [ "$r" = active ] || [ "$r" = enabled ]
EOF
cat > "$T/bin/sudo" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -n ] && shift; exec "$@"
EOF
cat > "$T/bin/nft" <<'EOF'
#!/usr/bin/env bash
[ "$NFT" = ilegible ] && { echo "Operation not permitted" >&2; exit 1; }
echo "table inet filter"
[ "$NFT" = v1 ] && echo "table inet cyberflow"
[ "$NFT" = v2 ] && echo "table inet cyberflow_dmz"
exit 0
EOF
chmod +x "$T/bin/"*
fallos=0
caso() {  # nombre esperado TIMER_AC TIMER_EN SERV_AC NFT
  local n=$1 esp=$2 out
  out=$(PATH="$T/bin:$PATH" TIMER_AC=$3 TIMER_EN=$4 SERV_AC=$5 NFT=$6 bash "$G" "$T/vacio" "$T/vacio" x y 2>&1)
  if printf '%s' "$out" | grep -qF -- "$esp"; then echo "OK    $n: $(printf '%s' "$out" | tail -1)"
  else echo "FALLO $n: esperaba «$esp», salió: $out"; fallos=$((fallos + 1)); fi
}
caso "v1 activo (estado del 03/04-nov)" "PARADA el agente v1"            active   enabled  inactive v1
caso "timer parado pero enabled"         "PARADA ppi-enforce-agent.timer" inactive enabled  inactive v1
caso "servicio v1 en ejecución"          "PARADA ppi-enforce-agent.service" inactive disabled active none
caso "tabla v1 restante"                 "PARADA queda la tabla"          inactive disabled inactive v1
caso "nft ilegible (fallo cerrado)"      "PARADA no se pueden leer"       inactive disabled inactive ilegible
caso "solo cyberflow_dmz (no es v1)"     "OK    condición previa"         inactive disabled inactive v2
caso "limpio (sigue al respaldo)"        "PARADA el respaldo no verifica" inactive disabled inactive none

# 4A (2026-11-04): respaldo con ruleset VACÍO (srv-dmz tras P0). Sin constancia de lectura debe parar; con
# ruleset.lectura rc=0 debe pasar esa comprobación y parar después (el paquete del banco no existe).
resp() {  # dir lectura(si|no) contenido
  mkdir -p "$1"; printf '%s' "$3" > "$1/ruleset.nft"; echo 'Defaults env_reset' > "$1/sudoers-defaults.txt"
  [ "$2" = si ] && echo "rc=0 bytes=${#3} utc=X" > "$1/ruleset.lectura"
  ( cd "$1" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
}
resp "$T/r-vacio-sin" no ""; resp "$T/r-vacio-con" si ""; resp "$T/r-lleno" no "table inet filter {}"
caso2() {  # nombre esperado respaldo
  local out; out=$(PATH="$T/bin:$PATH" TIMER_AC=inactive TIMER_EN=disabled SERV_AC=inactive NFT=none bash "$G" "$3" "$T/vacio" x y 2>&1)
  if printf '%s' "$out" | grep -qF -- "$2"; then echo "OK    $1: $(printf '%s' "$out" | tail -1)"
  else echo "FALLO $1: esperaba «$2», salió: $out"; fallos=$((fallos + 1)); fi
}
caso2 "ruleset vacío sin constancia de lectura" "PARADA el respaldo no tiene una lectura válida" "$T/r-vacio-sin"
caso2 "ruleset vacío leído (rc=0)"              "PARADA el paquete no verifica"                 "$T/r-vacio-con"
caso2 "ruleset con contenido (respaldo antiguo)" "PARADA el paquete no verifica"                 "$T/r-lleno"
[ "$fallos" = 0 ] && echo "ENSAYO OK (10/10)" || { echo "ENSAYO CON $fallos FALLOS"; exit 1; }
