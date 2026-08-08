# Decimoséptimo canario oficial R05 — HTTPS-10MB

Fecha: 8 de agosto de 2026. Campaña `F1N-HTTPS-10MB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única transferencia HTTPS legítima de 10 MB a 2M. Commit
`04d0320d22757cde1c9106c3d66cad7565acb3b7`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a`.
El preflight pasó todos los gates.

## Evidencia

- HTTPS 200, 10.485.760 bytes, 4.530441 s, 2.314.511 B/s.
- PCAP `8783/8783/8783` de 11.225.598 bytes, cero drops y sin límite.
- Longitudes IPv4: 7.255 paquetes entre 500–1500 bytes (82.6028 %),
  7.252 exactamente a 1500, media 1.248,10 y máximo 1.500.
- EVE: 11 registros, TLS 1.3 y 10 stats; no aparecen HTTP/fileinfo porque el
  contenido está cifrado.
- Dos ventanas elegibles con ratios pesados `0.65206246` y `0.99220837`.
  La tasa de sesiones TLS es `0.01666667` por ventana de 60 s.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`e3659bdf8e41e96add17c14e644c763bf99c4ece5acc99cfee3cca4b0a45d342`, manifest
`d3841f33a6a695445d243381845f7b363c74a00395639a1a711873d13d86669b`, campaña
`940065a2122e2e6863d914e97888d1d0bbf04b06627c3d606182cc940c581007`, features
`daed3bfa06e10d244e235c33a5afa762a425bd808a2ad551b418df4d038adae7` y ledger
`2b20c5e1ad3d2b998b0dedf7c957b53eba45bab338749d1fc3110bec3ca74c42`.

## Auditoría y límites

El auditor global queda en 133/145 campañas aceptadas, R05 19/29, 10 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. La opacidad HTTP es esperada por TLS; no se interpreta como
ausencia de aplicación. No se ejecutó scoring ni se modificó el modelo.

Siguiente paso: documentar/publicar y continuar con el próximo preflight R05.
