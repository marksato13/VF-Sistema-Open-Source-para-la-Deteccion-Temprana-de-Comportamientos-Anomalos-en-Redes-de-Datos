#!/usr/bin/env bash
# [CLIENTES adminclientes] Generadores legítimos de E-carga v2: cyberflow-lab.target y sus seis unidades de perfiles.
# VERSION 2026-11-06.2 (sustituye a la de guiones-c7f24510, que daba rc 0 tras un start fallido).
#
#   generadores.sh estado            solo lectura; rc 0 si todas las consultas se leyeron, 5 si alguna falló
#   generadores.sh permisos          solo lectura: sudo -n -l (líneas del target), zona, hash y estado
#   generadores.sh configuracion     solo lectura: las seis unidades corresponden a la configuración esperada
#   generadores.sh arrancar          SOLO con orden explícita de Mark: sudo -n systemctl start del target + confirmación
#   generadores.sh parar             sudo -n systemctl stop del target + confirmación
#   generadores.sh comprobar-parado  solo lectura: confirma la parada sin volver a pedirla
#
# Códigos de salida (inequívocos):
#   0  operación hecha y CONFIRMADA (o consulta completa, en estado/configuracion/comprobar-parado)
#   2  uso o precondición no cumplida: no se ha intentado ninguna mutación
#   3  el comando systemctl start/stop devolvió error (se imprime el estado leído después, como evidencia)
#   4  estado leído sin errores, pero NO coincide con lo esperado (arranque parcial, unidades o procesos vivos)
#   5  estado desconocido: alguna consulta falló y no se puede confirmar ni negar
# Nunca modifica el generador ni las unidades, nunca las habilita y nunca para nada por su cuenta tras un arranque
# fallido: quien lo llama decide (el procedimiento manda ejecutar «parar» si «arrancar» no da 0).
#
# Configuración esperada (argv de las unidades, evidencia 08-carga/clientes_ro2.txt y servicios-*.txt del 01-nov):
#   cyberflow-lab-<perfil>.service ejecuta clientes_lab.py --perfil <perfil> --origen <IP>, IP .21–.26.
# Para que la parada permitida por sudo (stop del TARGET) detenga las unidades, cada una debe tener
# PartOf=cyberflow-lab.target; «arrancar» lo exige antes de arrancar.
set -u
set -o pipefail
VERSION=2026-11-06.2
GEN=${CF_GEN:-$HOME/laboratorio/clientes_lab.py}
PROC=${CF_PROC:-/proc}
HASH_ESPERADO=ae5134a778e66d90f5c3fbcd47323e328f3422cf4ba8d5197649f402c1d4cdc3
TARGET=cyberflow-lab.target
PERFILES="ofimatica:10.10.20.21 navegacion:10.10.20.22 descargas:10.10.20.23 aplicacion:10.10.20.24 ligero:10.10.20.25 erratico:10.10.20.26"
ESPERA=${CF_ESPERA:-1}          # s entre lecturas de confirmación
ESPERA_MAX=${CF_ESPERA_MAX:-20} # s máximos para confirmar
ESTABLE=${CF_ESTABLE:-5}        # s que los PID deben mantenerse para confirmar un arranque
RC_OK=0; RC_USO=2; RC_OPERACION=3; RC_NO_CONFIRMADO=4; RC_DESCONOCIDO=5

hash_gen() {  # imprime el sha256 completo o falla
  local h
  h=$(sha256sum < "$GEN" 2>/dev/null | cut -d' ' -f1) || return 1
  [[ $h =~ ^[0-9a-f]{64}$ ]] || return 1
  echo "$h"
}

campo() { sed -n "s/^$1=//p" <<<"$2" | head -1; }

# leer_unidad UNIDAD -> globales U_LS U_AS U_SS U_PID U_NR U_PARTOF U_EXEC; rc 1 si la consulta falla o viene incompleta
leer_unidad() {
  local o
  o=$(systemctl show -p LoadState -p ActiveState -p SubState -p MainPID -p NRestarts -p PartOf -p ExecStart "$1" 2>&1)
  local rc=$?
  if [ $rc != 0 ]; then Q_ERR="systemctl show $1 rc=$rc: ${o:0:160}"; return 1; fi
  U_LS=$(campo LoadState "$o"); U_AS=$(campo ActiveState "$o"); U_SS=$(campo SubState "$o")
  U_PID=$(campo MainPID "$o"); U_NR=$(campo NRestarts "$o"); U_PARTOF=$(campo PartOf "$o"); U_EXEC=$(campo ExecStart "$o")
  if [ -z "$U_LS" ] || [ -z "$U_AS" ] || [ -z "$U_SS" ] || ! [[ $U_PID =~ ^[0-9]+$ ]] || ! [[ $U_NR =~ ^[0-9]+$ ]]; then
    Q_ERR="systemctl show $1: respuesta incompleta (LoadState=$U_LS ActiveState=$U_AS MainPID=$U_PID NRestarts=$U_NR)"; return 1
  fi
}

leer_target() {  # globales T_LS T_AS T_UF
  local o
  o=$(systemctl show -p LoadState -p ActiveState -p UnitFileState "$TARGET" 2>&1)
  local rc=$?
  if [ $rc != 0 ]; then Q_ERR="systemctl show $TARGET rc=$rc: ${o:0:160}"; return 1; fi
  T_LS=$(campo LoadState "$o"); T_AS=$(campo ActiveState "$o"); T_UF=$(campo UnitFileState "$o")
  if [ -z "$T_LS" ] || [ -z "$T_AS" ]; then Q_ERR="systemctl show $TARGET: respuesta incompleta"; return 1; fi
}

cmdline_de() {  # argv de un PID con espacios; rc 1 si no se puede leer
  local f="$PROC/$1/cmdline" s
  [ -r "$f" ] || return 1
  s=$(tr '\0' ' ' < "$f" 2>/dev/null) || return 1
  [ -n "$s" ] || return 1
  echo "$s"
}

procesos_gen() {  # PID de todos los procesos cuyo argv contiene clientes_lab.py; rc 1 si no se puede listar PROC
  local d c
  [ -d "$PROC" ] && [ -r "$PROC" ] || return 1
  for d in "$PROC"/[0-9]*; do
    [ -e "$d" ] || continue
    c=$(cmdline_de "${d##*/}") || continue      # un proceso que desaparece entre el listado y la lectura no cuenta
    case "$c" in *clientes_lab.py*) echo "${d##*/}" ;; esac
  done
  return 0
}

# Lee target, unidades y procesos. Deja ESTADO_LINEA y ESTADO_OK (1 si todo se leyó). No decide nada.
leer_todo() {
  local p perfil ip u det=""
  ESTADO_OK=1; Q_ERR=""; ERRORES=""
  if leer_target; then det="target=$T_AS carga=$T_LS habilitado=${T_UF:-?}"; else ESTADO_OK=0; ERRORES+="$Q_ERR; "; det="target=ERROR"; fi
  local h; h=$(hash_gen) || { h=ERROR; ESTADO_OK=0; ERRORES+="hash del generador ilegible; "; }
  PIDS_GEN=$(procesos_gen) || { ESTADO_OK=0; ERRORES+="no se pudo listar $PROC; "; PIDS_GEN=""; }
  local n; n=$(grep -c . <<<"$PIDS_GEN")
  [ "$ESTADO_OK" = 1 ] || n=ERROR
  det+=" hash=${h:0:8} procesos=$n unidades:"
  for p in $PERFILES; do
    perfil=${p%%:*}; ip=${p#*:}; u="cyberflow-lab-$perfil.service"
    if leer_unidad "$u"; then det+=" $perfil=$U_AS/$U_SS/pid$U_PID/nr$U_NR"
    else det+=" $perfil=ERROR"; ESTADO_OK=0; ERRORES+="$Q_ERR; "; fi
  done
  ESTADO_LINEA="gen $det consulta=$([ "$ESTADO_OK" = 1 ] && echo ok || echo ERROR)"
}

estado() {
  leer_todo
  echo "$ESTADO_LINEA"
  [ "$ESTADO_OK" = 1 ] && return $RC_OK
  echo "ESTADO_DESCONOCIDO: ${ERRORES%; }" >&2
  return $RC_DESCONOCIDO
}

configuracion() {  # rc 0 si las seis unidades corresponden a la configuración esperada; 4 si no; 5 si no se pudo leer
  local p perfil ip u malo=0 m
  for p in $PERFILES; do
    perfil=${p%%:*}; ip=${p#*:}; u="cyberflow-lab-$perfil.service"; m=0
    if ! leer_unidad "$u"; then echo "CONSULTA_FALLIDA $Q_ERR"; return $RC_DESCONOCIDO; fi
    [ "$U_LS" = loaded ] || { echo "NO_CORRESPONDE $u LoadState=$U_LS"; malo=1; continue; }
    case " $U_PARTOF " in *" $TARGET "*) ;; *) echo "NO_CORRESPONDE $u sin PartOf=$TARGET: el stop del target no la pararía"; m=1;; esac
    case "$U_EXEC " in *"$GEN --perfil $perfil --origen $ip "*|*"$GEN --perfil $perfil --origen $ip;"*) ;;
      *) echo "NO_CORRESPONDE $u ExecStart no es «$GEN --perfil $perfil --origen $ip»: ${U_EXEC:0:200}"; m=1;; esac
    [ $m = 0 ] && echo "OK $u $perfil $ip" || malo=1
  done
  [ $malo = 0 ] && return $RC_OK || return $RC_NO_CONFIRMADO
}

# Arranque confirmado: target active; cada unidad active/running con MainPID cuyo argv es el del perfil y su IP;
# los procesos clientes_lab.py son exactamente esos seis MainPID; y siguen iguales (PID y NRestarts) ESTABLE s después.
comprobar_arrancado() {  # rc 0 / 4 / 5 ; deja DETALLE
  local p perfil ip u c pids="" nrs=""
  DETALLE=""
  leer_todo
  [ "$ESTADO_OK" = 1 ] || { DETALLE="consulta fallida: ${ERRORES%; }"; return $RC_DESCONOCIDO; }
  [ "$T_AS" = active ] || DETALLE+="target $T_AS; "
  for p in $PERFILES; do
    perfil=${p%%:*}; ip=${p#*:}; u="cyberflow-lab-$perfil.service"
    leer_unidad "$u" || { DETALLE="consulta fallida: $Q_ERR"; return $RC_DESCONOCIDO; }
    if [ "$U_AS" != active ] || [ "$U_SS" != running ] || [ "$U_PID" = 0 ]; then DETALLE+="$perfil $U_AS/$U_SS pid$U_PID; "; continue; fi
    c=$(cmdline_de "$U_PID") || { DETALLE+="$perfil pid$U_PID sin argv legible; "; continue; }
    case "$c" in *"$GEN --perfil $perfil --origen $ip "*) ;; *) DETALLE+="$perfil pid$U_PID argv inesperado: ${c:0:120}; "; continue;; esac
    pids+="$U_PID "; nrs+="$perfil:$U_NR "
  done
  local esperados vivos
  esperados=$(tr ' ' '\n' <<<"$pids" | grep . | sort -n | tr '\n' ' ')
  vivos=$(sort -n <<<"$PIDS_GEN" | grep . | tr '\n' ' ')
  [ "$esperados" = "$vivos" ] || DETALLE+="procesos clientes_lab.py [${vivos% }] distintos de los MainPID [${esperados% }]; "
  CONFIRMADOS="$esperados|$nrs"
  [ -z "$DETALLE" ] && return $RC_OK || return $RC_NO_CONFIRMADO
}

# Parada confirmada: target inactive; cada unidad inactive (o failed) con MainPID 0; ningún proceso clientes_lab.py.
comprobar_parado() {  # rc 0 / 4 / 5 ; deja DETALLE
  local p perfil u
  DETALLE=""
  leer_todo
  [ "$ESTADO_OK" = 1 ] || { DETALLE="consulta fallida: ${ERRORES%; }"; return $RC_DESCONOCIDO; }
  [ "$T_AS" = inactive ] || DETALLE+="target $T_AS; "
  for p in $PERFILES; do
    perfil=${p%%:*}; u="cyberflow-lab-$perfil.service"
    leer_unidad "$u" || { DETALLE="consulta fallida: $Q_ERR"; return $RC_DESCONOCIDO; }
    case "$U_AS" in inactive|failed) ;; *) DETALLE+="$perfil $U_AS; ";; esac
    [ "$U_PID" = 0 ] || DETALLE+="$perfil MainPID $U_PID; "
  done
  [ -z "$PIDS_GEN" ] || DETALLE+="procesos clientes_lab.py vivos: $(tr '\n' ' ' <<<"$PIDS_GEN"); "
  [ -z "$DETALLE" ] && return $RC_OK || return $RC_NO_CONFIRMADO
}

esperar() {  # esperar FUNCION -> repite hasta rc 0 o ESPERA_MAX; devuelve el último rc
  local f=$1 t0 rc
  t0=$(date +%s)
  while :; do
    "$f"; rc=$?
    [ $rc = 0 ] && return 0
    [ $(( $(date +%s) - t0 )) -ge "$ESPERA_MAX" ] && return $rc
    sleep "$ESPERA"
  done
}

arrancar() {
  local h rc
  h=$(hash_gen) || { echo "ABORTA: no se puede leer el generador $GEN"; return $RC_USO; }
  [ "$h" = "$HASH_ESPERADO" ] || { echo "ABORTA: sha256 del generador $h distinto del esperado $HASH_ESPERADO"; return $RC_USO; }
  configuracion; rc=$?
  [ $rc = 0 ] || { echo "ABORTA: configuración de unidades no verificada (rc $rc)"; return $RC_USO; }
  comprobar_parado; rc=$?
  [ $rc = 0 ] || { echo "ABORTA: no se arranca desde un estado que no es «parado confirmado» (rc $rc): $DETALLE"; return $RC_USO; }
  echo "$(date -u +%FT%TZ) ARRANQUE solicitado: sudo -n systemctl start $TARGET"
  local o; o=$(sudo -n systemctl start "$TARGET" 2>&1); rc=$?
  echo "start rc=$rc ${o:0:300}"
  if [ $rc != 0 ]; then
    leer_todo; echo "$ESTADO_LINEA"
    echo "ARRANQUE_FALLIDO: systemctl start rc=$rc (ejecutar «parar» antes de cualquier otra cosa)"; return $RC_OPERACION
  fi
  esperar comprobar_arrancado; rc=$?
  if [ $rc != 0 ]; then
    echo "$ESTADO_LINEA"
    [ $rc = $RC_DESCONOCIDO ] && echo "ARRANQUE_NO_CONFIRMADO (estado desconocido): $DETALLE" \
                              || echo "ARRANQUE_PARCIAL: $DETALLE (ejecutar «parar»)"
    return $rc
  fi
  local primeros=$CONFIRMADOS
  sleep "$ESTABLE"
  comprobar_arrancado; rc=$?
  echo "$ESTADO_LINEA"
  if [ $rc != 0 ] || [ "$CONFIRMADOS" != "$primeros" ]; then
    [ $rc = $RC_DESCONOCIDO ] && { echo "ARRANQUE_NO_CONFIRMADO (estado desconocido tras ${ESTABLE} s): $DETALLE"; return $RC_DESCONOCIDO; }
    echo "ARRANQUE_INESTABLE: PID o NRestarts cambiaron en ${ESTABLE} s (${primeros} -> ${CONFIRMADOS}) $DETALLE (ejecutar «parar»)"
    return $RC_NO_CONFIRMADO
  fi
  echo "ARRANQUE_CONFIRMADO: target active, 6 unidades running con su perfil e IP, procesos = MainPID (${CONFIRMADOS%%|*})"
  return $RC_OK
}

parar() {
  local o rc rcs
  echo "$(date -u +%FT%TZ) PARADA solicitada: sudo -n systemctl stop $TARGET"
  o=$(sudo -n systemctl stop "$TARGET" 2>&1); rcs=$?
  echo "stop rc=$rcs ${o:0:300}"
  esperar comprobar_parado; rc=$?
  echo "$ESTADO_LINEA"
  if [ $rcs != 0 ]; then
    echo "PARADA_FALLIDA: systemctl stop rc=$rcs; confirmado=$([ $rc = 0 ] && echo si || echo no) $DETALLE"; return $RC_OPERACION
  fi
  case $rc in
    0) echo "PARADA_CONFIRMADA: target inactivo, 6 unidades inactivas con MainPID 0 y 0 procesos clientes_lab.py"; return $RC_OK ;;
    5) echo "PARADA_NO_CONFIRMADA (estado desconocido): $DETALLE"; return $RC_DESCONOCIDO ;;
    *) echo "PARADA_NO_CONFIRMADA: $DETALLE"; return $RC_NO_CONFIRMADO ;;
  esac
}

case "${1:-}" in
  estado) estado ;;
  permisos)
    sudo -n -l 2>&1 | grep -E "systemctl (start|stop) $TARGET|ALL" || echo "sin permiso sudo -n visible para el target"
    h=$(hash_gen) || h=ERROR
    echo "zona=$(cat /etc/timezone 2>/dev/null || timedatectl show -p Timezone --value) ahora_utc=$(date -u +%FT%TZ) hash_generador=$h esperado=$([ "$h" = "$HASH_ESPERADO" ] && echo si || echo NO)"
    estado ;;
  configuracion) configuracion ;;
  arrancar) arrancar ;;
  parar) parar ;;
  comprobar-parado) comprobar_parado; rc=$?; echo "$ESTADO_LINEA"
    case $rc in 0) echo "PARADO_CONFIRMADO";; 5) echo "ESTADO_DESCONOCIDO: $DETALLE";; *) echo "NO_PARADO: $DETALLE";; esac; exit $rc ;;
  *) echo "uso: generadores.sh estado|permisos|configuracion|arrancar|parar|comprobar-parado (VERSION $VERSION)"; exit $RC_USO ;;
esac
