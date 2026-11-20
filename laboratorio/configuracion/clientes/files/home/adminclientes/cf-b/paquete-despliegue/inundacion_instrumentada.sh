#!/bin/bash
# VARIANTE INSTRUMENTADA del comando de la inundación HTTP (E3). Mismas condiciones que el original de `escenarios-4c.json`:
#   fin=$((SECONDS+90)); n=8; N bucles en paralelo; cada iteración = un `curl -s -o /dev/null --max-time 2 URL`; al final imprime `intentos=N`.
# Añade UN registro por iteración, con hora y resultado, para distinguir los INTENTOS del generador de las peticiones que el servidor ACEPTÓ:
#   t_inicio  t_fin  codigo_http  t_conexion_s  rc_curl  lazo
#   - intento aceptado por el servidor: codigo_http != 000 (el servidor respondió);
#   - intento sin respuesta: codigo_http = 000 (rc_curl 28 = tiempo agotado, 7 = conexión rechazada).
# Uso: inundacion_instrumentada.sh <salida.tsv> [url] [segundos] [n_paralelo]      (CF_MAXTIME cambia --max-time, solo para pruebas)
# El registro es temporal y local: se escribe en un fichero por lazo y se fusiona al final. No cambia el tráfico: sólo añade 2 `date` por iteración.
set -u
export LC_ALL=C
SALIDA="${1:?uso: $0 <salida.tsv> [url] [segundos] [n]}"
URL="${2:-http://10.10.30.10/}"
DUR="${3:-90}"
N="${4:-8}"
MAXT="${CF_MAXTIME:-2}"
fin=$((SECONDS+DUR))
d=$(mktemp -d)
for i in $(seq "$N"); do
  (
    c=0
    : > "$d/$i.tsv"
    while [ "$SECONDS" -lt "$fin" ]; do
      t0=$(date +%s.%N)
      r=$(curl -s -o /dev/null -w '%{http_code} %{time_connect}' --max-time "$MAXT" "$URL")
      rc=$?
      t1=$(date +%s.%N)
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$t0" "$t1" "${r%% *}" "${r##* }" "$rc" "$i" >> "$d/$i.tsv"
      c=$((c+1))
    done
    echo "$c" > "$d/$i.n"
  ) &
done
wait
{ printf '# t_inicio\tt_fin\tcodigo_http\tt_conexion_s\trc_curl\tlazo\n'; sort -n "$d"/*.tsv; } > "$SALIDA"
echo "intentos=$(cat "$d"/*.n | awk '{s+=$1} END{print s+0}')"
rm -rf "$d"
