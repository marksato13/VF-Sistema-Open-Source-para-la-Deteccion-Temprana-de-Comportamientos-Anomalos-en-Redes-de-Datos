#!/usr/bin/env bash
# Ensayo de banco (Etapa 4): estado_sombra.py con PROCESOS REALES de Linux. SOLO en el banco Docker.
#
#   docker run --rm --network none -v "<repo>:/src:ro" -v "<salida>:/out" cyberflow-etapa3-banco:1 \
#     bash /src/deploy/etapa4/banco/ensayo_estado_sombra.sh
#
# Agentes falsos (scripts llamados agente_enforce.py / agente_enforce_v2.py que solo duermen) y systemctl/sudo/nft
# falsos (no hay systemd en el contenedor). La comprobación se lanza como la lanzaría ssh: sshd ejecuta
# «$SHELL -c '<orden remota>'», y la orden remota lleva las palabras agente_enforce y --aplicar (como g01).
#   S1  sombra: v2 sin --aplicar + la comprobación por "SSH" -> rc 0; el patrón antiguo (pgrep|grep) da >= 1
#   S2  agente v1 real con --aplicar lanzado con sh -c -> rc 1, y lo ve aunque vaya envuelto
#   S3  agente v2 con --aplicar=si -> rc 1
#   S4  sudo -n falla (contraseña) -> rc 2 desconocido, no 0
#   S5  nft falla -> rc 2;  S6 traza ausente -> rc 2;  S7 systemctl falla -> rc 2
#   S8  tabla cyberflow_dmz -> rc 1;  S9 evento aplicacion en la traza -> rc 1
#   S10 SSH REAL a localhost (solo si el banco tiene sshd y ssh): mismo resultado que S1
# No toca nada fuera del contenedor. Salida: /out/ensayo-estado-sombra.txt
set -u
OUT=/out; SRC=/src; LOG="$OUT/ensayo-estado-sombra.txt"
mkdir -p "$OUT"; : > "$LOG"
say() { printf '%s %s\n' "$(date -u +%FT%T.%3NZ)" "$*" | tee -a "$LOG"; }
fallo=0
espera() {   # $1 nombre, $2 rc esperado, $3 rc obtenido
  if [ "$3" = "$2" ]; then say "OK    $1 (rc=$3)"; else say "FALLO $1 (rc=$3, se esperaba $2)"; fallo=1; fi; }
[ -f /.dockerenv ] || { echo "solo dentro del contenedor del banco"; exit 2; }
ES="$SRC/deploy/etapa4/srvdmz/estado_sombra.py"
say "python: $(python3 --version 2>&1); estado_sombra: $(grep -m1 '^VERSION' "$ES")"

F=/tmp/falsos; mkdir -p "$F" /tmp/opt/agente-v2 /tmp/enforce
# agentes falsos: mismo nombre de fichero que los reales, solo duermen
for s in /tmp/opt/agente-v2/agente_enforce_v2.py /tmp/enforce/agente_enforce.py; do
  printf 'import time\nwhile True:\n    time.sleep(1)\n' > "$s"
done
cat > "$F/falso.py" <<'EOF'
import json, os, subprocess, sys
kind, args = sys.argv[1], sys.argv[2:]
cfg = json.load(open(os.environ.get("CFG", "/tmp/falsos/cfg.json")))
if kind == "systemctl":
    if cfg.get("systemctl_rc"):
        sys.stderr.write("Failed to connect to bus\n"); sys.exit(cfg["systemctl_rc"])
    s = cfg["unidades"][args[1]]
    print(f"ActiveState={s[0]}\nUnitFileState={s[1]}\nLoadState=loaded\nExecStart={s[2]}")
elif kind == "sudo":
    if cfg.get("sudo_falla"):
        sys.stderr.write("sudo: a password is required\n"); sys.exit(1)
    if args[0] == "cat":
        if cfg.get("traza") is None:
            sys.stderr.write("cat: No such file or directory\n"); sys.exit(1)
        sys.stdout.write(cfg["traza"]); sys.exit(0)
    sys.exit(subprocess.run(args).returncode)
elif kind == "nft":
    if cfg.get("nft_rc"):
        sys.stderr.write("netlink: Error: Operation not permitted\n"); sys.exit(cfg["nft_rc"])
    print("\n".join(cfg.get("tablas", [])))
EOF
EXEC_V2="{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 -I /opt/cyberflow/agente-v2/agente_enforce_v2.py --perfil dmz --seguir ; }"
EXEC_V1="{ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 /home/adminsrvdmz/enforce/agente_enforce.py --aplicar --sudo ; }"
cfg() {   # $1 = fragmento JSON que se mezcla con el sano
  python3 - "$1" > "$F/cfg.json" <<EOF
import json, sys
base = {"unidades": {"ppi-enforce-agent.timer": ["inactive", "disabled", ""],
                     "ppi-enforce-agent.service": ["inactive", "static", "$EXEC_V1"],
                     "ppi-enforce-agent-v2-dmz.service": ["active", "enabled", "$EXEC_V2"]},
        "tablas": ["table inet filter", "table ip nat"],
        "traza": '{"evento": "recepcion", "estado": "aceptado"}\n'}
base.update(json.loads(sys.argv[1] or "{}"))
print(json.dumps(base))
EOF
}
FALSOS="--systemctl 'python3 $F/falso.py systemctl' --sudo 'python3 $F/falso.py sudo' --nft 'python3 $F/falso.py nft'"
# orden remota como la de g01: contiene «agente_enforce» y «--aplicar» en su texto
REMOTA="echo comprobacion agente_enforce --aplicar; python3 -I $ES --alcance completo $FALSOS"
por_ssh() {   # sshd -> $SHELL -c "<orden remota>": el bash -c queda vivo como padre del python
  bash -c "$REMOTA; rc=\$?; echo rc_remoto=\$rc; exit \$rc" >> "$LOG" 2>&1; }
antiguo() { pgrep -af agente_enforce | grep -c -- --aplicar; }

python3 -I /tmp/opt/agente-v2/agente_enforce_v2.py --perfil dmz --feed /x --seguir & V2=$!
sleep 0.5

# S1 sombra + patrón antiguo
cfg '{}'
# el patrón antiguo, ejecutado DENTRO de un bash -c con las mismas palabras (como g01)
n_ant=$(bash -c "echo agente_enforce --aplicar >/dev/null; pgrep -af agente_enforce | grep -c -- --aplicar")
say "S1 patrón antiguo (pgrep -af | grep -c --aplicar dentro de bash -c) = $n_ant con 0 agentes aplicando"
[ "${n_ant:-0}" -ge 1 ] && say "OK    S1 regresión reproducida: el patrón antiguo se contaba a sí mismo" \
                      || { say "FALLO S1 no se reprodujo el falso positivo antiguo"; fallo=1; }
por_ssh; espera "S1 sombra con la comprobación por SSH simulado" 0 $?

# S2 agente v1 real con --aplicar envuelto en sh -c
sh -c "python3 /tmp/enforce/agente_enforce.py --aplicar --sudo; true" & SH=$!
sleep 0.5
por_ssh; espera "S2 agente v1 real con --aplicar bajo sh -c" 1 $?
pkill -f '/tmp/enforce/agente_enforce.py' ; wait "$SH" 2>/dev/null

# S3 v2 con --aplicar=si
python3 -I /tmp/opt/agente-v2/agente_enforce_v2.py --perfil dmz --aplicar=si & V2B=$!
sleep 0.5
por_ssh; espera "S3 agente v2 con --aplicar=si" 1 $?
kill "$V2B"; wait "$V2B" 2>/dev/null

cfg '{"sudo_falla": true}';  por_ssh; espera "S4 sudo -n falla: desconocido, no cero" 2 $?
cfg '{"nft_rc": 1}';         por_ssh; espera "S5 nft falla: desconocido" 2 $?
cfg '{"traza": null}';       por_ssh; espera "S6 traza ausente: desconocido" 2 $?
cfg '{"systemctl_rc": 1}';   por_ssh; espera "S7 systemctl falla: desconocido" 2 $?
cfg '{"tablas": ["table inet filter", "table inet cyberflow_dmz"]}'
por_ssh; espera "S8 tabla cyberflow_dmz" 1 $?
cfg '{"traza": "{\"evento\": \"aplicacion\", \"ip\": \"10.10.20.30\"}\n"}'
por_ssh; espera "S9 evento aplicacion en la traza" 1 $?

# S10 SSH real, solo si el banco lo permite (no se instala nada)
cfg '{}'
if command -v sshd >/dev/null && command -v ssh >/dev/null; then
  mkdir -p /run/sshd /root/.ssh; ssh-keygen -q -t ed25519 -N '' -f /tmp/k >/dev/null
  cat /tmp/k.pub >> /root/.ssh/authorized_keys; ssh-keygen -q -A
  /usr/sbin/sshd -p 2222 -o ListenAddress=127.0.0.1 -o PermitRootLogin=prohibit-password
  sleep 0.5
  ssh -p 2222 -i /tmp/k -o StrictHostKeyChecking=no -o BatchMode=yes root@127.0.0.1 "$REMOTA" >> "$LOG" 2>&1
  espera "S10 SSH real a localhost" 0 $?
else
  say "S10 NO EJECUTABLE: el banco no tiene sshd/ssh; la invocación SSH se cubre con S1–S9 (\$SHELL -c, como sshd)"
fi
kill "$V2" 2>/dev/null
say "RESULTADO: $([ $fallo = 0 ] && echo 'todas las comprobaciones OK' || echo 'HAY FALLOS')"
exit $fallo
