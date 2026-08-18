# Décimo canario oficial R05 — HTTP-1GB

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-1GB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única captura con `1GB 20M`, commit
`4f3c4e859f045183fd58608e1cc1ba2eb1483230`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77`.
El preflight pasó todos los gates con 120,8 GB libres.

La comprobación manual previa confirmó `/srv/ppi/files/1GB.bin` con
1.073.741.824 bytes, SHA-256
`49bc20df15e412a64472421e13fe86ff1c5165e18b2afccf160d4dc19fe68a14`, HTTP
200 y `Content-Length` exacto.

## Evidencia

- HTTP 200, 1.073.741.824 bytes, 51.006792 s, 20.950.957 B/s.
- PCAP: 3 archivos, 752.360/752.360/752.360 paquetes, 1.136.949.165 bytes,
  cero drops, sin límite alcanzado y transferencia remota verificada.
- Longitudes IPv4: 742.579 paquetes entre 500–1500 bytes (98.7000 %),
  742.574 exactamente a 1500, media 1.481,18 y máximo 1.500.
- EVE: 29 registros (1 HTTP, 1 fileinfo, 3 flows, 24 stats), sin decoder
  inválido ni overflow. `fileinfo TRUNCATED` sigue siendo el límite de
  inspección de Suricata.
- Features: seis ventanas elegibles; ratios pesados
  `0.93909941`, `0.99640691`, `0.99630915`, `0.99624866`, `0.99498669` y
  `0.99594285`. Todas pertenecen al mismo episodio.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes principales: preflight
`c863a4575731214a511a099c23a5b600ff00f35d2293bdd5aa786a22da8b2544`, manifest
`4aee43eceadf906171a2492f52b4459f6ef93359371f8f9c9eb5bb5fdf0ceb7f`, campaña
`2be6f982949612a29e3d770002bc7e3d1b00681dfbd30995f4afaee9a5b33096`, features
`057e5e480ca725583e6556d238d8112d9a6801fb8c70105046bd00be576cdf7e` y ledger
`22a2cc3d5dd68396bb3fdca71301d4f44af82f9233ca71a6f9de1e8203e517e0`.

## Auditoría y límites

El auditor global queda en 126/145 campañas aceptadas, R05 10/29, 19 celdas
faltantes, 33 vectores duplicados, 16 cruces entre particiones y cero campañas
inválidas o advertencias. Las seis ventanas son autocorrelacionadas y no son
seis muestras independientes. No se ejecutó scoring ni se modificó el modelo.

La campaña completa la escalada HTTP legítima de 10 MB, 100 MB, 500 MB y 1 GB,
aportando evidencia fuerte para que el tamaño de paquete por sí solo no sea
tratado como ataque. Siguiente paso: documentar/publicar y continuar sólo con
el próximo preflight independiente R05.
