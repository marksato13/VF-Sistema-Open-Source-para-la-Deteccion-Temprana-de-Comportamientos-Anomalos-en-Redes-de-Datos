# Ensamblador seguro del dataset F1 — G6

Fecha: 21 de julio de 2026. Implementación: `scripts/dataset/build_f1_dataset.py`.

## Decisión

El dataset final ya no se formará concatenando CSV manualmente. El ensamblador aplica gates de procedencia, integridad, partición y completitud antes de escribir cualquier split. Con `f1-normal-v2`, la auditoría debe encontrar cuatro pilotos `v1` excluidos, cero campañas oficiales aceptadas y 145 celdas faltantes; por tanto no produce dataset.

## Autoridad de los datos

El ensamblador no confía en un solo archivo. Cruza:

```text
matriz versionada ─┬─ manifiesto de campaña ─ paquete SHA/PCAP/EVE
                   ├─ ledger del ejecutor
                   ├─ reporte de extracción ─ paquete SHA/CSV
                   └─ matriz y esquema recuperados desde el commit citado
```

El nombre canónico `F1N-{PROFILE}-Rxx` determina una sola campaña posible por celda. La partición se recalcula desde la repetición y la matriz; no se acepta el valor del manifiesto sin comprobarlo.

## Gates implementados

### 1. Anti-calibración

- `purpose=experiment` en ledger y manifiesto;
- partición `train`, `validation` o `test` según R01–R05;
- rechazo de `calibration` y `excluded_calibration`, incluso con historia de 60 s.

### 2. Integridad de evidencia

- cobertura exacta y SHA-256 correcto de todos los archivos del bundle de campaña y de features;
- campaña `completed`, evidencia `complete=true`, cero drops, cero PCAP truncados y copia remota/local coincidente;
- paquetes capturados igual a parseados y EVE extraído igual al checkpoint;
- cero drops/ifdrops de Suricata, `decoder.invalid=0`, `alert_queue_overflow=0` y sin reset de contadores;
- al menos una muestra válida de recursos del Sensor.

### 3. Trazabilidad Git

- captura realizada con `git.dirty=false`;
- commit de 40 caracteres existente;
- SHA-256 de matriz y esquema recalculado con `git show <commit>:<ruta>`;
- coincidencia entre commit, manifiesto, ledger y reporte de extracción.

Esto impide validar retroactivamente una campaña antigua contra una matriz nueva solo porque el archivo actual tiene el mismo nombre.

### 4. Contrato del perfil

- ID, escenario, argumentos, estrato, estimación y cobertura idénticos a la matriz;
- hash canónico de los argumentos registrado por el ejecutor y el manifiesto;
- warm-up de 60 s y settle de 9 s;
- una matriz y un esquema únicos para todo el dataset.

### 5. CSV y dominio

- columnas y orden exactos de `multilayer-v1`;
- `campaign_id` correcto, entidad dentro de `10.20.0.0/24`, timestamp con zona horaria e historia de al menos 60 s;
- 14 valores numéricos finitos y no negativos; ratios entre 0 y 1;
- ninguna ventana duplicada y conteos iguales en CSV, reporte y ledger;
- hashes de PCAP/EVE/esquema/CSV recalculados, no solo leídos.

### 6. Completitud

- exactamente 29 perfiles × 5 repeticiones;
- una campaña por celda y listado explícito de cada celda faltante;
- repositorio actual limpio antes de construir;
- rechazo de destino preexistente para no sobrescribir un dataset anterior.

Los vectores idénticos entre campañas se reportan como sospechosos, pero no se eliminan automáticamente: una repetición legítima puede generar valores iguales y borrarla sesgaría la muestra.

## Salidas

Cuando las 145 celdas pasen, se crearán atómicamente:

```text
artifacts/datasets/f1-normal-v2/
├── train.csv
├── validation.csv
├── test.csv
├── manifest.json
└── SHA256SUMS
```

Cada fila agrega `partition`, `profile_id` y `repetition` como metadata, conserva la metadata causal y mantiene las 14 features en el orden congelado. El manifiesto registra cada campaña fuente, commit, hash del CSV y bytes PCAP.

## Pruebas adversariales

`tests/test_f1_dataset_builder.py` crea un repositorio Git y bundles sintéticos independientes. El candidato válido atraviesa todos los gates. Las pruebas negativas confirman rechazo de:

1. calibración forzada a `train`;
2. repetición R05 declarada como `train`;
3. `complete=true` con drops;
4. CSV modificado después del hash;
5. captura con Git sucio;
6. matriz actual distinta a la existente en el commit citado;
7. ID que no corresponde a la celda;
8. matriz incompleta;
9. desacuerdo del hash ledger/CSV;
10. EVE extraído distinto al esperado;
11. PCAP que alcanzó el límite de captura;
12. estado diferente entre ledger y manifiesto;
13. ventana duplicada dentro del CSV;
14. hash de argumentos distinto al perfil congelado.

La suite completa incluye una construcción sintética completa de 145 celdas, la reproducibilidad de la matriz `v1` y las pruebas del esquema de features.

## Uso reproducible

Auditar sin escribir:

```bash
python3 scripts/dataset/build_f1_dataset.py --audit-only \
  > artifacts/f1-dataset-audit.json
```

Intentar construir —actualmente debe terminar con código 3 por incompletitud—:

```bash
python3 scripts/dataset/build_f1_dataset.py
```

## Límite de seguridad

`SHA256SUMS` detecta corrupción o edición accidental mientras la lista permanezca intacta, pero no es una firma digital: un operador con escritura total podría modificar un archivo y regenerar la lista. Para la entrega final se debe copiar el bundle a almacenamiento de respaldo de solo lectura o firmar el manifiesto raíz después de cada lote. Este límite no se ocultará como si SHA-256 por sí solo demostrara autoría.

## Estado de G6

El ensamblador elimina una ruta importante de contaminación, pero G6 continúa pendiente por almacenamiento, aplicación/validación de las IP virtuales, SSH/SFTP y recolección oficial. El script no convierte pilotos exitosos en un dataset de entrenamiento.
