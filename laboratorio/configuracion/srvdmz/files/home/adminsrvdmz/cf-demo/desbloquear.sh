#!/bin/bash
# Liberación humana: retira la IP del firewall de este host. Durante la gracia (120 s por
# defecto) se absorbe la cola del mismo episodio; después, una ofensa nueva vuelve a aplicarse.
# Uso: ~/cf-demo/desbloquear.sh 10.10.20.30 [gracia_s]
IP=${1:?Uso: desbloquear.sh IP [gracia_s]}
GRACIA=${2:-120}
cd ~/enforce || exit 1
echo "antes de liberar : $IP en el firewall = $(~/cf-demo/en-firewall.sh "$IP")"
python3 agente_enforce.py --feed feed.json --firma feed.sig --clave-publica pub.pem \
  --aplicar --sudo --liberar "$IP" --gracia "$GRACIA"
echo "tras liberar     : $IP en el firewall = $(~/cf-demo/en-firewall.sh "$IP")"
