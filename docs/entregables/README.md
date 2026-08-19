# Entregables académicos

Documentos preparados para la sustentación y la evaluación de la tesis. A diferencia del resto de `docs/` —que registra la evidencia fase por fase a medida que se produjo— esta carpeta contiene documentos **de cara al evaluador**, construidos sobre esa evidencia y sin repetirla.

## Índice

| # | Documento | Estado | Contenido |
|---|---|---|---|
| 01 | [Informe de evaluación crítica](01-informe-evaluacion-critica.md) | **Entregado** | Autoevaluación crítica de los resultados bajo criterios de validez, confiabilidad y evaluación técnica. Cubre dataset, 28 features, modelo OCSVM, métricas, pruebas con tráfico normal y anómalo, funcionamiento en tiempo real y mecanismo de bloqueo. Diferencia lo validado, lo pendiente y el trabajo futuro, y propone una priorización realista |
| 02 | Manual de implementación técnica | Pendiente | Instalación reproducible del sistema completo desde cero |
| 03 | Actualización del PPI | Pendiente | Documento del proyecto, actualizado al estado final |

## Sobre el documento 01

Fusiona deliberadamente los dos encargos recibidos, porque analizados son el mismo entregable: uno aporta el título formal y el formato académico (breve, crítico, diferenciando validado / pendiente / futuro), y el otro el alcance técnico obligatorio y los criterios de evaluación. Separarlos habría producido dos documentos casi idénticos.

**Aporte propio del informe.** Además de evaluar lo existente, calcula **intervalos de confianza de Wilson al 95 %** sobre las proporciones ya medidas —una magnitud que el trabajo original nunca computó—. Esto no repite ningún experimento: es aritmética sobre cifras existentes, y revela dos hechos que las estimaciones puntuales ocultaban:

- La detección del 50 % en `ANOM-AUTH-FAIL-50` tiene un intervalo de 18,8 % – 81,2 % con n = 6: **no sostiene ninguna conclusión**.
- La diferencia entre el FPR offline (4,71 %) y el operativo (23–26 %) **no se solapa**, luego no se explica por azar muestral.

## Figuras

Generadas desde los artefactos reales, sin dependencias externas, mediante `scripts/entregables/generar_figuras_informe.py`:

```bash
python3 scripts/entregables/generar_figuras_informe.py
```

El script escribe los tres SVG de `figuras/` e imprime la tabla completa de intervalos de confianza citada en el informe, de modo que cualquier cifra pueda reproducirse y verificarse.

| Figura | Muestra |
|---|---|
| `fig1-fpr-offline-vs-operativo.svg` | El hallazgo central: el FPR medido offline no se sostiene en operación |
| `fig2-deteccion-por-familia.svg` | Detección por familia, OCSVM frente a Isolation Forest, con los puntos ciegos |
| `fig3-scores-trafico-pesado.svg` | Los cuatro scores reales de una transferencia legítima frente al umbral |
