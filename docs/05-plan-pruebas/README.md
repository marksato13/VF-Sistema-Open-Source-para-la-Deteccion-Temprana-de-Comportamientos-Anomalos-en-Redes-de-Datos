# Plan reproducible de pruebas experimentales

Este plan separa las campañas para que el entrenamiento y la evaluación sean defendibles.

## Precondiciones

1. Confirmar zona horaria `America/Lima` y NTP sincronizado en las cinco VMs.
2. Desconectar en ESXi las NIC externas de Sensor, Servidor, Kali y Cliente durante toda campaña oficial. El Sensor puede reconectarse únicamente en una ventana de mantenimiento sin captura activa.
3. Verificar `ip route get 10.30.0.10` desde Cliente y Kali: siguiente salto `10.20.0.1`.
4. Registrar antes y después de cada campaña: `capture.kernel_drops`, `decoder.invalid`, `alert_queue_overflow`, CPU, RAM, espacio de disco y número de eventos EVE.

El procedimiento automatizado, la estructura de evidencia y los criterios de aceptación se describen en `09-sistema-campanas-F1.md`.
La validación extremo a extremo y los dos fallos corregidos se registran en `10-validacion-orquestador-G3.md`.
El diseño y la validación PCAP están en `11-diseno-captura-PCAP-G4.md` y `12-validacion-captura-PCAP-G4.md`.
El contrato de las 14 variables causales se define en `../06-features-modelado/01-diccionario-multicapa-G5.md`.
Su validación sintética y real está en `../06-features-modelado/02-validacion-extractor-G5.md`.
La matriz ejecutable F1, su partición y el gate de almacenamiento están en `../07-dataset-campanas/01-matriz-F1-normal-G6.md`.
Los primeros pilotos DNS/HTTP y el bloqueo negativo de capacidad están en `../07-dataset-campanas/02-validacion-pilotos-G6.md`.
El ensamblador con gates anti-contaminación y sus pruebas están en `../07-dataset-campanas/03-ensamblador-seguro-F1-G6.md`.
El rediseño multidestino y la transición conservadora de matriz `v1` a `v2` están en `../07-dataset-campanas/04-diversidad-L3-multidestino-v2.md`.
La aplicación persistente y el piloto con ratio L3 igual a 1.0 están en `../07-dataset-campanas/05-validacion-diversidad-L3-v2.md`.
La auditoría posterior al reinicio, el bypass externo confirmado y el gate de aislamiento están en `13-auditoria-preexperimental-G7.md`.
El cierre operacional, la captura correlacionada y la prueba de persistencia pendiente están en `14-cierre-operacional-G7.md`.
El reinicio real, la persistencia del aislamiento y el cierre **APTO PERSISTENTE** están en `15-validacion-persistencia-G7.md`.
El bloqueo preventivo de C8 por NTP y el diseño VM01→Sensor→laboratorio están en `16-correccion-ntp-interno-G7.md`.
El archivado recuperable de intentos rechazados, sus rutas y los gates para reutilizar un ID canónico están en `17-archivado-intentos-fallidos.md`.
El primer canario oficial aceptado y sus límites están en `../07-dataset-campanas/06-primer-canario-oficial-F1.md`.
El segundo canario oficial, HTTP 10 MB, su distribución de paquetes grandes y el límite de inspección observado en Suricata están en `../07-dataset-campanas/07-canario-HTTP-10MB-F1.md`.
El tercer canario oficial, HTTP 100 MB, su escalamiento, recursos y dos ventanas elegibles están en `../07-dataset-campanas/08-canario-HTTP-100MB-F1.md`.
El cuarto canario oficial, HTTP 500 MB, la rotación PCAP y el análisis de paquetes TCP pequeños están en `../07-dataset-campanas/09-canario-HTTP-500MB-F1.md`.
El quinto canario oficial, HTTP 1 GB, la no conformidad EVE cerrada y la quietud preventiva están en `../07-dataset-campanas/10-canario-HTTP-1GB-F1.md`.
El sexto canario oficial, HTTPS 10 MB, la sesión TLS y sus límites de representatividad están en `../07-dataset-campanas/11-canario-HTTPS-10MB-F1.md`.
El séptimo canario oficial, HTTPS 100 MB, su escalamiento y flows mDNS fuera de alcance están en `../07-dataset-campanas/12-canario-HTTPS-100MB-F1.md`.
El octavo canario oficial, HTTPS 500 MB, la rotación PCAP y la separación entre volumen y churn TLS están en `../07-dataset-campanas/13-canario-HTTPS-500MB-F1.md`.
El noveno canario oficial, HTTPS 1 GB, el cierre de tamaños y la ventana FIN/ACK están en `../07-dataset-campanas/14-canario-HTTPS-1GB-F1.md`.
El décimo canario oficial, cinco HTTP 404 legítimos, sus dos ventanas autocorrelacionadas y sus límites están en `../07-dataset-campanas/15-canario-HTTP-404-5-F1.md`.
El undécimo canario oficial, veinte sesiones TLS secuenciales, la tasa L7 y sus límites de homogeneidad están en `../07-dataset-campanas/16-canario-TLS-SESSIONS-20-F1.md`.
El duodécimo canario oficial, tres VIP lógicas y `unique_dst_ip_ratio_30s=1`, está en `../07-dataset-campanas/17-canario-HTTP-MULTI-1-F1.md`.
El decimotercer canario oficial, quince health checks multidestino y `unique_dst_ip_ratio_30s=0.2`, está en `../07-dataset-campanas/18-canario-HTTP-MULTI-5-F1.md`.
El decimocuarto canario oficial, dos descargas HTTP concurrentes y su throughput observado, está en `../07-dataset-campanas/19-canario-HTTP-C2-F1.md`.
El decimoquinto canario oficial, cuatro descargas HTTP concurrentes, su cola FIN/ACK y el aislamiento de mDNS, está en `../07-dataset-campanas/20-canario-HTTP-C4-F1.md`.
El intento `HTTP-C8/R01` rechazado por 476 drops de `tcpdump` y el diagnóstico de búfer están en `../07-dataset-campanas/21-intento-rechazado-HTTP-C8-F1.md`.
La calibración C8 con búfer de 64 MiB, cero drops y exclusión anti-calibración está en `../07-dataset-campanas/22-calibracion-buffer-HTTP-C8-G6.md`.
El reintento oficial C8 aceptado, su separación del intento fallido y la comparación controlada están en `../07-dataset-campanas/23-canario-HTTP-C8-F1.md`.
El canario de cinco rechazos TCP legítimos y la validación de ratios L4 están en `../07-dataset-campanas/24-canario-TCP-REFUSED-5-F1.md`.
El canario iperf3 TCP 50 Mbit/s, su alerta de clasificación L7 y la línea base pesada están en `../07-dataset-campanas/25-canario-TCP-50M-F1.md`.
El escalamiento iperf3 TCP a 100 Mbit/s y sus cuatro retransmisiones recuperadas están en `../07-dataset-campanas/26-canario-TCP-100M-F1.md`.
El techo iperf3 TCP de 200 Mbit/s, sus cinco retransmisiones y cierre de la progresión TCP están en `../07-dataset-campanas/27-canario-TCP-200M-F1.md`.
El primer canario iperf3 UDP a 10 Mbit/s, su pérdida y jitter, la cobertura benigna pesada y los límites del futuro modelo están en `../07-dataset-campanas/28-canario-UDP-10M-F1.md`.
El escalamiento iperf3 UDP a 25 Mbit/s, la composición exacta del PCAP y la revisión de sesgos están en `../07-dataset-campanas/29-canario-UDP-25M-F1.md`.
El techo iperf3 UDP a 50 Mbit/s, la comparación 10/25/50 y el cierre de la progresión R01 están en `../07-dataset-campanas/30-canario-UDP-50M-F1.md`.
El canario mixto concurrente HTTP+iperf3+DNS, su solapamiento y señales L3/L4/L7 están en `../07-dataset-campanas/31-canario-MIXED-LIGHT-F1.md`.

## Grupo A: tráfico legítimo pesado

Ejecutar desde Cliente hacia Servidor, con una sesión nueva por escenario:

| ID | Escenario | Evidencia mínima |
|---|---|---|
| A1 | ICMP sostenido | pérdida, alertas y contadores |
| A5 | descarga HTTP de archivo de 500 MB o más | bytes, paquetes y evento HTTP |
| A10 | descargas HTTP concurrentes | conexiones simultáneas y falsos positivos |
| A12 | `iperf3` TCP | throughput, tamaño de paquete y drops |
| A13 | `iperf3` UDP controlado | bitrate, pérdida y drops |
| A14 | HTTP + SSH + `iperf3` concurrentes | métricas agregadas y disponibilidad |

Los escenarios A deben incluir tráfico legítimo con paquetes de 500–1500 bytes para ampliar el rango de entrenamiento de Isolation Forest.

## Grupo B: ataques controlados desde Kali

Solo después de cerrar Grupo A: escaneo TCP/UDP limitado, ráfaga de SYN, autenticación HTTP fallida visible en red, consultas DNS anómalas y solicitudes HTTP anómalas. Los intentos SSH fallidos solo se usarán si se integran logs del host, porque su resultado está cifrado. Cada escenario tendrá timestamp, origen, destino, comando, duración y evidencia asociada.

## Grupo C: mixto

Cliente genera A12/A14 mientras Kali ejecuta un único escenario B. Se evalúa separación temporal y por flujo, sin reutilizar sesiones del entrenamiento.

## Criterios de aceptación

- `kernel_drops=0` o una tasa documentada y reproducible bajo carga.
- Ningún bloqueo del tráfico normal de Grupo A.
- Cada ataque de Grupo B debe tener evento o evidencia de red correlacionable.
- Dataset separado por campaña: 60 % entrenamiento, 20 % validación y 20 % prueba.
- No se declara implementada ninguna feature L3/L4/L7 hasta disponer de código, diccionario y prueba.
