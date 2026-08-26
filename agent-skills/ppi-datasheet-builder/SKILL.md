---
name: ppi-datasheet-builder
description: "Construye o revisa el datasheet científico de multilayer-v2 con identidad, composición, recolección, etiquetas, particiones, sesgos, privacidad, licencia y mantenimiento, siempre trazado a artefactos."
---

# Datasheet del PPI

Lee primero `docs/agent-context/ppi-data-science-context.md` desde la raíz y después
`docs/dataset/DATASHEET_MULTILAYER_V2.md` junto con su generador.

## Reglas

- El datasheet responde por los datos. Métricas del modelo van en la model card
  y comportamiento desplegado en la system card.
- No edites solo el Markdown generado. Corrige primero
  `scripts/entregables/generar_datasheet.py` y regenera después.
- Deriva cifras desde CSV, JSON y configuraciones. Registra numerador,
  denominador, unidad y fecha.
- Incluye 11 áreas: identidad; entorno; unidad; escenarios; etiquetado;
  particiones/fuga; variables; calidad; sesgos; privacidad/uso; publicación y
  mantenimiento.
- Declara por separado ventanas y episodios, Kali real y heredado, variables
  definidas y efectivas, y artefactos publicados y no publicados.
- No declares cerrada una debilidad porque el texto la mencione. Exige salida,
  prueba o artefacto.

## Verificación

Regenera en un árbol limpio, confirma que el diff solo contiene cambios
esperados, ejecuta la auditoría del dataset y valida los SHA-256. Señala como
consulta cualquier decisión editorial ambigua.
