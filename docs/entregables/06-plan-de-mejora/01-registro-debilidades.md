# Registro de debilidades y mitigaciones

Cada punto tiene identificador estable (`D-nn`) para poder citarlo desde la tesis, el PPI o el artículo. **Ninguna debilidad se lista sin su evidencia**: si no hay medición que la respalde, no entra en este registro.

Leyenda de impacto: 🔴 crítico · 🟠 alto · 🟡 medio · ⚪ bajo

---

## A · Inferencia estadística

Es la dimensión más débil del proyecto. No afecta al funcionamiento del sistema, sino a **qué se puede afirmar** a partir de sus resultados.

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-01** | El modelo final se eligió observando el conjunto de prueba | El manifiesto registra `ocsvm_scaled` como *comparador* y una política que prohibía promoverlo por ganar una métrica posterior. El 88,3 % es el máximo sobre 7 candidatos sin conjunto reservado | 🔴 | Horas | **Declararlo explícitamente** en tesis y PPI: la cifra es una estimación optimista. La corrección completa (`PM-multilayer-v2-v2` con evaluación nueva) es trabajo futuro |
| **D-07** | Comparación con el criterio de Youden prometida y no entregada | El protocolo la anunciaba como comparación informativa | ⚪ | Horas | Calcularla y reportarla, o retirar la promesa del protocolo |

> **Ya resuelto en esta fase:** ausencia de intervalos de confianza (se incorporaron intervalos de Wilson 95 % a todas las proporciones) y ausencia de ROC/AUC, recall, especificidad y F1 (se calcularon re-puntuando el modelo congelado: **ROC-AUC 0,974**).

---

## B · Dataset y variables

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-09** | División por índice de repetición, sin jornada de holdout externa | R01–R03 entrenamiento, R04 validación, R05 prueba: los 44 perfiles aparecen en las tres particiones. Se mide repetibilidad, no generalización | 🟠 | Días | Capturar una jornada nueva y reservarla sin participar en entrenamiento ni calibración |
| **D-10** | Seis escenarios legítimos exigidos no existen | Faltan SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones; tampoco hay captura multi-sistema-operativo | 🟡 | Días | Capturarlos, o declararlos como límite de alcance si el jurado no los exige |
| **D-25** | Tamaño muestral por debajo de la meta declarada | 1 373 ventanas frente a la meta de 2 000–3 000; ~6 ventanas por episodio, luego no son independientes | 🟡 | Semanas | Reportar el tamaño efectivo por episodio junto al de ventanas, y declarar la brecha |

> **Ya resuelto en esta fase:** `D-12` `tls_handshake_failure_ratio_60s` queda
> declarada **no observable**; el corpus se reporta como **27 variables efectivas
> de 28 definidas**. Evidencia:
> [`03-diccionario-multicapa-v2.md`](../../fase02-features-multicapa/03-diccionario-multicapa-v2.md).
>
> **Ya resuelto en esta fase:** `D-06` — protocolo de determinismo y semillas
> en [`10-protocolo-determinismo-y-semillas.md`](../../fase04-modelado/10-protocolo-determinismo-y-semillas.md).
> Declara qué componentes son estocásticos y cuáles no —el OCSVM **no admite
> semilla porque su ajuste no tiene componente aleatoria**— y lo **verifica**:
> 10 ajustes repetidos producen el mismo SHA-256 y el mismo umbral.
>
> **Ya resuelto en esta fase:** `D-15` — matriz de trazabilidad cerrada en
> [`requisitos-jurado/README.md`](../../requisitos-jurado/README.md). Ninguna
> fila queda en «Planificado»: cada requisito está cumplido con evidencia
> enlazada, cumplido con una reserva medida, o declarado pendiente con lo que
> concretamente falta. Corregidas además 7 rutas rotas por el renombrado de
> carpetas.
>
> **Ya resuelto en esta fase:** `D-03` y `D-05` —
> [`09-validacion-cruzada-y-estabilidad.md`](../../fase04-modelado/09-validacion-cruzada-y-estabilidad.md).
> Validación cruzada agrupada por episodio en 5 pliegues: la detección media
> (85,5 %) **cae dentro** del intervalo de Wilson de la evaluación de un solo
> paso, así que el resultado no depende de la partición elegida. Remuestreo del
> umbral con B = 1 000: **coeficiente de variación 4,10 %**, por debajo del 5 %
> declarado de antemano, con banda [1,6496 – 1,8132].
>
> **Ya resuelto en esta fase:** `D-04` las comparaciones entre los siete
> modelos tienen prueba de significancia —
> [`08-significancia-entre-modelos.md`](../../fase04-modelado/08-significancia-entre-modelos.md):
> McNemar exacto por pares con corrección de Holm-Bonferroni sobre 21
> comparaciones. Las 6 de `ocsvm_scaled` son significativas sin excepción;
> **ninguna diferencia de falso positivo lo es**, así que afirmar que un modelo
> comete menos falsos positivos que otro no está respaldado.
>
> **Ya resuelto en esta fase:** `D-02` la ablación por capas y la comparación
> 14 vs 28 están ejecutadas —
> [`07-ablacion-multicapa.md`](../../fase04-modelado/07-ablacion-multicapa.md).
> La expansión multicapa queda justificada con significancia (p < 0,001), pero
> **el estudio también muestra que las 8 variables L7 nuevas no aportan
> detección medible y cuestan 5 falsos positivos**. No se promueve la
> configuración de 20 variables: hacerlo repetiría la selección posterior que
> `D-01` declara.
>
> **Ya resuelto en esta fase:** `D-26` los gates no cubrían duplicados ni
> constantes — se añadieron cuatro (`constants_declared`,
> `no_duplicate_crossing_label`, `no_duplicate_crossing_partition`,
> `duplicates_within_tolerance`), con prueba positiva y negativa.
> Evidencia: [`181-correccion-catalogo-auditoria-y-gates.md`](../../fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md).

---

## C · Modelo en operación

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-11** | **El error sobre tráfico legítimo pesado es 5 veces el de laboratorio** | 4,71 % offline frente a 23–26 % operativo, con intervalos que no se solapan. Reproducido en aislamiento: una transferencia legítima de 200 Mbit/s bloqueó a un cliente 120 s | 🔴 | 1–2 semanas | Recalibrar el umbral incluyendo tráfico pesado como episodios normales y repetir la validación operativa. **Mientras tanto: declararlo** |
| **D-13** | Sin nivel intermedio de respuesta entre permitir y bloquear | Decisión de diseño documentada; exigiría un segundo umbral calibrado | 🟡 | Semanas | Declarar como trabajo futuro. No inventar el número |
| **D-21** | El bloqueo actúa solo por IP | Inefectivo ante rotación de dirección del atacante | ⚪ | Semanas | Declarar como límite estructural; fuera del alcance de la tesis |
| **D-27** | El heurístico de fuerza bruta no está calibrado estadísticamente | Sus umbrales (≥5 peticiones, ≥80 % de 401/403) responden a criterio razonado | 🟡 | Días | Declararlo en la defensa; calibrarlo exigiría datos etiquetados de fuerza bruta |
| **D-16** | Sin monitoreo de deriva del modelo | No hay procedimiento definido para detectar si el umbral pierde validez | ⚪ | Días | Documentar el procedimiento como trabajo futuro, no implementarlo |

> **Ya resuelto en esta fase:** atraso del motor bajo carga (parseo incremental: de acumular 161 s a mantenerse en 7–15 s), falso positivo por ventana sin paquetes, y reprocesamiento de backlog al reiniciar. Los tres con prueba positiva y negativa en producción.

---

## D · Validación con personas

Es la dimensión con menor puntaje en la ficha de auditoría (**55,6 %**) y la única sin ninguna evidencia.

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-18** | **Ninguna validación con usuarios reales** | No hubo pruebas con analistas de seguridad ni medición de experiencia de uso del panel | 🟠 | 3–5 días | **Instrumento, guion y script de cálculo ya preparados** en [`08-validacion-usuarios/`](../08-validacion-usuarios/README.md); falta convocar a los 5–8 evaluadores |
| **D-28** | Sin evaluación por expertos o jueces | No se aplicó Delphi, juicio experto ni instrumento equivalente | 🟡 | Días | Sesión de juicio experto con 3 evaluadores, o declarar la ausencia |

---

## E · Requisitos y documentación

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-17** | Manual de implementación técnica pendiente | Existe manual de operación, no de instalación reproducible desde cero | 🟠 | 1 día | Redactarlo; los comandos ya están probados en los despliegues documentados |
| **D-20** | **El PPI no refleja los resultados obtenidos** | Se redactó antes de que existieran; debe subirse actualizado al sistema LAM Research | 🔴 | Horas | Actualizar contra la tabla de correspondencia de `05-ppi/README.md` |

> **Ya resuelto en esta fase:** `D-14` el diccionario científico de las 28
> variables —fórmula, denominador, comportamiento con denominador cero, fuente
> exacta, rango teórico y observado, observabilidad, coste y estado— se publica
> **generado desde el extractor congelado**, no redactado a mano:
> [`03-diccionario-multicapa-v2.md`](../../fase02-features-multicapa/03-diccionario-multicapa-v2.md).
> Cierra un requisito explícito del jurado.

---

## F · Seguridad del propio sistema

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-19** | El sistema no se evaluó como objetivo de ataque | No se probó evasión del detector ni abuso del bloqueo mediante suplantación de IP para provocar denegación de servicio contra terceros | 🟡 | Días | Diseñar dos pruebas adversariales, o declarar la omisión como trabajo futuro |
| **D-22** | Acceso administrativo permanente sin restricción | Contradice la evidencia de aislamiento registrada en fases previas | 🟡 | Horas | **Revertir al modelo de sudoers estrecho antes de la defensa**, para que esa evidencia vuelva a ser cierta |

---

## G · Entregables

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-23** | La ficha de auditoría no tiene ningún gráfico | El puntaje 82,4 % y su evolución desde 62,7 % se comunican solo con tablas | ⚪ | Horas | Añadir barras de las tres dimensiones y un gráfico antes/después |
| **D-24** | El informe de validación excede la extensión pedida | ~5,2 páginas frente a las 3–4 solicitadas | ⚪ | Horas | Mover las referencias a anexo o condensar las tablas |

---

## H · Datasheet y publicación del corpus

Dimensión detectada por la evaluación de rúbrica de datasheet (61/100). La
identidad formal del dataset es la peor puntuada: **2/6**.

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|

> **Ya resuelto en esta fase:** `D-34` existen las tres tarjetas separadas —
> [datasheet](../../dataset/DATASHEET_MULTILAYER_V2.md),
> [model card](../../dataset/MODEL_CARD_OCSVM.md) y
> [system card](../../dataset/SYSTEM_CARD_MOTOR.md)—, generadas desde el
> manifiesto y las corridas de F6.
>
> **Ya resuelto en esta fase:** `D-08` el dataset, el manifiesto y **los siete
> modelos candidatos** (5,7 MB) se publican con el repositorio, verificables con
> `sha256sum -c docs/dataset/SHA256SUMS`. Se descubrió al hacerlo que los seis
> comparadores sí existían en el disco de evidencias y que sus hashes coinciden
> con el manifiesto, así que la comparación de modelos pasa a ser reproducible,
> no solo citable.
>
> **Ya resuelto en esta fase:** `D-33` licencias (MIT para el código, CC BY 4.0
> para datos y documentación), responsables, contacto institucional, política de
> retención y usos prohibidos, declarados en `LICENSE`, `LICENSE-DATA`, `README.md`
> y las secciones 1 y 10 del datasheet.
>
> **Ya resuelto en esta fase:** `D-29` el datasheet canónico existe —
> [`docs/dataset/DATASHEET_MULTILAYER_V2.md`](../../dataset/DATASHEET_MULTILAYER_V2.md),
> generado desde los artefactos y con las once secciones de la rúbrica. Sus
> secciones de licencia (`D-33`) y de publicación descargable (`D-08`) quedan
> **declaradas como pendientes dentro del propio documento**, no ocultas.
>
> **Ya resuelto en esta fase**, con evidencia en
> [`181-correccion-catalogo-auditoria-y-gates.md`](../../fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md):
>
> - `D-30` cinco documentos afirmaban **38 perfiles** normales; el dataset tiene **44**, y los 44 aparecen en las tres particiones.
> - `D-31` el catálogo de anomalías declaraba **3 de 9** familias; se completó separando `profiles` (heredados, VM05) de `kali_profiles` (ofensivos, VM04), sin debilitar la lista blanca benigna.
> - `D-32` el reporte de auditoría almacenado describía el corpus de 75/18; regenerado a 1 373/179 y el anterior archivado sin borrar.
> - `D-35` los generadores de Word tomaban el logo de un directorio efímero de sesión y omitían la carátula **en silencio** al faltar; logo llevado al repositorio y fallo ahora ruidoso.


---

## Trazabilidad

Cada punto de este registro puede verificarse en su fuente:

| Origen | Documento |
|---|---|
| Validación operativa del sistema desplegado | [`docs/fase07-validacion-final/`](../../fase07-validacion-final/) |
| Evaluación crítica completa, con las 11 figuras | [`../01-evaluacion-critica/`](../01-evaluacion-critica/informe-evaluacion-critica.md) |
| Validación interna, externa y confiabilidad | [`../02-validacion-y-confiabilidad/`](../02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md) |
| Ficha de auditoría del producto | [`../04-ficha-auditoria/`](../04-ficha-auditoria/ficha-auditoria.md) |
| Registro técnico del sistema (12 filas, 7 corregidas) | [`docs/07-mejoras-futuras/01-debilidades-y-mejoras.md`](../../07-mejoras-futuras/01-debilidades-y-mejoras.md) |
| Requisitos del jurado y su matriz de cumplimiento | [`docs/requisitos-jurado/`](../../requisitos-jurado/README.md) |
