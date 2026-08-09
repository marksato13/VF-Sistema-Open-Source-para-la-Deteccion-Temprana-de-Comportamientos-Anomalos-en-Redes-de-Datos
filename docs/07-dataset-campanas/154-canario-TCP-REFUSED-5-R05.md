# Vigésimo quinto canario oficial R05 — TCP-REFUSED-5

Fecha: 8 de agosto de 2026. Campaña `F1N-TCP-REFUSED-5-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutaron cinco intentos TCP legítimos contra un puerto rechazado.
Commit `c249f094f78f0b41d96d343a1a7ddac78394116c`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e`.
El preflight pasó todos los gates.

## Evidencia

- Escenario: `attempts=5`, `expected_refusals=5`.
- PCAP `10/10/10` de 824 bytes, cero drops, cero inválidos y sin alcanzar el
  límite de captura.
- Las diez tramas fueron pequeñas por diseño: 0 % entre 500–1500 bytes,
  media IPv4 50,00 y máximo 60 bytes.
- EVE: 10 registros `stats`; la ausencia de alertas no invalida el escenario,
  pues el objetivo es observar errores TCP legítimos, no generar una firma.
- Dos ventanas elegibles: la primera registra `flow_attempt_count_30s=1`,
  `syn_count_10s=1`, `syn_completion_ratio_10s=0`,
  `rst_ratio_10s=0.5`; la segunda registra cinco intentos, cuatro SYN,
  completitud 0 y `rst_ratio_10s=0.5`. Ratios pesados `0` y `0`.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`9d8fd32b34179b3fc85676ac5acb409028b3647c0837e26a3deeaa3d2a7c72fd`, manifest
`7a32c315e9b884382a81a390cfc517af0a64d69239522da0931c8c3c10e82e37`, campaña
`c679dc95387d63a9e840f20349873535a0e84835105a97402c438b1bcf72a80c`, features
`2636301c6b70354ed5f30b2a403e3a21634c85fd94abbd7ce0f525c944d9d81b` y ledger
`879d224e8a9a4036081ad7f710eedfe278e4a0e79cee5c1ad1a92a63269c6597`.

## Auditoría y límites

El auditor global queda en 141/145 campañas aceptadas, R05 27/29, 4 celdas
faltantes, 37 vectores duplicados, 20 cruces y cero campañas inválidas o
advertencias. Faltan `TLS-SESSIONS-20`, `UDP-10M`, `UDP-25M` y `UDP-50M`, todas
R05. El vector de esta campaña cruza con la repetición anterior del mismo
escenario; se conserva para trazabilidad y no se presenta como diversidad
independiente. No se ejecutó scoring ni se modificó el modelo.
