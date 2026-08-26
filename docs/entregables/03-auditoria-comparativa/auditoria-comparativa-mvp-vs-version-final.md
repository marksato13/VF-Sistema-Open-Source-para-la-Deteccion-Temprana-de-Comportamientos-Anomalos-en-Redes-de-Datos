# Auditoría comparativa: MVP anterior frente a la versión final

**Proyecto:** Sistema open source para la detección temprana de comportamientos anómalos en redes de datos

**Repositorios auditados:** [MVP del ciclo anterior](https://github.com/marksato13/Sistema-Open-source-para-la-Detecci-n-Temprana-de-Comportamientos-An-malos-en-Redes-de-Datos) y [versión final en desarrollo](https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos)

**Cortes revisados:** MVP `9cdbb6fcf1d3` · versión final `1216c8feb4d5`

**Fecha de auditoría:** 19 de agosto de 2026

**Naturaleza del documento:** auditoría técnica y metodológica; separa hechos verificados, inferencias y recomendaciones.

---

## 1. Propósito y alcance

Este documento responde cuatro preguntas:

1. ¿Qué cambió realmente entre el repositorio anterior y la versión final?
2. ¿Por qué el cambio de arquitectura y de modelo tiene fundamento técnico?
3. ¿En qué medida se atendieron las observaciones realizadas por el jurado en la jornada científica?
4. ¿Cómo debe construirse y documentarse el dataset para que los resultados sean defendibles y reproducibles?

La revisión cubrió arquitectura, captura, extracción de características, particionado, entrenamiento, selección de modelo, métricas offline, validación operacional, bloqueo, documentación y reproducibilidad. No es una certificación de seguridad ni una aprobación para producción.

### 1.1 Criterio de evidencia

Cada conclusión usa una de estas categorías:

- **Verificado:** está respaldada por código, configuración, artefactos o pruebas ejecutadas.
- **Inferencia:** interpretación razonable construida a partir de la evidencia.
- **Recomendación:** cambio propuesto; no debe presentarse como trabajo ya ejecutado.

### 1.2 Verificaciones realizadas

- Inspección del historial, estructura y archivos de ambos repositorios.
- Contraste entre lo declarado en los documentos y lo implementado en los programas.
- Reejecución de la suite de la versión final: **85 pruebas aprobadas**.
- Reauditoría del dataset multicapa: integridad de esquema, etiquetas, valores ausentes y separación por episodio.
- Re-puntuación del modelo congelado: reproducción exacta de **13/276** falsos positivos y **158/179** anomalías detectadas.
- Recálculo independiente de ROC-AUC: **0,9741**.
- Verificación de hashes de los CSV, modelo y calibrador contra el manifiesto.
- Comprobación sintáctica del código Python y Bash del MVP; el repositorio anterior no incluye una suite de pruebas equivalente.

---

## 2. Dictamen ejecutivo

La versión final **sí es una evolución técnica sustancial**, no un simple cambio visual o una reescritura. La arquitectura pasó de un sensor pasivo en una red plana a un sistema inline segmentado; las variables pasaron de 14 estadísticas de flujo a 28 variables causales multicapa; el bloqueo dejó de depender de una conexión SSH remota; y la trazabilidad experimental mejoró mediante campañas, manifiestos, hashes, pruebas y automatización.

Sin embargo, el sistema todavía **no es sólido para operación desatendida**. El resultado offline del modelo es prometedor, pero la validación real demostró que tráfico legítimo pesado puede cruzar el umbral y provocar un bloqueo. Además, el modelo final fue promovido después de observar el conjunto de prueba, todavía no existe una jornada temporal externa completamente reservada y falta la ablación solicitada por el jurado.

El dictamen correcto para la defensa es:

> La versión actual demuestra viabilidad técnica y detección temprana reproducible en un laboratorio controlado. Aún requiere validación externa, recalibración y ampliación del dataset antes de habilitar bloqueo automático sin supervisión.

No debe afirmarse que el sistema está listo para producción ni que OCSVM es universalmente superior a Isolation Forest.

### 2.1 Estado resumido

| Dimensión | MVP anterior | Versión final | Dictamen |
|---|---|---|---|
| Arquitectura | Red plana, sensor pasivo | Redes segmentadas, sensor/router inline | Mejora clara |
| Unidad de análisis | Flujo | Ventana causal por iniciador | Mejor para detección temprana |
| Variables | 14 de flujo | 28 de L3/L4/L7 | Atiende al jurado, falta ablación |
| Particionado | Aleatorio por filas | Por episodios R01–R05 | Mejora; no prueba escenarios no vistos |
| Modelo operativo | Isolation Forest | OCSVM escalado | Mejor cobertura en este dataset, con sesgo de selección |
| Evaluación | Holdout reutilizado para umbral y reporte | Train/validation/test + ataques separados | Mejora metodológica, todavía sin holdout externo |
| Respuesta | Bloqueo remoto por SSH/ipset | Bloqueo local con nftables, 120 s | Más robusto, pero mayor riesgo ante FP |
| Reproducibilidad | Snapshot y ZIP parcial | Automatización, pruebas, hashes y manifiestos | Mejora fuerte |
| Falsos positivos reales | No medidos de forma comparable | 23–26 % en dos pases F6 | Brecha crítica abierta |

---

## 3. Qué pidió el jurado y qué se hizo

La fuente primaria dentro del repositorio es la [matriz de requisitos del jurado](../../requisitos-jurado/README.md). Las observaciones centrales fueron:

- No asumir que un paquete de 500–1.500 bytes es malicioso: el tráfico legítimo pesado también produce paquetes grandes.
- Ampliar la representación hacia capas L3, L4 y L7.
- Considerar frecuencia de SYN, proporción de IP únicas e intentos de autenticación fallidos.
- Separar entrenamiento, validación y prueba por sesiones completas.
- Evaluar con un día o conjunto temporal externo.
- Verificar que el sistema no bloquee tráfico normal en las pruebas finales.
- Comparar la base anterior con las capas añadidas y ejecutar un estudio de ablación.

### 3.1 Matriz de cumplimiento auditada

| Requisito | Evidencia actual | Estado auditado |
|---|---|---|
| Tratar tráfico pesado como potencialmente legítimo | Existen perfiles HTTP/HTTPS/TCP/UDP intensos y una prueba aislada `iperf-tcp 200M` | **Parcial**: se capturó, pero todavía produjo un bloqueo falso |
| Incorporar L3/L4/L7 | Contrato de 28 variables en [`configs/features/multilayer-v2.json`](../../../configs/features/multilayer-v2.json) | **Cumplido técnicamente** |
| Frecuencia de SYN | `syn_rate_10s` y razón de finalización | **Cumplido** |
| Proporción de destinos/IP únicas | `unique_dst_ip_ratio_30s` | **Cumplido** |
| Fallos de autenticación | Razón de respuestas HTTP 401/403 | **Parcial**: no equivale a observar fallos SSH cifrados |
| Split por sesiones completas | No se divide un `episode_id` entre particiones | **Cumplido** |
| Split 60/20/20 | 132/44/44 episodios normales; 824/273/276 ventanas | **Cumplido aproximadamente** |
| Conjunto temporal externo | No existe una jornada nueva reservada y abierta una sola vez | **Pendiente crítico** |
| Comparación de modelos | Siete detectores/configuraciones sobre el mismo dataset | **Cumplido con cautela** |
| Ablación base 14 vs capas añadidas | No existe experimento controlado equivalente | **Pendiente** |
| Cero bloqueos sobre tráfico normal final | F6 bloqueó un cliente normal por 120 s | **No cumplido** |
| Comparar sistema anterior y nuevo | Este informe y los experimentos actuales aportan el contraste | **Parcial**: falta una evaluación experimental bajo un protocolo idéntico |

La matriz de requisitos original debe actualizarse para que no muestre como cerrado aquello que la evidencia operacional contradice.

---

## 4. Línea base: repositorio del ciclo anterior

### 4.1 Arquitectura

El MVP usaba cuatro máquinas virtuales dentro de una red plana `192.168.0.0/24`. El sensor observaba tráfico en modo promiscuo y el servidor mantenía la lista de bloqueo. Para aplicar una decisión, el sensor se conectaba por SSH al servidor y modificaba `ipset`.

Consecuencias:

- El sensor era principalmente pasivo; la garantía de que todo el tráfico atravesara el punto de decisión era débil.
- Administración, cliente, atacante y servidor compartían el mismo dominio de red.
- La respuesta dependía de conectividad SSH, credenciales, permisos y disponibilidad de otra máquina.
- La atribución y el aislamiento de fallos eran más difíciles.

### 4.2 Datos y modelo

El código de `scripts/fase3_entrenar.py` trabaja con 14 variables agregadas por flujo y usa `train_test_split(..., shuffle=True)`. También contiene rutas e IP normales fijadas en el programa. El evaluador reutiliza el mismo conjunto de anomalías para construir umbrales ROC y reportar el desempeño.

Métricas registradas en `results/metricas_offline.txt`:

| Medida | Valor reportado |
|---|---:|
| Filas normales de entrenamiento | 53.708 |
| Filas normales de holdout | 13.427 |
| Filas anómalas | 596.836 |
| ROC-AUC | 0,8956 |
| FPR en `tau1` | 20,27 % |
| Precisión | 99,54 % |
| Recall | 99,36 % |
| F1 | 99,45 % |

Estas métricas no deben leerse de forma aislada. El conjunto evaluado tenía aproximadamente **44,4 ventanas anómalas por cada ventana normal**. Esa prevalencia extrema infla precisión y F1 y no representa una red donde la mayoría del tráfico es legítimo. El FPR de 20,27 % es la señal más relevante para operación.

### 4.3 Problemas metodológicos del MVP

1. **Fuga por dependencia temporal potencial.** Un split aleatorio por filas puede colocar observaciones cercanas de una misma sesión en entrenamiento y prueba.
2. **Reutilización del conjunto evaluado.** El conjunto de anomalías participa en la elección del umbral y en el reporte final.
3. **Lista blanca antes del modelo.** Las IP consideradas normales podían omitir la inferencia; por ello un “FPR operativo 0” no mide necesariamente el error real del detector.
4. **Unidad de observación limitada.** Las estadísticas de flujo no representan bien secuencias tempranas ni relaciones entre capas.
5. **Contradicción documental.** Un documento de defensa afirmaba partición cronológica mientras el programa usaba mezcla aleatoria; un documento maestro posterior reconoce la corrección.
6. **Reproducibilidad incompleta.** El ZIP incluye modelo, escalador, predictor y holdout, pero no las capturas crudas necesarias para reconstruir todo el dataset.
7. **Historial mínimo.** El repositorio oficial contiene un único commit y 170 archivos, por lo que referencias internas a una evolución por commits no pueden verificarse desde ese historial.
8. **Sin pruebas automatizadas.** El código pasa comprobaciones sintácticas, pero no dispone de una suite que proteja causalidad, esquema o integración.

El MVP sirvió para demostrar el concepto. Sus cifras no deben compararse directamente con las de la versión final como si ambos experimentos tuvieran la misma población, unidad de análisis y protocolo.

---

## 5. Versión final: arquitectura y fundamento del cambio

### 5.1 Arquitectura actual

La versión final usa cinco máquinas virtuales:

| VM | Función principal |
|---|---|
| VM01 | Administración y orquestación |
| VM02 | Sensor, router inline, extracción, inferencia y bloqueo |
| VM03 | Servidor en DMZ |
| VM04 | Kali / origen de ataques controlados |
| VM05 | Cliente legítimo |

Las redes se separan en administración `10.10.10.0/24`, LAN `10.20.20.0/24` y DMZ `10.30.30.0/24`. Las interfaces externas se aíslan durante campañas. La infraestructura está documentada en la [guía de virtualización](../../fase00-infraestructura/virtualizacion/README.md) y automatizada con Ansible.

El sensor inline procesa PCAP y eventos EVE de Suricata, construye ventanas causales, puntúa con el modelo congelado y aplica bloqueos locales mediante nftables. El dashboard se expone en loopback y funciona como superficie de observación, no como autoridad de decisión.

### 5.2 Por qué el cambio de arquitectura está justificado

| Cambio | Problema que resuelve | Beneficio | Nuevo riesgo |
|---|---|---|---|
| Red plana → LAN/DMZ/gestión | Mezcla de roles y rutas ambiguas | Aislamiento y trazabilidad | Mayor complejidad de red |
| Sensor pasivo → gateway inline | No todo el tráfico debía cruzar el detector | Punto de observación y control definido | Un fallo o FP afecta disponibilidad |
| Bloqueo remoto → nftables local | Dependencia de SSH y del servidor | Menor latencia y menos puntos de fallo | Privilegios locales sensibles |
| Flujo terminado → ventanas 10/30/60 s | Detección tardía y poca secuencia | Alerta antes de terminar la sesión | Ventanas solapadas no son independientes |
| Captura aislada → PCAP + EVE + manifiesto | Baja trazabilidad | Procedencia y reconstrucción | Mayor volumen y sincronización |
| Ejecución manual → Ansible y servicios | Configuración no repetible | Despliegue auditable | Inventarios/secretos deben protegerse |

La latencia mediana registrada bajó aproximadamente de **62 s en el MVP a 8 s en la versión final**. Esta comparación describe la mejora operacional observada, pero no reemplaza una prueba controlada idéntica entre versiones.

### 5.3 La contrapartida importante

Mover el detector al camino inline convierte un error estadístico en un incidente de disponibilidad. En un sensor pasivo, un falso positivo genera una alerta; en el diseño actual puede bloquear a un usuario legítimo. Por eso la mejora arquitectónica solo es defendible si se acompaña de:

- calibración específica por modo de respuesta;
- expiración y reversión verificables;
- modo observación antes de modo bloqueo;
- métricas por episodio, no solo por ventana;
- reglas de seguridad que eviten bloquear infraestructura crítica;
- validación explícita de tráfico pesado legítimo.

---

## 6. Del modelo anterior al modelo actual

### 6.1 Representación actual

La unidad es una ventana causal asociada a la IP iniciadora, cerrada cada 10 s y con hasta 60 s de historia. El contrato define 28 variables:

| Capa | Cantidad | Ejemplos |
|---|---:|---|
| L3 | 9 | volumen, diversidad de destinos, fragmentación, razón de paquetes grandes |
| L4 | 8 | tasa SYN, finalización TCP, puertos y comportamiento UDP |
| L7 | 11 | DNS, HTTP, TLS y errores de autenticación HTTP |

La extracción causal está protegida por pruebas: un evento futuro no debe modificar una ventana ya cerrada. El contrato canónico está en [`configs/features/multilayer-v2.json`](../../../configs/features/multilayer-v2.json).

### 6.2 Modelo congelado

El modelo operacional es:

```text
StandardScaler → OneClassSVM(kernel="rbf", gamma="scale", nu=0.05)
```

Se entrena únicamente con tráfico normal de entrenamiento. El umbral `1,8126087939765134` se obtiene del 5 % inferior de los scores normales de validación; se alerta si el score operacional queda por debajo de ese umbral, de acuerdo con la convención implementada por el calibrador.

### 6.3 Comparación bajo el dataset nuevo

| Modelo | FPR normal test | Detección global | Lectura |
|---|---:|---:|---|
| Isolation Forest ponderado, candidato primario inicial | 4,35 % (12/276) | 54,2 % (97/179) | Menor FPR puntual, grandes puntos ciegos |
| Isolation Forest uniforme | 5,07 % (14/276) | 57,5 % (103/179) | Misma limitación por familias |
| OCSVM escalado | 4,71 % (13/276) | **88,3 % (158/179)** | Mejor cobertura global en este conjunto |

El OCSVM detectó 26/31 ventanas de ráfaga SYN y 40/40 de sonda UDP, donde las variantes principales de Isolation Forest obtuvieron 0/31 y 0/40. Su debilidad está en autenticación: 3/6 en fallos HTTP y 16/29 en password spraying.

### 6.4 Por qué OCSVM funcionó mejor aquí

**Inferencia técnica.** Después de estandarizar las 28 variables, el kernel RBF puede construir una frontera no lineal alrededor de la región normal. En este dataset, los patrones SYN y UDP se apartan de esa región de una forma que el aislamiento aleatorio de los árboles no capturó con la configuración evaluada.

La justificación válida es empírica y acotada:

> OCSVM obtuvo mejor cobertura por familia que las alternativas probadas sobre el dataset multicapa v2, manteniendo un FPR offline semejante.

La afirmación inválida sería:

> OCSVM es siempre mejor que Isolation Forest para detectar anomalías de red.

### 6.5 Sesgo de selección del modelo

El manifiesto experimental declaraba `if_primary_weighted` como conclusión principal y a OCSVM como comparador que no debía reemplazarlo por ganar una métrica observada en `test` o `evaluation_only`. La versión operacional promovió OCSVM después de ver esos resultados.

Por tanto:

- 88,3 % es un resultado reproducible del conjunto conocido;
- no es todavía una estimación completamente ciega del modelo seleccionado;
- puede tener sesgo optimista por selección post hoc entre siete alternativas;
- debe validarse en un conjunto temporal externo jamás usado para escoger modelo, hiperparámetros ni umbral.

Esta limitación también se reconoce en el [informe de evaluación crítica](01-informe-evaluacion-critica.md).

### 6.6 Comparación válida e inválida con el MVP

El AUC antiguo de 0,8956 y el nuevo AUC de 0,9741 **no son directamente comparables**, porque cambiaron:

- la unidad de observación;
- las fuentes y proporciones de datos;
- las etiquetas y familias de ataque;
- el particionado;
- la definición del score y del umbral.

La comparación científicamente más limpia disponible es OCSVM frente a Isolation Forest **sobre el mismo dataset nuevo**. Para atribuir la mejora a arquitectura, features o algoritmo se necesita la ablación descrita en la sección 10.

---

## 7. Auditoría del dataset multicapa v2

### 7.1 Composición observada

| Conjunto | Ventanas | Episodios | Procedencia/uso |
|---|---:|---:|---|
| Normal total | 1.373 | 220 | Entrenamiento, validación y prueba |
| Train normal | 824 | 132 | Ajuste del scaler y modelo |
| Validation normal | 273 | 44 | Fijación del umbral |
| Test normal | 276 | 44 | Estimación offline de FPR |
| Anomalías | 179 | 132 | Evaluación; 161 Kali-real y 18 heredadas |

La auditoría ejecutada sobre los CSV actuales confirmó:

- esquema completo y etiquetas limpias;
- cero valores ausentes;
- ningún episodio dividido entre particiones;
- 28 columnas de variables en orden contractual;
- una variable constante: `tls_handshake_failure_ratio_60s`;
- 22 vectores de características duplicados.

La puerta automática devuelve `pass=true`, pero constantes y duplicados no la hacen fallar. En adelante deben aparecer como advertencias formales y no quedar ocultos por un único estado “PASS”.

### 7.2 Fortalezas

- Se separa por `episode_id`, evitando la fuga directa de un mismo episodio.
- El extractor reutilizado por entrenamiento y tiempo real reduce diferencias entre laboratorio y operación.
- Las ventanas son causales.
- Existen PCAP, EVE, manifiestos, sincronización temporal y hashes.
- Se documenta por separado la procedencia Kali-real y heredada.
- La partición, el contrato de variables y el modelo quedan congelados.

### 7.3 Limitaciones

1. **Mismos perfiles en las tres particiones.** Los 44 perfiles normales aparecen en train, validation y test; R01–R03 entrenan, R04 valida y R05 prueba. Se mide repetibilidad de escenarios conocidos, no generalización a condiciones nuevas.
2. **Sin día externo.** No existe una captura posterior reservada antes de la selección final.
3. **Tamaño inferior a la meta.** Se obtuvieron 1.373 ventanas normales frente a la meta documental de 2.000–3.000 ventanas independientes.
4. **Ventanas solapadas.** Más filas no equivalen automáticamente a más observaciones independientes.
5. **Cobertura incompleta.** Faltan SSH, SCP/SFTP, SMB, backup, streaming, actualizaciones y diversidad de sistemas operativos.
6. **Una feature sin variación.** La variable TLS indicada no aporta separación en el corpus actual; debe capturarse adecuadamente o retirarse en una versión nueva.
7. **Autenticación parcial.** HTTP 401/403 es observable, pero el fallo de credenciales SSH no se obtiene pasivamente del contenido cifrado.
8. **Artefactos fuera de Git.** Los CSV y modelos están bajo `artifacts/`, excluido por `.gitignore`; un clon externo no puede reproducir las métricas sin una publicación adicional.
9. **Reportes derivados desactualizados.** Algunos JSON de construcción/auditoría aún reflejan el corpus inicial de 75 normales y 18 anomalías, mientras los CSV y el manifiesto actual contienen 1.373 y 179. Deben regenerarse o archivarse con un nombre de versión explícito.

### 7.4 Riesgo de desbalance por episodio

En train, 5 de 132 episodios concentran 261 de 824 ventanas, es decir, **31,7 %**. Aunque no exista fuga entre particiones, los episodios largos pesan más en un entrenamiento por ventanas. Se probó ponderación por episodio para Isolation Forest, pero no una sensibilidad equivalente para el OCSVM elegido.

Recomendación: evaluar OCSVM con ponderación o muestreo balanceado por episodio, bootstrap por episodio y métricas agregadas tanto por ventana como por episodio.

---

## 8. Cómo debe hacerse el datasheet

El datasheet no es una lista de columnas. Es el documento que permite entender de dónde provienen los datos, para qué pueden usarse, qué sesgos contienen y cómo reproducirlos.

### 8.1 Ruta y versión recomendadas

Crear, para la siguiente captura formal:

```text
docs/dataset/DATASHEET_MULTILAYER_V2_1.md
```

La versión `v2.1` debe ser nueva. No se deben sustituir silenciosamente los CSV, el modelo o el umbral congelados como `v2-v1`.

### 8.2 Contenido mínimo

1. **Ficha de identidad**
   - nombre, versión, fecha, responsables, licencia y contacto;
   - propósito y relación exacta con las observaciones del jurado.

2. **Topología y entorno**
   - diagrama y roles de VM01–VM05;
   - rangos IP, rutas y punto de captura;
   - versiones de SO, Suricata, Python, librerías y configuración relevante;
   - reloj/NTP y zona horaria.

3. **Unidad de observación**
   - IP iniciadora;
   - cierre cada 10 s;
   - historia máxima de 60 s;
   - ventanas solapadas y dependencia temporal resultante;
   - regla causal: solo eventos con tiempo menor o igual al cierre.

4. **Catálogo de escenarios**
   - código, objetivo, comando o generador, duración, intensidad y repeticiones;
   - normal/anómalo y justificación;
   - capa cubierta;
   - escenario completo, fallido o excluido, con motivo.

5. **Etiquetado y procedencia**
   - regla exacta para asignar `label`, `profile_id`, `episode_id` y `source_kind`;
   - distinción Kali-real, heredado y sintético;
   - tratamiento de ventanas de calentamiento, vacías o ambiguas;
   - revisión manual y desacuerdos.

6. **Particiones**
   - episodios y fechas de train/validation/test;
   - evidencia de que ningún episodio cruza particiones;
   - conjunto temporal externo, completamente sellado;
   - razón de las proporciones y conteos por ventana y episodio.

7. **Diccionario de variables**
   - fórmula exacta de las 28 variables;
   - capa, unidad, ventana, fuente EVE/PCAP;
   - denominador cero y valores faltantes;
   - cardinalidad, rango y costo computacional;
   - limitaciones de observabilidad, especialmente cifrado.

8. **Calidad**
   - ausentes, infinitos, constantes, duplicados y outliers;
   - correlación/redundancia;
   - cobertura por capa, escenario, día, intensidad y sistema operativo;
   - distribución por episodio para no confundir ventanas con muestras independientes.

9. **Sesgos y limitaciones**
   - laboratorio controlado, pocos hosts y perfiles repetidos;
   - desbalance y dependencia temporal;
   - ataques conocidos frente a ataques no vistos;
   - diferencia entre autenticación HTTP observable y protocolos cifrados.

10. **Uso responsable**
    - usos permitidos y prohibidos;
    - privacidad, anonimización y retención;
    - advertencia de que no autoriza bloqueo autónomo en producción.

11. **Reproducibilidad y mantenimiento**
    - comandos de captura, extracción y auditoría;
    - SHA-256 de PCAP/EVE/CSV/modelo/configuración;
    - convención de versiones y changelog;
    - ubicación pública de un release o repositorio de datos.

### 8.3 Flujo experimental recomendado

```text
Pre-registrar escenarios, criterios y particiones
                     ↓
Capturar PCAP + EVE + logs + manifiesto por episodio
                     ↓
Sellar episodios y hashes antes de extraer
                     ↓
Extraer ventanas causales con un único extractor
                     ↓
Auditar esquema, etiquetas, duplicados, constantes y cobertura
                     ↓
Entrenar solamente con train normal
                     ↓
Seleccionar modelo y umbral solamente con validation
                     ↓
Congelar código, datos, modelo y decisión
                     ↓
Abrir test externo temporal una sola vez
                     ↓
Validar el sistema inline y publicar datasheet + model card
```

### 8.4 Regla principal

El datasheet debe describir **lo que realmente se capturó**, no únicamente lo que estaba en el plan. Los escenarios no ejecutados, los artefactos descartados y los resultados desfavorables también forman parte del registro científico.

---

## 9. Validación operacional F6

La campaña final ejecutó dos pases de 29 corridas y pruebas aisladas. Hubo disponibilidad completa en 57 comprobaciones de servicio y una latencia mediana cercana a 8 s cuando el motor estaba al día. Los resultados completos están en [`docs/fase07-validacion-final/02-resultados-f6.md`](../../fase07-validacion-final/02-resultados-f6.md).

### 9.1 Resultado decisivo

| Contexto | Falsos positivos |
|---|---:|
| Test offline normal | 4,71 % (13/276) |
| F6, pase 1 | 25,81 % (16/62) |
| F6, pase 2 | 22,97 % (17/74) |

En aislamiento, tráfico legítimo `iperf TCP 200M × 30 s` produjo scores aproximados de 1,968; 1,814; 1,689 y 1,920 frente al umbral 1,8126. Una ventana cruzó el umbral y el cliente fue bloqueado durante 120 s. Otra quedó permitida por un margen mínimo, señal de solapamiento entre normalidad pesada y anomalía.

Esto refuta la generalización del FPR offline. El sistema detecta ataques, pero todavía no cumple la condición del jurado de evitar bloqueos sobre tráfico normal pesado.

### 9.2 Otros límites operacionales

- Se observó un retraso de hasta 161 s del motor durante carga; posteriormente se cambió a lectura incremental y una prueba de 500 MB bajó a 7–15 s. La concurrencia extrema sigue siendo un límite por validar.
- La respuesta implementa PERMIT/ALERT/BLOCK y expiración, pero no un modo LIMIT calibrado.
- El bloqueo por IP penaliza todo el tráfico del host, aunque la anomalía pertenezca a una sola sesión.
- Los umbrales de autenticación —mínimo de cinco solicitudes y 80 % de fallos— tienen justificación operativa, pero no una calibración estadística suficiente.

Hasta corregir estas brechas, la configuración defendible es **observación o alerta**, no bloqueo automático general.

---

## 10. Experimentos que faltan para atribuir la mejora

La pregunta “¿mejoró por la arquitectura, las variables o el modelo?” no puede responderse solo comparando dos AUC obtenidos en datasets distintos.

### 10.1 Ablación mínima solicitada

Sobre las mismas particiones, el mismo algoritmo y el mismo procedimiento de umbral:

| Experimento | Variables | Pregunta |
|---|---|---|
| A | 14 equivalentes al MVP | Línea base comparable |
| B | A + L3 nuevas | ¿Qué aporta L3? |
| C | B + L4 | ¿Qué aporta L4? |
| D | C + L7 = 28 | ¿Qué aporta L7 y el conjunto completo? |
| E | 28 menos L3 | Sensibilidad sin L3 |
| F | 28 menos L4 | Sensibilidad sin L4 |
| G | 28 menos L7 | Sensibilidad sin L7 |

Reportar por experimento:

- FPR y detección por ventana y por episodio;
- intervalos de confianza al 95 %;
- detección por familia;
- latencia y costo de extracción/inferencia;
- estabilidad por bootstrap de episodios;
- decisión tomada solo con validation.

### 10.2 Comparación de algoritmos limpia

Después de fijar el mejor conjunto de variables usando únicamente train/validation:

1. entrenar IF, OCSVM y demás candidatos con idénticos episodios;
2. calibrar cada umbral para un objetivo de FPR equivalente en validation;
3. elegir el modelo sin consultar test externo;
4. congelar la elección y abrir el conjunto externo una sola vez;
5. mantener el resultado aunque sea desfavorable.

Solo entonces podrá afirmarse que el cambio de modelo mejora la generalización.

---

## 11. Hallazgos priorizados

### H-01 — Bloqueo falso de tráfico legítimo pesado

- **Severidad:** crítica.
- **Hecho:** una transferencia legítima cruzó el umbral y bloqueó al cliente 120 s; F6 dio 22,97–25,81 % de FP por ventana.
- **Riesgo:** indisponibilidad provocada por el propio sistema.
- **Corrección:** operar en ALERT/LIMIT, ampliar normales pesados, recalibrar y exigir una prueba externa sin bloqueos antes de habilitar BLOCK.
- **Estado:** abierto.

### H-02 — Selección post hoc de OCSVM

- **Severidad:** alta metodológica.
- **Hecho:** el protocolo declaraba IF como modelo principal y OCSVM como comparador; OCSVM se promovió tras observar test/evaluación.
- **Riesgo:** estimación optimista de 88,3 %.
- **Corrección:** abrir una versión formal nueva y evaluarla en un día externo sellado.
- **Estado:** reconocido, no resuelto.

### H-03 — Falta de validación externa temporal

- **Severidad:** alta.
- **Hecho:** las particiones repiten los mismos 44 perfiles en R01–R05.
- **Riesgo:** medir repetibilidad en vez de generalización.
- **Corrección:** capturar una fecha posterior, nuevos perfiles e idealmente más de un SO; no usarla para ajustar nada.
- **Estado:** abierto.

### H-04 — Ablación pendiente

- **Severidad:** alta frente al jurado.
- **Hecho:** hay comparación de modelos, pero no 14 vs L3/L4/L7 bajo condiciones controladas.
- **Riesgo:** no poder atribuir científicamente la mejora a las nuevas capas.
- **Corrección:** ejecutar la matriz A–G de la sección 10.
- **Estado:** abierto.

### H-05 — OCSVM sin análisis de estabilidad equivalente

- **Severidad:** media-alta.
- **Hecho:** la sensibilidad de diez semillas y el tratamiento del peso por episodio se aplicaron a ramas IF, no al OCSVM final.
- **Riesgo:** desconocer dependencia de episodios dominantes y estabilidad muestral.
- **Corrección:** bootstrap/submuestreo por episodio y métricas de variación para OCSVM.
- **Estado:** abierto.

### H-06 — Contrato de variables incompleto como diccionario científico

- **Severidad:** media.
- **Hecho:** el JSON enumera las 28 variables, capas, ventanas, unidades y fuentes, pero falta un diccionario dedicado con fórmulas completas y manejo de bordes para todas ellas.
- **Riesgo:** un tercero no puede implementar un extractor independiente equivalente.
- **Corrección:** incorporar el diccionario de la sección 8.2 al datasheet.
- **Estado:** parcial.

### H-07 — Artefactos no distribuibles desde un clon

- **Severidad:** media.
- **Hecho:** `artifacts/` está excluido de Git; los archivos locales y sus hashes existen, pero no se obtienen al clonar.
- **Riesgo:** reproducibilidad externa incompleta.
- **Corrección:** publicar un release versionado con CSV redactados, modelo, manifiesto, hashes y licencia; documentar descarga y verificación.
- **Estado:** abierto.

### H-08 — Reportes JSON de distintas generaciones mezclados

- **Severidad:** media documental.
- **Hecho:** algunos informes derivados indican 75/18, mientras el dataset/modelo vigente usa 1.373/179.
- **Riesgo:** contradicción ante evaluadores y automatizaciones.
- **Corrección:** regenerar los informes actuales o mover los anteriores a `archive/` con versión y fecha inequívocas.
- **Estado:** abierto.

### H-09 — Feature TLS constante y duplicados no elevados por la puerta

- **Severidad:** media-baja.
- **Hecho:** una de 28 variables es constante y hay 22 vectores duplicados; la auditoría global aún pasa.
- **Riesgo:** presentar “28 variables efectivas” cuando solo 27 varían y subestimar dependencia.
- **Corrección:** separar errores de advertencias, documentar duplicados por episodio y resolver TLS en v2.1.
- **Estado:** abierto.

### H-10 — Permisos y documentación operacional inconsistentes

- **Severidad:** media de seguridad.
- **Hecho:** documentos distintos describen sudo limitado y sudo permanente sin restricciones.
- **Riesgo:** privilegios excesivos y defensa contradictoria.
- **Corrección:** auditar sudoers vigente, aplicar mínimo privilegio y actualizar una única fuente canónica.
- **Estado:** abierto.

---

## 12. Hoja de ruta recomendada

### 12.1 Antes de la siguiente exposición

1. Actualizar la matriz del jurado con estados reales.
2. Presentar el bloqueo falso como hallazgo, no ocultarlo.
3. Regenerar o archivar los JSON de 75/18.
4. Publicar el diccionario completo de 28 variables.
5. Aclarar que hoy existen 28 columnas, pero 27 variables con variación observada.
6. Marcar documentos anteriores como reemplazados cuando contradigan el estado vigente.
7. Mantener BLOCK desactivado para tráfico general; usar ALERT/LIMIT.

### 12.2 En uno o dos días de trabajo experimental

1. Ejecutar la ablación 14 → L3 → L4 → L7.
2. Evaluar estabilidad de OCSVM por episodio.
3. Fijar modelo, parámetros y umbral usando solo train/validation.
4. Generar datasheet y model card versionados.
5. Crear un release reproducible de artefactos, sin datos sensibles.

### 12.3 Siguiente campaña formal

1. Capturar escenarios faltantes: SSH, SCP/SFTP, SMB, backup, streaming y actualizaciones.
2. Añadir tráfico pesado concurrente y variedad de sistemas operativos.
3. Reservar una jornada temporal externa.
4. Abrir una versión `PM-multilayer-v2-v2`; no modificar silenciosamente v1.
5. Evaluar una sola vez el conjunto externo.
6. Repetir F6 con expiración/restablecimiento entre episodios y métricas por episodio.
7. Habilitar BLOCK solo después de superar un criterio predefinido sobre tráfico normal pesado.

---

## 13. Cómo defender el cambio ante el jurado

Una explicación breve y rigurosa puede ser:

> El MVP demostró que era posible detectar anomalías, pero usaba una red plana, variables de flujo y una evaluación aleatoria que podía mezclar observaciones relacionadas. La versión final convirtió el sensor en un punto inline segmentado, incorporó 28 variables causales de L3/L4/L7 y separó los episodios completos. En el mismo dataset nuevo, OCSVM cubrió ataques SYN y UDP que Isolation Forest no detectó y alcanzó 88,3 % de detección con 4,71 % de FPR offline. No obstante, la validación real reveló falsos bloqueos sobre tráfico pesado y la selección de OCSVM fue posterior a observar test. Por eso presentamos el resultado como viabilidad técnica y dejamos como trabajo obligatorio una validación temporal externa, ablación y recalibración antes de producción.

Esta formulación es más defendible que exagerar los resultados: muestra evolución, evidencia, autocrítica y un plan de cierre.

---

## 14. Conclusión final

La arquitectura nueva es más coherente con el objetivo de detección temprana y respuesta controlada. El cambio de modelo tiene evidencia favorable dentro del dataset multicapa, especialmente en SYN y UDP. El trabajo también mejoró de forma fuerte en trazabilidad, causalidad, automatización y reproducibilidad.

La principal debilidad ya no es demostrar que el sistema funciona, sino demostrar que **generaliza sin afectar al tráfico legítimo**. Para cerrar esa brecha se necesitan tres piezas: ablación, selección limpia del modelo y conjunto externo temporal. El datasheet debe convertirse en la fuente canónica que conecte esas decisiones con episodios, fórmulas, particiones, hashes, sesgos y límites de uso.

Por tanto, la versión final es claramente más sólida que el MVP, pero su estado honesto es **prototipo experimental avanzado**, no sistema listo para bloqueo autónomo en producción.

---

## 15. Fuentes internas principales

- [Requisitos y observaciones del jurado](../../requisitos-jurado/README.md)
- [Informe extenso de resultados y evaluación crítica](01-informe-evaluacion-critica.md)
- [Informe de validación y confiabilidad](02-informe-validacion-confiabilidad.md)
- [Diccionario multicapa G5](../../fase02-features-multicapa/01-diccionario-multicapa-G5.md)
- [Cierre del dataset normal v2](../../fase03-dataset/167-cierre-normales-v2-y-consolidacion.md)
- [Auditoría de calidad del dataset](../../fase03-dataset/171-auditoria-calidad-dataset-v2.md)
- [Protocolo de entrenamiento multicapa](../../fase03-dataset/169-protocolo-entrenamiento-multilayer-v2.md)
- [Resultado de calibración](../../fase04-modelado/05-resultado-calibracion-multilayer-v2-v1.md)
- [Diseño del motor en tiempo real](../../fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md)
- [Protocolo F6](../../fase07-validacion-final/01-protocolo-f6.md)
- [Resultados F6](../../fase07-validacion-final/02-resultados-f6.md)
- [Contrato canónico de 28 variables](../../../configs/features/multilayer-v2.json)
