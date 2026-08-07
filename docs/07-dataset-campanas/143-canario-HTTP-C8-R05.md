# Decimocuarto canario oficial R05 — HTTP-C8

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-C8-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una única campaña con ocho descargas HTTP concurrentes de 100 MB,
limitadas a 2M por flujo. Commit `a5a8b0a949cb8fccc97039700c80d8058bfea0ca`,
matriz `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `048896cb26996464f54cd1f8d12cceb7d61e49246645aea858af30019dec7bdb`.
El preflight continuo pasó todos los gates.

## Evidencia

- Ocho HTTP 200 de 104.857.600 bytes, cada uno en aproximadamente 49,51 s.
- PCAP `594796/594796/594796` de 888.312.996 bytes, cero drops y sin límite.
- Longitudes IPv4: 580.006 paquetes entre 500–1500 bytes (97.5134 %),
  579.257 exactamente a 1500, media 1.463,47 y máximo 1.500.
- EVE: 38 registros: 8 HTTP, 8 fileinfo y 22 stats; sin decoder inválido ni
  overflow.
- Seis ventanas elegibles; ratios pesados `0.92923891`, `0.97809710`,
  `0.99018093`, `0.99085931`, `0.99057890` y `0.97578692`. Son un único
  episodio concurrente.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`6301f0a73d343ab17c19305f0847627bd30b88c0a3a1c8101f37fa0d6af6f80f`, manifest
`f1b5358e4cba031a53302121760cc7af6aa6953dba9f59a692c382a63f022c55`, campaña
`180d0c51d58ef2030e97445b1ec73672de25070e353918d237264fc2e10286da`, features
`15f338ef33edb22d185419cabf92eb0795b6745d313a775b2bc4c4ee54072bb8` y ledger
`7551ae890b6f88441be8ec4f393cf5b7fd3cf2a16cda76b2551e201fe1b5bbc4`.

## Auditoría y límites

El auditor global queda en 130/145 campañas aceptadas, R05 15/29, 14 celdas
faltantes, 33 vectores duplicados, 16 cruces y cero campañas inválidas o
advertencias. Las seis ventanas son autocorrelacionadas por episodio y no son
muestras independientes. No se ejecutó scoring ni se modificó el modelo.

Siguiente paso: documentar/publicar y continuar con el próximo preflight R05.
