# Decimonoveno canario oficial R05 — HTTPS-500MB

Fecha: 8 de agosto de 2026. Campaña `F1N-HTTPS-500MB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única transferencia HTTPS legítima de 500 MB a 20M. Commit
`385b2fd5fc604d70eaa1d73560aac3e7fdbca188`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f`.
El preflight pasó todos los gates.

## Evidencia

- HTTPS 200, 524.288.000 bytes, 24.524318 s, 21.378.290 B/s.
- PCAP `372171/372171/372171` de 556.002.406 bytes, cero drops y sin límite.
- Longitudes IPv4: 362.918 paquetes entre 500–1500 bytes (97.5138 %),
  362.852 exactamente a 1500, media 1.463,94 y máximo 1.500.
- EVE: 18 registros, TLS y 17 stats; sin HTTP/fileinfo por cifrado.
- Tres ventanas elegibles con ratios pesados `0.95123205`, `0.98631825` y
  `0.98766135`; TLS session rate `0.01666667` en cada una.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`8f49683be88266204673c436f3d49161366f460291ed654dfc8d3732381901ca`, manifest
`6bb7e114e35d6e2db062d294df5834ea868d827ea8f3e84500f52f1803b04ad1`, campaña
`4875a048d59205671741bd4d18f621d584ad6633573e257e5cd35f1a11121b3e`, features
`fc94f94f8886dc5b4991591f91687263c9b87fc025ad95913ba74d0913c23ebd` y ledger
`6a04005ee42dc5a3f56a330f7019ebf8f32d44f6b4077d944fe334a00368e3d0`.

## Auditoría y límites

El auditor global queda en 135/145 campañas aceptadas, R05 21/29, 8 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. EVE no expone HTTP por diseño TLS. No se ejecutó scoring ni se
modificó el modelo. Siguiente paso: documentar/publicar y continuar con el
próximo preflight R05.
