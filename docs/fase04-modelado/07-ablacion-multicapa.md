# Ablación por capas y comparación 14 vs 28 variables

> **Generado**: `scripts/modeling/experiments/ablacion_multicapa.py`. Ninguna cifra se transcribe.

Cierra **D-02**, requisito explícito del jurado: demostrar que las variables multicapa se ganan su lugar, en vez de suponerlo.

---

## Protocolo, fijado antes de ejecutar

- El algoritmo **no se re-ajusta**: es el congelado, `Pipeline(StandardScaler, OneClassSVM(rbf, gamma=scale, nu=0.05))`.
- Cada configuración se ajusta **solo con `train`**, calibra su umbral **solo con `validation`** (α = 0,05, misma regla de cuantil) y se evalúa **una vez** sobre `test` y las anomalías.
- **Ninguna configuración sustituye al modelo congelado.** El estudio es descriptivo: mide aporte, no busca un ganador.
- `multicapa-28` **debe reproducir el modelo congelado bit a bit**, o el experimento se detiene.

**Verificación superada:** `multicapa-28` reprodujo el umbral `1.8126087939765134` y los recuentos 13/276 y 158/179 del manifiesto congelado.

---

## Resultados

| Configuración | Vars | FPR benigno | Detección global | Detección Kali |
|---|---:|---:|---:|---:|
| `base-14` | 14 | 2,90 % | 67,0 % | 66,5 % |
| `base+L3` | 17 | 2,17 % | 78,2 % | 78,9 % |
| `base+L3+L4` | 20 | 2,90 % | 87,7 % | 89,4 % |
| **`multicapa-28`** | 28 | 4,71 % | **88,3 %** | 88,8 % |
| `sin-L3` | 19 | 2,90 % | 79,9 % | 79,5 % |
| `sin-L4` | 20 | 5,80 % | 43,0 % | 42,2 % |
| `sin-L7` | 17 | 3,62 % | 78,8 % | 80,1 % |
| `sin-constante` | 27 | 4,71 % | 88,3 % | 88,8 % |

### Con intervalos de confianza

| Configuración | Detección Kali | IC 95 % |
|---|---|---|
| `base-14` | 107/161 = **66,5 %** | [58,9 – 73,3] |
| `base+L3` | 127/161 = **78,9 %** | [71,9 – 84,5] |
| `base+L3+L4` | 144/161 = **89,4 %** | [83,7 – 93,3] |
| `multicapa-28` | 143/161 = **88,8 %** | [83,0 – 92,8] |

---

## Grupos de variables

| Grupo | Nuevas en v2 | Total en v2 |
|---|---|---:|
| `L3` | `ttl_mean_10s`, `fragment_ratio_10s`, `protocol_diversity_30s` | 9 |
| `L4` | `tcp_retransmission_ratio_10s`, `flow_duration_mean_30s`, `tx_rx_byte_ratio_30s` | 8 |
| `L7` | `http_request_rate_60s`, `http_method_entropy_60s`, `http_auth_failure_ratio_60s`, `dns_query_rate_60s`, `unique_dns_name_ratio_60s`, `tls_handshake_failure_ratio_60s`, `tls_version_ratio_60s`, `http_status_5xx_ratio_60s` | 11 |

---

## Pruebas pareadas de McNemar

Sobre **las mismas ventanas**, así que la comparación es pareada. Con recuentos pequeños se usa la binomial exacta, no la aproximación ji².

| Pregunta | Solo A | Solo B | p | |
|---|---:|---:|---:|---|
| ¿Aporta la expansión multicapa completa?<br>`base-14` vs `multicapa-28` | 5 | 43 | &lt; 0,001 | **significativo** |
| ¿Aportan las 8 variables L7 nuevas?<br>`base+L3+L4` vs `multicapa-28` | 5 | 6 | 1,000 | no significativo |
| ¿Aportan las 6 variables L3+L4 nuevas?<br>`base-14` vs `base+L3+L4` | 4 | 41 | &lt; 0,001 | **significativo** |
| ¿Cuánto sostiene el grupo L4?<br>`sin-L4` vs `multicapa-28` | 0 | 81 | &lt; 0,001 | **significativo** |

---

## Qué contesta esto

### 1 · La expansión multicapa está justificada

Pasar de 14 a 28 variables sube la detección sobre ataques genuinos de **66,5 %** a **88,8 %**, y la diferencia es **estadísticamente significativa** (McNemar exacto, p &lt; 0,001: 43 ventanas que solo detecta el multicapa frente a 5 que solo detecta la base).

Es la respuesta directa al requisito del jurado: las variables multicapa **no se supusieron útiles, se midieron**.

### 2 · Pero «hacen falta las 28» no se sostiene

> `base+L3+L4` usa **20 variables** y consigue **89,4 %** de detección sobre Kali —frente al 88,8 % del contrato completo— con **8 falsos positivos en vez de 13**.

McNemar no encuentra diferencia de detección: p = 1,000, con 5 y 6 ventanas discordantes. **Las 8 variables L7 nuevas no aportan detección medible y cuestan 5 falsos positivos adicionales.**

Es un resultado incómodo y se declara tal cual. Un jurado que pregunte «¿por qué 28 y no 20?» tiene razón en preguntarlo.

### 3 · Por qué NO se promueve la configuración de 20

Promoverla **repetiría exactamente el error** que la model card declara: elegir un modelo por ganar una comparación sobre el mismo conjunto de prueba con el que se midió todo lo demás. La ventaja de `base+L3+L4` hereda el mismo sesgo optimista.

**El modelo congelado sigue congelado.** Adoptar 20 variables exige un protocolo nuevo, con el criterio fijado de antemano y una evaluación reservada que nadie haya mirado. Eso es trabajo futuro, no una conclusión de este estudio.

### 4 · La capa 4 es la que sostiene el sistema

Retirar el grupo L4 completo hunde la detección global a **43,0 %** y sube el falso positivo a **5,80 %**. McNemar: **81 ventanas** se pierden y **0** se ganan. Es el grupo crítico, y tiene sentido: los ataques del corpus son mayoritariamente de comportamiento de transporte —ráfagas de SYN, escaneo de puertos, sondeo UDP—.

### 5 · La variable no observable aporta exactamente cero

`sin-constante` da resultados **idénticos** al contrato completo: 13/276 y 158/179, mismo umbral. Confirma numéricamente lo que el diccionario ya declaraba: `tls_handshake_failure_ratio_60s` no es una señal, y el corpus debe reportarse como **27 variables efectivas**. De paso valida la bancada: una variable constante *debe* dar cero diferencia, y la da.

### 6 · Que L7 no aporte al modelo no significa que sobre

El motor en producción usa `http_auth_failure_ratio_60s` en un **detector heurístico independiente**, que en F6 detectó un rociado de contraseñas real **por sí solo**, sin ayuda del modelo, con 6,1 s de adelanto.

Las variables L7 no ganan su lugar **dentro del vector del OCSVM**; sí lo ganan **como reglas explícitas** sobre la señal semántica. Son dos preguntas distintas y conviene no confundirlas.

---

## Limitación de este estudio

Todas las configuraciones se evalúan sobre los **mismos** `test` y anomalías usados en la calibración original. Los valores **absolutos** heredan el sesgo optimista declarado en la model card. Lo que este estudio sostiene es la comparación **relativa** entre configuraciones —para la que el umbral se calibró por separado en `validation`, sin que ninguna mirara `test`—, no el desempeño real esperable.

---

## Detección por familia

| Familia | `base-14` | `base+L3+L4` | `multicapa-28` | `sin-L7` |
|---|---:|---:|---:|---:|
| `AUTH-FAIL-50` | 1/6 | 1/6 | 3/6 | 2/6 |
| `DNS-NX-200` | 6/6 | 6/6 | 6/6 | 4/6 |
| `KALI-DNS-ENTROPY-50` | 21/21 | 21/21 | 21/21 | 1/21 |
| `KALI-PASSWORD-SPRAY-50` | 15/29 | 12/29 | 16/29 | 17/29 |
| `KALI-PORT-SCAN` | 20/20 | 20/20 | 20/20 | 20/20 |
| `KALI-PORT-SCAN-WIDE` | 20/20 | 20/20 | 20/20 | 20/20 |
| `KALI-SYN-RATE-50` | 31/31 | 31/31 | 26/31 | 31/31 |
| `KALI-UDP-PROBE-50` | 0/40 | 40/40 | 40/40 | 40/40 |
| `SYN-RATE-10` | 6/6 | 6/6 | 6/6 | 6/6 |
