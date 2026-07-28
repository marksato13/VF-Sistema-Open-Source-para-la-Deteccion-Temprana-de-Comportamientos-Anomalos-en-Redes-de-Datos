# Vigesimoprimer canario oficial R02 — HTTP concurrente C8

Fecha: 28 de julio de 2026. Campaña: `F1N-HTTP-C8-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo, antecedente y preflight

El perfil descarga simultáneamente ocho copias de `100MB.bin` desde un solo Cliente `10.20.0.20` hacia Servidor `10.30.0.10`. Cada flujo usa `--limit-rate 2M`; demuestra ocho conexiones solapadas, no ocho clientes, usuarios ni destinos.

El primer intento R01 había sido rechazado por 476 drops. Una calibración excluida y el retry R01 posterior pasaron con el búfer ampliado. R02 no tenía un intento previo ni requirió archivado.

El preflight confirmó Git limpio y sincronizado en `237efca9a34ae68a4d46701e0811c06727a6ee51`, ID libre, matriz/almacenamiento PASS, 136,722,616,320 bytes disponibles en VM01 y 136,499,449,856 en Sensor. El archivo midió 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió HTTP 200 y longitud correcta.

Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.158 ms. Servicios, rutas, captura, generador y aislamiento pasaron. Las cuatro NIC externas estaban `DOWN` y `172.17.25.111–114` quedó bloqueado por ICMP/TCP22.

El controlador remoto de PCAP coincidió con Git, SHA-256 `f4a0bf90d1f348f1173678c717f620fdad99c31325b0c5c7d5b5d47843a74b54`; registraba búfer de 65,536 KiB, `net.core.rmem_max=67,108,864` y rotación 512 MB × 4.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `http-concurrent` / `8 100MB 2M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `048896cb26996464f54cd1f8d12cceb7d61e49246645aea858af30019dec7bdb` |

## Transferencias y concurrencia

El escenario terminó con código cero y stderr vacío. Las ocho descargas devolvieron HTTP 200 y 104,857,600 bytes; sus tiempos estuvieron entre 49.507318 y 49.535939 s, y sus velocidades entre 2,116,798 y 2,118,022 B/s.

Los puertos origen fueron `45640`, `45656`, `45666`, `45670`, `45676`, `45692`, `45698` y `45702`. Sus SYN iniciales abarcaron 49.730 ms y los spans PCAP estuvieron entre 49.508531 y 49.532486 s. Los ocho flujos se solaparon, pero pertenecen al mismo episodio y no son unidades experimentales independientes.

La suma de velocidades fue 135.527552 Mbit/s; los 838,860,800 bytes sobre el mayor tiempo equivalen a 135.475102 Mbit/s. Son 0.9759 % y 0.9368 % sobre el nominal agregado de 134.217728 Mbit/s; el margen frente a 200 Mbit/s fue 64.472448 Mbit/s. `curl --limit-rate` no se interpreta como shaping exacto.

## Rotación e integridad

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 888,265,804 |
| `capture.pcap0` / `capture.pcap1` | 512,001,184 / 376,264,620 bytes |
| Capturados / recibidos / parseados | 592,548 / 592,548 / 592,548 |
| Drops tcpdump | **0** |
| TCP SYN / SYN-ACK / FIN / RST | 8 / 8 / 16 / 0 |
| Transferencia / límite de rotación | verificada / no alcanzado |
| Delta Suricata / PCAP | 592,556 / 592,548 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 37 / 37 |
| Stats / HTTP / fileinfo | 21 / 8 / 8 |

Los ocho paquetes adicionales del contador Suricata no están identificados y no se interpretan como drops; los contadores específicos declaran cero pérdidas.

Los ocho HTTP son `GET /files/100MB.bin` con estado 200. Los ocho `fileinfo` quedaron `TRUNCATED` a 102,400 bytes y `gaps=false`. Las descargas y PCAP están completos, pero no se afirma inspección íntegra del cuerpo por Suricata.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 12,446 | 2.1004 % |
| De 500 a 1500 bytes | 580,102 | **97.8996 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 579,313 | 97.7664 % |

La longitud media fue 1,469.06 bytes y la máxima, 1,500. C8 amplía el rango benigno pesado solicitado por el jurado.

## Features y horizontes

El extractor produjo seis filas elegibles del mismo episodio:

| Fin UTC | Paquetes | Packet rate | Large ratio | Attempts | SYN | HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `20:31:20` | 52,043 | 5,204.3 s⁻¹ | 0.87694791 | 8 | 8 | 8 |
| `20:31:30` | 117,175 | 11,717.5 s⁻¹ | 0.98965650 | 8 | 0 | 8 |
| `20:31:40` | 118,293 | 11,829.3 s⁻¹ | 0.98825797 | 8 | 0 | 8 |
| `20:31:50` | 117,254 | 11,725.4 s⁻¹ | 0.98943320 | 0 | 0 | 8 |
| `20:32:00` | 117,152 | 11,715.2 s⁻¹ | 0.98985079 | 0 | 0 | 8 |
| `20:32:10` | 70,631 | 7,063.1 s⁻¹ | 0.98565786 | 0 | 0 | 8 |

El horizonte de 30 s deja `attempts=0` en las tres últimas ventanas; HTTP persiste por su horizonte de 60 s. Solo la primera ventana contiene SYN y tiene `syn_completion_ratio_10s=1`. Las ratios destino/puerto son 0.125 mientras los intentos permanecen en el horizonte y cero después. Estas transiciones son semántica causal, no pérdida de flujos.

## Comparación R01↔R02

R01 y R02 completaron ocho transferencias en aproximadamente 49.51–49.54 s, con dos segmentos PCAP, EVE 37/37 y cero drops. R02 produjo 592,548 paquetes frente a 600,128: −7,580 (−1.2631 %). Contiene 7,650 paquetes pequeños menos, 70 paquetes objetivo más y 36 paquetes exactamente de 1,500 bytes menos.

La proporción objetivo aumentó de 96.6514 % a 97.8996 %, +1.2482 puntos, y la media de 1,451.03 a 1,469.06 bytes. La causa no fue medida y no se califica como normal, marginal ni significativa sin un criterio previo.

Ambas produjeron seis filas, pero la alineación UTC distribuyó sus paquetes de forma diferente. Los PCAP, EVE, CSV, ledger, timestamps y puertos origen son independientes; ningún vector exacto R01↔R02 coincide.

El Sensor produjo 124 muestras: CPU máxima 47.29 %, RSS 781,816 KiB, memoria disponible mínima 13,959,244 KiB y carga máxima 0.36. R01 registró 31.53 % de CPU y 780,304 KiB RSS. Los incrementos de 15.76 puntos y 1,512 KiB se conservan sin causa ni extrapolación. C8 tuvo menos CPU máxima que C4/R02, por lo que tampoco se asume escalado lineal con el número de flujos.

## Integridad raíz

```text
manifest.json          d58d1c30f71735a5a13115fc8297e4c88c2fb5e554f412032bbf5d5aa6d2df3c
capture.pcap0          7d3b95d2002f48269aa846859c070d434b0196b83b83a33344cb9e743b33ffe3
capture.pcap1          6e4f8b6ec7d9e6f90ede7acaf9b4b800eeba03c618f445a16380364084a42691
eve-slice              ecc62b26e35662f48e8c5fa2bb0db78979420a25d97246ed941b11b8596f7f32
campaign SHA256SUMS    6cd5ff661cce649127a05297ec2cdcd0ced60656cb377f1decf160ae89f4573a
multilayer-v1.csv      02eccbdb374f3e0d4272be663d58d896fe5cffb594338a433731a52efdaa8430
extraction-report      e672ae08949a9ae6842805eb30140fe7835fac1b7934972eba5e66ec826b0f9d
feature SHA256SUMS     78788d967a833e1e6ec2e050ee77aa1a9d3474ce91f989895a11a7e88f2fb4ad
ledger                 2820fec606bb45500e67be5cb95f8a2734ef78ad72f4f4b8f3a0fd7f3b349fc0
```

El ensamblador aceptó 50/145 campañas, R02 21/29, 95 faltantes globales y 8 de R02, cero inválidas/advertencias, una calibración excluida, seis coincidencias dentro de `train` y cero entre particiones. C8 no añadió coincidencias.

Claude aceptó con limitaciones y autorizó el preflight siguiente. Se corrigieron unidades, causalidad, tolerancias, inventario de duplicados, independencia de flujos, límites CPU, condiciones inventadas y proyección de resultados futuros.

**F1N-HTTP-C8-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight nuevo de `F1N-TCP-REFUSED-5-R02`.
