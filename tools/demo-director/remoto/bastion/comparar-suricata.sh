#!/bin/bash
# Mismo trafico, dos detectores. SOLO LECTURA en Sensor1 (salvo dejar el resumen
# en ~/feed/comparaciones/); en la VM de Suricata escribe solo en ~/cf-demo/.
# No necesita sudo en ninguna maquina.
# Uso: comparar-suricata.sh <IP> <desde_epoch> <hasta_epoch> [escenario]
#
# Ademas de la salida para la consola deja la EVIDENCIA en dos sitios:
#   VM Suricata  ~/cf-demo/<ID>/{pcap,log/fast.log,log/eve.json}  (lo que vio Suricata)
#   Sensor1      ~/feed/comparaciones/<ID>.json                    (resumen que lee el panel)
set -uo pipefail
IP=${1:?IP}; DESDE=${2:?desde}; HASTA=${3:?hasta}; ESC=${4:-}
export TZ=America/Lima
C1=$'\033[1;36m'; C0=$'\033[0m'; AM=$'\033[1;33m'
paso() { printf "\n${C1}▶ %s${C0}\n" "$1"; }
T0=$(date +%s)
ID=cmp-$(date +%Y%m%d-%H%M%S)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

paso "1/4 Sensor1: tráfico de $IP entre $(date -d @$DESDE +%T) y $(date -d @$HASTA +%T) (anillo PCAP del espejo)"
timeout 120 ssh -o BatchMode=yes sensor1 "
  set -e; d=\$(mktemp -d); n=0
  for f in /var/lib/ppi-motor-capture/live-*.pcap; do
    m=\$(stat -c %Y \"\$f\")
    if [ \$m -ge $((DESDE - 5)) ] && [ \$m -le $((HASTA + 20)) ]; then
      tcpdump -r \"\$f\" -w \"\$d/\$(basename \$f)\" \"host $IP or (vlan and host $IP)\" 2>/dev/null || true; n=\$((n+1)); fi
  done
  echo \"  ficheros del anillo leídos: \$n\" >&2
  python3 ~/cf-demo/recortar_pcap.py $DESDE $HASTA \"\$d\"/*.pcap
  tar -C \"\$d\" -czf - . ; rm -rf \"\$d\"" > "$TMP/pcap.tgz" 2> >(tee "$TMP/p1.txt" >&2)
sleep 0.3
echo "  paquetes extraídos: $(du -h "$TMP/pcap.tgz" | cut -f1) comprimidos"

paso "2/4 Copia a la VM de Suricata (10.10.60.13), aislada del sensor"
timeout 120 ssh -o BatchMode=yes suricata "mkdir -p ~/cf-demo/$ID/pcap ~/cf-demo/$ID/log && tar -m -C ~/cf-demo/$ID/pcap -xzf - 2>/dev/null" < "$TMP/pcap.tgz"
echo "  evidencia: suricata:~/cf-demo/$ID/"

FIRMAS=$(timeout 30 ssh -o BatchMode=yes suricata "grep -cE '^(alert|drop|reject|pass) ' /var/lib/suricata/rules/suricata.rules" 2>/dev/null)
paso "3/4 Suricata 7 + ET Open (${FIRMAS:-?} firmas activas) analiza ese mismo tráfico"
timeout 600 ssh -o BatchMode=yes suricata "
  cd ~/cf-demo/$ID; t=\$(date +%s.%N)
  suricata -c ~/suricata-compare-trial-20261002/suricata.yaml -S /var/lib/suricata/rules/suricata.rules \
    -r pcap -l log -k none --runmode single >log/salida.txt 2>&1
  seg=\$(echo \"\$(date +%s.%N) - \$t\" | bc | cut -c1-5)
  n=\$(cat log/fast.log 2>/dev/null | wc -l)
  dist=\$(cut -d']' -f3 log/fast.log 2>/dev/null | sed 's/\[Classification.*//' | sort -u | grep -c .)
  echo \"  Suricata tardó \$seg s (carga de firmas incluida)\"
  echo \"  alertas de Suricata: \$n  (firmas distintas: \$dist; cada paquete llega 2 veces: VLAN 20 y 30 del espejo)\"
  [ \"\$n\" -gt 0 ] && echo \"  primera alerta de Suricata: \$(head -1 log/fast.log | cut -c12-19) (hora del paquete, UTC)\"
  [ \"\$n\" -gt 0 ] && cut -d']' -f3- log/fast.log | sed 's/\[Classification.*//' | sort | uniq -c | sort -rn | head -6 | sed 's/^/    /'
  echo \"@@version=\$(suricata -V 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)\"
  echo \"@@segundos=\$seg\"; echo \"@@alertas=\$n\"; echo \"@@distintas=\$dist\"
  [ \"\$n\" -gt 0 ] && echo \"@@primera=\$(head -1 log/fast.log | cut -c1-19)\"
  [ \"\$n\" -gt 0 ] && cut -d']' -f3- log/fast.log | sed 's/\[Classification.*//; s/^ *//; s/ *\[\*\*\] *$//' | sort | uniq -c | sort -rn | head -5 | sed -E 's/^ *([0-9]+) (.*)$/@@top=\1|\2/'
  true" > "$TMP/p3.txt"
grep -v '^@@' "$TMP/p3.txt"

paso "4/4 CyberFlow sobre la misma ventana (registro del motor y acuse del host)"
timeout 60 ssh -o BatchMode=yes sensor1 "export TZ=America/Lima
  tail -n 40000 ~/cyberflow/logs/motor_decision.log | jq -r --arg ip $IP --arg d $(date -u -d @$DESDE +%FT%T) --arg h $(date -u -d @$((HASTA + 10)) +%FT%T) '
    select(.entity_ip==\$ip and .window_end_utc>\$d and .window_end_utc<=\$h)
    | (.decision==\"ALERT\" and .score!=null and .threshold!=null and (.score < .threshold)) as \$claro
    | [(.logged_at|localtime|strftime(\"%H:%M:%S\")),
       (if .heuristico then .heuristico.accion elif \$claro then \"LIMIT\" else \"-\" end),
       (if \$claro then \"modelo\" else \"\" end),
       (if .heuristico then .heuristico.heuristico else \"\" end)] | join(\"|\")' > /tmp/cfcmp.txt
  tot=\$(wc -l < /tmp/cfcmp.txt); acc=\$(grep -cv '^[^|]*|-|' /tmp/cfcmp.txt)
  echo \"  ventanas de $IP: \$tot · con acción: \$acc\"
  echo \"@@ventanas=\$tot\"; echo \"@@con_accion=\$acc\"
  primera=\$(grep -v '^[^|]*|-|' /tmp/cfcmp.txt | head -1)
  if [ -n \"\$primera\" ]; then
    echo \"  primera acción: \$(echo \$primera | awk -F'|' '{printf \"%s  %s  %s %s\", \$1, \$2, \$3, \$4}')\"
    echo \"@@primera_cf=\$primera\"
  fi
  grep -v '^[^|]*|-|' /tmp/cfcmp.txt | awk -F'|' '{k=\$2\"  \"(\$3!=\"\"&&\$4!=\"\"?\$3\" + \"\$4:\$3\$4); c[k]++} END{for(k in c) printf \"    %2d ventanas  %s\\n\", c[k], k}'
  grep -v '^[^|]*|-|' /tmp/cfcmp.txt | awk -F'|' '{k=\$2\"|\"(\$3!=\"\"&&\$4!=\"\"?\$3\" + \"\$4:\$3\$4); c[k]++} END{for(k in c) printf \"@@desglose=%d|%s\\n\", c[k], k}'
  python3 - <<'PY'
import json, time
try:
    a = json.load(open('/home/m4rk/feed/acuses/srv-dmz.json'))
except Exception:
    a = {}
ev = [e for e in a.get('eventos', []) if e.get('ip') == '$IP' and e.get('evento') in ('aplicada', 'cambiada')
      and $DESDE - 5 <= float(e.get('t', 0)) <= $HASTA + 180]
if ev:
    e = ev[0]
    print('  aplicada en srv-dmz: %s %s (acuse del host)' % (time.strftime('%H:%M:%S', time.localtime(float(e['t']))), e.get('accion', '')))
    print('@@aplicada=%s|%s' % (time.strftime('%H:%M:%S', time.localtime(float(e['t']))), e.get('accion', '')))
PY
  rm -f /tmp/cfcmp.txt" > "$TMP/p4.txt"
grep -v '^@@' "$TMP/p4.txt"

# Resumen JSON de la comparacion -> Sensor1 (~/feed/comparaciones/), para el panel.
python3 - "$TMP" "$ID" "$IP" "$DESDE" "$HASTA" "$ESC" "${FIRMAS:-0}" <<'PY' | timeout 30 ssh -o BatchMode=yes sensor1 "mkdir -p ~/feed/comparaciones && cat > ~/feed/comparaciones/.tmp && mv ~/feed/comparaciones/.tmp ~/feed/comparaciones/$ID.json"
import json, re, sys, time
tmp, ident, ip, desde, hasta, esc, firmas = sys.argv[1:8]
def kv(fichero):
    d = {}
    for l in open(fichero, encoding='utf-8', errors='replace'):
        if l.startswith('@@') and '=' in l:
            k, v = l[2:].rstrip('\n').split('=', 1)
            d.setdefault(k, []).append(v)
    return d
p1 = open(tmp + '/p1.txt', encoding='utf-8', errors='replace').read()
s, c = kv(tmp + '/p3.txt'), kv(tmp + '/p4.txt')
uno = lambda d, k, f=str, x=None: f(d[k][0]) if k in d and d[k][0] != '' else x
m = re.search(r'intervalo exacto: (\d+) de (\d+)', p1)
fl = re.search(r'leídos: (\d+)', p1)
prim = uno(c, 'primera_cf', str, '')
apl = uno(c, 'aplicada', str, '')
print(json.dumps({
    'id': ident, 'escenario': esc or None, 'ip': ip, 'desde': float(desde), 'hasta': float(hasta),
    'generado': time.time(),
    'pcap': {'ficheros': int(fl.group(1)) if fl else None,
             'paquetes': int(m.group(1)) if m else None, 'leidos': int(m.group(2)) if m else None},
    'suricata': {'version': uno(s, 'version'), 'firmas': int(firmas or 0), 'segundos': uno(s, 'segundos', float),
                 'alertas': uno(s, 'alertas', int, 0), 'firmas_distintas': uno(s, 'distintas', int, 0),
                 'primera_utc': uno(s, 'primera'),
                 'top': [{'n': int(t.split('|', 1)[0]), 'firma': t.split('|', 1)[1]} for t in s.get('top', [])],
                 'evidencia': 'suricata:~/cf-demo/%s/log/fast.log' % ident},
    'cyberflow': {'ventanas': uno(c, 'ventanas', int, 0), 'con_accion': uno(c, 'con_accion', int, 0),
                  'primera': dict(zip(('hora', 'accion', 'modelo', 'regla'), prim.split('|'))) if prim else None,
                  'desglose': [dict(zip(('n', 'accion', 'origen'), x.split('|', 2))) for x in c.get('desglose', [])],
                  'aplicada': dict(zip(('hora', 'accion'), apl.split('|'))) if apl else None,
                  'evidencia': 'sensor1:~/cyberflow/logs/motor_decision.log'},
}, ensure_ascii=False))
PY

printf "\n${AM}Comparación lista en %s s.${C0} Suricata solo alerta (no responde); CyberFlow decide y publica la respuesta.\n" $(( $(date +%s) - T0 ))
echo "Evidencia: suricata:~/cf-demo/$ID/log/fast.log · sensor1:~/feed/comparaciones/$ID.json"
