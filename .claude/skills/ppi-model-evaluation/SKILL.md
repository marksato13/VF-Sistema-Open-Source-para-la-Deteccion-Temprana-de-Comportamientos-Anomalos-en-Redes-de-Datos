---
name: ppi-model-evaluation
description: "Evalúa y compara el OCSVM congelado y sus candidatos con métricas trazables, intervalos, denominadores, análisis por familia, significancia y límites de selección posterior."
---

# Evaluación de modelos del PPI

Lee `docs/agent-context/ppi-data-science-context.md` desde la raíz, verifica
`docs/dataset/SHA256SUMS` y solo entonces carga archivos `.joblib`.

## Procedimiento

1. Reproduce el umbral y los recuentos del manifiesto antes de calcular métricas
   adicionales. Aborta ante cualquier diferencia.
2. Define anomalía como clase positiva y documenta la regla `score < threshold`.
3. Reporta matriz de confusión, recall/detección, especificidad, precisión, F1,
   FPR y ROC-AUC con numeradores, denominadores e intervalos de Wilson para
   proporciones.
4. Separa global, Kali real, heredado, familia y episodio. No mezcles unidades.
5. Compara candidatos en el mismo punto de calibración y declara que hay siete
   filas pero seis objetos únicos.
6. Para pruebas pareadas, respeta clusters por episodio. Corrige multiplicidad y
   no llames “mejor” a una diferencia no demostrada.
7. Expón D-01: OCSVM fue promovido después de observar la evaluación; sus
   valores absolutos son optimistas aunque una ventaja relativa sea estable.
8. Contrasta siempre FPR offline y operativo.

## Salida

Genera una tabla auditable y una conclusión de defensa: qué métrica importa,
qué sostiene la evidencia y qué no puede afirmarse.
