# Noveno canario oficial R05 — HTTP-500MB

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-500MB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

## Control

Se ejecutó una única captura del perfil `HTTP-500MB` con argumentos `500MB 20M`.
El commit fue `4ea0460001922635d55f7e2be6893cb42f2ab5ec`; matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`; argumentos
`fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f`.
El preflight continuo pasó todos los gates con 121,3 GB libres y 70 s de
quietud previa.

Antes de capturar se comprobó `/srv/ppi/files/500MB.bin`: 524288000 bytes,
SHA-256 `a08a92258f621b55d08ad1e84c90c2ea6286fc6b6c9a4dfa7156afb16c190170`.
El cliente confirmó HTTP 200 y `Content-Length: 524288000`.

## Evidencia

- HTTP 200, 524.288.000 bytes, 24.507255 s, 21.393.175 B/s.
- PCAP: dos archivos, 367.817/367.817/367.817 paquetes, 554.879.765 bytes,
  cero drops, sin límite alcanzado y transferencia remota verificada.
- Longitudes IPv4: 362.375 paquetes entre 500–1500 bytes (98.5205 %),
  362.372 exactamente a 1500, media 1.478,58 y máximo 1.500.
- EVE: 18 registros (1 HTTP, 1 fileinfo, 16 stats); sin decoder inválido ni
  overflow. `fileinfo TRUNCATED` representa el límite de inspección de
  Suricata, no una descarga incompleta.
- Features: cuatro ventanas elegibles, con ratios pesados
  `0.87246327`, `0.98474561`, `0.99557456` y `0.99559842`. Son ventanas del
  mismo episodio HTTP, no cuatro transferencias independientes.
- Recursos: 91 muestras, CPU 0.00–19.12 %, RSS estable en 782.504 KiB.

Los bundles de campaña y features pasaron `sha256sum -c SHA256SUMS`. Hashes:

| Evidencia | SHA-256 |
|---|---|
| preflight | `a86718d93500b304c4d87b9937bb7d067262a922785bc627bed572d6a3c85cc8` |
| manifest | `769eedf52006f4fa441dbdeaff148adcb2bc4366099f7d02d746d064a4b747d8` |
| bundle campaña | `78bcb3c4cfcedd4b3935560d7ef7ad6fde3c62dbab34f1afd186e96622280d60` |
| longitudes | `2e7a8ade6bf81d0c62cc124f18946e749465d1a7f4adc2e317e1e075e49c03fa` |
| deltas | `198808c2051e9d1c20434668d3a1dafc848052f86be602554a061955000eecae` |
| EVE | `39fe5a3db351c9cf4dfd4108030ba376d57f03aee8f352cd15bfdcc65e9a0faf` |
| escenario | `4d258bc74ac7d563927a20daaa009152a87f9e3243af45fc1f7b4216487fe096` |
| features CSV | `a92ff9284cd18652a4386d54f190e16934c7d8f0b507a30eb600da0f96186a61` |
| extracción | `34aefe7ddd23011b44eb7ace9c080aea5bee967a17d2a46d9d9fd51afca7afae` |
| ledger | `cc746c5b929f4693a37d4b400bcddd4e1f0eb8b17bf5dfb359394b311e3c9439` |

## Auditoría y límites

El auditor global quedó en 125/145 campañas aceptadas, R05 9/29, 20 celdas
faltantes, 33 vectores duplicados, 16 cruces entre particiones y cero campañas
inválidas o advertencias. HTTP-500MB/R05 aporta cuatro filas y 367.817
observaciones de paquetes. No se ejecutó scoring ni se modificó el modelo.

Las cuatro ventanas están autocorrelacionadas por pertenecer a una sola
transferencia. El tráfico se etiqueta benigno por escenario controlado, no por
el tamaño del paquete. Siguiente paso autorizado: documentar/publicar este
cierre y ejecutar sólo el preflight independiente de `HTTP-1GB/R05`.
