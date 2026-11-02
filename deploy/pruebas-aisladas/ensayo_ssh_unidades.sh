#!/bin/bash
# Ensayo del procedimiento de instalacion (cierre de la Etapa 2, punto 8) en el banco :3.
#
# SOLO en el contenedor cyberflow-etapa2-banco:3 con --network none, como root. Reproduce
# en un unico host (127.0.0.1) las cuentas, rutas, permisos, llaves con comando forzado,
# sudoers y unidades del procedimiento revisado, y comprueba:
#   S1  transporte SSH real del rele: servir (sensor) y recibir en dos fases (destino)
#   S2  una cuenta con shell nologin NO puede usar el comando forzado (por eso cffeed)
#   S3  el comando forzado rechaza cualquier otra orden (id, cat /etc/shadow, rm)
#   S4  permisos: feed 0640 cffeed:cfagente; cfagente lee pero no modifica ni el feed,
#       ni el codigo de /opt, ni la clave publica, ni el perfil del helper
#   S5  agente bajo cfagente con python3 -I desde /opt: importa feed.py co-desplegado y
#       acepta la pareja entregada (SOMBRA: sin --aplicar)
#   S6  sudoers: visudo -cf; cfagente ejecuta el helper SIN argumentos; con argumentos,
#       otro binario o nft directo, sudo lo niega
#   S7  perfil fijo: con /etc/cyberflow/nft-helper.perfil = dns, una peticion dmz se rechaza
#   S8  systemd-analyze verify de las cinco unidades candidatas
# Sale con 0 solo si todo pasa; escribe el detalle en /out/ensayo-ssh-unidades.json.
set -u
REPO=${REPO:-/w}
OUT=${OUT:-/out}
mkdir -p "$OUT"
declare -A R
pasa() { R[$1]="PASA"; echo "PASA $1 ${2:-}"; }
falla() { R[$1]="FALLA: ${2:-}"; echo "FALLA $1 ${2:-}"; }

# --- cuentas -------------------------------------------------------------------
useradd -m -s /bin/bash m4rk
useradd -m -s /bin/bash gadmin
useradd -r -m -d /var/lib/cyberflow/cffeed-home -s /bin/sh cffeed && passwd -l cffeed >/dev/null
useradd -r -M -d /nonexistent -s /usr/sbin/nologin cfagente
useradd -r -m -d /home/cfnologin -s /usr/sbin/nologin cfnologin      # contraejemplo de S2
usermod -aG cfagente cffeed

# --- rutas del procedimiento -----------------------------------------------------
install -d -o root -g root -m 0755 /opt/cyberflow/agente-v2 /opt/cyberflow/relay-v2 /etc/cyberflow
install -d -o root -g root -m 0755 /var/lib/cyberflow
install -d -o cffeed -g cfagente -m 2750 /var/lib/cyberflow/feed
install -d -o cfagente -g cfagente -m 0700 /var/lib/cyberflow/agente
install -d -o cfnologin -g cfnologin -m 0750 /home/cfnologin/feed
install -o root -g root -m 0644 "$REPO/scripts/enforce/agente_enforce_v2.py" "$REPO/scripts/engine/feed.py" /opt/cyberflow/agente-v2/
install -o root -g root -m 0644 "$REPO/deploy/enforcement/relay_eventos.py" "$REPO/scripts/engine/feed.py" /opt/cyberflow/relay-v2/
install -o root -g root -m 0755 "$REPO/deploy/enforcement/candidato-etapa2/cf-feed-ssh.sh" /usr/local/bin/cf-feed-ssh.sh
install -o root -g root -m 0755 "$REPO/scripts/enforce/cf_nft_helper.py" /usr/local/sbin/cf-nft-helper
echo dns > /etc/cyberflow/nft-helper.perfil && chown root:root /etc/cyberflow/nft-helper.perfil && chmod 0644 /etc/cyberflow/nft-helper.perfil
install -o root -g root -m 0440 "$REPO/deploy/enforcement/candidato-etapa2/cf-nft-helper.sudoers" /etc/sudoers.d/cf-nft-helper

# --- claves del feed (sensor) y feed v2 firmado --------------------------------------
install -d -o m4rk -g m4rk -m 0700 /home/m4rk/feed-v2
python3 - "$REPO" <<'PY'
import sys, time, json
sys.path.insert(0, sys.argv[1] + "/scripts/engine")
import feed
feed.generar_claves("/home/m4rk/priv.pem", "/home/m4rk/feed-v2/pub.pem")
ahora = time.time()
e = {"ip": "10.10.20.30", "destino": "dc1", "alcance": "dns", "accion": "LIMIT", "hasta": round(ahora + 600),
     "evento_id": "banco|ssh"}
e["id"] = feed.id_entrada(e["ip"], "dc1", "dns", "LIMIT", e["evento_id"])
d = feed.serializar(feed.construir_v2([e], 1, ahora, 300))
open("/home/m4rk/feed-v2/feed.json", "wb").write(d)
open("/home/m4rk/feed-v2/feed.sig", "wb").write(feed.firmar(d, "/home/m4rk/priv.pem"))
PY
chown -R m4rk:m4rk /home/m4rk
install -o root -g root -m 0644 /home/m4rk/feed-v2/pub.pem /opt/cyberflow/agente-v2/pub.pem
install -o root -g root -m 0644 /home/m4rk/feed-v2/pub.pem /opt/cyberflow/relay-v2/pub.pem

# --- llaves del rele (gadmin) con comando forzado -------------------------------------
su gadmin -c "mkdir -p ~/.ssh ~/relay-v2 && chmod 700 ~/.ssh && ssh-keygen -q -t ed25519 -N '' -f ~/.ssh/rele"
PUB=$(cat /home/gadmin/.ssh/rele.pub)
forzar() {  # usuario home modo dir
  install -d -o "$1" -g "$1" -m 0700 "$2/.ssh"
  echo "command=\"/usr/local/bin/cf-feed-ssh.sh $3 $4\",restrict $PUB" > "$2/.ssh/authorized_keys"
  chown "$1:$1" "$2/.ssh/authorized_keys"; chmod 0600 "$2/.ssh/authorized_keys"
}
forzar m4rk /home/m4rk servir /home/m4rk/feed-v2
forzar cffeed /var/lib/cyberflow/cffeed-home recibir /var/lib/cyberflow/feed
forzar cfnologin /home/cfnologin recibir /home/cfnologin/feed
/usr/sbin/sshd -o ListenAddress=127.0.0.1 -o PasswordAuthentication=no
sleep 1
su gadmin -c "ssh-keyscan -q -t ed25519 127.0.0.1 > ~/.ssh/known_hosts 2>/dev/null"

# --- S1: rele real por SSH ------------------------------------------------------------
su gadmin -c "python3 -I /opt/cyberflow/relay-v2/relay_eventos.py \
  --origen m4rk@127.0.0.1:/home/m4rk/feed-v2,/home/gadmin/.ssh/rele \
  --destino dc1=cffeed@127.0.0.1:/var/lib/cyberflow/feed,/home/gadmin/.ssh/rele \
  --destino nologin=cfnologin@127.0.0.1:/home/cfnologin/feed,/home/gadmin/.ssh/rele \
  --clave-publica /opt/cyberflow/relay-v2/pub.pem --traza /home/gadmin/relay-v2/traza.jsonl \
  --max-iteraciones 1" ; RC=$?
cp /home/gadmin/relay-v2/traza.jsonl "$OUT/traza-rele-ssh.jsonl" 2>/dev/null
if [ $RC -eq 0 ] && cmp -s /home/m4rk/feed-v2/feed.json /var/lib/cyberflow/feed/feed.json \
   && cmp -s /home/m4rk/feed-v2/feed.sig /var/lib/cyberflow/feed/feed.sig \
   && grep -q '"dc1": {"entregado_en"' /home/gadmin/relay-v2/traza.jsonl; then
  pasa S1_transporte_ssh_real "pareja identica en /var/lib/cyberflow/feed"
else falla S1_transporte_ssh_real "rc=$RC"; fi

# --- S2: nologin no sirve para el comando forzado -------------------------------------
if grep -q '"nologin": {"error"' /home/gadmin/relay-v2/traza.jsonl && [ ! -e /home/cfnologin/feed/feed.json ]; then
  pasa S2_nologin_no_admite_comando_forzado "$(grep -o '"nologin": {"error": "[^"]*' /home/gadmin/relay-v2/traza.jsonl | head -1)"
else falla S2_nologin_no_admite_comando_forzado "la cuenta nologin recibio el feed"; fi

# --- S3: el comando forzado rechaza otras ordenes ---------------------------------------
ok=1
for orden in "id" "cat /etc/shadow" "rm -f /var/lib/cyberflow/feed/feed.json" "cat > /var/lib/cyberflow/feed/../x" \
             "cat /var/lib/cyberflow/feed/feed.json; id"; do
  out=$(su gadmin -c "ssh -i ~/.ssh/rele -o BatchMode=yes cffeed@127.0.0.1 '$orden'" 2>&1 </dev/null); rc=$?
  [ $rc -ne 0 ] && echo "$out" | grep -q "orden no permitida" || ok=0
done
out=$(su gadmin -c "ssh -i ~/.ssh/rele -o BatchMode=yes m4rk@127.0.0.1 'cat /home/m4rk/priv.pem'" 2>&1 </dev/null)
echo "$out" | grep -q "orden no permitida" || ok=0
[ -f /var/lib/cyberflow/feed/feed.json ] || ok=0
[ $ok -eq 1 ] && pasa S3_comando_forzado_rechaza_otras "5 ordenes en cffeed + lectura de la clave privada en m4rk" \
  || falla S3_comando_forzado_rechaza_otras "alguna orden no fue rechazada"

# --- S4: permisos ------------------------------------------------------------------------
perm=$(stat -c '%a %U:%G' /var/lib/cyberflow/feed/feed.json)
ok=1
[ "$perm" = "640 cffeed:cfagente" ] || ok=0
runuser -u cfagente -- cat /var/lib/cyberflow/feed/feed.json >/dev/null 2>&1 || ok=0
for f in /var/lib/cyberflow/feed/feed.json /var/lib/cyberflow/feed/nuevo /opt/cyberflow/agente-v2/agente_enforce_v2.py \
         /opt/cyberflow/agente-v2/pub.pem /etc/cyberflow/nft-helper.perfil /usr/local/sbin/cf-nft-helper; do
  runuser -u cfagente -- sh -c "echo x >> $f" 2>/dev/null && ok=0
done
runuser -u cfagente -- mv /var/lib/cyberflow/feed/feed.json /var/lib/cyberflow/feed/otro 2>/dev/null && ok=0
[ $ok -eq 1 ] && pasa S4_permisos "feed $perm; cfagente lee y no modifica feed, codigo, clave ni perfil" \
  || falla S4_permisos "feed $perm"

# --- S5: agente bajo cfagente, python3 -I desde /opt, en sombra -----------------------------
res=$(cd / && runuser -u cfagente -- /usr/bin/python3 -I /opt/cyberflow/agente-v2/agente_enforce_v2.py --perfil dns \
  --feed /var/lib/cyberflow/feed/feed.json --firma /var/lib/cyberflow/feed/feed.sig \
  --clave-publica /opt/cyberflow/agente-v2/pub.pem --estado /var/lib/cyberflow/agente/estado.json \
  --traza /var/lib/cyberflow/agente/traza.jsonl --helper "sudo -n /usr/local/sbin/cf-nft-helper" 2>&1)
echo "$res" > "$OUT/agente-sombra.txt"
if echo "$res" | grep -q '"estado": "aceptado"' && ! nft list tables 2>/dev/null | grep -q cyberflow; then
  pasa S5_agente_python_I_en_sombra "$res"
else falla S5_agente_python_I_en_sombra "$res"; fi

# --- S6: sudoers --------------------------------------------------------------------------
ok=1
visudo -cf /etc/sudoers.d/cf-nft-helper >/dev/null || ok=0
r=$(echo '{"perfil":"dns","operaciones":[{"op":"listar"}]}' | runuser -u cfagente -- sudo -n /usr/local/sbin/cf-nft-helper 2>&1)
echo "$r" | grep -q '"ok": true' || ok=0
echo '{}' | runuser -u cfagente -- sudo -n /usr/local/sbin/cf-nft-helper --perfil dmz >/dev/null 2>&1 && ok=0
runuser -u cfagente -- sudo -n /usr/sbin/nft list ruleset >/dev/null 2>&1 && ok=0
runuser -u cffeed -- sudo -n /usr/local/sbin/cf-nft-helper </dev/null >/dev/null 2>&1 && ok=0
[ $ok -eq 1 ] && pasa S6_sudoers "solo el helper sin argumentos; cffeed sin sudo" || falla S6_sudoers "$r"

# --- S7: perfil fijo por host ----------------------------------------------------------------
r=$(echo '{"perfil":"dmz","operaciones":[{"op":"asegurar"}]}' | runuser -u cfagente -- sudo -n /usr/local/sbin/cf-nft-helper 2>&1)
if echo "$r" | grep -q perfil_no_autorizado && ! nft list tables | grep -q cyberflow_dmz; then
  pasa S7_perfil_fijo "$r"; else falla S7_perfil_fijo "$r"; fi

# --- S8: unidades --------------------------------------------------------------------------
# Se instalan como en el procedimiento (0644 root:root). ppi-publicar-feed-v2 usa el venv de
# Sensor1 (/home/m4rk/cyberflow/.venv), que no existe en el banco: se verifica aparte y su
# ExecStart queda como comprobacion PENDIENTE en el sensor (no se simula con un falso binario).
for u in "$REPO"/deploy/enforcement/candidato-etapa2/*.service; do install -o root -g root -m 0644 "$u" /etc/systemd/system/; done
v=$(cd /etc/systemd/system && systemd-analyze verify ppi-relay-eventos.service ppi-enforce-agent-v2-dmz.service      ppi-enforce-agent-v2-dns.service 2>&1 | grep -v -e "^$")
vp=$(cd /etc/systemd/system && systemd-analyze verify ppi-publicar-feed-v2.service 2>&1 | grep -v -e "^$")
printf '%s
--- ppi-publicar-feed-v2 ---
%s
' "$v" "$vp" > "$OUT/systemd-analyze.txt"
otros=$(echo "$vp" | grep -v "/home/m4rk/cyberflow/.venv/bin/python is not executable")
if [ -z "$v" ] && [ -z "$otros" ]; then
  pasa S8_systemd_analyze "rele y agentes sin ningun aviso; publicador: solo falta el venv de Sensor1 (pendiente en vivo)"
else falla S8_systemd_analyze "$(echo "$v $otros" | head -3)"; fi

# --- resumen ---------------------------------------------------------------------------
python3 - "$OUT/ensayo-ssh-unidades.json" <<PY
import json, sys
r = {$(for k in "${!R[@]}"; do printf '"%s": "%s", ' "$k" "${R[$k]//\"/\'}"; done)}
json.dump({"casos": dict(sorted(r.items())), "pasa": all(v == "PASA" for v in r.values())},
          open(sys.argv[1], "w"), indent=1)
print(json.dumps(r, indent=1, sort_keys=True))
PY
for k in "${!R[@]}"; do [ "${R[$k]}" = "PASA" ] || exit 1; done
exit 0
