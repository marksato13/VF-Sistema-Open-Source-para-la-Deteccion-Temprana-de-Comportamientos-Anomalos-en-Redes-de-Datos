# Vigesimonoveno canario oficial R03 — MIXED-LIGHT

Fecha: 4 de agosto de 2026. Campaña: `F1N-MIXED-LIGHT-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La última celda R03 combina concurrentemente tres cargas legítimas desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`: HTTP 100 MB limitado a 5 MB/s, iperf3 TCP a 50 Mbit/s durante 10 s y veinte consultas DNS válidas. Su finalidad es observar conjuntamente volumen y comportamiento L3/L4/L7; no reproduce diversidad de hosts ni tráfico productivo aleatorio.

El dry-run fijó `experiment/train`, commit limpio y sincronizado `2034dcfa82088c72218108fae541c342f5c52620`, quietud/warm-up/settle/cooldown `70/60/9/30 s`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.

El volumen oficial pasó con 128,163,131,392 bytes disponibles. NTP pasó en cinco nodos con máximo absoluto 3.020 ms y SSH 4/4. Las cuatro NIC externas estaban `DOWN` por MAC, el bypass `172.17.25.111–114` quedó bloqueado por ICMP/TCP22 y las rutas atravesaban el Sensor. NGINX, dnsmasq, iperf3, firewall y Suricata estaban activos; captura e ID libres; drops, `ifdrops`, decoder y overflow estaban en cero.

El archivo de 100 MB, su hash y HEAD pasaron; DNS resolvió `server.ppi.lab` como `10.30.0.10`. El sondeo iperf3 transfirió 6,291,456 bytes iguales por extremo a unos 50 Mbit/s, sin retransmisiones. El generador local/remoto coincidió en `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`. Los sondeos ocurrieron antes de los 70 s de quietud y Claude autorizó una ejecución.

## Resultado por componente

El escenario terminó con código cero y stderr vacío.

| Componente | Resultado |
|---|---|
| HTTP | 200; 104,857,600 bytes; 19.507751 s; 5,375,176 B/s |
| iperf3 TCP emisor | 62,521,344 bytes; 50.009894 Mbit/s; 10.001436 s; una retransmisión |
| iperf3 TCP receptor | 62,521,344 bytes; 50.001435 Mbit/s; 10.003128 s |
| DNS | 20 respuestas en la salida; EVE: 20 solicitudes + 20 respuestas `NOERROR` |

Los bytes iperf3 coinciden entre extremos. La retransmisión se conserva como observación legítima sin atribuir causa. EVE confirma veinte consultas `server.ppi.lab/A` y respuestas `10.30.0.10`.

## Concurrencia demostrada

Un parser de solo lectura del PCAP clásico reconstruyó tres conexiones TCP y veinte pares DNS:

| Flujo | Inicio epoch | Diferencia frente al primero | Paquetes / span |
|---|---:|---:|---:|
| iperf control `58792→5201` | 1785887955.044801 | 0 ms | 27 / 10.020541 s |
| iperf datos `58794→5201` | 1785887955.058640 | 13.839 ms | 45,305 / 10.007106 s |
| HTTP `36334→80` | 1785887955.062793 | 17.992 ms | 76,977 / 19.508564 s |
| primer DNS `→53` | 1785887955.074512 | 29.711 ms | 40 / 0.531612 s para 20 pares |

El GET HTTP apareció a +20.712 ms. Desde la primera consulta hasta la última respuesta, los tres componentes coexistieron 0.531612 s. HTTP e iperf3 datos coexistieron aproximadamente 10.003 s por los límites de sus flujos, o 10.000 s desde el GET hasta el cierre de datos. Esto acredita solapamiento temporal; no prueba interacción causal ni independencia estadística.

Cada conexión TCP contiene 1 SYN, 1 SYN/ACK, 2 FIN y 0 RST. La composición total se reconcilia: 27 + 45,305 + 76,977 = 122,309 TCP, más 40 UDP DNS, igual a 122,349 paquetes.

## PCAP, EVE y contaminación controlada

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 177,535,700 |
| Capturados / recibidos / parseados | 122,349 / 122,349 / 122,349 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 122,351 / 122,349 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 58 / 58, mismo inode |
| Muestras Sensor / stderr | 74 / vacío |
| Lock / captura residual | ausente / inactiva |

El delta Suricata `+2` no tiene causa identificada. Los 58 registros EVE son trece `stats`, cuarenta DNS, un HTTP, un `fileinfo`, una alerta permitida SID `2260003`, una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED` y un `flow`. La alerta/anomalía corresponde al control iperf3 y no se etiqueta como ataque. `fileinfo` quedó `TRUNCATED` en 102,400 bytes: limita el seguimiento de archivo de Suricata, no el conteo curl ni la integridad del PCAP.

El `flow` adicional conserva un DNS de preflight, puerto origen 46229: comenzó y terminó a las `18:53:30`, y Suricata lo emitió por timeout a las `18:58:40` durante el warm-up. EVE no quedó libre de preflight. Sin embargo, el PCAP contiene paquetes únicamente entre `18:59:15.044801` y `18:59:34.571357`; sus veinte DNS y un HTTP son las 21 observaciones de aplicación del escenario. El extractor no usa ese `flow` diferido como observación de aplicación y deriva los intentos desde el PCAP. Por tanto, el rastro se conserva documentalmente pero no contamina estas features.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 6,432 | 5.2571 % |
| De 500 a 1500 bytes | 115,917 | **94.7429 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 115,404 | 94.3236 % |

La longitud media fue 1,421.06 y la máxima, 1,500. Esto aporta tráfico pesado benigno del laboratorio, no representatividad poblacional.

## Features y recursos

El extractor procesó 122,349 paquetes, obtuvo 21 observaciones de aplicación y produjo tres filas elegibles:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | HTTP | DNS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `23:59:20` | 57,931 | 7,906,803.6 B/s | 0.90863268 | 23 | 3 | 1 | 20 |
| `23:59:30` | 59,343 | 8,722,920.2 B/s | 0.98127833 | 23 | 0 | 1 | 20 |
| `23:59:40` | 5,075 | 756,796.8 B/s | 0.99448276 | 23 | 0 | 1 | 20 |

Las filas suman el PCAP. Los 23 intentos representan veinte flujos UDP DNS y tres conexiones TCP; la primera fila tiene completion 1. Las filas posteriores conservan historia causal de 30/60 s. HTTP errors y DNS NXDOMAIN son cero. Ningún vector coincide exactamente con R01/R02. Las tres filas pertenecen a un episodio y están autocorrelacionadas; no son tres repeticiones independientes.

El Sensor registró CPU máxima 17.59 %, RSS máxima 781,720 KiB, memoria disponible entre 14,034,640 y 14,161,960 KiB y carga entre 0.05 y 0.30. No se aplica un SLA ni umbral de capacidad.

## Comparación R01/R02/R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| HTTP bytes | 104,857,600 | 104,857,600 | 104,857,600 |
| iperf3 bytes por extremo | 62,521,344 | 62,521,344 | 62,521,344 |
| DNS respuestas / filas | 20 / 3 | 20 / 3 | 20 / 3 |
| HTTP duración | 19.517769 s | 19.504571 s | 19.507751 s |
| Retransmisiones iperf3 | 2 | 0 | 1 |
| PCAP paquetes / bytes | 122,802 / 177,537,599 | 123,919 / 177,624,489 | 122,349 / 177,535,700 |
| Menores de 500 | 6,910 | 8,032 | 6,432 |
| De 500 a 1500 | 115,892 | 115,887 | 115,917 |
| Ratio 500–1500 | 94.3731 % | 93.5183 % | 94.7429 % |
| Exactamente 1500 | 115,381 | 115,381 | 115,404 |
| EVE | 57 | 57 | 58 |

Los payloads y resultados de aplicación se conservan. El evento EVE adicional R03 está identificado. Las diferencias restantes de paquetes, ratios, duración y retransmisiones no reciben causa sin una prueba específica; no demuestran tendencia.

## Integridad y decisión

```text
manifest              dba522c7ced095cfbc628d0ef6acab07a2aed47b44c4f0bbbe0b2a90c23f789d
pcap                  b0f7e68d971b04201f1b44db67acdc4352d9c758d7a2550d84e1f69a36dddcda
eve                   1a39bdc246f9dab6480e67fd70206efd27f5b2bf4236498a14d939c8da95dd14
campaign SHA256SUMS   57a50bc41e33d8e96e0503c00ab9f30ea4e6aabd6d0d55b354299252b6e90ac0
features CSV          576eba0805125dd2e387182c68fee27553ae84d6767a8e1bcc5a2a94224e08e0
extraction report     45c98dd434d76c31cf831fbd314ef7c79c9a82698e5c27da6b4588f5d435b6f5
feature SHA256SUMS    2507c8d5d6e3b2507190bc404932eaa08f265a49db3c9e923616f64186fc12d3
ledger                58299b83dfc3780490d19e4220f1b220adb70359d1e15639c79b2af79eebb100
```

Todos los hashes pasaron. El ensamblador aceptó 87/145, cerró R03 29/29 y dejó 58 faltantes R04/R05; cero inválidas/advertencias, diecisiete duplicados exactos dentro de `train` sin incremento y cero cruzados. `ready_to_build=false` porque faltan dos repeticiones.

Claude emitió **ACEPTAR CON LIMITACIONES**. Se corrigió su línea base de siete duplicados al estado vigente de diecisiete y no se adoptó una atribución causal a fase UTC.

**F1N-MIXED-LIGHT-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: únicamente auditoría agregada de cierre R03; no iniciar R04.
