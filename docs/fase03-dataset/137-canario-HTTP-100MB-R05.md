# Octavo canario oficial R05 — HTTP-100MB

Fecha: 7 de agosto de 2026. Campaña: `F1N-HTTP-100MB-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y control

Se ejecutó una única captura del perfil `HTTP-100MB` con argumentos `100MB 10M`.
El commit congelado fue `b601a61aab36dd9470928adba5575d8a17f1cb9f`, la matriz
tiene SHA-256 `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`
y los argumentos `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e`.
El preflight continuo pasó todos sus gates; incluyó 70 s de quietud previa,
NTP, almacenamiento oficial, aislamiento, rutas, servicios, probes y Suricata.

Antes de abrir la captura se comprobó manualmente en el servidor que
`/srv/ppi/files/100MB.bin` mide `104857600` bytes y tiene SHA-256
`20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`. El
cliente devolvió HTTP 200 y `Content-Length: 104857600`.

## Evidencia primaria

- Transferencia: HTTP 200, `104857600` bytes, 9.503927 s, 11,033,081 B/s.
- PCAP: `77987/77987/77987` paquetes, `111346495` bytes, cero drops y
  transferencia remota verificada.
- Longitudes IPv4: 72,484 paquetes entre 500–1500 bytes (92.9437 %),
  72,471 exactamente a 1500, media 1,397.76 y máximo 1,500.
- Suricata: 14 eventos EVE (1 HTTP, 1 fileinfo y 12 stats), sin decoder
  inválido ni overflow. `fileinfo` informa `TRUNCATED` a 102,400 bytes por el
  límite de inspección; no contradice el HTTP ni el PCAP completo.
- Features: dos ventanas elegibles, con 70,718 y 7,269 paquetes; ratios de
  paquetes grandes `0.92260811` y `0.99587288`. Son ventanas del mismo
  episodio y no transferencias independientes.
- Recursos del Sensor: 64 muestras, CPU 0.00–15.76 %, RSS estable en 782,504
  KiB, memoria disponible 14,081,032–14,162,384 KiB y load1 0.10–0.21.

Todos los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes de trazabilidad:

| Evidencia | SHA-256 |
|---|---|
| preflight | `cdc3f9ac6cca53201c6f1c57f2c0f78b6f20a1e3eddbeb68683a8477eb09956e` |
| manifest | `b69947740b09531eb5404a461610ff1016163f62513ed127e141de8b5112b7dc` |
| bundle de campaña | `36968502c99a973740d5f723008a1d0dc37b24b1f611aeed22ef362ccb41ab9a` |
| resumen de longitudes | `97864393e810011092351deb3bb6a11dd38be378128e9f971702d10068d91cca` |
| deltas | `50bce715d00221cac3cb311398e2cbe6737091221233c0276c489b283d4a6bc1` |
| EVE | `0f9455cbfb0d568320e353024a83fa441898a33ae046249dcfc4f1389a9922bc` |
| escenario | `fc4af5919672fea6bdec3bbc7f1069388ba399a7b79622defed7d2b41cb1b45d` |
| features CSV | `4dc9efde373334446af8207c26c2d2436d2497efa8d086e51ee9070e831421b2` |
| reporte de extracción | `23ab8990ad96d63ad000a5fcc17509de6f8c176086feea63eabc088e9788536b` |
| ledger | `242724641518a8e264d9fc0182bec04a3acd07e487d43fbd937610a341ea1a92` |

## Auditoría y límites

El auditor global quedó en 124/145 campañas aceptadas, R05 8/29, 21 celdas
faltantes, 33 vectores duplicados, 16 cruces entre particiones y cero campañas
inválidas o advertencias. El resumen R05 contiene 8 perfiles, 13 filas, 86,824
observaciones de paquetes y 306 de aplicación. HTTP-100MB aporta 77,987
observaciones y dos filas.

Los duplicados estructurales y las dos ventanas del mismo episodio no se
interpretan como independencia estadística. No se ejecutó scoring ni se
modificó ningún modelo. La revisión Claude no pudo iniciarse en esta sesión por
falta de autenticación (`Not logged in`); la aceptación anterior es, por tanto,
una revisión técnica reproducible de Codex pendiente de confirmación Claude.

La campaña responde a la observación del jurado: el tráfico legítimo pesado se
etiqueta por escenario controlado, no por asumir que un paquete grande sea un
ataque. Siguiente paso autorizado: sólo el preflight independiente del próximo
perfil R05; no captura desatendida, scoring ni reentrenamiento.
