# Vigesimosexto canario oficial R04 — UDP 10 Mbit/s

Fecha: 6 de agosto de 2026. Campaña `F1N-UDP-10M-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Un flujo UDP benigno de iperf3 a 10 Mbit/s durante 20 s, desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:5201` a través del Sensor. Usa bloques de 1,448 bytes y aporta tráfico grande legítimo L3/L4; no representa un SLA ni una aplicación productiva.

Un primer preflight usó por error `nc ... 22>/dev/null`: `nc` no recibió puerto y el gate TCP/22 fue un falso positivo. El log se archivó como `invalid-attempt-01`; no abrió captura ni creó campaign, features o ledger. Todo el preflight se repitió con `22 >/dev/null`.

El control válido pasó entre `15:46:27.235` y `15:46:50.977 -05:00` sobre commit limpio y sincronizado `75ebd8d88cc536821df00ae999b47848894b2c11`. Pasaron contrato, almacenamiento con 121,864,777,728 bytes, NTP 5/5 con máximo 0.555 ms, SSH, ID, NIC externas `DOWN`, bypass ICMP/TCP22, rutas, Suricata/captura, listener ocioso/exclusivo, iperf 3.20, probes y generador. Log SHA-256 `35e2ee85987bc68018f79cf26a6530f3ce58faa3fcf8b70ee1640788617dbc62`. Claude autorizó exactamente una ejecución. No hubo reintento ni scoring.

## Resultado UDP y secuencia

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 25,002,616 | 25,002,616 |
| Datagramas | 17,267 | 17,267 |
| Duración | 20.001940 s | 20.002671 s |
| Bitrate | 10.000076 Mbit/s | 9.999711 Mbit/s |
| Desviación nominal | +0.000764 % | −0.002891 % |
| Jitter | 0 ms | 0.020782 ms |
| Perdidos / fuera de orden | 0 / 0 | 0 / 0 |

`17,267 × 1,448 = 25,002,616`. La auditoría binaria de solo lectura encontró IDs `1..17,267`: todos únicos, ordenados, sin faltantes ni duplicados. Esto prueba continuidad en el punto Sensor; el reporte receptor aporta evidencia distinta sobre recepción de aplicación. No se generaliza la fiabilidad de iperf3 3.20.

El PCAP reconcilia 17,267 datagramas de datos, dos UDP de inicialización y 27 TCP de control: 17,296 paquetes. El control TCP `37560` tuvo 1 SYN, 1 SYN/ACK, 2 FIN, 0 RST y span 20.024649 s. `flow_attempt_count_30s=2` representa inicio UDP más control TCP, no dos usuarios.

## Integridad, EVE y features

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 17,296 / 17,296 / 17,296 |
| PCAP | 1 archivo / 26,007,319 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 17,300 / 17,296 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 17,267 / 17,296 (99.8323 %) |
| longitud media / máxima | 1,473.66 / 1,476 bytes |

El delta Suricata +4 queda sin causa. El PCAP supera los bytes UDP de datos en 1,004,703 bytes (4.018392 %) por cabeceras, inicialización, control y estructura; no mide pérdida. Pérdida de extremo, continuidad de secuencia y drops de captura son controles diferentes aunque los tres pasaron.

EVE contiene doce stats y un flow DNS iniciado durante el preflight inválido a `15:45:38`, emitido por timeout a `15:50:45`. Sus dos paquetes están fuera del PCAP y no alteraron las features. No hay alertas ni observaciones L7; la benignidad proviene del escenario versionado, no de esa ausencia.

Las tres filas contienen 2,103, 8,632 y 6,561 paquetes, suman 17,296 y son ventanas correlacionadas de un episodio. Ninguna coincide exactamente con R01–R03; el auditor no incrementó duplicados ni cruces. Los cuatro episodios transfirieron los mismos bytes/datagramas sin pérdida/reordenamiento; jitter R01/R02/R03/R04 fue 0.027371/0.049850/0.042085/0.020782 ms, sin inferir tendencia o rango normal.

El Sensor produjo 69 muestras: CPU 0–3.07 %, RSS 782,504 KiB, memoria disponible 14,077,912–14,160,788 KiB y load1 0.12–0.29. Ambos bundles pasaron. Hashes: manifest `fa08c803…`, PCAP `c4a5cee3…`, EVE `0d3f3521…`, CSV `d7ce8dbc…`, extraction report `ada01526…` y ledger `2f4610d6…`.

El auditor limpio aceptó 113/145, R04 26/29, 32 faltantes, 25 coincidencias, ocho cruces y cero inválidas/advertencias. Claude confirmó los artefactos y emitió **ACEPTAR CON LIMITACIONES**. Su frase “14 líneas” se corrige al desglose válido de 13 registros: doce stats + un flow. Siguiente autorizado: sólo preflight independiente de `F1N-UDP-25M-R04`; no su captura ni scoring.
