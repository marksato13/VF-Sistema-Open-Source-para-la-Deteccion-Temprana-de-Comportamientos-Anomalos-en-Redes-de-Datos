# Kali como generador de anomalías controladas v2

Kali (VM04, `10.10.10.40`) se utiliza sólo para evaluación ciega y nunca para
contaminar las campañas normales. Las herramientas disponibles fueron
verificadas: `nmap`, `nping`, `hping3`, `curl`, `dig`, `jq`, `python3` y
`openssl`. El playbook `09-configurar-kali-herramientas-v2.yml` permite
reinstalarlas de forma reproducible si fuese necesario.

El runner `scripts/kali/run-anomaly-v2.sh` sólo admite destinos `10.30.0.10`,
`.11` y `.12`, y limita los puertos a los servicios del laboratorio. Sus tres
escenarios son:

- `tcp-syn-rate`: ráfaga SYN controlada para L4.
- `tcp-port-scan`: sondeo limitado de puertos 80, 443 y 65000 para L4.
- `udp-probe`: sondeo UDP limitado al puerto DNS 53 para L4/L7.

No se ejecutaron estos escenarios todavía. Cada ejecución oficial deberá usar
un `campaign_id` de la matriz de anomalías, conservar PCAP/EVE, registrar el
comando y quedar fuera de train/validation. No se autoriza usar el runner
contra Internet, terceros ni rangos no declarados.
