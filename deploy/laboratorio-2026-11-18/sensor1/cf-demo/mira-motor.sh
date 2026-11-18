#!/bin/bash
# Decisiones del motor de CyberFlow en vivo. SOLO LECTURA.
# Uso: ~/cf-demo/mira-motor.sh [IP]     (sin IP: solo las ventanas que piden accion)
# Formato compacto para paneles estrechos: una linea por ventana con score.
IP=${1:-}
export TZ=America/Lima
printf '\033[1;36mMOTOR CyberFlow%s\033[0m · una línea por ventana\n' "${IP:+ · $IP}"
printf '\033[2mhora     acción  score  umbral  modelo   regla\033[0m\n'
tail -n 0 -F ~/cyberflow/logs/motor_decision.log 2>/dev/null | jq --unbuffered -r --arg ip "$IP" '
  select(.event == "decision")
  | select(($ip == "" and (.decision == "ALERT" or .heuristico != null)) or .entity_ip == $ip)
  | select(.score != null or .heuristico != null)
  | (if .heuristico then (if .heuristico.accion == "BLOCK" then "\u001b[1;41m BLOCK\u001b[0m" else "\u001b[1;43;30m LIMIT\u001b[0m" end)
     elif .decision == "ALERT" then "\u001b[1;43;30m LIMIT\u001b[0m" else "\u001b[32mPERMIT\u001b[0m" end) as $acc
  | [ (.logged_at | localtime | strftime("%H:%M:%S")),
      (if $ip == "" then .entity_ip else empty end),
      $acc,
      (if .score then ((.score * 100 | round) / 100 | tostring) else "  -  " end),
      ((.threshold * 100 | round) / 100 | tostring),
      (if .decision == "ALERT" then "\u001b[1;33mANÓMALO\u001b[0m" else "normal " end),
      (if .heuristico then "\u001b[1;31m" + .heuristico.heuristico + "\u001b[0m " + (.heuristico.motivo | .[0:38]) else "" end)
    ] | join(" ")'
