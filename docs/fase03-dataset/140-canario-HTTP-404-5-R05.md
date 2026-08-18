# Undécimo canario oficial R05 — HTTP-404-5

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-404-5-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única captura de cinco solicitudes a rutas inexistentes. Commit
`974d52aee761f2965c1683122c30375a27495557`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`, argumentos
`5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e`. El
preflight continuo pasó todos los gates.

## Evidencia

- Cinco solicitudes HTTP, todas `404`.
- PCAP `50/50/50` de 6.309 bytes, cero drops y sin límite alcanzado.
- EVE: 20 registros: 5 `http`, 5 `fileinfo` y 10 `stats`; sin decoder inválido
  ni overflow.
- Todas las longitudes IPv4 son pequeñas: media 95,70, máximo 378 y 0 % en
  500–1500 bytes. Esto es esperado para respuestas de error cortas.
- Una fila elegible con 50 paquetes, 5 SYN, ratio de completitud 1.0,
  `http_error_ratio_60s=1.0` y `unique_dst_port_ratio_30s=0.2`.
- Recursos: 53 muestras del Sensor; el bundle conserva la serie y sus hashes.

Hashes principales: preflight
`1b36ea544f486021ca40675cbbba6d8e82bafdf7eb836ba93ec9bedb72545060`, manifest
`60eb787aeabc41514643df8972ff867fceb0c273d58b0134ae7f29c084346acf`, campaña
`2b592e26e9281520b79292bfeb62739f124e9eaad053160387324064dd13bdae`, features
`51f3731169625853c37216edcb1b09fc1afe1901bcc164a17a83f865b690665c` y ledger
`4a153ae4e6e60a41d8c19de20a7456fc1553760b64e06494766b56ec7ecde310`.
Los bundles pasaron `sha256sum -c SHA256SUMS`.

## Auditoría y límites

El auditor global queda en 127/145 campañas aceptadas, R05 11/29, 18 celdas
faltantes, 33 vectores duplicados, 16 cruces entre particiones y cero campañas
inválidas o advertencias. La etiqueta es error legítimo controlado, no ataque;
esta celda aporta cobertura L4/L7 y no tráfico pesado. No se ejecutó scoring ni
se modificó el modelo. Siguiente paso: documentar/publicar y continuar con el
próximo preflight R05.
