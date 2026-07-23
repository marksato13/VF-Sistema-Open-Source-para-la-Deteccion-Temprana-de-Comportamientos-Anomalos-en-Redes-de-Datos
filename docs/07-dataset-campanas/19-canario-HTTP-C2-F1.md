# Decimocuarto canario oficial F1 — HTTP concurrente C2 R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-C2-R01`. Es la decimocuarta campaña aceptada y la primera celda oficial de concurrencia HTTP.

## Objetivo y alcance

El perfil descarga simultáneamente dos copias de `100MB.bin` desde un solo Cliente hacia `10.30.0.10`. Cada `curl` usa `--limit-rate 10M`, es decir, 10 MiB/s nominales. El techo nominal agregado es 20 MiB/s o 167.77 Mbit/s decimales.

La concurrencia corresponde a dos flujos del mismo Cliente y destino. No representa dos usuarios, dos hosts cliente ni diversidad L3.

## Preflight

El preflight confirmó Git limpio y sincronizado en `c81569dbe43ed29220ea865d989d58e61621c016`, ID libre, ausencia de captura activa, 145,690,947,584 bytes disponibles en VM01 y almacenamiento PASS.

Las cuatro VM remotas mantuvieron `America/Lima` y NTP sincronizado. Las rutas permanecieron forzadas por el Sensor, los servicios estaban activos, `/srv/ppi/files/100MB.bin` midió exactamente 104,857,600 bytes y un HEAD devolvió HTTP 200. Suricata y el generador remoto pasaron sus controles. El HEAD fue seguido por 70 segundos de quietud.

Kali conservó `172.17.25.113/24` en `eth0`, pero la interfaz seguía `DOWN`, sin ruta externa y bloqueada desde VM01.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-C2` / `R01` |
| Escenario / argumentos | `http-concurrent` / `2 100MB 10M` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `1c65572c683bb319db50f0e8a31d65ac0ee998bd62b7fdc92c459d972436b976` |

## Ejecución y concurrencia

La captura comenzó a las `23:54:41` y cerró a las `23:56:21 America/Lima`. El Cliente completó ambas descargas:

| Flujo | HTTP | Bytes | Tiempo | Velocidad reportada |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 9.530846 s | 11,001,919 B/s |
| 2 | 200 | 104,857,600 | 9.517726 s | 11,017,085 B/s |

Los puertos origen `58408` y `58422` registran el mismo timestamp inicial en el PCAP, `1784782547.281434`, y permanecen activos 9.528359 y 9.517378 segundos. Esto demuestra solapamiento real, no dos transferencias consecutivas.

La suma de velocidades reportadas es 176.152032 Mbit/s; el cálculo de bytes totales sobre el mayor tiempo es 176.030711 Mbit/s. El valor observado supera aproximadamente 4.92 % el nominal de 167.77216 Mbit/s, pero permanece 23.85 Mbit/s por debajo del techo operativo de 200 Mbit/s. `curl --limit-rate` controla el promedio y admite variación; no se presenta como un shaper exacto.

## Integridad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 151,467 / 151,467 paquetes |
| PCAP total / archivos | 222,315,680 bytes / 1 |
| TCP | 2 SYN, 2 SYN/ACK, 4 FIN, 0 RST |
| Drops tcpdump | 0 |
| Delta Suricata | 151,471 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 16 / 16 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 68, stderr vacío |
| SHA campaña/features | todos PASS |

## Paquetes, EVE y recursos

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 6,505 | 4.2947 % |
| De 500 a 1500 bytes | 144,962 | **95.7053 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 144,933 | 95.6862 % |

La longitud media fue 1,437.75 bytes y la máxima 1,500. Este perfil aporta tráfico pesado legítimo concurrente a la observación del jurado.

EVE contiene doce `stats`, dos `http` y dos `fileinfo`. Ambos HTTP son GET 200 a `/files/100MB.bin`. Los `fileinfo` quedaron `TRUNCATED` a 102,400 bytes por el límite de inspección de Suricata, con `gaps=false`. Las descargas y el PCAP están completos; no se afirma inspección íntegra del contenido.

Suricata alcanzó 27 % de CPU, mantuvo RSS en 776,372 KiB, memoria disponible mínima de 14,139,280 KiB y carga de un minuto máxima de 0.31.

## Features y semántica SYN

El extractor produjo dos filas elegibles:

| Fin UTC | Paquetes | `byte_rate_10s` | `large_ip_ratio_10s` | SYN | Intentos 30 s | Completitud SYN |
|---|---:|---:|---:|---:|---:|---:|
| `04:55:50` | 62,566 | 8,541,396.2 | 0.90691430 | 2 | 2 | 1.0 |
| `04:56:00` | 88,901 | 13,235,768.4 | 0.99233979 | 0 | 2 | 0.0 |

`syn_completion_ratio_10s` usa `min(SYN,SYN/ACK)/SYN` dentro de la ventana de diez segundos y devuelve cero cuando el denominador es cero. Por eso la segunda fila no indica conexiones fallidas: no contiene SYN nuevos; los dos handshakes están en la primera fila y el Cliente verificó ambas descargas completas.

Las filas pertenecen al mismo episodio y comparten las observaciones HTTP del horizonte de 60 segundos. `campaign_id` ya conserva ese grupo causal; no se añade metadata fuera del esquema congelado.

Los dos intentos se dirigen a una IP y un puerto, por lo que `unique_dst_ip_ratio_30s=1/2=0.5` y `unique_dst_port_ratio_30s=1/2=0.5`. Los puertos origen efímeros no forman parte de estos ratios.

## Integridad raíz

```text
manifest.json          9ceb65c51332abb0f6dc0b3128f555ff9f4b4351657f7d2e46af42e3b8ab2125
capture.pcap0          837e6a191ecce58d44f44234379aba23dccca0f8de42655ae659efa5b8ca813c
multilayer-v1.csv      6e9c61de1b441bc9a37a6408cd001113b05e867389704ef36c440b72086671c4
extraction-report.json c25aef97c963139a853528c981a75ec3f8bc88be70c248e7bf8faa59334f1095
ledger                 587d8457a6d620ca52c192f49a6827def6efcd1bc7de94cab80e978926e018d8
```

## Revisión y decisión

Claude Code 2.1.217/Haiku emitió **ACEPTAR** y autorizó C4 condicionado a repetir los gates. Señaló correctamente el overshoot, autocorrelación, semántica de la segunda fila y truncamiento `fileinfo`.

Se corrigieron errores del dictamen sobre conteo EVE, ratios, puertos origen, espacio del Sensor y una propuesta de metadata incompatible con el esquema. La evidencia identifica correlación mediante `campaign_id`.

El ensamblador acepta catorce campañas, cero inválidas, cero advertencias, cero duplicados y reporta 131 celdas faltantes.

**CANARIO HTTP C2 ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `HTTP-C4/R01`: cuatro descargas concurrentes de 100 MB, `5M` por flujo y el mismo nominal agregado. Si aparecen drops o se supera el techo operativo, la campaña se rechazará y no se avanzará a C8. Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTP-C2-F1.md`.

Seguimiento: C4 pasó esos gates y quedó aceptado con limitaciones en `20-canario-HTTP-C4-F1.md`.
