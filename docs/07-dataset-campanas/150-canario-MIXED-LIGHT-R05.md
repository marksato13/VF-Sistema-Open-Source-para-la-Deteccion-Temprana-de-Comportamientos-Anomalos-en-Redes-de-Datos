# Vigésimo primero canario oficial R05 — MIXED-LIGHT

Fecha: 8 de agosto de 2026. Campaña `F1N-MIXED-LIGHT-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó el escenario mixto legítimo concurrente HTTP + TCP/iperf3 + DNS.
Commit `9ea07813a9519e8f748fb8f4e02ad3e51f99a182`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
El preflight pasó todos los gates y dejó la NIC externa desconectada.

## Evidencia

- HTTP 200, 104.857.600 bytes, 19.507908 s, 5.375.132 B/s.
- Iperf3 TCP completado durante 10 s a 50.007.669 bit/s, 62.521.344 bytes
  recibidos y tres retransmisiones; el transporte no mostró pérdida de captura.
- DNS: 20 respuestas legítimas.
- PCAP `123386/123386/123386` de 177.595.130 bytes, cero drops y sin alcanzar
  el límite de captura.
- Longitudes IPv4: 115.897 paquetes entre 500–1500 bytes (93.9304 %),
  115.389 exactamente a 1500, media 1.409,35 y máximo 1.500.
- EVE: 57 registros: 40 DNS, 1 HTTP, 1 fileinfo, 1 alert, 1 anomaly y 13
  stats. La alerta/anomaly pertenece a la política de observabilidad del
  escenario y se conserva, no se elimina.
- Tres ventanas elegibles del mismo episodio. La primera registra
  `flow_attempt_count_30s=23`, `syn_count_10s=3`,
  `syn_completion_ratio_10s=1.0` y `dns_query_count_60s=20`; los ratios pesados
  son `0.88253789`, `0.97498487` y `0.99474756`. Las tres ventanas tienen
  `unique_dst_ip_ratio_30s=0.04347826` y `dns_nxdomain_ratio_60s=0`.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`692f05856be8f2d118949e62039e4d1dab5ce2b4596ef9560a93bf1d86103b1e`, manifest
`31c4dba1831930c269a3a17bf1ed8b3d05af5d3f782b1db13318b624af58cc1b`, campaña
`e68e4bf565436f4949bda6c517edc72abfc6c0e52bfcb14a15cbee6c2eb62137`, features
`3c2c373b256ee949733f6d74c8b7c41882d31929d09f1606e81f3c7c0301a14c` y ledger
`2101e05dfd7a831108f46f259915af9e9ec4d85d68d0cfc9196f95b7e49cbb32`.

## Auditoría y límites

El auditor global queda en 137/145 campañas aceptadas, R05 23/29, 8 celdas
faltantes, 36 vectores duplicados, 19 cruces y cero campañas inválidas o
advertencias. Faltan `TCP-100M`, `TCP-200M`, `TCP-50M`, `TCP-REFUSED-5`,
`TLS-SESSIONS-20`, `UDP-10M`, `UDP-25M` y `UDP-50M`, todas R05.

Las tres filas pertenecen a un único episodio concurrente y están
autocorrelacionadas; no equivalen a tres escenarios independientes. La
campaña aporta simultáneamente señales L3 (destinos), L4 (SYN/completitud) y
L7 (HTTP/DNS), además de tráfico pesado legítimo. No se ejecutó scoring ni se
modificó el modelo. El siguiente paso es completar las ocho celdas R05
restantes con preflight independiente.
