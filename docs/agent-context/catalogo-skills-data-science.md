# Catálogo compartido de habilidades de ciencia de datos

Las habilidades viven una sola vez en `agent-skills/` y se exponen mediante
enlaces simbólicos en `.agents/skills/` (Codex) y `.claude/skills/` (Claude
Code). Así ambos agentes leen exactamente las mismas instrucciones.

La estructura sigue el estándar abierto **Agent Skills**: un directorio por
habilidad y un `SKILL.md` con frontmatter YAML `name` y `description`. Codex
descubre habilidades de repositorio en `.agents/skills`; Claude Code las
descubre en `.claude/skills`. Ambas documentaciones admiten directorios
enlazados simbólicamente:

- https://developers.openai.com/codex/skills/
- https://code.claude.com/docs/en/skills

| Prioridad | Habilidad | Cuándo usarla | Salida principal |
|---|---|---|---|
| P0 | `ppi-dataset-audit` | Integridad, esquema, duplicados, constantes y particiones | Informe de gates y hallazgos |
| P0 | `ppi-datasheet-builder` | Crear o revisar el datasheet | Datasheet trazable, sin métricas mezcladas |
| P0 | `ppi-feature-contract-review` | Revisar las 28 variables y el extractor | Matriz contrato↔código↔datos |
| P0 | `ppi-leakage-validity-audit` | Revisar fuga y validez interna/externa | Riesgos por unidad y partición |
| P0 | `ppi-model-evaluation` | Comparar modelos y métricas | Tabla con denominadores, IC y límites |
| P0 | `ppi-scientific-claim-audit` | Revisar PPI, tesis, artículo o defensa | Matriz afirmación↔evidencia |
| P1 | `ppi-experiment-freezer` | Congelar una versión nueva autorizada | Manifiesto, hashes y protocolo |
| P1 | `ppi-operational-validation` | Contrastar offline contra despliegue | Métricas operativas y fallos |
| P1 | `ppi-release-readiness` | Auditar una entrega o publicación | Checklist reproducible de salida |
| P2 | `ppi-scientific-figures` | Generar figuras desde resultados | Gráficos con fuente y denominador |

Invocación explícita:

```text
Codex:  $ppi-model-evaluation
Claude: /ppi-model-evaluation
```

La selección implícita depende de la descripción YAML de cada habilidad. Las
habilidades que pueden congelar o publicar exigen autorización explícita en su
propio procedimiento.
