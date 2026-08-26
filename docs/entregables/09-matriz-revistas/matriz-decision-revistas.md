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
| **CIT** | Supera | ISSN confirmado, ficha activa en Scopus, indexación adicional en Web of Science ESCI, DOAJ, INSPEC, ACM Digital Library y Engineering Village; adhesión declarada a las Core Practices de COPE, revisión por pares en tres fases con cribado antiplagio iThenticate y archivo de números desde 2001. Fuera de la lista de revistas depredadoras consultada |

### Descartadas por el filtro

| Revista | Motivo |
|---|---|
| International Journal of Communication Networks and Information Security (IJCNIS) | **Descontinuada de Scopus desde 2022** y presente en la lista de revistas depredadoras consultada |
| Indonesian Journal of Electrical Engineering and Computer Science (IJEECS) | **Descontinuada de Scopus en 2025** |
| Journal of Cyber Security and Mobility | Q4 con APC de 1 300 EUR: no compite en ningún criterio |
| International Journal of Information Security and Privacy | Q4 |

> Sobre la condición de depredadora: no se afirma una certificación absoluta. Se declara que cada candidata **supera los filtros documentales aplicados** —ISSN, ficha de Scopus, política de revisión, archivo con DOI, APC transparente y editor identificable— y que debe reverificarse antes del envío.

---

## 2 bis · Filtro de disponibilidad

La coordinación mantiene una **lista de control de artículos** con 17 revistas ya registradas. Tres de las candidatas figuran en ella, de modo que la lista funciona como un **segundo filtro de entrada**: no cambia el puntaje de ninguna revista, decide cuáles siguen disponibles.

| Revista | Lista de control | Detalle |
|---|---|---|
| **BEEI** | **Ya registrada** | N.º 8 de la lista de control institucional, registrada como Q1 · Indonesia · USD 385 |
| **IJSSE** | **Ya registrada** | N.º 7 de la lista de control institucional, registrada como Q3 · Reino Unido · USD 700 |
| **ISJ** | Disponible | No figura entre las 17 revistas de la lista de control institucional |
| **ICS** | Disponible | No figura entre las 17 revistas de la lista de control institucional |
| **IJACSA** | **Ya registrada** | N.º 5 de la lista de control institucional, registrada como Q3 · Reino Unido · USD 1 100 |
| **CIT** | Disponible | No figura entre las 17 revistas de la lista de control institucional |

**Se separa del puntaje a propósito.** Bajar la nota de una revista por estar en la lista mezclaría una restricción administrativa con una evaluación técnica, y haría irreproducible la matriz: los puntajes valen lo mismo hoy y cuando la lista cambie.

> La lista registra a BEEI como Q1 y el APC de IJSSE como USD 700. La consulta directa a las fuentes oficiales el 26/08/2026 da **Q1 por CiteScore y Q3 por SJR** para BEEI y **USD 850** para IJSSE. Las discrepancias se dejan a la vista en vez de promediarse.

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

| Criterio (peso) | BEEI | ISJ | CIT | IJSSE | ICS | IJACSA |
|---|---:|---:|---:|---:|---:|---:|
| Pertinencia temática (30 %) | 9 | 9 | 9 | 9 | 6 | 6 |
| Visibilidad bibliométrica (25 %) | 8 | 8 | 9 | 6 | 9 | 8 |
| Viabilidad editorial (20 %) | 9 | 6 | 5 | 9 | 6 | 10 |
| Costo y accesibilidad (15 %) | 8 | 10 | 6 | 5 | 10 | 3 |
| Compatibilidad formal (10 %) | 7 | 7 | 9 | 8 | 6 | 7 |
| **PUNTAJE PONDERADO** | **84.0** | **81.0** | **77.5** | **75.5** | **73.5** | **69.5** |
| Datos con fuente primaria | 5/6 | 0/6 | 6/6 | 5/6 | 0/6 | 0/6 |

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

### 2. Information Security Journal: A Global Perspective — 81.0 puntos

`Taylor & Francis · Reino Unido` · ISSN 1939-3555 · [ficha en Scopus](https://www.scopus.com/sourceid/19700187807)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | pendiente de verificar en la ficha de Scopus | ? |
| Cuartil SJR | Q2 como mejor cuartil · SJR 0,489 · h-index 33 | ~ |
| Revisión | pendiente de verificar en las instrucciones para autores | ? |
| Periodicidad | 6 números al año · **36 · 35 · 38 artículos en 2024 · 2025 · 2026**, contados sobre el índice completo de dblp | ~ |
| APC | Híbrida: publicar por la vía de suscripción no exige APC. **No figura en DOAJ**, lo que es coherente con que no haya migrado a acceso abierto de pago | ~ |
| Plantilla | pendiente de verificar | ? |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Su alcance nombra seguridad de redes y control de acceso; publica trabajos sobre ataques SSH y denegación de servicio HTTP, las mismas familias del corpus |
| Visibilidad bibliométrica | **8** | Mejor cuartil Q2 y h-index 33, el más alto tras Emerald |
| Viabilidad editorial | **6** | **Corregido**: la cifra anterior de 21 artículos al año era falsa. El índice de dblp da 35–38, capacidad equivalente a la de CIT, repartida en 6 números al año en vez de 4. Baja de 10 porque el tipo y el tiempo de revisión siguen sin verificar: dos de los cuatro componentes del criterio |
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción |
| Compatibilidad formal | **7** | Editorial mayor con formato estándar; requisitos concretos sin verificar |

### 3. Cybernetics and Information Technologies (CIT) — 77.5 puntos

`Instituto de TIC · Academia Búlgara de Ciencias · Bulgaria` · ISSN 1314-4081 · [ficha en Scopus](https://www.scopus.com/sourceid/21100199814)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 4,2 · SNIP 0,854 · la revista publica ambos en su página de indexación | ✔ |
| Cuartil SJR | **Q2** · SJR 0,456 · h-index 27 · además Web of Science ESCI con factor de impacto 1,7 (Q3) | ✔ |
| Revisión | Single-blind, ≥2 revisores, en tres fases · **3–6 meses** en modo regular · 1–3 meses en vía rápida · cribado de texto generado por IA con rechazo sin derecho a revisión por encima del 20 % | ✔ |
| Periodicidad | 4 números al año · **46 · 43 · 42 artículos en 2023 · 2024 · 2025** y 23 en los dos primeros números de 2026 | ✔ |
| APC | **600 EUR a partir del 1 de septiembre de 2026** · vía rápida 1 200 EUR · solo se paga si el artículo se acepta | ✔ |
| Plantilla | Plantilla DOCX oficial · hasta **20 páginas** · envío por correo electrónico | ✔ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Su alcance declara tecnologías de comunicación entre computadoras, aprendizaje profundo y automático, y reconocimiento de patrones. Lo decisivo no es el alcance sino lo que publica: entre 2024 y 2026 sacó detección de intrusiones con IA explicable, detección de intrusiones con redes convolucionales, detección de DDoS entre conjuntos de datos y una arquitectura de **detección y mitigación** de DDoS, que es el análogo más cercano al control inline de este proyecto entre todas las candidatas |
| Visibilidad bibliométrica | **9** | Única candidata con cuartil **Q2 verificado en fuente primaria** y, a la vez, factor de impacto en Web of Science. CiteScore 4,2, igual al de BEEI, pero con SJR 0,456 frente al Q3 de BEEI |
| Viabilidad editorial | **5** | El punto débil: 3–6 meses hasta la primera decisión, el plazo más largo del conjunto. Su capacidad, en cambio, es estable y comparable a la de ISJ e ICS: 46, 43 y 42 artículos en 2023, 2024 y 2025, contados sobre los PDF de cada número |
| Costo y accesibilidad | **6** | 600 EUR desde septiembre de 2026, por debajo de los USD 850 de IJSSE pero por encima de los USD 415 de BEEI |
| Compatibilidad formal | **9** | Límite de 20 páginas, frente a las 8 de BEEI: el artículo cabe entero sin pagar por página adicional. Plantilla oficial y envío por correo |

### 4. International Journal of Safety and Security Engineering (IJSSE) — 75.5 puntos

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

### 5. Information and Computer Security — 73.5 puntos

`Emerald · Reino Unido` · ISSN 2056-4961 · [ficha en Scopus](https://www.scopus.com/sourceid/21100421900)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | pendiente de verificar en la ficha de Scopus | ? |
| Cuartil SJR | Q2 como mejor cuartil · Q3 en Computer Networks and Communications, Information Systems y Software · h-index 60 | ~ |
| Revisión | pendiente de verificar | ? |
| Periodicidad | **34 · 38 · 42 artículos en 2023 · 2024 · 2025**, contados sobre el índice completo de dblp | ~ |
| APC | Híbrida: no exige APC por la vía de suscripción. **No figura en DOAJ**, lo que es coherente con que no haya migrado a acceso abierto de pago | ~ |
| Plantilla | pendiente de verificar | ? |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **6** | Cubre la categoría de redes, pero su centro editorial se inclina a factores humanos, concienciación y cumplimiento de políticas: un artículo puramente técnico corre riesgo de quedar fuera de foco |
| Visibilidad bibliométrica | **9** | h-index 60, el más alto de todas las candidatas |
| Viabilidad editorial | **6** | Capacidad creciente y la mayor de las tres disponibles —34, 38 y 42 artículos en 2023, 2024 y 2025—, pero el tipo y el tiempo de revisión siguen sin verificar |
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción |
| Compatibilidad formal | **6** | Requisitos sin verificar |

### 6. International Journal of Advanced Computer Science and Applications (IJACSA) — 69.5 puntos

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

Los planes se asignan **solo entre las candidatas disponibles**, es decir, las que superan el filtro de legitimidad y además no figuran en la lista de control. Los puntajes de las tres ya registradas se conservan a la vista para que la comparación siga siendo completa.

> **El orden por debajo del Plan A es provisional.** Solo BEEI, IJSSE y CIT tienen sus datos sensibles verificados en fuente primaria; ISJ, ICS e IJACSA se puntuaron con fuentes secundarias. Completar esa verificación **puede reordenar las posiciones siguientes**, y por eso la sección 8 enumera lo que falta comprobar antes del envío.
>
> Se presenta así, con las lagunas a la vista, porque ocultar la diferencia de verificación entre candidatas sería el error más grave de esta matriz.
>
> **La distancia entre el Plan A y el Plan B es de medio punto** (77,5 frente a 77,0), menor que lo que puede mover una sola verificación pendiente. Lo que hoy separa a las dos no es el puntaje sino la evidencia: CIT tiene 6 de 6 datos verificados en la propia revista y ISJ tiene 0 de 6.

| | Revista | Puntaje | Estado | Por qué en esa posición |
|---|---|---:|---|---|
| — | BEEI | 84.0 | Ya en la lista de control | Gana en tres de los cinco criterios y tiene 5 de 6 datos **verificados en fuente primaria**. Mejor combinación de encaje temático, visibilidad y coste, pero ya figura en la lista de control. |
| **Plan A** | ISJ | 81.0 | Disponible | **No exige APC** por la vía de suscripción y empata en pertinencia con las mejores. Sube al primer puesto al corregirse su capacidad, que no era de 21 artículos al año sino de 35–38. Su puntaje es el más frágil: 0 de 6 datos verificados en la revista, y el tiempo de revisión sin comprobar. |
| **Plan B** | CIT | 77.5 | Disponible | Puntúa menos, pero es la **única con los seis datos verificados en la propia revista**, la única con Q2 y factor de impacto de Web of Science confirmados, y la única que publica detección **y mitigación**. Su desventaja está declarada: 3–6 meses hasta la primera decisión. |
| — | IJSSE | 75.5 | Ya en la lista de control | Encaje temático idéntico al de BEEI y ciclo editorial rápido, pero pierde en visibilidad (CiteScore 2,8 frente a 4,2) y su APC duplica al de BEEI. Ya figura en la lista de control. |
| **Plan C** | ICS | 73.5 | Disponible | El mayor prestigio de la lista (h-index 60), pero su centro editorial se inclina a factores humanos y buena parte de sus datos sigue sin verificar. |
| — | IJACSA | 69.5 | Ya en la lista de control | La más rápida de todas, pero de alcance genérico, con el APC más alto y ya registrada en la lista de control. |

---

## 7 · Justificación

**ISJ encabeza la aritmética** con 81.0 puntos sobre 100 entre las candidatas disponibles, por delante de CIT (77.5). **BEEI puntúa más alto que ambas (84.0)**, pero queda fuera por el filtro de disponibilidad, no por una debilidad técnica.

### El orden entre el Plan A y el Plan B no está resuelto

Hay que decirlo antes que nada, porque es la debilidad más seria de esta matriz:

| | ISJ | CIT |
|---|---|---|
| Puntaje | **81.0** | 77.5 |
| Datos verificados en la revista | **0 de 6** | **6 de 6** |
| Tipo y tiempo de revisión | Sin verificar | Single-blind · 3–6 meses |

**El Plan A gana en parte por lo que no se sabe de él.** El criterio de viabilidad pondera cuatro componentes —tipo de revisión, tiempo, periodicidad y capacidad— y en ISJ dos están sin verificar, mientras que CIT declara los cuatro y es penalizada precisamente por declarar el plazo más lento del conjunto. Una matriz que premia el desconocimiento está mal construida, y esta lo hace en este punto.

No se corrige inventando una penalización a posteriori, que sería justo el sesgo inverso. Se corrige **verificando**: si el tiempo de revisión de ISJ resulta mayor que los 3–6 meses de CIT, el orden se invierte. Esa única comprobación decide entre Plan A y Plan B y encabeza la lista de pendientes.

### Por qué ISJ está arriba

1. **No cobra.** Es híbrida y publicar por la vía de suscripción no exige APC. Que **no figure en DOAJ** es coherente con que no haya migrado a acceso abierto de pago. Frente a los 600 EUR de CIT, la diferencia es todo el presupuesto del artículo.
2. **Publica las mismas familias de ataque del corpus**: trabajos sobre ataques SSH y denegación de servicio HTTP, que son exactamente dos de las familias etiquetadas.
3. **La objeción que la frenaba era falsa.** Se le había atribuido una capacidad de 21 artículos al año, cifra tomada de una fuente secundaria. El índice completo de dblp da **36, 35 y 38 en 2024, 2025 y 2026**: capacidad equivalente a la de CIT y repartida en seis números al año en vez de cuatro. Corregir ese dato es lo que movió a ISJ del cuarto lugar al primero.

### Por qué CIT sigue siendo la apuesta más segura

Aunque puntúe menos, es la **única candidata con los seis datos sensibles verificados en la propia revista**, y eso tiene un valor que el puntaje no captura.

- **Publica exactamente este problema**, comprobado en sus números y no deducido de su alcance: detección de intrusiones con IA explicable (2024), con redes convolucionales (2026), detección de DDoS entre conjuntos de datos (2026) y una arquitectura de detección **y mitigación** de DDoS (2025). Esa última es el único antecedente, entre las seis candidatas, de un trabajo que no solo detecta sino que responde: el mismo par detección + control inline de este proyecto.
- **Doble indexación verificada:** único caso cuyo Q2 aparece confirmado en la propia revista junto a un factor de impacto de Web of Science (1,7 · Q3 · ESCI).
- **Veinte páginas de límite**, frente a las 8 de BEEI: las 28 variables, la calibración del umbral y la brecha entre error de laboratorio y de operación entran sin recortar ni pagar por página adicional.
- **Su plazo está declarado y es malo:** 3–6 meses hasta la primera decisión. Es una desventaja conocida, que es distinto de una desventaja ausente.

### Cómo decidir

| Si la restricción dominante es… | La revista es… |
|---|---|
| El presupuesto | **ISJ** o **ICS**: ninguna cobra por la vía de suscripción |
| La certeza sobre el proceso editorial | **CIT**: es la única con todo verificado |
| El encaje con un antecedente de detección + respuesta | **CIT** |
| La fecha de sustentación | **Ninguna de las tres.** CIT declara 3–6 meses y las dos híbridas de editorial mayor no publican su plazo |

La decisión **no se tomó por cuartil**. Si la visibilidad hubiera pesado el 70 %, como es habitual, el orden habría sido otro y se habría perseguido prestigio a costa del encaje y del plazo. Aquí la pertinencia temática pesa más que la visibilidad porque un mal encaje produce rechazo de escritorio antes de llegar a revisión.

---

## 8 · Pendientes antes del envío

Esta matriz **no debe usarse tal cual el día del envío**. Falta:

- **Verificar el tipo y el tiempo de revisión de ISJ.** Es la comprobación que decide entre el Plan A y el Plan B: si supera los 3–6 meses de CIT, el orden se invierte. Hoy el Plan A puntúa más alto en parte porque dos componentes de su criterio de viabilidad están sin verificar.
- **Confirmar que ISJ e ICS siguen aceptando la vía de suscripción sin APC.** Su puntaje de coste de 10 sostiene todo su primer puesto; si alguna migró a acceso abierto de pago, cae al último lugar.
- Verificar el **cuartil SJR** de las cinco candidatas en Scimago. Aquí figura como fuente secundaria: **el percentil de Scopus no es el cuartil SJR**, y confundirlos invalidaría el criterio de visibilidad.
- Completar en fuente primaria los datos marcados con `?` en ISJ, ICS e IJACSA: CiteScore, tipo y tiempo de revisión, periodicidad y plantilla.
- Reverificar el APC de las cinco: cambia sin aviso. El de IJSSE ya pasó de USD 700 a USD 850 entre dos consultas.
- Confirmar por escrito con la coordinación académica el requisito exacto de cuartil o índice del programa: es un **filtro**, no un criterio ponderado.
- Comprobar que la extensión del artículo cabe en el límite base de 8 páginas de BEEI, o presupuestar el coste por página adicional.
- **Aclarar con CIT cuál es su APC vigente y desde cuándo.** Hay dos cifras en circulación: su registro en DOAJ declara 360 EUR y sus instrucciones para autores declaran 600 EUR a partir del 1 de septiembre de 2026. Y preguntar si aplica por fecha de envío o por fecha de aceptación: La política dice «600 EUR a partir del 1 de septiembre de 2026» sin precisar el disparador; con una revisión de 3 a 6 meses, un envío de hoy se acepta después de esa fecha en cualquier escenario.
- Pasar el manuscrito por un detector de texto generado por IA antes de enviarlo a CIT: por encima del 20 % la revista rechaza **sin derecho a revisión**.
- Confirmar con la coordinación qué significa exactamente estar en la lista de control: si inhabilita la revista o solo la registra. Toda la sección 2 bis depende de esa respuesta.
