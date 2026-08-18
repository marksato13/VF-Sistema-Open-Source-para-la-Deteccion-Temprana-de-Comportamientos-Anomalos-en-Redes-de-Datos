# Vigésimo octavo canario oficial R05 — UDP-25M

Fecha: 8 de agosto de 2026. Campaña `F1N-UDP-25M-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una transferencia UDP legítima con iperf3 a 25M durante 20 s.
Commit `c7ddab8ff80bcd7159b74c1bbdda62856ef6dc2b`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `13602f7b87f04df16d76256c0103ad6ff1679f754cd54e9c6ed2871df05656d6`.
El preflight pasó todos los gates.

## Evidencia

- Iperf3 UDP: 62.504.368 bytes enviados y recibidos, ~20.0015 s,
  24.999841/24.999181 Mbit/s, 43.166 datagramas, pérdida 0 %, jitter del
  receptor 0,0520 ms y sin reordenamiento.
- PCAP `43194/43194/43194` de 65.011.135 bytes, cero drops, cero inválidos y
  sin alcanzar el límite de captura.
- Longitudes IPv4: 43.166 paquetes entre 500–1500 bytes (99.9352 %), media
  1.475,10 y máximo 1.476 bytes.
- EVE: 12 registros stats.
- Tres ventanas elegibles; ratios pesados `0.99895869`, `1.00000000` y
  `0.99819620`. La ventana principal registra 21.582 paquetes por 10 s;
  completitud SYN no aplica al flujo UDP.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`a70ef74fe5f0399e97e87dbc27d4ef376a567a9481ea2e1c7a7f64743ec52f54`, manifest
`23d987da7ea22b1cea496981062e993bfdd67f70f86d2ba3032e08526bb509e6`, campaña
`f5cd7620466b5cab4cb82ea118a6f7a6104dd64005160374810923059c74ab2b`, features
`ee34d17794247793a69f23c434de35a6cb9ffa434d27113b332858539d2edeee` y ledger
`05b6d56cac5d32003ddb82da30915369c67838258a957e4087b8792ea87fee9a`.

## Auditoría y límites

El auditor global queda en 144/145 campañas aceptadas, R05 29/29, 1 celda
faltante, 37 vectores duplicados, 20 cruces y cero campañas inválidas o
advertencias. Falta únicamente `UDP-50M/R05`. La pérdida UDP se reporta
separada de los drops del sensor, que permanecieron en cero. No se ejecutó
scoring ni se modificó el modelo.
