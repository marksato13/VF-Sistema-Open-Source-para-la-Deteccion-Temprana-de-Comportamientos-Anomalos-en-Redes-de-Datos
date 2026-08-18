# Quinto canario oficial R04 — PING-10

Fecha: 4 de agosto de 2026. Campaña: `F1N-PING-10-R04`. Partición: `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil genera diez echo request ICMP a intervalo nominal de un segundo desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`, con sus diez replies. Es tráfico benigno ligero para ejercitar `icmp_ratio_10s`; la alerta de laboratorio no etiqueta ataque.

El preflight fijó commit limpio `58c02b67244ec795d807a6584842aa9d0b5ae33d`, perfil `PING-10`, repetición 4, `validation`, argumentos `10 1`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `4027af88974510696bfebde488ece5ffaa0fdaace6f2d504d035a226e095db67`. Almacenamiento y NTP pasaron; el máximo absoluto observado fue 1.057956 ms. También pasaron NIC externas, bypass, SSH, Suricata, contadores, servicios, rutas, DNS, eco de control, generador, IDs, ledger, lock y captura.

Una primera comprobación buscó el generador en una ruta remota equivocada y se detuvo antes de crear campaña. Se corrigió a `/home/useransible/bin/ppi-run-benign` y se repitió el bloque completo con `PASS`; no hubo intento parcial ni artefactos huérfanos. Claude revisó esta incidencia y autorizó exactamente una captura sin scoring.

## Resultado ICMP

| Control | Resultado |
|---|---:|
| Echo request / reply PCAP | 10 / 10 |
| Secuencias distintas | 1–10 |
| Transmitidos / recibidos | 10 / 10 |
| Pérdida | 0 % |
| Duración informada | 9.213 s |
| Span de requests PCAP | 9.213521 s |
| RTT mín./prom./máx./mdev | 0.353/0.480/1.085/0.207 ms |
| Stderr | vacío |

El PCAP conserva diez pares con ID ICMP 12346 y secuencias consecutivas. EVE contiene diez alertas, todas y sólo SID `1000001`, firma `PPI LAB ICMP TEST`, severidad 3, sobre echo request tipo 8/código 0. La regla es telemetría permitida del laboratorio y confirma la semántica del episodio; no representa una detección de ataque.

## PCAP, EVE y flows diferidos

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 20 / 20 / 20 |
| PCAP | 1 archivo / 2,304 bytes |
| Drops tcpdump | 0 |
| EVE esperado / extraído | 23 / 23 |
| Tipos EVE | 10 alert + 11 stats + 2 flow |
| Delta Suricata / PCAP | 24 / 20 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los veinte IPv4 miden 84 bytes y son menores de 500 bytes. Suricata incrementó cuatro paquetes más que PCAP, patrón observado en PING-10/R01–R03; la causa continúa sin atribuirse.

Los dos `flow` EVE son probes anteriores, no tráfico del escenario:

- ICMP: tráfico real `21:35:30.252473–21:36:23.784413`, dos request/reply de los controles repetidos, emitido `21:41:25.682834` por `timeout`;
- DNS: tráfico real `21:36:23.519187–21:36:23.519580`, una consulta/respuesta de control, emitido `21:41:29.671615` por `timeout`.

La captura se verificó desde `21:40:51.468782` y el escenario empezó `21:41:52.208011`; por tanto, los paquetes de ambos flows ocurrieron antes del PCAP, aunque Suricata los publicó durante el warm-up. Permanecen visibles y limitan la afirmación de que el slice EVE sea exclusivamente causal. El extractor usa las veinte observaciones del PCAP, registra cero observaciones de aplicación y no consume eventos `flow`; las dos filas numéricas no se alteraron.

## Fase UTC y features

El episodio cruzó el borde UTC `02:42:00` y produjo dos ventanas elegibles:

| Fin UTC | Paquetes | Packet rate | Byte rate | Attempts 30 s | Attempt rate 10 s | Ratio IP / ICMP |
|---|---:|---:|---:|---:|---:|---:|
| `02:42:00` | 16 | 1.6/s | 134.4 B/s | 1 | 0.1/s | 1 / 1 |
| `02:42:10` | 4 | 0.4/s | 33.6 B/s | 1 | 0.0/s | 1 / 1 |

Ambas filas tienen `mean_ip_len_10s=84`, ratio pesado cero y ratio de puertos cero porque ICMP no tiene transporte L4. Son ventanas autocorrelacionadas de un solo episodio, no dos repeticiones independientes.

R01 produjo una fila de 20 paquetes; R02, 18/2; R03, 6/14; y R04, 16/4. La fase UTC cambia el reparto sin cambiar los diez pares causales. Ninguna de las dos filas R04 coincide exactamente con una fila previa de `train`, incluido `PING-100`; no se añade un cruce `seen`.

## Recursos, integridad y auditoría

El Sensor produjo 60 muestras: CPU 0–1.51 %, RSS constante 781,720 KiB, memoria disponible 14,093,960–14,162,716 KiB y load1 0.12–0.71. Son observaciones, no umbrales. Ambos stderr están vacíos.

Todos los archivos de ambos bundles pasaron y el PCAP remoto/local comparte SHA-256 `723c3b1d4697340d69b014b0ebc86be7c6285f5035ba813c7d942b64717d7d87`:

```text
manifest.json          10338af2d31677b1611775b7ab3b38af1ba4b9e44f11c27e6833977042aacc5a
eve-slice.jsonl        2f506080b7e28a2797c1ce4b78382caf653d7ac6b7e0a04a1f5b4672b0a0cb71
campaign SHA256SUMS    dd52384399a99d2ec18ad943446e83686b0f066a5895d5daa2225afea4f805c0
multilayer-v1.csv      20ec9ac1668078977b524777db99486e2b9da08559e55b60becbb1462199f177
feature SHA256SUMS     0067a4881a32abfbaf0c3084e93c0c0eb1359f8b3db836bea346bdb0c8005b4f
ledger                 36cdc880c507c1217d9d280691cfc0d84d10d58f9bdf4b5569854f1dda05ce90
```

El auditor ejecutado desde Git limpio aceptó 92/145, R04 5/29, 53 faltantes, cero inválidas/advertencias. Permanecen veinte coincidencias globales y tres cruces train↔validation; esta campaña no incrementa ninguno. `ready_to_build=false` corresponde sólo a F1 incompleta.

**F1N-PING-10-R04 ACEPTADA CON LIMITACIONES.** Valida diez pares ICMP, telemetría SID 1000001, captura íntegra y fase 16/4; conserva dos flows diferidos fuera del PCAP y el delta Suricata +4 sin causa atribuida. No se calcularon scores ni umbrales. Siguiente autorizado: sólo preflight independiente de `F1N-PING-100-R04`.
