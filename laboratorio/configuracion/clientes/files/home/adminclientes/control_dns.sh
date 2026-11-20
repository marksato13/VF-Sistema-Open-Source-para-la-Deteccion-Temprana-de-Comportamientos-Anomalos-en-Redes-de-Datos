#!/usr/bin/env bash
# [CLIENTES adminclientes] sin sudo. Control DNS legítimo de la prueba complementaria DNS (13-nov-2026): una consulta
# por segundo desde 10.10.20.20 (IP del puesto, sin perfil de carga) a DC1 por un nombre real del dominio, y registra
# hora UTC, rcode, respuesta y tiempo. No toca a los 6 perfiles clientes_lab.py (siguen con sus propios registros).
# Uso: setsid nohup bash control_dns.sh SALIDA.tsv &
O=${1:?salida}
printf 't_epoch\tstatus\trespuesta\tqtime_ms\n' >> "$O"
while true; do
  t=$(date +%s.%N)
  r=$(dig +time=2 +tries=1 -b 10.10.20.20 @10.10.10.20 vm-ad-dc.ad.francos-sac.com A 2>&1)
  st=$(sed -n 's/.*status: \([A-Z]*\),.*/\1/p' <<<"$r" | head -1); [ -z "$st" ] && st=SIN_RESPUESTA
  ans=$(awk '/ANSWER SECTION/{f=1;next} f&&NF{print $NF; exit}' <<<"$r")
  qt=$(sed -n 's/;; Query time: \([0-9]*\) msec/\1/p' <<<"$r")
  printf '%s\t%s\t%s\t%s\n' "$t" "$st" "${ans:--}" "${qt:--}" >> "$O"
  sleep 1
done
