#!/usr/bin/env bash
# Banco (4A, 2026-11-04): comprobaciones de los instaladores que pararon (o habrían parado) en falso en vivo.
#   U  instalar_srvdmz_sombra.sh  «la unidad lleva --aplicar»: el grep veía el COMENTARIO «SIN --aplicar».
#   K  instalar_sensor1_sombra.sh llave-rele: diff | grep -c | grep -qx 1 con pipefail paraba siempre.
#   L  instalar_bastion_sombra.sh «llaves limitadas»: ssh (rc=1 del comando forzado) | grep -q con pipefail.
# Se extraen los bloques marcados y se ejecutan con dobles; además, control con la forma antigua. Nada real.
#   bash deploy/etapa4/banco/ensayo_comprobaciones_4a.sh
set -u
AQUI=$(cd "$(dirname "$0")" && pwd); E="$AQUI/.."
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; mkdir -p "$T/bin"
fallos=0
bloque() { sed -n "/^ *# >>> $2/,/^ *# <<< $2/p" "$1"; }
ejec() {  # bloque_fichero -> imprime PASA o PARADA
  bash -c 'set -uo pipefail; parar() { echo "PARADA $*"; exit 1; }; . "$1"; echo PASA' _ "$1" 2>&1 | tail -1
}
esperar() {  # nombre esperado(PASA|PARADA) salida
  case "$3" in "$2"*) echo "OK    $1: $3";; *) echo "FALLO $1: esperaba $2, salió: $3"; fallos=$((fallos + 1));; esac
}

# --- U: unidad v2 real (con el comentario) y una con --aplicar en ExecStart
bloque "$E/srvdmz/instalar_srvdmz_sombra.sh" comprobacion-unidad | sed "s#/etc/systemd/system/ppi-enforce-agent-v2-dmz.service#\"\$UNIDAD\"#" > "$T/u.sh"
[ -s "$T/u.sh" ] || { echo "FALLO bloque U no encontrado"; exit 1; }
U="$E/unidades/srvdmz/ppi-enforce-agent-v2-dmz.service"
sed 's#--perfil dmz#--perfil dmz --aplicar#' "$U" > "$T/u-aplicar.service"
sed 's#--perfil dmz#--perfil dmz --aplicar=si#' "$U" > "$T/u-aplicar-igual.service"
esperar "U unidad real (comentario «SIN --aplicar»)" PASA   "$(UNIDAD=$U ejec "$T/u.sh")"
esperar "U ExecStart con --aplicar"                  PARADA "$(UNIDAD=$T/u-aplicar.service ejec "$T/u.sh")"
esperar "U ExecStart con --aplicar=si"               PARADA "$(UNIDAD=$T/u-aplicar-igual.service ejec "$T/u.sh")"
esperar "U control: grep antiguo sobre la unidad real" PARADA \
  "$(bash -c 'parar() { echo "PARADA $*"; exit 1; }; grep -q -- "--aplicar" "$1" && parar antigua; echo PASA' _ "$U")"

# --- K: authorized_keys con una línea añadida, dos, y una cambiada
bloque "$E/sensor1/instalar_sensor1_sombra.sh" comprobacion-authorized-keys > "$T/k.sh"
[ -s "$T/k.sh" ] || { echo "FALLO bloque K no encontrado"; exit 1; }
mkdir -p "$T/r" "$T/h/.ssh"; printf 'ssh-ed25519 AAAA1 a\nssh-ed25519 AAAA2 b\n' > "$T/r/authorized_keys"
k() { cp "$T/r/authorized_keys" "$T/h/.ssh/authorized_keys"; eval "$1"; R="$T/r" HOME="$T/h" ejec "$T/k.sh"; }
esperar "K una línea añadida (caso real)" PASA   "$(k 'echo "command=x,restrict ssh-ed25519 AAAA3 rele" >> "$T/h/.ssh/authorized_keys"')"
esperar "K dos líneas añadidas"           PARADA "$(k 'printf "x\ny\n" >> "$T/h/.ssh/authorized_keys"')"
esperar "K una añadida y otra quitada"    PARADA "$(k 'sed -i 1d "$T/h/.ssh/authorized_keys"; echo z >> "$T/h/.ssh/authorized_keys"')"
esperar "K control: forma antigua con una línea añadida" PARADA "$(cp "$T/r/authorized_keys" "$T/h/.ssh/authorized_keys"; echo z >> "$T/h/.ssh/authorized_keys"
  bash -c 'set -uo pipefail; diff "$1" "$2" | grep -c "^>" | grep -qx 1 && echo PASA || echo PARADA' _ "$T/r/authorized_keys" "$T/h/.ssh/authorized_keys")"

# --- L: llaves del relé limitadas (ssh simulado: comando forzado que rechaza con rc=1, o shell abierta)
bloque "$E/bastion/instalar_bastion_sombra.sh" comprobacion-llaves-limitadas > "$T/l.sh"
[ -s "$T/l.sh" ] || { echo "FALLO bloque L no encontrado"; exit 1; }
cat > "$T/bin/ssh" <<'EOF'
#!/usr/bin/env bash
case "$SSH_MODO" in
  limitada) echo "orden no permitida" >&2; exit 1;;
  abierta)  echo "uid=1000(m4rk) gid=1000(m4rk)"; exit 0;;
  caida)    echo "ssh: connect to host 10.10.60.11 port 22: Connection refused" >&2; exit 255;;
esac
EOF
chmod +x "$T/bin/ssh"
esperar "L ambas llaves limitadas (caso real)" PASA   "$(PATH="$T/bin:$PATH" SSH_MODO=limitada K=/x ejec "$T/l.sh")"
esperar "L llave con shell abierta"            PARADA "$(PATH="$T/bin:$PATH" SSH_MODO=abierta K=/x ejec "$T/l.sh")"
esperar "L sin conexión"                       PARADA "$(PATH="$T/bin:$PATH" SSH_MODO=caida K=/x ejec "$T/l.sh")"
esperar "L control: forma antigua con llave limitada" PARADA "$(PATH="$T/bin:$PATH" SSH_MODO=limitada bash -c 'set -uo pipefail; ssh x id 2>&1 | grep -q "orden no permitida" && echo PASA || echo PARADA')"

[ "$fallos" = 0 ] && echo "ENSAYO OK (12/12)" || { echo "ENSAYO CON $fallos FALLOS"; exit 1; }
