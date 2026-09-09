---
name: revision-entregables-curso
description: "Revisa un entregable del curso Investigación V contra lo que pide su Sesión: extensión, secciones obligatorias, amenazas a la validez, ISO/IEC 25010, los tres ejes de confiabilidad, y coherencia de cifras entre documentos. Usar antes de entregar cualquier informe al profesor."
---

# Revisión de un entregable del curso

Antes de nada, identifica **de qué Sesión** es el entregable. Cada una pide
cosas distintas y la extensión es eliminatoria.

## Lo que pide cada Sesión

| Entregable | Sesión | Extensión | Obligatorio |
|---|---|---|---|
| Informe de evaluación crítica | 01, diap. 33 | **2–4 pp** | Lo listo, lo que no, cómo se aborda y en qué tiempo · amenazas a la validez (diap. 27) · ISO/IEC 25010 (diap. 7 y 23) |
| Plan de validación | 02, diap. 33 | **1–2 pp** | Los tres ejes: confiabilidad, replicabilidad y pertinencia |
| Matriz de revistas | 04, diap. 14–15 | Matriz + **1 p** de justificación | Criterios ponderados al 100 % · compartir con ambos asesores (diap. 27) |
| Mapeo de artículos | 05 | `.xlsx` | **≥ 12 artículos** con nombres reales de sección |

**Mide las páginas de verdad**, no las supongas. Un informe de 4,1 pp incumple
un límite de 4.

## Comprobaciones, en este orden

1. **Extensión.** Cuenta páginas del `.docx` o del PDF. Si se pasa, es
   crítico: se corrige recortando, no discutiendo.
2. **Secciones obligatorias.** Que estén, y con contenido, no solo el título.
3. **Cifras contra la fuente.** Toda cifra se comprueba con `ppi_cifra`. Los
   valores vigentes son 25,81 % y 22,97 % de FPR operativo, 4,71 % en
   laboratorio, 88,8 % de detección Kali-real, 8,0 s de lead time mediano,
   58 corridas, umbral 1,8126.
4. **Coherencia entre documentos.** El informe de evaluación crítica es el
   consolidado; el de validación y confiabilidad es el detalle. Donde se
   repitan —la confiabilidad, por ejemplo— **deben decir lo mismo**.
5. **Que el `.docx` venga de su `.md`.** Si se generó aparte, se desincroniza.
   Ya ocurrió: un `.docx` afirmaba cifras distintas de su propio `.md`.
6. **Asteriscos literales y emoji.** Un `**` visible o un `✅` que desaparece
   al exportar a PDF son fallos de entrega, no de estilo.
7. **Ambos asesores** en la portada: Ing. Nemias Saboya Ríos e Ing. Fernando
   Manuel Asin Gómez.

## Lo que no se puede declarar cumplido

- `REQ-013`, pertinencia con usuarios: `respuestas-sus.csv` tiene **cero
  filas**. Mientras siga así, no se declara validado.
- `REQ-005`, jornada de holdout externa: no existe.
- `REQ-012`, replicabilidad: faltan DOI y preregistro.

Si un documento los da por cerrados, es hallazgo **crítico**.

## Salida

Hallazgos con el formato obligatorio, ordenados por severidad. Al final, una
línea: **apto para entregar** o **no apto**, y por qué.
