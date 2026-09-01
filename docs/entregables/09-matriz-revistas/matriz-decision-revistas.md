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
| **IJIES** | Supera con reserva | ISSN confirmado, ficha en Scopus, política de revisión y tarifas publicadas, y **publica su tasa de aceptación**, transparencia poco habitual. Fuera de la lista de depredadoras. **La reserva es concreta**: hay que confirmar que su cobertura en Scopus sigue activa, porque TELKOMNIKA, IJECE e IJEECS —revistas del mismo perfil de alto volumen— fueron descontinuadas en 2025 |
| **IJIT** | Supera | Editada por Springer Nature, con ficha activa en Scopus, política editorial pública y archivo mensual. Fuera de la lista de depredadoras. Su respaldo editorial elimina el riesgo de descontinuación que sí tienen las revistas independientes de alto volumen |
| **ISI** | Supera | ISSN confirmado, ficha activa en Scopus, revisión double-blind declarada, doce números al año con archivo y DOI, y página oficial de APC. Mismo editor que IJSSE, cuyo proceso ya se había verificado. Fuera de la lista de depredadoras |

### Descartadas por el filtro

| Revista | Motivo |
|---|---|
| International Journal of Communication Networks and Information Security (IJCNIS) | **Descontinuada de Scopus desde 2022** y presente en la lista de revistas depredadoras consultada |
| Indonesian Journal of Electrical Engineering and Computer Science (IJEECS) | **Descontinuada de Scopus en 2025** |
| Journal of Cyber Security and Mobility | Q4 con APC de 1 300 EUR: no compite en ningún criterio |
| International Journal of Information Security and Privacy | Q4 |
| TELKOMNIKA (IAES) | **Descontinuada de Scopus en 2025.** Publicaba 154 artículos al año: exactamente el perfil de alto volumen que se buscaba, y precisamente por eso su caída importa |
| International Journal of Electrical and Computer Engineering (IAES) | **Descontinuada de Scopus en 2025** |
| Journal of Cybersecurity and Privacy, Electronics, Applied Sciences, Sensors, Future Internet, Information y Computers (MDPI) | **Las siete figuran en la lista de revistas depredadoras consultada.** Es la editorial de mayor volumen del mercado, y queda descartada en bloque |
| IJASEIT | CiteScore 1,5 y volumen en descenso: 343, 257 y 239 artículos en 2023, 2024 y 2025 |

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
| **IJIES** | Disponible | No figura entre las 17 revistas de la lista de control institucional |
| **IJIT** | Disponible | No figura entre las 17 revistas de la lista de control institucional |
| **ISI** | Disponible | No figura entre las 17 revistas de la lista de control institucional |

**Se separa del puntaje a propósito.** Bajar la nota de una revista por estar en la lista mezclaría una restricción administrativa con una evaluación técnica, y haría irreproducible la matriz: los puntajes valen lo mismo hoy y cuando la lista cambie.

> La lista registra a BEEI como Q1 y el APC de IJSSE como USD 700. La consulta directa a las fuentes oficiales el 26/08/2026 da **Q1 por CiteScore y Q3 por SJR** para BEEI y **USD 850** para IJSSE. Las discrepancias se dejan a la vista en vez de promediarse.

---

## 2 ter · Filtro de acceso abierto

**Requisito del autor, 01/09/2026: si no es de acceso abierto, se descarta.** Funciona como un tercer filtro de entrada, igual que los dos anteriores: no toca ningún puntaje, decide quién sigue en carrera.

Se midió con un criterio único para las nueve: el estado de acceso de **todo lo que cada revista publicó desde el 1 de enero de 2025**, según OpenAlex, y una descarga real de PDF sin sesión iniciada para comprobar que el lector no topa con un muro.

| Revista | Estado | Cerrados | Licencia | Veredicto | Detalle |
|---|---|---:|---|---|---|
| **BEEI** | Diamante | 0/682 (0.0 %) | CC BY-SA | Pasa | Su propia portada declara literalmente que «provides immediate open access to all published articles». Ninguno de sus 682 artículos publicados desde enero de 2025 está cerrado |
| **IJACSA** | Diamante | 0/2156 (0.0 %) | — | Pasa | Ninguno de sus 2.156 artículos de 2025 está cerrado |
| **CIT** | Diamante | 0/58 (0.0 %) | CC BY | Pasa | **La única del conjunto registrada en DOAJ.** Ninguno de sus artículos cerrado |
| **IJIES** | **Bronce** | 75/1098 (6.8 %) | ninguna | Pasa | Se lee gratis, pero en la categoría más débil de acceso abierto: **bronce**, sin ninguna licencia declarada. El editor puede retirar el acceso cuando quiera y el lector no tiene derechos de reutilización. Tampoco está en DOAJ |
| **IJSSE** | Híbrido | 34/400 (8.5 %) | CC BY | Pasa | Los PDF se descargan sin pago y llevan licencia CC BY, pero la revista **no está registrada en DOAJ** y un 8,5 % de sus artículos figura como cerrado |
| **ISI** | Híbrido | 81/521 (15.5 %) | CC BY | Pasa | Los PDF se descargan sin pago y llevan licencia CC BY, pero la revista **no está registrada en DOAJ** y un 15,5 % de sus artículos figura como cerrado |
| **ICS** | **Cerrado** | 79/101 (78.2 %) | — | **Descartada** | **El 78,2 % de sus artículos está tras el muro de pago** |
| **ISJ** | **Cerrado** | 89/101 (88.1 %) | — | **Descartada** | **El 88,1 % de sus artículos está tras el muro de pago** |
| **IJIT** | **Cerrado** | 648/714 (90.8 %) | — | **Descartada** | **El 90,8 % de sus artículos está tras el muro de pago.** Abrir uno cuesta USD 3.390 por la vía Open Choice |

**Tres candidatas caen aquí: IJIT, ISJ e ICS.** Las tres eran gratuitas para el autor por la vía de suscripción, y eso las hacía atractivas en el criterio de costo. El filtro deja a la vista lo que ese ahorro costaba: entre el 78 % y el 91 % de sus artículos no los puede leer nadie sin suscripción institucional.

> **Gratis para el autor y abierto para el lector son cosas distintas**, y esta matriz las confundía hasta hoy. IJIT puntuaba 10 en costo por no cobrar APC, sin que nada reflejara que su artículo quedaría cerrado. El filtro corrige esa confusión sin retocar puntajes.

> **No todas las que pasan son iguales.** BEEI y CIT son acceso abierto pleno: cero artículos cerrados y licencia declarada. IJIES es el caso más débil de las que pasan —**bronce, sin licencia**—: se lee gratis hoy porque el editor lo permite, no porque el lector tenga derecho.

### DOAJ: solo CIT está registrada

DOAJ bloquea el acceso automatizado (Cloudflare, HTTP 403 en API, `/toc/` y búsqueda), así que se comprobó por **tres vías independientes**, cada una validada con un **control positivo**: CIT, la única del conjunto que sí consta en DOAJ. Se probaron **todos los ISSN de cada revista**, porque DOAJ registra por cualquiera de ellos.

| Revista | OpenAlex `is_in_doaj` | Wikidata `P5115` | Ficha DOAJ archivada |
|---|:--:|:--:|:--:|
| **CIT** *(control)* | **true** | **`1314-4081`** | **Sí — desde 2018** |
| IJIES | false | ausente | no |
| ISI | false | ausente | no |
| BEEI | false | ausente | no |
| IJSSE | false | ausente | no |

Las tres vías coinciden y el control se detecta en las tres. **Ninguna de las cuatro elegidas figura en DOAJ.** No las descalifica —todas están en Scopus, con editor identificable y política de revisión pública— pero les quita una garantía externa. Ninguna menciona DOAJ en su propio sitio.


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

| Criterio (peso) | IJIES | BEEI | ISJ | IJIT | CIT | IJSSE | ICS | IJACSA | ISI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pertinencia temática (30 %) | 9 | 9 | 9 | 8 | 9 | 9 | 6 | 6 | 7 |
| Visibilidad bibliométrica (25 %) | 8 | 8 | 8 | 7 | 9 | 6 | 9 | 8 | 7 |
| Viabilidad editorial (20 %) | 10 | 9 | 6 | 8 | 5 | 9 | 6 | 10 | 8 |
| Costo y accesibilidad (15 %) | 9 | 8 | 10 | 10 | 6 | 5 | 10 | 3 | 5 |
| Compatibilidad formal (10 %) | 7 | 7 | 7 | 7 | 9 | 8 | 6 | 7 | 7 |
| **PUNTAJE PONDERADO** | **87.5** | **84.0** | **81.0** | **79.5** | **77.5** | **75.5** | **73.5** | **69.5** | **69.0** |
| Datos con fuente primaria | 5/6 | 5/6 | 0/6 | 0/6 | 6/6 | 5/6 | 0/6 | 0/6 | 5/6 |

---

## 5 · Ficha por candidata

### 1. International Journal of Intelligent Engineering and Systems (IJIES) — 87.5 puntos

`INASS · Japón` · ISSN 2185-3118 · [ficha en Scopus](https://www.scopus.com/sourceid/21100199790)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 3,3 · percentil 62 en General Engineering y 52 en General Computer Science, **Q2 en ambas** | ✔ |
| Cuartil SJR | pendiente de verificar en Scimago, hoy bloqueado por Cloudflare | ? |
| Revisión | Publicación unos 2 meses después de la aceptación · **tasa de aceptación declarada: 17,9 % en 2025, 17,8 % en 2024, 14,1 % en 2023** | ✔ |
| Periodicidad | **Mensual desde 2025** · **481 · 556 · 542 artículos** en 2024 · 2025 · 2026, el mayor volumen de las candidatas disponibles | ✔ |
| APC | **USD 300** · **USD 400 desde el 1 de octubre de 2026** · USD 100 extra si no se usa su plantilla · USD 50 por página a partir de la 10.ª | ✔ |
| Plantilla | `IJIES_Format.docx` obligatoria · **límite de 10 páginas** antes del recargo | ✔ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Su alcance nombra ingeniería de redes y computación inteligente, pero lo que decide es su producción: **86 artículos desde 2024 con «intrusion detection», «anomaly detection» o «network security» en el título**. Ninguna otra candidata se acerca a ese volumen temático |
| Visibilidad bibliométrica | **8** | CiteScore 3,3 y Q2 en sus dos categorías. Por debajo del 4,2 de BEEI y CIT, pero con cuartil verificado en la propia revista |
| Viabilidad editorial | **10** | Mensual, con el mayor volumen de las candidatas de acceso abierto —556 al año, frente a 377 de BEEI— y publicación unos 2 meses después de aceptar. **Y publica su tasa de aceptación**, que ninguna otra hace: 17,9 % |
| Costo y accesibilidad | **9** | USD 300 hoy y USD 400 desde octubre: el más bajo de todas las candidatas que cobran, por debajo incluso de los USD 415 de BEEI |
| Compatibilidad formal | **7** | Plantilla propia obligatoria y **límite de 10 páginas**: la mitad que CIT. Este artículo pagaría páginas adicionales |

### 2. Bulletin of Electrical Engineering and Informatics (BEEI) — 84.0 puntos

`IAES · Indonesia` · ISSN 2089-3191 · [ficha en Scopus](https://www.scopus.com/sourceid/21100826382)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 4,2 · percentil 65 en Computer Networks and Communications | ✔ |
| Cuartil SJR | Q3 · la revista declara además Q1 por CiteScore | ~ |
| Revisión | Single-blind, ≥2 revisores; 8–12 semanas declaradas | ✔ |
| Periodicidad | Bimestral · 76 artículos en el número de agosto de 2026 · **377 artículos en 2025**, 453 en 2024 y 415 en 2023 | ✔ |
| APC | USD 415 hasta 8 páginas · USD 50 por página adicional · USD 830 si es autor único | ✔ |
| Plantilla | DOCX oficial disponible | ✔ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **9** | Su alcance declara explícitamente redes de comunicaciones, seguridad de redes, aprendizaje automático y ciberseguridad: los cuatro ejes del artículo |
| Visibilidad bibliométrica | **8** | CiteScore 4,2 y percentil 65, el más alto de las candidatas verificadas |
| Viabilidad editorial | **9** | Bimestral con 76 artículos por número y ciclo declarado de 8 a 12 semanas. Su volumen anual (377) es menor que el de IJIES (556) |
| Costo y accesibilidad | **8** | USD 415 con coautoría —USD 830 si fuera autor único—, por encima de los USD 300 de IJIES y por debajo de los USD 850 de ISI e IJSSE |
| Compatibilidad formal | **7** | Plantilla disponible, pero el límite base de 8 páginas obliga a comprimir o a pagar por página adicional |

### 3. Information Security Journal: A Global Perspective — 81.0 puntos

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
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción. El acceso abierto opcional cuesta USD 3.390, pero nadie está obligado a tomarlo |
| Compatibilidad formal | **7** | Editorial mayor con formato estándar; requisitos concretos sin verificar |

### 4. International Journal of Information Technology (IJIT) — 79.5 puntos

`Springer Nature · BVICAM, Nueva Delhi` · ISSN 2511-2104 · [ficha en Scopus](https://www.scopus.com/sourceid/21101022413)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 2,6 · h-index 23 | ~ |
| Cuartil SJR | **Q2** | ~ |
| Revisión | pendiente de verificar en las instrucciones para autores | ? |
| Periodicidad | **Mensual** · **661 · 640 artículos** en 2024 y 2025 | ~ |
| APC | **Híbrida: publicar por la vía de suscripción no exige APC**, pero el artículo queda tras el muro de pago. La vía de acceso abierto (Open Choice) cuesta **USD 3.390 · EUR 2.690 · GBP 2.390**. No figura en DOAJ. Medido: de **714 artículos publicados desde 2025, 648 (90,8 %) están cerrados** y solo 29 son de acceso abierto pagado | ~ |
| Plantilla | pendiente de verificar | ? |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **8** | Alcance amplio de tecnologías de la información, menos específico que IJIES, pero con **50 artículos desde 2024** cuyo título nombra detección de intrusiones, de anomalías o seguridad de redes |
| Visibilidad bibliométrica | **7** | Q2 por SJR y respaldo de Springer Nature, pero CiteScore 2,6 está por debajo de IJIES y **el 90,8 % de sus artículos quedan tras el muro de pago**: la vía gratuita reduce el alcance real del trabajo |
| Viabilidad editorial | **8** | Mensual y con el mayor volumen absoluto de las nueve —unos 640 artículos al año—, pero **su tiempo de revisión está sin verificar**: no se le puntúa 10 por un dato que no se conoce |
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción. El acceso abierto opcional cuesta USD 3.390, pero nadie está obligado a tomarlo |
| Compatibilidad formal | **7** | Formato estándar de Springer; requisitos concretos sin verificar |

### 5. Cybernetics and Information Technologies (CIT) — 77.5 puntos

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

### 6. International Journal of Safety and Security Engineering (IJSSE) — 75.5 puntos

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

### 7. Information and Computer Security — 73.5 puntos

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
| Costo y accesibilidad | **10** | Sin APC obligatorio por la vía de suscripción. El acceso abierto opcional cuesta USD 3.390, pero nadie está obligado a tomarlo |
| Compatibilidad formal | **6** | Requisitos sin verificar |

### 8. International Journal of Advanced Computer Science and Applications (IJACSA) — 69.5 puntos

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

### 9. Ingénierie des Systèmes d'Information (ISI) — 69.0 puntos

`IIETA · Francia` · ISSN 1633-1311 · [ficha en Scopus](https://www.scopus.com/sourceid/21100202935)

| Dato | Valor | |
|---|---|:--:|
| CiteScore 2025 | 2,6 · SNIP 0,497 | ✔ |
| Cuartil SJR | **Q3** · SJR 0,236 — el único **Q3** de las candidatas disponibles, que es el cuartil que el autor pidió de preferencia | ✔ |
| Revisión | Double-blind, ≥2 expertos independientes. **No declara plazo**: su página de revisión describe el proceso y las cuatro decisiones posibles, pero ningún tiempo | ? |
| Periodicidad | **12 números al año** · **235 y 305 artículos** en 2024 y 2025 | ✔ |
| APC | USD 850 por artículo aceptado | ✔ |
| Plantilla | DOCX oficial · **extensión preferida de 6 a 12 páginas** · **mínimo 20 referencias** | ✔ |

| Criterio | Puntaje | Justificación |
|---|:--:|---|
| Pertinencia temática | **7** | Su alcance declarado nombra minería de datos, aprendizaje automático y detección de fallos, pero **no** seguridad de redes. Lo que sí hace es publicarla: **11 artículos desde 2024** con detección de intrusiones en el título. Se puntúa por lo que publica, no por cómo se describe — el mismo criterio aplicado a las demás |
| Visibilidad bibliométrica | **7** | CiteScore 2,6 y SJR 0,236. Por debajo de IJIES (3,3) y CIT (4,2), pero con **el cuartil verificado en la propia revista** |
| Viabilidad editorial | **8** | Doce números al año y 305 artículos en 2025: capacidad amplia. No llega a 9 porque **no declara plazo de revisión**, y a un dato desconocido no se le da la nota máxima |
| Costo y accesibilidad | **5** | USD 850, casi el triple que IJIES |
| Compatibilidad formal | **7** | **Extensión preferida de 6 a 12 páginas**, más estrecha de lo que se había registrado y menos de la mitad que CIT. El mínimo de 20 referencias no es obstáculo para este artículo |

> `✔` verificado en fuente primaria · `~` fuente secundaria · `?` pendiente

---

## 6 · Plan A, B, C y D

**Los cuatro planes los fijó el autor el 01/09/2026**, entre las candidatas que superan los tres filtros de entrada. No se derivan del puntaje: se derivan de una decisión, y el puntaje queda a la vista al lado para que la diferencia se pueda discutir.

| | Revista | Puntaje | Acceso | En la lista de control | Por qué en esa posición |
|---|---|---:|---|---|---|
| **Plan A** | IJIES | 87.5 | **Bronce** | No | **El mayor volumen del conjunto abierto** —556 al año en 2025, frente a los 377 de BEEI— con el APC más bajo (USD 300) y publicación 2 meses después de aceptar. Dos reservas: hay que confirmar que sigue activa en Scopus, y su acceso abierto es **bronce sin licencia**, el más débil de los cuatro planes. |
| **Plan B** | ISI | 69.0 | Híbrido | No | El único **Q3** verificado, con 305 artículos al año, licencia **CC BY** y PDF de descarga libre comprobada. En contra: APC de USD 850, extensión de 6 a 12 páginas y **ningún plazo de revisión declarado**. |
| **Plan C** | BEEI | 84.0 | Diamante | **Sí** | **El acceso abierto más sólido de los cuatro** —diamante, CC BY-SA, cero artículos cerrados y declaración explícita en su portada— con el segundo mejor puntaje absoluto (84,0) y 377 artículos en 2025. Su única objeción es administrativa: **figura en la lista de control**. |
| **Plan D** | IJSSE | 75.5 | Híbrido | **Sí** | Encaje temático idéntico al de BEEI y ciclo editorial rápido, con licencia CC BY. Pierde en visibilidad (CiteScore 2,8 frente a 4,2) y su APC de USD 850 duplica al de BEEI. También **figura en la lista de control**. |

### Dos tensiones que el autor asume, y conviene tener escritas

**1. El Plan A es el acceso abierto más débil de los cuatro.** IJIES encabeza por puntaje (87,5), volumen (556 al año) y precio (USD 300), pero su acceso abierto es **bronce sin licencia**: gratis de leer mientras el editor quiera, sin derecho de reutilización y fuera de DOAJ. BEEI —el Plan C— es el más sólido en esto: diamante, CC BY-SA, cero cerrados y declaración explícita en su portada. Si lo que se busca es acceso abierto en sentido estricto, el orden se invertiría.

**2. Los Planes C y D figuran en la lista de control de la coordinación.** Es la razón por la que ambos estaban excluidos hasta hoy. Volver a incluirlos es una decisión del autor y **depende de una pregunta que sigue sin responder**: si la lista inhabilita la revista o solo registra lo ya publicado. Conviene resolverla con la coordinación antes de enviar a cualquiera de las dos.

> Las tres descartadas por acceso —IJIT, ISJ e ICS— conservan su puntaje en las tablas anteriores. No se borran: si el criterio de acceso abierto cambiara, vuelven inmediatamente y sin recalcular nada.


---

## 7 · Justificación

**IJIES encabeza con 87.5 puntos sobre 100**, la puntuación más alta de las nueve candidatas, por delante de BEEI (84.0). Con los tres filtros de entrada aplicados —legitimidad, lista de control y acceso abierto—, es además la única de las cuatro elegidas que no arrastra ninguna objeción administrativa.

### Volumen anual, contado en la misma fuente para todas

El volumen se midió con OpenAlex, que indexa el registro completo de cada revista, para que las cifras sean comparables entre sí y no dependan de cómo publique su índice cada editorial.

| Revista | 2023 | 2024 | 2025 | 2026 | Estado |
|---|---:|---:|---:|---:|---|
| **IJIES** | 389 | 481 | 556 | 542 | Plan A |
| **IJIT** | — | 661 | 640 | — | Disponible |
| IJACSA | 1447 | 1539 | 1347 | 707 | Ya en la lista |
| BEEI | 415 | 453 | 377 | 305 | Ya en la lista |
| IJSSE | 129 | 187 | 253 | 133 | Ya en la lista |
| **ISJ** | 17 | 39 | 62 | 39 | Disponible |
| **ICS** | 44 | 42 | 52 | 47 | Disponible |
| **CIT** | 46 | 43 | 35 | 23 | Disponible |

**La diferencia es de un orden de magnitud.** IJIES e IJIT publican entre diez y quince veces más que CIT, ISJ o ICS. Donde CIT abre 4 números al año, IJIES abre 12.

### El matiz que no hay que perder de vista

> **Más volumen no es lo mismo que más fácil.** IJIES publica su tasa de aceptación —cosa que ninguna otra candidata hace— y es del **17,9 % en 2025**, 17,8 % en 2024 y 14,1 % en 2023. Publica mucho porque recibe mucho, no porque acepte con facilidad.

Lo que un volumen alto sí garantiza es otra cosa, y es real: **más plazas abiertas y menos espera**. IJIES publica unos 2 meses después de aceptar y saca número todos los meses; CIT tarda de 3 a 6 meses solo en la primera decisión y saca cuatro números al año. Esa diferencia se mide en trimestres.

### Por qué IJIES encabeza

1. **Produce este tema en cantidad.** No es una revista de seguridad, pero desde 2024 lleva **86 artículos cuyo título nombra detección de intrusiones, detección de anomalías o seguridad de redes**. Ninguna otra candidata se acerca.
2. **Es la más barata de todas las que cobran:** USD 300 hoy, USD 400 desde el 1 de octubre de 2026 — por debajo incluso de los USD 415 de BEEI.
3. **Es la más rápida:** publicación unos 2 meses después de la aceptación, con número mensual.
4. **Publica su tasa de aceptación.** Que una revista exponga voluntariamente que rechaza al 82 % de lo que recibe es un indicador de higiene editorial, no un defecto.

### El riesgo de IJIES, que es concreto

**Hay que confirmar que su cobertura en Scopus sigue activa antes de enviar nada.** TELKOMNIKA, IJECE e IJEECS —revistas independientes del mismo perfil de alto volumen— fueron **descontinuadas de Scopus en 2025**. Publicar en una revista descontinuada invalidaría el artículo para cualquier requisito de indexación del programa.

Ese riesgo es exactamente lo que hace valioso al Plan B: **IJIT tiene un volumen comparable —unos 640 artículos al año— y está editada por Springer Nature**, de modo que la descontinuación deja de ser una preocupación. Además no cobra APC por la vía de suscripción. Su punto ciego es el opuesto: **no se ha verificado su tiempo de revisión**, y por eso puntúa 8 y no 10 en viabilidad.

### Qué elegir según la restricción

| Si lo que manda es… | La revista es… |
|---|---|
| El volumen y la rapidez | **IJIES** — 556 artículos al año y 2 meses hasta publicar |
| El presupuesto | **IJIT**, **ISJ** o **ICS** — ninguna cobra por la vía de suscripción |
| La seguridad de que la revista no caiga del índice | **IJIT** — respaldo de Springer |
| La certeza sobre el proceso editorial | **CIT** — la única con los seis datos verificados |
| El encaje con un antecedente de detección **y respuesta** | **CIT** |
| La fecha de sustentación | **IJIES**, y solo si su cobertura en Scopus se confirma |

La decisión **no se tomó por cuartil**. Si la visibilidad hubiera pesado el 70 %, como es habitual, el orden habría sido otro y se habría perseguido prestigio a costa del encaje, el coste y el plazo.

---

## 8 · Pendientes antes del envío

Esta matriz **no debe usarse tal cual el día del envío**. Falta:

- **Confirmar que IJIES sigue con cobertura activa en Scopus.** Es la verificación más importante de toda la matriz: TELKOMNIKA, IJECE e IJEECS, del mismo perfil de alto volumen, fueron descontinuadas en 2025. Se comprueba en su ficha de fuente, https://www.scopus.com/sourceid/21100199790, mirando que la cobertura llegue hasta el presente y no tenga aviso de discontinuación.
- **Verificar el tiempo de revisión de IJIT**, hoy sin dato: es lo único que le impide competir por el primer puesto.
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

---

## 9 · Cumplimiento de los criterios pedidos

Los criterios no son los de la rúbrica de la sesión, sino los que fijó el autor a lo largo de la búsqueda. Se auditan uno por uno, sin agregarlos en un puntaje, porque **un criterio incumplido no se compensa con otro**.

| Criterio | IJIES | IJIT | ISI |
|---|:--:|:--:|:--:|
| Cuartil Q3 preferido, Q2 aceptable | ~ | ~ | ✔ |
| Tema afín a ciberseguridad o redes | ✔ | ✔ | ✔ |
| Fácil de publicar | ✘ | ? | ? |
| Fuera de la lista de revistas depredadoras | ✔ | ✔ | ✔ |
| Fuera de la lista de control de la coordinación | ✔ | ✔ | ✔ |
| Publica muchos artículos al año | ✔ | ✔ | ✔ |
| Indexación vigente comprobada | ✘ | ✔ | ✔ |
| Enlace y fuente por cada dato | ✔ | ✘ | ~ |

`✔` cumple · `~` cumple parcialmente · `?` sin dato · `✘` no cumple o sin confirmar

### Detalle

**Cuartil Q3 preferido, Q2 aceptable**

- `~` **IJIES** — Q2 por CiteScore, verificado. **SJR sin verificar**
- `~` **IJIT** — Q2 por SJR, fuente secundaria
- `✔` **ISI** — **Q3 por SJR 0,236**, verificado — el único que da el cuartil preferido

**Tema afín a ciberseguridad o redes**

- `✔` **IJIES** — 86 artículos desde 2024 con detección de intrusiones, de anomalías o seguridad de redes en el título
- `✔` **IJIT** — 50 artículos desde 2024
- `✔` **ISI** — 11 artículos desde 2024, pese a que su alcance no nombra seguridad de redes

**Fácil de publicar**

- `✘` **IJIES** — **Tasa de aceptación declarada: 17,9 %.** Es el único dato real del conjunto, y dice que no es fácil
- `?` **IJIT** — **Sin dato.** No publica su tasa de aceptación
- `?` **ISI** — **Sin dato.** Solo consta la revisión double-blind de unos 2 meses

**Fuera de la lista de revistas depredadoras**

- `✔` **IJIES** — Comprobado contra las 2 779 entradas de la lista consultada
- `✔` **IJIT** — Comprobado contra las 2 779 entradas de la lista consultada
- `✔` **ISI** — Comprobado contra las 2 779 entradas de la lista consultada

**Fuera de la lista de control de la coordinación**

- `✔` **IJIES** — Comprobado contra las 17 revistas registradas
- `✔` **IJIT** — Comprobado contra las 17 revistas registradas
- `✔` **ISI** — Comprobado contra las 17 revistas registradas

**Publica muchos artículos al año**

- `✔` **IJIES** — **556 en 2025**
- `✔` **IJIT** — **640 en 2025**
- `✔` **ISI** — **305 en 2025**

**Indexación vigente comprobada**

- `✘` **IJIES** — **Sin confirmar.** Es el riesgo abierto: TELKOMNIKA, IJECE e IJEECS, del mismo perfil, cayeron de Scopus en 2025
- `✔` **IJIT** — Springer Nature: sin riesgo de descontinuación
- `✔` **ISI** — Ficha activa en Scopus, mismo editor que IJSSE

**Enlace y fuente por cada dato**

- `✔` **IJIES** — 5 de 6 datos en fuente primaria
- `✘` **IJIT** — **0 de 6 en fuente primaria**: todo viene de agregadores
- `~` **ISI** — 5 de 6 en fuente primaria: **no declara plazo de revisión**

### Lectura honesta del cuadro

**Ninguna de las tres cumple los ocho criterios.** Cada una falla en algo distinto, y eso es lo que las hace complementarias en vez de redundantes:

| Revista | Lo que le falta |
|---|---|
| **IJIES** | Confirmar que sigue en Scopus. Es lo único que la separa de cumplirlo todo |
| **IJIT** | Todo su expediente es de segunda mano: 0 de 6 datos en fuente primaria |
| **ISI** | El APC más alto de las tres, USD 850, y la menor producción temática |

**Dos criterios no se pueden cerrar con ninguna candidata.** El primero es «fácil de publicar»: solo IJIES publica su tasa de aceptación, y es del 17,9 %. Las otras dos no publican el dato, así que su casilla queda en `?` y no en `✔` — **no saber no es aprobar**. El segundo es el cuartil Q3 preferido: solo ISI lo tiene verificado; IJIES e IJIT son Q2, que el autor aceptó como alternativa pero no era su primera opción.

> Si «fácil de publicar» pesa más que el volumen, la matriz **no tiene hoy evidencia para responder**, y pedir la tasa de aceptación por correo a IJIT e ISI es más útil que cualquier reordenamiento de puntajes.

### Las que quedaron fuera por volumen

| Revista | Puntaje | Artículos en 2025 |
|---|---:|---:|
| ISJ | 81.0 | **62** |
| CIT | 77.5 | **35** |
| ICS | 73.5 | **52** |

Con el listón en 200 artículos al año, estas tres salen pese a puntuar alto. **ISJ puntúa 81,0 y publica 62 al año**: si el volumen dejara de ser un requisito, volvería al segundo puesto.
