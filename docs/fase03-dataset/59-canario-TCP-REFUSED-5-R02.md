# Vigesimosegundo canario oficial R02 — TCP REFUSED 5

Fecha: 28 de julio de 2026. Campaña: `F1N-TCP-REFUSED-5-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y alcance

La celda representa cinco intentos legítimos desde Cliente `10.20.0.20` hacia un servicio ausente en `10.30.0.10:65000`. Evita tratar un RST o un SYN no completado como ataque por sí solo dentro de este contexto controlado.

No es un escaneo, no utiliza Kali y no representa diversidad de orígenes, destinos, puertos ni frecuencias. Tampoco demuestra que cualquier patrón de RST sea benigno.

## Preflight

El preflight confirmó Git limpio y sincronizado en `e2fafe3919d49ada91f4172e2730e9e063356d06`, ID/captura libres, almacenamiento oficial PASS y 135,834,034,176 bytes disponibles. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.171006 ms.

Servicios, generador, rutas y aislamiento pasaron. Las cuatro NIC externas estaban `DOWN`; `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

La comprobación específica confirmó:

1. `ss` no encontró listener en el puerto 65000 del Servidor;
2. `nc` desde Cliente devolvió `Connection refused`, no timeout.

Un primer comando con `awk` tuvo un error de escape y no se contó como PASS. La comprobación se repitió correctamente con el filtro nativo de `ss`. Los sondeos ocurrieron antes de 70 s de quietud y no aparecen en la captura oficial.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumento | `tcp-refused` / `5` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

## Resultado TCP

El generador terminó con código cero, stderr vacío y:

```json
{"scenario":"tcp-refused","attempts":5,"expected_refusals":5}
```

El PCAP contiene exactamente cinco pares:

| Control | Resultado |
|---|---:|
| SYN Cliente→Servidor | 5 |
| RST/ACK Servidor→Cliente | 5 |
| SYN/ACK / FIN | 0 / 0 |
| Puertos origen | `47090`, `47094`, `47110`, `51102`, `51104` |
| Puerto destino | `65000` |
| Span del episodio | 2.427005 s |

Los intervalos entre SYN fueron 0.591626, 0.611446, 0.612788 y 0.610872 s. Las latencias SYN→RST/ACK fueron 0.242, 0.418, 0.279, 0.248 y 0.273 ms. Las respuestas activas demuestran rechazo del host y descartan simples expiraciones del generador.

## Integridad y EVE

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 824 |
| Capturados / recibidos / parseados | 10 / 10 / 10 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 14 / 10 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 10 / 10 |
| Tipos EVE | 10 `stats`, cero L7 y cero alertas |

Los cuatro paquetes adicionales del contador Suricata no son cuatro eventos EVE y no están identificados. No se les atribuye causa; los contadores específicos demuestran cero drops.

Los diez paquetes miden menos de 500 bytes, con longitud media 50 y máxima 60. Esta campaña cubre normalidad L4, no tráfico pesado; complementa las campañas HTTP/HTTPS.

## Features

El extractor produjo dos filas elegibles del mismo episodio:

| Fin UTC | Paquetes | Attempts 30 s | SYN | Packet rate | Attempt/SYN rate | Completion | RST ratio | IP/port ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `23:37:40` | 6 | 3 | 3 | 0.6 s⁻¹ | 0.3 / 0.3 s⁻¹ | 0 | 0.5 | 0.33333333 |
| `23:37:50` | 4 | 5 | 2 | 0.4 s⁻¹ | 0.2 / 0.2 s⁻¹ | 0 | 0.5 | 0.2 |

`syn_completion_ratio_10s=0` es correcto porque no hubo SYN/ACK. `rst_ratio_10s=0.5` refleja un RST/ACK por cada SYN. Las ratios de IP y puerto destino disminuyen al incorporar los cinco intentos en el horizonte de 30 s.

Las dos filas son ventanas correlacionadas; no son repeticiones. R01 y R02 suman cuatro filas, no doce, y ninguna coincide exactamente.

## Comparación R01↔R02

Ambas repeticiones tienen diez paquetes/824 bytes, cinco pares SYN–RST/ACK, cero drops, EVE con diez `stats`, tamaños 50/60 y dos filas elegibles. R01 distribuyó 2/8 paquetes entre ventanas; R02, 6/4, por distinta alineación UTC.

El span fue 2.449771 s en R01 y 2.427005 s en R02. R01 registró latencias de 0.242–0.274 ms; R02, 0.242–0.418 ms. El máximo mayor se conserva sin causalidad ni umbral.

Los PCAP, EVE, CSV, ledger, timestamps y puertos origen son independientes. La repetición conserva el mismo resultado funcional, pero no produce vectores exactos duplicados.

El Sensor produjo 55 muestras: CPU máxima 1.52 %, RSS 781,816 KiB, memoria disponible mínima 14,083,796 KiB y carga máxima 0.37. R01 registró 56 muestras, CPU 1.53 % y RSS 780,304 KiB.

## Integridad raíz

```text
manifest.json          1c6b0671ab86e0fe5de2f193dd47e809a1dfdd7ca4984df20c8de94e4ba26ca3
capture.pcap0          1c07169694364dac2172f3b1887e71db4b946f85b92b6b2cb3898062a35736f3
eve-slice              0705778b17edb2791a894d90965a442780b0df66181f7a751387911a6c67252d
campaign SHA256SUMS    c0ea32cd8d21fab7a911ee11bfa90df58b168d7616468cf4917894e55376ea33
multilayer-v1.csv      9bb3b8f10c71a7701b3ce31bdefb1883c8a8e980da51679f8647198ca589858b
extraction-report      fc5731dc9ffd777b6fe2cfe4ea469b46eb6dd66b4f291c9fc038f9f70ebb7da9
feature SHA256SUMS     68493afe318f5b70d2878e74b8e5b880cca1494cbd79f79c8bc58d91b11d6fce
ledger                 af420d4feaa84b459b99e14ee3157d797982f982fe39c5e481f1e0b9639eb4e3
```

El ensamblador aceptó 51/145 campañas, R02 22/29, 94 faltantes globales y 7 de R02, cero inválidas/advertencias, una calibración excluida, seis coincidencias dentro de `train` y cero entre particiones. TCP-REFUSED no añadió coincidencias.

Claude aceptó con limitaciones y autorizó el preflight siguiente. Se corrigieron generalización de RST, unidades, contadores, alertas inventadas, número de filas, duplicación inexistente, particiones y gates ficticios.

**F1N-TCP-REFUSED-5-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-TCP-50M-R02`.
