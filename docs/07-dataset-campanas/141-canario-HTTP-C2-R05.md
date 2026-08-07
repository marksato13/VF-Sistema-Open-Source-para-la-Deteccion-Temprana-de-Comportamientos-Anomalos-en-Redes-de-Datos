# Duodécimo canario oficial R05 — HTTP-C2

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-C2-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única campaña concurrente con dos descargas de 100 MB limitadas
a 10M por flujo. Commit `3b93dcffb994fef2a8b42f39168534ed0d288ec1`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`, argumentos
`1c65572c683bb319db50f0e8a31d65ac0ee998bd62b7fdc92c459d972436b976`.
El preflight continuo pasó todos los gates.

## Evidencia

- Dos HTTP 200, cada uno de 104.857.600 bytes; duración 9.507263/9.505733 s.
- PCAP `152425/152425/152425` de 222.413.988 bytes, cero drops y sin límite.
- Longitudes IPv4: 144.976 paquetes entre 500–1500 bytes (95.1130 %),
  144.941 exactamente a 1500, media 1.429,17 y máximo 1.500.
- EVE: 16 registros: 2 HTTP, 2 fileinfo y 12 stats; sin decoder inválido ni
  overflow.
- Dos ventanas elegibles, 58.262 y 94.163 paquetes, con ratios pesados
  0.88689025 y 0.99087752. Ambas pertenecen al mismo episodio concurrente.
- Features reflejan dos intentos L4 (`flow_attempt_count_30s=2`) y ratio de
  destinos `0.5`, coherentes con los dos flujos concurrentes.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`86d0d87d7855c185f4e32b4f1be082cf423a33c8a8fdbf0686e0669acb0df7d2`, manifest
`ceb20038566cd52ec21dfd1b880fd07ba2cda504059c92f42c237461508436cf`, campaña
`262aed4150cf4919e2a1dc3f93264ffe65b1072255de6057e32dd3d4d1a3cd25`, features
`d48f9e9fc32022b7c512b27c7ef3616b6ecac2744e3c69bd485ed8048be1b94f` y ledger
`d618fdcfca1485ac14fdf65b7ffc37b64c39d947affc68810afd4f2cc3b1d42c`.

## Auditoría y límites

El auditor global queda en 128/145 campañas aceptadas, R05 12/29, 17 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. Las dos ventanas son autocorrelacionadas por episodio y no son
dos muestras independientes. No se ejecutó scoring ni se modificó el modelo.
Siguiente paso: documentar/publicar y continuar con el próximo preflight R05.
