# Undécimo canario oficial F1 — recambio TLS R01

Fecha: 22 de julio de 2026. Campaña: `F1N-TLS-SESSIONS-20-R01`. Es la undécima campaña aceptada y la primera celda oficial del perfil de recambio de sesiones TLS.

## Objetivo y alcance

El generador realiza veinte invocaciones HTTPS secuenciales a `/health`. Cada invocación abre una conexión nueva, comprueba HTTP 200 desde el Cliente y espera 0.1 segundos antes de la siguiente. El perfil mide la tasa de sesiones TLS cortas autorizadas; no representa concurrencia, múltiples clientes, múltiples destinos, navegación humana ni diversidad de huellas criptográficas.

## Preflight

El preflight confirmó Git limpio y sincronizado en `d65219992cff0cb2597b7020a598b57d1a5007e3`, ID libre, ausencia de captura activa, 145,691,734,016 bytes disponibles y gate de almacenamiento PASS.

Las cuatro VM remotas mantuvieron `America/Lima` y NTP sincronizado. Cliente y Kali alcanzaron la DMZ mediante `10.20.0.1`; los servicios del Servidor y Suricata estaban activos. HTTPS devolvió 200 y el generador remoto conservó el SHA-256 versionado. La sesión de preflight fue seguida por 70 segundos de quietud.

Kali aún conservaba `172.17.25.113/24` configurada en `eth0`, pero la interfaz estaba `DOWN`, no existía ruta externa y VM01 no alcanzó esa dirección por ICMP ni TCP/22. El riesgo latente de una reconexión permanece como gate obligatorio.

| Campo | Valor |
|---|---|
| Perfil / repetición | `TLS-SESSIONS-20` / `R01` |
| Escenario / argumentos | `https-sessions` / `20` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `9246e824773fc95ffe7097ebf344e3aef5d4cd76329e4d39a4fd0e79eb8d75c4` |

## Ejecución e integridad

La captura comenzó a las `23:06:41` y cerró a las `23:08:03 America/Lima`. El escenario produjo veinte líneas `{"session":N,"http_code":200}`, sin stderr y con código de salida cero.

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 431 / 431 paquetes |
| PCAP total / archivos | 144,426 bytes / 1 |
| Drops tcpdump | 0 |
| Delta Suricata | 433 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 30 / 30 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 55, stderr vacío |
| SHA campaña/features | todos PASS |

El PCAP demuestra veinte conexiones TCP completas mediante veinte puertos origen distintos: 20 SYN, 20 SYN/ACK, 40 FIN y 0 RST.

## EVE y visibilidad TLS

EVE contiene diez `stats` y exactamente veinte eventos TLS; no hay ruido ni eventos del preflight. Las sesiones abarcan desde `23:07:48.085582` hasta `23:07:50.544741`, aproximadamente 2.46 segundos.

Las veinte observaciones comparten:

- origen `10.20.0.20` y destino `10.30.0.10:443`;
- TLS 1.3;
- JA3 `7587a1ac9a4f17b4e4e5fe226716f4df`;
- JA3S `15af977ce25de452b96affa2addb1036`;
- JA4 `t13i3012h2_1d37bd780c83_8537cf56674e`.

El HTTP 200 está probado por las veinte salidas de `curl`, pero no aparece como evento HTTP en Suricata porque el contenido está cifrado. La señal L7 pasiva disponible para el extractor es el evento TLS. El certificado es autofirmado y el Cliente usa `--insecure`; no se afirma equivalencia con PKI productiva.

## Tamaño de paquetes

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 371 | 86.0789 % |
| De 500 a 1500 bytes | 60 | **13.9211 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 40 | 9.2807 % |

La longitud media fue 305.04 bytes y la máxima 1,500. Este perfil de handshakes y respuestas cortas no es una campaña pesada. Su distribución complementa, pero no se suma como diversidad de volumen a, las ocho descargas HTTP/HTTPS de 10 MB–1 GB.

## Features y dependencia temporal

El extractor consumió 431 paquetes y veinte observaciones TLS. Produjo dos filas elegibles:

| Fin UTC | Paquetes 10 s | Intentos 30 s | SYN 10 s | `large_ip_ratio_10s` | Completitud SYN | `tls_session_rate_60s` |
|---|---:|---:|---:|---:|---:|---:|
| `04:07:50` | 324 | 15 | 15 | 0.13888889 | 1.0 | 0.25 |
| `04:08:00` | 107 | 20 | 5 | 0.14018692 | 1.0 | 0.33333333 |

La primera fila observa 15 sesiones antes del límite de ventana. La segunda contiene los cinco inicios restantes y conserva las veinte dentro de su horizonte TLS de 60 segundos. Los valores `0.25` y `0.33333333` representan 15/60 y 20/60 sesiones por segundo.

Ambas filas comparten el mismo episodio de 2.46 segundos y no son muestras independientes. La partición se mantiene por campaña completa. La eventual evaluación estadística debe agrupar por campaña y evitar tratar ventanas solapadas como repeticiones experimentales separadas.

## Recursos

Suricata alcanzó 1.52 % de CPU, mantuvo RSS en 776,372 KiB, memoria disponible mínima de 14,195,360 KiB y carga de un minuto máxima de 0.10.

## Integridad raíz

```text
manifest.json          f7fb63aee78b3248105f8891075535606b3dda44ae0a7a214e96e52b7929a411
capture.pcap0          63cd70fcb44a079714234e352be7990702d30132f32b285b68aa7e5cd59cd7f0
multilayer-v1.csv      98cd3fdf7963b134aabce3f1eb78c71107862441f926078db259010523113f2b
extraction-report.json 21b52a26b446d07d9cec35a29673348ae755db9fb23717fa04034b517d4f926b
ledger                 62a62ad744418d86b5b0472c43197897259cc9baab92bcd1e205a4cf6ebd247a
```

## Revisión y decisión

Claude Code 2.1.217/Haiku emitió **ACEPTAR CONDICIONADO**. No encontró fallos bloqueantes y exigió declarar la tasa aproximada de 8.1 sesiones/s, una sola huella, un solo cliente/destino, PKI no productiva y autocorrelación. Las condiciones quedan satisfechas en este documento.

La campaña representa automatización HTTPS autorizada de alta frecuencia, no comportamiento humano típico. Normalizar este punto no convierte cualquier ráfaga TLS en benigna: F3 deberá medir tasas y contextos ofensivos separados, y la evaluación final comprobará falsos negativos.

El ensamblador acepta once campañas, cero inválidas, cero advertencias, cero duplicados y reporta 134 celdas faltantes.

**CANARIO DE RECAMBIO TLS ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `HTTP-MULTI-1/R01`: una solicitud HTTP secuencial desde el mismo Cliente a cada VIP `.10`, `.11` y `.12`. La concurrencia se evalúa después, por separado, en `HTTP-C2/C4/C8`. Revisión: `../04-revisiones-claude/2026-07-22-canario-TLS-SESSIONS-20-F1.md`.
