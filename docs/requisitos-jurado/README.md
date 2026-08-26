# Mejoras de la versión final observadas por el jurado

## 1. Estado del documento

Este documento registra las dos observaciones formuladas por el jurado y las convierte en requisitos verificables de la versión final. En esta etapa las mejoras están **planificadas**; no se declararán implementadas hasta completar el código, las capturas, el entrenamiento y las pruebas correspondientes.

## 2. Contexto

El MVP demostró que Isolation Forest puede identificar desviaciones en los flujos de red del laboratorio y activar acciones `PERMIT`, `LIMIT` y `BLOCK`. Sin embargo, el conjunto normal utilizado para entrenarlo tiene representación limitada de tráfico legítimo pesado y las 14 variables actuales se concentran principalmente en estadísticas generales por flujo.

La versión final debe reducir la posibilidad de confundir volumen con ataque y debe representar comportamiento de las capas 3, 4 y 7 mediante variables temporales y multicapa.

## 3. Observación 1 — Ampliar el rango normal de entrenamiento

### Observación recibida

> Conseguir o generar un dataset con tráfico pesado legítimo y paquetes grandes, entre 500 y 1500 bytes, para que Isolation Forest aprenda que un paquete grande no constituye por sí solo un ataque.

### Problema identificado

Un modelo one-class aprende la distribución del tráfico que se le presenta como normal. Si las capturas normales contienen principalmente sesiones ligeras, una descarga, copia o transmisión legítima de alto volumen puede quedar fuera de esa distribución y recibir un score anómalo.

El tamaño del paquete no debe evaluarse aisladamente. Debe interpretarse junto con duración, direccionalidad, tasa, flags, respuestas del servidor, número de conexiones y comportamiento de la aplicación.

### Objetivo de mejora

Construir un nuevo conjunto de entrenamiento normal que represente tráfico:

- Ligero y pesado.
- Interactivo y sostenido.
- Cifrado y no cifrado.
- De una y varias conexiones simultáneas.
- Producido desde distintos sistemas operativos.
- Capturado en sesiones y horarios diferentes.
- Con paquetes distribuidos entre 500 y 1500 bytes, sin excluir paquetes pequeños normales.

### Escenarios normales que se incorporarán

| Código | Escenario | Finalidad |
|---|---|---|
| A1 | Navegación HTTP/HTTPS | Línea base interactiva |
| A2 | Sesiones SSH legítimas | Tráfico administrativo |
| A3 | Transferencia SCP/SFTP | Archivos grandes cifrados |
| A4 | Tráfico sostenido mixto | Concurrencia normal |
| A5 | Descarga HTTP de archivos grandes | Paquetes cercanos al MTU |
| A6 | Carga HTTP de archivos grandes | Tráfico pesado hacia el servidor |
| A7 | Transferencia SMB | Comportamiento Windows/archivos |
| A8 | Backup comprimido | Flujo prolongado de gran volumen |
| A9 | Streaming multimedia | Variación legítima de bitrate |
| A10 | Descargas concurrentes | Varias conexiones legítimas |
| A11 | Actualización de paquetes | Múltiples conexiones HTTPS |
| A12 | `iperf3` TCP controlado | Throughput alto y estable |
| A13 | `iperf3` UDP controlado | Throughput UDP sin intención maliciosa |
| A14 | Tráfico pesado concurrente | Descarga, SSH y navegación simultáneas |

### Rangos que se reportarán

Las capturas normales se analizarán al menos en estos intervalos:

| Intervalo | Interpretación |
|---|---|
| 64–499 bytes | Paquetes pequeños y de control |
| 500–999 bytes | Carga intermedia |
| 1000–1499 bytes | Carga grande |
| 1500 bytes | Paquetes al MTU cuando corresponda |

No se forzará que todos los paquetes sean grandes. El objetivo es que el dataset normal represente la distribución real de actividades legítimas.

### Separación de datos

Las capturas se dividirán por sesiones completas, no mediante una mezcla aleatoria de flujos pertenecientes a la misma sesión:

- 60 % de sesiones para entrenamiento.
- 20 % para calibración de umbrales.
- 20 % para prueba final.

Adicionalmente, se reservará una jornada nueva como validación temporal externa. Ninguna captura de esa jornada participará en entrenamiento ni calibración.

### Criterios de aceptación

- Existencia de capturas normales en todos los intervalos definidos.
- Metadatos de escenario, fecha, origen, destino, duración y volumen.
- Cero reutilización de una misma sesión entre entrenamiento y prueba.
- Reporte de `PERMIT`, `LIMIT` y `BLOCK` por escenario normal pesado.
- Ningún `BLOCK` sobre los escenarios normales de la prueba final.
- FPR reportado con y sin aplicación de whitelist.
- Comparación del modelo original contra el modelo entrenado con rango ampliado.

## 4. Observación 2 — Incorporar variables de capas 3, 4 y 7

### Observación recibida

> Ampliar las 14 variables de entrada para representar comportamiento de las capas 3, 4 y 7; por ejemplo, intentos fallidos de login, frecuencia de flags SYN y proporción de IPs únicas.

### Estado de las 14 variables del MVP

El vector actual contiene:

1. `pkts_toserver`
2. `pkts_toclient`
3. `bytes_toserver`
4. `bytes_toclient`
5. `duration`
6. `pkt_rate`
7. `byte_rate`
8. `pkt_ratio`
9. `byte_ratio`
10. `avg_pkt_size`
11. `is_tcp`
12. `is_udp`
13. `is_icmp`
14. `dest_port`

Estas variables describen volumen y características básicas del flujo, pero no capturan suficientemente la secuencia de acciones de una IP ni eventos de aplicación.

### Decisión de diseño

La versión final no conservará obligatoriamente el número 14. Se construirá un vector candidato más amplio y luego se seleccionarán las variables con evidencia estadística, estabilidad y costo operacional aceptable.

### Variables candidatas de Capa 3

| Variable | Ventana | Interpretación |
|---|---:|---|
| `unique_dst_ips_30s` | 30 s | Destinos diferentes contactados por el origen |
| `unique_src_ips_to_dst_30s` | 30 s | Orígenes diferentes hacia un destino |
| `unique_ip_ratio_30s` | 30 s | Destinos únicos respecto del total de conexiones |
| `icmp_rate_10s` | 10 s | Frecuencia de actividad ICMP |

### Variables candidatas de Capa 4

| Variable | Ventana | Interpretación |
|---|---:|---|
| `syn_count_10s` | 10 s | Frecuencia de flags SYN |
| `syn_ack_ratio_10s` | 10 s | Relación entre SYN y SYN-ACK |
| `rst_rate_10s` | 10 s | Frecuencia de resets TCP |
| `unique_dst_ports_10s` | 10 s | Puertos distintos contactados |
| `failed_tcp_ratio_30s` | 30 s | Conexiones que no completan el establecimiento |
| `udp_flow_rate_10s` | 10 s | Flujos UDP iniciados por unidad de tiempo |

### Variables candidatas de Capa 7

| Variable | Ventana | Interpretación |
|---|---:|---|
| `failed_login_count_60s` | 60 s | Intentos fallidos de autenticación |
| `http_request_rate_30s` | 30 s | Frecuencia de solicitudes HTTP |
| `http_error_ratio_30s` | 30 s | Proporción de respuestas HTTP 4xx/5xx |
| `dns_unique_query_ratio_60s` | 60 s | Diversidad de consultas DNS |
| `tls_session_rate_30s` | 30 s | Frecuencia de nuevas sesiones TLS |

### Fuentes de datos

El sensor procesará eventos Suricata de tipo:

- `flow`
- `alert`
- `http`
- `ssh`
- `dns`
- `tls`

Las variables temporales se construirán mediante ventanas deslizantes por IP. Solo podrá utilizarse información disponible hasta el instante de la decisión.

### Prevención de fuga de información

- No utilizar eventos futuros para construir una variable actual.
- No emplear la etiqueta futura como variable.
- No derivar una variable directamente del mismo umbral usado para etiquetar.
- Separar entrenamiento y prueba por sesión, escenario, fecha o IP cuando corresponda.
- Ajustar scaler, selector de variables y modelo exclusivamente con entrenamiento.

### Evaluación de aporte por capa

Se compararán al menos cuatro configuraciones:

| Configuración | Variables |
|---|---|
| Base | 14 variables originales |
| Base + L3 | Originales y comportamiento IP |
| Base + L3 + L4 | Originales, IP y transporte |
| Multicapa | Originales, L3, L4 y L7 |

Para cada configuración se reportará:

- AUC-ROC y, cuando corresponda, PR-AUC.
- Precision, recall y F1.
- FPR y TPR por escenario.
- Matriz de confusión.
- Latencia de extracción e inferencia.
- CPU y RAM del sensor.
- Importancia y estabilidad de las variables.

Se realizará también una prueba de ablación retirando por separado los grupos L3, L4 y L7 para medir su aporte.

### Criterios de aceptación

- Incorporar al menos una variable validada de cada capa 3, 4 y 7.
- Incluir explícitamente frecuencia SYN, proporción de IPs únicas e intentos fallidos de login, salvo justificación experimental documentada.
- Demostrar que las variables se calculan sin información futura.
- Comparar el modelo multicapa con las 14 variables originales.
- Mantener una latencia operacional compatible con el requisito del sistema.
- Publicar diccionario de datos, fórmulas, unidades y ventanas.

## 5. Impacto sobre la arquitectura

Las observaciones requieren los siguientes componentes nuevos o modificados:

```text
Suricata eve.json
      │
      ├── flow / alert
      ├── http / ssh
      └── dns / tls
      │
      ▼
Agregador temporal por IP
      │
      ├── ventanas de 10 s
      ├── ventanas de 30 s
      └── ventanas de 60 s
      │
      ▼
Vector de variables multicapa
      │
      ▼
Isolation Forest v2
      │
      └── PERMIT / LIMIT / BLOCK
```

La VM sensor fue dimensionada con 6 vCPU, 16 GB de RAM y 160 GB de disco para soportar captura, agregación temporal, inferencia y conservación de evidencias.

## 6. Automatización y evidencias

Ansible se utilizará posteriormente para:

- Preparar cliente, sensor, servidor y atacante.
- Ejecutar escenarios normales pesados con parámetros versionados.
- Iniciar y detener capturas.
- Registrar fecha, duración, volumen y escenario.
- Ejecutar pruebas normales, anómalas y mixtas.
- Recolectar logs, CSV, métricas y uso de recursos.
- Comprobar criterios de aceptación.

Cada resultado deberá vincularse con:

- Commit del código.
- Versión del dataset.
- Hash del modelo.
- Inventario de máquinas.
- Parámetros de la corrida.
- Fecha y hora.
- Resultado PASS/FAIL.

## 7. Orden planificado de implementación

1. Construir y validar la topología virtual.
2. Automatizar la configuración base con Ansible.
3. Definir el formato y diccionario del dataset.
4. Generar tráfico normal pesado.
5. Implementar el agregador temporal multicapa.
6. Construir y seleccionar las nuevas variables.
7. Entrenar Isolation Forest v2.
8. Calibrar umbrales con datos separados.
9. Ejecutar pruebas comparativas y de ablación.
10. Ejecutar la validación temporal final.
11. Publicar resultados y limitaciones.

## 8. Matriz de trazabilidad

*Cerrada al 26 de agosto de 2026. Cada fila enlaza a evidencia verificable; una
fila sin evidencia se declara pendiente, no se marca como cumplida.*

### Observación 1 — Tráfico legítimo pesado

| Requisito | Estado | Evidencia |
|---|---|---|
| Dataset normal con tráfico pesado | ✅ **Cumplido** | 44 perfiles con transferencias de 10 MB a 1 GB y 2–8 flujos concurrentes · [datasheet §4](../dataset/DATASHEET_MULTILAYER_V2.md) |
| Paquetes normales entre 500 y 1500 bytes | ✅ **Cumplido** | HTTP 91,6–98,7 % · HTTPS 95,4–98,0 % · C2 95,7 % · C4 96,2 % en los diez canarios pesados |
| Un paquete grande no debe ser señal de ataque por sí solo | ⚠️ **Cumplido con reserva medida** | El tráfico pesado entra como normalidad, pero la validación operativa demostró que **aún genera falsos positivos**: 22,97 % frente al 4,71 % de laboratorio · [system card](../dataset/SYSTEM_CARD_MOTOR.md) |
| Cargas legítimas reproducibles y concurrentes | ✅ **Cumplido** | Generadores versionados con techos calibrados (200 Mbit/s TCP, 50 Mbit/s UDP) |
| Separación correcta de entrenamiento, validación y prueba | ⚠️ **Cumplido en la forma, no en el fondo** | Ningún episodio se reparte (gate `no_episode_split`, 0 violaciones), pero **los 44 perfiles aparecen en las tres particiones**: se mide repetibilidad, no generalización |

### Observación 2 — Variables multicapa

| Requisito | Estado | Evidencia |
|---|---|---|
| Variable de Capa 3 | ✅ **Cumplido** | 9 variables L3 · [diccionario](../fase02-features-multicapa/03-diccionario-multicapa-v2.md) |
| Variable de Capa 4 | ✅ **Cumplido** | 8 variables L4 · ídem |
| Variable de Capa 7 | ✅ **Cumplido** | 11 variables L7, incluida la señal semántica de fallo de autenticación · ídem |
| Definición matemática, ventana temporal y fuente de datos | ✅ **Cumplido** | Diez campos por variable, **generados desde el extractor congelado** · ídem |
| Tratamiento de valores faltantes | ✅ **Cumplido** | Convenio de denominador cero declarado; cero valores faltantes en las 1 552 ventanas |
| Coste de cálculo en línea | ✅ **Cumplido** | Declarado por variable; el motor las calcula cada 10 s en producción |
| Justificación de por qué representa comportamiento | ✅ **Cumplido** | Columna «estado» del diccionario, con las redundancias declaradas |
| **Comparación contra las 14 variables anteriores** | ✅ **Cumplido** | 66,5 % → 88,8 % de detección, **p < 0,001** · [ablación](../fase04-modelado/07-ablacion-multicapa.md) |
| **Evaluación de aporte por capa (ablación)** | ✅ **Cumplido** | Cuatro configuraciones progresivas más retirada por grupo. **Resultado incómodo declarado:** las 8 variables L7 nuevas no aportan detección medible |
| No aceptar una variable solo porque su nombre menciona una capa | ✅ **Cumplido** | `tls_handshake_failure_ratio_60s` **declarada no observable**: 27 efectivas de 28 definidas |

### Requisitos transversales

| Requisito | Estado | Evidencia |
|---|---|---|
| **Validación sin mezcla de sesiones** | ✅ **Cumplido** | Gate `no_episode_split` con 0 violaciones, más los gates de duplicados que cruzan partición, con tolerancia cero |
| **Automatización reproducible** | ✅ **Cumplido** | 1 150 playbooks de Ansible, generadores versionados y `sha256sum -c` sobre los artefactos publicados |
| Prevención de fuga de información | ✅ **Cumplido** | Ventanas estrictamente causales, verificado con prueba unitaria; etiqueta unida tras extraer las variables |
| Métricas con medida de incertidumbre | ✅ **Cumplido** | Intervalos de Wilson en toda proporción y McNemar con corrección de Holm · [significancia](../fase04-modelado/08-significancia-entre-modelos.md) |
| Robustez del resultado frente a la partición | ✅ **Cumplido** | Validación cruzada agrupada por episodio · [validación cruzada](../fase04-modelado/09-validacion-cruzada-y-estabilidad.md) |
| Datos y código disponibles | ✅ **Cumplido** | Dataset, manifiesto y 7 modelos publicados con licencias MIT y CC BY 4.0 |

### Lo que sigue pendiente, declarado

| Requisito | Estado | Qué falta |
|---|---|---|
| Jornada de holdout temporal externa | 🔴 **Pendiente** | Capturar una jornada nueva y reservarla sin participar en entrenamiento ni calibración |
| Seis escenarios legítimos previstos | 🔴 **Pendiente** | SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones |
| Captura multi-sistema-operativo | 🔴 **Pendiente** | Un solo sistema operativo cliente |
| Validación con usuarios reales | 🔴 **Pendiente** | Instrumento y guion listos en [`08-validacion-usuarios/`](../entregables/08-validacion-usuarios/README.md); falta convocar evaluadores |
| Falso positivo aceptable sobre tráfico pesado | 🔴 **Pendiente** | Recalibrar el umbral incluyendo ese tráfico como normalidad y repetir la validación operativa |

> **Ninguna fila queda en «Planificado».** Cada requisito está cumplido con
> evidencia enlazada, cumplido con una reserva medida, o declarado pendiente
> con lo que concretamente falta. Un requisito sin evidencia no se marca como
> cumplido.
