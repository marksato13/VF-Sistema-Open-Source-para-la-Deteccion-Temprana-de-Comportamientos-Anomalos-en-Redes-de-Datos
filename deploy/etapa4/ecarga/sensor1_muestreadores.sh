#!/usr/bin/env bash
# [SENSOR1 m4rk] Muestreadores de E-carga v2 en Sensor1 (solo lectura, sin sudo). VERSION 2026-11-06.4.
#   salud_captura.py muestrear (10 s)  ~/cyberflow-e4/herramientas-20261106 (VERSION 2026-11-06.1; idéntico al del paquete)
#   muestreo_fino.py (1 s), obs_pcap.py (cada PCAP cerrado), muestreo_s14.py (1 s, S14 r3)  del paquete en el que está
#   este guion: la ruta del paquete se deduce de la ubicación del guion (deploy/etapa4/ecarga/), sin nombres fijos.
#
#   sensor1_muestreadores.sh comprobar DIR FIN_EPOCH FIN_ISO   comprobaciones previas + obs_pcap --en-seco
#   sensor1_muestreadores.sh arrancar  DIR FIN_EPOCH FIN_ISO   lanza los cuatro y CONFIRMA que siguen vivos
#   sensor1_muestreadores.sh parar     DIR                     TERM a los PID de DIR/pids cuya cmdline coincide y confirma
#   sensor1_muestreadores.sh estado    DIR
# rc: 0 bien; 1 alguna comprobación FALLO; 2 uso o DIR ya usado; 3 algún muestreador no arrancó o no se paró.
set -u
set -o pipefail
ORDEN=${1:?orden}; O=${2:?DIR}
E="$(cd "$(dirname "$0")" && pwd)"; P="$(cd "$E/../../.." && pwd)"
H="$HOME/cyberflow-e4/herramientas-20261106"
PY="$HOME/cyberflow/.venv/bin/python"; ANILLO=/var/lib/ppi-motor-capture; EVE=/var/log/suricata/eve.json
EV_ESPERADO=53e9f7bd578123f6499289ebbb92d8d6c71a6e56b7c1c35a59463b98aad5c23f
RETENCION_MIN=900
ok() { echo "OK    $*"; }; no() { echo "FALLO $*"; fallo=1; }
fallo=0
# Muestreadores en marcha (2026-11-06.4). Se identifican por el PROGRAMA ejecutado y sus ARGUMENTOS (argv exacto de
# /proc/<pid>/cmdline, separado por NUL), nunca por texto que aparezca dentro de una orden: «pgrep -af» (hasta la .3)
# coincidía con el propio intérprete cuando este guion se ejecutaba como «bash -c "$txt"» (P0 r2, 06-nov 23:24Z).
# Un proceso es MUESTREADOR si y solo si:
#   - argv[0] es un intérprete python (nombre base python, python3, python3.12…);
#   - tras las opciones del intérprete (-I -B -u…; -X/-W con su valor; «-c» o «-m» => no ejecuta un guion), el primer
#     argumento es un guion cuyo nombre base es muestreo_fino.py, obs_pcap.py o muestreo_s14.py, o salud_captura.py
#     seguido de «muestrear» (los cuatro de «arrancar», de cualquier paquete o ruta).
#   Un bash, un grep, un editor o un «python -c» que lleven esos nombres como TEXTO no son muestreadores; no se excluye
#   ningún proceso por ser bash ni por ser antecesor de esta consulta.
# Estados (rc): 0 AUSENCIA confirmada · 10 PRESENCIA (una línea MUESTREADOR por proceso) · cualquier otro rc =
#   DESCONOCIDO: no se pudo enumerar /proc, o el argv de algún proceso que sigue vivo no se pudo leer, o error interno.
#   Un proceso que termina durante la consulta (su /proc/<pid> desaparece) no está en marcha: se cuenta y se informa.
# Solo lee /proc; python con -I -B -S y código en -c: no escribe caché ni importa nada del paquete.
MUESTREADORES_PY='
import json, os, re, sys

OBJETIVO = ("muestreo_fino.py", "obs_pcap.py", "muestreo_s14.py")
INTERPRETE = re.compile(r"python[0-9.]*\Z")


def muestreador(argv):
    """Nombre del muestreador que ejecuta este argv, o None."""
    if not argv or not INTERPRETE.match(os.path.basename(argv[0])):
        return None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if a == "-" or not a.startswith("-"):
            break
        if a.startswith("--"):
            i += 2 if a == "--check-hash-based-pycs" else 1
            continue
        for j, c in enumerate(a[1:], 1):
            if c in "cm":
                return None
            if c in "XW":
                if j == len(a) - 1:
                    i += 1
                break
        i += 1
    if i >= len(argv):
        return None
    nombre = os.path.basename(argv[i])
    if nombre in OBJETIVO:
        return nombre
    if nombre == "salud_captura.py" and i + 1 < len(argv) and argv[i + 1] == "muestrear":
        return "salud_captura.py muestrear"
    return None


def leer(proc="/proc", listar=os.listdir, abrir=open, existe=os.path.exists):
    presentes, desaparecidos, ilegibles, revisados = [], 0, [], 0
    for pid in sorted((p for p in listar(proc) if p.isdigit()), key=int):
        ruta = os.path.join(proc, pid)
        try:
            with abrir(os.path.join(ruta, "cmdline"), "rb") as f:
                crudo = f.read()
        except (FileNotFoundError, ProcessLookupError):
            desaparecidos += 1
            continue
        except OSError as e:
            if existe(ruta):
                ilegibles.append("%s: %s" % (pid, e))
            else:
                desaparecidos += 1
            continue
        revisados += 1
        argv = [x.decode("utf-8", "surrogateescape") for x in crudo.split(b"\0")]
        if argv and argv[-1] == "":
            argv.pop()
        n = muestreador(argv)
        if n:
            presentes.append((int(pid), n, argv))
    return presentes, desaparecidos, ilegibles, revisados


def main():
    try:
        presentes, desaparecidos, ilegibles, revisados = leer()
    except OSError as e:
        print("DESCONOCIDO no se pudo enumerar /proc: %s" % e)
        return 2
    for pid, n, argv in presentes:
        print("MUESTREADOR pid=%d %s argv=%s" % (pid, n, json.dumps(argv)))
    for x in ilegibles[:5]:
        print("ILEGIBLE %s" % x)
    print("CONSULTA revisados=%d desaparecidos=%d ilegibles=%d presentes=%d"
          % (revisados, desaparecidos, len(ilegibles), len(presentes)))
    if presentes:
        return 10
    if ilegibles:
        print("DESCONOCIDO argv ilegible en %d proceso(s) vivo(s)" % len(ilegibles))
        return 2
    if revisados == 0:
        print("DESCONOCIDO ningun proceso legible en /proc")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
'
muestreadores() { python3 -I -B -S -c "$MUESTREADORES_PY"; }
comprobar() {
  local FIN=$1 ISO=$2 v libre mem a rc viejo edad
  (cd "$P" && sha256sum -c --strict --quiet SHA256SUMS) && ok "paquete $(basename "$P"): SHA256SUMS verifica" || no "paquete $P"
  [ "$(sha256sum < "$P/deploy/etapa4/sensor1/evaluar_ecarga.py" | cut -c1-64)" = "$EV_ESPERADO" ] \
    && ok "evaluar_ecarga.py sha256 = publicado" || no "evaluar_ecarga.py sha256"
  v=$(python3 -I -B -c 'import importlib.util as u,sys;s=u.spec_from_file_location("e",sys.argv[1]);m=u.module_from_spec(s);s.loader.exec_module(m);print(m.VERSION)' "$P/deploy/etapa4/sensor1/evaluar_ecarga.py")
  [ "$v" = 2026-11-06.4 ] && ok "evaluar_ecarga VERSION $v" || no "evaluar_ecarga VERSION $v"
  (cd "$H" && sha256sum -c --strict --quiet SHA256SUMS) && ok "herramientas-20261106: SHA256SUMS verifica" || no "herramientas-20261106"
  cmp -s "$H/salud_captura.py" "$P/scripts/etapa4/salud_captura.py" && ok "salud_captura.py de herramientas = paquete" \
    || no "salud_captura.py de herramientas distinto del paquete"
  [ -x "$PY" ] && ok "python del venv: $("$PY" -V 2>&1)" || no "python del venv"
  for f in "$P/deploy/etapa4/cierre/muestreo_fino.py" "$P/deploy/etapa4/sensor1/obs_pcap.py" "$P/deploy/etapa4/sensor1/clasificar_periodo.py" \
           "$P/deploy/etapa4/sensor1/comparar_suricata.py" "$P/deploy/etapa4/sensor1/verificar_sensor1.sh" "$E/muestreo_s14.py" "$E/evaluar_s14.py"; do
    [ -r "$f" ] && ok "legible $(basename "$f")" || no "no legible $f"; done
  [ -r "$EVE" ] && ok "eve.json legible ($(stat -c %s "$EVE") B)" || no "eve.json no legible"
  [ -r "$ANILLO" ] && [ -x "$ANILLO" ] && ok "anillo legible ($(ls -1 "$ANILLO" | wc -l) ficheros)" || no "anillo no legible"
  viejo=$(ls -1 "$ANILLO" 2>/dev/null | grep -E '^live-[0-9]{14}\.pcap$' | sort | head -1)
  if [ -n "$viejo" ]; then
    edad=$(( $(date +%s) - $(date -u -d "${viejo:5:8} ${viejo:13:2}:${viejo:15:2}:${viejo:17:2}" +%s) ))
    [ "$edad" -ge $RETENCION_MIN ] && ok "retención del anillo: el fichero más antiguo tiene $edad s (>= $RETENCION_MIN s, la de derivar_pcap)" \
      || no "retención del anillo $edad s < $RETENCION_MIN s: derivar_pcap 2026-11-06.2 usa $RETENCION_MIN s"
  else no "no se pudo medir la retención del anillo"; fi
  for f in /proc/net/softnet_stat /proc/pressure/cpu /proc/pressure/io /proc/pressure/memory /proc/vmstat /proc/diskstats; do
    [ -r "$f" ] && ok "legible $f" || no "no legible $f (S14 r3 lo necesita)"; done
  [ "$(getconf CLK_TCK)" = 100 ] && ok "USER_HZ 100" || echo "INFO  USER_HZ $(getconf CLK_TCK) (muestreo_s14 lo registra)"
  for u in ppi-motor-capture ppi-via-rapida@ens37; do
    n=$(journalctl --no-pager -u "$u" --since "-10min" 2>/dev/null | grep -c "packets captured")
    [ "${n:-0}" -gt 0 ] && ok "journal de $u legible ($n lecturas SIGUSR1 en 10 min)" || no "journal de $u sin lecturas SIGUSR1"; done
  libre=$(df --output=avail -k /home 2>/dev/null | tail -1 | tr -d ' ')
  [[ $libre =~ ^[0-9]+$ ]] && [ "$libre" -ge 2097152 ] && ok "/home libre $((libre/1024)) MiB (>= 2 GiB)" || no "/home libre ${libre:-ilegible} kB"
  mem=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null)
  [[ $mem =~ ^[0-9]+$ ]] && [ "$mem" -ge 1048576 ] && ok "MemAvailable $((mem/1024)) MiB (>= 1 GiB)" || no "MemAvailable ${mem:-ilegible} kB"
  mkdir -p "$(dirname "$O")" && [ -w "$(dirname "$O")" ] && ok "destino de evidencia escribible: $(dirname "$O")" || no "destino $O"
  [ -e "$O" ] && no "DIR $O ya existe (no se reutiliza)" || ok "DIR $O libre"
  if a=$(ps -eo args 2>/dev/null) && [ -n "$a" ]; then
    grep -qE -- "--(enforce|aplicar)( |$)" <<<"$a" && no "hay procesos con --aplicar/--enforce" || ok "0 procesos con --aplicar/--enforce"
  else no "ps no se pudo leer"; fi
  m=$(muestreadores 2>&1); rc=$?
  printf '%s\n' "$m" | sed 's/^/INFO  muestreadores: /'
  case $rc in
    0) ok "ningún muestreador en marcha (ausencia confirmada: $(grep -m1 '^CONSULTA ' <<<"$m" | cut -c10-))";;
    10) no "ya hay muestreadores en marcha: $(grep '^MUESTREADOR ' <<<"$m" | cut -d' ' -f2-3 | tr '\n' ' ')";;
    *) no "estado de los muestreadores DESCONOCIDO (rc $rc): $(grep -m1 -E '^(DESCONOCIDO|ILEGIBLE)|Error' <<<"$m" | cut -c1-200)";;
  esac
  echo "== obs_pcap --en-seco"
  python3 -I -B "$P/deploy/etapa4/sensor1/obs_pcap.py" --dir "$ANILLO" --salida "$O-seco-obs_pcap" --hasta-epoch "$FIN" --hasta-iso "$ISO" --en-seco
  rc=$?; [ $rc = 0 ] && ok "obs_pcap --en-seco rc 0" || no "obs_pcap --en-seco rc $rc"
  [ -e "$O-seco-obs_pcap" ] && no "obs_pcap en seco creó $O-seco-obs_pcap" || ok "obs_pcap en seco no creó salida"
  echo "fallo=$fallo"; return $fallo
}
vivo() { [ -r /proc/$1/cmdline ] && tr '\0' ' ' < /proc/$1/cmdline 2>/dev/null | grep -q -- "$2"; }
arrancar() {
  local FIN=$1 ISO=$2 malos=0 pid nombre
  { [ -e "$O/muestras.jsonl" ] || [ -e "$O/pids" ]; } && { echo "ABORTA: $O ya tiene muestras o pids"; exit 2; }
  mkdir -p "$O" || exit 2
  (cd "$H" && sha256sum -c --strict --quiet SHA256SUMS) || { echo "ABORTA: herramientas-20261106"; exit 2; }
  (setsid nohup "$PY" -I "$H/salud_captura.py" muestrear --salida "$O/muestras.jsonl" --suricata-stats /var/log/suricata/stats.log \
     --interfaz ens37 --unidad ppi-motor --unidad ppi-motor-capture --unidad ppi-via-rapida@ens37 --unidad ppi-publicar-feed-v2 \
     --unidad suricata --anillo "$ANILLO" --resumen-rapida "$HOME/feed-v2/via-rapida-resumen.jsonl" \
     --ciclos "$HOME/cyberflow/logs/_state-e4/ciclos.jsonl" --hijos-de-unidad ppi-via-rapida@ens37 --intervalo 10 --hasta "$ISO" \
     > "$O/muestrear.out" 2>&1 < /dev/null & echo "$! salud_captura.py muestrear" >> "$O/pids")
  (setsid nohup python3 -I "$P/deploy/etapa4/cierre/muestreo_fino.py" --salida "$O/fino.jsonl" --intervalo 1 --hasta "$FIN" \
     > "$O/fino.out" 2>&1 < /dev/null & echo "$! muestreo_fino.py" >> "$O/pids")
  (setsid nohup python3 -I "$P/deploy/etapa4/sensor1/obs_pcap.py" --dir "$ANILLO" --salida "$O/obs_pcap" --hasta-epoch "$FIN" \
     --hasta-iso "$ISO" > "$O/obs_pcap.log" 2>&1 < /dev/null & echo "$! obs_pcap.py" >> "$O/pids")
  (setsid nohup python3 -I "$E/muestreo_s14.py" --salida "$O/s14.jsonl" --intervalo 1 --hasta "$FIN" \
     > "$O/s14.out" 2>&1 < /dev/null & echo "$! muestreo_s14.py" >> "$O/pids")
  echo "$(date -u +%FT%TZ) arrancados (fin $FIN = $ISO)" >> "$O/eventos.log"
  sleep 3
  while read -r pid nombre; do
    vivo "$pid" "$nombre" && echo "vivo   $pid $nombre" || { echo "NO ARRANCÓ $pid $nombre"; malos=1; }
  done < "$O/pids"
  [ $malos = 0 ] && { echo "ARRANQUE_CONFIRMADO: 4 muestreadores vivos"; return 0; }
  echo "ARRANQUE_INCOMPLETO: ver $O/*.out y obs_pcap.log"; return 3
}
estado() {
  [ -r "$O/pids" ] || { echo "sin $O/pids"; return 2; }
  while read -r pid nombre; do
    vivo "$pid" "$nombre" && echo "vivo   $pid $nombre" || echo "parado $pid $nombre"
  done < "$O/pids"
  for f in muestras.jsonl fino.jsonl obs_pcap/pcap.jsonl s14.jsonl; do [ -e "$O/$f" ] && echo "fichero $f $(wc -l < "$O/$f") líneas"; done
  return 0
}
parar() {
  local pid nombre quedan=0
  [ -r "$O/pids" ] || { echo "sin $O/pids"; return 2; }
  while read -r pid nombre; do
    vivo "$pid" "$nombre" && { kill -TERM "$pid" && echo "TERM $pid $nombre" || echo "TERM falló $pid $nombre"; }
  done < "$O/pids"
  echo "$(date -u +%FT%TZ) parada manual" >> "$O/eventos.log"; sleep 3
  while read -r pid nombre; do vivo "$pid" "$nombre" && { echo "SIGUE VIVO $pid $nombre"; quedan=1; }; done < "$O/pids"
  [ $quedan = 0 ] && { echo "PARADA_CONFIRMADA: ningún muestreador de $O vivo"; return 0; }
  return 3
}
case "$ORDEN" in
  comprobar) comprobar "${3:?FIN_EPOCH}" "${4:?FIN_ISO}" ;;
  arrancar)  arrancar "${3:?FIN_EPOCH}" "${4:?FIN_ISO}" ;;
  estado)    estado ;;
  parar)     parar ;;
  *) echo "orden no válida"; exit 2 ;;
esac
