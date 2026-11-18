#!/usr/bin/env bash
# [SENSOR1 m4rk] Verificación de la 4A en Sensor1: SOLO lecturas, sin sudo (la puede ejecutar Claude).
#   bash verificar_sensor1.sh [RESPALDO_DIR]
# Cada línea: "OK", "FALLO" (para la 4A) o "INFO". Código de salida 1 si hay algún FALLO.
# 2026-11-06 (pendientes 4A): el publicador v1 se retiró en el cierre complementario (04-nov); ahora debe estar
# inactivo, NO habilitado y sin procesos, y el motor_startup se busca en los registros actual y rotados (también .gz)
# y debe ser el del PROCESO VIGENTE (comun/verif_estado.py). Un error de lectura o de systemctl nunca da OK.
set -uo pipefail
R="${1:-}"
fallo=0
# 4A (2026-11-04): cada comprobación sin pipefail (grep -q corta la tubería: SIGPIPE río arriba daba FALLO falso).
c() { if ( set +o pipefail; eval "$2" ); then echo "OK    $1"; else echo "FALLO $1"; fallo=1; fi; }
i() { echo "INFO  $*"; }
# Ejecuta un bloque de comprobaciones que imprime OK/FALLO/INFO: FALLO si alguna línea es FALLO, si su código de
# salida no es 0 o si no imprimió ningún OK (un guion que se rompe sin escribir nada no puede pasar por correcto).
bloque() { local n="$1" s; shift; s=$("$@" 2>&1); local rc=$?; [ -n "$s" ] && echo "$s"
  if [ $rc -ne 0 ] || grep -q '^FALLO' <<<"$s" || ! grep -q '^OK' <<<"$s"; then
    grep -q '^FALLO' <<<"$s" || echo "FALLO $n (rc=$rc sin resultado)"; fallo=1; fi; }
VE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/comun/verif_estado.py"
E4="$HOME/cyberflow-e4"
L="$HOME/cyberflow/logs/motor_decision.log"
F="$HOME/feed-v2"
PY="$HOME/cyberflow/.venv/bin/python"
pm=$(systemctl show -p MainPID --value ppi-motor)
pc=$(systemctl show -p MainPID --value ppi-motor-capture)
pv=$(systemctl show -p MainPID --value ppi-via-rapida@ens37)

# ---- servicios y versión cargada
for u in ppi-motor ppi-motor-capture ppi-via-rapida@ens37 ppi-publicar-feed-v2 cf-tcpdump-estadisticas.timer \
         suricata; do
  c "$u activo" "systemctl is-active --quiet $u"
done
bloque "publicador v1 retirado" python3 -I "$VE" v1-retirado \
  --unidad ppi-publicar-feed.timer --unidad ppi-publicar-feed.service --proceso publicar_feed.py
c "motor = candidato ec78ca5 con --disparo eventos" \
  "tr '\0' ' ' < /proc/$pm/cmdline | grep -q 'cyberflow-e4/ec78ca5/scripts/engine/motor_decision.py .*--disparo eventos'"
c "motor SIN --enforce" "! tr '\0' ' ' < /proc/$pm/cmdline | grep -q -- '--enforce'"
c "captura con -G 5" "tr '\0' ' ' < /proc/$pc/cmdline | grep -q -- '-G 5'"
c "código candidato sin cambios (SHA256SUMS)" "( cd $E4/ec78ca5 && sha256sum -c --quiet SHA256SUMS )"
[ -n "$R" ] && c "código anterior ~/cyberflow intacto" "( cd $HOME/cyberflow && sha256sum -c --quiet $R/cyberflow-codigo.sha256 )"
c "importaciones desde el candidato" "bash $E4/ec78ca5/deploy/etapa4/sensor1/comprobar_importaciones.sh \
  $E4/ec78ca5 $PY $HOME/cyberflow $HOME/cyberflow/scripts > /dev/null"
i "NRestarts motor/captura/vía: $(systemctl show -p NRestarts --value ppi-motor)/$(systemctl show -p NRestarts --value ppi-motor-capture)/$(systemctl show -p NRestarts --value ppi-via-rapida@ens37)"

# ---- arranque del motor: el del PROCESO VIGENTE, en el registro actual o en los rotados (también .gz)
# 2026-11-06: antes se buscaba solo en el registro actual; tras la rotación diaria daba FALLO falso, y cualquier
# arranque histórico con el mismo umbral habría dado OK. Ahora se contrasta con el inicio real del PID, su línea de
# ejecución y el umbral del manifiesto (y el congelado). Lo que no se pueda demostrar es FALLO.
bloque "motor_startup del proceso vigente" python3 -I "$VE" motor-arranque --unidad ppi-motor --registro "$L" \
  --umbral -0.5693969936322356 --disparo eventos --procesamiento incremental

# ---- decisiones del motor candidato (últimas 2000 líneas del registro actual)
bloque "decisiones del motor" "$PY" -I -c '
import collections, json, sys
dec = []
with open(sys.argv[1], encoding="utf-8") as f:
    for l in collections.deque(f, 2000):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get("event") == "decision":
            dec.append(r)
def c(n, ok):
    print(("OK    " if ok else "FALLO ") + n)
nuevas = [d for d in dec if "decision_if" in d]
print(f"INFO  decisiones en la cola del registro actual: {len(dec)} ({len(nuevas)} con decision_if)")
c("decisiones con decision_if y auth_failure", bool(nuevas) and all("auth_failure" in d for d in nuevas))
c("decisiones con http_vista y dns_vista", bool(nuevas) and all("http_vista" in d and "dns_vista" in d for d in nuevas))
tard = sum(1 for d in nuevas if (d.get("http_vista") or {}).get("httph_tardios_excluidos_60s"))
print(f"INFO  decisiones con registros HTTP tardíos excluidos de la vista: {tard} de {len(nuevas)}")
af = [d for d in nuevas if (d.get("auth_failure") or {}).get("historico") and not (d.get("auth_failure") or {}).get("vista")]
print(f"INFO  auth_failure solo histórico (no aceptado por la vista HTTP): {len(af)}")
' "$L"
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
