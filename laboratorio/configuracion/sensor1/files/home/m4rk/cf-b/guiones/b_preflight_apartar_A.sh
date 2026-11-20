#!/bin/bash
# Campaña B - preflight: aparta (renombra, no borra ni copia) los restos de la corrida de A para que B parta limpia.
# Uso: b_preflight_apartar_A.sh sensor|kali   (CF_MODO=seco por omisión; CF_MODO=real mueve)
#  sensor [m4rk, Sensor1]: ~/cf-e4/4c -> ~/cf-e4/4c-A-completa-<ts>  (g01b y cf-4b-rotacion usan ~/cf-e4/4c como fase única de B)
#  kali [adminatacante]:   ~/cf-e4-4c/{corrida,comando.txt,lanzado.txt,terminado.txt,generador.*,permiso.json}
#                          -> ~/cf-e4-4c-A-completa-<ts>/ ; se CONSERVA sha256-esperado.txt (y su copia .antes-B)
# Se niega si hay un generador en marcha o si el destino ya existe. rc 0 bien; 2 se negó/uso; 3 falló el movimiento.
set -u
DONDE="${1:?sensor|kali}"; MODO="${CF_MODO:-seco}"; TS="${CF_TS:-$(date -u +%Y%m%dT%H%MZ)}"
case "$MODO" in seco|real) ;; *) echo "CF_MODO debe ser seco o real"; exit 2;; esac
mueve() { if [ "$MODO" = real ]; then mv "$1" "$2" || { echo "FALLO mv $1"; exit 3; }; echo "  movido $1 -> $2"; else echo "  SECO: mv $1 -> $2"; fi; }
[ "$(pgrep -fc '[g]enerar_campana')" = 0 ] || { echo "PARAR: hay un generador en marcha"; exit 2; }
echo "== apartar restos de A en $DONDE, modo=$MODO"
case "$DONDE" in
  sensor)
    O="${CF_FASE_DIR:-$HOME/cf-e4/4c}"; D="${CF_FASE_APARTADA:-$HOME/cf-e4/4c-A-completa-$TS}"
    [ -d "$O" ] || { echo "  no hay $O: nada que apartar"; exit 0; }
    [ -e "$D" ] && { echo "PARAR: ya existe $D"; exit 2; }
    [ -e "$O/cierre.t" ] && [ -e "$O/replay/rc.txt" ] || echo "  AVISO: $O no parece una corrida cerrada (falta cierre.t o replay/rc.txt)"
    mueve "$O" "$D";;
  kali)
    K="${CF_K:-$HOME/cf-e4-4c}"; D="${CF_KALI_APARTADA:-$HOME/cf-e4-4c-A-completa-$TS}"
    [ -d "$K" ] || { echo "PARAR: no existe $K"; exit 2; }
    [ -e "$D" ] && { echo "PARAR: ya existe $D"; exit 2; }
    [ -f "$K/sha256-esperado.txt" ] || { echo "PARAR: falta sha256-esperado.txt"; exit 2; }
    [ "$MODO" = real ] && mkdir -p "$D"
    for f in corrida comando.txt lanzado.txt terminado.txt generador.rc generador.stdout generador.stderr permiso.json permiso.json.tmp; do
      [ -e "$K/$f" ] && mueve "$K/$f" "$D/$f"
    done
    echo "  se conserva: $(ls "$K" | tr '\n' ' ')";;
  *) echo "uso: sensor|kali"; exit 2;;
esac
echo "== fin modo=$MODO rc=0"
