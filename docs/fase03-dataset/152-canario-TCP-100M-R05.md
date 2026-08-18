# Vigésimo tercero canario oficial R05 — TCP-100M

Fecha: 8 de agosto de 2026. Campaña `F1N-TCP-100M-R05`, partición `test`,
`purpose=experiment`. Estado: **ACEPTADA CON LIMITACIONES**.

Se ejecutó una transferencia TCP legítima con iperf3 a 100M durante 20 s.
Commit `f9a152ae8a98174166e1f3b94b09da53fe7c4074`, matriz
`ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y
argumentos `253484f3d35c6eb92ae1a4c89c7983db5520cb8c6c9aa12f94730f48fb0908bf`.
El preflight pasó todos los gates.

## Evidencia

- Iperf3 TCP: 250.085.376 bytes enviados y recibidos, 20.001587 s,
  100.026213 Mbit/s enviados y 100.023768 Mbit/s recibidos; tres
  retransmisiones TCP reportadas por el emisor.
- PCAP `184497/184497/184497` de 265.217.372 bytes, cero drops, cero paquetes
  inválidos y sin alcanzar el límite de captura.
- Longitudes IPv4: 173.629 paquetes entre 500–1500 bytes (94.1094 %),
  171.722 exactamente a 1500, media 1.407,52 y máximo 1.500.
- EVE: 16 registros (14 stats, 1 alert y 1 anomaly), conservados íntegramente.
- Tres ventanas elegibles del mismo episodio; la primera registra dos SYN,
  `syn_completion_ratio_10s=1.0` y `flow_attempt_rate_10s=0.2`; ratios
  pesados `0.94173311`, `0.94050289` y `0.94163021`.

Los bundles pasaron `sha256sum -c SHA256SUMS`. Hashes: preflight
`0c7c6b34a27fe9a7319d81331ccf3e5b4838c32883fed0f4b889a6890abed32`, manifest
`88d0fc25ef0c9c0f0c5bda8d9be28be80850f0821aaa77953ea7f5ab3f174773`, campaña
`63255cbfddf839bdf8a876da2852bbe9222772d1f135a325ef23b63882b56c8a`, features
`ab721b1bb11e47207de802b35ea9617cf4b595ca4514d9b6b11aa65ed7ab4ecc` y ledger
`f8974843ae4c04ac2c0ef9fb210d7062e9f724db200c4d528567b17f196d8cbd`.

## Auditoría y límites

El auditor global queda en 139/145 campañas aceptadas, R05 25/29, 6 celdas
faltantes, 36 vectores duplicados, 19 cruces y cero campañas inválidas o
advertencias. Faltan `TCP-200M`, `TCP-REFUSED-5`, `TLS-SESSIONS-20`, `UDP-10M`,
`UDP-25M` y `UDP-50M`, todas R05.

Las tres filas son ventanas autocorrelacionadas de una sola transferencia. Las
retransmisiones de iperf3 no son drops del sensor: los contadores permanecieron
en cero. No se ejecutó scoring ni se modificó el modelo. El siguiente paso es
completar las seis celdas R05 restantes con preflight independiente.
