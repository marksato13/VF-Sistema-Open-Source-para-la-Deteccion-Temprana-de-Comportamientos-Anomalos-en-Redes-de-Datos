#!/usr/bin/env bash
# [SENSOR1 m4rk] Verificación de la 4A en Sensor1: SOLO lecturas, sin sudo (la puede ejecutar Claude).
#   bash verificar_sensor1.sh [RESPALDO_DIR]
# Cada línea: "OK", "FALLO" (para la 4A) o "INFO". Código de salida 1 si hay algún FALLO.
set -uo pipefail
R="${1:-}"
fallo=0
# 4A (2026-11-04): cada comprobación sin pipefail (grep -q corta la tubería: SIGPIPE río arriba daba FALLO falso).
c() { if ( set +o pipefail; eval "$2" ); then echo "OK    $1"; else echo "FALLO $1"; fallo=1; fi; }
i() { echo "INFO  $*"; }
E4="$HOME/cyberflow-e4"
L="$HOME/cyberflow/logs/motor_decision.log"
F="$HOME/feed-v2"
PY="$HOME/cyberflow/.venv/bin/python"
pm=$(systemctl show -p MainPID --value ppi-motor)
pc=$(systemctl show -p MainPID --value ppi-motor-capture)
pv=$(systemctl show -p MainPID --value ppi-via-rapida@ens37)

# ---- servicios y versión cargada
for u in ppi-motor ppi-motor-capture ppi-via-rapida@ens37 ppi-publicar-feed-v2 cf-tcpdump-estadisticas.timer \
         suricata ppi-publicar-feed.timer; do
  c "$u activo" "systemctl is-active --quiet $u"
done
c "motor = candidato ec78ca5 con --disparo eventos" \
  "tr '\0' ' ' < /proc/$pm/cmdline | grep -q 'cyberflow-e4/ec78ca5/scripts/engine/motor_decision.py .*--disparo eventos'"
c "motor SIN --enforce" "! tr '\0' ' ' < /proc/$pm/cmdline | grep -q -- '--enforce'"
c "captura con -G 5" "tr '\0' ' ' < /proc/$pc/cmdline | grep -q -- '-G 5'"
c "código candidato sin cambios (SHA256SUMS)" "( cd $E4/ec78ca5 && sha256sum -c --quiet SHA256SUMS )"
[ -n "$R" ] && c "código anterior ~/cyberflow intacto" "( cd $HOME/cyberflow && sha256sum -c --quiet $R/cyberflow-codigo.sha256 )"
c "importaciones desde el candidato" "bash $E4/ec78ca5/deploy/etapa4/sensor1/comprobar_importaciones.sh \
  $E4/ec78ca5 $PY $HOME/cyberflow $HOME/cyberflow/scripts > /dev/null"
i "NRestarts motor/captura/vía: $(systemctl show -p NRestarts --value ppi-motor)/$(systemctl show -p NRestarts --value ppi-motor-capture)/$(systemctl show -p NRestarts --value ppi-via-rapida@ens37)"

# ---- registros del motor candidato (últimas 2000 líneas + el ÚLTIMO motor_startup de todo el registro)
# 4A (2026-11-04): tras ~2000 decisiones el arranque salía de la cola y la comprobación daba FALLO falso.
{ grep -F '"event": "motor_startup"' "$L" | tail -1; tail -2000 "$L"; } > /tmp/e4-ult.jsonl
"$PY" - /tmp/e4-ult.jsonl > /tmp/e4-registros.txt <<'EOF'
import json, sys
dec, ini = [], None
for l in open(sys.argv[1], encoding="utf-8"):
    try:
        r = json.loads(l)
    except ValueError:
        continue
    if r.get("event") == "decision":
        dec.append(r)
    elif r.get("event") == "motor_startup":
        ini = r
def c(n, ok):
    print(("OK    " if ok else "FALLO ") + n)
nuevas = [d for d in dec if "decision_if" in d]
c("decisiones con decision_if y auth_failure", bool(nuevas) and all("auth_failure" in d for d in nuevas))
c("decisiones con http_vista y dns_vista", bool(nuevas) and all("http_vista" in d and "dns_vista" in d for d in nuevas))
c("motor_startup del candidato (incremental, disparo eventos, umbral del manifiesto)",
  ini is not None and ini.get("disparo") == "eventos" and "-0.5693969936322356" in json.dumps(ini))
tard = sum(1 for d in nuevas if (d.get("http_vista") or {}).get("httph_tardios_excluidos_60s"))
print(f"INFO  decisiones con registros HTTP tardíos excluidos de la vista: {tard} de {len(nuevas)}")
af = [d for d in nuevas if (d.get("auth_failure") or {}).get("historico") and not (d.get("auth_failure") or {}).get("vista")]
print(f"INFO  auth_failure solo histórico (no aceptado por la vista HTTP): {len(af)}")
EOF
cat /tmp/e4-registros.txt
grep -q '^FALLO' /tmp/e4-registros.txt && fallo=1
i "último ciclo: $(tail -1 "$HOME/cyberflow/logs/_state-e4/ciclos.jsonl" 2>/dev/null | cut -c1-300)"

# ---- vía rápida
bh() { tail -1 "$F/via-rapida-resumen.jsonl" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["bloque_hasta"])'; }
b1=$(bh); sleep 3; b2=$(bh)
c "resumen de la vía rápida avanza ($b1 -> $b2)" "[ '$b1' != '$b2' ]"
i "resumen vía rápida: $(tail -1 "$F/via-rapida-resumen.jsonl")"
i "señales rápidas: $(wc -l < "$F/senales-rapidas.jsonl" 2>/dev/null || echo 0) líneas (sin ataques, 0 sobre legítimos)"
i "tcpdump de la vía rápida: PID $(pgrep -x -P "$pv" tcpdump); estadísticas en journalctl -u ppi-via-rapida@ens37"

# ---- publicador v2 y feed
c "feed v2 reciente (< 60 s)" "[ \$(( \$(date +%s) - \$(stat -c %Y $F/feed.json) )) -lt 60 ]"
c "firma del feed v2 verifica con la clave PÚBLICA" \
  "openssl pkeyutl -verify -pubin -inkey $E4/pub.pem -rawin -in $F/feed.json -sigfile $F/feed.sig > /dev/null 2>&1"
i "traza del publicador (última): $(tail -1 "$F/traza.jsonl" | cut -c1-300)"
i "eventos 'rechazada' en la traza: $(grep -c '"rechazada"' "$F/traza.jsonl")"
i "menciones de dns_entropy en el feed v2 actual: $(grep -o 'dns_entropy' "$F/feed.json" | wc -l) (no hay agente DNS: nada se aplica en DC1)"

# ---- estadísticas de captura, relojes y recursos
c "SIGUSR1 periódico del anillo en el journal (últimos 2 min)" \
  "journalctl -u ppi-motor-capture --since -2min --no-pager | grep -q 'packets captured'"
c "SIGUSR1 periódico de la vía rápida en el journal (últimos 2 min)" \
  "journalctl -u ppi-via-rapida@ens37 --since -2min --no-pager | grep -q 'packets captured'"
i "anillo: $(ls /var/lib/ppi-motor-capture | wc -l) ficheros; últimos: $(ls /var/lib/ppi-motor-capture | tail -3 | tr '\n' ' ')"
i "suricata: $(tail -c 20000 /var/log/suricata/stats.log | grep -E 'capture.kernel_(packets|drops)' | tail -2 | tr -s ' ' | tr '\n' ' ')"
c "reloj sincronizado" "timedatectl show -p NTPSynchronized --value | grep -qx yes"
i "recursos: $(uptime | sed 's/.*load/load/'); mem $(free -m | awk '/Mem:/{print $3"/"$2" MB"}'); /home libre $(df -h --output=avail /home | tail -1)"
c "logrotate de feed-v2 instalado" "[ -f /etc/logrotate.d/cyberflow-etapa4 ]"
[ "$fallo" = 0 ] && echo "VERIFICACIÓN SENSOR1 OK" || { echo "VERIFICACIÓN SENSOR1 CON FALLOS"; exit 1; }
