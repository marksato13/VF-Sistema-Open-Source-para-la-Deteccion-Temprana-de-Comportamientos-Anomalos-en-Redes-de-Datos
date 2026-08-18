# Decimocuarto canario oficial R03 — HTTPS-1GB

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTPS-1GB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 1 GiB limitada a `20M` bytes/s. Cierra la progresión HTTPS individual 10/100/500 MiB/1 GiB de R03. Mide volumen y duración en una sesión TLS; la diversidad de sesiones se conserva separada en `TLS-SESSIONS-20`. El certificado es autofirmado y `curl` usa `--insecure`, por lo que no representa PKI productiva.

El preflight confirmó Git limpio y sincronizado en `123bd80c41f56c0d2df01491e740a26e35a90fe2`, ID/feature/ledger/lock libres, 132,010,639,360 bytes disponibles y almacenamiento oficial `PASS`. NTP pasó en VM01 más las cuatro VM, con desfase absoluto máximo de 1.383885 ms frente al máximo versionado de 0.1 s.

`/srv/ppi/files/1GB.bin` medía 1,073,741,824 bytes y tenía SHA-256 `49bc20df15e412a64472421e13fe86ff1c5165e18b2afccf160d4dc19fe68a14`. NGINX devolvió HTTPS 200, `Content-Length: 1073741824` y `ssl_verify_result=18`. Las cuatro VM, servicios, rutas por el Sensor, NIC externas `DOWN`, generador, captura inactiva, contadores Suricata y bypass pasaron.

Claude/Sonnet autorizó una única ejecución. Se corrigieron su denominación “cinco VM”, el SHA truncado en `…a1` y un gate inexistente sobre filas “fuera del episodio”.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `heavy-transfer` / `https` |
| Argumentos | `1GB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77` |

## Transferencia, rotación e integridad

`curl` obtuvo HTTP 200, 1,073,741,824 bytes en 51.021985 s, a 21,044,689 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 3 / 1,138,323,415 |
| Capturados / recibidos / parseados | 758,423 / 758,423 / 758,423 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 25 / 25 |
| TLS / flow / `stats` / HTTP / fileinfo | 1 / 1 / 23 / 0 / 0 |
| Delta Suricata / PCAP | 758,431 / 758,423 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los tres PCAP pasaron validación, transferencia y hashes; EVE quedó `complete_same_inode`. Los ocho paquetes adicionales del contador Suricata no están identificados y no existe tolerancia definida.

El evento TLS registra TLS 1.3, JA3, JA3S, JA4 y ALPN para `10.20.0.20 → 10.30.0.10:443`. El flow TCP cerrado de la misma transferencia registra 14,937 paquetes hacia el Servidor y 743,486 hacia el Cliente: suman los 758,423 del PCAP; su edad es 51 s y `tx_cnt=1`. EVE no produjo HTTP ni fileinfo por la opacidad TLS.

## Cobertura pesada R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 757,999 | 758,673 | 758,423 |
| 500–1500 bytes | 743,169 | 743,214 | 743,379 |
| Porcentaje objetivo | 98.0435 % | 97.9624 % | 98.0164 % |
| Exactamente 1500 bytes | 743,055 | 743,064 | 742,997 |
| Menores de 500 bytes | 14,830 | 15,459 | 15,044 |
| Longitud media IP | 1,471.61 | 1,470.42 | 1,470.91 |
| Duración `curl` | 51.021313 s | 51.029984 s | 51.021985 s |

Las tres repeticiones transfirieron el mismo volumen y contienen entre 743,169 y 743,379 paquetes del rango solicitado por el jurado. La duración máxima difiere 0.008671 s. No se afirma tendencia, causa ni determinismo.

## Seis ventanas correlacionadas

| Ventana UTC | Paquetes | Media IP | Heavy ratio | Attempts / SYN | TLS rate |
|---|---:|---:|---:|---:|---:|
| `15:37:20` | 24,809 | 1,424.91833609 | 0.94828490 | 1 / 1 | 0.01666667 |
| `15:37:30` | 151,197 | 1,463.60150003 | 0.97535665 | 1 / 0 | 0.01666667 |
| `15:37:40` | 154,100 | 1,463.54484101 | 0.97524335 | 1 / 0 | 0.01666667 |
| `15:37:50` | 147,136 | 1,479.87948565 | 0.98638674 | 0 / 0 | 0.01666667 |
| `15:38:00` | 147,398 | 1,478.34646332 | 0.98508799 | 0 / 0 | 0.01666667 |
| `15:38:10` | 133,783 | 1,478.11439421 | 0.98490840 | 0 / 0 | 0.01666667 |

Los conteos suman 758,423. Las ventanas de paquetes no se solapan, pero sus historias sí: el intento persiste durante 30 s en las tres primeras, mientras el SYN solo está en la primera; la sesión TLS permanece en las seis por su historia de 60 s. Son filas autocorrelacionadas de un episodio, no seis repeticiones.

R01 produjo siete filas por una cola final de cuatro paquetes; R02/R03 produjeron seis. Su posición frente a los bordes UTC define la segmentación temporal, sin demostrar una causa sobre el transporte. El ensamblador verifica que R03 no agregó un vector exacto.

El Sensor produjo 134 muestras: CPU máxima 7.42 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,072,704 KiB y carga máxima 0.50. Son observaciones sin un gate de presión definido.

## Integridad raíz

```text
manifest.json          a175dfb3b091697dc3c8c7356d503c9cfdf6dcadb3a3c55b94c3bfce5e52decc
capture.pcap0          67aa361de0fdfead02437b0c2315ceb13b924a9bf75b9e52e49c04e954620421
capture.pcap1          ac25fab745e6870181b81e1fc012ea6b05a44a1013124a6d4dd27e8962d0d307
capture.pcap2          9139872f5d9e5ce6aeca866b12e7c320725cbf156178abaf36fbfdb997af1eaa
eve-slice              7e90f44a3cc2a89af5bd3663b25680995e9b73cb4c4c603f116ea356e9378734
campaign SHA256SUMS    05ac4af562552c559f2852db2501ba6e8fb34bd6174cf4d1042d6f00b6d78c84
multilayer-v1.csv      4161ef509c7d42460e577910b14155039188fea0574ddc79dc613b05ef7d99bf
extraction-report      7685c3905e492b2cd1d25956bf0054396e1a0992eef01bba96c4cfcd60ee00c3
feature SHA256SUMS     2d68fb466d95e99eb192dc2e29dfa05afcab64099f2d3f6e495543476c18c667
ledger                 4e8eb2fe552247a226bc7d205628d8a9d03b936c062a15303a679cc84052dd38
```

El ensamblador aceptó 72/145 campañas: R03 14/29, 73 faltantes, cero inválidas/advertencias, once coincidencias exactas dentro de `train` —sin aumento— y cero cruces observados. Validation/test aún no existen, por lo que el cero actual no demuestra ausencia futura de fuga.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight de `HTTP-404-5/R03`. Se corrigieron su historia attempts/SYN, conteo NTP, SHA truncado, gate de filas y alcance de los cruces.

**F1N-HTTPS-1GB-R03 ACEPTADA CON LIMITACIONES.** Se completa la progresión HTTPS individual R03. Siguiente autorizado: solo preflight independiente de `F1N-HTTP-404-5-R03`.
