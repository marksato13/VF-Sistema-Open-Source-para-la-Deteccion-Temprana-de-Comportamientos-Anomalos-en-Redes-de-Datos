# Vigésimo sexto canario oficial R05 — TLS-SESSIONS-20

Fecha: 8 de agosto de 2026. Campaña `F1N-TLS-SESSIONS-20-R05`, partición
`test`, `purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutaron veinte sesiones HTTPS/TLS legítimas contra el servicio interno.
Commit `8c7b2b0a3703d8fe370c4897e3b8611eb76c90f7`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `9246e824773fc95ffe7097ebf344e3aef5d4cd76329e4d39a4fd0e79eb8d75c4`.
El preflight pasó todos los gates.

## Evidencia

- Veinte sesiones terminaron con HTTP 200 dentro del túnel TLS.
- PCAP `436/436/436` de 146.626 bytes, cero drops, cero inválidos y sin
  alcanzar el límite de captura.
- EVE: 30 registros, exactamente 20 `tls` y 10 `stats`; no se esperan eventos
  HTTP/fileinfo porque el contenido de aplicación está cifrado.
- Longitudes IPv4: 63 paquetes entre 500–1500 bytes (14.4495 %), media
  306,24 y máximo 1.500; este perfil mide churn de sesiones, no tráfico pesado.
- Dos ventanas elegibles: la primera registra cinco SYN y
  `tls_session_rate_60s=0.08333333`; la segunda 15 SYN y
  `tls_session_rate_60s=0.33333333`, con completitud SYN 1.0 en ambas.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`d7711879bb7cd779bed77a0c9bce8e5f3a1d34a345f26ae1dd9f26cb9145091e`, manifest
`c8133c4043f89de62871d60cc1918a7b610afc4726f91e5c81933aa07e2ae2ec`, campaña
`8437cabcba2d70d5680befc7c515b25462e1783530129320d5002fe6a8f8c0ea`, features
`4941fa5068f09939a6e39cc52d4b5c6f97d9b82e3fe5c87e1838fe818752d1de` y ledger
`cc0a66155fd6635b38ee7e1295ed85b2b875b56ac73c3663ddcd558165a629e9`.

## Auditoría y límites

El auditor global queda en 142/145 campañas aceptadas, R05 28/29, 3 celdas
faltantes, 37 vectores duplicados, 20 cruces y cero campañas inválidas o
advertencias. Faltan `UDP-10M`, `UDP-25M` y `UDP-50M`, todas R05.

Las dos filas son ventanas autocorrelacionadas del mismo episodio de churn.
Este perfil complementa las transferencias HTTPS grandes: demuestra que el
modelo recibe sesiones TLS legítimas sin exigir visibilidad HTTP. No se
ejecutó scoring ni se modificó el modelo. El siguiente paso es completar las
tres campañas UDP R05 restantes.
