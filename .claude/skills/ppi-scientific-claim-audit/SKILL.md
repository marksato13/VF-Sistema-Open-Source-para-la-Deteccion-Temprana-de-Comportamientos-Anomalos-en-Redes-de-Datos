---
name: ppi-scientific-claim-audit
description: "Audita afirmaciones científicas del PPI, tesis, artículo, README o defensa contra fuentes primarias; detecta cifras obsoletas, causalidad excesiva y resultados planificados presentados como obtenidos."
---

# Auditoría de afirmaciones científicas

Lee primero `docs/agent-context/ppi-data-science-context.md` desde la raíz del repositorio.

## Método

1. Extrae afirmaciones verificables y conserva la cita literal y ubicación.
2. Clasifica cada una como diseño, configuración, resultado, interpretación o
   limitación.
3. Busca la fuente primaria siguiendo el orden de autoridad compartido.
4. Marca: respaldada, parcialmente respaldada, falsa, obsoleta, ambigua o no
   verificable.
5. Para cifras exige numerador, denominador, unidad, intervalo cuando aplique y
   artefacto. Para comparaciones exige protocolo y unidad inferencial.
6. Detecta redondeo favorable, selección posterior, generalización indebida,
   confusión entre cero eventos y 100 % de disponibilidad, y mezcla entre
   offline y operación.
7. Propón texto listo para pegar con la voz del documento; no elimines contenido
   válido ni resuelvas ambigüedad editorial sin consulta.

## Salida

Tabla `ID / ubicación / texto actual / veredicto / texto propuesto / evidencia /
riesgo ante jurado`, ordenada por gravedad.
