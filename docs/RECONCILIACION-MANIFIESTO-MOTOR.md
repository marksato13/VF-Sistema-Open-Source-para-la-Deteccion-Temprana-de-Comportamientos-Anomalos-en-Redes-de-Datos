# Reconciliación del detector documentado y el desplegado

Verificado por SSH en Sensor1 el 2026-10-09. Este documento describe el estado; **no cambia artefactos, umbrales ni servicios**.

| Fuente | Qué declara | Lo que realmente corre | Acción |
|---|---|---|---|
| `systemctl cat ppi-motor` | Descripción textual «OCSVM», pero `ExecStart` apunta a `artifacts/preliminar/if_recalibrado_desplegable.joblib`, `manifest-if-recalibrado.json` y `--detector-name if_recalibrado_2026_09` | Isolation Forest recalibrado, servicio activo | Corregir el generador/descriptor **al planificar un despliegue**; no editar unidad viva para una demo. |
| `configs/cyberflow.toml` genérico | `modelo=artifacts/model/ocsvm_scaled.joblib`, `manifiesto=artifacts/model/manifest.json`, `umbral=1.8126087939765134`, `calibrado_en_esta_red=false` | Sensor1 usa `configs/cyberflow.local.toml`: IF y calibrado=true | Conservar como perfil histórico/instalación no calibrada. No regenerar systemd con este fichero. Documentar un perfil local específico, previa aprobación de Mark. |
| `artifacts/model/manifest.json` del laboratorio original | `if_primary_weighted` como conclusión principal; `ocsvm_scaled` como comparador | No es el manifiesto usado por `ppi-motor` | Mantener íntegro como evidencia experimental; no reescribirlo retrospectivamente. |
| `artifacts/preliminar/manifest-if-recalibrado.json` de Sensor1 | Detector `if_recalibrado_2026_09` y modelo desplegable | Es el manifiesto que usa el motor y el panel | Tratarlo como fuente operativa; no versionar secretos ni sustituir el modelo. |
| `docs/dataset/MODEL_CARD_OCSVM.md` | OCSVM del laboratorio v2, FPR 4,71 % y 88,3 % sobre su test | Histórico, no describe Sensor1 | Conservar como model card generada histórica. La ficha operativa está en `MODEL_CARD_IF_RECALIBRADO.md`. |
| `scripts/engine/dashboard.py` antes del bloque B1 | Tarjeta fija «OCSVM» y ficha de artefactos `ocsvm_scaled.joblib` | Falsas referencias en panel aun si el motor corría IF | B1 ya usa el `detector_name` del API y el `model_path` del manifiesto; validar roles y JS servido antes de desplegar. |

El motor toma el **umbral desde el manifiesto del detector seleccionado** (`load_threshold`); el `.toml` alimenta al generador de servicios y sus rutas/`detector`, por lo que **no** es correcto afirmar que el `.toml` obsoleto sea inocuo si se vuelve a generar la unidad. El umbral de IF es `score_samples = -0,568892`; corresponde al punto `decision_function = -0,068892` por el offset de -0,5. No intercambiar estas escalas.

El linaje es: `if_primary_weighted` fue preseleccionado en el experimento v2; posteriormente se promovió `ocsvm_scaled` al observar el conjunto de evaluación (sesgo declarado); al llevar ese modelo a otra red, el FPR inicial fue 92,4 %, y se recalibró Isolation Forest con normalidad de la red del Sensor1. El FPR **4,45 %** corresponde al test normal retenido de esa recalibración; no borra el FPR histórico **22,97–25,81 %** medido en F6 bajo otra configuración. La detección **69 % global** corresponde a 54/78 ventanas de Kali de septiembre; 9/9 de la batería posterior describe el **stack híbrido por episodio**, no el modelo solo.

## Evidencia comprobada

- Unidad viva `ppi-motor.service`: `--detector-name if_recalibrado_2026_09`, ruta del joblib y del manifiesto preliminar. `configs/cyberflow.local.toml`: `calibrado_en_esta_red=true` y la misma ruta. Servicio `active`.
- SHA-256 del joblib vivo: `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a`.
- Informe de calibración real `artifacts/preliminar/ensayo-if-v2.json` en Sensor1: SHA-256 `ec3ed06304fdbe6367ab1b69e40498980e6eed6df890f67ae5c4001f98c86421`, `train=204148`, `validation=65633`, `test=65421`, `fpr_test=0.044527`, `umbral_decision_function=-0.06889178778834089`.
- Orquestación: evidencia `L-recalibracion-seco-sensor1-2026-09-29.md`, `M-deteccion-kali-sensor1-2026-09-30.md` y runbook de congelado.

## Decisión pendiente de Mark

Decidir si `configs/cyberflow.toml` será una plantilla genérica histórica o se introducirá un perfil reproducible del despliegue real. Cambiar el default a rutas preliminares no publicadas rompería una instalación nueva; tampoco debe mostrarse el perfil genérico como «configuración viva» en la GUI. El bloque B1 muestra la configuración local cuando existe y el modelo declarado por el manifiesto.
