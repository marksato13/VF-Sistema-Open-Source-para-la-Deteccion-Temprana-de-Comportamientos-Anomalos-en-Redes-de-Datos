# Cómo replicar este trabajo

Qué se puede reproducir con lo publicado, qué no, y por qué. Escrito para alguien que
no tiene acceso a nuestro laboratorio.

> **Dos modelos, no confundir.** Lo que se reproduce desde **este** repositorio son las
> cifras del **modelo de laboratorio v2 (OCSVM congelado)** — resultados **históricos**.
> El modelo **desplegado hoy** es el **Isolation Forest recalibrado**
> (`if_recalibrado_2026_09`): su recalibración usó tráfico normal del Sensor1 que **no se
> publica**, así que de él se verifica el **manifiesto y el hash**, no se re-deriva aquí.
> Ver [`docs/FICHA-TECNICA-DESPLIEGUE-VIGENTE.md`](docs/FICHA-TECNICA-DESPLIEGUE-VIGENTE.md).

---

## Tres cosas distintas (no son lo mismo)

| | Qué significa | ¿Se puede aquí? |
|---|---|---|
| **Reproducir métricas publicadas** | Mismos datos + mismo código → mismo número | **Sí**, con los artefactos publicados (modelo de laboratorio) |
| **Replicar el despliegue** | Instalar y correr el sistema en otra máquina | **Parcial**: el software sí; el laboratorio de 5 VM exige hipervisor |
| **Validar en otra red** | Datos nuevos de otra red con el mismo método → resultados consistentes | **No** sin recalibrar con tráfico de **esa** red |

Instalar en una segunda VM demuestra **replicabilidad del despliegue**, no que los
resultados científicos se reproduzcan en otra red. Cada afirmación necesita su evidencia.

---

## Lo que sí se reproduce con lo que hay aquí (modelo de laboratorio v2 · OCSVM, histórico)

| Se reproduce | Con qué | Comprobación |
|---|---|---|
| **Las cifras del modelo congelado v2** | `artifacts/dataset/*.csv` + `artifacts/model/ocsvm_scaled.joblib` | Reevaluar da **13/276** y **158/179** exactos |
| **La extracción de variables** | `scripts/features/extract_multilayer_v2.py` | Mismo PCAP → mismas **28** columnas (contrato v2) |
| **El determinismo del pipeline** | `scripts/modeling/` | 10 ajustes → **mismo SHA-256** |
| **La ablación por capas** | `scripts/modeling/experiments/ablacion_multicapa.py` | 66,5 % → 88,8 %, p < 0,001 |
| **La integridad de todo** | `docs/dataset/SHA256SUMS` | `sha256sum -c` |

```bash
git clone <este repositorio> && cd <carpeta>
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-model.txt
sha256sum -c docs/dataset/SHA256SUMS   # desde la raíz
```

Si un solo hash no cuadra, **pare**: los artefactos no son los publicados y nada de lo
que salga después es comparable.

> **Versiones (punto a respetar).** El **demo** y las **herramientas de configuración**
> corren con **Python 3.11+**. El **modelo congelado** exige las versiones **exactas** de
> `requirements-model.txt`; con otras, el `joblib` puede no cargar igual y las cifras
> dejan de ser comparables. No mezcle ambos entornos.

---

## Lo que NO se reproduce, y hay que decirlo

**El laboratorio.** Cinco máquinas virtuales sobre VMware ESXi con tres redes aisladas.
Los playbooks de `ansible/` lo levantan, pero necesitan el hipervisor. Sin él puede leer
la configuración, no ejecutarla.

**Los PCAP y el `eve.json` completos.** No se publican: pesan demasiado y contienen
tráfico del laboratorio sin sanear. Lo que sí se publica es el **dataset derivado**, que
es lo que alimenta al modelo.

**La recalibración del modelo desplegado.** El IF recalibrado se calibró con tráfico
normal del Sensor1 (≈337 980 ventanas) que **no se publica**. De él queda la evidencia
de calibración, su manifiesto y su hash; no se re-deriva desde este repositorio.

**Las campañas.** Cada una está documentada con su manifiesto, contadores y hashes, pero
ese registro vive en el repositorio de la investigación
(`VF-PPI-TESIS-ORQUESTACION`), organizado en `01-arquitectura/`, `02-metodologia/`,
`03-entregables/` y `04-evidencias/` — **no** en una carpeta `investigacion/`. Este
repositorio es el **producto**. Volver a ejecutarlas exige el laboratorio.

---

## Lo que debe saber antes de usar estos resultados

Limitaciones **medidas**, con su contexto (no intercambiar entre modelos/escenarios):

**El falso positivo depende del conjunto y la configuración.** El **4,45 %** es del IF
recalibrado sobre **test normal retenido**; el histórico F6 (OCSVM, otra configuración)
dio **25,81 %** y **22,97 %**. Un `iperf-tcp 200M` legítimo, en aislamiento, produjo un
falso positivo genuino que bloqueó al cliente. El FPR del **sistema completo** (con
heurísticos y enforcement) se mide **aparte**. Sobre tráfico pesado, recalibre antes.

**El motor usa un buffer incremental.** No reparsea el anillo de PCAP completo en cada
ciclo. Los atrasos históricos bajo carga (hasta ~161 s) son de la **versión anterior**;
la versión actual debe medirse de nuevo.

**Una de las 28 variables del modelo no es observable.**
`tls_handshake_failure_ratio_60s` es constante en todo el dataset; las otras 27 varían.
El extractor v3 emite **31** variables (añade capa 2), pero el modelo puntúa con **28**
(contrato v2) y la capa 2 no entra al scoring.

El registro completo de cómo se investigó —diseño experimental, campañas, modelado y
validación— está en `VF-PPI-TESIS-ORQUESTACION` (`02-metodologia/`, `04-evidencias/`).
Aquí queda el producto y lo necesario para ejecutarlo y verificarlo.

Y una consideración de método (consta así): el modelo de laboratorio se eligió por
desempeño empírico medido sobre una evaluación bloqueada de un solo paso. El manifiesto
registra `ocsvm_scaled` con `role = sensitivity_or_comparator` mientras la política
declara principal a `if_primary_weighted`: **el artefacto congelado contradice su política
registrada**. El detalle del linaje —y por qué hoy corre un tercer modelo, el IF
recalibrado— está en [`docs/RECONCILIACION-MANIFIESTO-MOTOR.md`](docs/RECONCILIACION-MANIFIESTO-MOTOR.md).

---

## Composición del dataset

```
220 episodios normales · 1.373 ventanas
    entrenamiento 824 · validación 273 · prueba 276
179 ventanas anómalas
    161 originadas en Kali · 18 heredadas, reportadas por separado
```

Partición **disjunta por episodio**: ningún episodio se reparte entre particiones, y los
gates lo comprueban. El umbral del modelo de laboratorio se calibró **solo con
validación** (`alpha = 0,05`, `k = 13`), nunca con prueba. (El IF desplegado se recalibró
aparte en el Sensor1, también con `alpha = 0,05` sobre su validación.)

---

## Dónde está cada cosa

| | |
|---|---|
| **Ficha del despliegue vigente** | `docs/FICHA-TECNICA-DESPLIEGUE-VIGENTE.md` |
| Model card operativa (IF recalibrado) | `docs/dataset/MODEL_CARD_IF_RECALIBRADO.md` |
| Model card de laboratorio (OCSVM, histórica) | `docs/dataset/MODEL_CARD_OCSVM.md` |
| Reconciliación manifiesto vs motor | `docs/RECONCILIACION-MANIFIESTO-MOTOR.md` |
| Datasheet del dataset | `docs/dataset/DATASHEET_MULTILAYER_V2.md` |
| System card del motor | `docs/dataset/SYSTEM_CARD_MOTOR.md` |
| Diccionario de variables | `docs/dataset/DICCIONARIO_VARIABLES.md` |
| Modelo congelado de laboratorio y su manifiesto | `artifacts/model/` |
| Validación operacional (histórica F6) | `results/f6/f6_resultados.jsonl` y `docs/dataset/SYSTEM_CARD_MOTOR.md` |

---

## Licencias

**Código: MIT** (`LICENSE`). **Datos y documentación: ver `LICENSE-DATA`.** Son distintas
a propósito.

## Cómo citar

`CITATION.cff`, en la raíz. GitHub lo lee y ofrece la cita ya formateada en el botón
«Cite this repository».
