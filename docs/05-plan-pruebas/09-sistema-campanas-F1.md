# Sistema reproducible de campañas F1

Fecha de implementación: 20 de julio de 2026.

## Objetivo y alcance

Este bloque transforma las ejecuciones manuales de calibración en campañas trazables. Su función es conservar el contexto técnico necesario para decidir si una ejecución puede entrar al dataset. No etiqueta automáticamente una prueba como válida y no sustituye la revisión de calidad.

Los resultados de ejecución se guardan en `artifacts/campaigns/<ID>/`, excluido de Git. El repositorio conserva el código, la configuración y el procedimiento; PCAP, EVE, logs y datasets permanecen fuera de Git por tamaño, privacidad y riesgo de incluir datos sensibles.

## Componentes

| Componente | Función |
|---|---|
| `scripts/campaign/start.sh` | crea el manifiesto, bloquea ejecuciones simultáneas, audita las cuatro VMs, toma contadores iniciales e inicia el muestreo del Sensor |
| `scripts/campaign/stop.sh` | espera tres segundos para estabilización, detiene el muestreo, toma contadores finales, extrae el segmento EVE acotado, calcula deltas y genera `SHA256SUMS` |
| `scripts/campaign/run-f1.sh` | ejecuta un escenario benigno limitado desde VM05 y garantiza el cierre de la campaña aunque falle el escenario |
| `scripts/campaign/sample-sensor.sh` | registra por segundo CPU de Suricata, RSS, memoria disponible y carga del Sensor |
| `ppi-suricata-metrics` | consulta el socket de Suricata y devuelve únicamente métricas JSON sin aceptar argumentos |
| `06-desplegar-orquestacion-campanas.yml` | instala el recolector restringido en Sensor y el generador F1 en Cliente |

Solo puede existir una campaña activa. El bloqueo evita mezclar dos escenarios y se mantiene hasta que `stop.sh` cierre la ejecución.

## Modelo de privilegios

`useransible` no puede consultar directamente el socket de comandos de Suricata. Se instaló `/usr/local/sbin/ppi-suricata-metrics` con propietario `root:root` y modo `0755`. La única regla persistente es:

```text
useransible ALL=(root) NOPASSWD: /usr/local/sbin/ppi-suricata-metrics ""
```

El ejecutable no acepta argumentos. El 20 de julio se validaron estos tres casos:

- ejecución exacta: devuelve estado, PID, contadores de captura, errores, RSS y posición de EVE;
- ejecución con argumento: rechazada por sudoers;
- `sudo -n /usr/bin/id`: rechazado con código 1.

El despliegue inicial del archivo de sudoers requiere una cuenta administrativa o consola ESXi. En esta instalación se transfirieron primero ambos archivos a `/tmp`, se validó la regla con `visudo`, se instalaron como `root` y se retiraron las copias temporales. Las actualizaciones posteriores quedan descritas por Ansible, pero siguen requiriendo privilegio administrativo para modificar el ejecutable propiedad de `root`.

## Evidencia por campaña

Cada directorio contiene como mínimo:

| Archivo | Contenido y uso |
|---|---|
| `manifest.json` | ID, fase, escenario, clase, propósito, horas local/UTC, commit, estado del árbol y topología |
| `inventory-*.txt` | hostname, hora, kernel, NTP, interfaces y rutas de cada VM |
| `sensor-before.json` / `sensor-after.json` | instantáneas acumuladas del Sensor |
| `sensor-timeseries.tsv` | serie temporal de recursos durante el escenario |
| `scenario-output.txt` / `scenario-stderr.txt` | salida y error del generador remoto |
| `eve-slice.jsonl` | registros EVE añadidos mientras la campaña estuvo activa |
| `deltas.json` | paquetes, drops, errores, overflow y número de registros EVE de la ventana |
| `SHA256SUMS` | integridad de todos los archivos anteriores |

La extracción EVE usa el intervalo cerrado entre el número de línea inicial y el checkpoint final; no usa `tail` hasta el final porque podrían incorporarse eventos posteriores al conteo. Solo se declara completa si el inode es igual antes y después. Si ocurre una rotación, se crea un segmento vacío y `eve_slice_status` queda como `unavailable_log_rotated`; esa campaña no debe aceptarse sin recuperar ambos archivos rotados.

El ejecutor espera un segundo antes del escenario para obtener una muestra basal. Al cerrar, la espera predeterminada de tres segundos permite que Suricata actualice EVE y sus contadores antes del checkpoint final. Puede ajustarse entre 0 y 10 segundos con `PPI_CAMPAIGN_SETTLE_SECONDS`; el valor efectivo queda registrado como `settle_seconds`. Para las campañas oficiales se conservará el valor predeterminado.

`cpu_percent_lifetime` de las instantáneas es el promedio desde el inicio del proceso. Para analizar carga durante el escenario debe usarse `cpu_percent` de `sensor-timeseries.tsv`, calculado con la diferencia de ticks de CPU cada segundo. Ese valor puede superar 100 % porque Suricata usa varios núcleos.

## Uso

Ejecutar desde la raíz del repositorio. El ID debe ser único y no debe reutilizarse.

```bash
# Calibración; nunca se incorpora directamente al dataset final
PPI_CAMPAIGN_PURPOSE=calibration \
  scripts/campaign/run-f1.sh CAL-F1-DNS-001 dns-valid 3

# Campaña experimental benigna
scripts/campaign/run-f1.sh F1-A05-R01 http 500MB 20M

# Throughput dentro del techo validado
scripts/campaign/run-f1.sh F1-A12-R01 iperf-tcp 200M 20
```

Para un escenario que todavía no tenga ejecutor integrado:

```bash
scripts/campaign/start.sh F1-A14-R01 F1 http-ssh-iperf benign experiment
# ejecutar el procedimiento controlado
scripts/campaign/stop.sh F1-A14-R01 0
```

Si el escenario falla, `run-f1.sh` cierra igualmente la campaña y registra `status=scenario_failed`. Los artefactos fallidos se conservan para auditoría, pero no ingresan al dataset.

## Criterios para aceptar una ejecución

Una campaña candidata debe cumplir todos estos puntos:

1. `manifest.status` es `completed`, `evidence.complete` es `true`, `scenario_exit_code` es 0 y `git.dirty` es `false`.
2. El commit del manifiesto corresponde a la versión revisada de scripts y configuraciones.
3. `counter_reset_detected` es `false`; `kernel_drops`, `decoder_invalid` y `alert_queue_overflow` son cero.
4. `eve_slice_status` es `complete_same_inode`.
5. Las cuatro VMs tienen hora, NTP, interfaces y rutas coherentes.
6. La salida confirma bytes, solicitudes, bitrate o resultado esperado del escenario.
7. No hubo otra fuente de tráfico no planificada durante la ventana.
8. Los hashes se verifican con `sha256sum -c SHA256SUMS`.

La aceptación exige revisión humana. Cero drops demuestra únicamente que Suricata no reportó pérdida bajo las condiciones observadas; no demuestra ausencia absoluta de paquetes perdidos en toda la ruta.

## Secuencia siguiente

1. Ejecutar una campaña DNS corta con propósito `calibration` para validar el orquestador extremo a extremo.
2. Corregir cualquier hallazgo y congelar el commit operativo.
3. Ejecutar repeticiones independientes de A5, A10, A12 y A13; añadir A14 después de implementar su coordinador.
4. Validar distribución de tamaños de paquetes y falsos positivos por campaña.
5. Solo después cerrar F1 y pasar a ataques F2 desde Kali, con un ejecutor y límites separados.

Todavía no se capturan PCAP desde el orquestador. EVE permite validar funcionamiento, pero las futuras 14 features de capa 3 y 4 requerirán PCAP o telemetría de flujo reproducible. La captura limitada, la rotación, el espacio en disco y la anonimización deben resolverse antes de producir el dataset definitivo.
