# Plan de reentrenamiento (v3 + capa 2) — PARA DESPUÉS DE LA VALIDACIÓN

> **NO ejecutar antes de la validación interna del jueves.** El modelo congelado
> `if_recalibrado_desplegable.joblib` (FPR 4,45 %) es el artefacto que se valida;
> toda la evidencia (notas 24–32) lo describe. Reentrenar antes invalidaría esa
> evidencia y arriesgaría romper lo que funciona. Esto es la **siguiente versión**.

## Objetivos del reentrenamiento (motivados por debilidades medidas)
1. **Capa 2 en el scoring** (recom. ing. Fernando; ARP spoofing hoy 0 %): usar el
   extractor **v3** que añade features L2.
2. **Mejorar DNS en el modelo** (hoy 0 %, lo salva el heurístico): más volumen/tiempo
   de DGA en el entrenamiento o features DNS adicionales.
3. Mantener o bajar el **FPR** (hoy 4,45 % global del modelo).

## Pasos (todos reproducibles, sin tocar producción hasta el despliegue)
1. **Dataset**: consolidar la línea base v3 (`artifacts/linea-base/multilayer-v3.csv`,
   31 features con L2) + episodios de ataque etiquetados.
2. **Particionar sin fuga temporal**: `scripts/dataset/particionar_linea_base.py`
   (bandas de guarda).
3. **Entrenar**: `scripts/modeling/entrenar_preliminar.py` (IsolationForest) sobre v3.
4. **Recalibrar el umbral** en la red real (como se hizo para v2): fijar el umbral por
   percentil de FPR objetivo; **congelar**.
5. **Evaluar ANTES de desplegar**: correr la batería (notas 22/26) + `30-metricas.py`
   sobre el modelo nuevo; comparar v2 vs v3 (cobertura, FPR, latencia, ARP, DNS).
   **Criterio de aceptación**: v3 ≥ v2 en cobertura y ≤ v2 en FPR, y ARP/DNS mejoran.
6. **Desplegar** solo si pasa el criterio: nuevo `.joblib` + manifest + `--schema
   multilayer-v3.json` en el motor; respaldar el v2; `sudo -n systemctl restart
   ppi-motor`. Registrar como nueva versión del detector.
7. **Rollback**: conservar `if_recalibrado_desplegable.joblib` (v2) y su manifest; si
   el v3 regресa en algo, volver a v2 (un cp + restart).

## Qué NO cambia
El pipeline de enforcement (feed firmado, agentes, heurísticos) es independiente del
modelo; solo cambia el `.joblib` + `--schema`. Los heurísticos (incl. el fix de
`port_scan` 2026-10-06.2) siguen igual.

## Gate
Ejecutar este plan **tras** la validación del jueves, con una ventana de captura v3
propia y revalidación completa antes de reemplazar el modelo congelado.
