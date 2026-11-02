#!/usr/bin/env bash
# Ensayo de banco (Etapa 4): estadísticas de tcpdump sin parar la captura. SOLO en el banco Docker.
#
#   docker run --rm --privileged --network none \
#     -v "<repo>:/src:ro" -v "<salida>:/out" cyberflow-etapa3-banco:1 \
#     bash /src/deploy/etapa4/banco/ensayo_tcpdump_estadisticas.sh
#
# Comprueba, sobre una veth dentro del contenedor (sin red del laboratorio):
#   E1  anillo -G con -Z (como ppi-motor-capture): SIGUSR1 imprime "captured / received by filter /
#       dropped by kernel" en stderr, la captura sigue rotando y las cifras son acumuladas (no decrecen).
#   E2  tubería (como ppi-via-rapida@): tcpdump -w - | detector_rapido.py --flujo; SIGUSR1 al tcpdump
#       no corta la tubería y el resumen del detector sigue avanzando.
#   E3  descartes forzados: búfer mínimo y lector lento; "dropped by kernel" > 0 y crece; se anota si
#       "captured" incluye o no los descartados (semántica de libpcap/TPACKET_V3 en esta versión).
#   E4  acumulación en la tubería por /proc/<pid>/io (salud_captura.py muestrear --pid), solo si el
#       kernel del banco expone /proc/<pid>/io; si no, se declara no ejecutable (no se da por buena).
#   E5  cola de la tubería por recuento: capturados (SIGUSR1) − paquetes_tcp del detector; 0 tras drenar.
# No cambia nada fuera del contenedor. Salida: /out/ensayo-tcpdump-estadisticas.txt y ficheros auxiliares.
set -u
OUT=/out
SRC=/src
LOG="$OUT/ensayo-tcpdump-estadisticas.txt"
mkdir -p "$OUT"
: > "$LOG"
for f in "$OUT"/e[0-9]-*; do [ -e "$f" ] && : > "$f"; done   # vacía la salida de una corrida anterior
say() { printf '%s %s\n' "$(date -u +%FT%T.%3NZ)" "$*" | tee -a "$LOG"; }
fallo=0
comprobar() { if eval "$2"; then say "OK   $1"; else say "FALLO $1"; fallo=1; fi; }

[ "$(id -u)" = 0 ] || { echo "solo como root en el banco"; exit 2; }
[ -f /.dockerenv ] || { echo "solo dentro del contenedor del banco"; exit 2; }

say "versiones: $(tcpdump --version 2>&1 | tr '\n' ' ')"
say "kernel: $(uname -r)"
# vA en un netns propio (generador) y vB en el principal (captura): si las dos direcciones
# estuvieran en el mismo netns el kernel entregaría por lo y la veth no vería nada.
ip netns add gen
ip link add vA type veth peer name vB
ip link set vA netns gen
ip netns exec gen ip addr add 192.0.2.1/24 dev vA
ip netns exec gen ip link set vA up
ip netns exec gen ip link set lo up
ip addr add 192.0.2.2/24 dev vB
ip link set vB up
ip link set vB promisc on

# Generador: SYN TCP de 192.0.2.1 a 192.0.2.2 (puertos variables) a ritmo fijo, por la veth.
generador() {   # $1 = paquetes por segundo, $2 = segundos
  ip netns exec gen python3 - "$1" "$2" <<'EOF'
import socket, sys, time
pps, dur = float(sys.argv[1]), float(sys.argv[2])
fin = time.time() + dur
n = 0
while time.time() < fin:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(False)
    try:
        s.connect_ex(("192.0.2.2", 1000 + n % 50000))
    finally:
        s.close()
    n += 1
    time.sleep(max(0.0, 1.0 / pps))
print(n)
EOF
}

# ---------------------------------------------------------------- E1 anillo con -Z
id tcpdump >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin tcpdump
ANI=/tmp/anillo; install -d -o tcpdump -g root -m 2750 "$ANI"
tcpdump -i vB -n -s 0 -U -B 65536 -Z tcpdump -w "$ANI/live-%Y%m%d%H%M%S.pcap" -G 2 2> "$OUT/e1-stderr.txt" &
TD=$!
sleep 1
generador 300 12 > /dev/null &
GEN=$!
for i in 1 2 3; do
  sleep 3
  kill -USR1 "$TD"
  say "E1 SIGUSR1 #$i enviado (ficheros en el anillo: $(ls "$ANI" | wc -l))"
done
wait "$GEN"
sleep 3
n_antes=$(ls "$ANI" | wc -l)
kill -USR1 "$TD"; sleep 1
comprobar "E1 tcpdump sigue vivo tras 4 SIGUSR1" "kill -0 $TD"
sleep 3
n_despues=$(ls "$ANI" | wc -l)
say "E1 ficheros antes/después de la última señal: $n_antes / $n_despues"
kill -INT "$TD"; wait "$TD" 2>/dev/null
grep -E 'packets? captured' "$OUT/e1-stderr.txt" | tee -a "$LOG" > "$OUT/e1-estadisticas.txt"
comprobar "E1 hay 4 líneas de SIGUSR1 + 1 final" "[ \$(grep -c 'dropped by kernel' $OUT/e1-stderr.txt) -ge 5 ]"
comprobar "E1 'captured' no decrece entre lecturas" \
  "awk '/captured,/{c=\$1+0; if (c<p) exit 1; p=c}' $OUT/e1-stderr.txt"
comprobar "E1 la rotación continúa (hay más de 6 ficheros de 2 s)" "[ $n_despues -ge 6 ]"
comprobar "E1 los ficheros del anillo siguen siendo de tcpdump (setuid aplicado)" \
  "[ \"\$(stat -c %U \"\$(ls -d $ANI/* | head -1)\")\" = tcpdump ]"

# ---------------------------------------------------------------- E2 tubería con el detector
VR=/tmp/vr; mkdir -p "$VR"
cd "$SRC" || exit 2
( set -o pipefail
  tcpdump -i vB -n -U --immediate-mode -s 128 -w - "tcp or (vlan and tcp)" 2> "$OUT/e2-stderr.txt" \
  | python3 scripts/engine/detector_rapido.py --flujo --salida "$VR/senales.jsonl" --resumen "$VR/resumen.jsonl" ) &
TUB=$!
sleep 2
TD2=$(pgrep -n -x tcpdump)
PY2=$(pgrep -n -f detector_rapido.py)
say "E2 tcpdump PID $TD2, detector PID $PY2"
generador 200 8 > /dev/null &
GEN=$!
sleep 3
p1=$(tail -1 "$VR/resumen.jsonl" | python3 -c 'import json,sys; print(json.load(sys.stdin)["paquetes_tcp"])')
kill -USR1 "$TD2"
sleep 3
p2=$(tail -1 "$VR/resumen.jsonl" | python3 -c 'import json,sys; print(json.load(sys.stdin)["paquetes_tcp"])')
wait "$GEN"
say "E2 paquetes_tcp del detector antes/después de SIGUSR1: $p1 / $p2"
comprobar "E2 la tubería sigue viva tras SIGUSR1" "kill -0 $TD2 && kill -0 $PY2"
comprobar "E2 el resumen sigue avanzando" "[ $p2 -gt $p1 ]"
comprobar "E2 la estadística sale por stderr de tcpdump" "grep -q 'dropped by kernel' $OUT/e2-stderr.txt"
grep -E 'captured' "$OUT/e2-stderr.txt" | tee -a "$LOG" >/dev/null

# ---------------------------------------------------------------- E5 cola de la tubería por recuento
# capturados (SIGUSR1 de tcpdump) − paquetes_tcp (resumen del detector): lo escrito y aún no leído.
# Con tráfico puede ser > 0 (en vuelo); tras drenar debe ser 0 (el detector leyó todo lo capturado).
ultimo_capturado() { awk '/captured,/{c=$2} END{print c+0}' "$OUT/e2-stderr.txt"; }
ultimo_detector() { tail -1 "$VR/resumen.jsonl" | python3 -c 'import json,sys; print(json.load(sys.stdin)["paquetes_tcp"])'; }
generador 400 4 > /dev/null &
GEN=$!
sleep 2
kill -USR1 "$TD2"; d_det=$(ultimo_detector); sleep 0.3; c_mid=$(ultimo_capturado)
wait "$GEN"; sleep 3
kill -USR1 "$TD2"; sleep 0.5; c_fin=$(ultimo_capturado); d_fin=$(ultimo_detector)
say "E5 con tráfico: capturados=$c_mid detector≈$d_det; tras drenar: capturados=$c_fin detector=$d_fin"
comprobar "E5 tras drenar, capturados (tcpdump) = paquetes_tcp (detector)" "[ $c_fin -eq $d_fin ]"

# ---------------------------------------------------------------- E4 /proc/<pid>/io (si el kernel lo da)
if [ -r /proc/self/io ]; then
  python3 "$SRC/scripts/etapa4/salud_captura.py" muestrear --salida "$OUT/e4-rapido.jsonl" \
    --pid "$TD2" --pid "$PY2" --resumen-rapida "$VR/resumen.jsonl" --intervalo 1 --hasta "$(( $(date +%s) + 4 ))" &
  MU=$!
  generador 200 5 > /dev/null
  wait "$MU"      # solo el muestreador: la tubería sigue viva hasta el kill
  python3 "$SRC/scripts/etapa4/salud_captura.py" intervalos "$OUT/e4-rapido.jsonl" "$OUT/e4-rapido-inc.jsonl" | tee -a "$LOG"
else
  say "E4 NO EJECUTABLE en este banco: el kernel $(uname -r) no expone /proc/<pid>/io; el método se verifica por lectura en Sensor1"
fi
kill -INT "$TD2"; wait "$TUB" 2>/dev/null

# ---------------------------------------------------------------- E3 descartes con lector lento
( tcpdump -i vB -n -U --immediate-mode -B 1 -s 0 -w - 2> "$OUT/e3-stderr.txt" \
  | python3 -c 'import sys,time
while True:
    b = sys.stdin.buffer.read(256)
    if not b: break
    time.sleep(0.05)' ) &
LENTO=$!
sleep 2
TD3=$(pgrep -n -x tcpdump)
# ráfaga con cuerpo para llenar el búfer: datagramas UDP de 1 KB
ip netns exec gen python3 - <<'EOF'
import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
fin = time.time() + 6
while time.time() < fin:
    for _ in range(200):
        s.sendto(b"x" * 1000, ("192.0.2.2", 9))
    time.sleep(0.01)
EOF
kill -USR1 "$TD3"; sleep 1
generador 50 1 > /dev/null
kill -USR1 "$TD3"; sleep 1
kill -INT "$TD3" 2>/dev/null; kill "$LENTO" 2>/dev/null; wait "$LENTO" 2>/dev/null
grep -E 'captured' "$OUT/e3-stderr.txt" | tee -a "$LOG" >/dev/null
# formato: "tcpdump: C packets captured, R packets received by filter, D packets dropped by kernel"
comprobar "E3 hay descartes del kernel con búfer mínimo y lector lento" \
  "awk '/captured,.*dropped by kernel/{d=\$(NF-4)+0} END{exit !(d>0)}' $OUT/e3-stderr.txt"
comprobar "E3 los descartes no decrecen entre lecturas" \
  "awk '/captured,.*dropped by kernel/{d=\$(NF-4)+0; if (d<p) exit 1; p=d}' $OUT/e3-stderr.txt"
comprobar "E3 recibidos por el filtro = capturados + descartados (última lectura)" \
  "awk '/captured,.*dropped by kernel/{c=\$2;r=\$5;d=\$(NF-4)} END{exit !(r==c+d)}' $OUT/e3-stderr.txt"
awk '/captured,/{print "E3 última lectura: " $0}' "$OUT/e3-stderr.txt" | tail -1 | tee -a "$LOG"

say "RESULTADO: $([ $fallo = 0 ] && echo 'todas las comprobaciones OK' || echo 'HAY FALLOS')"
exit $fallo
