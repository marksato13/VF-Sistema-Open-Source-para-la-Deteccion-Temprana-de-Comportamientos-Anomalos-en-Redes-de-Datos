# Flujo de captura de datos y migración al pipeline multicapa v2

Fecha: 2026-08-12. Estado: **documentado; migración v2 pendiente de
implementación y validación piloto**.

## Resumen ejecutivo

El flujo de captura existente es defendible para F1/v1: registra PCAP crudo,
EVE de Suricata, métricas del sensor, manifiestos, ledger, logs de escenario y
hashes. Sin embargo, el orquestador oficial todavía apunta a la matriz y al
extractor `multilayer-v1`. El contrato `multilayer-v2`, su extractor y las
matrices v2 existen, pero no deben considerarse integrados hasta completar el
puente de ejecución y el ensamblador v2.

No se debe ejecutar la matriz oficial v2 mientras produzca CSV `multilayer-v1`:
la captura sería válida como evidencia cruda, pero las nuevas variables no se
extraerían y el dataset quedaría etiquetado de forma incorrecta.

## Flujo real de captura

1. `scripts/f1/run_matrix_profile.py` valida matriz, esquema, almacenamiento,
   repetición y partición; crea un ledger con hashes de matriz/argumentos,
   commit Git y `campaign_id`.
2. `scripts/campaign/start.sh` crea el manifiesto, registra las cuatro VMs,
   relojes, interfaces y rutas, toma métricas iniciales de Suricata y solicita
   al sensor iniciar `tcpdump`.
3. VM02 Sensor captura en `ens35` con filtro LAN↔DMZ, snaplen completo,
   buffer de 64 MiB y rotación de cuatro archivos de 512 MB. En paralelo se
   muestrean métricas del sensor.
4. VM05 Cliente o VM04 Kali ejecuta el escenario autorizado. Cliente produce
   tráfico normal; Kali sólo anomalías reservadas para evaluación ciega.
5. `scripts/campaign/stop.sh` espera el asentamiento, detiene tcpdump, copia
   PCAP, verifica hashes remoto/local, valida cada archivo con tcpdump y extrae
   el segmento EVE correspondiente a la ventana de campaña.
6. El cierre genera `manifest.json`, `pcap-start.json`, `pcap-stop.json`,
   `sensor-before.json`, `sensor-after.json`, `deltas.json`, `eve-slice.jsonl`,
   `sensor-timeseries.tsv`, `scenario-output.txt`, errores y `SHA256SUMS`.
7. El extractor lee PCAP/EVE y genera CSV más `extraction-report.json`; los
   logs API/DNS son evidencia auxiliar para reconciliar observaciones L7, no
   sustituyen al PCAP.

## Qué se registra y qué fuente alimenta cada señal

| Fuente | Registro | Uso |
|---|---|---|
| PCAP de VM02 | paquetes IP crudos, timestamps, protocolo, puertos, flags, tamaños | L3/L4; en v2 también TTL, fragmentación, retransmisión, duración y TX/RX |
| EVE Suricata | HTTP, DNS, TLS, timestamps y estados | L7; métodos, errores HTTP, autenticación, nombres DNS y TLS |
| API local | `auth.jsonl` con hora, IP reenviada, método, ruta y resultado | reconciliación de login 200/401 y respuestas controladas |
| dnsmasq | consultas DNS internas | reconciliación de nombres, respuestas y NXDOMAIN |
| manifiesto/ledger | escenario, argumentos, commit, repetición, partición y hashes | trazabilidad y reproducibilidad |
| métricas sensor | drops, ifdrops, decoder inválido y overflow | gate de integridad de captura |

## Protección contra fuga temporal

El extractor sólo incluye observaciones en la ventana causal:

```text
window_end - history < timestamp <= window_end
```

La fila sólo es elegible para entrenamiento cuando dispone de hasta 60 segundos
de historia verificada. Los eventos posteriores al cierre de una ventana no
pueden alterar sus features. Las particiones se asignan por episodio, nunca por
fila individual del mismo episodio.

## Estado de integración v1/v2

Actualmente las siguientes piezas aún son v1:

```text
run_matrix_profile.py  → f1-normal-v2.json + multilayer-v1.json
extract_campaign.sh    → extract_multilayer.py
salida                 → multilayer-v1.csv
build_f1_dataset.py    → multilayer-v1
```

La migración correcta debe crear un camino separado, sin sobrescribir F1:

```text
run_matrix_profile_v2.py
        ↓
multilayer-v2-normal.json
        ↓
start/stop (misma captura y gates)
        ↓
extract_multilayer_v2.py
        ↓
multilayer-v2.csv + reporte + hashes
        ↓
build_multilayer_v2_dataset.py
```

El pipeline v1 se conserva para reproducibilidad histórica. El pipeline v2 se
aceptará sólo después de un piloto que demuestre columnas, causalidad,
reconciliación PCAP/EVE/logs y `episode_id`.

## Plan de capturas para completar el dataset

### Fase P — pilotos normales

Ejecutar un episodio por perfil y verificar primero:

- API normal: GET/PUT/DELETE/login correcto y `/api/error` 500 controlado.
- API autenticación: logins fallidos 401.
- DNS multidestino y DNS mixto.
- HTTP 404, HTTPS/TLS, TCP/UDP, ICMP y tráfico mixto.

No se construye dataset con P; sólo se revisan evidencias y features.

### Fase N — normales v2

Ejecutar la matriz normal versionada con cinco repeticiones por perfil:

- R01–R03 → train.
- R04 → validation.
- R05 → test.

Cada ejecución debe tener `episode_id` único y pasar todos los gates de
integridad. La meta es ampliar gradualmente hasta 2.000–3.000 ventanas
independientes, no duplicar filas de F1-R05.

### Fase A — anomalías ciegas

Después de congelar normales y documentación de train, ejecutar desde Kali
únicamente contra la DMZ:

- ráfaga SYN limitada;
- sondeo restringido de puertos;
- sondeo UDP/53;
- NXDOMAIN sostenido;
- autenticación fallida repetitiva.

Las anomalías se etiquetan `label=anomaly`, se excluyen de train/validation y
se reservan para la evaluación final.

## Criterios de aceptación por captura

Una campaña entra al dataset sólo si:

- escenario y comando terminan con el resultado esperado;
- PCAP remoto/local coincide por SHA-256;
- PCAP es parseable y el conteo coincide con tcpdump;
- `kernel_drops=0`, `kernel_ifdrops=0`, `decoder_invalid=0` y sin overflow;
- EVE coincide con los checkpoints de Suricata;
- logs API/DNS son reconciliables por tiempo y episodio;
- extracción v2 genera al menos una fila elegible;
- hashes y manifiesto son completos;
- no hay mezcla de episodios entre particiones.

## Conclusión

La captura cruda y los controles de integridad son una buena base y ya están
operativos. Lo que falta antes de afirmar que el dataset v2 está completo es
integrar formalmente el orquestador y el ensamblador con `multilayer-v2`,
ejecutar pilotos, corregir discrepancias y sólo entonces lanzar la matriz
normal completa y las anomalías ciegas.
