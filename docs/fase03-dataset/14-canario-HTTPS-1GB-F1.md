# Noveno canario oficial F1 — HTTPS 1 GB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTPS-1GB-R01`. Es la novena campaña aceptada y cierra los cuatro tamaños HTTPS individuales de R01.

## Alcance y preflight

El perfil mide volumen y duración en una sola sesión TLS 1.3. La diversidad de sesiones permanece separada en `TLS-SESSIONS-20`; el certificado continúa siendo autofirmado y el Cliente usa `--insecure`.

El preflight confirmó Git limpio en `a68b8a6b98807966e266bfd825d0a19dd6baffdf`, 146,830,491,648 bytes disponibles, gate de disco PASS, ID libre, NTP/zona correctos, NIC externas en `DOWN`, rutas por el Sensor, NGINX activo, archivo de 1,073,741,824 bytes, HTTPS 200, generador íntegro y Suricata sin pérdidas. El runner aplicó 70 segundos de quietud y 60 de warm-up capturado.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTPS-1GB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `1GB`, límite `20M` bytes/s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77` |

## Ejecución e integridad

La campaña comenzó a las `22:35:42` y cerró a las `22:38:50 America/Lima`. El escenario terminó sin stderr:

```json
{"http_code":200,"bytes":1073741824,"seconds":51.021313,"speed_Bps":21044966}
```

El throughput calculado con bytes y tiempo es 168.36 Mbit/s decimales, inferior al techo calibrado de 200 Mbit/s.

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 757,999 / 757,999 paquetes |
| PCAP total | 1,138,215,605 bytes |
| Archivos PCAP | 3 |
| Tamaños | 512,001,211; 512,001,416; 114,212,978 bytes |
| Drops tcpdump | 0 |
| Delta Suricata | 758,005 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 25 / 25 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 133, stderr vacío |
| SHA campaña/features | todos PASS |

## Distribución y recursos

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 14,830 | 1.9565 % |
| De 500 a 1500 bytes | 743,169 | **98.0435 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 743,055 | 98.0285 % |

La longitud media fue 1,471.61 bytes y la máxima 1,500. Los paquetes pequeños son todos TCP, 14,786 sin payload y cero fragmentados.

Suricata alcanzó 10.36 % CPU, RSS de 776,372 KiB, memoria disponible mínima de 13,986,016 KiB y carga máxima de 0.59.

## EVE y features

EVE contiene 23 stats, un TLS 1.3 y el flow correspondiente a la misma transferencia. No existe ruido de preflight, mDNS ni IPv6.

El extractor produjo siete filas elegibles. Seis contienen la transferencia; la última registra solo cuatro paquetes de cierre:

| Ventana UTC | Paquetes | `mean_ip_len_10s` | `large_ip_ratio_10s` | `tls_session_rate_60s` |
|---|---:|---:|---:|---:|
| `03:36:50` | 24,259 | 1,331.34271817 | 0.88363082 | 0.01666667 |
| `03:37:00` | 160,564 | 1,453.57993074 | 0.96797539 | 0.01666667 |
| `03:37:10` | 147,028 | 1,481.77213864 | 0.98749218 | 0.01666667 |
| `03:37:20` | 146,815 | 1,483.40027926 | 0.98856384 | 0.01666667 |
| `03:37:30` | 146,822 | 1,482.69801528 | 0.98808762 | 0.01666667 |
| `03:37:40` | 132,507 | 1,482.52987389 | 0.98797045 | 0.01666667 |
| `03:37:50` | 4 | 58.0 | 0.0 | 0.0 |

La última fila es defendible como normalidad de cierre: contiene FIN/ACK posteriores a la carga y el handshake ya quedó fuera de la ventana L7 de 60 segundos. No se elimina por tener bajo volumen; borrarla ocultaría el comportamiento temporal real. El ensamblador no reporta vectores duplicados.

## Integridad raíz

```text
manifest.json          5d889d4c5923f2cb486338d2b4ec195b4a284f6ffc2c8b6535234c7222262305
capture.pcap0          9d95acbbfaf7fe4df4c635f495ed66af0fe66a649817934189d6f2a45cc3a80d
capture.pcap1          788701251f681a682e6a4ce516ab4aaa561381f0594e14c85653ae76fb7f20b2
capture.pcap2          e815ce53acafa427e33e79e9812d8bf2a1db41532c5da6708ff868f3f7161796
multilayer-v1.csv      9b0a3de75eb8a450bf2597bef6f0c721811bb5b080e06748005ce74797034008
extraction-report.json 5200095e776cf6cac55ba0cf9e55516113256a7f700f9a7a7ccc19dbda20f161
ledger                 be3ae641e75f032611e3eac6986e615f26cb89175e75b630cff0a1c2252dbdd1
```

## Revisión y decisión

Claude Code/Haiku emitió **ACEPTAR** y consideró defendible conservar la ventana de cierre. Ratificó que una sesión única respeta el contrato y que la diversidad se abordará en `TLS-SESSIONS-20`. Su throughput aproximado se corrigió a 168.36 Mbit/s; la conclusión de estar bajo el techo no cambia.

El ensamblador acepta nueve campañas, cero inválidas, cero advertencias, cero duplicados y 136 faltantes.

**CANARIO HTTPS 1 GB ACEPTADO.** Se completan los tamaños individuales HTTP y HTTPS de R01. El siguiente perfil exacto de la matriz es `HTTP-404-5/R01`. Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTPS-1GB-F1.md`.

> **Seguimiento:** `HTTP-404-5/R01` fue ejecutado y aceptado con cinco 404 legítimos y dos filas elegibles. Ver `15-canario-HTTP-404-5-F1.md`.
