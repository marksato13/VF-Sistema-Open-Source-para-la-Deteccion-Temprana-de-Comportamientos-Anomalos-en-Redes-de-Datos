# Vigésimo canario oficial R05 — HTTPS-1GB

Fecha: 8 de agosto de 2026. Campaña `F1N-HTTPS-1GB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única transferencia HTTPS legítima de 1 GiB a 20M. Commit
`1a0efcf301bf6a4c5d858a4af3dad30028c1d014`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77`.
El preflight pasó todos los gates: NTP, SSH, NIC externa desconectada,
aislamiento, rutas, Suricata, servicios y probes.

## Evidencia

- HTTPS 200, 1.073.741.824 bytes, 51.021556 s, 21.044.866 B/s.
- PCAP `757634/757634/757634` de 1.138.328.899 bytes, cero drops y sin
  alcanzar el límite de captura; la transferencia remota fue verificada.
- Longitudes IPv4: 743.274 paquetes entre 500–1500 bytes (98.1046 %),
  743.157 exactamente a 1500, media 1.472,48 y máximo 1.500.
- EVE: 26 registros (1 flow, 1 TLS y 24 stats); sin HTTP/fileinfo por el
  cifrado TLS.
- Seis ventanas elegibles del mismo episodio, con ratios pesados
  `0.92518703`, `0.98729004`, `0.98743401`, `0.98840138`, `0.98846738` y
  `0.98692389`; TLS session rate `0.01666667` en cada ventana.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`dd317a7499b1fac9a51711f12255faa22b96b4fc09628817dbeda7191bb6e4bf`, manifest
`383c733e694dd07a3202accbdb80623a9c46925acc81148d1b9ba8abe147c87d`, campaña
`9ac9a17d28124a6d62ec944875b4d2c577490561588ca2635c082e152b153b1b`, features
`987547ed8bba5836e7be003435771114076a804729c79ecceb8e83f0ce180376` y ledger
`01005ab7c1643b030ddfc868dbc35ba009a8f5644d5736f16471ea8d8ceaff01`.

## Auditoría y límites

El auditor global queda en 136/145 campañas aceptadas, R05 22/29, 9 celdas
faltantes, 36 vectores duplicados, 19 cruces y cero campañas inválidas o
advertencias. Las nueve celdas faltantes son `MIXED-LIGHT`, `TCP-100M`,
`TCP-200M`, `TCP-50M`, `TCP-REFUSED-5`, `TLS-SESSIONS-20`, `UDP-10M`,
`UDP-25M` y `UDP-50M`, todas en R05.

Las seis filas pertenecen a un único episodio HTTPS; por ello están
autocorrelacionadas y no deben interpretarse como seis sesiones independientes.
La captura aporta tráfico pesado legítimo para que el tamaño de paquete no sea
un indicador aislado de anomalía. No se ejecutó scoring ni se modificó el
modelo. El siguiente paso es completar las celdas R05 faltantes con preflight
independiente antes de construir el dataset final.
