# Protocolo de entrenamiento multilayer-v2

El modelo se ajusta únicamente con las 44 ventanas de `train`. El umbral no
se elige mirando las anomalías: se fija como el percentil 5 de la función de
decisión sobre las 15 ventanas de `validation`. La evaluación final combina
las 16 ventanas normales de `test` con las 5 ventanas anómalas reservadas.

El script reproducible es `scripts/modeling/train_multilayer_v2.py` y genera
un reporte JSON con hashes, parámetros, matriz de confusión, ROC-AUC y
average precision. Con sólo 5 ventanas anómalas y episodios correlacionados,
las métricas son evidencia de esta evaluación controlada, no una estimación
productiva definitiva.

## Primer resultado reproducible

La primera ejecución incluyó por error contadores de metadata además de las
28 features; ese reporte se descarta. Tras corregir el selector para leer
exclusivamente `configs/features/multilayer-v2.json`, el resultado fue: 44
filas de train, 15 de validation, 16 normales de test y 5 anomalías; 1/5
anomalías detectadas, 2/16 normales de test marcadas, ROC-AUC 0.5375 y
average precision 0.2933. La matriz de confusión fue `[[14,2],[4,1]]`.

Este resultado no valida todavía el detector. Es un diagnóstico de que las
tres anomalías controladas actuales se solapan con la normalidad capturada o
son demasiado pocas para separar estadísticamente. Antes de afirmar
desempeño se requiere ampliar episodios anómalos independientes y revisar el
diseño de señales/etiquetas, sin reutilizar `test` para ajustar el modelo.

También se ejecutó una variante que promedia las ventanas por episodio antes
de ajustar el modelo (30 episodios train, 10 validation, 10 test y 12
anómalos). Detectó 0/12 episodios anómalos, marcó 1/10 episodios normales y
obtuvo ROC-AUC 0.5417/AP 0.5506. Se conserva como análisis de sensibilidad; no
se selecciona el método por producir una métrica más conveniente.
