# Vigésimo séptimo canario oficial R05 — UDP-10M

Fecha: 8 de agosto de 2026. Campaña `F1N-UDP-10M-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una transferencia UDP legítima con iperf3 a 10M durante 20 s.
Commit `59a77ecf7f72a7ed3c142f5d88e1b5cce443df8e`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `f13202e70b2d4d581dbb998885e48b1de6e7980d54a8aae59e0d57b9c630a1ae`.
El preflight pasó todos los gates.

## Evidencia

- Iperf3 UDP: 25.002.616 bytes enviados y recibidos, ~20.001982 s,
  10.000055/9.999728 Mbit/s, 17.267 datagramas, pérdida 0 %, jitter del
  receptor 0,3366 ms y sin reordenamiento reportado.
- PCAP `17296/17296/17296` de 26.007.321 bytes, cero drops, cero inválidos y
  sin alcanzar el límite de captura.
- Longitudes IPv4: 17.267 paquetes entre 500–1500 bytes (99.8323 %), media
  1.473,66 y máximo 1.476 bytes.
- EVE: 12 registros stats.
- Tres ventanas elegibles; ratios pesados `0.99127590`, `1.00000000` y
  `0.99809635`. La ventana principal registra 8.633 paquetes por 10 s y
  completitud SYN 0 porque el flujo es UDP.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`4a61ea3cd6369bb00e901aa0c0a6531736d858a09a53b4cf8abb485eb6fad11f`, manifest
`c8e720e8060591cadbd3862e54bcffd5fc78fa02ed28f732d2ea717e84e9178e`, campaña
`9ef8844ad170ad49e6c5fe808638130c385321722790742abf8db3aca5958f3b`, features
`f60ab46ad02eaa9fc2723e1dae039c7c550f11ef5a0aefac164ff29e6e647f35` y ledger
`4ad760c883edf8157de0cb21d89e61687928ac30df86c18185df6cd04c04e33e`.

## Auditoría y límites

El auditor global queda en 143/145 campañas aceptadas, R05 29/29, 2 celdas
faltantes, 37 vectores duplicados, 20 cruces y cero campañas inválidas o
advertencias. Faltan `UDP-25M` y `UDP-50M`, ambas R05. La pérdida UDP de 0 %
se reporta separada de los drops del sensor, que también fueron cero. No se
ejecutó scoring ni se modificó el modelo.
