# Sexto canario oficial F1 — HTTPS 10 MB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTPS-10MB-R01`. Es la sexta campaña aceptada, la primera HTTPS y la primera que activa `tls_session_rate_60s` en el dataset oficial.

## Alcance

Este escenario representa una transferencia HTTPS mínima de laboratorio con TLS 1.3 y certificado autofirmado. El Cliente usa `curl --insecure` de forma explícita. Sirve para capturar volumen cifrado, comportamiento TCP y establecimiento TLS; no representa todavía diversidad de autoridades certificadoras, SNI, OCSP, múltiples servidores ni fallos criptográficos de producción.

## Preflight y quietud

El preflight confirmó:

- Git limpio y sincronizado en `ca9b188b57951909996cf32c0b0cae5b5713edf5`;
- volumen oficial con 147,509,428,224 bytes disponibles y gate global en PASS;
- ID libre y ausencia de campaña/captura activa;
- NTP y `America/Lima` en las cuatro VMs remotas;
- NIC externas en `DOWN` y rutas LAN↔DMZ mediante el Sensor;
- NGINX activo, archivo de 10,485,760 bytes y HTTPS 200 desde Servidor y Cliente;
- `ssl_verify_result=18`, esperado para el certificado autofirmado aceptado solo por `--insecure`;
- generador remoto idéntico al versionado;
- Suricata activo con cero drops, ifdrops, errores de decodificación y overflow.

El runner aplicó 70 segundos de quietud antes de abrir EVE/PCAP. Después inició el warm-up capturado de 60 segundos.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTPS-10MB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `10MB`, límite `2M` bytes/s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a` |

## Ejecución

La campaña comenzó a las `21:55:52` y cerró a las `21:57:17 America/Lima`. El escenario terminó con código 0 y stderr vacío:

```json
{"http_code":200,"bytes":10485760,"seconds":4.528286,"speed_Bps":2315613}
```

La respuesta y el conteo los registró `curl` en el extremo cliente. Suricata no puede leer el código HTTP ni el cuerpo dentro de TLS.

## Captura e integridad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 7,608 / 7,608 paquetes |
| Tamaño PCAP | 11,130,372 bytes |
| Drops tcpdump | 0 |
| Delta de captura Suricata | 7,610 paquetes |
| Drops / ifdrops Suricata | 0 / 0 |
| Decoder invalid / alert overflow | 0 / 0 |
| EVE esperado/extraído | 12 / 12 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras del Sensor | 57, stderr vacío |
| `SHA256SUMS` | todos PASS |

## Distribución IPv4

| Rango | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 349 | 4.5873 % |
| De 500 a 1500 bytes | 7,259 | **95.4127 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 7,240 | 95.1630 % |

La longitud media fue 1,432.98 bytes y la máxima 1,500. Los 349 paquetes pequeños son todos TCP, 339 sin payload y cero fragmentados. El cifrado agrega registros TLS pequeños legítimos además del control TCP.

## EVE y señal L7

El segmento contiene 10 stats, un evento TLS y un flow IPv6 link-local. El evento relevante registra:

- TLS 1.3;
- iniciador `10.20.0.20` y destino `10.30.0.10`;
- JA3, JA3S y JA4;
- ALPN ofrecido `h2` y `http/1.1`.

No existe evento HTTP ni fileinfo porque el contenido está cifrado. La descarga completa se prueba con la salida del Cliente y PCAP, no con inspección del cuerpo por EVE.

### Flow IPv6 fuera de alcance

El flow `fe80::…:158a → ff02::2` comenzó a las `21:55:18`, durante la quietud, y Suricata lo emitió a las `21:55:57` por timeout, ya dentro de la campaña. Es control IPv6 link-local originado por el Sensor, no el preflight HTTPS:

- está fuera del filtro IPv4 del PCAP;
- no pertenece a la entidad `10.20.0.0/24`;
- el extractor ignora `event_type=flow`;
- no modifica ninguna fila.

La quietud cumplió su objetivo de drenar la sesión HTTPS del preflight, pero no pretende suprimir tráfico periódico generado durante sus 70 segundos. La evidencia EVE cruda se conserva y la elegibilidad se decide por alcance y tipo de evento, no borrando registros incómodos.

## Features y recursos

El extractor procesó 7,608 paquetes y una observación TLS. Produjo dos filas con `eligible_training=True`:

| Ventana UTC | Paquetes | `mean_ip_len_10s` | `large_ip_ratio_10s` | `tls_session_rate_60s` |
|---|---:|---:|---:|---:|
| `02:57:00` | 4,086 | 1,398.69016153 | 0.93049437 | **0.01666667** |
| `02:57:10` | 3,522 | 1,472.75979557 | 0.98154458 | **0.01666667** |

El valor equivale a una sesión única dividida entre 60 segundos. `http_request_count_60s=0` y `http_error_ratio_60s=0` significan “HTTP no observable dentro de TLS”, no prueba de ausencia de errores HTTP.

Suricata alcanzó 2.26 % de CPU, RSS de 776,372 KiB, memoria disponible mínima de 14,183,216 KiB y carga máxima de 0.26.

## Integridad raíz

```text
manifest.json          e2b26c7cd7c698699c6881322dba5422928bff9122638c94e0bfc0b31e898c30
capture.pcap0          43b7ef71f53100efd09e73e0ab58625d3aa93d1d6f5daf4effd8cf40684079f6
multilayer-v1.csv      65229d8fe1d4fd366c8a451b75b65abeaa1705b22ce5ce71fdeef62729302f53
extraction-report.json a114186c63178c6ad22587700ace8300f2f749b7d6a516b45575619852a4c168
ledger                 a0c646d1f519bbc1a1128d7e30e22bd33566dd2c84403b1bb7c63e0de7560ff3
```

## Revisión y decisión

Claude Code/Haiku emitió **ACEPTAR CONDICIONADO** a declarar el certificado autofirmado, la opacidad L7 y la necesidad futura de diversidad TLS. Esas condiciones quedan explícitas aquí. Dos imprecisiones del dictamen fueron corregidas contra timestamps y código: el flow IPv6 se emitió durante la campaña, y el extractor sí consume el evento TLS aunque descarta el flow.

El ensamblador acepta seis campañas, cero inválidas, cero advertencias y 139 faltantes.

**CANARIO HTTPS 10 MB ACEPTADO CON LIMITACIONES.** El siguiente perfil en orden es `HTTPS-100MB/R01`.

Revisión completa: `../04-revisiones-claude/2026-07-22-canario-HTTPS-10MB-F1.md`.

> **Seguimiento:** `HTTPS-100MB/R01` fue ejecutado y aceptado con 96.9502 % de paquetes en el rango objetivo y cero drops. Ver `12-canario-HTTPS-100MB-F1.md`.
