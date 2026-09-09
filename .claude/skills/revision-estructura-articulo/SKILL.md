---
name: revision-estructura-articulo
description: "Revisa la estructura y la redacción del artículo para IJIES contra lo que hacen los artículos reales de la revista: secciones, subsecciones de metodología, extensión de la introducción y sus siete elementos. Usar al escribir o revisar cualquier sección del artículo."
---

# Revisión de la estructura del artículo

La referencia **no es un marco metodológico importado**. Son los artículos
reales de IJIES, analizados uno a uno. Ninguno de los quince cita CRISP-DM,
DSRM ni ningún otro marco: la metodología es el pipeline en orden de ejecución.

Fuente completa con los DOI:
`docs/articulo/02-estructura-metodologia.md`.

## La estructura fijada

```
1 Introduction · 2 Related work · 3 Proposed methodology
4 Results and discussion · 5 Conclusion
+ Conflicts of Interest · Author Contributions · References
```

Cinco secciones de cuerpo es la norma: tres de cada cinco artículos semilla las
tienen. Las de después de las referencias son **rígidas en IJIES**: 7 de 7 las
llevan, y son las que se olvidan.

## Las seis subsecciones de la metodología

```
3.1  Testbed and traffic generation
3.2  Multi-layer feature extraction
3.3  Dataset construction and labeling
3.4  Detection model and threshold calibration
3.5  Real-time engine and inline enforcement
3.6  Evaluation protocol
```

**`3.2` va antes que `3.3`, y no es negociable.** El extractor convierte los
paquetes en vectores y esos vectores *son* las filas del dataset. En los
artículos de IJIES el orden es el inverso porque sus autores descargan
NSL-KDD o UNSW-NB15; aquí no se descarga nada.

**`3.5` conserva epígrafe propio.** Es lo único que no tiene ninguno de los
quince artículos analizados: todos usan datasets públicos y ninguno despliega.
Fusionarla para parecerse a ellos escondería la aportación.

## La introducción, medida sobre 15 artículos

| Elemento | Presente en |
|---|---|
| Antecedentes · Problema · Justificación | **15/15** |
| Organización del manuscrito | 13/15 |
| Objetivos · Contribuciones | 12/15 |
| **Pregunta de investigación** | **1/15** |

```
párrafos    4 – 17     mediana  7
palabras  358 – 1564   mediana 765
citas       4 – 29     mediana 13
figuras   14 de 15 no tienen ninguna
```

Una introducción fuera de ese rango necesita justificarse. Y si lleva
preguntas de investigación numeradas, será la excepción, no la norma.

Detalle por artículo: `mapeo_introduccion_15.xlsx` del OneDrive del usuario.

## Cómo se redacta cada subsección

- **Abrir con la figura de arquitectura** y un párrafo que recorra el flujo.
  Los cinco semilla lo hacen; es lo primero que mira un revisor.
- **Orden de ejecución, no orden lógico.** Sin marco teórico previo.
- **Cada subsección con su fórmula o su parámetro**: `nu=0,05`, umbral
  `1,8126`, `alpha=0,05`, `k=13`, expiración de 120 s.

## Plazo

Envío el **28 de septiembre de 2026**. El APC sube de 300 a 400 USD el 1 de
octubre. Tres días de margen.
