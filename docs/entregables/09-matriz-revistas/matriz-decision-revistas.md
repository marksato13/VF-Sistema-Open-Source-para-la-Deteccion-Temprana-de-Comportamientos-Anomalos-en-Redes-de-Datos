# Matriz de decisión de revistas científicas

**Proyecto:** Sistema open source para la detección temprana de comportamientos anómalos en redes de datos
**Autores:** Rubén Mark Salazar Tocas · Uziel Elias Sauñe Fernandez
**Curso:** Investigación V · Sesión 04
**Fecha de consulta de todos los datos:** 26 de agosto de 2026

> **Generada**, no redactada a mano: `scripts/entregables/generar_matriz_revistas.py`.
> Los puntajes ponderados se calculan; ninguno se transcribe.

---

## 1 · El artículo que se quiere publicar

Antes de puntuar hay que saber qué se compara contra cada alcance editorial.

| Elemento | En este proyecto |
|---|---|
| **Problema** | Detección temprana de comportamientos anómalos en redes de datos |
| **Método** | Aprendizaje no supervisado (OCSVM) sobre 28 variables multicapa L3/L4/L7 extraídas de telemetría causal |
| **Sistema** | Control inline: bloqueo automático con nftables en el router del laboratorio |
| **Dominio** | Redes, ciberseguridad y protección de infraestructura |
| **Contribución** | Validación de un sistema desplegado, con la brecha medida entre el error de laboratorio (4,71 %) y el de operación (23–26 %) |

---

## 2 · Filtro de legitimidad

**La legitimidad no se pondera: es un filtro de entrada.** Una candidata que no lo supera sale de la matriz por completo, sin importar cuánto puntúe en lo demás.

| Revista | Resultado | Evidencia |
|---|---|---|
| **BEEI** | Supera | ISSN confirmado, ficha activa en Scopus, política de revisión por pares publicada, archivo de números con DOI, APC transparente y editor identificable. Fuera de la lista de revistas depredadoras consultada |
| **IJSSE** | Supera | ISSN confirmado, ficha activa en Scopus, revisión double-blind declarada, archivo de números con DOI y página oficial de APC. Fuera de la lista de revistas depredadoras consultada |
| **ISJ** | Supera | Editorial de trayectoria reconocida, ficha activa en Scopus e indexación adicional en ESCI. Fuera de la lista de revistas depredadoras consultada |
| **ICS** | Supera | Editorial de trayectoria reconocida y ficha activa en Scopus. Fuera de la lista de revistas depredadoras consultada |
| **IJACSA** | Supera con reserva | Ficha activa en Scopus e indexación en WoS ESCI, y fuera de la lista de depredadoras consultada. Se registra que su reputación editorial es más discutida que la de las demás candidatas |

### Descartadas por el filtro

| Revista | Motivo |
|---|---|
| International Journal of Communication Networks and Information Security (IJCNIS) | **Descontinuada de Scopus desde 2022** y presente en la lista de revistas depredadoras consultada |
| Indonesian Journal of Electrical Engineering and Computer Science (IJEECS) | **Descontinuada de Scopus en 2025** |
| Journal of Cyber Security and Mobility | Q4 con APC de 1 300 EUR: no compite en ningún criterio |
| International Journal of Information Security and Privacy | Q4 |

> Sobre la condición de depredadora: no se afirma una certificación absoluta. Se declara que cada candidata **supera los filtros documentales aplicados** —ISSN, ficha de Scopus, política de revisión, archivo con DOI, APC transparente y editor identificable— y que debe reverificarse antes del envío.

---

## 3 · Criterios y pesos

| Criterio | Peso | Regla de puntuación |
|---|---:|---|
| Pertinencia temática | 30 % | Coincidencia entre el alcance editorial declarado y el problema, método y dominio del artículo |
| Visibilidad bibliométrica | 25 % | CiteScore, percentil y cuartil SJR identificados por separado, con su fuente |
| Viabilidad editorial | 20 % | Tipo de revisión, tiempo declarado, periodicidad y capacidad de publicación |
| Costo y accesibilidad | 15 % | APC vigente, cargos por página y acceso abierto |
| Compatibilidad formal | 10 % | Plantilla, límite de páginas y requisitos de envío |
| **Total** | **100 %** | |

**Fórmula:** `aporte = puntaje × peso / 10`, con puntajes de 0 a 10 y total sobre 100.

Ningún criterio supera el 30 %, por debajo del techo del 35–40 % recomendado. La pertinencia temática pesa más que la visibilidad **a propósito**: un mal encaje produce rechazo de escritorio por muy alto que sea el cuartil.

---

## 4 · Matriz

| Criterio (peso) | BEEI | ISJ | IJSSE | ICS | IJACSA |
|---|---:|---:|---:|---:|---:|
| Pertinencia temática (30 %) | 9 | 9 | 9 | 6 | 6 |
| Visibilidad bibliométrica (25 %) | 8 | 8 | 6 | 9 | 8 |
| Viabilidad editorial (20 %) | 9 | 4 | 9 | 5 | 10 |
| Costo y accesibilidad (15 %) | 8 | 10 | 5 | 10 | 3 |
| Compatibilidad formal (10 %) | 7 | 7 | 8 | 6 | 7 |
| **PUNTAJE PONDERADO** | **84.0** | **77.0** | **75.5** | **71.5** | **69.5** |
| Datos con fuente primaria | 5/6 | 0/6 | 5/6 | 0/6 | 0/6 |

---

## 5 · Ficha por candidata

### 1. Bulletin of Electrical Engineering and Informatics (BEEI) — 84.0 puntos

`IAES · Indonesia` · ISSN 2089-3191 · [ficha en Scopus](https://www.scopus.com/sourceid/21100826382)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 4,2 · percentil 65 en Computer Networks and Communications | ✔ |
| Cuartil SJR | Q3 · la revista declara además Q1 por CiteScore | ~ |
| Revisión | Single-blind, ≥2 revisores; 8–12 semanas declaradas | ✔ |
| Periodicidad | Bimestral · 76 artículos en el número de agosto de 2026 | ✔ |
| APC | USD 415 hasta 8 páginas · USD 50 por página adicional · USD 830 si es autor único | ✔ |
| Plantilla | DOCX oficial disponible | ✔ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Su alcance declara explícitamente redes de comunicaciones, seguridad de redes, aprendizaje automático y ciberseguridad: los cuatro ejes del artículo |
| Visibilidad bibliométrica | **8** | CiteScore 4,2 y percentil 65, el más alto de las candidatas verificadas |
| Viabilidad editorial | **9** | Bimestral con 76 artículos por número: alta capacidad y ciclo declarado corto |
| Costo y accesibilidad | **8** | USD 415 con coautoría, el más bajo de las candidatas con APC |
| Compatibilidad formal | **7** | Plantilla disponible, pero el límite base de 8 páginas obliga a comprimir o a pagar por página adicional |

### 2. Information Security Journal: A Global Perspective — 77.0 puntos

`Taylor & Francis · Reino Unido` · ISSN 1939-3555 · [ficha en Scopus](https://www.scopus.com/sourceid/19700187807)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | pendiente de verificar en la ficha de Scopus | ? |
| Cuartil SJR | Q2 como mejor cuartil · SJR 0,489 · h-index 33 | ~ |
| Revisión | pendiente de verificar en las instrucciones para autores | ? |
| Periodicidad | 6 números al año · 21 artículos en el volumen 34 (2025) | ~ |
| APC | Híbrida: publicar por la vía de suscripción no exige APC | ~ |
| Plantilla | pendiente de verificar | ? |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Su alcance nombra seguridad de redes y control de acceso; publica trabajos sobre ataques SSH y denegación de servicio HTTP, las mismas familias del corpus |
| Visibilidad bibliométrica | **8** | Mejor cuartil Q2 y h-index 33, el más alto tras Emerald |
| Viabilidad editorial | **4** | Solo 21 artículos en el volumen 34: capacidad muy limitada y, por tanto, probabilidad de aceptación baja |
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción |
| Compatibilidad formal | **7** | Editorial mayor con formato estándar; requisitos concretos sin verificar |

### 3. International Journal of Safety and Security Engineering (IJSSE) — 75.5 puntos

`IIETA · Canadá` · ISSN 2041-904X · [ficha en Scopus](https://www.scopus.com/sourceid/21100785501)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 2,8 · percentil 60 en Safety, Risk, Reliability and Quality | ✔ |
| Cuartil SJR | Q3 | ~ |
| Revisión | Double-blind, ≥2 expertos independientes; ~2 meses | ✔ |
| Periodicidad | 12 números regulares al año · 20 artículos en el número de julio de 2026 | ✔ |
| APC | USD 850 por artículo aceptado, sin cargo por página | ✔ |
| Plantilla | DOCX oficial disponible | ✔ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Declara seguridad informática, evaluación de amenazas, ciberseguridad y protección de infraestructura crítica; publica de forma habitual detección de intrusiones con aprendizaje automático |
| Visibilidad bibliométrica | **6** | CiteScore 2,8 y percentil 60: por debajo de BEEI en ambos indicadores |
| Viabilidad editorial | **9** | Doce números al año y revisión double-blind de unos dos meses |
| Costo y accesibilidad | **5** | USD 850, el doble que BEEI |
| Compatibilidad formal | **8** | Plantilla disponible y sin límite estrecho de páginas declarado |

### 4. Information and Computer Security — 71.5 puntos

`Emerald · Reino Unido` · ISSN 2056-4961 · [ficha en Scopus](https://www.scopus.com/sourceid/21100421900)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | pendiente de verificar en la ficha de Scopus | ? |
| Cuartil SJR | Q2 como mejor cuartil · Q3 en Computer Networks and Communications, Information Systems y Software · h-index 60 | ~ |
| Revisión | pendiente de verificar | ? |
| Periodicidad | pendiente de verificar | ? |
| APC | Híbrida: no exige APC por la vía de suscripción | ~ |
| Plantilla | pendiente de verificar | ? |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **6** | Cubre la categoría de redes, pero su centro editorial se inclina a factores humanos, concienciación y cumplimiento de políticas: un artículo puramente técnico corre riesgo de quedar fuera de foco |
| Visibilidad bibliométrica | **9** | h-index 60, el más alto de todas las candidatas |
| Viabilidad editorial | **5** | Sin datos verificados de tiempo ni periodicidad |
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción |
| Compatibilidad formal | **6** | Requisitos sin verificar |

### 5. International Journal of Advanced Computer Science and Applications (IJACSA) — 69.5 puntos

`TheSAI · Reino Unido` · ISSN 2158-107X · [ficha en Scopus](https://www.scopus.com/sourceid/21100867241)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 3,4 | ~ |
| Cuartil SJR | Q3 | ~ |
| Revisión | Doble ciego con al menos tres revisores; decisión en unas 3 semanas | ~ |
| Periodicidad | Mensual, con fecha de cierre fija cada mes | ~ |
| APC | GBP 800 · GBP 750 para estudiantes y revisores | ~ |
| Plantilla | Plantilla propia obligatoria | ~ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **6** | Declara cubrir «todas las ramas de las ciencias de la computación»: alcance amplio y por tanto menos específico que las tres primeras |
| Visibilidad bibliométrica | **8** | CiteScore 3,4 y doble indexación en Scopus y WoS ESCI |
| Viabilidad editorial | **10** | Mensual y con decisión declarada en unas tres semanas: la más rápida |
| Costo y accesibilidad | **3** | GBP 800, el más alto de todas las candidatas |
| Compatibilidad formal | **7** | Plantilla propia obligatoria, que exige reformatear |

> `✔` verificado en fuente primaria · `~` fuente secundaria · `?` pendiente

---

## 6 · Plan A, B y C

> **El orden por debajo del Plan A es provisional.** Solo BEEI e IJSSE tienen sus datos sensibles verificados en fuente primaria; las otras tres se puntuaron con fuentes secundarias. Una verificación completa **puede reordenar las posiciones 2 a 5**, y por eso la sección 8 enumera lo que falta comprobar antes del envío.
>
> Se presenta igual, con el orden y sus lagunas a la vista, porque ocultar la diferencia de verificación entre candidatas sería el error más grave de esta matriz.

**Plan A — BEEI (84.0)**

**Plan B — ISJ (77.0)**

**Plan C — IJSSE (75.5)**

| | Revista | Puntaje | Por qué en esa posición |
|---|---|---:|---|
| **Plan A** | BEEI | 84.0 | Gana en tres de los cinco criterios y es la que más datos tiene **verificados en fuente primaria** (5 de 6). Mejor combinación de encaje temático, visibilidad y coste. |
| **Plan B** | ISJ | 77.0 | Empata en pertinencia con las mejores y **no exige APC**, pero publica solo 21 artículos al año: su bajo puntaje de viabilidad refleja una probabilidad de aceptación mucho menor. |
| **Plan C** | IJSSE | 75.5 | Encaje temático idéntico al de BEEI y ciclo editorial rápido, pero pierde en visibilidad (CiteScore 2,8 frente a 4,2) y su APC duplica al de BEEI. |
| 4.º | ICS | 71.5 | El mayor prestigio de la lista (h-index 60), pero su centro editorial se inclina a factores humanos y buena parte de sus datos sigue sin verificar. |
| 5.º | IJACSA | 69.5 | La más rápida de todas, pero de alcance genérico y con el APC más alto. |

---

## 7 · Justificación

**BEEI es el Plan A** porque obtiene el puntaje ponderado más alto (84.0 sobre 100) y, sobre todo, porque es la candidata con más datos verificados en fuente primaria (5 de 6). Su alcance editorial nombra de forma explícita los cuatro ejes del artículo —redes de comunicaciones, seguridad de redes, aprendizaje automático y ciberseguridad—, presenta el CiteScore y el percentil más altos del conjunto (4,2 y 65) y su APC de USD 415 con coautoría es el más bajo entre las revistas que cobran.

**No se eligió ISJ** pese a no exigir APC: publica solo 21 artículos al año, de modo que su capacidad —y por tanto la probabilidad de aceptación— es sustancialmente menor. Se conserva como Plan B precisamente porque su coste nulo la hace la mejor alternativa si el presupuesto desaparece.

**No se eligió IJSSE** aunque su encaje temático es equivalente: pierde en visibilidad bibliométrica y su APC duplica al del Plan A, sin ofrecer a cambio una ventaja editorial que lo compense.

La decisión **no se tomó por cuartil**. Si la visibilidad hubiera pesado el 70 %, como es habitual, el orden habría sido otro y se habría perseguido prestigio a costa del encaje y del plazo. Aquí la pertinencia temática pesa más que la visibilidad porque un mal encaje produce rechazo de escritorio antes de llegar a revisión.

---

## 8 · Pendientes antes del envío

Esta matriz **no debe usarse tal cual el día del envío**. Falta:

- Verificar el **cuartil SJR** de las cinco candidatas en Scimago. Aquí figura como fuente secundaria: **el percentil de Scopus no es el cuartil SJR**, y confundirlos invalidaría el criterio de visibilidad.
- Completar en fuente primaria los datos marcados con `?` en ISJ, ICS e IJACSA: CiteScore, tipo y tiempo de revisión, periodicidad y plantilla.
- Reverificar el APC de las cinco: cambia sin aviso. El de IJSSE ya pasó de USD 700 a USD 850 entre dos consultas.
- Confirmar por escrito con la coordinación académica el requisito exacto de cuartil o índice del programa: es un **filtro**, no un criterio ponderado.
- Comprobar que la extensión del artículo cabe en el límite base de 8 páginas de BEEI, o presupuestar el coste por página adicional.
