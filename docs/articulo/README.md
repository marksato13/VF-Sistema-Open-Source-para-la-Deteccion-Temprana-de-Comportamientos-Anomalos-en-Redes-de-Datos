# Artículo científico — material de preparación

Documentos de apoyo para redactar y publicar el artículo derivado de la tesis.

## Revistas objetivo

Seleccionadas tras verificar indexación vigente, volumen real de publicación,
presencia de artículos afines al tema y **ausencia en listas de revistas
depredadoras**.

| | Revista | Cuartil | Artículos/año | APC |
|---|---|---|---:|---|
| **1** | [Bulletin of Electrical Engineering and Informatics](https://beei.org/index.php/EEI) · IAES | Q3 (SJR, por confirmar) · Q1 por CiteScore | ≈360 | USD 415 |
| **2** | [International Journal of Safety and Security Engineering](https://www.iieta.org/Journals/IJSSE) · IIETA | Q3 (SJR, por confirmar) | 174 | **USD 850** |

> En BEEI el artículo de **autor único cuesta el doble** (USD 830). Firmar en
> coautoría no es solo correcto: es más barato.

## Mapeo por secciones

[`mapeo-secciones-BEEI-IJSSE.xlsx`](mapeo-secciones-BEEI-IJSSE.xlsx) — cómo
estructuran su artículo diez trabajos afines, cinco de cada revista.

| Hoja | Contenido |
|---|---|
| `Cómo se hizo` | Criterio de selección y precisión de cada cifra |
| `BEEI` | 5 artículos con título, DOI, metadatos y una columna por sección |
| `IJSSE` | Ídem |
| `Patrones` | Lo comparable entre ambas revistas |

**Las cifras se contaron sobre el PDF completo de cada artículo**, no sobre
resúmenes ni metadatos. Los conteos de párrafos son aproximados —bloques
separados por línea en blanco con más de 120 caracteres—; citas, tablas y
figuras son exactas.

Regenerar:

```bash
python3 scripts/articulo/generar_mapeo_revistas.py
```

## Patrones que conviene respetar al escribir

| | BEEI | IJSSE |
|---|---|---|
| Secciones | 4–7 · mediana 6 | 5–7 · mediana 6 |
| Sección dominante | Método, hasta 27 párrafos | Método, hasta 21 párrafos |
| Concentración de citas | Introducción y *Related Work* | *Related Work*, hasta 24 citas |
| Resultados y discusión | 3 de 5 los separan | 3 de 5 los fusionan |
| Referencias totales | 26–54 | 22–34 |
| Conclusión | 1–9 párrafos, casi sin citas | Breve, sin citas |

**El método casi no cita**: es descripción propia. La bibliografía se concentra
al principio del artículo.

## Dos oportunidades detectadas

**Solo 3 de los 10 declaran limitaciones** en una subsección propia. Este
proyecto tiene limitaciones **medidas con intervalos de confianza**, lo que en
este corpus es la excepción, no la norma.

**Los 10 usan datasets públicos** —NSL-KDD, KDD Cup 99, UNSW-NB15, CIC-IDS2017,
ToN-IoT—. Este trabajo usa dataset propio con despliegue real, así que conviene
**adelantarse en la introducción** a la pregunta «¿por qué no un dataset
estándar?»: porque un dataset público no permite medir control en línea ni
falso positivo operativo, que es justamente la contribución.

## Los dos artículos más cercanos al proyecto

| Artículo | Por qué |
|---|---|
| **FL-NDR** (`10.18280/ijsse.160615`) | No solo detecta: **responde**, con tres niveles de acción hasta la cuarentena. Es control inline con otro nombre |
| **Hybrid ML zero-day** (`10.18280/ijsse.150815`) | Un **autocodificador modela el tráfico normal** y marca lo desviado: el mismo principio no supervisado del OCSVM congelado |

## Trazabilidad

| Tema | Documento |
|---|---|
| Resultados y su crítica | [`../entregables/01-evaluacion-critica/`](../entregables/01-evaluacion-critica/informe-evaluacion-critica.md) |
| Datos | [`../dataset/DATASHEET_MULTILAYER_V2.md`](../dataset/DATASHEET_MULTILAYER_V2.md) |
| Modelo | [`../dataset/MODEL_CARD_OCSVM.md`](../dataset/MODEL_CARD_OCSVM.md) |
| Sistema desplegado | [`../dataset/SYSTEM_CARD_MOTOR.md`](../dataset/SYSTEM_CARD_MOTOR.md) |
| Ablación y significancia | [`../fase04-modelado/07-ablacion-multicapa.md`](../fase04-modelado/07-ablacion-multicapa.md) · [`08-significancia-entre-modelos.md`](../fase04-modelado/08-significancia-entre-modelos.md) |

## Corrección de datos — 26 de agosto de 2026

| Dato | Valor anterior | Valor verificado | Fuente |
|---|---|---|---|
| APC de IJSSE | USD 700 | **USD 850** | [Página oficial de APC](https://www.iieta.org/journals/ijsse/Article%20Processing%20Charge), consultada el 26/08/2026 |
| Cuartil de BEEI | «Q3» a secas | **Q1 por CiteScore · Q3 por SJR** | Son rankings distintos y no deben combinarse |

El valor de USD 700 provenía de un extracto de búsqueda, no de la página
oficial. **CiteScore, percentil Scopus y cuartil SJR son tres indicadores
distintos** y presentarlos como equivalentes es un error de método.
