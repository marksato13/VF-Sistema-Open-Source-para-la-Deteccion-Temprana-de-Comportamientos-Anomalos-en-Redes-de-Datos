# Entregables académicos

Documentos de cara al evaluador, construidos sobre la evidencia registrada fase por fase en el resto de `docs/`.

## Índice

| # | Documento | Estado |
|---|---|---|
| 01 | [Informe de resultados y evaluación crítica](01-informe-evaluacion-critica.md) | **Entregado** |
| 02 | Manual de implementación técnica | Pendiente |
| 03 | Actualización del PPI | Pendiente |

## Estructura del documento 01

Un solo informe con dos partes, porque los dos encargos recibidos son complementarios y no independientes:

- **Parte I — Resultados.** Qué se obtuvo, con gráficas y tablas. Descriptivo.
- **Parte II — Evaluación crítica.** Si esos resultados valen, bajo criterios de validez, confiabilidad y evaluación técnica. Analítico: dictamina, prioriza y propone.

La diferencia entre ambos géneros: los resultados son *el análisis de sangre*; la evaluación crítica es *el diagnóstico*.

## Gráficas

Las 10 figuras se generan desde artefactos reales con:

```bash
.venv/bin/python3 scripts/entregables/generar_graficas.py
```

El script **re-puntúa los conjuntos con el modelo congelado** (`ocsvm_scaled.joblib`) y verifica que reproduce exactamente el manifiesto (13/276 y 158/179) antes de dibujar nada. También imprime la tabla de intervalos de confianza de Wilson usada en el informe, de modo que cualquier cifra sea reproducible y verificable.

| Grupo | Figuras | Qué muestran |
|---|---|---|
| **A · Modelo congelado** | `A1` curva ROC · `A2` distribución de scores · `A3` matriz de confusión · `A4` barrido de umbral | Capacidad discriminante, dónde se solapan las clases y qué se gana o pierde al mover el umbral |
| **B · Comparación de modelos** | `B1` detección frente a FPR · `B2` mapa de calor por familia | Por qué se eligió OCSVM y dónde falla frente a las alternativas |
| **C · Operación real (F6)** | `C1` FPR offline vs operativo · `C2` lead-time · `C3` scores de tráfico pesado | Comportamiento del sistema desplegado, incluidos los resultados negativos |
| **D · Dataset y variables** | `D1` particiones, familias y features por capa | Composición y alcance de los datos |

## Aportes propios del informe

Además de evaluar lo existente, el informe **calcula magnitudes que el trabajo original nunca computó**:

- **ROC-AUC = 0,974** y curva completa, recall, especificidad y F1 (antes solo había FPR y detección en un único punto de operación).
- **Intervalos de confianza de Wilson 95 %** sobre todas las proporciones. Revelan, por ejemplo, que el "50 % de detección en fuerza bruta" tiene un intervalo de 18,8 % – 81,2 % con n = 6 y por tanto no sostiene ninguna conclusión.
- **Verificación independiente** de que el modelo congelado reproduce sus propias métricas al re-puntuar.

## Capturas pendientes

El informe deja dos espacios señalados para capturas que deben tomarse manualmente del panel en vivo (`http://127.0.0.1:8788/` mediante túnel SSH): el panel operativo y una IP bloqueada durante un ataque.
