# Vigesimonoveno canario oficial R04 — MIXED-LIGHT

Fecha: 6 de agosto de 2026. Campaña `F1N-MIXED-LIGHT-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La última celda R04 combina concurrentemente tres cargas legítimas desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`: HTTP 100 MB limitado, iperf3 TCP a 50 Mbit/s durante 10 s y veinte consultas DNS válidas. Su finalidad es observar conjuntamente volumen y comportamiento L3/L4/L7; no reproduce diversidad de hosts ni tráfico productivo aleatorio.

El dry-run fijó escenario `mixed-light`, argumentos vacíos, estimación de 200,000,000 bytes, matriz SHA-256 `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.

El preflight continuo pasó entre `18:06:24.589` y `18:06:47.851 -05:00` sobre commit limpio y sincronizado `b09e2601ad2448240566776fd2a77560826ec02f`. Pasaron contrato/almacenamiento con 121,643,053,056 bytes libres, NTP 5/5 con máximo absoluto 8.638 ms dentro del gate de 10 ms, SSH e identidades, NIC externas `DOWN`, bypass bloqueado, rutas por Sensor, Suricata/captura, listener iperf exclusivo y ocioso, iperf 3.20, DNS/ICMP y generador. Log SHA-256 `03a4d6f8595002e6d4940821a5ed7d7a16eb48ac103fb59180f4c08c398846e1`. Claude autorizó exactamente una ejecución; no hubo reintento ni scoring.

## Resultado por componente

El escenario terminó con código cero y stderr vacío.

| Componente | Resultado |
|---|---|
| HTTP | 200; 104,857,600 bytes; 19.506684 s; 5,375,470 B/s |
| iperf3 TCP emisor | 62,521,344 bytes; 50.009319 Mbit/s; 10.001551 s; una retransmisión |
| iperf3 TCP receptor | 62,521,344 bytes; 49.998201 Mbit/s; 10.003775 s |
| DNS | 20 respuestas en salida; EVE: 20 solicitudes + 20 respuestas `NOERROR` |

Los bytes TCP coinciden entre extremos. La retransmisión se conserva como observación legítima sin atribuir causa. Los veinte IDs DNS fueron únicos en cada sentido y todas las respuestas incluyeron `server.ppi.lab A 10.30.0.10`.

## Concurrencia demostrada

El PCAP reconstruye tres conexiones TCP y veinte pares DNS:

| Flujo | Inicio epoch | Diferencia frente al primero | Paquetes / span |
|---|---:|---:|---:|
| iperf control `35850→5201` | 1786057803.884940 | 0 ms | 27 / 10.015806 s |
| iperf datos `35864→5201` | 1786057803.889380 | 4.440 ms | 45,432 / 10.011036 s |
| HTTP `43990→80` | 1786057803.910755 | 25.815 ms | 76,134 / 19.507744 s |
| primer DNS `→53` | 1786057803.918679 | 33.739 ms | 40 / 0.465199 s para 20 pares |

Desde la primera consulta hasta la última respuesta los tres componentes coexistieron 0.465199 s. HTTP e iperf datos coexistieron 9.989661 s según sus límites de flujo. Esto demuestra solapamiento temporal, no interacción causal ni independencia estadística.

Cada conexión TCP contiene 1 SYN, 1 SYN/ACK, 2 FIN y 0 RST. La composición se reconcilia exactamente: 27 + 45,432 + 76,134 = 121,593 TCP, más 40 UDP DNS, igual a 121,633 paquetes.

## PCAP, EVE y features

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 177,458,172 |
| Capturados / recibidos / parseados | 121,633 / 121,633 / 121,633 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 121,635 / 121,633 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 57 / 57, mismo inode |
| Muestras Sensor / stderr | 75 / vacío |
| Lock / captura residual | ausente / inactiva |

El delta Suricata +2 queda sin causa atribuida. Los 57 registros EVE son trece `stats`, cuarenta DNS, un HTTP, un `fileinfo`, una alerta permitida SID `2260003` y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED`. Alerta/anomalía corresponden a clasificación L7 del flujo iperf3 y no se etiquetan como ataque. No existe `flow` diferido: la quietud drenó los probes.

`fileinfo` quedó `TRUNCATED` en 102,400 bytes: limita el seguimiento de archivo de Suricata, no el conteo curl, los bytes TCP ni la integridad del PCAP.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 5,729 | 4.7101 % |
| De 500 a 1500 bytes | 115,904 | **95.2899 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 115,390 | 94.8690 % |

La longitud media fue 1,428.96 bytes y la máxima, 1,500. Es tráfico pesado benigno del laboratorio, no representatividad poblacional.

| Fin UTC | Paquetes | Byte rate | Ratio grande | Attempts | SYN | HTTP | DNS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `23:10:10` | 63,797 | 8,859,927.6 | 0.92540402 | 23 | 3 | 1 | 20 |
| `23:10:20` | 54,197 | 7,989,137.4 | 0.98385519 | 23 | 0 | 1 | 20 |
| `23:10:30` | 3,639 | 531,850.8 | 0.97389393 | 23 | 0 | 1 | 20 |

Las filas suman 121,633; las 21 observaciones de aplicación son un HTTP y veinte queries DNS. Los 23 intentos son veinte flujos UDP DNS y tres conexiones TCP. Las filas posteriores conservan historia causal de 30/60 s; pertenecen a un episodio y no son tres muestras independientes. Ningún vector de catorce features coincide exactamente con R01, R02 o R03.

## Comparación y recursos

| Métrica | R01 | R02 | R03 | R04 |
|---|---:|---:|---:|---:|
| HTTP bytes | 104,857,600 | 104,857,600 | 104,857,600 | 104,857,600 |
| iperf bytes por extremo | 62,521,344 | 62,521,344 | 62,521,344 | 62,521,344 |
| DNS respuestas / filas | 20 / 3 | 20 / 3 | 20 / 3 | 20 / 3 |
| HTTP duración | 19.517769 s | 19.504571 s | 19.507751 s | 19.506684 s |
| Retransmisiones | 2 | 0 | 1 | 1 |
| PCAP paquetes | 122,802 | 123,919 | 122,349 | 121,633 |
| PCAP bytes | 177,537,599 | 177,624,489 | 177,535,700 | 177,458,172 |
| Paquetes 500–1500 | 115,892 | 115,887 | 115,917 | 115,904 |
| Ratio 500–1500 | 94.3731 % | 93.5183 % | 94.7429 % | 95.2899 % |
| EVE | 57 | 57 | 58 | 57 |

Los resultados de aplicación se conservan. R03 tuvo un `flow` diferido identificado; R04 no. Las diferencias de paquetes, ratio, duración y retransmisiones no reciben causa sin prueba específica ni demuestran tendencia.

El Sensor registró CPU 0–15.76 %, RSS estable en 782,504 KiB, memoria disponible 14,063,400–14,152,396 KiB y load1 0.08–0.39. No existe un SLA ni umbral formal de suficiencia.

## Hashes, auditoría y decisión

```text
manifest              4bedebfe070bc43e0f48b3ed276122ef4ade8aa267d21519f31778085fdc7a29
pcap                  2643d38e76454174cb5521499d640b63e4475e1dd963440084f8d45831684d44
eve                   e7d0c147ac6cb56295b0111482e153306147fa12afefa16e401acfec78badfe0
campaign SHA256SUMS   7f2ab056d190dc5183c75081ec09c5ef8457dfc3a818f9ace195d8871cbd7a13
features CSV          0af4ab9e4813da93f60d5406e311a48127efdc35cb3977f19a993009c87601cb
extraction report     fc46c8af5332312fc6d986cd2bcefa7d705f579cb9750240dedcf627ff232d52
feature SHA256SUMS    77a8c6b50e38cec8d27eea9ec992ae0d743a41ffe2d4433908ad9ce7b815582e
ledger                971d89922a12367873cba5d00949328ccfecbeb768abcd0a3df84b774049d284
```

Ambos bundles y el listado remoto del PCAP pasaron. El auditor limpio aceptó 116/145, cerró R04 29/29 y dejó sólo las 29 celdas R05; 27 coincidencias totales y diez cruces sin incremento, cero inválidas/advertencias. `ready_to_build=false` porque R05 sigue sellada.

Claude emitió **ACEPTAR CON LIMITACIONES** sin contradicciones en la evidencia primaria. Su sesión sólo lectura no pudo verificar el JSON agregado no persistido; Codex lo ejecutó y capturó aparte. Las limitaciones son el delta +2, alerta/anomalía L7 permitida, fileinfo truncado, una retransmisión, ventanas correlacionadas y alcance virtualizado. **F1N-MIXED-LIGHT-R04 queda cerrada y R04 completa 29/29.** Siguiente autorizado: únicamente auditoría agregada de cierre R04; no iniciar R05, calibración ni scoring hasta publicar ese gate.
