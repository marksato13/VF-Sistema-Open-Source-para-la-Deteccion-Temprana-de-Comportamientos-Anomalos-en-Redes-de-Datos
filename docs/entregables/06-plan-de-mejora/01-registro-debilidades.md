# Registro de debilidades y mitigaciones

Cada punto tiene identificador estable (`D-nn`) para poder citarlo desde la tesis, el PPI o el artículo. **Ninguna debilidad se lista sin su evidencia**: si no hay medición que la respalde, no entra en este registro.

Leyenda de impacto: 🔴 crítico · 🟠 alto · 🟡 medio · ⚪ bajo

---

## A · Inferencia estadística

Es la dimensión más débil del proyecto. No afecta al funcionamiento del sistema, sino a **qué se puede afirmar** a partir de sus resultados.

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-01** | El modelo final se eligió observando el conjunto de prueba | El manifiesto registra `ocsvm_scaled` como *comparador* y una política que prohibía promoverlo por ganar una métrica posterior. El 88,3 % es el máximo sobre 7 candidatos sin conjunto reservado | 🔴 | Horas | **Declararlo explícitamente** en tesis y PPI: la cifra es una estimación optimista. La corrección completa (`PM-multilayer-v2-v2` con evaluación nueva) es trabajo futuro |
| **D-03** | Sin validación cruzada sobre el modelo congelado | Solo existe *leave-one-episode-out* sobre un pipeline descartado | 🟠 | Horas | Ejecutar validación cruzada por episodios sobre el modelo actual; datos y modelo ya existen |
| **D-04** | Sin pruebas de significancia entre modelos | Se comparan 88,3 % y 54,2 % como puntos desnudos | 🟡 | Horas | Prueba de McNemar o bootstrap pareado sobre las mismas ventanas |
| **D-05** | El análisis de sensibilidad no cubre el modelo elegido | `manifest.stability` contiene las 4 ramas de Isolation Forest, no `ocsvm_scaled`. Además se ajustó sin ponderación pese a que 5/132 episodios concentran el 31,7 % de las filas | 🟠 | Horas | Estabilidad por remuestreo/submuestreo del OCSVM, para dar una banda al umbral 1,8126 |
| **D-07** | Comparación con el criterio de Youden prometida y no entregada | El protocolo la anunciaba como comparación informativa | ⚪ | Horas | Calcularla y reportarla, o retirar la promesa del protocolo |

> **Ya resuelto en esta fase:** ausencia de intervalos de confianza (se incorporaron intervalos de Wilson 95 % a todas las proporciones) y ausencia de ROC/AUC, recall, especificidad y F1 (se calcularon re-puntuando el modelo congelado: **ROC-AUC 0,974**).

---

## B · Dataset y variables

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-02** | **La ablación por capas L3/L4/L7 nunca se ejecutó** | Requisito explícito del jurado, aún marcado "Planificado". No existe script ni artefacto. Ninguna de las 28 variables ha demostrado que se gana su lugar | 🔴 | 1–2 días | Ejecutar las cuatro configuraciones (Base 14 · +L3 · +L3+L4 · Multicapa) y la retirada por grupo. **No requiere campañas nuevas** |
| **D-08** | **El dataset y el modelo no están publicados** | El repositorio excluye `artifacts/` en bloque; esa regla arrastra al dataset (708 KB) y al modelo (8 KB) junto con las dependencias (60 MB) y las capturas (24 MB) | 🔴 | **Minutos** | Excluir esos dos artefactos de la regla y publicarlos. Sube el ítem 2.2 de la ficha de 1 a 3 |
| **D-09** | División por índice de repetición, sin jornada de holdout externa | R01–R03 entrenamiento, R04 validación, R05 prueba: los 44 perfiles aparecen en las tres particiones. Se mide repetibilidad, no generalización | 🟠 | Días | Capturar una jornada nueva y reservarla sin participar en entrenamiento ni calibración |
| **D-10** | Seis escenarios legítimos exigidos no existen | Faltan SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones; tampoco hay captura multi-sistema-operativo | 🟡 | Días | Capturarlos, o declararlos como límite de alcance si el jurado no los exige |
| **D-12** | `tls_handshake_failure_ratio_60s` es constante y no observable | Vale 0,0 en todo el dataset; se demostró que Suricata no produce el evento intermedio | 🟡 | Horas | **Declararla no observable** y reportar 27 variables efectivas, en vez de mantener una constante en el vector |
| **D-25** | Tamaño muestral por debajo de la meta declarada | 1 373 ventanas frente a la meta de 2 000–3 000; ~6 ventanas por episodio, luego no son independientes | 🟡 | Semanas | Reportar el tamaño efectivo por episodio junto al de ventanas, y declarar la brecha |

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
| **D-18** | **Ninguna validación con usuarios reales** | No hubo pruebas con analistas de seguridad ni medición de experiencia de uso del panel | 🟠 | 3–5 días | Aplicar un instrumento validado (SUS) con 5–8 evaluadores sobre el panel operativo |
| **D-28** | Sin evaluación por expertos o jueces | No se aplicó Delphi, juicio experto ni instrumento equivalente | 🟡 | Días | Sesión de juicio experto con 3 evaluadores, o declarar la ausencia |

---

## E · Requisitos y documentación

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-14** | **Sin diccionario de fórmulas para las variables 15–28** | El jurado pidió "diccionario, fórmulas, unidades y ventanas"; solo existe para las 14 de la versión anterior | 🔴 | Horas | **Extraerlas del código del extractor**, que ya las implementa, y publicarlas |
| **D-15** | Matriz de cumplimiento de requisitos obsoleta | 4 filas sin cerrar y referencias a rutas que ya no existen | 🟠 | Horas | Actualizarla al estado real y corregir las rutas |
| **D-17** | Manual de implementación técnica pendiente | Existe manual de operación, no de instalación reproducible desde cero | 🟠 | 1 día | Redactarlo; los comandos ya están probados en los despliegues documentados |
| **D-20** | **El PPI no refleja los resultados obtenidos** | Se redactó antes de que existieran; debe subirse actualizado al sistema LAM Research | 🔴 | Horas | Actualizar contra la tabla de correspondencia de `05-ppi/README.md` |
| **D-06** | Determinismo y semillas sin declarar como protocolo | 10 semillas registradas, pero no cubren el modelo elegido; el determinismo del OCSVM no se documenta | 🟡 | Horas | Documentarlo explícitamente en el protocolo |

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
| **D-23** | La ficha de auditoría no tiene ningún gráfico | El puntaje 62,7 % y la proyección a 76,5 % se comunican solo con tablas | ⚪ | Horas | Añadir barras de las tres dimensiones y un gráfico antes/después |
| **D-24** | El informe de validación excede la extensión pedida | ~5,2 páginas frente a las 3–4 solicitadas | ⚪ | Horas | Mover las referencias a anexo o condensar las tablas |

---

## H · Datasheet y publicación del corpus

Dimensión detectada por la evaluación de rúbrica de datasheet (61/100). La
identidad formal del dataset es la peor puntuada: **2/6**.

| ID | Debilidad | Evidencia | Impacto | Esfuerzo | Mitigación |
|---|---|---|---|---|---|
| **D-29** | **No existe un datasheet canónico del dataset** | La evidencia está repartida entre configuraciones, informes, código y artefactos locales; no hay documento único de procedencia, estructura, calidad y límites | 🔴 | 1 día | Redactar `docs/dataset/DATASHEET_MULTILAYER_V2.md` con las once secciones de la rúbrica |
| **D-33** | Sin licencia, responsables, contacto ni política de uso | No hay licencia del dataset, retención, anonimización ni usos prohibidos declarados | 🟠 | Horas | Redactarlas; el tráfico es de laboratorio y sin datos personales, así que la política es corta pero debe existir |
| **D-34** | Sin *model card* ni *system card* separadas del datasheet | Datos, modelo y sistema desplegado se describen mezclados en los mismos informes | 🟡 | Horas | Tres documentos: datasheet (datos), model card (OCSVM), system card (motor inline, bloqueo, FPR operativo) |

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
