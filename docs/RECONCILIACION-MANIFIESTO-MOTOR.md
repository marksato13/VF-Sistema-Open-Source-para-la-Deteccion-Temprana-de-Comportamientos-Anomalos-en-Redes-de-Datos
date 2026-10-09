# Reconciliación del detector documentado y el desplegado

Verificado por SSH en Sensor1 el 2026-10-09. Este documento describe el estado; **no
cambia artefactos, umbrales ni servicios**. Ficha consolidada:
[`FICHA-TECNICA-DESPLIEGUE-VIGENTE.md`](FICHA-TECNICA-DESPLIEGUE-VIGENTE.md).

| Fuente | Qué declara | Lo que realmente corre | Acción |
|---|---|---|---|
| `systemctl cat ppi-motor` | Descripción textual «OCSVM», pero `ExecStart` apunta a `artifacts/preliminar/if_recalibrado_desplegable.joblib`, `manifest-if-recalibrado.json` y `--detector-name if_recalibrado_2026_09` | Isolation Forest recalibrado, servicio activo | Corregir la descripción al planificar un despliegue; no editar la unidad viva para una demo. |
| [`configs/cyberflow.toml`](../configs/cyberflow.toml) (perfil genérico) | `modelo=artifacts/model/ocsvm_scaled.joblib`, `manifiesto=artifacts/model/manifest.json`, `umbral=1.8126087939765134`, `calibrado_en_esta_red=false` | Sensor1 usa `configs/cyberflow.local.toml`: IF y `calibrado=true` | Conservar como perfil histórico / instalación no calibrada. No regenerar systemd con él en Sensor1. |
| [`artifacts/model/manifest.json`](../artifacts/model/manifest.json) del laboratorio | `if_primary_weighted` como conclusión principal; `ocsvm_scaled` como comparador | No es el manifiesto que usa `ppi-motor` | Mantener íntegro como evidencia experimental; no reescribirlo retrospectivamente. |
| `artifacts/preliminar/manifest-if-recalibrado.json` (Sensor1) | Detector `if_recalibrado_2026_09` y modelo desplegable | Es el manifiesto que usan el motor y el panel | Fuente operativa; su publicación queda pendiente como evidencia (ver abajo). |
| [`docs/dataset/MODEL_CARD_OCSVM.md`](dataset/MODEL_CARD_OCSVM.md) | OCSVM del laboratorio v2, FPR 4,71 %, 88,3 % | Histórico; no describe Sensor1 | Conservada como card histórica (el generador la rotula así). Card operativa: [`MODEL_CARD_IF_RECALIBRADO.md`](dataset/MODEL_CARD_IF_RECALIBRADO.md). |
| [`scripts/engine/dashboard.py`](../scripts/engine/dashboard.py) | Tarjeta «Detector» fija en «OCSVM» y paso del recorrido «One-Class SVM» | Referencias falsas en el panel aunque el motor corra IF | Corregido: la tarjeta usa el `detector_name` real de `/api/status`. |

El motor toma el **umbral desde el manifiesto del detector seleccionado**
(`load_threshold`); el `.toml` alimenta al generador de servicios y sus rutas/detector,
así que **no** es inocuo si se vuelve a generar la unidad con el perfil genérico. El
umbral del IF es `score_samples = −0,568892`, que corresponde a
`decision_function = −0,068892` por el `offset_ = −0,5` de sklearn. No intercambiar
estas escalas.

**Linaje.** `if_primary_weighted` fue preseleccionado en el experimento v2; después se
promovió `ocsvm_scaled` al observar el conjunto de evaluación (sesgo declarado). Al
llevar el OCSVM a la red de Sensor1 sus primeras decisiones fueron 92,4 % ALERT sin
ataques, y se recalibró un Isolation Forest con normalidad de esa red; su FPR sobre
**test normal retenido** fue **4,45 %**. **Esa diferencia no aísla el efecto de
recalibrar**: entre ambas mediciones cambiaron el modelo, los datos y el alcance (se
excluyó el plano de control y se deduplicó el espejo). El 4,45 % tampoco borra el FPR
histórico **22,97–25,81 %** de F6 (otra configuración). La detección **69 %** son 54/78
ventanas de Kali de septiembre; el 9/9 de la batería posterior es del **stack híbrido
por episodio**, no del modelo solo.

## Evidencia comprobada

- Unidad viva `ppi-motor.service`: `--detector-name if_recalibrado_2026_09`, ruta del
  joblib y del manifiesto preliminar. `configs/cyberflow.local.toml`:
  `calibrado_en_esta_red=true` y la misma ruta. Servicio `active`.
- SHA-256 del joblib vivo: `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a`.
- Informe de calibración `artifacts/preliminar/ensayo-if-v2.json` en Sensor1: SHA-256
  `ec3ed06304fdbe6367ab1b69e40498980e6eed6df890f67ae5c4001f98c86421`, `train=204148`,
  `validation=65633`, `test=65421`, `fpr_test=0.044527`,
  `umbral_decision_function=-0.06889178778834089`.
- Evidencia de investigación (commit `bb6e91d784622aab52f8b9f579186e50484dfdf6` de
  `VF-PPI-TESIS-ORQUESTACION`):
  [L](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/L-recalibracion-seco-sensor1-2026-09-29.md),
  [M](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/M-deteccion-kali-sensor1-2026-09-30.md).

## Pendiente de publicar

El manifiesto operativo, el informe de calibración y la salida de
[`scripts/modeling/verificar_equivalencia_umbral.py`](../scripts/modeling/verificar_equivalencia_umbral.py)
ejecutado sobre el artefacto vivo se publicarán como evidencia en orquestación (son
JSON de métricas, sin secretos). El joblib no se publica; queda su hash.

## Decisión pendiente

Decidir si `configs/cyberflow.toml` sigue como plantilla genérica histórica o se
introduce un perfil reproducible del despliegue real. Cambiar el valor por defecto a
rutas preliminares no publicadas rompería una instalación nueva.
