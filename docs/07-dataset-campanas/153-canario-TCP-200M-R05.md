# Vigésimo cuarto canario oficial R05 — TCP-200M

Fecha: 8 de agosto de 2026. Campaña `F1N-TCP-200M-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una transferencia TCP legítima de techo con iperf3 a 200M durante
20 s. Commit `8683cd9b796692153eadf5f2679060647f1fc675`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `faee06d0a2df5e1d04db840eb446cbee345863478160c705e01d6f39a459bc93`.
El preflight pasó todos los gates.

## Evidencia

- Iperf3 TCP: 500.170.752 bytes enviados y 500.039.680 recibidos,
  20.006285/20.007895 s, 200.005449/199.936947 Mbit/s; tres retransmisiones
  TCP reportadas por el emisor.
- PCAP `368621/368621/368621` de 530.400.293 bytes, cero drops, cero inválidos
  y sin alcanzar el límite de 560 MB.
- Longitudes IPv4: 347.238 paquetes entre 500–1500 bytes (94.1992 %),
  343.458 exactamente a 1500, media 1.408,88 y máximo 1.500.
- EVE: 18 registros (16 stats, 1 alert y 1 anomaly), conservados íntegramente.
- Tres ventanas elegibles del mismo episodio; ratios pesados
  `0.73291112`, `0.94271147` y `0.94657779`; la primera registra dos SYN,
  `syn_completion_ratio_10s=1.0` y `flow_attempt_rate_10s=0.2`.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`8212e73ebd06f2bc0f96836ed3560ebe632da879c860c80e6e4b78a2da50f31b`, manifest
`3050cde33a3eb35046d983b36c1bd634dcef2c8adbce6de1a84304f1f48fa62c`, campaña
`17fc8f648bff364375bf5f0960ed73833969f3f7fc48833c0617fd214f293abd`, features
`b3b8b3019024a291cb33b87a49441441af6244a32c1848eed25ac9eec63bde10` y ledger
`cc9dca6254cc81241f57d41f45f634c6812f4fd59760b3b26246c286382d4698`.

## Auditoría y límites

El auditor global queda en 140/145 campañas aceptadas, R05 26/29, 5 celdas
faltantes, 36 vectores duplicados, 19 cruces y cero campañas inválidas o
advertencias. Faltan `TCP-REFUSED-5`, `TLS-SESSIONS-20`, `UDP-10M`, `UDP-25M` y
`UDP-50M`, todas R05.

Las tres filas son ventanas autocorrelacionadas de una sola transferencia. Las
retransmisiones TCP no son drops del sensor. No se ejecutó scoring ni se
modificó el modelo. El siguiente paso es completar las cinco celdas R05
restantes con preflight independiente.
