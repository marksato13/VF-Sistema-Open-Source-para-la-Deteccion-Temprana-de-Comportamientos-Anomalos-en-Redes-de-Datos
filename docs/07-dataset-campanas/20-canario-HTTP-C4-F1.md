# Decimoquinto canario oficial F1 — HTTP concurrente C4 R01

Fecha: 23 de julio de 2026. Campaña: `F1N-HTTP-C4-R01`. Es la decimoquinta campaña aceptada y la segunda celda oficial de concurrencia HTTP.

## Objetivo y alcance

El perfil ejecuta simultáneamente cuatro descargas de `100MB.bin` desde el Cliente `10.20.0.20` hacia el servidor NGINX interno `10.30.0.10`. Cada `curl` usa `--limit-rate 5M`: 5 MiB/s nominales por flujo. El agregado nominal permanece en 20 MiB/s o 167.77216 Mbit/s decimales.

La prueba no necesita Internet. Cliente y Servidor se comunican exclusivamente por PPI-LAN/PPI-DMZ a través del Sensor:

```text
Cliente 10.20.0.20
        │  HTTP interno
        ▼
Sensor 10.20.0.1 / 10.30.0.1
        │
        ▼
Servidor 10.30.0.10 — NGINX — /srv/ppi/files/100MB.bin
```

Los cuatro flujos pertenecen a un solo Cliente y un solo destino. Demuestran concurrencia de conexiones, no cuatro usuarios ni cuatro equipos independientes.

## Preflight

El preflight confirmó Git limpio y sincronizado en `243b9096bb50b51b532508b1c39eb77ac8a08ff1`, ID libre, ausencia de captura activa, 145,468,416,000 bytes disponibles en VM01 y gate de almacenamiento PASS.

Las cuatro VM remotas conservaron `America/Lima` y NTP sincronizado. Las NIC externas estaban inactivas, Kali no tenía ruta externa y TCP/22 externo permaneció bloqueado desde VM01. Las rutas Cliente/Kali→Sensor→Servidor, el retorno DMZ, los servicios y Suricata pasaron. `/srv/ppi/files/100MB.bin` midió exactamente 104,857,600 bytes y un HEAD interno devolvió HTTP 200. El generador local y remoto coincidió en SHA-256.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-C4` / `R01` |
| Escenario / argumentos | `http-concurrent` / `4 100MB 5M` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `d8197cefd6d7c50ed78fad328040916bb2b3efbe78c449c62e4c0d6502e93d73` |

## Ejecución y concurrencia

El manifiesto registra ejecución entre `00:12:44` y `00:14:46 America/Lima`. Los cuatro procesos terminaron sin stderr:

| Flujo | HTTP | Bytes | Tiempo | Velocidad reportada |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 19.504977 s | 5,375,940 B/s |
| 2 | 200 | 104,857,600 | 19.526496 s | 5,370,016 B/s |
| 3 | 200 | 104,857,600 | 19.517645 s | 5,372,451 B/s |
| 4 | 200 | 104,857,600 | 19.512357 s | 5,373,907 B/s |

El PCAP distingue los puertos origen `59702`, `59716`, `59724` y `59740`. Sus primeros paquetes aparecieron entre `00:13:50.850348` y `00:13:50.864120`: un intervalo inicial de solo 13.772 ms. Sus spans fueron 19.506359, 19.523973, 19.514055 y 19.519256 segundos. Cada flujo tuvo un SYN, un SYN/ACK, dos FIN y cero RST. Esto prueba solapamiento real de los cuatro flujos.

Se transfirieron 419,430,400 bytes. La suma de velocidades reportadas fue 171.938512 Mbit/s; bytes totales sobre el mayor tiempo equivalen a 171.840519 Mbit/s. El observado superó aproximadamente 2.48 % el nominal, pero conservó 28.061488 Mbit/s de margen hasta el techo operativo de 200 Mbit/s. `curl --limit-rate` limita el promedio y no se interpreta como shaping exacto.

## Integridad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 301,517 / 301,517 paquetes |
| PCAP total / archivos | 444,599,458 bytes / 1 |
| TCP | 4 SYN, 4 SYN/ACK, 8 FIN, 0 RST |
| Drops tcpdump | 0 |
| Delta Suricata | 301,523 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 25 / 25 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 84, stderr vacío |
| SHA campaña/features | todos PASS |

## Paquetes, EVE y recursos

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 11,517 | 3.8197 % |
| De 500 a 1500 bytes | 290,000 | **96.1803 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 289,862 | 96.1345 % |

La longitud media fue 1,444.54 bytes y la máxima 1,500. C4 amplía con tráfico concurrente legítimo el rango normal pedido por el jurado.

EVE contiene quince `stats`, cuatro `http`, cuatro `fileinfo` y dos `mdns`. Los cuatro HTTP son GET 200 a `/files/100MB.bin`. Los `fileinfo` quedaron `TRUNCATED` a 102,400 bytes, `gaps=false`, debido al límite de inspección de Suricata; las cuatro transferencias y el PCAP sí están completos.

Los dos eventos mDNS proceden del Cliente durante la captura: uno IPv4 hacia `224.0.0.251` y otro IPv6 link-local hacia `ff02::fb`, ambos con consultas `_ipp._tcp.local` y `_ipps._tcp.local`. El filtro PCAP oficial captura únicamente LAN↔DMZ, por lo que mDNS no está en el PCAP. El extractor consume `http`, `dns` y `tls`, no `mdns`; esos eventos permanecen en EVE crudo para trazabilidad y no alteran las features.

Suricata alcanzó 43.41 % de CPU y 777,128 KiB de RSS. La memoria disponible mínima fue 14,059,304 KiB y la carga de un minuto máxima 1.33. No existe un umbral formal de CPU para aceptar F1; estos valores se conservan como línea base operacional y la integridad se decide por drops, errores, recursos disponibles y evidencia completa.

## Features y cola de cierre

El extractor produjo tres filas elegibles:

| Fin UTC | Paquetes | `byte_rate_10s` | `large_ip_ratio_10s` | SYN | Intentos 30 s | HTTP 60 s | Completitud SYN |
|---|---:|---:|---:|---:|---:|---:|---:|
| `05:14:00` | 176,930 | 24,960,254.4 | 0.93841632 | 4 | 4 | 4 | 1.0 |
| `05:14:10` | 124,574 | 18,595,070.4 | 0.99511937 | 0 | 4 | 4 | 0.0 |
| `05:14:20` | 13 | 67.6 | 0.0 | 0 | 4 | 4 | 0.0 |

Las tres filas pertenecen al mismo episodio y no son repeticiones independientes. `campaign_id` preserva ese grupo causal.

La tercera fila contiene exactamente trece paquetes TCP posteriores al corte de `05:14:10`: ocho FIN y cinco ACK, cero payload y cero RST. Es la terminación normal de los cuatro flujos, no una nueva transferencia ni un ataque. Se conserva porque es una ventana causal válida del comportamiento benigno.

`syn_completion_ratio_10s` usa `min(SYN,SYN/ACK)/SYN` dentro de cada ventana y `safe_ratio` devuelve cero cuando no hay SYN. Por ello las filas segunda y tercera no representan handshakes fallidos: simplemente no contienen SYN nuevos.

Los cuatro intentos se dirigen a una IP y un puerto, de modo que `unique_dst_ip_ratio_30s=1/4=0.25` y `unique_dst_port_ratio_30s=1/4=0.25`.

## Integridad raíz

```text
manifest.json          04846660729f46d12ea14b02217c11820e918d72fb1a6697186b6116691150c8
capture.pcap0          a09b182c7eef15cfaf39d4c67a27588091eb3085d77e2a9911e92c6377d49bbd
multilayer-v1.csv      f060406195ef092a97e020b745cf86149b269642affe372484598e72ef23fbce
extraction-report.json 0ac08fee8e824604d4367cf227b1980cd28314248983886af9fe52adaa012faa
ledger                 739897fc3c17a5d09ec029dd09e267d1920b66690a83d76927a3d364e07ae559
```

## Revisión y decisión

Claude Code 2.1.217/Haiku emitió **ACEPTAR CONDICIONADO** y autorizó C8. Las condiciones quedaron cerradas en este documento: correlación de ventanas, alcance de mDNS, cola FIN/ACK, semántica de CPU y límite `fileinfo`.

Se corrigieron dos extrapolaciones de la revisión: la progresión oficial fue C2→C4, no tres flujos→cuatro, y una predicción de CPU para C8 no es evidencia ni gate. La rotación PCAP prevista para C8 es operación normal mientras los hashes, paquetes y límites pasen.

El ensamblador acepta quince campañas, cero inválidas, cero advertencias, cero duplicados y reporta 130 celdas faltantes.

**CANARIO HTTP C4 ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `HTTP-C8/R01`: ocho descargas concurrentes de 100 MB, `2M` por flujo, nominal agregado 16 MiB/s o 134.217728 Mbit/s y PCAP estimado de 920,000,000 bytes. Se ejecutará en otro paso, tras un preflight nuevo. Revisión: `../04-revisiones-claude/2026-07-23-canario-HTTP-C4-F1.md`.
