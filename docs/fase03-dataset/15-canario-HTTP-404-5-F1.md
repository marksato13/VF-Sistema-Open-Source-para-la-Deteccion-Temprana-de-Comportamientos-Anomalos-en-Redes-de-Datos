# Décimo canario oficial F1 — HTTP 404 legítimo R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-404-5-R01`. Es la décima campaña aceptada y la primera celda oficial del estrato de error HTTP legítimo.

## Objetivo

El perfil produce cinco solicitudes secuenciales a recursos inexistentes. Su propósito no es simular enumeración ofensiva ni tráfico pesado, sino aportar normalidad explícita con `http_error_ratio_60s=1`: un 404 aislado o de baja frecuencia no debe considerarse ataque por sí solo. La decisión futura debe usar su combinación con tasas, intentos de flujo, completitud SYN y las demás features.

## Preflight

El preflight confirmó:

- Git limpio y sincronizado en `2a7e969f29f9cd4216c904763e4ebd408e468ce3`;
- ID libre, ausencia de captura activa y 145,691,938,816 bytes disponibles;
- gate de almacenamiento PASS;
- `America/Lima` y NTP sincronizado en las cuatro VM remotas;
- rutas de Cliente y Kali hacia `10.30.0.10` mediante `10.20.0.1`;
- `ppi-server-firewall`, NGINX, dnsmasq, `ppi-iperf3`, chrony y SSH activos;
- respuesta 404 correcta y generador remoto con el mismo SHA-256 que el archivo versionado;
- Suricata activo, sin drops, `decoder.invalid` ni overflow.

La comprobación inicial consultó por error una unidad inexistente llamada `ppi-firewall`. La unidad desplegada real es `ppi-server-firewall.service`, de tipo `oneshot`, y estaba `active (exited)` con resultado exitoso. `ppi-iperf3.service` también estaba `active (running)`.

Sensor, Servidor y Cliente no tenían IPv4 externa activa. Kali conservaba `172.17.25.113/24` configurada localmente, pero `eth0` estaba `DOWN`, sin ruta externa; VM01 no alcanzó esa dirección por ICMP ni TCP/22. Esto no contaminó la campaña, aunque constituye un riesgo latente si la NIC se reconecta: cada preflight debe seguir verificando enlace, rutas y alcanzabilidad.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-404-5` / `R01` |
| Escenario / argumentos | `http-missing` / `5` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

## Ejecución e integridad

La captura comenzó a las `22:52:43` y cerró a las `22:54:04 America/Lima`. El escenario devolvió cinco líneas, sin stderr y con código de salida cero:

```json
{"request":1,"http_code":404}
{"request":2,"http_code":404}
{"request":3,"http_code":404}
{"request":4,"http_code":404}
{"request":5,"http_code":404}
```

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 50 / 50 paquetes |
| PCAP total / archivos | 6,309 bytes / 1 |
| Drops tcpdump | 0 |
| Delta Suricata | 52 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 20 / 20 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 54, stderr vacío |
| SHA campaña/features | todos PASS |

El PCAP contiene únicamente TCP entre `10.20.0.20` y `10.30.0.10`: 5 SYN, 5 SYN/ACK, 10 FIN y 0 RST. Cada solicitud abrió y cerró correctamente su conexión.

## EVE y tamaño de paquetes

EVE contiene diez eventos `stats`, cinco `http` y cinco `fileinfo`. Los eventos HTTP corresponden exactamente a `/recurso-inexistente-1` hasta `/recurso-inexistente-5`, todos con estado 404 y cuerpo de 162 bytes. Cada `fileinfo` terminó `CLOSED`, con `gaps=false` y tamaño 162. No apareció la solicitud de preflight ni tráfico ajeno.

Los 50 paquetes miden menos de 500 bytes; la longitud IPv4 media fue 95.70 bytes y la máxima 378. El 0 % dentro de 500–1500 bytes es correcto para este estrato de respuestas pequeñas. No sustituye la evidencia pesada: las ocho campañas HTTP/HTTPS anteriores ya cubren ese objetivo de forma separada.

## Features y dependencia temporal

El extractor consumió 50 paquetes y cinco observaciones HTTP. Produjo dos filas elegibles:

| Fin de ventana UTC | Paquetes 10 s | Intentos 30 s | SYN 10 s | HTTP 60 s | Completitud SYN | Ratio de error HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `03:53:50` | 10 | 1 | 1 | 1 | 1.0 | **1.0** |
| `03:54:00` | 40 | 5 | 4 | 5 | 1.0 | **1.0** |

La primera solicitud cayó justo antes del límite decimal de ventana y las otras cuatro justo después. Por eso los conteos de 10 segundos se dividen 1+4, mientras el horizonte HTTP de 60 segundos de la segunda fila conserva las cinco solicitudes. Las filas son válidas, pero están autocorrelacionadas: no deben presentarse como dos clientes ni como dos comportamientos independientes.

La campaña usa un solo cliente, un solo servidor, método GET, rutas sintéticas y cinco solicitudes secuenciales. Demuestra la existencia de 404 legítimos de baja tasa, no la diversidad completa de errores web ni un fuzzing de rutas.

## Recursos

Suricata alcanzó 1.52 % de CPU, mantuvo RSS en 776,372 KiB, memoria disponible mínima de 14,198,528 KiB y carga de un minuto máxima de 0.26. No hubo presión de recursos.

## Integridad raíz

```text
manifest.json          1073c9f51fed3e57fa5b49b8515fe59ca961769bbb2a53d1db215cded0f04927
capture.pcap0          3e58f9672c7b9cea0646942f96b7f331c7711c6aea31af433d0f6837ad6bba37
multilayer-v1.csv      6c8c1663705f1632ebfe2ffc20d98fdb8479903525709c47aba48caa0f35bdd2
extraction-report.json 91dd80bbef531c5ca498087c16421428cce52996fe0f3604872e5c92d4146dc4
ledger                 81d435d5c7b70ed1e9667de0021e0a1ab95ebbe0f8674bb68a56587a12c9fdd1
```

## Revisión y decisión

Claude Code 2.1.217/Haiku emitió **ACEPTAR** sin fallos bloqueantes. Identificó como límites no bloqueantes la baja diversidad, el tamaño de muestra, la repetición sintética y la dependencia entre ventanas. Codex verificó esas observaciones contra PCAP, EVE y CSV.

El ensamblador acepta diez campañas, cero inválidas, cero advertencias, cero duplicados y reporta 135 celdas faltantes.

**CANARIO HTTP 404 LEGÍTIMO ACEPTADO CON LIMITACIONES DECLARADAS.** El siguiente perfil exacto es `TLS-SESSIONS-20/R01`: veinte conexiones HTTPS secuenciales a `/health`, no concurrentes. Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTP-404-5-F1.md`.

> **Seguimiento:** `TLS-SESSIONS-20/R01` fue ejecutado y aceptado con veinte sesiones TLS 1.3 y dos filas elegibles. Ver `16-canario-TLS-SESSIONS-20-F1.md`.
