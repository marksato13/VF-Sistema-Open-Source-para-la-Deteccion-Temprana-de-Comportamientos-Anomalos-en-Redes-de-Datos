# Tercer canario oficial R04 — DNS-MIXED-20-2

Fecha: 4 de agosto de 2026. Campaña: `F1N-DNS-MIXED-20-2-R04`. Partición: `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil combina veinte resoluciones válidas y dos NXDOMAIN controlados. Es error operativo benigno diseñado para que `dns_nxdomain_ratio_60s>0` no implique ataque por sí solo.

Después de publicar `DNS-VALID-200/R04`, el auditor limpio confirmó 89/145, cero inválidas/advertencias y Git limpio. El preflight fijó `dns-mixed 20 2`, `validation`, commit `1ff545e2c788529a4ea80c91b2c53bcc1d6e3ba7`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `4086992cb07355511e61bfce11d4c2dbf71be23f526d062154f55c2d707ea157`.

NTP pasó 5/5 con máximo absoluto 1.038 ms. NIC externas, bypass, servicios, rutas, DNS, generador, contadores, ID, ledger, lock y captura pasaron. Claude revisó ese preflight y autorizó exactamente una ejecución con comprobación posterior de 20 `NOERROR`, 2 NXDOMAIN, fase, integridad y vector visto.

## Resultado DNS

EVE conserva el orden causal exacto: veinte respuestas `NOERROR` con `rdata=10.30.0.10`, seguidas de dos `NXDOMAIN`. No hay alertas ni anomalías.

| Evidencia | Resultado |
|---|---:|
| DNS requests / responses | 22 / 22 |
| `NOERROR` / NXDOMAIN | 20 / 2 |
| Respuestas A esperadas | 20 |
| PCAP capturados / recibidos / parseados | 44 / 44 / 44 |
| PCAP | 5,092 bytes, un archivo |
| Drops tcpdump | 0 |
| EVE | 54: 44 DNS + 9 stats + 1 flow diferido |

Los DNS causales ocurrieron entre `21:01:40.950859` y `21:01:41.436493 -05:00`, intervalo 0.485634 s, sin cruzar un borde de 10 s. Los 44 IPv4 son menores de 500 bytes; media 85.18, máximo 93 y cero en el rango pesado. El tamaño mayor de las respuestas NXDOMAIN no se convierte en etiqueta.

## Flow diferido ajeno al PCAP causal

EVE contiene un `flow` DNS emitido a `21:01:12.752116`, antes del escenario. Su propio registro declara inicio/fin `20:56:10.267236–20:56:10.267970`, puerto Cliente 36492, dos paquetes, razón `timeout`, `alerted=false`. Corresponde al probe DNS del preflight y fue publicado unos cinco minutos después.

Ese flow no aparece en el PCAP, cuya primera trama es de `21:01:40.950859`, y no entra a las features: el extractor usa las 44 observaciones de paquete y los eventos DNS atribuibles, no eventos `flow`. La quietud de 70 s no drenó un timeout de aproximadamente cinco minutos. Se conserva en EVE sin borrarlo y limita la afirmación de que el slice sea exclusivamente causal; no contamina la fila numérica observada.

## Feature y repetibilidad

El extractor produjo una fila elegible con historia de 60 s:

```text
packet_count_10s=44
flow_attempt_count_30s=22
dns_query_count_60s=22
packet_rate_10s=4.40000000
byte_rate_10s=374.80000000
mean_ip_len_10s=85.18181818
unique_dst_ip_ratio_30s=1/22=0.04545455
flow_attempt_rate_10s=2.20000000
unique_dst_port_ratio_30s=1/22=0.04545455
dns_nxdomain_ratio_60s=2/22=0.09090909
```

`application_observations=24` significa 22 queries más dos marcadores NXDOMAIN internos; no son 24 transacciones. PCAP/EVE contienen 22 transacciones y 44 mensajes/paquetes.

El vector de catorce features coincide decimal y exactamente con R01, R02 y R03. Artefactos, tiempos, puertos e IDs DNS son independientes, pero R04 añade una coincidencia train↔validation `seen`. Se conserva la fila y se reportará estratificada; no se recalibra ni modifica el modelo durante R04.

## Sensor, recursos e integridad

Suricata incrementó 44 paquetes, igual que PCAP; no hubo diferencia +4 en esta campaña. `kernel_drops`, `kernel_ifdrops`, `decoder_invalid` y `alert_queue_overflow` permanecieron en cero, sin reset y con checkpoint EVE completo.

El muestreador produjo 53 filas: CPU 0–2.03 %, RSS 781,720 KiB, memoria disponible 14,092,488–14,166,152 KiB y load1 0.01–0.09. Los stderr de escenario/muestreo están vacíos. Ambos bundles SHA-256 y la copia PCAP remoto/local pasaron completos.

## Auditoría y decisión

El auditor limpio aceptó 90/145, R04 3/29, 55 faltantes, cero inválidas/advertencias, 19 coincidencias entre campañas y dos cruces train↔validation: `DNS-VALID-10/R04` y esta campaña. `ready_to_build=false` corresponde sólo a F1 incompleta.

**F1N-DNS-MIXED-20-2-R04 ACEPTADA CON LIMITACIONES.** Se valida el error DNS benigno `2/22`, la integridad causal del PCAP/features y el segundo vector visto; EVE conserva un flow de preflight diferido fuera del PCAP. Claude confirmó que no altera las features. No hay scoring. Siguiente autorizado: sólo preflight de `F1N-DNS-MIXED-50-10-R04`.
