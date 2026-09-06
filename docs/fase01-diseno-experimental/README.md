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
El contrato de las 14 variables causales se define en `../F4-modelado/01-diccionario-multicapa-G5.md`.
Su validación sintética y real está en `../F4-modelado/02-validacion-extractor-G5.md`.
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
El canario DNS válido de diez consultas, su línea base ligera y la separación de alcances PCAP/Suricata están en `../07-dataset-campanas/32-canario-DNS-VALID-10-F1.md`.
El canario DNS válido de 200 consultas, la reutilización de puerto y la separación transacción/flujo están en `../07-dataset-campanas/33-canario-DNS-VALID-200-F1.md`.
El canario DNS mixto 50+10, su segundo nivel legítimo de NXDOMAIN y el sesgo de orden temporal están en `../07-dataset-campanas/34-canario-DNS-MIXED-50-10-F1.md`.
El canario ICMP de diez solicitudes, su intento canónico único y la regla de telemetría no productiva están en `../07-dataset-campanas/35-canario-PING-10-F1.md`.
El canario ICMP de cien solicitudes, sus cuatro ventanas y el cierre 29/29 de R01 están en `../07-dataset-campanas/36-canario-PING-100-cierre-R01-F1.md`.
El gate agregado de 77 filas, cobertura de las 14 features, política de duplicados y autorización condicionada de R02 están en `../07-dataset-campanas/37-auditoria-agregada-R01-F1.md`.
El inicio de R02, la repetibilidad exacta de `DNS-VALID-10` y la separación entre gate de campaña y gate de repetición están en `../07-dataset-campanas/38-canario-DNS-VALID-10-R02.md`.
La segunda campaña R02 y el efecto de fase de una ráfaga corta sobre ventanas UTC fijas están en `../07-dataset-campanas/39-canario-DNS-VALID-200-R02.md`.
La tercera campaña R02, el ratio NXDOMAIN legítimo `2/22` y la segunda coincidencia exacta R01↔R02 están en `../07-dataset-campanas/40-canario-DNS-MIXED-20-2-R02.md`.
La cuarta campaña R02, el ratio NXDOMAIN legítimo `10/60` y la tercera coincidencia exacta R01↔R02 están en `../07-dataset-campanas/41-canario-DNS-MIXED-50-10-R02.md`.
La quinta campaña R02 y el reparto ICMP 18/2 causado por un borde UTC fijo están en `../07-dataset-campanas/42-canario-PING-10-R02.md`.
La sexta campaña R02, sus ventanas ICMP 48/96/56 y la coincidencia estable de 96 paquetes están en `../07-dataset-campanas/43-canario-PING-100-R02.md`.
La séptima campaña R02 y su comparación de tráfico legítimo pesado HTTP están en `../07-dataset-campanas/44-canario-HTTP-10MB-R02.md`.
La octava campaña R02 y la transferencia HTTP legítima de 100 MiB están en `../07-dataset-campanas/45-canario-HTTP-100MB-R02.md`.
La novena campaña R02 y la transferencia HTTP sostenida de 500 MiB están en `../07-dataset-campanas/46-canario-HTTP-500MB-R02.md`.
La décima campaña R02 y la transferencia HTTP legítima de 1 GiB están en `../07-dataset-campanas/47-canario-HTTP-1GB-R02.md`.
La undécima campaña R02, su sesión TLS y el efecto del borde UTC están en `../07-dataset-campanas/48-canario-HTTPS-10MB-R02.md`.
La duodécima campaña R02 y la transferencia HTTPS legítima de 100 MiB están en `../07-dataset-campanas/49-canario-HTTPS-100MB-R02.md`.
La decimotercera campaña R02 y la transferencia HTTPS sostenida de 500 MiB están en `../07-dataset-campanas/50-canario-HTTPS-500MB-R02.md`.
La decimocuarta campaña R02, la transferencia HTTPS de 1 GiB y el inventario pendiente están en `../07-dataset-campanas/51-canario-HTTPS-1GB-R02.md`.
La decimoquinta campaña R02, cinco errores HTTP legítimos y la proyección de almacenamiento están en `../07-dataset-campanas/52-canario-HTTP-404-5-R02.md`.
La decimosexta campaña R02 y veinte sesiones TLS secuenciales están en `../07-dataset-campanas/53-canario-TLS-SESSIONS-20-R02.md`.
La decimoséptima campaña R02 y la repetibilidad multidestino de tres VIP están en `../07-dataset-campanas/54-canario-HTTP-MULTI-1-R02.md`.
La decimoctava campaña R02, quince health checks multidestino y `unique_dst_ip_ratio_30s=0.2`, está en `../07-dataset-campanas/55-canario-HTTP-MULTI-5-R02.md`.
La decimonovena campaña R02, dos descargas HTTP concurrentes y 93.6718 % de paquetes pesados, está en `../07-dataset-campanas/56-canario-HTTP-C2-R02.md`.
La vigésima campaña R02, cuatro descargas HTTP concurrentes y 93.6295 % de paquetes pesados, está en `../07-dataset-campanas/57-canario-HTTP-C4-R02.md`.
La vigesimoprimera campaña R02, ocho descargas HTTP concurrentes, rotación PCAP y cero drops, está en `../07-dataset-campanas/58-canario-HTTP-C8-R02.md`.
La vigesimosegunda campaña R02 y cinco rechazos TCP legítimos controlados están en `../07-dataset-campanas/59-canario-TCP-REFUSED-5-R02.md`.
La vigesimotercera campaña R02, iperf3 TCP a 50 Mbit/s y clasificación L7 fallida permitida, está en `../07-dataset-campanas/60-canario-TCP-50M-R02.md`.
La vigesimocuarta campaña R02, iperf3 TCP a 100 Mbit/s, cero drops y 95.5827 % de paquetes pesados, está en `../07-dataset-campanas/61-canario-TCP-100M-R02.md`.
La vigesimoquinta campaña R02 cierra la progresión TCP a 200 Mbit/s con dos PCAP, cero drops y 94.1073 % de paquetes pesados en `../07-dataset-campanas/62-canario-TCP-200M-R02.md`.
La vigesimosexta campaña R02 abre UDP a 10 Mbit/s con cero pérdida, cero drops y 99.8323 % de paquetes pesados en `../07-dataset-campanas/63-canario-UDP-10M-R02.md`.
La vigesimoséptima campaña R02 reproduce UDP a 25 Mbit/s con cero pérdida/drops y totales R01↔R02 idénticos en `../07-dataset-campanas/64-canario-UDP-25M-R02.md`.
La vigesimoctava campaña R02 cierra UDP a 50 Mbit/s con PCAP íntegro y documenta una discrepancia de un datagrama en el receptor iperf3 3.20 en `../07-dataset-campanas/65-canario-UDP-50M-R02.md`.
La vigesimonovena campaña completa R02 con HTTP+iperf3+DNS concurrentes, 29/29 celdas válidas y señales conjuntas L3/L4/L7 en `../07-dataset-campanas/66-canario-MIXED-LIGHT-R02.md`.
El gate agregado R02, la comparación descriptiva R01↔R02, cobertura multicapa, sesgos, duplicados y condiciones para R03 están en `../07-dataset-campanas/67-auditoria-agregada-R02-F1.md`.
La primera campaña R03 reproduce `DNS-VALID-10` por tercera vez con evidencia independiente y el mismo vector controlado en `../07-dataset-campanas/68-canario-DNS-VALID-10-R03.md`.
La segunda campaña R03 reproduce 200 respuestas DNS válidas y documenta el efecto de fase en dos ventanas en `../07-dataset-campanas/69-canario-DNS-VALID-200-R03.md`.
La tercera campaña R03 reproduce el patrón benigno de veinte consultas válidas y dos NXDOMAIN, con evidencia independiente y un tercer vector exacto, en `../07-dataset-campanas/70-canario-DNS-MIXED-20-2-R03.md`.
La cuarta campaña R03 reproduce cincuenta consultas válidas y diez NXDOMAIN, conserva un vector exacto independiente y delimita el peso repetido, en `../07-dataset-campanas/71-canario-DNS-MIXED-50-10-R03.md`.
La quinta campaña R03 genera diez pares ICMP en ventanas 6/14 y documenta una equivalencia observacional con el prefijo de `PING-100/R01` en `../07-dataset-campanas/72-canario-PING-10-R03.md`.
La sexta campaña R03 genera cien pares ICMP en ventanas 62/98/40, sin pérdida ni un nuevo vector exacto, en `../07-dataset-campanas/73-canario-PING-100-R03.md`.
La séptima campaña R03 transfiere 10 MiB por HTTP y aporta 7,248 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/74-canario-HTTP-10MB-R03.md`.
La octava campaña R03 transfiere 100 MiB por HTTP y aporta 72,464 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/75-canario-HTTP-100MB-R03.md`.
La novena campaña R03 transfiere 500 MiB por HTTP, rota dos PCAP y aporta 362,216 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/76-canario-HTTP-500MB-R03.md`.
La décima campaña R03 transfiere 1 GiB por HTTP, rota tres PCAP y aporta 742,152 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/77-canario-HTTP-1GB-R03.md`.
La undécima campaña R03 transfiere 10 MiB por HTTPS, aporta 7,256 paquetes legítimos de 500–1500 bytes y una sesión TLS 1.3 en `../07-dataset-campanas/78-canario-HTTPS-10MB-R03.md`; Claude/Sonnet la aceptó con limitaciones tras renovar su sesión.
La duodécima campaña R03 transfiere 100 MiB por HTTPS, aporta 72,576 paquetes legítimos de 500–1500 bytes y dos ventanas correlacionadas en `../07-dataset-campanas/79-canario-HTTPS-100MB-R03.md`.
La decimotercera campaña R03 transfiere 500 MiB por HTTPS, rota dos PCAP y aporta 362,957 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/80-canario-HTTPS-500MB-R03.md`.
La decimocuarta campaña R03 cierra los tamaños HTTPS individuales con 1 GiB, tres PCAP y 743,379 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/81-canario-HTTPS-1GB-R03.md`.
La decimoquinta campaña R03 reproduce cinco HTTP 404 legítimos, excluye las rutas de preflight y registra un vector exacto R02↔R03 en `../07-dataset-campanas/82-canario-HTTP-404-5-R03.md`.
La decimosexta campaña R03 reproduce veinte sesiones TLS secuenciales, veinte huellas homogéneas y dos ventanas correlacionadas, sin añadir duplicados exactos, en `../07-dataset-campanas/83-canario-TLS-SESSIONS-20-R03.md`.
La decimoséptima campaña R03 observa tres VIP lógicas en una VM y reproduce exactamente el vector R01/R02, elevando a trece el contador de duplicados dentro de `train`, en `../07-dataset-campanas/84-canario-HTTP-MULTI-1-R03.md`.
La decimoctava campaña R03 ejecuta quince GET entre tres VIP lógicas y vuelve a reproducir el vector R01/R02, elevando a catorce el contador de duplicados dentro de `train`, en `../07-dataset-campanas/85-canario-HTTP-MULTI-5-R03.md`.
La decimonovena campaña R03 ejecuta dos descargas HTTP concurrentes, aporta 144,929 paquetes legítimos de 500–1500 bytes y eleva a quince los duplicados dentro de `train` por su fila de cierre, en `../07-dataset-campanas/86-canario-HTTP-C2-R03.md`.
La vigésima campaña R03 ejecuta cuatro descargas HTTP concurrentes, aporta 290,000 paquetes legítimos de 500–1500 bytes y no añade duplicados exactos, en `../07-dataset-campanas/87-canario-HTTP-C4-R03.md`.
La vigesimoprimera campaña R03 ejecuta ocho descargas HTTP concurrentes, rota dos PCAP y aporta 580,019 paquetes legítimos de 500–1500 bytes sin añadir duplicados, en `../07-dataset-campanas/88-canario-HTTP-C8-R03.md`.
La vigesimosegunda campaña R03 reproduce cinco rechazos TCP legítimos mediante cinco pares SYN–RST/ACK y una fila L4 sin añadir duplicados, en `../07-dataset-campanas/89-canario-TCP-REFUSED-5-R03.md`.
La vigesimotercera campaña R03 reproduce iperf3 TCP a 50 Mbit/s, aporta 86,818 paquetes legítimos de 500–1500 bytes y conserva cuatro retransmisiones sin causa atribuida, en `../07-dataset-campanas/90-canario-TCP-50M-R03.md`.
La vigesimocuarta campaña R03 reproduce iperf3 TCP a 100 Mbit/s, aporta 173,634 paquetes legítimos de 500–1500 bytes y conserva siete retransmisiones sin causa atribuida, en `../07-dataset-campanas/91-canario-TCP-100M-R03.md`.
La vigesimoquinta campaña R03 cierra el techo TCP a 200 Mbit/s con dos PCAP, cero drops y 347,157 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/92-canario-TCP-200M-R03.md`.
La vigesimosexta campaña R03 abre UDP a 10 Mbit/s con cero pérdida/reordenamiento, cero drops y 17,267 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/93-canario-UDP-10M-R03.md`.
La vigesimoséptima campaña R03 reproduce UDP a 25 Mbit/s con cero pérdida/reordenamiento, cero drops y 43,166 paquetes legítimos de 500–1500 bytes en `../07-dataset-campanas/94-canario-UDP-25M-R03.md`.
La vigesimoctava campaña R03 cierra el techo UDP a 50 Mbit/s con 86,329 secuencias completas en Sensor, extremos coincidentes, cero drops y sin reproducir la discrepancia de R02, en `../07-dataset-campanas/95-canario-UDP-50M-R03.md`.
La vigesimonovena campaña R03 combina HTTP, TCP y DNS con solapamiento medido, captura íntegra, un `flow` de preflight diferido excluido de features y cero duplicados nuevos; cierra R03 29/29 en `../07-dataset-campanas/96-canario-MIXED-LIGHT-R03.md`.

La auditoría agregada de R03 distingue 19.54 GB crudos de 87 episodios/224 ventanas train, valida las catorce features, registra diecisiete coincidencias y responde con alcance limitado a las observaciones del jurado en `../07-dataset-campanas/97-auditoria-agregada-R03-F1.md`. El contrato y la política de filas para R04/R05 quedan congelados en `18-congelamiento-protocolo-R04-R05.md`.
El protocolo `PM-F1-v1` resuelve G5↔G6, congela Isolation Forest y comparadores, separa ajuste/calibración/test y define sensibilidades por campaña y vector exacto en `../fase04-modelado/01-protocolo-modelado-F1-v2.md`.
La revisión adversarial, los dos bloqueos corregidos y las condiciones operativas para abrir R04 están en `../04-revisiones-claude/2026-08-04-protocolo-modelado-F1-v2.md`.
El primer canario R04 reproduce diez resoluciones DNS válidas con PCAP/EVE íntegros, registra el primer vector exacto `seen` train↔validation y mantiene bloqueado el scoring hasta 29/29 en `../07-dataset-campanas/98-canario-DNS-VALID-10-R04.md`.
El segundo canario R04 completa 200 transacciones DNS válidas en dos ventanas causales, sin vector exacto train y sin scoring, en `../07-dataset-campanas/99-canario-DNS-VALID-200-R04.md`.
El tercer canario R04 conserva 20 resoluciones válidas + 2 NXDOMAIN, un vector `seen` y un flow de preflight diferido fuera de PCAP/features en `../07-dataset-campanas/100-canario-DNS-MIXED-20-2-R04.md`.
El cuarto canario R04 conserva 50 resoluciones válidas + 10 NXDOMAIN, un tercer vector `seen`, PCAP íntegro y delta Suricata +4 no atribuido en `../07-dataset-campanas/101-canario-DNS-MIXED-50-10-R04.md`.
El quinto canario R04 genera diez pares ICMP íntegros en ventanas 16/4, sin cruce exacto nuevo, y conserva dos flows de preflight diferidos fuera del PCAP/features en `../07-dataset-campanas/102-canario-PING-10-R04.md`.
El sexto canario R04 genera cien pares ICMP íntegros en ventanas 76/98/26 y registra la ventana central como cuarto cruce `seen` train↔validation en `../07-dataset-campanas/103-canario-PING-100-R04.md`.
El séptimo canario R04 descarga 10 MiB por HTTP, aporta 7,245 paquetes legítimos de 500–1500 bytes y una fila nueva en `../07-dataset-campanas/104-canario-HTTP-10MB-R04.md`.
El octavo canario R04 descarga 100 MiB por HTTP, aporta 72,459 paquetes legítimos de 500–1500 bytes y dos filas nuevas en `../07-dataset-campanas/105-canario-HTTP-100MB-R04.md`.
El noveno canario R04 descarga 500 MiB por HTTP, rota dos PCAP, aporta 362,240 paquetes legítimos de 500–1500 bytes y tres filas nuevas en `../07-dataset-campanas/106-canario-HTTP-500MB-R04.md`.
El décimo canario R04 descarga 1 GiB por HTTP, rota tres PCAP, aporta 742,012 paquetes legítimos de 500–1500 bytes y seis filas nuevas en `../07-dataset-campanas/107-canario-HTTP-1GB-R04.md`.
El undécimo canario R04 transfiere 10 MiB por HTTPS, aporta 7,258 paquetes legítimos de 500–1500 bytes y una fila TLS nueva en `../07-dataset-campanas/108-canario-HTTPS-10MB-R04.md`.
El duodécimo canario R04 transfiere 100 MiB por HTTPS, aporta 72,561 paquetes legítimos de 500–1500 bytes y dos filas nuevas en `../07-dataset-campanas/109-canario-HTTPS-100MB-R04.md`.
El decimotercer canario R04 transfiere 500 MiB por HTTPS, rota dos PCAP, aporta 362,741 paquetes legítimos de 500–1500 bytes y cuatro filas nuevas en `../07-dataset-campanas/110-canario-HTTPS-500MB-R04.md`.
El decimocuarto canario R04 cierra HTTPS individual con 1 GiB, tres PCAP, 743,106 paquetes legítimos de 500–1500 bytes y seis filas nuevas en `../07-dataset-campanas/111-canario-HTTPS-1GB-R04.md`.
El decimoquinto canario R04 reproduce cinco HTTP 404 legítimos, excluye probes de preflight y registra el quinto cruce exacto `seen` en `../07-dataset-campanas/112-canario-HTTP-404-5-R04.md`.
El decimosexto canario R04 ejecuta veinte sesiones TLS 1.3 secuenciales, conserva dos ventanas correlacionadas sin duplicado exacto nuevo y queda documentado en `../07-dataset-campanas/113-canario-TLS-SESSIONS-20-R04.md`.
El decimoséptimo canario R04 consulta tres VIP lógicas de una sola VM, reproduce una firma exacta R01–R03 y añade el sexto cruce `seen` en `../07-dataset-campanas/114-canario-HTTP-MULTI-1-R04.md`.
El decimoctavo canario R04 ejecuta cinco health checks por cada una de tres VIP lógicas, reproduce la firma R01–R03 y añade el séptimo cruce `seen` en `../07-dataset-campanas/115-canario-HTTP-MULTI-5-R04.md`.
El decimonoveno canario R04 completa dos descargas HTTP concurrentes, aporta 145,016 paquetes legítimos de 500–1500 bytes y una fila nueva en `../07-dataset-campanas/116-canario-HTTP-C2-R04.md`.
El vigésimo canario R04 completa cuatro descargas HTTP concurrentes, aporta 290,018 paquetes legítimos de 500–1500 bytes y tres filas nuevas en `../07-dataset-campanas/117-canario-HTTP-C4-R04.md`.
El vigesimoprimer canario R04 completa ocho descargas HTTP concurrentes, rota dos PCAP, aporta 580,006 paquetes legítimos de 500–1500 bytes y seis filas nuevas en `../07-dataset-campanas/118-canario-HTTP-C8-R04.md`.
El vigesimosegundo canario R04 reproduce cinco rechazos TCP activos legítimos, valida SYN/RST y añade el octavo cruce `seen` en `../07-dataset-campanas/119-canario-TCP-REFUSED-5-R04.md`.
El vigesimotercer canario R04 completa TCP iperf3 a 50 Mbit/s, aporta 86,816 paquetes legítimos de 500–1500 bytes y tres filas nuevas en `../07-dataset-campanas/120-canario-TCP-50M-R04.md`.
El vigesimocuarto canario R04 completa TCP iperf3 a 100 Mbit/s, aporta 173,629 paquetes legítimos de 500–1500 bytes y tres filas nuevas en `../07-dataset-campanas/121-canario-TCP-100M-R04.md`.
El vigesimoquinto canario R04 completa el techo TCP iperf3 a 200 Mbit/s, rota dos PCAP, aporta 347,166 paquetes legítimos de 500–1500 bytes y tres filas nuevas en `../07-dataset-campanas/122-canario-TCP-200M-R04.md`.
El vigesimosexto canario R04 completa UDP iperf3 a 10 Mbit/s, valida la secuencia `1..17,267`, cero pérdida/drops y tres filas nuevas en `../07-dataset-campanas/123-canario-UDP-10M-R04.md`.
El vigesimoséptimo canario R04 completa UDP iperf3 a 25 Mbit/s, valida la secuencia `1..43,166`, cero pérdida/drops y registra el noveno cruce exacto `seen` en `../07-dataset-campanas/124-canario-UDP-25M-R04.md`.
El vigesimoctavo canario R04 conserva la secuencia UDP `1..86,329` en el Sensor, reproduce el déficit receptor contradictorio de un datagrama y registra el décimo cruce `seen` en `../07-dataset-campanas/125-canario-UDP-50M-R04.md`.
El vigesimonoveno canario R04 combina HTTP, TCP y DNS con solapamiento medido, PCAP íntegro y tres filas nuevas; cierra R04 29/29 en `../07-dataset-campanas/126-canario-MIXED-LIGHT-R04.md`.
La auditoría agregada cierra R04 con 29 episodios, 72 ventanas validation, cobertura de las catorce features, 58 ventanas con tráfico pesado y diez cruces `seen` preservados en `../07-dataset-campanas/127-auditoria-agregada-R04-F1.md`. Siguiente: preparar calibración atómica antes de abrir R05.
La calibración atómica `PM-F1-v1` se ejecutó una sola vez y congeló el IF principal con umbral `-0.5667565423690721`; hashes, seis pipelines, estabilidad, diez cruces `seen` y sensibilidad al agrupamiento están en `../07-dataset-campanas/128-calibracion-PM-F1-v1.md`. R05 aún requiere procedimiento y revisión propios.
La preparación R05 confirma 0/29 test y añade un preflight continuo versionado con nueve gates, logs atómicos y revisión adversarial en `../07-dataset-campanas/129-preparacion-R05-y-preflight-versionado.md`. Está autorizado sólo ejecutar el preflight de `DNS-VALID-10/R05`, no su captura.
El primer canario R05 `DNS-VALID-10` fue aceptado con PCAP 20/20/20, cero drops, EVE 29/29 y una fila. Su vector repite exactamente R01–R04 y abre el primer cruce `train↔test`: se conserva como limitación de diversidad, no se deduplica ni se puntúa parcialmente. Auditor: 117/145, R05 1/29, 28 faltantes y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/130-canario-DNS-VALID-10-R05.md`. Siguiente: publicar el cierre y ejecutar sólo un preflight nuevo de `DNS-VALID-200/R05` contra el commit limpio.
El segundo canario R05 `DNS-VALID-200` reconcilia 200 solicitudes + 200 respuestas DNS, PCAP 400/400/400, cero drops y EVE 410/410. Dos puertos efímeros reutilizados explican 198 intentos L4 frente a 200 consultas L7; toda la ráfaga cayó en una sola ventana y produjo un vector nuevo. Un bloqueo Claude llevó a fijar explícitamente el volumen oficial. Auditor: 118/145, R05 2/29, 27 faltantes y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/131-canario-DNS-VALID-200-R05.md`. Siguiente: publicar y ejecutar sólo preflight de `DNS-MIXED-20-2/R05`; no scoring.
El tercer canario R05 `DNS-MIXED-20-2` conserva veinte pares `NOERROR` y dos NXDOMAIN legítimos, PCAP 44/44/44, cero drops y ratio L7 `2/22`. Dos flows de probes fueron emitidos cinco minutos después por timeout, pero están fuera del PCAP/features. Su vector repite R01–R04 y abre otro cruce train↔test. Auditor: 119/145, R05 3/29, 26 faltantes y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/132-canario-DNS-MIXED-20-2-R05.md`. Siguiente: publicar y ejecutar sólo preflight de `DNS-MIXED-50-10/R05`; no scoring.
El cuarto canario R05 `DNS-MIXED-50-10` conserva cincuenta pares `NOERROR` seguidos de diez NXDOMAIN, PCAP 120/120/120, cero drops y EVE 130 sin flows. Su única fila usa 120 observaciones de paquete y 70 de aplicación, con ratio L7 `10/60`; repite R01–R04 y añade un cruce train↔test estructural, no reutilización de archivos. Auditor: 120/145, R05 4/29, 25 faltantes, 30 duplicados, 13 cruces y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/133-canario-DNS-MIXED-50-10-R05.md`. Siguiente: publicar y ejecutar sólo un preflight nuevo de `PING-10/R05`; no scoring.
El quinto canario R05 `PING-10` conserva diez pares ICMP, PCAP 20/20/20, cero pérdida/drops y dos ventanas 16/4 idénticas a R04. EVE contiene diez alertas permitidas, diez stats, un Router Solicitation IPv6 ambiental y un DNS diferido del preflight; además, el flow ICMP de las alertas conserva su inicio en el probe previo. Ninguno entra en PCAP/features, pero limita la causalidad estricta de EVE. Auditor: 121/145, R05 5/29, 24 faltantes, 32 duplicados, 15 cruces y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/134-canario-PING-10-R05.md`. Siguiente: publicar y ejecutar sólo un preflight nuevo de `PING-100/R05`; no scoring.
El sexto canario R05 `PING-100` conserva cien pares ICMP, PCAP 200/200/200, cero pérdida/drops y tres ventanas 66/96/38. La central coincide con la firma 96 de R01/R02 y añade un cruce train↔test; las otras dos son nuevas. EVE contiene cien alertas permitidas, once stats y un DNS diferido; el flow ICMP de las alertas hereda su inicio del probe previo sin entrar en PCAP/features. Auditor: 122/145, R05 6/29, 23 faltantes, 33 duplicados, 16 cruces y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/135-canario-PING-100-R05.md`. Siguiente: publicar y ejecutar sólo un preflight nuevo de `HTTP-10MB/R05`; no scoring.
El séptimo canario R05 `HTTP-10MB` descargó 10,485,760 bytes con HTTP 200; PCAP 8,033/8,033/8,033, cero drops y 7,244 paquetes legítimos de 500–1500 bytes. Dos filas nuevas presentan `large_ip_ratio` 0.808/0.988. EVE conserva dos flows de preflight y `fileinfo` truncado por inspección, sin contradecir curl/PCAP. Auditor: 123/145, R05 7/29, 22 faltantes, 33 duplicados, 16 cruces y cero inválidas/advertencias. Evidencia en `../07-dataset-campanas/136-canario-HTTP-10MB-R05.md`. Siguiente: publicar y ejecutar sólo un preflight nuevo de `HTTP-100MB/R05`; no scoring.

## Grupo A: tráfico legítimo pesado

Ejecutar desde Cliente hacia Servidor, con una sesión nueva por escenario:

| ID | Escenario | Evidencia mínima |
|---|---|---|
| A1 | ICMP sostenido | pérdida, alertas y contadores |
| A5 | descarga HTTP de archivo de 500 MB o más | bytes, paquetes y evento HTTP |
| A10 | descargas HTTP concurrentes | conexiones simultáneas y falsos positivos |
| A12 | `iperf3` TCP | throughput, tamaño de paquete y drops |
| A13 | `iperf3` UDP controlado | bitrate, pérdida y drops |
| A14 | HTTP + DNS + `iperf3` concurrentes | métricas agregadas, solapamiento y disponibilidad |

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
