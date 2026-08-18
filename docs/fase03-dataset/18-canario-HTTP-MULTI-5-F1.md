# Decimotercer canario oficial F1 — HTTP multidestino repetido R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-MULTI-5-R01`. Es la decimotercera campaña aceptada y la segunda celda oficial del estrato HTTP multidestino.

## Objetivo y alcance

El perfil realiza cinco solicitudes HTTP secuenciales desde `10.20.0.20` hacia cada VIP `10.30.0.10`, `.11` y `.12`: quince conexiones en total. Su objetivo es complementar el punto 3/3 de `HTTP-MULTI-1` con `unique_dst_ip_ratio_30s=3/15=0.2`.

Las tres VIP son identidades lógicas en una sola VM Servidor. El resultado demuestra diversidad de direcciones IP observables en Capa 3, no tres hosts físicos, múltiples clientes, dominios de fallo distintos ni concurrencia.

## Preflight

El preflight confirmó Git limpio y sincronizado en `90213633c0cc061d618e281e5ba4e4a010e4040f`, ID libre, ausencia de captura activa, 145,691,176,960 bytes disponibles y almacenamiento PASS.

Las cuatro VM remotas mantuvieron `America/Lima` y NTP sincronizado. Cliente y Kali conservaron la ruta por el Sensor; las tres VIP estaban presentes y respondieron HTTP 200. Los servicios, Suricata y el generador remoto pasaron sus controles. Los health checks de preflight fueron seguidos por 70 segundos de quietud.

Kali conservó `172.17.25.113/24` en `eth0`, pero la interfaz seguía `DOWN`, sin ruta externa y bloqueada desde VM01 por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-MULTI-5` / `R01` |
| Escenario / argumentos | `http-multi` / `5` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

El hash de argumentos también puede aparecer en otro perfil cuya lista canónica sea `["5"]`. No identifica por sí solo una campaña: el ensamblador cruza además ID, escenario, perfil, repetición, matriz, manifiesto y ledger.

## Ejecución e integridad

La captura comenzó a las `23:38:19` y cerró a las `23:39:40 America/Lima`. El escenario produjo quince HTTP 200, cinco por VIP, sin stderr y con código de salida cero.

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 150 / 150 paquetes |
| PCAP total / archivos | 16,749 bytes / 1 |
| Drops tcpdump | 0 |
| Delta Suricata | 152 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 40 / 40 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 54, stderr vacío |
| SHA campaña/features | todos PASS |

El PCAP contiene quince conexiones completas: cinco SYN por VIP, 15 SYN/ACK, 30 FIN y 0 RST. Los quince eventos HTTP abarcan aproximadamente 1.67 segundos.

## EVE y tamaño de paquetes

EVE contiene diez `stats`, quince `http` y quince `fileinfo`. Cada VIP recibió cinco `GET /health`, todos con estado 200 y cuerpo de 36 bytes. Los quince `fileinfo` terminaron `CLOSED`, `gaps=false`, tamaño 36. No apareció el preflight ni tráfico ajeno.

Los 150 paquetes son menores de 500 bytes; la longitud IPv4 media es 81.50 bytes y la máxima 251. El 0 % en 500–1500 bytes es correcto para health checks pequeños y no se presenta como evidencia de tráfico pesado.

## Features

El extractor produjo una fila elegible:

| Feature | Valor | Interpretación |
|---|---:|---|
| `packet_count_10s` | 150 | diez paquetes por conexión |
| `flow_attempt_count_30s` | 15 | quince conexiones |
| `syn_count_10s` | 15 | cinco SYN por VIP |
| `http_request_count_60s` | 15 | quince health checks |
| `packet_rate_10s` | 15.0 | paquetes por segundo en la ventana |
| `flow_attempt_rate_10s` | 1.5 | intentos por segundo |
| `unique_dst_ip_ratio_30s` | **0.2** | 3 destinos / 15 intentos |
| `unique_dst_port_ratio_30s` | 0.06666667 | 1 puerto / 15 intentos |
| `syn_completion_ratio_10s` | 1.0 | quince conexiones completadas |
| `http_error_ratio_60s` | 0.0 | quince respuestas 200 |

Existe una sola fila porque todo el episodio cayó dentro de un único intervalo de diez segundos; no hay filas inactivas descartadas en el CSV. Los 60 segundos de warm-up hacen que su `history_coverage_s=60` y permiten marcarla elegible.

Esta fila y la de `HTTP-MULTI-1` son puntos complementarios, no repeticiones independientes: 3/3 = 1.0 frente a 3/15 = 0.2. El ensamblador bloquea el entrenamiento mientras F1 no alcance las 145 celdas, evitando usar cualquiera de ellas de forma aislada.

## Recursos

Suricata alcanzó 2.25 % de CPU, mantuvo RSS en 776,372 KiB, memoria disponible mínima de 14,165,660 KiB y carga de un minuto máxima de 0.27.

## Integridad raíz

```text
manifest.json          1d8c661537a1588835065966432755b415cf7f1adbad2ad731b50160e7f3a480
capture.pcap0          f5e2d44224f1b72fc89b01dc46d2f0640ea8afe90522266e96abe4f2ce170870
multilayer-v1.csv      c0a485976e2f81327950f64e162391962ddb89f4cf53a6bddbaceac8a6556c02
extraction-report.json 91f5609f914196699c3a3efc606a0ebabb4c997fbbf7c7ecb7a12e77d857d7fa
ledger                 cda99b6d7514d223a3c1219c2cfae06c552129b33ff1333b71e4301bfd6ee95b
```

## Revisión y decisión

Claude Code 2.1.217/Haiku emitió **ACEPTAR CONDICIONADO** y no encontró bloqueantes. Exigió declarar una sola fila, ráfaga rápida, VIP lógicas, un cliente/puerto y el riesgo latente de Kali. Estas condiciones están documentadas.

Se corrigieron cuatro imprecisiones de la revisión: existen quince conexiones, no treinta; la campaña es `experiment/train`, no calibración; las 14 features no incluyen RTT; y el siguiente límite `10M` está expresado en bytes/s, no bits/s.

El ensamblador acepta trece campañas, cero inválidas, cero advertencias, cero duplicados y reporta 132 celdas faltantes.

**CANARIO HTTP MULTIDESTINO REPETIDO ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `HTTP-C2/R01`: dos descargas concurrentes de 100 MB a un solo destino, limitadas a `10M` bytes/s por flujo. Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTP-MULTI-5-F1.md`.

> **Seguimiento:** `HTTP-C2/R01` fue ejecutado y aceptado con dos flujos solapados, 95.7053 % de paquetes pesados y cero drops. Ver `19-canario-HTTP-C2-F1.md`.
