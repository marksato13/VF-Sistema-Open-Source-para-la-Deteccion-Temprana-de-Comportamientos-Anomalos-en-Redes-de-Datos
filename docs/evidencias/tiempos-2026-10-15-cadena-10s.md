# Evidencia de respuesta con la cadena de 10 segundos

Fecha: 2026-10-15. Escenario vigente: Sensor1 por SPAN, feed firmado, relay en
bastión y agente `nftables` en el host DMZ.

## Configuración verificada

| Tramo | Timer | Calendario |
|---|---|---|
| Sensor1 | `ppi-publicar-feed.timer` | `*-*-* *:*:00/10` |
| Bastión | `ppi-relay-feed.timer` | `*-*-* *:*:03/10` |
| Host DMZ | `ppi-enforce-agent.timer` | `*-*-* *:*:06/10` |

Los tres usan `AccuracySec=1s`. Se observaron varios ciclos consecutivos sin
errores. El relay tarda aproximadamente 1–2 s y el agente menos de 1 s.

## Prueba real: port scan a BLOCK

Origen: Kali `10.10.20.30`. Destino: host DMZ `10.10.30.10`.

```text
Inicio del escaneo (Kali):  2026-10-15 12:47:34.588 UTC
Duración de nmap:           17,63 s
Decisión port_scan→BLOCK:   2026-10-15 12:48:00.676 UTC (reloj corregido)
Publicación firmada:        2026-10-15 12:48:06 UTC aprox.
Relay:                      2026-10-15 12:48:13–14 UTC
Aplicación en nftables:     2026-10-15 12:48:16 UTC
```

Resultados:

- Ataque iniciado → decisión: **26,1 s**.
- Decisión → `nftables`: **15,3 s**.
- Ataque iniciado → `nftables`: **41,4 s**.
- El agente informó `errores: 0` y el set mostró `10.10.20.30`.

La primera decisión relevante quedó registrada con `logged_at =
1792068444.6857338`. Sensor1 estaba **35,990 s atrasado** frente al punto medio
de dos lecturas consecutivas del bastión; por eso se corrigió su timestamp antes
de calcular tiempos entre hosts.

## Hallazgos corregidos durante la prueba

1. Republicar una misma decisión incrementaba la reincidencia en cada ciclo. El
   publicador ahora agrupa eventos BLOCK continuos dentro de un episodio de 120 s,
   persiste `ultimo_evento_block` y acota el contador al nivel efectivo `3+`.
2. El agente vaciaba ambos sets en cada pasada. Cuando una decisión salía de la
   ventana de publicación de 120 s, eliminaba el bloqueo antes de su timeout de
   300/1800/3600 s. Ahora los sets no se vacían: `nftables` conserva cada elemento
   hasta su caducidad nativa.

La deduplicación se confirmó posteriormente en el estado vivo: `10.10.20.30`
quedó en `bloqueos: 3` con un solo `ultimo_evento_block`, sin crecer cada 10 s.

## Prueba segura de caducidad nativa

Se publicó temporalmente una acción firmada para `198.51.100.10`, dirección
TEST-NET reservada para documentación y no enrutable. Después, el feed de Sensor1
y el recibido por la DMZ volvieron a `entradas: []`. Aun así, el set mostró:

```text
198.51.100.10 timeout 4m16s expires 3m26s45ms
```

Esto demuestra que un feed vacío ya no acorta una acción vigente; el kernel la
retira al vencer su timeout.

Una segunda prueba sobre `198.51.100.20` validó la ampliación por reincidencia:
el elemento existente pasó de `timeout: 257, expires: 238` a `timeout: 551,
expires: 537`. El agente leyó el estado actual, eliminó y recreó solo ese elemento
dentro del mismo lote `nft -f -`; el journal informó `errores: 0`. Los ciclos
posteriores aplicaron un único lote atómico de siete operaciones y conservaron el
timeout. La entrada TEST-NET se retiró manualmente al terminar la validación.

La reconstrucción de las reglas también se envía ahora como una sola transacción
`nft -f -`. Ya no existe una ventana entre `flush chain` y la reposición de las
reglas: el lote completo se confirma o se conserva el estado anterior.
Un `LIMIT` posterior tampoco rebaja ni elimina un `BLOCK` que siga vigente. Si un
elemento caduca entre la lectura JSON del set y el commit, el agente relee,
replanifica y reintenta una vez el lote completo.

## Limitación operativa pendiente

Sensor1 reportó `NTP=yes` pero `NTPSynchronized=no`, sin servidor alcanzable y
con 35,990 s de desfase. Bastión y DMZ sí estaban sincronizados. El polling cada
10 s sigue funcionando, pero el orden nominal `:00 → :03 → :06` solo es
determinista entre relojes sincronizados. Debe habilitarse un NTP interno
alcanzable desde la VLAN del sensor antes de usar timestamps entre hosts sin
corrección.

El feed y su firma todavía son dos ficheros separados. Una lectura que coincida
con su reemplazo puede fallar de forma segura por firma inválida y retrasar la
acción hasta el siguiente ciclo; no permite aceptar un feed manipulado. Empaquetar
cada generación en un artefacto único queda como mejora de disponibilidad.
