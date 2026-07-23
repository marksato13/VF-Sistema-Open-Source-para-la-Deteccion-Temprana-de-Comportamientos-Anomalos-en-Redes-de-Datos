# Duodécimo canario oficial F1 — HTTP multidestino R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-MULTI-1-R01`. Es la duodécima campaña aceptada y la primera celda oficial del estrato HTTP multidestino.

## Objetivo y alcance

El perfil realiza una solicitud HTTP secuencial desde `10.20.0.20` hacia cada VIP `10.30.0.10`, `.11` y `.12`. Su objetivo es producir un caso normal con tres direcciones destino distintas y comprobar `unique_dst_ip_ratio_30s`.

Las VIP son identidades lógicas persistentes en una sola VM Servidor, no tres máquinas, enlaces o dominios de fallo independientes. La campaña mide diversidad de direcciones IP observables en Capa 3; no demuestra diversidad física, múltiples clientes ni concurrencia.

## Preflight

El preflight confirmó Git limpio y sincronizado en `1f03de7ecf113a776b9b0d7ce7d1b129c8e31e83`, ID libre, ausencia de captura activa, 145,691,377,664 bytes disponibles y almacenamiento PASS.

Las cuatro VM remotas mantuvieron `America/Lima` y NTP sincronizado. Cliente y Kali enrutaron hacia la DMZ mediante el Sensor. Las tres VIP estaban presentes y `/health` devolvió HTTP 200 en cada una. El generador remoto conservó el hash versionado y Suricata estaba activo sin pérdidas ni errores. Los tres health checks de preflight fueron seguidos por 70 segundos de quietud.

Kali conservó `172.17.25.113/24` en `eth0`, pero la interfaz seguía `DOWN`, sin ruta externa y bloqueada desde VM01 por ICMP y TCP/22. El riesgo de reconexión permanece como gate.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-MULTI-1` / `R01` |
| Escenario / argumentos | `http-multi` / `1` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `43de3a417d75f4818c5a553268b80ce3a5805109a3bbc6b605e9fb0b8f50b485` |

## Ejecución e integridad

La captura comenzó a las `23:23:31` y cerró a las `23:24:51 America/Lima`. El escenario terminó sin stderr:

```json
{"target":"10.30.0.10","request":1,"http_code":200}
{"target":"10.30.0.11","request":1,"http_code":200}
{"target":"10.30.0.12","request":1,"http_code":200}
```

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 30 / 30 paquetes |
| PCAP total / archivos | 3,369 bytes / 1 |
| Drops tcpdump | 0 |
| Delta Suricata | 34 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 16 / 16 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 53, stderr vacío |
| SHA campaña/features | todos PASS |

El PCAP contiene tres conexiones completas: un SYN hacia cada VIP, 3 SYN/ACK, 6 FIN y 0 RST.

## EVE y tamaño de paquetes

EVE contiene diez `stats`, tres `http` y tres `fileinfo`. Cada VIP recibió exactamente un `GET /health`, respondió 200 con 36 bytes y produjo `fileinfo.state=CLOSED`, `gaps=false`. No apareció tráfico de preflight ni ruido ajeno.

Los treinta paquetes son menores de 500 bytes; su longitud IPv4 media es 81.50 bytes y la máxima 251. El 0 % en el rango 500–1500 bytes es esperado para tres health checks y no reemplaza las campañas pesadas ya aceptadas.

## Feature L3

El extractor produjo una fila elegible:

| Feature | Valor | Interpretación |
|---|---:|---|
| `packet_count_10s` | 30 | diez paquetes por conexión |
| `flow_attempt_count_30s` | 3 | tres conexiones |
| `syn_count_10s` | 3 | un SYN por VIP |
| `http_request_count_60s` | 3 | tres health checks |
| `unique_dst_ip_ratio_30s` | **1.0** | 3 destinos / 3 intentos |
| `unique_dst_port_ratio_30s` | 0.33333333 | 1 puerto / 3 intentos |
| `syn_completion_ratio_10s` | 1.0 | tres conexiones completadas |
| `http_error_ratio_60s` | 0.0 | tres respuestas 200 |

El ratio 1.0 no significa tres muestras independientes ni tres hosts físicos. Es un componente de una sola fila producida por una campaña. Tampoco es un valor único en F1: varias campañas de una sola conexión tienen ratio 1/1. Aquí se diferencia por `flow_attempt_rate_10s=0.3`, tres intentos y la procedencia multidestino.

La campaña completa la celda oficial, pero no basta por sí sola para estimar una distribución. El ensamblador impide construir o entrenar con F1 incompleta; `HTTP-MULTI-5` aportará después el punto 3/15 = 0.2 y las cinco repeticiones conservarán la separación train/validation/test.

## Recursos

Suricata alcanzó 1.52 % de CPU, mantuvo RSS en 776,372 KiB, memoria disponible mínima de 14,197,676 KiB y carga de un minuto máxima de 0.18.

## Integridad raíz

```text
manifest.json          14193d8493849bb19876db6806527d1a687f4cbfdc3724cee193bf5c07a8d371
capture.pcap0          37302e055062d5ff016ef162bf6e4bf6152804018f64f8e52fd9888aa414622e
multilayer-v1.csv      1938e5bab8f7ab5e8631e5a08f3f1754bbdc31e06b51028e62ca97f60935828b
extraction-report.json a5fd44fcff82f7fdad0dae051bcf38dfa920147e4a8e171009c1e8f3eed2b4ea
ledger                 dd14f59f10a594c03fcb24f7296b5aeefd471406d9326d81b5baa572bdfbb10d
```

## Revisión y decisión

Claude Code 2.1.217/Haiku emitió **ACEPTAR CONDICIONADO** por tamaño de muestra, una sola VM y una sola fila. Codex confirmó los límites y corrigió que los tres destinos no son réplicas estadísticas, que la campaña es `experiment/train` y que el ratio 1.0 ya aparece en otras campañas normales.

La condición de no entrenar con esta fila aislada está implementada estructuralmente: el ensamblador no construirá los splits hasta aceptar las 145 celdas.

El ensamblador acepta doce campañas, cero inválidas, cero advertencias, cero duplicados y reporta 133 celdas faltantes.

**CANARIO HTTP MULTIDESTINO ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `HTTP-MULTI-5/R01`: cinco solicitudes secuenciales por VIP, quince en total, con ratio esperado 3/15 = 0.2. Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTP-MULTI-1-F1.md`.
