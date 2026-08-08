# Decimosexto canario oficial R05 — HTTP-MULTI-5

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-MULTI-5-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única campaña con cinco solicitudes secuenciales por cada VIP
lógica (`10.30.0.10`, `.11` y `.12`), quince solicitudes en total. Commit
`afe0fdf52b9aa109cc226f2f12b5675e6ec1e840`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e`.
El preflight pasó todos los gates.

## Evidencia

- Quince respuestas HTTP 200, cinco por VIP.
- PCAP `150/150/150` de 16.749 bytes, cero drops y sin límite.
- Todas las longitudes IPv4 fueron pequeñas: media 81,50 y máximo 251.
- EVE: 40 registros: 15 HTTP, 15 fileinfo y 10 stats.
- Una fila elegible con 15 intentos L4, `flow_attempt_rate_10s=1.5`,
  `unique_dst_ip_ratio_30s=0.2` y error HTTP cero.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`8eadfe087dc840871f696092304fc72f7c64d1ef8a883729bb747a66c6809087`, manifest
`e96cea179857d37fd3de8666552eb13212401810faa612dba8e949d62e958d97`, campaña
`447cda69d7c38a80cb6eccc13bae78e3f663e0f079a1591c0da7b6b760839bc4`, features
`750d235c5a3511e2e28c49c0173c9ef9d93dbb439f87e3dc69b559e79133bae6` y ledger
`9cce7f17d6034291c088e2c572e957b8fccbf39820e50836725db15d38ca4d4e`.

## Auditoría y límites

El auditor global queda en 132/145 campañas aceptadas, R05 18/29, 11 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. La celda aporta repetición multi-destino ligera, no tráfico
pesado. No se ejecutó scoring ni se modificó el modelo. Siguiente paso:
documentar/publicar y continuar con el próximo preflight R05.
