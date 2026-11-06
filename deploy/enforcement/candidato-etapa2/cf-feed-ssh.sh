#!/bin/sh
# Comando forzado para las llaves del rele v2 (authorized_keys). Instalar 0755 root:root
# en /usr/local/bin/cf-feed-ssh.sh.
#   Sensor1, cuenta m4rk (servir):
#     command="/usr/local/bin/cf-feed-ssh.sh servir /home/m4rk/feed-v2",restrict ssh-ed25519 AAAA... rele
#   srv-dmz y DC1, cuenta de TRANSPORTE cffeed (recibir):
#     command="/usr/local/bin/cf-feed-ssh.sh recibir /var/lib/cyberflow/feed",restrict ssh-ed25519 AAAA... rele
#
# sshd ejecuta el comando forzado con la SHELL de la cuenta ($SHELL -c ...): una cuenta
# con /usr/sbin/nologin NO puede usarlo. Por eso el transporte usa cffeed (shell
# /bin/sh, contrasena bloqueada, solo esta llave) y el agente usa cfagente (nologin, sin
# llaves). cffeed escribe en un directorio setgid del grupo cfagente; con umask 027 los
# ficheros quedan 0640 cffeed:cfagente: el agente los lee y no los puede modificar.
#
# Solo admite las ordenes exactas de relay_eventos.py sobre feed.json/feed.sig en el
# directorio fijado AQUI (no en la orden remota). Entrega en dos fases: subir los dos
# temporales y despues renombrar ambos en una sola orden. Cualquier otra cosa se rechaza.
set -eu
umask 027
modo="$1"; dir="$2"
case "$modo:${SSH_ORIGINAL_COMMAND:-}" in
  "servir:cat $dir/feed.json") exec cat "$dir/feed.json" ;;
  "servir:cat $dir/feed.sig")  exec cat "$dir/feed.sig" ;;
  "recibir:cat > $dir/.feed.json.tmp") exec cat > "$dir/.feed.json.tmp" ;;
  "recibir:cat > $dir/.feed.sig.tmp")  exec cat > "$dir/.feed.sig.tmp" ;;
  "recibir:mv -f $dir/.feed.sig.tmp $dir/feed.sig && mv -f $dir/.feed.json.tmp $dir/feed.json")
      mv -f "$dir/.feed.sig.tmp" "$dir/feed.sig" && exec mv -f "$dir/.feed.json.tmp" "$dir/feed.json" ;;
  # P4 (2026-11-06): paquete feed+firma en un fichero, publicado con UN rename (relay_eventos --entrega paquete)
  "recibir:cat > $dir/.feed.par.tmp") exec cat > "$dir/.feed.par.tmp" ;;
  "recibir:mv -f $dir/.feed.par.tmp $dir/feed.par") exec mv -f "$dir/.feed.par.tmp" "$dir/feed.par" ;;
  *) echo "orden no permitida" >&2; exit 1 ;;
esac
