# Vigésimo noveno canario oficial R05 — UDP-50M

Fecha: 9 de agosto de 2026. Campaña `F1N-UDP-50M-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una transferencia UDP legítima de techo con iperf3 a 50M durante
20 s. Commit `c27a3fd77356ee8f321ae2699cc9d94f9c274774`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f`.
El preflight pasó todos los gates.

## Evidencia

- Iperf3 UDP: 125.007.288 bytes enviados y recibidos, ~20.0016 s,
  49.998853/49.997256 Mbit/s, 86.331 datagramas, pérdida 0 %, jitter del
  receptor 0,0796 ms y cero paquetes fuera de orden.
- PCAP `86362/86362/86362` de 130.017.874 bytes, cero drops, cero inválidos y
  sin alcanzar el límite de 140 MB.
- Longitudes IPv4: 86.331 paquetes entre 500–1500 bytes (99.9641 %), media
  1.475,50 y máximo 1.476 bytes.
- EVE: 12 registros stats.
- Tres ventanas elegibles; ratios pesados `0.99938959`, `1.00000000` y
  `0.99908795`. La ventana central reproduce exactamente un vector de
  `UDP-50M-R03` y se conserva como cruce explícito, no como nueva diversidad.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`28545a12ab23e0df497a30e977b5277d749f419390c2b70528cc9ee44ca3404a`, manifest
`a8a6212080bf03802a01b7e2e9547588f4db78db9a7ad37d9d0429d081f3ae59`, campaña
`06fa940211f12eda46b4fb4478a2184430e8efd9137f6397124e45c5e4d09295`, features
`7a2b26d176d72b09d1fc4ff61e71bae623c482bd252517c361e5976fb022badb` y ledger
`89e848eba80946a45819556e04735f924aade2c3da6623e1a3de7c2a82c75cd3`.

## Auditoría y límites

El auditor global queda en 145/145 campañas aceptadas, R05 29/29, cero celdas
faltantes, 41 vectores duplicados, 24 cruces y cero campañas inválidas o
advertencias. El dataset está **listo para construir**, pero el cruce exacto
UDP R03↔R05 y las ventanas autocorrelacionadas deben quedar excluidos de una
estimación ingenua de independencia. No se ejecutó scoring ni se modificó el
modelo.
