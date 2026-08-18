# Vigesimoctavo canario oficial R04 — UDP 50 Mbit/s

Fecha: 6 de agosto de 2026. Campaña `F1N-UDP-50M-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Un flujo UDP benigno de iperf3 a 50 Mbit/s durante 20 s, desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201` a través del Sensor. Usa bloques de 1,448 bytes, representa el techo UDP calibrado de F1 y aporta tráfico grande legítimo L3/L4; no representa un SLA ni una aplicación productiva.

El dry-run válido fijó argumentos `["50M","20"]`, estimación de 140,000,000 bytes, matriz SHA-256 `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA-256 `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f`. Un dry-run anterior sin `PPI_ARTIFACTS_ROOT` marcó correctamente almacenamiento no oficial y no escribió estado. La primera invocación directa del helper fue rechazada por permiso de ejecución antes de iniciar; no creó log ni tocó las VM. Se repitió el mismo helper explícitamente con Bash.

El preflight continuo válido pasó entre `17:48:37.514` y `17:49:01.390 -05:00` sobre commit limpio y sincronizado `f072b4ff65709c1d604111648509a6b06a04b170`. Pasaron contrato/almacenamiento con 121,773,305,856 bytes libres, NTP 5/5 con máximo absoluto 4.969 ms, SSH e identidades, NIC externas `DOWN`, bypass bloqueado, rutas por Sensor, Suricata/captura, listener iperf exclusivo y ocioso, iperf 3.20, probes y generador. Log SHA-256 `2067e08d6571285181364d5d231fac69d0f0cb106fdf458404865b49fbd59ce0`. Claude autorizó exactamente una ejecución, condicionada a comparar extremos y secuencia binaria; no hubo reintento ni scoring.

## Resultado iperf3 y discrepancia reproducida

| Métrica | Emisor | Receptor | Diferencia |
|---|---:|---:|---:|
| Bytes | 125,004,392 | 125,002,944 | −1,448 |
| Datagramas | 86,329 | 86,328 | −1 |
| Duración | 20.000970 s | 20.001742 s | +0.000772 s |
| Bitrate | 49.999332 Mbit/s | 49.996823 Mbit/s | −0.002509 Mbit/s |
| Desviación nominal | −0.001336 % | −0.006354 % | — |
| Jitter | 0 ms | 0.031097 ms | — |

El déficit receptor es un bloque completo y equivale a 0.001158359 % de los 86,329 datagramas enviados. Sin embargo, iperf3 3.20 declara simultáneamente `lost_packets=0`, `lost_percent=0` y `out_of_order=0`. Esos campos contradicen los totales de `sum_sent`/`sum_received` y no se usan para afirmar pérdida cero de extremo.

La auditoría binaria de sólo lectura encontró en el PCAP los IDs `1..86,329`: todos únicos, consecutivos y ordenados, sin faltantes ni duplicados. El Sensor observó todo lo enviado; esto prueba conservación de evidencia en ese punto, pero no demuestra que el proceso iperf3 del Servidor contabilizara el último datagrama.

R04 reproduce la contradicción de un datagrama de R02; R03 no la reprodujo. Es compatible con cierre/procesamiento tardío o un defecto de reporte ya discutido en R02, pero ninguna evidencia permite distinguir pérdida en tránsito, kernel, aplicación o contabilidad. No se atribuye causa.

## Integridad, EVE y features

El PCAP reconcilia 86,329 datagramas de datos, dos UDP de inicialización de cuatro bytes y 27 paquetes TCP de control: 86,358 paquetes. El control TCP `35000` tuvo 1 SYN, 1 SYN/ACK, 2 FIN, 0 RST y span 20.004891 s.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 86,358 / 86,358 / 86,358 |
| PCAP | 1 archivo / 130,014,693 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 86,362 / 86,358 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 86,329 / 86,358 (99.9664 %) |
| longitud media / máxima | 1,475.53 / 1,476 bytes |

El delta Suricata +4 queda sin causa atribuida. El PCAP supera los bytes UDP enviados en 5,010,301 bytes (4.008100 %) por cabeceras, inicialización, control y estructura; no mide pérdida. La discrepancia de aplicación y los drops de observación son controles diferentes.

EVE contiene trece `stats`, sin `flow`, `alert` ni observaciones de aplicación. Los 70 segundos de quietud drenaron los probes de preflight. Esta celda aporta carga y comportamiento L3/L4, no semántica L7; la ausencia de alertas no prueba benignidad.

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | SYN / completion |
|---|---:|---:|---:|---:|---:|---:|
| `22:55:20` | 11,438 | 1,143.8 | 1,685,986.8 | 1,474.0224 | 0.99860115 | 1 / 1 |
| `22:55:30` | 43,163 | 4,316.3 | 6,370,858.8 | 1,476.0000 | 1.00000000 | 0 / 0 |
| `22:55:40` | 31,757 | 3,175.7 | 4,685,545.9 | 1,475.4372 | 0.99959064 | 0 / 0 |

Las tres ventanas correlacionadas suman 86,358. La fila interior coincide exactamente en las catorce features con la fila interior de R01; ninguna fila coincide con R02 ni R03. Se conserva como vector `seen` train↔validation, sin deduplicación post hoc.

| Repetición | Emisor / receptor | Jitter receptor | Paquetes PCAP |
|---|---:|---:|---:|
| R01 | 86,331 / 86,331 | 0.132158 ms | 86,364 |
| R02 | 86,331 / 86,330 | 0.099880 ms | 86,360 |
| R03 | 86,329 / 86,329 | 0.104768 ms | 86,359 |
| R04 | 86,329 / 86,328 | 0.031097 ms | 86,358 |

Dos de cuatro episodios exhiben el déficit receptor. Esto no demuestra frecuencia poblacional, tendencia ni causa. El Sensor produjo 72 muestras: CPU 0–4.41 %, RSS estable en 782,504 KiB, memoria disponible 13,949,964–14,165,740 KiB y load1 0.00–0.40. No existe umbral formal de suficiencia.

## Hashes, auditoría y decisión

```text
manifest              9cc9304ac1ad08fd5c3372ad41b14ca5c014619d23bc1135b0af61891bc1a9a4
pcap                  0e56b03e3694156bda188a7dc2fa9363526d28dfeb56735ae033689a927a498e
eve                   e43dfb167172bc307f3ca8e211319e09587d51c4f46b03cdabfa079860967ec4
campaign SHA256SUMS   a06c1e29f74b89f785d4c3197ecaf47187455029a3972e11d32ba2e46baabe7b
features CSV          213a928071a2031699cb1481ff66fd6a28a306ba5b8225980c98015e79b9dddf
extraction report     4755d3529b6e48ca79d76843deed7ad74c1ad8faf827396b38f5ef08b98ff376
feature SHA256SUMS    bf12e5fb7daa40eb5b6d4c1ad63036da8b7bbd731dc64938534b322d557ce488
ledger                87f2a593142404f0563ae77d5ba02799f8e99f61ae905906e429b0f5d54b6848
```

Ambos bundles y el listado remoto del PCAP pasaron. Captura y lock quedaron inactivos. El auditor limpio aceptó 115/145: R04 28/29, 30 faltantes, 27 coincidencias totales, diez cruces y cero inválidas/advertencias.

Claude emitió **ACEPTAR CON LIMITACIONES**. La aceptación cubre las features L3/L4 observadas en el Sensor, cuyo PCAP es íntegro; no permite afirmar entrega UDP íntegra extremo a extremo. Se conservan como limitaciones el déficit receptor no resuelto, los campos de pérdida contradictorios de iperf3 3.20, el delta Suricata +4 y el alcance virtualizado. **F1N-UDP-50M-R04 queda cerrada.** Siguiente autorizado: sólo preflight independiente de `F1N-MIXED-LIGHT-R04`; no su captura ni scoring.
