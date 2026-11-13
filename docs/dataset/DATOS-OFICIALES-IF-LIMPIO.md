# Datos oficiales del modelo operativo `if_limpio_2026_10`

**Data oficial: 337 719 ventanas** del Sensor1 → tras la banda de guarda, **334 941**
(entrenamiento 203 967 + validación 65 553 + prueba 65 421). Con ella se entrenó el modelo desplegado y se calibró el
umbral que usa el motor (α = 0,01 → `score_samples < -0.6223889502095352`). Sustituye como referencia a «≈337 980».

**Descarga (Release `datos-if-limpio-2026-10`):**
<https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos/releases/tag/datos-if-limpio-2026-10>

| Asset | SHA-256 |
|---|---|
| [`if-limpio-2026-10-particionado-limpio.csv.gz`](https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos/releases/download/datos-if-limpio-2026-10/if-limpio-2026-10-particionado-limpio.csv.gz) (7,5 MB) | `84697fc3efc4c4c9eb07017582d52b4852d6b77712b3bbbdfe0fc29670ba827e` (descomprimido: `5ef83b32…1b573`) |
| `exclusiones-entrenamiento-181.csv` / `validacion-kali-80-excluidas.csv` | iguales a las de `exclusiones-if-limpio/` |
| `DATOS-OFICIALES-IF-LIMPIO.json`, `SHA256SUMS` | manifiesto y hashes |

Comprobar: `gunzip -k if-limpio-2026-10-particionado-limpio.csv.gz && sha256sum -c SHA256SUMS`.
El CSV pesa 149 MB sin comprimir (supera el límite de GitHub para el repositorio), por eso va como asset del Release
y no dentro de `artifacts/`. Es un conjunto aparte del dataset `multilayer-v2`: variables derivadas por IP y ventana
(no paquetes), con IP internas del laboratorio aislado.

## Fichero físico

| Campo | Valor |
|---|---|
| Fichero | Sensor1 `artifacts/preliminar/limpio-2026-10/particionado-limpio.csv` |
| SHA-256 | `5ef83b32469238b74eb16c2c2ff422a7757711318c0c77646e67bb966e61b573` |
| Filas / bytes | 337 980 / 149 543 885 |
| Origen | `artifacts/aprendizaje/base/particionado-nota-L.csv` (sha `bdf6f6419ec19e711c7add9e8b5f1440b896b32270c25d69b7e8267d4f9aba7a`) |
| Modelo | `if_limpio_2026_10_desplegable.joblib`, sha `df547da098e51171aa267c8466edc6624bc1bd5c6b602639cc00bd4711a2fd60` |

## Cadena de recuentos

Clave de ventana: (`campaign_id`, `entity_ip`, `window_end_utc`).

| Paso | Filas | Lista |
|---|---:|---|
| `particionado-limpio.csv` | 337 980 | — |
| − Kali 10.10.20.30 excluida del entrenamiento (`eligible_training=False`, 27-sep 21:35–22:05 UTC) | −181 | [`exclusiones-if-limpio/exclusiones-entrenamiento-181.csv`](exclusiones-if-limpio/exclusiones-entrenamiento-181.csv) (sha `5403ed33…2301`) |
| − Kali 10.10.20.30 en validación, excluida solo de la calibración α (normalidad no confirmada; no se etiqueta como ataque) | −80 | [`exclusiones-if-limpio/validacion-kali-80-excluidas.csv`](exclusiones-if-limpio/validacion-kali-80-excluidas.csv) (sha `a8d1de2d…74dc`) |
| **Data oficial** | **337 719** | |
| − banda de guarda de 60 s por bloque de 2 h (`particion=descartada_guarda`) | −2 778 | columna `particion` |
| **Tras partición y depuración** | **334 941** | |
| · entrenamiento | 203 967 | |
| · validación (umbral) | 65 553 | |
| · prueba normal | 65 421 | incluye 74 ventanas de 10.10.20.30 |

Comprobación: 337 980 − 181 − 80 = 337 719; 337 719 − 2 778 = 334 941 = 203 967 + 65 553 + 65 421.
Umbral: `numpy.quantile(score_samples(validación 65 553), 0.01, method="linear")` = `-0.6223889502095352`.

Manifiesto legible por máquina: [`DATOS-OFICIALES-IF-LIMPIO.json`](DATOS-OFICIALES-IF-LIMPIO.json). Registro completo
de la calibración en el repositorio de la investigación (`VF-PPI-TESIS-ORQUESTACION`,
`03-entregables/13-respuesta-observaciones-validacion-interna/seccion4-resultados/4.1-modelos/`).

`MODEL_CARD_IF_RECALIBRADO.md` describe el modelo **anterior** (IF recalibrado, 337 980 filas, α = 0,05) y se
conserva como histórico.
