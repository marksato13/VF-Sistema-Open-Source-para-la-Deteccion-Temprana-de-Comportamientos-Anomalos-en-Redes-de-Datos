# Decimoquinto canario oficial R05 — HTTP-MULTI-1

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-MULTI-1-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única campaña con una solicitud HTTP secuencial a cada VIP lógica
(`10.30.0.10`, `.11` y `.12`). Commit `1cd0e4e5e1bef7719cf13e384bbefbc2a8d01720`,
matriz `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `43de3a417d75f4818c5a553268b80ce3a5805109a3bbc6b605e9fb0b8f50b485`.
El preflight pasó todos los gates.

## Evidencia

- Tres respuestas HTTP 200, una por VIP.
- PCAP `30/30/30` de 3.369 bytes, cero drops y sin límite.
- Todas las longitudes IPv4 fueron pequeñas: media 81,50 y máximo 251.
- EVE: 16 registros: 3 HTTP, 3 fileinfo, 1 flow y 9 stats.
- Una fila elegible con tres intentos L4, `unique_dst_ip_ratio_30s=1.0`,
  `unique_dst_port_ratio_30s=0.33333333` y ratio de error HTTP cero.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`f0e9c42226b30e915256fe147f8c7500ed8b14490869c5262fffc6ee9973779c`, manifest
`e77426d01cbf38af8ea54d2cc588d73e1b7d88fcacb6945a801f0715691536db`, campaña
`03e0ee69e3873f3e5ae30b06dcd499ec0e218b438e8b933932d6534cb5c74046`, features
`8f631215f5cf6cfdfedb7db9a1454253c68315ea5e781afc99273be69526cb0c` y ledger
`f2ef9e870644243e593a7e0abb7ae7ea6336a168b403cb5b7aee34262bf8be13`.

## Auditoría y límites

El auditor global queda en 131/145 campañas aceptadas, R05 16/29, 13 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. La celda aporta diversidad de destino, no tráfico pesado. No se
ejecutó scoring ni se modificó el modelo. Siguiente paso: documentar/publicar y
continuar con el próximo preflight R05.
