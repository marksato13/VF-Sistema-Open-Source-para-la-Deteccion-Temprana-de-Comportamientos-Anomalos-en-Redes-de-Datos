#!/usr/bin/env bash
# Instalación, aceptación y reversión de la INSTRUMENTACIÓN por host (propuesta; NO ejecutada en el laboratorio). SECO POR OMISIÓN; no genera tráfico y no arranca ningún proceso.
# Uso: cf_d5_instrumentacion.sh {kali|clientes|srvdmz} {instalar|aceptar|revertir} [--aplicar]
#   kali     (adminatacante) copia inundacion_instrumentada.sh; el cambio de `escenarios-4c.json` lo hace Mark con la config firmada de la corrida (aquí solo se muestra la línea)
#   clientes (adminclientes) copia clientes_factor1_tx.py; el arranque con --registro lo ordena Mark al iniciar la corrida
#   srvdmz   (adminsrvdmz)   copia muestreador_set.py; arranque/parada con `iniciar|parar` del propio guion (solo con --aplicar)
# Variables: CF_PAQUETE, CF_HOME (por omisión el HOME del usuario).
set -uo pipefail
HOST="${1:-}"; ACCION="${2:-}"; shift 2 2>/dev/null || true
APLICAR=0
for a in "$@"; do case "$a" in --aplicar) APLICAR=1;; *) echo "opción desconocida: $a" >&2; exit 2;; esac; done
CF_HOME="${CF_HOME:-$HOME}"; PQ="${CF_PAQUETE:-$CF_HOME/cf-b/paquete-despliegue}"; DEST="$CF_HOME/cf-b/instrumentacion"; RESP="$CF_HOME/cf-b/respaldo-d5"
run() { if [ "$APLICAR" = 1 ]; then "$@"; else echo "[seco] $*"; fi; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
ok=0; mal=0
c() { if [ "$2" = 0 ]; then echo "OK    $1"; ok=$((ok+1)); else echo "FALLA $1"; mal=$((mal+1)); fi; }
case "$HOST" in kali) ARTS="inundacion_instrumentada.sh";; clientes) ARTS="clientes_factor1_tx.py";; srvdmz) ARTS="muestreador_set.py";; *) echo "host: kali|clientes|srvdmz"; exit 2;; esac

instalar() {
  echo "== $HOST: instalar instrumentación (aplicar=$APLICAR)"
  ( cd "$PQ" && sha256sum -c SHA256SUMS --quiet ) || { echo "los artefactos NO coinciden con SHA256SUMS"; exit 3; }
  run mkdir -p "$DEST"
  for f in $ARTS; do run install -m 0755 "$PQ/$f" "$DEST/$f"; done
  case "$HOST" in
    kali) echo "Mark: en la config firmada de la corrida, el comando de la inundación pasa a: bash $DEST/inundacion_instrumentada.sh $CF_HOME/cf-e4-4c/intentos-<episodio>.tsv http://10.10.30.10/ 90 8  (misma duración, URL y nº de lazos que el original)";;
    clientes) echo "Mark: arrancar cada perfil con: python3 $DEST/clientes_factor1_tx.py --registro ~/cf-e4/4c/transacciones-<perfil>.tsv --perfil <p> --origen <ip> --servidor 10.10.30.10 --dns 10.10.10.20";;
    srvdmz) echo "iniciar: cf_d5_instrumentacion.sh srvdmz iniciar --aplicar   |   parar: cf_d5_instrumentacion.sh srvdmz parar --aplicar";;
  esac
}
aceptar() {
  echo "== $HOST: aceptación"
  ( cd "$PQ" && sha256sum -c SHA256SUMS --quiet ); c "artefactos = SHA256SUMS" $?
  for f in $ARTS; do [ "$(sha "$DEST/$f")" = "$(sha "$PQ/$f")" ]; c "instalado $f = paquete" $?; [ "$(stat -c %a "$DEST/$f")" = 755 ]; c "$f 0755" $?; done
  case "$HOST" in
    kali) bash -n "$DEST/inundacion_instrumentada.sh"; c "sintaxis de la inundación instrumentada" $?;;
    clientes) python3 -I -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$DEST/clientes_factor1_tx.py"; c "sintaxis del envoltorio de clientes" $?;;
    srvdmz) python3 -I "$DEST/muestreador_set.py" --help >/dev/null 2>&1; c "el muestreador arranca (--help)" $?;;
  esac
  echo "resumen: $ok OK, $mal FALLAN"; [ "$mal" = 0 ]
}
revertir() {
  echo "== $HOST: revertir instrumentación (aplicar=$APLICAR) — los registros temporales se archivan con hash, no se borran"
  TS=$(date -u +%Y%m%dT%H%M%SZ); run mkdir -p "$RESP"
  [ -d "$DEST" ] && run mv "$DEST" "$RESP/instrumentacion.retirada-$TS"
  echo "los ficheros intentos-*.tsv / transacciones-*.tsv / set-lecturas.jsonl se mueven a un directorio con sufijo y sha256 (no se borran)"
}
iniciar() { [ "$HOST" = srvdmz ] || exit 2; run bash -c "nohup python3 -I '$DEST/muestreador_set.py' --salida '$CF_HOME/cf-b/set-lecturas.jsonl' --intervalo 2 > /dev/null 2>&1 & echo \$! > '$CF_HOME/cf-b/muestreador.pid'"; }
parar() { [ "$HOST" = srvdmz ] || exit 2; [ -r "$CF_HOME/cf-b/muestreador.pid" ] && run kill "$(cat "$CF_HOME/cf-b/muestreador.pid")"; }
case "$ACCION" in instalar) instalar;; aceptar) aceptar;; revertir) revertir;; iniciar) iniciar;; parar) parar;; *) echo "uso: $0 {kali|clientes|srvdmz} {instalar|aceptar|revertir|iniciar|parar} [--aplicar]"; exit 2;; esac
