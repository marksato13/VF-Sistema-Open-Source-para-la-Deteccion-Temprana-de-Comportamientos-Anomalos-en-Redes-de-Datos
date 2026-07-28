# Decimosexto canario oficial R02 — TLS-SESSIONS-20

Fecha: 28 de julio de 2026. Campaña: `F1N-TLS-SESSIONS-20-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Veinte sesiones HTTPS legítimas, secuenciales y de corta duración contra `/health`. El perfil aporta churn de conexiones y sesiones TLS; no representa concurrencia ni diversidad de clientes, servidores o PKI.

El preflight confirmó Git limpio y sincronizado en `c7606c7aa6a1c0cc9b44badcef2abca6760a8da4`, ID libre, 137,392,971,776 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.573 ms. HTTPS devolvió 200 y `ssl_verify_result=18`, esperado para el certificado autofirmado. Servicios, captura, generador, rutas, aislamiento y Suricata pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumento | `https-sessions` / `20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `9246e824773fc95ffe7097ebf344e3aef5d4cd76329e4d39a4fd0e79eb8d75c4` |

## Conteos e integridad

El Cliente produjo veinte líneas `session=1..20`, todas con HTTP 200; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 144,356 |
| Capturados / parseados / drops | 430 / 430 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 30 / 30 |
| Stats / TLS / flow / HTTP / fileinfo | 10 / 20 / 0 / 0 / 0 |
| Delta Suricata / PCAP | 432 / 430 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos adicionales del contador Suricata no están identificados. `430/430` demuestra igualdad capturado/parseado, no un conteo teórico independiente.

EVE registra exactamente veinte TLS 1.3 entre `15:08:41.776756` y `15:08:44.229454` UTC, con veinte puertos origen distintos y los mismos JA3, JA3S y JA4. Esta igualdad es coherente con un solo Cliente y Servidor; no demuestra diversidad criptográfica ni de aplicaciones. Todos los hashes pasaron.

## Tamaños y feature

| Rango IPv4 | Paquetes |
|---|---:|
| Menores de 500 bytes | 368 |
| 500–1500 bytes | 62 (14.4186 %) |
| Exactamente 1500 bytes | 40 |
| Mayores de 1500 bytes | 0 |

La media IP fue 305.66 bytes y el máximo 1,500. El perfil es de sesiones cortas y no sustituye las campañas pesadas.

R02 produjo una fila elegible:

| Paquetes | Attempts / SYN | Attempt/SYN rate | IP/port ratio | SYN completion | TLS rate |
|---:|---:|---:|---:|---:|---:|
| 430 | 20 / 20 | 2.0 / 2.0 s⁻¹ | 0.05 / 0.05 | 1.0 | 0.33333333 |

`tls_session_rate_60s=20/60`, una tasa, no un porcentaje. Los ceros HTTP significan opacidad por cifrado. `large_ip_ratio_10s=0.14418605` sí es observable porque se calcula desde PCAP.

## Comparación R01

| Métrica | R01 | R02 |
|---|---:|---:|
| Salidas HTTP 200 / TLS EVE | 20 / 20 | 20 / 20 |
| PCAP capturados / delta Suricata | 431 / 433 | 430 / 432 |
| Paquetes 500–1500 | 60 (13.9211 %) | 62 (14.4186 %) |
| Exactamente 1500 | 40 | 40 |
| Duración PCAP | 2.473437 s | 2.468210 s |
| Filas | 2 | 1 |

R01 transcurrió de `04:07:48.074516` a `04:07:50.547953` UTC, cruzó el borde y produjo filas de 324/107 paquetes con tasas TLS 15/60 y 20/60. R02 transcurrió de `15:08:41.762365` a `15:08:44.230575`, quedó dentro de una ventana y produjo una fila de 430 con 20/60. Ningún vector coincide exactamente.

La única fila R02 pertenece a un episodio concentrado; no se describe como autocorrelación entre filas. Los artefactos R01/R02 son independientes y ambas campañas están en `train`.

El Sensor produjo 55 muestras: CPU máxima 1.52 %, RSS 780,308 KiB, memoria disponible mínima 14,071,096 KiB y carga máxima 0.25.

## Integridad raíz

```text
manifest.json          5b5b2679805f9724427712734de93fcadc035e1df2be8666998203b049dbdfb6
capture.pcap0          5c5f321ac1e80d1c938d78cb6fd34d0c2b26f925bf81d1c04cdff856325ba694
eve-slice              11ea50143b5cae375e4598ee7a60d48462dd6f3b966f68f165461592d2f06df3
campaign SHA256SUMS    a9483353adfab467c5a636a7ec3cc413f939c8fc67ffdf833cdb842ce1f77eae
multilayer-v1.csv      0a9d0aae33e3292671a9ce6efa47bf6036ed93ae517919a7f459c36a4698452d
extraction-report      9066f9e371669109b5ec8385d9f427aa384f94a2da7a344aca7947a78acd1d4c
feature SHA256SUMS     d42a277b67ad38f97664e03cc739de91c3205e0817a08b84be587a785d03236f
ledger                 4177b4efee7a53b41c6657ccb27c299641af73301bf13c74b2a8f1c19e536066
```

El ensamblador aceptó 45/145 campañas, R02 16/29, 100 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó y autorizó `HTTP-MULTI-1/R02`. Se corrigieron conteo esperado, opacidad de `large_ip_ratio`, timings ajenos, HTTP/2 no verificado y evaluación de recursos sin umbral.

**F1N-TLS-SESSIONS-20-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-MULTI-1-R02`.
