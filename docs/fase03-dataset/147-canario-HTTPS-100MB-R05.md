# Decimoctavo canario oficial R05 — HTTPS-100MB

Fecha: 8 de agosto de 2026. Campaña `F1N-HTTPS-100MB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única transferencia HTTPS legítima de 100 MB a 10M. Commit
`d8b60a06a53f00c88f296ea9e5986fd712d9ced1`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e`.
El preflight pasó todos los gates.

## Evidencia

- HTTPS 200, 104.857.600 bytes, 9.523563 s, 11.010.333 B/s.
- PCAP `76822/76822/76822` de 111.400.547 bytes, cero drops y sin límite.
- Longitudes IPv4: 72.598 paquetes entre 500–1500 bytes (94.5016 %),
  72.553 exactamente a 1500, media 1.420,11 y máximo 1.500.
- EVE: 12 registros, TLS y 11 stats; sin HTTP/fileinfo por cifrado.
- Dos ventanas elegibles con ratios pesados `0.94873210` y `0.94276397`;
  TLS session rate `0.01666667` por ventana.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`ef84a761cb7b3257b22c49ca8b14f1b119c29793bcd7be6767379f964238a73d`, manifest
`4f2cb7c6d4237667e9036b00877ded89437c855b969b37a1a7b384c39447e5f9`, campaña
`0f2c393e0b284c12b6c9a038598d0e4843947c907f41709d55caa4a96db9945f`, features
`8ae17e500abed709b3f1d5a1332289b31e0524bf88a6279403a5f33f1abe0b78` y ledger
`00d0a280625e67225b90c0cccaf7835788723857e3d1873abea454b3e3483b6e`.

## Auditoría y límites

El auditor global queda en 134/145 campañas aceptadas, R05 20/29, 9 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. EVE no expone HTTP por diseño TLS. No se ejecutó scoring ni se
modificó el modelo. Siguiente paso: documentar/publicar y continuar con el
próximo preflight R05.
