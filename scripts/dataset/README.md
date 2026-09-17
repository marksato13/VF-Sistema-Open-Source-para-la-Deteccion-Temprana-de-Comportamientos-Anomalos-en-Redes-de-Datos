# scripts/dataset/ — ensamblado del dataset

## Vigente: `multilayer-v2` (28 features, dataset actual)

- `build_multilayer_v2_dataset.py` combina las filas elegibles de las campañas
  `v2` cerradas en un único CSV, exigiendo un mapa explícito
  `campaign_id → train|validation|test`. Cada campaña es un `episode_id`; si
  un episodio aparece en más de una partición, el ensamblador falla.

  Ejemplo de mapa:

  ```json
  {"F2N-DNS-MULTI-10-R01":"train","F2N-DNS-MULTI-10-R04":"validation","F2N-DNS-MULTI-10-R05":"test"}
  ```

- `run_v2_anomaly.py` ejecuta únicamente la matriz de evaluación ciega
  `multilayer-v2-anomalies.json` (anomalías heredadas). Cada episodio queda en
  `partition=evaluation_only` y `label=anomaly`; nunca se agrega al CSV normal.
- `run_v2_anomaly_kali.py` es el equivalente para las anomalías reales
  originadas en Kali (`10.20.0.100`), vía `scripts/campaign/run-f1-kali.sh` —
  ver `docs/fase03-dataset/` para el detalle de cada familia de ataque.
- `audit_multilayer_v2.py` audita el CSV consolidado (esquema, particiones,
  duplicados, cobertura de features) sin escribir nada; es el gate que corren
  también el calibrador (`scripts/modeling/calibrate_multilayer_v2_v1.py`) y
  el motor de tiempo real antes de confiar en el dataset.

Extracción por campaña individual: `scripts/features/extract_multilayer_v2.py`
(no vive en esta carpeta, ver `scripts/features/README.md`).

## Legado: `f1-normal-v2` (14 features, pipeline anterior)

`build_f1_dataset.py` es el ensamblador del dataset **anterior** (14 features,
`f1-normal-v2`, 145 celdas), superado por `multilayer-v2`. Se conserva sin
modificar porque construyó la evidencia histórica de `docs/fase03-dataset/01`
a `05` y `docs/fase04-modelado/01-protocolo-modelado-F1-v2.md`; no se usa
para trabajo nuevo.

```bash
export PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts
python3 scripts/dataset/build_f1_dataset.py --audit-only  # solo auditoría, no escribe
python3 scripts/dataset/build_f1_dataset.py                # construcción definitiva
```

Requiere exactamente las 145 celdas válidas de `f1-normal-v2`, sin campañas
inválidas y con el repositorio limpio. Valida bundles SHA-256, manifiesto,
ledger, argumentos del escenario, PCAP/EVE, reporte de extracción, CSV,
commit Git, matriz, esquema, split y dominio de las 14 features.

### Resumen agregado por repetición (pipeline legado)

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
python3 scripts/analysis/summarize_f1_repetition.py \
  --repetition 1 \
  --require-complete
```

`gate_pass=true` exige que la repetición contenga todos los perfiles de la
matriz, que Git esté limpio y que el repositorio de evidencia no tenga
campañas inválidas ni advertencias. Los vectores exactos repetidos dentro de
una campaña, entre campañas y entre particiones se reportan por separado como
diagnóstico; una coincidencia de las 14 features no prueba por sí sola
reutilización de una sesión, por lo que no se elimina ni convierte
automáticamente en fallo de recolección.

## Convenciones comunes a ambos pipelines

El destino es `$PPI_ARTIFACTS_ROOT/datasets/<nombre>/`, fuera de Git. Sin la
variable se conserva `artifacts/` como valor compatible para auditar pilotos
históricos; las campañas y datasets oficiales requieren el volumen dedicado.
Si el destino ya existe, los scripts se detienen y nunca reemplazan un
dataset silenciosamente.
