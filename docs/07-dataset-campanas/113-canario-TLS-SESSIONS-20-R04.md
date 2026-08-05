# Decimosexto canario oficial R04 — TLS-SESSIONS-20

Fecha: 5 de agosto de 2026. Campaña `F1N-TLS-SESSIONS-20-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Veinte sesiones HTTPS legítimas, nuevas y secuenciales entre Cliente y Servidor. El perfil aporta comportamiento L4/L7 de renovación de conexiones TLS sin asumir que una frecuencia mayor de SYN o de handshakes sea anómala por sí sola.

El preflight completo pasó en un único proceso continuo entre `12:53:56.111` y `12:54:17.361 -05:00` sobre commit limpio `4a875485f5a671671e662da48d9270ca395659a5`. Pasaron contrato, almacenamiento, NTP 5/5 (máximo absoluto 0.490 ms), aislamiento de NIC externas, bypass, SSH, rutas, Suricata, servicios, captura, IDs, DNS, ICMP y generador. Los probes HTTPS exclusivos devolvieron HTTP 200 y validaron el certificado con `verify=18`. Claude autorizó exactamente una captura. No hubo reintento ni scoring.

## Evidencia y features

La salida contiene exactamente veinte sesiones numeradas `1..20`, todas con HTTP 200; stderr quedó vacío. Cada sesión creó un puerto origen distinto.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 433 / 433 / 433 |
| PCAP | 1 archivo / 146,150 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 435 / 433 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes de 500–1500 bytes | 63 / 433 (14.55 %) |
| Paquetes de 1,500 bytes | 40 |
| longitud media / máxima | 307.47 / 1,500 bytes |

El delta Suricata +2 queda sin causa atribuida. EVE contiene diez stats y veinte eventos TLS, sin `flow` ni otros tipos. Las veinte sesiones usan TLS 1.3 y comparten JA3 `7587a1ac…`, JA3S `15af977c…` y JA4 `t13i3012h2_1d37bd780c83_8537cf56674e`, coherente con un único cliente, servidor y configuración.

Las dos filas elegibles dividen un mismo episodio por el borde de ventana UTC:

| Fin UTC | Paquetes | intentos / SYN | tasa pkt/s | media bytes | ratio pesado | tasa TLS |
|---|---:|---:|---:|---:|---:|---:|
| `17:57:30` | 282 | 13 / 13 | 28.2 | 308.91 | 0.1489 | 0.2167 |
| `17:57:40` | 151 | 20 / 7 | 15.1 | 304.79 | 0.1391 | 0.3333 |

Ambas tienen finalización 1.0; juntas suman los 433 paquetes. Ninguna coincide exactamente con el mismo perfil R01–R03 ni incrementa los duplicados globales. Las filas no son observaciones independientes entre sí: proceden de una sola ejecución y conservan la correlación por episodio para el particionado y modelado.

El Sensor produjo 55 muestras: CPU 0–1.64 %, RSS 781,720 KiB, memoria disponible 14,085,716–14,156,088 KiB y load1 0.16–0.58. Los bundles pasaron. Hashes: PCAP `0d1c3e0b…`, manifest `15a43351…`, EVE `68cb6e26…`, CSV `9f4d022e…` y ledger `33de2d1…`.

El auditor limpio aceptó 103/145, R04 16/29, 42 faltantes, 22 coincidencias, cinco cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** La campaña demuestra churn TLS benigno homogéneo y secuencial, no concurrencia, diversidad de clientes, variedad criptográfica ni una PKI externa. Las dos ventanas están correlacionadas; se conserva además el delta Suricata +2. No hubo scoring. Siguiente autorizado: sólo preflight `F1N-HTTP-MULTI-1-R04`.
