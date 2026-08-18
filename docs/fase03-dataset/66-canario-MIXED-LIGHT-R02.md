# Vigesimonoveno canario oficial R02 — MIXED-LIGHT

Fecha: 28 de julio de 2026. Campaña: `F1N-MIXED-LIGHT-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La última celda R02 combina concurrentemente tres cargas legítimas desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`: HTTP 100 MB limitado a 5 MB/s, iperf3 TCP a 50 Mbit/s durante 10 s y veinte consultas DNS válidas. Su finalidad es observar conjuntamente volumen y comportamiento L3/L4/L7; no reproduce toda la diversidad o aleatoriedad de una red productiva.

El preflight confirmó Git limpio y sincronizado en `50f3ccded641b146b0fd43cf60d9b75913e32bdd`, ID y lock libres, almacenamiento oficial `PASS` y 134,683,660,288 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 0.552 ms.

Suricata estaba activo y sus contadores previos de drops e `ifdrops` eran cero. NGINX, dnsmasq e iperf3 estaban activos; HTTP devolvió salud correcta, DNS resolvió `server.ppi.lab` como `10.30.0.10` y un control iperf3 de un segundo entregó 131,072 bytes iguales con cero retransmisiones. El generador local y remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

Las rutas Cliente→Servidor y Servidor→Cliente atravesaban el Sensor. Las cuatro NIC externas estaban `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22. Los 70 s de quietud drenaron los sondeos antes de abrir la evidencia oficial.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `mixed-legitimate` / `mixed-light` |
| Argumentos | ninguno |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## Resultado por componente

El escenario terminó con código cero y stderr vacío.

| Componente | Resultado |
|---|---|
| HTTP | 200; 104,857,600 bytes; 19.504571 s; 5,376,052 B/s |
| iperf3 TCP emisor | 62,521,344 bytes; 50.009209 Mbit/s; 10.001573 s; cero retransmisiones |
| iperf3 TCP receptor | 62,521,344 bytes; 50.005839 Mbit/s; 10.002247 s |
| DNS | 20 respuestas en la salida; EVE: 20 solicitudes + 20 respuestas `NOERROR` |

Los bytes iperf3 coinciden entre extremos. EVE confirma que las veinte consultas fueron `server.ppi.lab/A` y que las respuestas resolvieron `10.30.0.10`.

## Concurrencia demostrada

El PCAP permite reconstruir el inicio de cada flujo:

| Flujo | Inicio epoch | Diferencia frente al primero | Span observado |
|---|---:|---:|---:|
| iperf control `57314→5201` | 1785298726.978369 | 0 ms | 10.011656 s |
| iperf datos `57316→5201` | 1785298726.983309 | 4.940 ms | 10.007358 s |
| primer DNS `→53` | 1785298727.005605 | 27.236 ms | 0.441626 s para los 20 pares |
| HTTP `51350→80` | 1785298727.013401 | 35.032 ms | 19.505108 s |

Los tres componentes comenzaron dentro de 35.032 ms. El intervalo común HTTP+iperf3+DNS fue aproximadamente 0.433830 s, desde el inicio HTTP hasta la última respuesta DNS; HTTP e iperf3 coexistieron unos 9.977266 s. Esto acredita concurrencia real, no independencia estadística ni mezcla productiva aleatoria.

## PCAP, EVE y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 123,919 / 123,919 / 123,919 |
| PCAP | 1 archivo / 177,624,489 bytes |
| TCP / UDP | 123,879 / 40 paquetes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 123,921 / 123,919 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 57 / 57 |
| Transferencia / límite PCAP | verificada / no alcanzado |

El delta Suricata supera al PCAP en dos paquetes. No existe una tolerancia contractual ni se atribuye causa; ambos puntos conservan cero drops y el contrato de evidencia pasa por igualdad capturado=recibido=parseado, no por igualdad entre contadores de herramientas distintas. Los 148 bytes de `pcap-validation.stderr` son el banner de lectura de tcpdump y las fallas registradas son cero. El muestreador tuvo stderr vacío.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 8,032 | 6.4817 % |
| De 500 a 1500 bytes | 115,887 | **93.5183 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 115,381 | 93.1100 % |

La longitud media fue 1,403.39 bytes y la máxima, 1,500. El episodio aporta tráfico pesado legítimo junto con señales de aplicación; no demuestra representatividad poblacional ni convierte tamaño en etiqueta.

EVE contiene trece `stats`, cuarenta DNS, un HTTP, un `fileinfo`, una alerta permitida SID `2260003` y una anomalía `APPLAYER_PROTO_DETECTION_SKIPPED` sobre el control iperf3. `fileinfo` quedó en 102,400 bytes con estado `TRUNCATED`: limita el seguimiento del archivo por Suricata, no la descarga acreditada por curl ni la integridad del PCAP. La alerta/anomalía se conserva como telemetría y no se etiqueta como ataque.

El Sensor produjo 75 muestras: CPU máxima 17.30 %, RSS 781,816 KiB, memoria disponible mínima 14,076,144 KiB y carga máxima 0.50. No se aplica un umbral de recursos.

## Features

El extractor procesó 123,919 paquetes, obtuvo 21 observaciones de aplicación —veinte consultas DNS y una solicitud HTTP— y produjo tres filas elegibles correlacionadas:

| Fin UTC | Paquetes | Byte rate | Large ratio | Attempts | SYN | HTTP | DNS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `04:18:50` | 47,846 | 6,190,427.2 B/s | 0.85904778 | 23 | 3 | 1 | 20 |
| `04:19:00` | 67,788 | 9,963,824.3 B/s | 0.98161917 | 23 | 0 | 1 | 20 |
| `04:19:10` | 8,285 | 1,236,438.0 B/s | 0.99493060 | 23 | 0 | 1 | 20 |

Los 23 intentos representan veinte flujos UDP DNS, una conexión HTTP y las conexiones de control/datos iperf3. La primera fila contiene tres SYN con `syn_completion_ratio_10s=1`. Hay un destino IP y tres puertos destino, por lo que `unique_dst_ip_ratio_30s=1/23` y `unique_dst_port_ratio_30s=3/23`. `dns_nxdomain_ratio_60s=0/20` y `http_error_ratio_60s=0`.

Las filas segunda y tercera conservan historia causal de 30/60 s aunque ya no contengan SYN nuevos. Las tres proceden de un único episodio y no son observaciones i.i.d. La campaña ejercita señales L3/L4/L7 y tráfico pesado benigno, pero por sí sola no prueba que el futuro Isolation Forest generalice.

## Comparación R01↔R02

R01 y R02 preservan los mismos bytes HTTP e iperf3, veinte consultas DNS, 115,381 paquetes de 1,500 bytes, 57 eventos EVE y tres filas. Ningún vector de 14 features coincide exactamente entre ambas campañas.

| Métrica | R01 | R02 | R02 − R01 |
|---|---:|---:|---:|
| HTTP bytes | 104,857,600 | 104,857,600 | 0 |
| iperf3 bytes emisor/receptor | 62,521,344 / 62,521,344 | 62,521,344 / 62,521,344 | 0 / 0 |
| Retransmisiones iperf3 | 2 | 0 | −2 |
| Paquetes PCAP | 122,802 | 123,919 | +1,117 (+0.909594 %) |
| Bytes archivo PCAP | 177,537,599 | 177,624,489 | +86,890 (+0.048942 %) |
| TCP / UDP | 122,762 / 40 | 123,879 / 40 | +1,117 / 0 |
| Menores de 500 | 6,910 | 8,032 | +1,122 |
| De 500 a 1500 | 115,892 | 115,887 | −5 |
| Proporción 500–1500 | 94.3731 % | 93.5183 % | −0.8548 puntos |
| Exactamente 1500 | 115,381 | 115,381 | 0 |
| EVE / filas | 57 / 3 | 57 / 3 | 0 / 0 |

La redistribución de paquetes TCP y de ventanas explica que las features no sean idénticas, pero no se atribuye a retransmisiones, ACK, segmentación, temporización u otra causa sin una prueba específica. CPU máxima cambió 20.69→17.30 %, RSS 780,308→781,816 KiB, memoria mínima 13,908,744→14,076,144 KiB y carga 0.37→0.50; son observaciones, no tendencia.

## Integridad raíz

```text
manifest.json          c203c043ee357558342941ecf41cb85125224d6fdab78ae94327e6436a3334cf
capture.pcap0          b093bae22bac135089cf1074c0510f6860dea22931e6095b7ea4e2756ca3bc05
eve-slice              df9970b5ef2879b522d7205c32bb3752f86f5ab95a507c1432e38a39c8571241
campaign SHA256SUMS    81df5ee6c080ac255f0905d2253098ad8d6e46823668c5cc494f2aea8fb65bf8
multilayer-v1.csv      0446717c3f411e2818f4e3b9891c3ebd86ce3bf7452e6ffa4bb8d5c56d04ab75
extraction-report      d9363da1aa6bdd2a747ef9dbcd3addd7f35567ac45b1dda3583f9a7eb94a923a
feature SHA256SUMS     da86e2ca4adcc820e2279b074a08c0aeb6e3e2239511ccf66b6fbaa6eecb4a86
ledger                 4a0ba40bd3a818c18eb184bf5c4641a341767217ac5a06d8d65babed6dd0a56d
```

El ensamblador aceptó 58/145 campañas: R02 29/29, 87 faltantes globales, cero inválidas/advertencias, una calibración excluida, siete coincidencias exactas dentro de `train` y cero entre particiones. MIXED-LIGHT no añadió coincidencias. El dataset global no se construye porque faltan R03–R05.

Claude aceptó con limitaciones. Se corrigieron solapamientos, tolerancia y causalidad inventadas, normalidad de retransmisiones, independencia/contaminación no probadas, probabilidad de falsos negativos, cálculo de filas y propuestas Pearson/AUC sin diseño.

**F1N-MIXED-LIGHT-R02 ACEPTADA CON LIMITACIONES.** Completa las 29/29 celdas de R02 con captura íntegra y señales conjuntas L3/L4/L7. Siguiente: auditoría agregada de cierre R02; no iniciar R03.
