# Decimotercer canario oficial R05 — HTTP-C4

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-C4-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única campaña con cuatro descargas HTTP concurrentes de 100 MB,
limitadas a 5M por flujo. Commit `a3e551157f2de6fe991ae1f86dc973019caa6308`,
matriz `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `d8197cefd6d7c50ed78fad328040916bb2b3efbe78c449c62e4c0d6502e93d73`.
El preflight continuo pasó todos los gates.

## Evidencia

- Cuatro HTTP 200 de 104.857.600 bytes, cada uno en aproximadamente 19,51 s.
- PCAP `308525/308525/308525` de 445.134.062 bytes, cero drops y sin límite.
- Longitudes IPv4: 289.968 paquetes entre 500–1500 bytes (93.9853 %),
  289.852 exactamente a 1500, media 1.412,78 y máximo 1.500.
- EVE: 23 registros: 4 HTTP, 4 fileinfo y 15 stats; sin decoder inválido ni
  overflow.
- Tres ventanas elegibles, con 140.751, 146.366 y 21.408 paquetes; ratios
  pesados `0.87848044`, `0.99099518` y `0.99369395`. Son un único episodio.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`f164195113a5cf0b329743f385859eba6713c1d82ca22466b12513c02bcca6c2`, manifest
`43a3a793dca40989ba7b8cc2fe276f4146cb75ac731cd0ea44974d3a34cc72cd`, campaña
`5209fe77252ff47b193c11265060aa00ee7bd1108066ad14c9e85dd940e15008`, features
`691b9c99e9216815e222875fbf9318e7516452bda3404398bf9108b5a7ae39c3` y ledger
`341dba6fba0882a8a7d66ba1d5b191314505fddb8947874537dc97ad719bdb23`.

## Auditoría y límites

El auditor global queda en 129/145 campañas aceptadas, R05 13/29, 16 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. Las tres ventanas son autocorrelacionadas por episodio y no son
muestras independientes. No se ejecutó scoring ni se modificó el modelo.

Siguiente paso: documentar/publicar y continuar con el próximo preflight R05.
