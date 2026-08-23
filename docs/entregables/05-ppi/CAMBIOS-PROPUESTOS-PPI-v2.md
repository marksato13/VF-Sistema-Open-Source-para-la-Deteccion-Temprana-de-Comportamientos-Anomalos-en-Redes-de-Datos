# Cambios propuestos y aplicados al PPI — versión 2

**Documento intervenido:** `docs/entregables/05-ppi/PPI Editar_actual.docx`

**Respaldo previo:** `docs/entregables/05-ppi/PPI Editar_actual.backup-20260822-before-v2.docx`

**Rama:** `main`

**Fecha de actualización:** 22 de agosto de 2026

**Acción D-20:** actualización del PPI contra los resultados y limitaciones reales del sistema.

## Nota sobre las páginas

El DOCX fue guardado por Microsoft Word para la web sin `lastRenderedPageBreak`, campos `PAGE` ni una propiedad de cantidad de páginas. La paginación, además, cambia al sustituir textos y figuras. Esta máquina no dispone de Word ni LibreOffice para recalcularla con fidelidad. Por esa razón, cada ubicación contiene la sección y el identificador exacto del párrafo o tabla, y marca la página como **“por confirmar en Word”**. No se inventaron números de página.

Los identificadores `Pnnnn` y `TnnRnnCnn` son auxiliares de esta auditoría: permiten localizar sin ambigüedad el contenido en `word/document.xml`, pero no forman parte del texto visible del PPI.

Los cambios están ordenados por gravedad: primero afirmaciones falsas o insostenibles, luego contenido desactualizado y al final mejoras de presentación.

---

## PPI-01 — Declarar la selección posterior del modelo

| Campo | Contenido |
|---|---|
| **ID** | `PPI-01` |
| **Ubicación** | §1.2.3, §2.4.5, §2.6.3 y §2.7.3; `P0066`, `P0224`, `P0292`, `P0324`; página por confirmar en Word |
| **Texto actual** | “Salida esperada: modelo Isolation Forest entrenado, parámetros de configuración definidos y evidencia técnica suficiente para sustentar su integración en el mecanismo de control inline.” |
| **Texto propuesto** | “Resultado obtenido: modelo OCSVM congelado, parámetros y umbral registrados con SHA-256. La selección es posterior a observar test: el manifiesto designaba if_primary_weighted como conclusión principal y ocsvm_scaled como comparador. En consecuencia, la detección global de 88,3 % (158/179; IC de Wilson 95 %: 82,7 %–92,2 %) y el ROC-AUC 0,974 son estimaciones optimistas al ser el máximo observado entre siete candidatos sobre los mismos conjuntos.” |
| **Justificación** | `artifacts/model/manifest.json` registra `if_primary_weighted` con rol `primary`, `ocsvm_scaled` con rol `sensitivity_or_comparator` y una política que prohibía promover comparadores por ganar una métrica posterior. La consecuencia metodológica está desarrollada en `docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md`. |
| **Debilidad asociada** | `D-01`, `D-20` |
| **Tipo** | corrección metodológica · adición de limitación |
| **Riesgo si no se hace** | El jurado podría leer el manifiesto y preguntar por qué el modelo congelado contradice la política predefinida o por qué se presenta 88,3 % como una estimación ciega. |

---

## PPI-02 — Reportar el FPR operativo junto al offline

| Campo | Contenido |
|---|---|
| **ID** | `PPI-02` |
| **Ubicación** | §2.4.7 y §2.6.4; `P0235`–`P0238`, `P0298`; página por confirmar en Word |
| **Texto actual** | “Después (propuesta): sistema integrado con modelo predictivo, motor de decisión y control inline.” |
| **Texto propuesto** | “Operación F6: FPR de 25,81 % (16/62; IC 95 %: 16,6 %–37,9 %) en el pase 1 y 22,97 % (17/74; IC 95 %: 14,9 %–33,7 %) en el pase 2, sobre tráfico legítimo pesado.”<br><br>“En operación, el FPR aumentó a 25,81 % (16/62; IC 95 %: 16,6 %–37,9 %) y 22,97 % (17/74; IC 95 %: 14,9 %–33,7 %). Una transferencia legítima iperf-tcp 200M obtuvo score 1,689, inferior a 1,8126, y bloqueó al cliente durante 120 segundos. Este es el principal límite de validez externa.” |
| **Justificación** | `docs/fase07-validacion-final/02-resultados-f6.md` registra ambos pases y la prueba aislada. Los intervalos ya calculados proceden de `docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md`. |
| **Debilidad asociada** | `D-11`, `D-20` |
| **Tipo** | corrección de cifra · adición de limitación |
| **Riesgo si no se hace** | El jurado podría contrastar 4,71 % con F6 y preguntar por qué el PPI oculta el resultado que refuta la generalización sobre tráfico pesado. |

---

## PPI-03 — Sustituir el modelo declarado por el modelo congelado real

| Campo | Contenido |
|---|---|
| **ID** | `PPI-03` |
| **Ubicación** | §1.2.3, hipótesis específicas, variable independiente, §2.4.5, §2.6.3 y tablas 1, 2, 4 y 9; `P0065`, `P0085`, `P0086`, `P0090`, `P0141`, `P0221`, `P0291`, `T01`, `T02`, `T09`; página por confirmar en Word |
| **Texto actual** | “El análisis se centra en la implementación y evaluación del modelo de detección de anomalías adoptado en el sistema integrado, correspondiente a Isolation Forest. Su uso responde a su compatibilidad con datos tabulares de flujo, baja latencia de inferencia y viabilidad de integración en escenarios de operación inline.” |
| **Texto propuesto** | “El análisis final se centra en ocsvm_scaled, un OCSVM con kernel RBF y nu = 0,05 sobre variables estandarizadas. Se comparó con cuatro variantes de Isolation Forest, LOF y Elliptic Envelope. OCSVM se desplegó por su mayor cobertura empírica de familias con un FPR offline semejante, no porque sea universalmente superior.” |
| **Justificación** | El modelo, parámetros, rol, umbral y evaluación primaria están en `artifacts/model/manifest.json`. La comparación se documenta en `docs/fase04-modelado/05-resultado-calibracion-multilayer-v2-v1.md`. |
| **Debilidad asociada** | `D-01`, `D-20` |
| **Tipo** | corrección metodológica |
| **Riesgo si no se hace** | El jurado podría preguntar por qué el PPI desarrolla Isolation Forest mientras el artefacto y el motor despliegan OCSVM. |

---

## PPI-04 — Incorporar resultados con intervalos de Wilson

| Campo | Contenido |
|---|---|
| **ID** | `PPI-04` |
| **Ubicación** | §2.6.4; `P0295`–`P0297`; página por confirmar en Word |
| **Texto actual** | “En términos analíticos, las métricas de detección incluyen Precision, Recall, F1-score y FPR. En términos de anticipación, se considera Lead Time como indicador del tiempo efectivo de alerta antes de la materialización del evento crítico.” |
| **Texto propuesto** | “El modelo obtuvo ROC-AUC 0,974; detección global de 88,3 % (158/179; IC 95 %: 82,7 %–92,2 %) y detección Kali-real de 88,8 % (143/161; IC 95 %: 83,0 %–92,8 %). Estas cifras heredan el sesgo optimista de la selección posterior del modelo entre siete candidatos.”<br><br>“El FPR offline fue 4,71 % (13/276; IC 95 %: 2,8 %–7,9 %). Las familias de autenticación fueron el punto débil: AUTH-FAIL alcanzó 50,0 % (3/6; IC 95 %: 18,8 %–81,2 %) y PASSWORD-SPRAY 55,2 % (16/29; IC 95 %: 37,5 %–71,6 %); el tamaño muestral impide conclusiones fuertes para AUTH-FAIL.” |
| **Justificación** | Todas las cifras e intervalos están en `docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md`; los conteos primarios se reproducen desde `artifacts/model/manifest.json`. No se recalcularon los intervalos ya existentes. |
| **Debilidad asociada** | Sin ID abierto: la falta de intervalos figura como resuelta en el registro; relacionada con `D-01` y `D-20`. |
| **Tipo** | corrección de cifra · corrección metodológica |
| **Riesgo si no se hace** | El jurado podría cuestionar la incertidumbre de resultados con n pequeño, especialmente el 50 % de AUTH-FAIL con solo seis ventanas. |

---

## PPI-05 — Declarar 27 variables efectivas de 28 definidas

| Campo | Contenido |
|---|---|
| **ID** | `PPI-05` |
| **Ubicación** | Variable independiente y §2.6.5; `P0097`, `P0102`, `P0301`; página por confirmar en Word |
| **Texto actual** | “Las variables pueden incluir métricas como volumen de bytes, número de paquetes, duración del flujo, tasas de transferencia, ratios derivadas y variables agregadas por ventana temporal.” |
| **Texto propuesto** | “El contrato define 28 variables multicapa calculadas en ventanas causales de 10, 30 y 60 segundos: 9 de L3, 8 de L4 y 11 de L7. Incluye volumen, tasas, razones, diversidad de destinos, actividad SYN, comportamiento DNS, HTTP y TLS. La variable tls_handshake_failure_ratio_60s permaneció en 0,0 en todo el dataset por falta del evento intermedio en Suricata; por ello se reportan 27 variables efectivas de 28 definidas.” |
| **Justificación** | El contrato está en `configs/features/multilayer-v2.json`; la no observabilidad está demostrada en `docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md` y resumida en `CLAUDE.md`. |
| **Debilidad asociada** | `D-12`, `D-20` |
| **Tipo** | corrección de cifra · adición de limitación |
| **Riesgo si no se hace** | El jurado podría pedir variación o aporte de cada variable y encontrar que una de las 28 columnas es constante en todo el dataset. |

---

## PPI-06 — Corregir la topología del laboratorio

| Campo | Contenido |
|---|---|
| **ID** | `PPI-06` |
| **Ubicación** | §2.3 y §2.4.2; figura 1, `P0195`, `P0196`, `P0203`, `P0204`; página por confirmar en Word |
| **Texto actual** | “El entorno se implementa mediante el hipervisor VMware, sobre el cual se despliegan las máquinas virtuales que conforman la topología de laboratorio. Estas incluyen una estación cliente con Windows 11, una estación de administración con Ubuntu Desktop, una máquina atacante con Kali Linux, un nodo sensor con Ubuntu para Suricata, un servidor de servicios internos y un nodo de datos. Cada VM se configura con los recursos de cómputo, interfaces de red y direccionamiento IP correspondientes al diseño de la topología, con pfSense como gateway y firewall del segmento LAN.” |
| **Texto propuesto** | “El entorno se implementó sobre VMware ESXi con cinco máquinas virtuales: VM01 Administración, VM02 Sensor/Router, VM03 Servidor protegido, VM04 Kali y VM05 Cliente legítimo. La topología separa PPI-MGMT (10.10.10.0/24), PPI-LAN (10.20.0.0/24) y PPI-DMZ (10.30.0.0/24). VM02 funciona como gateway inline LAN–DMZ; no se utiliza pfSense ni un nodo de datos adicional.” |
| **Justificación** | Arquitectura vigente en `CLAUDE.md` y `docs/fase00-infraestructura/virtualizacion/README.md`. La figura se sustituyó por `docs/entregables/graficas/E1-topologia.png`. |
| **Debilidad asociada** | `D-20` |
| **Tipo** | corrección metodológica · actualización de figura |
| **Riesgo si no se hace** | El jurado podría preguntar dónde están pfSense, Windows 11 y el sexto nodo, componentes que no existen en el laboratorio validado. |

---

## PPI-07 — Corregir el mecanismo de enforcement

| Campo | Contenido |
|---|---|
| **ID** | `PPI-07` |
| **Ubicación** | Variable independiente, §2.4.6, tabla 8 y presupuesto; `P0092`, `P0094`, `P0124`, `P0130`, `P0131`, `P0181`, `P0187`, `P0228`, `T08`, `T10`; página por confirmar en Word |
| **Texto actual** | “La integración se realiza vinculando la salida del modelo (score de anomalía) con un motor de decisión basado en umbrales y políticas de acción graduales. Este motor traduce el nivel de riesgo en veredictos operativos (permitir, limitar o bloquear), los cuales se aplican sobre el tráfico mediante NFQUEUE e iptables/ipset.” |
| **Texto propuesto** | “La integración vincula el score del OCSVM con un motor de decisión de umbral único. El motor emite PERMIT o ALERT y, ante una alerta válida, aplica BLOCK mediante nftables en el propio Sensor/Router VM02. El bloqueo expira de forma nativa a los 120 segundos y no depende de SSH entre VMs. No se implementó un nivel LIMIT porque requeriría un segundo umbral calibrado.” |
| **Justificación** | Diseño y evidencia del mecanismo en `docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md`; estado vigente en `CLAUDE.md`. |
| **Debilidad asociada** | `D-13`, `D-21`, `D-20` |
| **Tipo** | corrección metodológica |
| **Riesgo si no se hace** | El jurado podría pedir demostrar NFQUEUE, iptables, ipset, dos umbrales o LIMIT, aunque ninguno forma parte del producto congelado. |

---

## PPI-08 — Reemplazar el tamaño muestral planificado por el obtenido

| Campo | Contenido |
|---|---|
| **ID** | `PPI-08` |
| **Ubicación** | §2.4.4 y §2.5.1; `P0218`, `P0242`; página por confirmar en Word |
| **Texto actual** | “La muestra se define como el conjunto de ventanas temporales recolectadas durante 14 días calendario, con captura continua y registro estructurado de eventos.” |
| **Texto propuesto** | “La muestra observada comprende 1 373 ventanas normales de 220 episodios y 179 ventanas anómalas de 132 episodios. Las normales se distribuyeron en train 824, validation 273 y test 276; las anomalías proceden de 161 ventanas Kali-real y 18 heredadas. La recolección se organizó por campañas y repeticiones, no como captura continua durante 14 días.” |
| **Justificación** | Conteos en `artifacts/model/manifest.json`, `docs/fase03-dataset/180-consolidacion-dataset-v2-ampliado.md` y `docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md`. |
| **Debilidad asociada** | `D-09`, `D-25`, `D-20` |
| **Tipo** | corrección de cifra · corrección metodológica |
| **Riesgo si no se hace** | El jurado podría pedir los 14 días de captura continua y encontrar campañas por episodios con un tamaño inferior a la meta original. |

---

## PPI-09 — Corregir la unidad de análisis y el particionado

| Campo | Contenido |
|---|---|
| **ID** | `PPI-09` |
| **Ubicación** | §2.5.1; `P0241`; página por confirmar en Word |
| **Texto actual** | “La unidad de análisis de esta investigación está constituida por flujos de red (flows) y eventos de telemetría en formato EVE JSON generados por Suricata en un entorno de laboratorio controlado.” |
| **Texto propuesto** | “La unidad de análisis es una ventana causal asociada a la IP iniciadora, cerrada cada 10 segundos y construida con historia de 10, 30 y 60 segundos a partir de PCAP y EVE JSON. Cada ventana contiene 28 variables multicapa y pertenece a un episode_id que no se divide entre train, validation y test.” |
| **Justificación** | `configs/features/multilayer-v2.json`, `artifacts/model/manifest.json` y pruebas de causalidad referidas en `docs/entregables/02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md`. |
| **Debilidad asociada** | `D-09`, `D-20` |
| **Tipo** | corrección metodológica |
| **Riesgo si no se hace** | El jurado podría preguntar cómo se evita la fuga temporal si la unidad declarada es un flujo pero el modelo recibe ventanas solapadas. |

---

## PPI-10 — Corregir el protocolo de recolección

| Campo | Contenido |
|---|---|
| **ID** | `PPI-10` |
| **Ubicación** | §2.5.1 y §2.5.2; `P0245`, `P0247`, `P0248`, `P0251`, `P0268`, `P0269`, `P0273`, `P0278`; página por confirmar en Word |
| **Texto actual** | “Recolección continua de eventos durante 14 días en el entorno de prueba.”<br><br>“Generación controlada de tráfico anómalo con hping3, en ventanas planificadas.” |
| **Texto propuesto** | “Captura por episodio de PCAP, EVE JSON, métricas, manifiesto y hashes, con relojes sincronizados.”<br><br>“Generación controlada desde Kali de DNS anómalo, escaneo, SYN-rate, UDP-probe y fallos de autenticación, en episodios identificados.” |
| **Justificación** | Procedimiento de campañas y dataset en `docs/fase03-dataset/`; composición consolidada en `artifacts/model/manifest.json`. |
| **Debilidad asociada** | `D-09`, `D-10`, `D-20` |
| **Tipo** | corrección metodológica |
| **Riesgo si no se hace** | El jurado podría solicitar una captura continua inexistente o asumir que todas las anomalías proceden únicamente de hping3. |

---

## PPI-11 — Corregir entrenamiento, calibración y umbral

| Campo | Contenido |
|---|---|
| **ID** | `PPI-11` |
| **Ubicación** | Variable independiente y §2.4.5; `P0094`, `P0221`, `P0222`; página por confirmar en Word |
| **Texto actual** | “El proceso contempla el entrenamiento del modelo bajo condiciones homogéneas de datos y evaluación, así como el ajuste de sus parámetros principales para adecuarlo al comportamiento del tráfico observado en el entorno de laboratorio.” |
| **Texto propuesto** | “El scaler y el modelo se ajustaron únicamente con las 824 ventanas normales de train. El umbral se calibró con 273 ventanas normales de validation, y test y anomalías se evaluaron en un paso. Los episodios no se repartieron entre particiones y el extractor causal usado offline es el mismo del motor en tiempo real.” |
| **Justificación** | `artifacts/model/manifest.json`: train 824, validation 273, test 276, α = 0,05, comparación estricta `score < threshold`, umbral 1,8126087939765134. |
| **Debilidad asociada** | `D-01`, `D-06`, `D-20` |
| **Tipo** | corrección de cifra · corrección metodológica |
| **Riesgo si no se hace** | El jurado podría preguntar qué datos ajustaron el scaler, el modelo y el umbral, y si test intervino en la calibración. |

---

## PPI-12 — Conservar las ecuaciones de Isolation Forest como comparador, no como modelo final

| Campo | Contenido |
|---|---|
| **ID** | `PPI-12` |
| **Ubicación** | Variable independiente, “Arquitectura general del modelo”; `P0096`–`P0131`; página por confirmar en Word |
| **Texto actual** | “El modelo propuesto se basa en el algoritmo Isolation Forest, este se emplea para detectar comportamientos anómalos en el tráfico de red a partir de variables derivadas de la telemetría capturada en tiempo real.” |
| **Texto propuesto** | “El modelo final congelado es un OCSVM con kernel RBF y nu = 0,05, aplicado después de estandarizar las características. Cada observación es una ventana causal por IP iniciadora con 28 variables definidas —L3 = 9, L4 = 8 y L7 = 11—, de las cuales 27 fueron efectivas porque tls_handshake_failure_ratio_60s permaneció constante y no observable. Las ecuaciones de Isolation Forest que siguen se conservan como descripción del comparador inicialmente designado, no como formulación del modelo desplegado.” |
| **Justificación** | No se eliminaron ecuaciones OMML ni referencias válidas. Se cambió su alcance para concordar con el rol registrado en `artifacts/model/manifest.json`. |
| **Debilidad asociada** | `D-01`, `D-12`, `D-20` |
| **Tipo** | corrección metodológica |
| **Riesgo si no se hace** | El jurado podría identificar que las fórmulas explican un algoritmo distinto del archivo `.joblib` desplegado. |

---

## PPI-13 — Actualizar la validación F6 planificada por la ejecutada

| Campo | Contenido |
|---|---|
| **ID** | `PPI-13` |
| **Ubicación** | §2.4.7 y §2.5.1; `P0233`, `P0237`, `P0251`; página por confirmar en Word |
| **Texto actual** | “La validación se ejecutará durante 14 días calendario (2 semanas), mediante un plan de pruebas repetibles por escenarios. Se consideran cuatro escenarios de evaluación: (i) tráfico normal sostenido, (ii) tráfico anómalo puntual, (iii) tráfico anómalo persistente y (iv) tráfico mixto (normal + anómalo). Para cada escenario se realizarán 10 corridas controladas, totalizando 40 pruebas experimentales.” |
| **Texto propuesto** | “La validación final F6 se ejecutó con el motor y el enforcement activos en dos pases de 29 corridas más dos pruebas de aislamiento. El pase 2 controló el atraso del motor antes de iniciar cada corrida; el pase 1 se conservó como evidencia contaminada por carga acumulada. La campaña evaluó tráfico legítimo, ataques reales, disponibilidad y tiempo hasta la alerta o bloqueo.” |
| **Justificación** | `docs/fase07-validacion-final/02-resultados-f6.md` y `results/f6/f6_resultados.jsonl`. |
| **Debilidad asociada** | `D-11`, `D-20` |
| **Tipo** | corrección de cifra · corrección metodológica |
| **Riesgo si no se hace** | El jurado podría pedir las 40 corridas por cuatro escenarios, que no corresponden al protocolo finalmente ejecutado. |

---

## PPI-14 — Declarar el alcance limitado de la generalización

| Campo | Contenido |
|---|---|
| **ID** | `PPI-14` |
| **Ubicación** | §2.5.1; `P0262`; página por confirmar en Word |
| **Texto actual** | “En síntesis, el diseño muestral se orienta a construir un conjunto de datos representativo del comportamiento de red en laboratorio, suficiente para entrenar, ajustar y validar el modelo de detección de anomalías.” |
| **Texto propuesto** | “En síntesis, el diseño muestral permite entrenar y evaluar el sistema dentro del laboratorio, pero no demuestra generalización externa. Los mismos 38 perfiles aparecen en train, validation y test mediante repeticiones distintas, no existe una jornada temporal externa y faltan escenarios legítimos previstos; estas condiciones limitan el alcance de las conclusiones.” |
| **Justificación** | `docs/entregables/02-validacion-y-confiabilidad/informe-validacion-confiabilidad.md` documenta la división R01–R03/R04/R05, la ausencia de holdout temporal y los escenarios faltantes. |
| **Debilidad asociada** | `D-09`, `D-10`, `D-25` |
| **Tipo** | adición de limitación · corrección metodológica |
| **Riesgo si no se hace** | El jurado podría interpretar “representativo” como evidencia de generalización a perfiles, fechas o sistemas operativos no observados. |

---

## PPI-15 — Actualizar el riesgo ético y operativo

| Campo | Contenido |
|---|---|
| **ID** | `PPI-15` |
| **Ubicación** | §2.7.3 y §2.7.5; `P0324`, `P0337`, `P0342`, `P0345`; página por confirmar en Word |
| **Texto actual** | “En consecuencia, los riesgos del estudio son controlables y de bajo impacto cuando se respetan las restricciones de entorno y procedimiento.” |
| **Texto propuesto** | “En consecuencia, los riesgos son controlables dentro del laboratorio aislado, pero el costo operativo de un falso positivo no es bajo: puede interrumpir todo el tráfico del host durante 120 segundos. El bloqueo automático fuera del laboratorio no se considera autorizado ni validado.” |
| **Justificación** | El bloqueo falso reproducido se registra en `docs/fase07-validacion-final/02-resultados-f6.md`; la política de uso limitada al laboratorio consta en `CLAUDE.md`. |
| **Debilidad asociada** | `D-01`, `D-11`, `D-13`, `D-21` |
| **Tipo** | adición de limitación · corrección metodológica |
| **Riesgo si no se hace** | El jurado podría cuestionar la afirmación “bajo impacto” frente a una denegación de servicio autoinfligida y medida. |

---

## PPI-16 — Incorporar la auditoría del producto

| Campo | Contenido |
|---|---|
| **ID** | `PPI-16` |
| **Ubicación** | §2.6.5, nuevo contenido en `P0302`; página por confirmar en Word |
| **Texto actual** | El párrafo estaba vacío; el PPI no reportaba la auditoría del producto. |
| **Texto propuesto** | “La auditoría del producto alcanzó 32 de 51 criterios, equivalente a 62,7 % (IC de Wilson 95 %: 49,0 %–74,7 %). El intervalo se presenta para mantener el mismo criterio de incertidumbre, aunque los 51 ítems conforman una lista de control y no una muestra probabilística.” |
| **Justificación** | Conteo primario en `docs/entregables/04-ficha-auditoria/ficha-auditoria.md`. El IC se calculó por script desde 32/51 porque no existía previamente; no se interpretó como inferencia sobre una población aleatoria. |
| **Debilidad asociada** | `D-20` |
| **Tipo** | corrección de cifra · adición de resultado |
| **Riesgo si no se hace** | El jurado podría preguntar por la evaluación integral del producto y encontrarla solo en un anexo no reflejado por el PPI. |

---

## PPI-17 — Actualizar las figuras metodológicas obsoletas

| Campo | Contenido |
|---|---|
| **ID** | `PPI-17` |
| **Ubicación** | §2.3, §2.5.2 y §2.6.2; figuras 1, 2 y 3; `P0195`–`P0196`, `P0275`–`P0278`, `P0287`–`P0288`; página por confirmar en Word |
| **Texto actual** | “Figura 1: Arquitectura por Fases del Producto de Ingeniería” · “Figura 2: Procedimiento de recolección” · “Figura 3: Pipeline técnico de procesamiento, modelado e integración operativa del sistema propuesto”. Las imágenes mostraban Isolation Forest, hping3 como única fuente, NFQUEUE/iptables/ipset, LIMIT y un plan de 14 días. |
| **Texto propuesto** | “Figura 1: Topología validada del laboratorio y punto de decisión inline” · “Figura 2: Composición del dataset multicapa v2” · “Figura 3: Comparación de modelos sobre el dataset multicapa v2”. |
| **Justificación** | Se reutilizaron, sin regenerar, `E1-topologia.png`, `D1-composicion-dataset.png` y `B1-comparacion-modelos.png` de `docs/entregables/graficas/`. Se preservó el anclaje de cada imagen y se ajustó su alto manteniendo el ancho y la relación de aspecto. |
| **Debilidad asociada** | `D-01`, `D-20` |
| **Tipo** | actualización de figura |
| **Riesgo si no se hace** | Las figuras contradicen de forma visual el texto y pueden ser detectadas más rápido que las correcciones narrativas. |

---

## PPI-18 — Actualizar tablas de antecedentes, herramientas y cronograma

| Campo | Contenido |
|---|---|
| **ID** | `PPI-18` |
| **Ubicación** | Tablas 1, 2, 8, 9 y 10; `T01R002C06`, `T01R004C06`, `T02R002C08`, `T02R006C08`, `T08R005C01`, `T08R005C03`, `T09R019C01`, `T10R003C01`; página por confirmar en Word |
| **Texto actual** | “Muy alta. Ofrece el mejor equilibrio entre simplicidad, capacidad de detección y baja latencia para integración inline.”<br><br>“Baja-media. Referente teórico, pero menos conveniente que Isolation Forest para una implementación ligera.”<br><br>“NFQUEUE + iptables/ipset”. |
| **Texto propuesto** | “Alta como candidato ligero, pero insuficiente como modelo operativo en este dataset: no detectó ninguna ventana de tcp-syn-rate (0/31) ni udp-probe (0/40).”<br><br>“Alta en el dataset multicapa evaluado: fue el modelo desplegado por su mayor cobertura empírica, con la limitación de una selección posterior a observar test.”<br><br>“nftables inline en VM02”. |
| **Justificación** | Puntos ciegos y comparación en `artifacts/model/manifest.json`; enforcement en `docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md`. |
| **Debilidad asociada** | `D-01`, `D-20` |
| **Tipo** | corrección metodológica · actualización de tabla |
| **Riesgo si no se hace** | El jurado podría observar que las tablas siguen recomendando IF y NFQUEUE aunque el texto ya declare OCSVM y nftables. |

---

## Consultas

1. **Paginación final.** Abrir el DOCX en Microsoft Word, actualizar campos si los hubiera y completar las páginas de esta matriz. El paquete no conserva paginación renderizada y no se debe inferir a mano.
2. **Diseño preexperimental o cuasiexperimental.** El comentario `C17` del autor cuestiona “preexperimental”, pero cambiar el diseño es una decisión metodológica sustantiva y ambigua. No se modificó §2.1 ni el esquema `GE–X–O`. ¿El asesor confirma que debe pasar a cuasiexperimental y con qué grupo o medición de comparación?
3. **Hipótesis después de obtener resultados.** Solo se actualizaron los componentes técnicos —OCSVM y PERMIT/ALERT/BLOCK—; no se cambió post hoc la dirección de las hipótesis. Confirmar si LAM exige mantener la formulación prospectiva original o añadir un estado de contrastación.
4. **Ecuaciones del comparador.** Las ecuaciones OMML de Isolation Forest se conservaron para no degradar formato ni borrar un antecedente válido; el texto ahora las identifica como comparador descartado. Confirmar si el asesor prefiere moverlas a un anexo y añadir formalmente la función de decisión del OCSVM.
5. **Referencias históricas.** Se conservaron las referencias bibliográficas a Isolation Forest, iptables e ipset porque documentan antecedentes y el diseño inicial. Falta confirmar si se añadirá una referencia formal de One-Class SVM y nftables antes de subir a LAM.
6. **Porcentajes ajenos y criterios planificados.** Los porcentajes de antecedentes bibliográficos, los umbrales objetivo de la tabla 6 y el criterio institucional de 15 % de similitud se conservaron sin intervalos de Wilson: no son proporciones obtenidas por este proyecto y el PPI no aporta sus denominadores. ¿El asesor desea retirar esas cifras secundarias o conservarlas como citas y criterios, como están ahora?

## Figuras

### Figuras actualizadas dentro del DOCX

| Sección | Figura insertada | Motivo |
|---|---|---|
| §2.3 Arquitectura | `E1-topologia.png` | Sustituye la arquitectura planificada por la topología real de cinco VMs y VM02 inline |
| §2.5.2 Recolección/dataset | `D1-composicion-dataset.png` | Sustituye el flujo planificado de 14 días por la composición real y las particiones |
| §2.6.2 Procesamiento/modelado | `B1-comparacion-modelos.png` | Sustituye el pipeline visual de IF/LIMIT por la comparación que sustenta el modelo desplegado |

### Inserciones recomendadas antes de LAM

| Prioridad | Gráfico existente | Sección recomendada |
|---|---|---|
| Alta | `A1-curva-roc.png` | Después de los resultados de §2.6.4 |
| Alta | `C1-fpr-offline-vs-operativo.png` | Inmediatamente después del contraste offline/operativo |
| Alta | `C3-scores-trafico-pesado.png` | Junto al caso aislado `iperf-tcp 200M` |
| Alta | `C2-lead-time.png` | Después del resultado de mediana 8,0 s y p95 8,7 s |
| Media | `B2-heatmap-familias.png` | Junto a las debilidades AUTH-FAIL y PASSWORD-SPRAY |
| Media | `A2-distribucion-scores.png` | Para explicar el solapamiento alrededor de 1,8126 |
| Media | `A3-matriz-confusion.png` | Como resumen de test benigno frente a anomalías |
| Baja | `A4-barrido-umbral.png` | Como apoyo a la discusión de recalibración; no presentarlo como umbral seleccionado de forma ciega |

Falta una figura actualizada del pipeline extremo a extremo `PCAP/EVE → ventanas causales → 28 definidas/27 efectivas → StandardScaler–OCSVM → PERMIT/ALERT/BLOCK → nftables`. Ninguno de los 11 PNG existentes representa exactamente ese flujo. No se generó una figura nueva.

## Verificación

### Documento y respaldo

| Elemento | SHA-256 |
|---|---|
| DOCX original | `16f4019581820ecadbc2109ffca7e8e51129e846aa9b6d7cb583be5936b53979` |
| Respaldo previo | `16f4019581820ecadbc2109ffca7e8e51129e846aa9b6d7cb583be5936b53979` |
| DOCX actualizado | `f9f3abba6b8fc12443bd01ded52e800bb91577774b272698120bf7999c0b5fbc` |

Comprobaciones realizadas:

- `unzip -t`: **sin errores**.
- Apertura con `python-docx 1.2.0`: **correcta**.
- Estructura antes/después: 1 084 párrafos XML, 10 tablas, 13 secciones, 4 dibujos y 18 inicios de comentarios.
- El paquete conserva los mismos 37 nombres de entrada.
- Solo cambiaron `word/document.xml` y las tres imágenes actualizadas (`word/media/image2.png`, `image3.png`, `image4.png`).
- Permanecieron idénticos `styles.xml`, `numbering.xml`, `comments.xml`, las relaciones del documento, el logotipo y el resto del paquete.
- Las tres imágenes insertadas coinciden por SHA-256 con los PNG fuente del repositorio.
- No se eliminó ninguna sección, tabla, comentario o ecuación; se conservan cuatro imágenes en total y tres de ellas fueron sustituidas por las figuras actualizadas declaradas arriba.

La verificación confirma integridad estructural y apertura programática. La comprobación visual final de saltos de página, pies, ajuste de tablas y paginación debe realizarse en Microsoft Word antes de cargar el archivo en LAM Research.

### Artefactos congelados antes y después

Los 15 archivos auditados conservaron exactamente el mismo SHA-256. La columna “antes” es idéntica a la columna “después”.

| Artefacto | SHA-256 antes | SHA-256 después |
|---|---|---|
| `artifacts/dataset/anomaly-build-report.json` | `35e967a3dcaa3103b9e7f935245fdb99208c902ed977b7cadb8025afb5aa975d` | `35e967a3dcaa3103b9e7f935245fdb99208c902ed977b7cadb8025afb5aa975d` |
| `artifacts/dataset/archive/multilayer-v2-anomalies-frozen-2026-08-14-18rows.csv` | `d8bf293d6427398c5091344397ec1aea3303f277cae32d0988a0dc164ada761a` | `d8bf293d6427398c5091344397ec1aea3303f277cae32d0988a0dc164ada761a` |
| `artifacts/dataset/archive/multilayer-v2-normal-frozen-2026-08-14-75rows.csv` | `be8b71104bda5200a04ee77bdda5c3e164c5ed9a753bfc8c7dae9bb41003e99e` | `be8b71104bda5200a04ee77bdda5c3e164c5ed9a753bfc8c7dae9bb41003e99e` |
| `artifacts/dataset/multilayer-v2-anomalies.csv` | `d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3` | `d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3` |
| `artifacts/dataset/multilayer-v2-audit-report.json` | `67a5000369faae4206f5a5ee7b6bf94811108ed2ff576859003e6c95a5f7fa7b` | `67a5000369faae4206f5a5ee7b6bf94811108ed2ff576859003e6c95a5f7fa7b` |
| `artifacts/dataset/multilayer-v2-model-report-episode.json` | `37bdd9c596d4f1357f178a4d67c2b94360835360f4a2045bf3d994024011dbb1` | `37bdd9c596d4f1357f178a4d67c2b94360835360f4a2045bf3d994024011dbb1` |
| `artifacts/dataset/multilayer-v2-model-report-expanded.json` | `cbd812f55c1ad9e8638c317fb48293bea585906c2bc4a0d5460c2545752e316a` | `cbd812f55c1ad9e8638c317fb48293bea585906c2bc4a0d5460c2545752e316a` |
| `artifacts/dataset/multilayer-v2-model-report.json` | `16560a5d14429c3c482a41422085ffe3e40b1944e8f99e62426af6aaa0ee986f` | `16560a5d14429c3c482a41422085ffe3e40b1944e8f99e62426af6aaa0ee986f` |
| `artifacts/dataset/multilayer-v2-normal.csv` | `3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab` | `3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab` |
| `artifacts/dataset/multilayer-v2-pipeline-diagnosis.json` | `6a88a0b8ff0610358dd65224955d90edf416a55ba34cdaadf0bf78e554277c00` | `6a88a0b8ff0610358dd65224955d90edf416a55ba34cdaadf0bf78e554277c00` |
| `artifacts/dataset/normal-build-report.json` | `6c3a767afe7c1b2a4f19f25c441e8cb4917d06478f122e5b10503c78c24f3e08` | `6c3a767afe7c1b2a4f19f25c441e8cb4917d06478f122e5b10503c78c24f3e08` |
| `artifacts/dataset/partition-map-normal-v2.json` | `421e2247798ede89d1af6440e18f0404cb469739abc0d12c64b189aa27696669` | `421e2247798ede89d1af6440e18f0404cb469739abc0d12c64b189aa27696669` |
| `artifacts/model/manifest.json` | `0a1e8c52dc3282029d9aa1c9a0adbe7cc03c28bbce48bd5b76959e46bdbf5b1b` | `0a1e8c52dc3282029d9aa1c9a0adbe7cc03c28bbce48bd5b76959e46bdbf5b1b` |
| `artifacts/model/ocsvm_scaled.joblib` | `af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236` | `af9b50c29f839037b2bda380fc197e017dea482d403c61fa7ae3df79cbff7236` |
| `configs/features/multilayer-v2.json` | `1445ccd4f33f2269a73fb26f36519924525e6018910ebc22dc2005d7163be90d` | `1445ccd4f33f2269a73fb26f36519924525e6018910ebc22dc2005d7163be90d` |

### Estado Git

No se ejecutó `git commit` ni `git push`. Los cambios quedan deliberadamente sin publicar para la revisión adversarial independiente de Claude.
