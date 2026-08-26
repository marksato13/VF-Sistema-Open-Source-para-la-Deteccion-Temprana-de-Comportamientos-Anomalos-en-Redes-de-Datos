---
name: ppi-scientific-figures
description: "Diseña o audita figuras científicas del PPI desde resultados versionados, con ejes, denominadores, intervalos, fuente, resolución y mensajes que no exageren la evidencia."
---

# Figuras científicas

Lee `docs/agent-context/ppi-data-science-context.md` desde la raíz y usa resultados JSON
o CSV como entrada; nunca copies cifras desde una imagen o desde memoria.

## Reglas

- Define la pregunta que responde cada figura y la unidad observacional.
- Muestra numeradores/denominadores o intervalos cuando una barra represente una
  proporción. No trunques ejes para exagerar diferencias.
- Separa FPR offline y operativo; no los unas como si provinieran de la misma
  distribución.
- Identifica selección posterior y valores descriptivos en título o pie.
- Usa paleta accesible, etiquetas legibles en español y 300 dpi para entrega.
- Registra script, entrada, commit y ruta de salida. Si se modifica una figura,
  se regenera desde datos; no se retoca el PNG manualmente.
- Reutiliza `scripts/entregables/generar_graficas.py` y los recursos existentes
  cuando correspondan.

## Salida

Entrega figura, pie listo para pegar y ficha de trazabilidad. Señala si falta un
gráfico necesario sin inventar datos para generarlo.
