# Plan de expansión del dataset multicapa v2

Fecha: 12 de agosto de 2026. Este documento redefine el siguiente ciclo del
proyecto después de cerrar la matriz F1 normal R05. El dataset actual es válido
para el pipeline, pero sus 371 ventanas agregadas no son suficientes para
afirmar generalización fuerte: varias ventanas pertenecen al mismo episodio y
el auditor registra duplicados y cruces entre particiones.

## Estado de partida

El ensamblado `/srv/ppi-evidence/artifacts/datasets/f1-normal-v2/` contiene 224
filas train, 72 validation y 75 test, 27 columnas totales y 14 features de
entrada. La matriz normal tiene 145/145 campañas aceptadas, cero faltantes y
`ready_to_build=true`. El manifest actual registra 41 vectores duplicados y 24
cruces entre particiones. Estos números no son un fallo de captura, pero
impiden tratar todas las filas como observaciones independientes.

## Objetivo cuantitativo v2

La meta es recolectar **2.000–3.000 ventanas independientes**, no copiar filas.
Cada episodio tendrá un `episode_id` único y ninguna ventana del mismo episodio
podrá repartirse entre train, validation y test. Como mínimo se planifican 15–20
episodios por perfil nuevo, con 2–3 ventanas elegibles por episodio. La división
objetivo será aproximadamente 60 % train, 20 % validation y 20 % test por
episodio, manteniendo perfiles y condiciones representados en los tres grupos.

## Nuevos grupos de escenarios

### N1 — Variabilidad legítima L3/L4

- HTTP/HTTPS hacia 3–8 destinos internos reales, no sólo VIP lógicas.
- UDP y TCP a 5, 10, 25, 50, 100 y 200 Mbit/s, con duraciones de 10, 20 y 60 s.
- Variación de puertos destino, tamaños de bloque, pausas y concurrencia 1/2/4/8.
- ICMP con tasas baja, media y ráfaga.
- Mezclas HTTP+DNS+TCP/UDP con desfases temporales distintos.

### N2 — Aplicación L7 legítima

- API interna con respuestas HTTP 200, 201, 204, 301, 400, 401, 403, 404 y 500.
- Métodos GET, POST, PUT y DELETE con cuerpos pequeños y grandes.
- Endpoint de autenticación local con logins válidos y fallidos etiquetados.
- DNS con dominios únicos, repetidos, NXDOMAIN y respuestas de distintos tamaños.
- HTTPS con TLS 1.2/1.3, SNI interno y sesiones cortas/largas.

La API y el login deben vivir en el Servidor, sin Internet. Nginx/dnsmasq/iperf3
existentes se conservan; sólo se añade una aplicación web local y un registro
de aplicación sincronizado con el ledger.

### N3 — Anomalías controladas para evaluación

Estas campañas no se mezclan con el entrenamiento normal: se guardan como
`label=anomaly` y se reservan para evaluación ciega.

- ráfaga SYN y escaneo TCP/UDP limitado;
- alta tasa de puertos o IP destino;
- DNS de alta entropía y NXDOMAIN sostenido;
- HTTP 401/403 repetido y password spraying simulado contra la API local;
- ráfaga UDP con pérdida/reordenamiento controlados;
- beaconing periódico y conexiones cortas repetitivas;
- combinación concurrente de dos señales anómalas.

No se ejecutarán ataques contra Internet ni contra terceros. Cada episodio
conservará origen, destino, comando, duración, timestamp, etiqueta y criterio
de parada.

## Esquema de features v2 propuesto

Se conserva `multilayer-v1` para reproducibilidad y se crea un esquema nuevo,
sin sobrescribir los CSV anteriores. Las 14 actuales cubren L3 (6), L4 (5) y
L7 (3). La propuesta añade:

- L3: `ttl_mean_10s`, `fragment_ratio_10s`, `protocol_diversity_30s`;
- L4: `tcp_retransmission_ratio_10s`, `flow_duration_mean_30s`,
  `tx_rx_byte_ratio_30s`;
- L7: `http_request_rate_60s`, `http_method_entropy_60s`,
  `http_auth_failure_ratio_60s`, `dns_query_rate_60s`, `unique_dns_name_ratio_60s`,
  `tls_handshake_failure_ratio_60s`, `tls_version_ratio_60s`.

El esquema v2 tendrá 26 features como máximo tras validar disponibilidad y
causalidad. No se añadirá una variable sólo porque sea fácil de extraer: cada
feature deberá tener definición, unidad, ventana, fuente PCAP/EVE/log, prueba
sintética y prueba real.

## Evidencia y servicios

PCAP seguirá siendo la fuente cruda de paquetes; EVE JSON será la telemetría
interpretada por Suricata; los logs de la API/DNS se usarán únicamente para
reconciliar observaciones L7. El extractor v2 combinará estas fuentes mediante
timestamp y `episode_id`, generará CSV v2 y conservará hashes de cada entrada.

Servicios internos requeridos: Nginx HTTPS, dnsmasq, iperf3, aplicación API de
login y sincronización NTP. No se requiere salida a Internet.

## Estado de habilitación de la API

El Servidor ya dispone de Python 3.14, Nginx, dnsmasq e iperf3; no requiere
Internet ni paquetes adicionales para la API propuesta. Se añadieron al
repositorio `configs/server/ppi-api.py`, su unidad `ppi-api.service` y el
proxy `/api/` de Nginx. La API usa únicamente la biblioteca estándar de Python
y registra autenticaciones en JSONL.

El despliegue remoto no se completó porque `useransible` no tiene actualmente
permiso sudo en VM03 (`sudo: I'm sorry useransible. I'm afraid I can't do that`).
No se modificó la VM ni se almacenaron contraseñas. Para continuar, desde la
consola de VM03 se debe habilitar temporalmente sudo para `useransible`, ejecutar
el playbook `ansible/playbooks/03-configurar-servicios-servidor.yml --limit
ppi-server`, validar `systemctl is-active ppi-api` y retirar inmediatamente el
permiso temporal. No se necesita conectar Internet.

### Revisión cruzada Codex + Claude (2026-08-12)

Claude Code participó en la implementación de dos correcciones acotadas, revisadas posteriormente por Codex:

- `configs/server/ppi-api.py`: el registro JSONL conserva la primera dirección de `X-Forwarded-For` cuando la solicitud llega mediante Nginx; si no existe, usa la dirección del socket.
- `configs/server/nginx-ppi.conf`: la ruta `/api/` queda publicada tanto en HTTP como en HTTPS, manteniendo el proxy hacia `127.0.0.1:8090` y las cabeceras de trazabilidad.

Validaciones ejecutadas: `python3 -m py_compile configs/server/ppi-api.py`, `git diff --check` y comprobación de que existen exactamente dos bloques `location /api/` (uno por servidor). No se desplegaron cambios en las VMs. La activación remota continúa bloqueada hasta otorgar temporalmente privilegios `sudo` a `useransible` desde la consola de VM03; después deberán retirarse.

## Criterios de aceptación

Un episodio nuevo sólo entra al dataset si pasa preflight, captura íntegra,
`kernel_drops=0`, `decoder_invalid=0`, reconciliación de volumen, EVE completo,
hashes válidos y extracción reproducible. Antes de entrenar se ejecutará una
auditoría de duplicados por `episode_id` y vector, y una revisión de cruces.

El orden obligatorio será: recolectar normales v2 → congelar train → recolectar
anomalías ciegas → calibrar en validation → evaluar una sola vez en test. No se
hará scoring ni reentrenamiento sobre el dataset F1 actual hasta aprobar esta
política y publicar el esquema v2.
