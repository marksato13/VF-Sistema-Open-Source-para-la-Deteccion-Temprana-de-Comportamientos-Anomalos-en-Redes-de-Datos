#!/usr/bin/env bash
# Orquestador de la bateria: 3 familias x 3 repeticiones.
# Por episodio: reloj del sensor -> ataque (Kali) -> reloj del sensor ->
# proc.sh (CyberFlow) + suri.sh (Suricata dedup). Resultado a CSV, append por
# episodio (si muere, lo hecho queda). Corre en el BASTION.
set -uo pipefail
SK="-n -i $HOME/.ssh/cyberflow-to-atacante adminatacante@10.10.20.30"
SS="-n -i $HOME/.ssh/cyberflow-to-sensor m4rk@10.10.60.11"
SC="-n -i $HOME/.ssh/id_ed25519 adminsuricata@10.10.60.13"
OUT=$HOME/orq_results.csv
echo "fam,rep,resultado_cyberflow,resultado_suricata" > "$OUT"
for fam in e3 e4 e1; do
  for rep in 1 2 3; do
    ID="${fam}-r${rep}"
    Tsf=$(ssh $SS date -u +%s)
    case $fam in
      e3) ssh $SK "fin=\$((SECONDS+90)); while [ \$SECONDS -lt \$fin ]; do dig +time=1 +tries=1 @10.10.10.20 \"\$(openssl rand -hex 8).noexiste\" +short >/dev/null 2>&1; sleep 0.4; done" >/dev/null 2>&1 ;;
      e4) ssh $SK "fin=\$((SECONDS+90)); while [ \$SECONDS -lt \$fin ]; do curl -s -o /dev/null --max-time 2 http://10.10.30.10/; done" >/dev/null 2>&1 ;;
      e1) ssh $SK "nmap -sT -T4 --max-retries 1 -p 1-1000 10.10.30.10 >/dev/null 2>&1" >/dev/null 2>&1 ;;
    esac
    Tef=$(ssh $SS date -u +%s)
    sleep 20
    LO=$(date -u -d @$((Tsf-20)) +%Y%m%d%H%M%S)
    HI=$(date -u -d @$((Tef+20)) +%Y%m%d%H%M%S)
    CS=$(date -u -d @$((Tsf-25)) +%Y-%m-%dT%H:%M:%SZ)
    HIISO=$(date -u -d @$((Tef+20)) +%Y-%m-%dT%H:%M:%SZ)
    T0=$(date -u -d @$Tsf +%Y-%m-%dT%H:%M:%SZ)
    RES=$(ssh $SS "bash /home/m4rk/piloto/proc.sh $ID $LO $HI $CS $T0 $HIISO" 2>/dev/null | grep RESULT || echo "RESULT $ID PROC_FAIL")
    scp -i $HOME/.ssh/cyberflow-to-sensor m4rk@10.10.60.11:/home/m4rk/piloto/$ID/dedup.pcap /tmp/$ID.pcap >/dev/null 2>&1
    scp -i $HOME/.ssh/id_ed25519 /tmp/$ID.pcap adminsuricata@10.10.60.13:/tmp/$ID.pcap >/dev/null 2>&1
    SURI=$(ssh $SC "bash /tmp/suri.sh /tmp/$ID.pcap $ID" 2>/dev/null | grep SURI || echo "SURI $ID NA")
    echo "$fam,$rep,[$RES],[$SURI]" >> "$OUT"
    echo "listo $ID"
  done
done
echo "ORQ_DONE" >> "$OUT"
