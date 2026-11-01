#!/bin/sh
# Comando forzado para las llaves del rele v2 (authorized_keys):
#   command="/usr/local/bin/cf-feed-ssh.sh servir /home/m4rk/feed-v2",restrict ssh-ed25519 AAAA... rele
#   command="/usr/local/bin/cf-feed-ssh.sh recibir /home/adminsrvdmz/enforce-v2",restrict ssh-ed25519 AAAA... rele
# Solo admite las ordenes que emite relay_eventos.py sobre feed.json y feed.sig en el
# directorio fijado aqui (no en la orden remota). Cualquier otra cosa se rechaza.
set -eu
modo="$1"; dir="$2"
case "$modo:${SSH_ORIGINAL_COMMAND:-}" in
  "servir:cat $dir/feed.json") exec cat "$dir/feed.json" ;;
  "servir:cat $dir/feed.sig")  exec cat "$dir/feed.sig" ;;
  "recibir:cat > $dir/.feed.json.tmp && mv -f $dir/.feed.json.tmp $dir/feed.json")
      cat > "$dir/.feed.json.tmp" && exec mv -f "$dir/.feed.json.tmp" "$dir/feed.json" ;;
  "recibir:cat > $dir/.feed.sig.tmp && mv -f $dir/.feed.sig.tmp $dir/feed.sig")
      cat > "$dir/.feed.sig.tmp" && exec mv -f "$dir/.feed.sig.tmp" "$dir/feed.sig" ;;
  *) echo "orden no permitida" >&2; exit 1 ;;
esac
