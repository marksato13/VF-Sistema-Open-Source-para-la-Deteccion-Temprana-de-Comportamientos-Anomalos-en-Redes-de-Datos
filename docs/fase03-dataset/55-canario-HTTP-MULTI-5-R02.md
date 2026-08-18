# Decimoctavo canario oficial R02 — HTTP-MULTI-5

Fecha: 28 de julio de 2026. Campaña: `F1N-HTTP-MULTI-5-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil ejecuta cinco solicitudes HTTP secuenciales contra cada VIP DMZ: `10.30.0.10`, `.11` y `.12`. Son quince conexiones a tres identidades L3 alojadas en una sola VM Servidor; no representan tres hosts físicos.

El preflight confirmó Git limpio y sincronizado en `3b23c34977a6e9458966935d53004fe0dca0a866`, ID libre, 137,392,414,720 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.334658 ms. Cliente y Kali conservaron la ruta por el Sensor, las tres VIP devolvieron HTTP 200 y los servicios requeridos estaban activos.

Las NIC externas de Sensor, Servidor, Kali y Cliente permanecieron `DOWN`. Las direcciones `172.17.25.111–114` quedaron bloqueadas tanto por ICMP como por TCP/22. La captura residual estaba inactiva y el generador remoto coincidió con el local:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumento | `http-multi` / `5` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

## Ejecución y conteos

El escenario terminó con código cero y stderr vacío. Su salida contiene exactamente quince líneas: cinco solicitudes por cada VIP, todas HTTP 200.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 16,749 |
| Capturados / parseados / drops | 150 / 150 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 40 / 40 |
| Stats / HTTP / fileinfo | 10 / 15 / 15 |
| Delta Suricata / PCAP | 152 / 150 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

El PCAP contiene quince SYN iniciales, quince SYN/ACK, treinta FIN y cero RST. Los dos paquetes adicionales del contador Suricata no están identificados; no se calcula un porcentaje ni se atribuye una causa porque Suricata y el PCAP filtrado tienen alcances distintos.

Cada VIP registra exactamente cinco `GET /health`, HTTP 200 y longitud 36. Los quince `fileinfo` están `CLOSED`, `gaps=false` y `size=36`. EVE quedó completo en el mismo inode y todos los hashes pasaron.

Los 150 paquetes son menores de 500 bytes, con longitud IPv4 media de 81.50 y máxima de 251. Este perfil cubre diversidad multidestino ligera; no constituye tráfico pesado legítimo.

## Features y repetibilidad

El extractor produjo una fila elegible:

| Paquetes | Attempts / SYN / HTTP | Packet rate | Attempt/SYN rate | IP ratio | Port ratio | Completion |
|---:|---:|---:|---:|---:|---:|---:|
| 150 | 15 / 15 / 15 | 15.0 s⁻¹ | 1.5 / 1.5 s⁻¹ | 0.2 | 0.06666667 | 1.0 |

`unique_dst_ip_ratio_30s=3/15=0.2` y `unique_dst_port_ratio_30s=1/15`. `large_ip_ratio_10s`, `http_error_ratio_60s`, `rst_ratio_10s`, `dns_nxdomain_ratio_60s` y `tls_session_rate_60s` valen cero, como corresponde al episodio observado.

R01 y R02 tienen los mismos 150 paquetes/16,749 bytes, conteos EVE, distribución de tamaños y vector exacto de 14 features. Sus duraciones PCAP fueron 1.667878 y 1.661227 s. Los PCAP, EVE, CSV, ledger, timestamps y quince puertos origen son distintos: son ejecuciones independientes que reproducen el mismo patrón determinista.

Esta coincidencia es la sexta entre campañas dentro de `train`; ninguna cruza particiones. No se elimina automáticamente: Isolation Forest conserva muestras repetidas. Su posible ponderación se cuantificará en la auditoría agregada R02 antes del entrenamiento.

El Sensor produjo 54 muestras: CPU máxima 1.52 %, RSS máxima 780,308 KiB, memoria disponible mínima 14,073,272 KiB y carga de un minuto máxima 0.25.

## Integridad raíz

```text
manifest.json          896f1f30dd0e4c66222a2c73aa2fa6fe80e12c1e95ba202a5019d0ad5a007114
capture.pcap0          403e5a0a7297a4ada8345cb03c82ce5b1cf77729fb10f31cd9ba02cf4a9e67aa
eve-slice              bff278a7a6276ca3f530cd86634e17a5d1553d62af76bc2f17f82b868086c230
campaign SHA256SUMS    c567d202dfc6d6430a1d8a55dacf777a796b9143b1c3ad876b23567fac2fcde4
multilayer-v1.csv      23d9c178c713a40b21c28e249631636257e780c7ad530afd201babdc56c61066
extraction-report      27e9e27f6e488c1204b556c1563bd2207099e6ea15aa8e348b2f494c357710c6
feature SHA256SUMS     fc9b5d34aeef916976fb6bb0c0f4d105e4f39dc15e3309f6b8ff4dbcfb2f4857
ledger                 16b09f55af3b47c721178192914c7dac11ddf888d1237797a5bd646699a8547d
```

El ensamblador aceptó 47/145 campañas, R02 18/29, 98 faltantes globales y 11 de R02, cero inválidas/advertencias, seis coincidencias dentro de `train` y cero entre particiones. F1 continúa incompleta y todavía no autoriza construir ni entrenar el dataset final.

Claude aceptó con limitaciones y autorizó el preflight individual de `HTTP-C2/R02`. Se corrigieron su IP física inventada, uso de `holdout`, conversión de RSS, inode no demostrado, soporte no nulo atribuido a las 14 señales y la afirmación prematura de validez global.

**F1N-HTTP-MULTI-5-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-C2-R02`.
