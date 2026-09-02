# Informe de resultados y evaluación crítica de la tesis: Detección temprana de comportamientos anómalos en redes de datos mediante modelos predictivos y un mecanismo de control inline

| | |
|---|---|
| **Estudiante** | Rubén Mark Salazar Tocas |
| **Asesores** | Ing. Nemias Saboya Ríos · Ing. Fernando Manuel Asin Gómez |
| **Institución** | Universidad Peruana Unión |
| **Fecha** | 19 de agosto de 2026 |
| **Estructura** | Parte I: resultados obtenidos · Parte II: evaluación crítica de esos resultados |

> **Entregable de la Sesión 01.** Este documento es el informe de resultados y evaluación crítica solicitado para esa sesión; el plan prospectivo de validación corresponde a la **Sesión 02** y está en [`07-plan-de-validacion/plan-de-validacion-de-resultados.md`](../07-plan-de-validacion/plan-de-validacion-de-resultados.md).

**Trazabilidad.** Todas las cifras salen de artefactos verificables: `artifacts/model/manifest.json`, `artifacts/model/ocsvm_scaled.joblib`, `artifacts/dataset/*.csv` y `results/f6/f6_resultados.jsonl`. Las gráficas y los intervalos de confianza se regeneran con:

```bash
.venv/bin/python3 scripts/entregables/generar_graficas.py
```

**Verificación de integridad.** Al re-puntuar los conjuntos con el modelo congelado, este informe reproduce **exactamente** las métricas del manifiesto (13/276 falsos positivos y 158/179 detecciones), lo que confirma de forma independiente que el modelo publicado reproduce sus propios resultados.

> **FPR operativo (fuente primaria: [`02-resultados-f6.md`](../../fase07-validacion-final/02-resultados-f6.md)).** El pase 1 registró **25,81 % (16/62)**, IC 95 % [16,6–37,9]; el pase 2 (lag-aware) registró **22,97 % (17/74)**, IC 95 % [14,9–33,7]. El rango entre ambos pases es **22,97–25,81 %**; no se trata de un promedio.

---
---

# PARTE I — RESULTADOS

## 1. Qué se construyó

Sistema de detección de anomalías de red desplegado sobre un laboratorio virtualizado de 5 máquinas, con el sensor actuando como router inline entre LAN y DMZ:

![Topología del laboratorio](../graficas/E1-topologia.png)

| Componente | Estado |
|---|---|
| Dataset multicapa (28 features, L3/L4/L7) | Consolidado y auditado |
| Modelo OCSVM | Congelado, umbral calibrado |
| Motor de decisión en tiempo real | Desplegado y activo (VM02) |
| Bloqueo inline (nftables) | Activo, expiración 120 s |
| Panel de observación | Activo, solo lectura |

## 2. Dataset y variables

![Composición del dataset](../graficas/D1-composicion-dataset.png)

| Magnitud | Valor |
|---|---|
| Ventanas normales / episodios | 1 373 / 220 |
| Partición (entrenamiento / validación / prueba) | 824 / 273 / 276 ventanas · 132 / 44 / 44 episodios |
| Ventanas de ataque / episodios | 179 / 132 |
| Procedencia de los ataques | 161 desde Kali real · 18 heredadas de otro mecanismo |
| Features por capa | L3 = 9 · L4 = 8 · L7 = 11 (total 28) |
| Integridad | `gates.pass = true`, `no_episode_split = true`, SHA-256 registrado |

## 3. Desempeño del modelo congelado

`Pipeline(StandardScaler → OneClassSVM(rbf, ν=0.05))`, umbral `score < 1,8126` fijado por cuantil α = 0,05 sobre validación.

### 3.1 Capacidad discriminante

![Curva ROC](../graficas/A1-curva-roc.png)

**ROC-AUC = 0,974.** Métrica calculada en este informe: el trabajo original nunca la computó. Indica que el modelo ordena correctamente casi cualquier par (benigno, anómalo), independientemente del umbral elegido.

### 3.2 Dónde está el umbral y por qué hay errores

![Distribución de scores](../graficas/A2-distribucion-scores.png)

Las dos poblaciones se separan bien en conjunto, pero **se solapan en la franja 1,6 – 2,0**, justo donde cae el umbral. Ese solapamiento es el origen material de los falsos positivos y negativos.

![Barrido de umbral](../graficas/A4-barrido-umbral.png)

### 3.3 Resultado en el punto de operación

![Matriz de confusión](../graficas/A3-matriz-confusion.png)

| Métrica | Valor | k / n | IC 95 % (Wilson) |
|---|---|---|---|
| **ROC-AUC** | **0,974** | — | *(calculada aquí)* |
| Detección global (recall) | 88,3 % | 158/179 | 82,7 % – 92,2 % |
| Detección Kali-real | 88,8 % | 143/161 | 83,0 % – 92,8 % |
| Detección heredada | 83,3 % | 15/18 | 60,8 % – 94,2 % |
| Detección por episodio | 90,2 % | 119/132 | 83,9 % – 94,2 % |
| Especificidad | 95,3 % | 263/276 | — |
| Falsos positivos (FPR) | 4,71 % | 13/276 | 2,8 % – 7,9 % |
| F1 | 0,903 | — | *(tasa base artificial, ver §8)* |

## 4. Comparación de modelos

![Comparación de los 7 modelos](../graficas/B1-comparacion-modelos.png)

Siete configuraciones de cuatro familias de algoritmos, evaluadas en un solo paso bloqueado. Todas con FPR comparable (3,6 – 5,1 %); **la diferencia real está en la detección**.

![Detección por familia y modelo](../graficas/B2-heatmap-familias.png)

| Modelo | Umbral | FPR test | Detección | Kali-real |
|---|---|---|---|---|
| **`ocsvm_scaled`** *(congelado)* | **1,8126** | **4,71 %** | **88,3 %** | **88,8 %** |
| `if_uniform` | −0,5543 | 5,07 % | 57,5 % | 55,9 % |
| `if_exact_collapsed` | −0,5543 | 5,07 % | 57,5 % | 55,9 % |
| `if_primary_weighted` *(rol registrado: primary)* | −0,5061 | 4,35 % | 54,2 % | 52,8 % |
| `if_scaled_weighted` | −0,5042 | 4,35 % | 54,2 % | 52,8 % |
| `lof_scaled` | −2,9405 | 3,62 % | 43,0 % | 40,4 % |
| `elliptic_envelope_scaled` | −4,0 × 10⁹ | 5,07 % | 27,4 % | 26,7 % |

**Hallazgo:** Isolation Forest tiene **dos puntos ciegos totales** —0/31 en SYN-RATE y 0/40 en UDP-PROBE, 71 ventanas sin detectar ninguna— que OCSVM resuelve. A cambio, OCSVM pierde en las familias de autenticación.

## 5. Resultados en operación real (validación F6)

Sistema desplegado, motor y enforcement activos: 2 pases de 29 corridas + 2 pruebas de aislamiento.

![Lead-time de detección](../graficas/C2-lead-time.png)

| Métrica operativa | Resultado |
|---|---|
| Lead-time de detección y bloqueo | **mediana 8,0 s** (rango 6,1 – 13,7 s) |
| Disponibilidad de servicios | **Cero caídas registradas** en 58 corridas · 55 con verificación explícita |
| Pérdida de paquetes en captura | **0 drops** |

![FPR offline frente a operativo](../graficas/C1-fpr-offline-vs-operativo.png)

![Scores de tráfico legítimo pesado](../graficas/C3-scores-trafico-pesado.png)

**Resultado negativo, reportado como tal:** el FPR benigno **no se sostiene** en operación. En aislamiento, una transferencia legítima `iperf-tcp 200M` produjo una ventana de score 1,689 que cruzó el umbral y **bloqueó a un cliente legítimo durante 120 s**.

El margen es además extremadamente estrecho: otra ventana de la misma transferencia legítima obtuvo 1,814 y **se permitió por 0,0014 puntos de score**. No es que el sistema distinga bien el tráfico pesado y falle en un caso aislado: es que las cuatro ventanas caen dentro del margen de decisión, y cuál se bloquea depende de fluctuaciones mínimas.

> **[ESPACIO PARA CAPTURA 1 — Panel operativo]**
> Insertar aquí una captura de `http://127.0.0.1:8788/` mostrando salud de servicios, distribución de scores y decisiones recientes.

> **[ESPACIO PARA CAPTURA 2 — Bloqueo en vivo]**
> Insertar aquí una captura de la sección "IPs bloqueadas ahora" durante un ataque, o la salida de `sudo ppi-enforce list`.

---
---

# PARTE II — EVALUACIÓN CRÍTICA

Criterios aplicados: **validez** (¿las conclusiones se siguen de la evidencia?), **confiabilidad** (¿son reproducibles?) y **evaluación técnica** (¿funciona en las condiciones previstas?).

## 6. Veredicto por criterio

| Criterio | Veredicto | Razón |
|---|---|---|
| Validez interna | **Parcial** | Controles anti-fuga reales y verificados, pero el modelo final se eligió observando el conjunto de prueba |
| Validez externa | **Insuficiente** | Refutada por el propio proyecto sobre tráfico legítimo pesado |
| Validez de constructo | **No demostrada** | La ablación exigida por el jurado nunca se ejecutó |
| Confiabilidad | **Alta** | Hashes, particiones disjuntas por episodio, causalidad probada con test unitario |
| Evaluación técnica | **Alta** | Funciona, se midió en despliegue real, sus fallos se corrigieron con evidencia |

> **Reproducibilidad no es replicabilidad.** Este proyecto tiene la primera
> —cualquiera descarga el repositorio y obtiene el mismo resultado— y **no tiene
> la segunda**, que exige datos nuevos. Es la limitación `D6` y se cierra con la
> jornada del 24 de octubre. El desglose por los tres ejes de la Sesión 02 está
> en [`02-validacion-y-confiabilidad/`](../02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md).

## 6 bis. Evaluación contra ISO/IEC 25010

La Sesión 01 nombra este estándar en su propósito y lo presenta como **marco de
referencia obligado** al evaluar sistemas de software. Sus ocho características,
contrastadas contra la evidencia de este proyecto:

| Característica | Evidencia | Estado |
|---|---|---|
| **Adecuación funcional** | Detecta y bloquea: 88,8 % de detección sobre ataques genuinos [83,0 – 92,8] | **Con evidencia** |
| **Eficiencia de desempeño** | Bloqueo en mediana de 8,0 s (rango 6,1–13,7). Limitación medida: el motor se atrasa hasta 161 s bajo carga sostenida | **Con evidencia, con límite declarado** |
| **Confiabilidad** | Cero caídas en 58 corridas; determinismo verificado —10 ajustes repetidos dieron el mismo SHA-256— | **Con evidencia** |
| **Seguridad** | Trazabilidad por SHA-256 de datos, modelos y calibrador; enforcement sin SSH entre VM | **Con evidencia** |
| **Usabilidad** | Panel desplegado, pero **ningún instrumento aplicado**. Es `D-18` | **Sin evidencia** |
| **Compatibilidad** | No evaluada: no se probó coexistencia con otros sistemas de detección | **Sin evidencia** |
| **Mantenibilidad** | Código modular y versionado, con pruebas; **no se midió** con métricas del estándar | **Sin evidencia formal** |
| **Portabilidad** | Desplegado en una sola configuración de laboratorio | **Sin evidencia** |

**Cuatro de ocho características tienen evidencia; cuatro no.** Declararlo así es
más defendible que afirmar «calidad validada»: el estándar sirve para saber qué
se midió y qué no, no para decorar el informe.

> Los otros marcos que nombra el propósito de la sesión se sitúan igual: **SUS**
> está preparado y pendiente de aplicar (`D-18`); **Delphi** y el juicio experto
> se contemplan para la validación de pertinencia; **CASP y JBI** son
> instrumentos de evaluación de literatura clínica y **no aplican** a un producto
> de ingeniería como este.

## 7. Lo que está validado con evidencia

| Aspecto | Evidencia |
|---|---|
| Particiones disjuntas por episodio | `manifest.audit_gates.no_episode_split = true` |
| Umbral fijado solo en validación, evaluación bloqueada de un paso | α = 0,05, k = 13, desigualdad estricta |
| Causalidad temporal (sin información futura) | Test unitario: un HTTP 500 posterior no altera una ventana cerrada |
| Reproducibilidad de artefactos | SHA-256 de CSV, calibrador y modelos; git limpio verificado |
| El modelo reproduce sus propias métricas | Re-puntuación en este informe: 13/276 y 158/179 exactos |
| Detección de 5 familias de ataque reales | 88,8 % Kali-real [83,0 – 92,8] |
| Detección y bloqueo en tiempo real | Mediana 8,0 s; sin caídas de servicio registradas |
| Corrección de 3 fallos reales de producción | Bucle de re-bloqueo, falso positivo por desincronización, replay de backlog |
| Detección honesta de una fuga propia | Resultado contaminado marcado *"no debe citarse"* |
| Trazabilidad | 330 commits · 181 documentos de campaña · 162 revisiones adversariales |

## 8. Debilidades detectadas

### 8.1 Metodológicas

**D1 · La selección del modelo se hizo sobre el conjunto de prueba.** *(severidad alta)*
El propio `manifest.json` registra:

> `model_selection_policy`: *"if_primary_weighted es la conclusion principal; LOF/OCSVM (…) no lo reemplazan por ganar una metrica posterior en test o evaluation_only."*

y asigna a `ocsvm_scaled` el rol `sensitivity_or_comparator`. **El modelo congelado es el comparador que esa política prohibía promover.** Consecuencia: el 88,3 % (y el AUC de 0,974) son el máximo sobre 7 candidatos evaluados en los mismos conjuntos, sin datos reservados que permitan una estimación insesgada.
→ *Solución:* declararlo explícitamente. La corrección completa exige `PM-multilayer-v2-v2` con evaluación nueva (semanas).

> **🟡 Parcialmente atendida.** La declaración ya está incorporada en la [model card](../../dataset/MODEL_CARD_OCSVM.md) —sección 3, antes de cualquier métrica— y en el PPI v2. Lo que sigue abierto es la corrección de fondo: un protocolo nuevo con evaluación reservada.
>
> **Matiz reforzado con estadística:** las **seis comparaciones por pares del OCSVM contra los otros modelos son significativas** con McNemar exacto tras corrección de Holm. Los intervalos de Wilson por ventanas se reportan como descriptivos porque las ventanas comparten episodios e historia; no se usan como prueba independiente de diferencia. Ver [`08-significancia-entre-modelos.md`](../../fase04-modelado/08-significancia-entre-modelos.md).

**D2 · No se calculó ninguna medida de incertidumbre.** *(severidad alta)*
No había intervalos de confianza, errores estándar ni pruebas de significancia. Los de este informe son un aporte propio, y revelan lo que las cifras puntuales ocultaban:

| Cifra reportada | IC 95 % real | Lectura |
|---|---|---|
| "50 % en AUTH-FAIL" (3/6) | **18,8 % – 81,2 %** | 62,5 puntos de ancho: **no sostiene ninguna conclusión** |
| "55,2 % en PASSWORD-SPRAY" (16/29) | 37,5 % – 71,6 % | Muy amplio; conclusión débil |
| 88,3 % detección global (158/179) | 82,7 % – 92,2 % | Sólido |
| 4,71 % FPR (13/276) | 2,8 % – 7,9 % | Sólido, pero ver D5 |

→ *Solución:* incorporarlos (hecho aquí, coste: minutos).

> **✅ Resuelta.** Los intervalos de Wilson se incorporaron a toda proporción del proyecto. Se añadió además lo que faltaba: **prueba de significancia entre modelos** con McNemar exacto y corrección de Holm-Bonferroni sobre las 21 comparaciones por pares.
>
> Hallazgo derivado que conviene citar: **ninguna diferencia de falso positivo entre los siete modelos alcanza significancia** (p mínimo = 0,52). Afirmar que un modelo comete menos falsos positivos que otro **no está respaldado por estos datos**.

**D3 · La ablación exigida por el jurado nunca se ejecutó.** *(severidad alta)*
El requisito pedía comparar cuatro configuraciones (Base 14 · +L3 · +L3+L4 · Multicapa) y retirar cada grupo de capa por separado. Sigue marcada *"Planificado"*; no existe script ni artefacto. **Ninguna de las 28 features ha demostrado empíricamente que se gana su lugar.** Además hay 6 pares con |r| > 0,8 (redundancia ya medida).
→ *Solución:* ejecutarla — 1-2 días, sin campañas nuevas.

> **✅ Resuelta.** Ejecutada en [`07-ablacion-multicapa.md`](../../fase04-modelado/07-ablacion-multicapa.md), con la configuración completa reproduciendo el modelo congelado **bit a bit** antes de comparar nada.
>
> | Configuración | Vars | FPR | Detección Kali |
> |---|---:|---:|---:|
> | `base-14` | 14 | 2,90 % | 66,5 % |
> | `base+L3+L4` | 20 | 2,90 % | **89,4 %** |
> | `multicapa-28` | 28 | 4,71 % | 88,8 % |
> | `sin-L4` | 20 | 5,80 % | 42,2 % |
>
> **La expansión multicapa está justificada** (66,5 % → 88,8 %, p < 0,001). **Pero «hacen falta las 28» no se sostiene:** las 8 variables L7 nuevas no aportan detección medible (p = 1,000) y cuestan 5 falsos positivos. No se promueve la configuración de 20 porque hacerlo repetiría exactamente el error de D1.
>
> **La capa 4 es la que sostiene el sistema:** retirarla hunde la detección a 42,2 % sin ganar una sola ventana.

**D4 · El análisis de sensibilidad no cubre el modelo elegido.** *(severidad media)*
Las 10 semillas, la ponderación por episodio y el colapso de duplicados se aplicaron **solo a Isolation Forest** (`manifest.stability` no contiene `ocsvm_scaled`). OCSVM además se ajustó **sin ponderación**, pese al desbalance documentado: *"5/132 episodios (3,8 %) concentran 261/824 filas train (31,7 %)"*.
→ *Solución:* estabilidad por submuestreo — horas.

> **✅ Resuelta.** Se atacó por dos vías, en [`09-validacion-cruzada-y-estabilidad.md`](../../fase04-modelado/09-validacion-cruzada-y-estabilidad.md):
>
> - **Validación cruzada agrupada por episodio**, 5 pliegues. La detección media (85,5 %) **cae dentro** del intervalo de Wilson de la evaluación de un solo paso [82,7 – 92,2]: el resultado no depende de la partición concreta que se eligió.
> - **Remuestreo del umbral por episodio**, B = 1 000. Coeficiente de variación **4,10 %**, por debajo del 5 % declarado de antemano, con banda **[1,6496 – 1,8132]** — información que el manifiesto no daba.
>
> Sobre las semillas: el OCSVM **no admite `random_state` porque su ajuste no tiene componente aleatoria**. Verificado con 10 ajustes repetidos que producen el mismo SHA-256 y el mismo umbral ([`10-protocolo-determinismo-y-semillas.md`](../../fase04-modelado/10-protocolo-determinismo-y-semillas.md)). Lo que sigue abierto es la **ponderación por episodio**, que no se aplicó.

### 8.2 De validez externa

**D5 · El FPR offline no se sostiene en operación.** *(severidad alta — la más importante)*

| Condición | FPR | IC 95 % |
|---|---|---|
| Offline (test) | 4,71 % | 2,8 % – 7,9 % |
| Operativo F6 pase 1 | 25,8 % | 16,6 % – 37,9 % |
| Operativo F6 pase 2 | **22,97 %** (17/74) | 14,9 % – 33,7 % |

Los intervalos se presentan como resumen descriptivo de ventanas correlacionadas; no se interpretan como evidencia inferencial independiente. El contraste se reprodujo en aislamiento — una transferencia legítima de 200 Mbit/s bloqueó a un cliente durante 120 s — y contradice la observación del jurado que motivó todo el esfuerzo del dataset.
→ *Solución:* recalibrar incluyendo tráfico pesado (1-2 semanas). Mientras tanto, **declararlo**: un FPR medido y admitido es más defendible que uno refutado por la evidencia propia.

**D6 · La división es por índice de repetición, no por sesión independiente.** *(severidad alta)*
R01–R03 → entrenamiento, R04 → validación, R05 → prueba. **Los 44 perfiles aparecen en las tres particiones**: se mide repetibilidad del escenario, no generalización. No existe la **jornada de holdout temporal externa** que el jurado exigió. Explica en buena parte D5.
→ *Solución:* capturar una jornada nueva como holdout externo — días.

**D7 · Cobertura de escenarios incompleta.** *(severidad media)*
De los 14 escenarios normales exigidos faltan **SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones**, y no hay captura multi-SO.
→ *Solución:* declarar como límite de alcance salvo exigencia expresa.

### 8.3 De constructo y documentación

**D8 · Sin diccionario de fórmulas para las features 15–28.** *(severidad media)* — El jurado pidió *"diccionario, fórmulas, unidades y ventanas"*. Solo existía para las 14 de v1.

> **✅ Resuelta.** Publicado el [diccionario científico de las 28 variables](../../fase02-features-multicapa/03-diccionario-multicapa-v2.md), con diez campos por variable: fórmula, tipo y rango teórico, fuente exacta, denominador, comportamiento con denominador cero, rango observado, observabilidad, coste en línea y estado. **Generado desde el extractor congelado**, y el script aborta si una variable del contrato no aparece en él.

**D9 · Una feature es constante y no observable.** *(severidad media)* — `tls_handshake_failure_ratio_60s` vale 0,0 en todo el dataset; se demostró que Suricata no puede producir el evento intermedio.

> **✅ Resuelta.** Declarada **no observable**; el corpus se reporta como **27 variables efectivas de 28 definidas**. La ablación lo confirmó numéricamente: la configuración sin esa variable da resultados **idénticos** al contrato completo, mismo umbral incluido.

**D10 · Los gates no cubren duplicados ni constantes.** *(severidad baja)* — `gates.pass = true` convivía con 22 vectores duplicados exactos y una feature constante.

> **✅ Resuelta.** Cuatro gates nuevos con prueba positiva y negativa: `constants_declared`, `no_duplicate_crossing_label`, `no_duplicate_crossing_partition` y `duplicates_within_tolerance`. Los tres primeros son de **tolerancia cero** — un duplicado que cruce etiqueta o partición indica fuga y falla siempre—; el presupuesto del 2 % en duplicados se declara como valor elegido, no derivado de los datos.

### 8.4 Del mecanismo de control

**D11 · El costo de un falso positivo es alto y está demostrado** — un FP corta el servicio a un cliente legítimo 120 s. Combinado con D5, es el principal riesgo operativo.
**D12 · Bloqueo por IP** — inefectivo ante rotación de IP; limitación estructural, declarable.
**D13 · Sin nivel intermedio de respuesta** (tipo limitación de tasa) — exigiría un segundo umbral calibrado.
**D14 · El heurístico de fuerza bruta no está calibrado estadísticamente** — sus umbrales (≥5 peticiones, ≥80 % de 401/403) son criterio razonado; está declarado en el código.

## 9. ¿Los resultados cumplen el objetivo?

**Componente 1 — Detectar y bloquear en tiempo real: CUMPLIDO.**
Detección del 88,8 % [83,0–92,8] sobre ataques genuinos, ROC-AUC 0,974, bloqueo en mediana de 8 s y sin caídas de servicio registradas.

**Componente 2 — Sin penalizar el tráfico legítimo: NO DEMOSTRADO.**
El FPR operativo fue **25,81 % (16/62) en el pase 1** y **22,97 % (17/74) en el pase 2**; el rango aproximado 23–26 % resume ambos pases. Además, un falso positivo se reprodujo en aislamiento. El sistema **no es apto para operación desatendida** en redes con transferencias pesadas legítimas.

**Veredicto.** El proyecto cumple su objetivo **como demostración de viabilidad técnica**, no como sistema de producción. Esa distinción no debilita la tesis si se declara, porque el criterio de finalización adoptado no fue *"demostrar que el sistema siempre acierta"* sino *"delimitar con evidencia qué detecta, bajo qué condiciones funciona y qué limitaciones conserva"*.

Lo que sí compromete la calidad académica no es el falso positivo —está medido y es defendible— sino **la ablación ausente y la falta de cuantificación de incertidumbre**, porque afectan a la validez de las conclusiones, no al desempeño del artefacto.

## 10. Estado de la remediación

*Actualizado al 26 de agosto de 2026.*

### 10.1 Ya resuelto, con evidencia publicada

Ninguna de estas acciones requirió capturar datos nuevos ni reentrenar el modelo congelado.

| Debilidad | Qué se hizo | Evidencia |
|---|---|---|
| **D2** Sin medidas de incertidumbre | Intervalos de Wilson en toda proporción **y** McNemar exacto con corrección de Holm sobre 21 comparaciones | [`08-significancia`](../../fase04-modelado/08-significancia-entre-modelos.md) |
| **D3** Ablación nunca ejecutada | Ejecutada, con la configuración completa reproduciendo el modelo congelado bit a bit | [`07-ablacion`](../../fase04-modelado/07-ablacion-multicapa.md) |
| **D8** Sin diccionario de las variables 15–28 | Publicado, generado desde el extractor congelado | [`03-diccionario`](../../fase02-features-multicapa/03-diccionario-multicapa-v2.md) |
| **D9** Variable constante no declarada | Declarada no observable: **27 efectivas de 28** | ídem |
| **D10** Gates sin duplicados ni constantes | Cuatro gates nuevos, con prueba positiva y negativa | [`181-correccion`](../../fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md) |
| **D1** Selección posterior | **Declarada** en la model card antes de cualquier métrica y en el PPI v2 | [`MODEL_CARD`](../../dataset/MODEL_CARD_OCSVM.md) |
| — Datos y código no reproducibles desde un clon | Dataset, manifiesto y **los 7 modelos candidatos** publicados con checksums y licencias MIT + CC BY 4.0 | [`SHA256SUMS`](../../dataset/SHA256SUMS) |
| — Sin documentación canónica de los datos | *Datasheet* de 11 secciones, *model card* y *system card* | [`docs/dataset/`](../../dataset/README.md) |

### 10.2 Lo que la ablación cambió en las conclusiones

Ejecutar D3 no solo cerró un requisito: **modificó lo que este informe puede afirmar.**

- La expansión multicapa **queda justificada con significancia**: 66,5 % → 88,8 % de detección sobre ataques genuinos, p < 0,001.
- Pero **«hacen falta las 28 variables» no se sostiene**: una configuración de 20 iguala la detección (p = 1,000) con **8 falsos positivos en vez de 13**. Las 8 variables L7 nuevas no aportan detección medible.
- **La capa 4 es la que sostiene el sistema**: retirarla hunde la detección a 42,2 % sin ganar una sola ventana.
- Que L7 no aporte *al vector del modelo* no significa que sobre: el motor la usa en un detector heurístico que en F6 **detectó un ataque real por sí solo**.

> **No se promueve la configuración de 20 variables.** Hacerlo repetiría exactamente el error de D1: elegir por ganar una comparación sobre el mismo conjunto de prueba. Adoptarla exige un protocolo nuevo con evaluación reservada.

### 10.3 Lo que sigue abierto

| Bloque | Acción | Resuelve |
|---|---|---|
| **Horas** | Declarar la selección posterior también en el documento de tesis | D1 |
| **Días** | **Validación con usuarios: SUS con 5–8 evaluadores** | pertinencia |
| **Días** | Sesión de juicio experto con 3 evaluadores | pertinencia |
| **Días** | Escenarios legítimos faltantes | D7 |
| **Semanas** | Jornada nueva como holdout temporal externo | D6 |
| **Semanas** | **Recalibrar incluyendo tráfico pesado y repetir F6** | D5 |

> **El bloque de horas está agotado: la inferencia estadística quedó cerrada.** Lo que queda depende de personas o de tiempo de laboratorio.
>
> **El SUS es el único cero absoluto**: cero en la ficha de auditoría, cero en el eje de pertinencia del plan de validación y `D-18` en el registro. Una sola sesión de dos horas lo convierte en evidencia y eleva la ficha de **82,4 % a 88,2 %**.

**D5 sigue siendo la debilidad principal del sistema** y no se resuelve escribiendo: exige recalibrar con tráfico legítimo pesado como normalidad y repetir la validación operativa.

## 10.4 Cronograma: cuándo se aborda cada pendiente

*Propuesta del equipo con fecha del 2 de septiembre de 2026, pendiente del visto
bueno de los asesores.* El docente pide no solo qué falta, sino **cómo y en qué
plazo**. Esto es lo que queda y cuándo se hace.

### La fecha que ordena todo el cronograma

**El 30 de septiembre de 2026.** IJIES sube su APC de **USD 300 a USD 400 el 1 de
octubre**, y el cargo lo asume la Universidad Peruana Unión: enviar antes de esa
fecha ahorra **USD 100 de presupuesto institucional**. Con la mediana medida de
la revista —41 días hasta la primera decisión y 158 hasta publicar— un envío el
**28 de septiembre** proyecta primera decisión hacia el **8 de noviembre de 2026**
y publicación hacia el **5 de marzo de 2027**.

> **De ahí sale el orden del cronograma:** todo lo que alimenta la sección de
> resultados del artículo se cierra **antes del 28 de septiembre**; lo que la
> mejora pero no la condiciona va después.

### Pendientes, responsable y fecha

| Fecha | Pendiente | Cómo se aborda | Responsable | Estado |
|---|---|---|---|---|
| **vie 4 sep 2026** | Declarar la selección posterior en el documento de tesis | Párrafo explícito en metodología, enlazado a la *model card* que ya lo declara | Salazar | PLANIFICADA |
| **mié 9 sep 2026** | **Validación con usuarios (SUS)** — `D-18` | Sesión de 2 h con 5–8 evaluadores; instrumento y hoja de cálculo listos en [`08-validacion-usuarios/`](../08-validacion-usuarios/) | Salazar · Sauñe | PLANIFICADA · **prioridad 1** |
| **sáb 19 sep 2026** | Escenarios legítimos faltantes — `D7` | Campaña F1 adicional: SSH, SCP/SFTP, backup y actualizaciones | Sauñe | PLANIFICADA |
| **mié 23 sep 2026** | Juicio experto (3 evaluadores) | Rúbrica de pertinencia sobre el producto desplegado, ya con los resultados del SUS a la vista | Salazar · asesores | PLANIFICADA |
| **lun 28 sep 2026** | **Envío del artículo a IJIES** | Manuscrito en `IJIES_Format.docx`, 8 a 10 páginas | Salazar · Sauñe | PLANIFICADA · **hito** |
| **sáb 10 oct 2026** | **Recalibrar con tráfico pesado y repetir F6** — `D5` | Reentrenar incluyendo `iperf-tcp 200M` como normalidad y repetir las 29 corridas | Salazar | PLANIFICADA · **debilidad principal** |
| **sáb 24 oct 2026** | *Holdout* temporal externo — `D6` | Campaña completa en fecha distinta, sin reutilizar episodios | Salazar · Sauñe | PLANIFICADA |

### Por qué el SUS va primero

Es **el único cero absoluto** que queda: cero en la ficha de auditoría, cero en
el eje de pertinencia del plan de validación y `D-18` en el registro de
debilidades. Cuesta **dos horas** y sube la ficha de **82,4 % a 88,2 %**. Ningún
otro pendiente tiene esa relación entre esfuerzo y resultado, y es además el
único que depende de conseguir personas y no de tiempo de laboratorio: por eso
se agenda lo antes posible, no lo más cómodo.

El juicio experto va **después** del SUS a propósito: los evaluadores expertos
juzgan mejor teniendo delante lo que dijeron los usuarios.

### Qué pasa si algo no llega

**El artículo no espera a los pendientes 4, 5 y 6.** La sección de resultados se
escribe con lo que ya está validado y bloqueado —el modelo congelado, la
evaluación de un solo paso y las 58 corridas de F6— porque **ese resultado ya
está completo y no va a cambiar**. Los tres pendientes mejoran la evidencia; no
la sustituyen. Si el 5 se retrasa, el artículo sale igual con la limitación
declarada, que es como debe salir de todos modos.

**Lo que sí bloquearía la sustentación es el pendiente 2.** Sin la sesión SUS, el
eje de pertinencia se queda en cero y la ficha de auditoría no pasa de 82,4 %.

### La fecha de sustentación

**No la fija el equipo**, sino el cronograma del programa. Lo que este informe sí
puede afirmar es que **ningún pendiente de esta lista la condiciona más allá del
24 de octubre de 2026**, y que el artículo puede enviarse antes de esa fecha sin
depender de ninguno de ellos. Si la sustentación cae antes de marzo de 2027 —lo
previsible—, el artículo estará **enviado y en revisión**, no publicado: es la
situación normal y así debe declararse ante el jurado.

## 11. Limitaciones de este propio informe

- No se auditó el código del extractor línea por línea; la confianza en las 28 features descansa en los tests unitarios existentes.
- **No se evaluó el sistema como objetivo de ataque** (evasión del detector, o abuso del bloqueo para provocar denegación de servicio contra terceros suplantando IP). Omisión relevante; debería ser trabajo futuro.
- El acceso administrativo permanente sin restricción vigente durante el desarrollo contradice la evidencia de aislamiento de fases previas. **Se recomienda revertirlo antes de la defensa.**
- El ROC-AUC de 0,974 calculado aquí se apoya en los mismos conjuntos usados para seleccionar el modelo, por lo que hereda el sesgo optimista de D1.

## 12. Conclusión

El proyecto entrega un sistema real, desplegado, instrumentado y medido, con trazabilidad y honestidad experimental superiores a lo habitual. Sus dos deficiencias son de naturaleza distinta: la **falta de validez externa sobre tráfico pesado** está medida y es defendible como límite conocido; la **ausencia de ablación y de cuantificación de incertidumbre** es una deficiencia del análisis, y es la más barata de corregir.

Corregidas, la tesis sostiene con solidez una afirmación acotada y verdadera:

> Se demostró la viabilidad de detectar comportamientos anómalos y ejercer control inline en tiempo real sobre una red real, con ROC-AUC de 0,974, detección del 88,8 % [83,0 – 92,8] sobre ataques genuinos y bloqueo en una mediana de 8 segundos; y se delimitó con evidencia la condición bajo la cual el sistema todavía no es apto para operación desatendida: el tráfico legítimo de alto volumen, donde el FPR operativo fue 25,81 % (16/62) en el pase 1 y 22,97 % (17/74) en el pase 2.

---

## Anexo A — Índice de gráficas

| Figura | Muestra | Fuente |
|---|---|---|
| `A1-curva-roc.png` | Capacidad discriminante (AUC 0,974) y punto de operación | Re-puntuación del `.joblib` |
| `A2-distribucion-scores.png` | Solapamiento entre benigno y anómalo en torno al umbral | Re-puntuación del `.joblib` |
| `A3-matriz-confusion.png` | Aciertos y errores en el punto de operación | Re-puntuación del `.joblib` |
| `A4-barrido-umbral.png` | Compromiso detección/falsos positivos según umbral | Re-puntuación del `.joblib` |
| `B1-comparacion-modelos.png` | Los 7 modelos: detección frente a FPR | `manifest.json` |
| `B2-heatmap-familias.png` | Detección por familia y modelo; puntos ciegos de IF | `manifest.json` |
| `C1-fpr-offline-vs-operativo.png` | El FPR offline no se sostiene en operación | `manifest.json` + F6 |
| `C2-lead-time.png` | Tiempo hasta el bloqueo por familia | `f6_resultados.jsonl` |
| `C3-scores-trafico-pesado.png` | Tráfico legítimo pesado dentro del margen del umbral | F6 |
| `D1-composicion-dataset.png` | Particiones, familias de ataque y features por capa | `manifest.json` + contrato |
| `E1-topologia.png` | Topología del laboratorio y punto de decisión | `docs/fase00-infraestructura/` |

## Anexo B — Trazabilidad

| Artefacto | Identificador |
|---|---|
| Commit del calibrado | `9467066a8d85fda8e176a6629e5f70c94c04eff0` (git limpio antes y después) |
| SHA-256 del calibrador | `81836b625887bfc84376e93334b29796573b20d990e81684d9a7ba7e38897980` |
| Modelo congelado | `artifacts/model/ocsvm_scaled.joblib` |
| Manifiesto de calibración | `artifacts/model/manifest.json` (2026-08-17) |
| Resultados de F6 | `results/f6/f6_resultados.jsonl` |
| Reproducción de gráficas e IC | `scripts/entregables/generar_graficas.py` |

## Anexo C — Evidencia documental citada

- `docs/fase03-dataset/180-consolidacion-dataset-v2-ampliado.md` — consolidación y auditoría del dataset
- `docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md` — feature no observable (D9)
- `docs/fase04-modelado/03-diagnostico-pipeline-multilayer-v2.md` — redundancia entre features y fuga detectada
- `docs/fase04-modelado/05-resultado-calibracion-multilayer-v2-v1.md` — comparación de los 7 modelos
- `docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md` — modelo congelado
- `docs/fase05-motor-tiempo-real/` — motor, enforcement y fallos de producción corregidos
- `docs/fase07-validacion-final/02-resultados-f6.md` — validación del sistema desplegado
- `docs/requisitos-jurado/README.md` — requisitos y matriz de cumplimiento
- `docs/07-mejoras-futuras/01-debilidades-y-mejoras.md` — registro vivo de debilidades
