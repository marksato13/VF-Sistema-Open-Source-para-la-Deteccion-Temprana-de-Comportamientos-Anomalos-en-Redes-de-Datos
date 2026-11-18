#!/usr/bin/env bash
# Ensayo de banco (Etapa 4): unidades y comprobación de importaciones. SOLO en el banco Docker.
#
#   docker run --rm --network none -v "<repo>:/src:ro" -v "<arbol-24f8a80>:/viejo:ro" -v "<salida>:/out" \
#     cyberflow-etapa3-banco:1 bash /src/deploy/etapa4/banco/ensayo_unidades_importaciones.sh
#
#   <arbol-24f8a80>: git archive 24f8a80 scripts configs (lo desplegado hoy en Sensor1 ~/cyberflow).
#
# U1  systemd-analyze verify de cada unidad nueva y de ppi-motor/ppi-motor-capture con su drop-in sobre
#     la COPIA LITERAL de las unidades base observadas en Sensor1 (banco/observado-sensor1/).
# U2  el ExecStart efectivo tras el drop-in es exactamente el del candidato (un solo ExecStart).
# U3  comprobar_importaciones.sh con la disposición real (cwd ~/cyberflow con el código viejo al lado)
#     da OK; y da PARADA si el código viejo entra en sys.path (caso que debe detectar).
set -u
OUT=/out; LOG="$OUT/ensayo-unidades-importaciones.txt"; mkdir -p "$OUT"; : > "$LOG"
fallo=0
say() { printf '%s\n' "$*" | tee -a "$LOG"; }
comprobar() { if eval "$2" >> "$LOG" 2>&1; then say "OK    $1"; else say "FALLO $1"; fallo=1; fi; }
[ -f /.dockerenv ] || { echo "solo en el banco"; exit 2; }
say "systemd: $(systemctl --version | head -1); python: $(python3 --version)"

# Usuarios y rutas falsas para que verify encuentre ejecutables y cuentas.
for u in m4rk gadmin cfagente; do id "$u" > /dev/null 2>&1 || useradd -m "$u"; done
id tcpdump > /dev/null 2>&1 || useradd -r tcpdump
install -d /home/m4rk/cyberflow/.venv/bin /home/m4rk/cyberflow/logs /home/m4rk/cyberflow-e4/ec78ca5 /home/m4rk/feed-v2 \
  /var/lib/ppi-motor-capture /var/log/suricata /opt/cyberflow/relay-v2 /opt/cyberflow/agente-v2
ln -sf /usr/bin/python3 /home/m4rk/cyberflow/.venv/bin/python
cp -r /viejo/scripts /viejo/configs /home/m4rk/cyberflow/
cp -r /src/scripts /src/configs /src/deploy /home/m4rk/cyberflow-e4/ec78ca5/
find /home/m4rk/cyberflow-e4 -name __pycache__ -prune -exec rm -rf {} +
cp /src/deploy/enforcement/relay_eventos.py /src/scripts/engine/feed.py /opt/cyberflow/relay-v2/
cp /src/scripts/enforce/agente_enforce_v2.py /src/scripts/engine/feed.py /opt/cyberflow/agente-v2/

# Unidades
U=/src/deploy/etapa4/unidades
B=/src/deploy/etapa4/banco/observado-sensor1
install -m 0644 "$B/ppi-motor.service" "$B/ppi-motor-capture.service" /etc/systemd/system/
install -d /etc/systemd/system/ppi-motor.service.d /etc/systemd/system/ppi-motor-capture.service.d
install -m 0644 "$U/sensor1/ppi-motor.service.d/etapa4.conf" /etc/systemd/system/ppi-motor.service.d/
install -m 0644 "$U/sensor1/ppi-motor-capture.service.d/etapa4.conf" /etc/systemd/system/ppi-motor-capture.service.d/
install -m 0644 "$U/sensor1/ppi-publicar-feed-v2.service" "$U/sensor1/ppi-via-rapida@.service" \
  "$U/sensor1/cf-tcpdump-estadisticas.service" "$U/sensor1/cf-tcpdump-estadisticas.timer" \
  "$U/bastion/ppi-relay-eventos.service" "$U/srvdmz/ppi-enforce-agent-v2-dmz.service" /etc/systemd/system/
# suricata.service no existe en el banco: verify avisaría de la dependencia After=; se crea un sustituto.
printf '[Service]\nExecStart=/bin/true\n' > /etc/systemd/system/suricata.service
# Igual con cyberflow-capture-nic.service (existe en Sensor1; la base de la captura depende de ella).
printf '[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/bin/true\n' > /etc/systemd/system/cyberflow-capture-nic.service
for u in ppi-motor.service ppi-motor-capture.service ppi-publicar-feed-v2.service ppi-via-rapida@ens37.service \
         cf-tcpdump-estadisticas.service cf-tcpdump-estadisticas.timer ppi-relay-eventos.service ppi-enforce-agent-v2-dmz.service; do
  out=$(SYSTEMD_LOG_LEVEL=notice systemd-analyze verify --man=no "/etc/systemd/system/${u/@ens37/@}" 2>&1 \
        | grep -v -e 'Failed to connect to bus' -e 'ens37.device' -e '^$')
  [ "${u#*@}" != "$u" ] && out=$(SYSTEMD_LOG_LEVEL=notice systemd-analyze verify --man=no "$u" 2>&1 \
        | grep -v -e 'Failed to connect to bus' -e 'sys-subsystem-net-devices' -e '^$')
  printf '%s\n' "--- $u" "$out" >> "$LOG"
  comprobar "U1 systemd-analyze verify $u sin avisos" "[ -z \"\$(printf '%s' \"$out\")\" ]"
done

# U2: un solo ExecStart efectivo con el candidato (el vacío del drop-in anula el de la base)
python3 - <<'EOF' >> "$LOG" 2>&1
import configparser, glob
def efectivo(base, dropins):
    ex = []
    for f in [base] + sorted(glob.glob(dropins)):
        txt, cur, sec = open(f).read().replace("\\\n", " "), None, None
        for l in txt.splitlines():
            l = l.strip()
            if l.startswith("["):
                sec = l
            elif sec == "[Service]" and l.startswith("ExecStart="):
                v = l.split("=", 1)[1].strip()
                ex = [] if v == "" else ex + [" ".join(v.split())]
    return ex
m = efectivo("/etc/systemd/system/ppi-motor.service", "/etc/systemd/system/ppi-motor.service.d/*.conf")
c = efectivo("/etc/systemd/system/ppi-motor-capture.service", "/etc/systemd/system/ppi-motor-capture.service.d/*.conf")
print("motor:", m); print("captura:", c)
assert len(m) == 1 and "/home/m4rk/cyberflow-e4/ec78ca5/scripts/engine/motor_decision.py" in m[0] and m[0].endswith("--disparo eventos")
assert "--state-dir /home/m4rk/cyberflow/logs/_state-e4" in m[0] and "--enforce" not in m[0]
base = efectivo("/etc/systemd/system/ppi-motor.service", "/nada/*")[0].split()
nuevo = m[0].split()
# mismos argumentos que la base salvo el guion, --state-dir y --disparo
quitar = lambda a: [x for i, x in enumerate(a) if x not in ("--state-dir", "--disparo") and (i == 0 or a[i-1] not in ("--state-dir", "--disparo")) and not x.endswith("motor_decision.py")]
assert quitar(base) == quitar(nuevo), (quitar(base), quitar(nuevo))
assert len(c) == 1 and c[0].endswith("-G 5") and "-G 15" not in c[0]
print("U2 OK")
EOF
comprobar "U2 ExecStart efectivo: candidato, mismos argumentos de detección, -G 5" "grep -q '^U2 OK' '$LOG'"

# U3: importaciones
I=/home/m4rk/cyberflow-e4/ec78ca5/deploy/etapa4/sensor1/comprobar_importaciones.sh
comprobar "U3 importaciones desde el candidato con la disposición de Sensor1" \
  "bash $I /home/m4rk/cyberflow-e4/ec78ca5 /home/m4rk/cyberflow/.venv/bin/python /home/m4rk/cyberflow /home/m4rk/cyberflow/scripts"
comprobar "U3 detecta código viejo si entra en sys.path (PARADA esperada)" \
  "! PYTHONPATH=/home/m4rk/cyberflow bash $I /home/m4rk/cyberflow-e4/ec78ca5 /home/m4rk/cyberflow/.venv/bin/python /home/m4rk/cyberflow /home/m4rk/cyberflow/scripts"
say "RESULTADO: $([ $fallo = 0 ] && echo 'todas las comprobaciones OK' || echo 'HAY FALLOS')"
exit $fallo
