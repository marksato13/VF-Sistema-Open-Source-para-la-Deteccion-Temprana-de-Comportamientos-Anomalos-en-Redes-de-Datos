# Vigésimo segundo canario oficial R05 — TCP-50M

Fecha: 8 de agosto de 2026. Campaña `F1N-TCP-50M-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una transferencia TCP legítima con iperf3 a 50M durante 20 s.
Commit `6f10f5d55cbd642543d9eb5e7b724ffedf233d42`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f`.
El preflight pasó todos los gates.

## Evidencia

- Iperf3 TCP: 125.042.688 bytes enviados y recibidos, 20.001628 s,
  50.013004 Mbit/s enviados y 50.011659 Mbit/s recibidos; tres
  retransmisiones TCP reportadas por el emisor.
- PCAP `91882/91882/91882` de 132.580.591 bytes, cero drops, cero paquetes
  inválidos y sin alcanzar el límite de captura.
- Longitudes IPv4: 86.817 paquetes entre 500–1500 bytes (94.4875 %), 85.860
  exactamente a 1500, media 1.412,94 y máximo 1.500.
- EVE: 15 registros (13 stats, 1 alert y 1 anomaly). La alerta/anomaly se
  conserva para trazabilidad de la política de observabilidad.
- Tres ventanas elegibles del mismo episodio: la primera registra dos SYN,
  `syn_completion_ratio_10s=1.0`, `flow_attempt_rate_10s=0.2` y
  `unique_dst_ip_ratio_30s=0.5`; ratios pesados `0.88851411`, `0.95444251` y
  `0.95056212`.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`518bee216f12c4f1a759437e86f81f38c661b3b695e759919ba43b8911080ff6`, manifest
`5c3e642aa7ec73b5606cf14fc5e35160fae01dcb167db3c8acfb7c57a2f646d3`, campaña
`9c58869cc50798c63b80708b29836963038e9480630d4fa71bd71bdcb60a85ab`, features
`9988541445d1726a2585013810690e1a8ca2ae0e9fd0dfe594de8ec7387de975` y ledger
`b8dc6b6c009531c9730274f2ee94014c96484825bfd82a180031c93b2f6fc39b`.

## Auditoría y límites

El auditor global queda en 138/145 campañas aceptadas, R05 24/29, 7 celdas
faltantes, 36 vectores duplicados, 19 cruces y cero campañas inválidas o
advertencias. Faltan `TCP-100M`, `TCP-200M`, `TCP-REFUSED-5`,
`TLS-SESSIONS-20`, `UDP-10M`, `UDP-25M` y `UDP-50M`, todas R05.

Las tres filas son ventanas autocorrelacionadas de una sola transferencia y no
representan tres episodios independientes. Las retransmisiones de iperf3 no
son drops del sensor: los contadores de captura permanecieron en cero. No se
ejecutó scoring ni se modificó el modelo. El siguiente paso es completar las
siete celdas R05 restantes con preflight independiente.
