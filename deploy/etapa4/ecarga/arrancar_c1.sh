#!/usr/bin/env bash
# [BASTIÓN gadmin] Paso C1 de E-carga v2: autoriza y emite la orden de arranque. VERSION 2026-11-07.2.
# SOLO con la orden de Mark. Sustituye al bloque manual de C1, que podía arrancar con una parada ya confirmada.
#
#   arrancar_c1.sh X T_G
# X es la carpeta del ensayo (X/bastion con el muestreador, X/manual para la evidencia). Espera hasta T_G y entonces:
#   1. toma el cerrojo X/bastion/ordenes.lock sin esperar: si está ocupado, hay una parada en curso y no arranca;
#   2. dentro del cerrojo, puerta_c1.py decide. Si no autoriza, NO se emite ninguna orden (rc 2, motivo en c1-puerta.jsonl);
#      después relee la hora: si ya superó T_G, tampoco se emite (rc 2). Sin tolerancia;
#   3. emite `generadores.sh arrancar`, con tiempo máximo, sin soltar el cerrojo;
#   4. al volver, relee: arrancar con rc distinto de 0, una solicitud de parada o el muestreador muerto obligan a parar
#      aquí mismo y a dejar PARADA-SOLICITADA, que el muestreador también atiende.
#
# Por qué no quedan generadores vivos, sea cual sea el orden. muestreo_bastion.sh escribe PARADA-SOLICITADA ANTES de pedir
# el cerrojo y arrancar_c1.sh lee la solicitud DENTRO de él:
#   - solicitud antes de la puerta: no se arranca;
#   - solicitud después: su `parar` espera al final de `arrancar`, y este guion la ve al volver.
# Si el ssh se corta y el arranque remoto termina tarde, muestreo_bastion.sh lo ve en la siguiente lectura de `estado`,
# reabre la parada y la repite. Esa vigilancia dura hasta FIN.
#
# Evidencia en X/manual: c1-puerta.jsonl (decisiones), arranque.txt, arranque.rc, RESULTADO-C1 (una línea JSON).
# rc: 0 arranque confirmado, sin solicitud de parada · 2 no autorizado: ninguna orden emitida ·
#     3 arranque abortado y parada confirmada · 4 parada NO confirmada: INTERVENCIÓN NECESARIA
set -u
set -o pipefail
VERSION=2026-11-07.2
X=${1:?X}; T_G=${2:?T_G}
[[ $T_G =~ ^[0-9]+$ ]] || { echo "ABORTA: T_G no es un epoch"; exit 2; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
O=$X/bastion; M=$X/manual
[ -d "$O" ] && [ -d "$M" ] || { echo "ABORTA: faltan $O o $M"; exit 2; }
[ ! -e "$M/arranque.rc" ] || { echo "ABORTA: ya existe $M/arranque.rc; C1 no se repite"; exit 2; }
SSH=${CF_SSH:-ssh}
K=${CF_LLAVES:-$HOME/.ssh}
T_ARRANQUE=${CF_T_ARRANQUE:-90}      # s máximos de la orden de arranque (generadores.sh confirma en hasta 25 s)
T_PARADA=${CF_T_PARADA:-90}
INTENTOS_PARADA=${CF_C1_INTENTOS:-3}
CLI="$SSH -o BatchMode=yes -o ConnectTimeout=10 -i $K/cyberflow-to-clientes adminclientes@10.10.20.20"

resultado() {  # resultado RESULTADO RC MOTIVO
  local m=${3//\\/\/}
  printf '{"version": "%s", "resultado": "%s", "rc": %s, "motivo": "%s", "t": %s}\n' \
    "$VERSION" "$1" "$2" "${m//\"/\'}" "$(date +%s)" > "$M/RESULTADO-C1"
  cat "$M/RESULTADO-C1"
}
denegar() {  # denegar MOTIVO: ninguna orden se ha emitido
  echo "NO AUTORIZADO, ninguna orden emitida: $1" | tee "$M/arranque.rc"
  resultado NO_AUTORIZADO 2 "$1"
  exit 2
}
puerta() {  # devuelve 0 solo si puerta_c1.py autoriza; un fallo de la propia puerta no autoriza
  local s r
  s=$(python3 -I -B "$AQUI/puerta_c1.py" "$O" "$(date +%s)" 2>&1); r=$?
  printf '%s\n' "$s" >> "$M/c1-puerta.jsonl"
  PUERTA=$s
  return $r
}
motivos_puerta() {
  python3 -I -B -c 'import json,sys;print("; ".join(json.loads(sys.argv[1])["motivos"])[:600])' "$PUERTA" 2>/dev/null \
    || printf 'la puerta no dio una respuesta válida'
}

[ "$(date +%s)" -lt "$T_G" ] || denegar "T_g ya pasó al llegar a C1"
while [ "$(date +%s)" -lt "$T_G" ] && [ ! -e "$O/PARADA-SOLICITADA" ]; do sleep 0.2; done

exec 9>>"$O/ordenes.lock" || denegar "no se puede abrir el cerrojo"
flock -n 9 || denegar "cerrojo ocupado: hay una parada en curso"
puerta || denegar "$(motivos_puerta)"
ahora=$(date +%s)
[ "$ahora" -le "$T_G" ] || denegar "T_g ya pasó antes de emitir la orden (ahora=$ahora, T_G=$T_G)"

date -u +%FT%T.%NZ | tee -a "$M/arranque.txt"
timeout "$T_ARRANQUE" $CLI 'bash -s arrancar' < "$AQUI/generadores.sh" 2>&1 9>&- | tee -a "$M/arranque.txt"
rc=${PIPESTATUS[0]}
echo "arrancar rc=$rc" | tee "$M/arranque.rc"

motivo=""
[ "$rc" = 0 ] || motivo="arrancar rc=$rc"
if [ -e "$O/PARADA-SOLICITADA" ]; then motivo="${motivo:+$motivo; }solicitud de parada durante el arranque"; fi
if ! python3 -I -B "$AQUI/puerta_c1.py" "$O" "$(date +%s)" --solo-muestreador > /dev/null 2>&1; then
  motivo="${motivo:+$motivo; }muestreador no vivo tras el arranque"
fi
if [ -z "$motivo" ]; then
  resultado ARRANCADO 0 ""
  exit 0
fi

echo "$(date +%s) arrancar_c1: $motivo" >> "$O/PARADA-SOLICITADA"
n=0; hecho=0
while [ $n -lt "$INTENTOS_PARADA" ] && [ $hecho = 0 ]; do
  n=$((n + 1))
  timeout "$T_PARADA" $CLI 'bash -s parar' < "$AQUI/generadores.sh" 2>&1 9>&- | tee -a "$M/arranque.txt"
  r=${PIPESTATUS[0]}
  echo "parar intento $n rc=$r" | tee -a "$M/arranque.rc"
  if [ "$r" = 0 ]; then hecho=1
  elif [ "$r" = 3 ]; then
    timeout "$T_PARADA" $CLI 'bash -s comprobar-parado' < "$AQUI/generadores.sh" 2>&1 9>&- | tee -a "$M/arranque.txt"
    r2=${PIPESTATUS[0]}
    echo "comprobar-parado intento $n rc=$r2" | tee -a "$M/arranque.rc"
    [ "$r2" != 0 ] || hecho=1
  fi
  [ $hecho = 1 ] || [ $n -ge "$INTENTOS_PARADA" ] || sleep 2
done
if [ $hecho = 1 ]; then
  echo "E-carga ABORTADA en el arranque: no hay ventana que evaluar ($motivo)" | tee -a "$M/arranque.rc"
  resultado ABORTADO_PARADO 3 "$motivo"
  exit 3
fi
echo "$(date -u +%FT%TZ) parada no confirmada tras $n intentos de C1 ($motivo)" > "$O/C1-PARADA-NO-CONFIRMADA"
echo "INTERVENCIÓN NECESARIA: parada NO confirmada ($motivo)" | tee -a "$M/arranque.rc"
resultado ABORTADO_SIN_CONFIRMAR 4 "$motivo"
exit 4
