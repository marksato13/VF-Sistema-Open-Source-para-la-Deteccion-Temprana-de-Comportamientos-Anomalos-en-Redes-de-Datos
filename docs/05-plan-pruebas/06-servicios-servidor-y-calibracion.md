# Servicios de VM03 y calibración inicial

Fecha: 20 de julio de 2026. Esta etapa prepara la fuente de tráfico legítimo y no forma parte del dataset final.

## Justificación técnica

Se eligió un baseline mínimo que cubre flujos y protocolos observables por el Sensor:

| Servicio | Puerto | Uso experimental | Telemetría esperada |
|---|---:|---|---|
| NGINX HTTP | TCP/80 | navegación, archivos y códigos 2xx/4xx | EVE `http`, `flow`, `fileinfo` |
| NGINX HTTPS | TCP/443 | tráfico cifrado legítimo | EVE `tls`, JA3/JA3S/JA4 y `flow` |
| dnsmasq local | UDP/TCP 53 | nombres válidos y NXDOMAIN | EVE `dns` request/response |
| iperf3 | TCP/UDP 5201 | throughput controlado | EVE `flow` y estadísticas de captura |
| OpenSSH/SFTP | TCP/22 | sesiones y transferencias legítimas | EVE `ssh` y `flow` |

NGINX documenta el servicio de contenido estático y el registro de solicitudes ([contenido estático](https://docs.nginx.com/nginx/admin-guide/web-server/serving-static-content/), [logging](https://docs.nginx.com/nginx/admin-guide/monitoring/logging/)). iperf3 permite TCP, UDP, dirección inversa y resultados JSON ([documentación ESnet](https://software.es.net/iperf/invoking.html)). Suricata EVE contempla HTTP, DNS, TLS, SSH, flow y estadísticas ([Suricata 8 EVE](https://docs.suricata.io/en/suricata-8.0.0/output/eve/)).

Claude revisó el conjunto y lo consideró un baseline mínimo razonable; recomendó incluir HTTPS y señaló que una base de datos solo sería necesaria si el jurado exige más diversidad L7. HTTPS quedó incluido. La base de datos se pospone hasta demostrar que aporta una feature o escenario que estos servicios no cubren.

## Límite de observabilidad

Suricata reconoce el protocolo SSH y sus metadatos, pero el resultado de autenticación viaja cifrado. Por ello, `número de logins SSH fallidos` no puede derivarse únicamente de EVE. Esa variable requeriría integrar y sincronizar `/var/log/auth.log` o el journal del Servidor. En la primera versión multicapa se priorizarán variables visibles en red: ratio HTTP 4xx, ratio DNS NXDOMAIN, frecuencia de métodos/URI, metadatos TLS, IP/puertos únicos y flags TCP.

## Configuración aplicada

- NGINX vinculado exclusivamente a `10.30.0.10:80` y `:443`.
- Certificado TLS autofirmado exclusivo de `server.ppi.lab`.
- Logs NGINX en JSON con método, URI, estado, bytes y duración.
- DNS local `ppi.lab`, sin resolución externa, vinculado a `10.30.0.10:53`.
- iperf3 vinculado a `10.30.0.10:5201`, duración máxima 60 s y guardia de bitrate de servidor.
- Archivos controlados de 10 MB, 100 MB, 500 MB y 1 GB en `/srv/ppi/files`.
- Cliente equipado con curl, wget, dig, iperf3 y jq.

Los archivos creados con `fallocate` sirven para estudiar tamaño de paquetes, duración y volumen. Si una versión futura analiza contenido/payload, deberán añadirse archivos reales o pseudoaleatorios de varios formatos para evitar sesgo por contenido uniforme.

## Validación de protocolos

- HTTP `/health`: respuesta correcta.
- HTTPS `/health`: respuesta correcta con TLS 1.3.
- DNS `server.ppi.lab`: `10.30.0.10`.
- DNS `inexistente.ppi.lab`: `NXDOMAIN`.
- Archivo 500 MB: cabecera `200 OK`, `Content-Length: 524288000`.
- EVE observado: HTTP, TLS 1.3, JA3, JA3S, JA4, DNS NOERROR, DNS NXDOMAIN y flow.

## Hallazgo de rendimiento y corrección

Una prueba exploratoria iperf3 sin pacing alcanzó aproximadamente 2.58 Gbit/s y elevó `capture.kernel_drops` a 389,932. Ese resultado invalida cualquier dataset recogido durante la ráfaga y demuestra que `--server-bitrate-limit` es una guardia de aborto, no un limitador de velocidad.

Se ajustó el Sensor de acuerdo con las opciones AF_PACKET documentadas por Suricata ([tuning y ring-size](https://docs.suricata.io/en/suricata-6.0.20/performance/tuning-considerations.html)):

- 4 threads AF_PACKET.
- TPACKET v3.
- ring-size 32768 por thread.
- block-size y buffer-size de 1 MiB.
- ring RX de `ens35` ampliado de 1024 a 4096.

Después del reinicio de Suricata, una prueba TCP limitada a 100 Mbit/s durante 10 s obtuvo 100.02 Mbit/s enviados, 100.00 Mbit/s recibidos, cero retransmisiones, `kernel_drops=0`, `decoder.invalid=0` y `alert_queue_overflow=0`.

## Decisión

Estado actualizado: **servicios listos y calibración de throughput cerrada**. Los resultados completos están en `07-resultados-calibracion-G2.md`. No se volverá a usar iperf3 TCP sin `-b`, ni se incorporará la ráfaga de 2.58 Gbit/s al dataset.

## Revisión crítica de Claude y correcciones

Claude identificó tres riesgos: iperf3 accesible desde cualquier origen, guardia de 500 Mbit/s superior al umbral validado y ausencia de límites HTTP. Se aplicaron estas correcciones:

- nftables en VM03 permite TCP/UDP 5201 únicamente desde Cliente `10.20.0.20` durante F1; una conexión desde Kali produjo `EXPECTED_BLOCKED`.
- iperf3 usa duración máxima 30 s y guardia de 300 Mbit/s/5 s.
- NGINX limita 20 conexiones por IP y 20 solicitudes/s con burst 40; los excesos responden 429 y quedan registrados.
- El ejecutor `scripts/f1/run-benign.sh` rechaza pruebas TCP sin bitrate y limita valores y duración.

Una comprobación posterior permitió al Cliente ejecutar 50 Mbit/s y obtener aproximadamente 50.28 Mbit/s en recepción, mientras Kali permaneció bloqueada.
