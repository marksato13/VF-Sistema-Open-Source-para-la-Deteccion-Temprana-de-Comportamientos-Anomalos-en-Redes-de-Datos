# Vigésimo octavo canario oficial F1 — PING-10 R01

Fecha: 27 de julio de 2026. Campaña: `F1N-PING-10-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Esta celda aporta una línea base ICMP legítima y ligera. Cliente `10.20.0.20` ejecutó diez solicitudes echo hacia Servidor `10.30.0.10`, con intervalo nominal de un segundo. El objetivo es medir `icmp_ratio_10s` y validar el tratamiento de una conversación ICMP completa, no simular reconocimiento ni ataques.

El preflight confirmó Git limpio y sincronizado en `dff7ed4ba5b1c2d4fba0cd62601b3fadae096602`, ID libre, 141,027,766,272 bytes disponibles en el volumen oficial y gate de capacidad en `PASS`. Las cinco máquinas respondieron por SSH y pasaron NTP. La ruta Cliente→Sensor→Servidor y un eco de control funcionaron; Suricata, PCAP y servicios estaban sanos. El generador local y remoto coincidió por SHA-256. Las NIC externas permanecieron `DOWN` y el bypass `172.17.25.111-.114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato | `light` |
| Argumentos | `10`, `1` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4027af88974510696bfebde488ece5ffaa0fdaace6f2d504d035a226e095db67` |

## Resultado ICMP

El generador ejecutó `ping -n -c 10 -i 1 10.30.0.10`. stdout informa diez paquetes transmitidos, diez recibidos, 0 % de pérdida y duración de 9,190 ms. El RTT observado por `ping` fue mínimo/promedio/máximo/mdev de `0.352/0.465/0.976/0.173 ms`; no se le asigna una categoría de rendimiento ni un SLA.

PCAP confirma:

| Control | Resultado |
|---|---:|
| Echo request / echo reply | 10 / 10 |
| Tipo y código de solicitudes | 8 / 0 |
| Tipo y código de respuestas | 0 / 0 |
| Identificador / secuencias | 12333 / 1–10 |
| TTL solicitud / respuesta | 64 / 63 |
| Span primera→última solicitud | 9.190037 s |
| Paquetes perdidos | 0 % |

Las veinte tramas forman diez pares request/reply del mismo diálogo. Todas comparten protocolo, extremos e identificador ICMP; bajo la clave canónica del extractor constituyen **un intento ICMP**, no diez flujos distintos.

## PCAP, EVE y regla de laboratorio

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 20 / 20 / 20 |
| PCAP | 1 archivo / 2,304 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 25 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 21 / 21 |
| Muestras Sensor / stderr | 60 / vacío |
| Transferencia / límite PCAP | verificada / no alcanzado |

Cada paquete mide 84 bytes IPv4: 20 de cabecera IP, 8 de ICMP y 56 de payload. La media y el máximo son 84 bytes; los veinte son menores de 500 bytes. El 0 % de tráfico pesado es correcto para ICMP ligero y no sustituye la cobertura de HTTP/HTTPS e iperf3.

EVE contiene diez `alert` y once `stats`. Cada echo request activó SID `1000001`, `PPI LAB ICMP TEST`, severidad 3, categoría vacía y `action=allowed`. `configs/suricata/local.rules` declara que la regla se reserva para validar el laboratorio y no representa un ataque. Por tanto:

- demuestra que Suricata observó las diez solicitudes;
- no bloqueó tráfico;
- no demuestra detección de anomalías;
- no constituye una evaluación de falsos positivos de un ruleset productivo.

El delta `kernel_packets=25` de Suricata supera en cinco al PCAP filtrado LAN↔DMZ. Esos cinco paquetes no están identificados en el bundle y no se confunden con los once eventos `stats`: los eventos estadísticos no son paquetes. Suricata observa `ens35` completa, mientras tcpdump conserva únicamente el filtro de la campaña.

El Sensor alcanzó CPU puntual máxima de 1.53 %, RSS de 780,308 KiB, memoria disponible mínima de 14,104,512 KiB y carga máxima de 0.12. Son observaciones sin umbral.

## Features

El extractor procesó veinte observaciones de paquete, cero observaciones de aplicación y produjo una fila elegible:

| Ventana UTC | Paquetes | Attempts | Tasa paquetes | Tasa attempts | Ratio ICMP |
|---|---:|---:|---:|---:|---:|
| `2026-07-27T15:24:20+00:00` | 20 | 1 | 2/s | 0.1/s | 1 |

La fila registra además `byte_rate_10s=168 B/s`, `mean_ip_len_10s=84`, `large_ip_ratio_10s=0` y `unique_dst_ip_ratio_30s=1/1=1`. Este último es máximo porque el denominador contiene un solo intento y un solo destino; no prueba escaneo ni ausencia de escaneo.

`unique_dst_port_ratio_30s=0` es el valor seguro cuando no existen intentos TCP/UDP: ICMP no tiene puertos. No debe interpretarse como evidencia sobre diversidad de puertos. SYN, RST, HTTP, DNS y TLS quedan en cero, coherentes con el escenario.

Una fila es una ventana de un episodio, no una repetición independiente. La serie usa un solo par, un identificador, un intervalo fijo y tamaño constante. Isolation Forest todavía no está entrenado; esta celda no demuestra detección, falsos positivos ni generalización.

## Integridad raíz

```text
manifest.json          dbf00e0bc3b84882b3957643a7e29261c1be8a2f9933d97feab57938d87ffd90
capture.pcap0          e5643eeb9758542f0fd6ba63d03fa1e8d2a490b9910e4b622358cb7ae60e25c1
eve-slice              035a120bf22f866fbeb8a9437c29db948c1a705cb9c6ffb6c96ee54fbd38b0b9
campaign SHA256SUMS    234000bc41099cbe826be3ba5751e987bc18eb87a6713e4597384885eabd1bfe
multilayer-v1.csv      7f0a32fbc08ec20300a7f408c736ec496b2da11b58f17f297f561cde9defb79b
extraction-report      17416dae4a35c15358b37fd215fecfe985a1c3df24602d4cd722a988f65e5d01
feature SHA256SUMS     f1cab2329423cbe1346d5de115f59aceae41f2dc9629d01932956969c4159bb7
ledger                 6eceb6cf09b95e0ce4a55e37e49eaf35f57aebdb15143158c8c85df3e357746e
```

Todos los hashes pasaron y la captura residual quedó inactiva. El ensamblador informó 145 campañas esperadas, 28 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 117 faltantes. El dataset completo todavía no puede construirse.

## Decisión

Claude emitió **ACEPTAR CON LIMITACIONES**, pero necesitó cuatro rondas: confundió conteos y composición de paquetes, inventó pesos/particiones, mezcló eventos con paquetes y contaminó una respuesta con cifras del DNS anterior. La respuesta final quedó restringida a los hechos verificados.

**CANARIO PING-10 ACEPTADO CON LIMITACIONES.** Aporta un diálogo ICMP legítimo íntegro y verifica la feature L3 sin convertir la alerta de prueba en ataque. El único gap R01 restante es `PING-100`; debe ejecutarse con preflight nuevo.
