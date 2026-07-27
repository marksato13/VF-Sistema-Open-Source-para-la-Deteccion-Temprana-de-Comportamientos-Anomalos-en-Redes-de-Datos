# Vigésimo noveno canario oficial F1 — PING-100 y cierre R01

Fecha: 27 de julio de 2026. Campaña: `F1N-PING-100-R01`. Estado: **ACEPTADA CON LIMITACIONES**. R01: **COMPLETA 29/29**.

## Objetivo y preflight

Esta celda incrementa la línea base ICMP legítima a cien solicitudes echo con intervalo nominal de 0.2 segundos. Cliente `10.20.0.20` alcanzó al Servidor `10.30.0.10` a través del Sensor. El perfil cubre `icmp_ratio_10s` y `packet_rate_10s` en el estrato `burst`.

El preflight confirmó Git limpio y sincronizado en `d27c1460c95da18aa1ed32532658926c5ca2b430`, ID libre, 141,027,553,280 bytes disponibles y gate de almacenamiento en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP. Ruta, eco de control, Suricata, captura y servicios estaban sanos. El generador local y remoto coincidió por SHA-256; las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `burst` |
| Argumentos | `100`, `0.2` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `412ee9eb50fba97316261a06e934257bc6a9467e24d73f56a2530aa368886fe0` |

## Resultado ICMP

El generador ejecutó `ping -n -c 100 -i 0.2 10.30.0.10`. stdout informa cien transmitidas, cien recibidas, 0 % de pérdida y 20,554 ms. El RTT mínimo/promedio/máximo/mdev fue `0.304/0.565/10.602/1.064 ms`. El máximo se conserva como observación sin causalidad ni umbral y no forma parte de las 14 features.

| Control PCAP | Resultado |
|---|---:|
| Echo request / echo reply | 100 / 100 |
| Tipo/código solicitud y respuesta | 8/0 y 0/0 |
| Identificador / secuencias | 12335 / 1–100 |
| TTL solicitud / respuesta | 64 / 63 |
| Span primera→última solicitud | 20.553039 s |
| Span primer→último paquete | 20.553292 s |
| Pérdida observada | 0 % |

Las doscientas tramas comparten protocolo, extremos e identificador ICMP. El extractor las atribuye a un intento canónico ICMP, no a cien conversaciones nuevas.

## PCAP, EVE y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 200 / 200 / 200 |
| PCAP | 1 archivo / 22,824 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 204 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 112 / 112 |
| Muestras Sensor / stderr | 68 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

Todos los paquetes miden 84 bytes IPv4 y son menores de 500 bytes. La media y el máximo son 84; `large_ip_ratio_10s=0` es correcto para ICMP ligero.

EVE contiene cien alertas SID `1000001`, una por echo request, y doce `stats`. La regla `PPI LAB ICMP TEST` tiene severidad 3, categoría vacía y `action=allowed`; es telemetría deliberada del laboratorio, no un ataque ni un clasificador productivo. `allowed` demuestra que no bloqueó, no que una alerta sea intrínsecamente benigna.

Suricata procesó un delta de 204 paquetes frente a los 200 del PCAP filtrado. Los cuatro adicionales no están identificados y no se convierten en eventos EVE hipotéticos. No existe una tolerancia porcentual definida; la aceptación se basa en integridad PCAP, cero drops/errores y declaración explícita de la diferencia.

El Sensor alcanzó CPU puntual máxima de 1.52 %, RSS de 780,308 KiB, memoria disponible mínima de 14,103,208 KiB y carga máxima de 0.40. Son observaciones sin umbral.

## Cuatro ventanas de un episodio

El extractor procesó 200 observaciones de paquete, cero de aplicación y produjo cuatro filas elegibles. `window_end_utc` es el extremo derecho de cada ventana:

| Fin UTC | Paquetes | Attempts historia 30 s | Tasa paquetes | Tasa attempts | Ratio IP | Ratio ICMP |
|---|---:|---:|---:|---:|---:|---:|
| `15:36:00` | 6 | 1 | 0.6/s | 0.1/s | 1 | 1 |
| `15:36:10` | 96 | 1 | 9.6/s | 0/s | 1 | 1 |
| `15:36:20` | 96 | 1 | 9.6/s | 0/s | 1 | 1 |
| `15:36:30` | 2 | 0 | 0.2/s | 0/s | 0 | 1 |

Las ventanas cubren, respectivamente, `(15:35:50,15:36:00]`, `(15:36:00,15:36:10]`, `(15:36:10,15:36:20]` y `(15:36:20,15:36:30]`. Los conteos de paquetes suman 200 sin duplicación. La historia de 30 segundos conserva el único intento en las tres primeras filas; en la cuarta, el inicio `15:35:59.468450` ya quedó fuera de `(15:36:00,15:36:30]`, por eso el denominador de destinos es vacío y el ratio seguro vale cero. La última fila no está truncada: contiene la solicitud 100 y su respuesta, que cruzaron la frontera de `15:36:20`.

Todas las filas registran longitud media 84, ratio pesado 0, ratio ICMP 1 y ratio de puertos 0 por ausencia de TCP/UDP. Son ventanas autocorrelacionadas de un episodio, no cuatro repeticiones independientes.

## Comparación ICMP R01

| Perfil | Solicitudes | Intervalo nominal | Span solicitudes | Paquetes | Filas | Tasa de paquetes observada |
|---|---:|---:|---:|---:|---:|---:|
| PING-10 | 10 | 1 s | 9.190037 s | 20 | 1 | 2/s |
| PING-100 | 100 | 0.2 s | 20.553039 s | 200 | 4 | 0.2–9.6/s |

PING-100 amplía conteo y frecuencia respecto a PING-10, pero siguen siendo dos episodios de un solo par, tamaño constante e intervalo determinista. La tasa 9.6/s es un conteo de paquetes por ventana, no throughput de aplicación ni distribución poblacional.

## Integridad raíz

```text
manifest.json          94e0c6b61bddc8216aaab310667269509c738df14887141e7e10eaf004e51d5b
capture.pcap0          46b78ad425a4cbc6a5dbb817169bab40c2b136cab8865ab4e0cad64597ddf1af
eve-slice              61d7754a8a3a669779100d72a93a7382aea86676a32f2072e89dabac7dc83c1d
campaign SHA256SUMS    68946aa2eb0aa72affa900ea69d1414ae7289a8441bfcfd069d8d3b613937530
multilayer-v1.csv      a953c5431a1d6fa885e10a82d75001196c48fd28fd4baac3b25ec8449dc1eefc
extraction-report      55455e9c87965136c3f5b30bd0ccaa3315e8133b17bf53372d644fbd901cb00b
feature SHA256SUMS     d2436f92dbb379d45157b6c121feb9601e7f97966b7f5995975846fe0b06832a
ledger                 51138a626e9dc5b886e1dca14acd0b6f0faed82dbb6aceaebaf73d66d3b6e099
```

Todos los hashes pasaron y la captura residual quedó inactiva.

## Cierre de R01

El ensamblador informó:

| Control | Resultado |
|---|---:|
| Esperadas / aceptadas | 145 / 29 |
| Inválidas / advertencias / duplicados | 0 / 0 / 0 |
| Gaps R01 | 0 |
| Gaps R02 / R03 / R04 / R05 | 29 / 29 / 29 / 29 |
| Total faltante | 116 |
| Dataset construible | no |

R01 completa las 29 celdas de la primera repetición. R02 y R03 pertenecen a `train`, R04 a `validation` y R05 a `test`; ninguna de esas repeticiones ha comenzado. El 20 % de celdas de matriz completado no equivale al 20 % de filas ni de peso del futuro modelo, porque cada campaña produce distinto número de ventanas.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**. Su primera revisión desplazó las ventanas, inventó campos/tolerancias y confundió kernel con EVE. Al solicitar corrección, contaminó toda la respuesta con `DNS-VALID-200`; se rechazó. La última respuesta quedó limitada a hechos verificados y mantuvo el dictamen.

**CANARIO PING-100 ACEPTADO CON LIMITACIONES Y R01 CERRADA 29/29.** El dataset aún no está listo. Antes de iniciar `DNS-VALID-10/R02`, corresponde consolidar la auditoría agregada de R01 y confirmar que no exista una razón científica u operativa para detener las repeticiones.
