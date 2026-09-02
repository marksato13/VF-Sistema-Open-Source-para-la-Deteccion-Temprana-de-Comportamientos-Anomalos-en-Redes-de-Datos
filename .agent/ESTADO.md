# Estado del trabajo entre agentes

**Actualizado:** 2 de septiembre de 2026

| | |
|---|---|
| **Tarea activa** | `PPI-DOCS-001` — ver [`TASK-ACTUAL.md`](TASK-ACTUAL.md) |
| **Estado** | `COMPLETO` — implementado por Codex, revisado y corregido por Claude |
| **Siguiente agente** | **El usuario**: revisar el diff y autorizar el commit |
| **Rama** | `main`, sincronizada con `origin` |

## Dónde está cada cosa

| Archivo | Quién lo escribe | Qué contiene |
|---|---|---|
| [`TASK-ACTUAL.md`](TASK-ACTUAL.md) | Usuario o Claude | La tarea ejecutable y sus criterios de aceptación |
| [`REGLAS-Y-LIMITES.md`](REGLAS-Y-LIMITES.md) | Estable | Prohibiciones y trampas del repositorio |
| [`../docs/revisiones-claude/HANDOFF-CLAUDE.md`](../docs/revisiones-claude/HANDOFF-CLAUDE.md) | **Claude** | Hallazgos con evidencia, decisiones tomadas, riesgos |
| `RESULTADO-ULTIMA-EJECUCION.md` | **Codex** | Qué hizo, con evidencia literal |
| `../docs/revisiones-claude/REVIEW-CODEX.md` | **Claude** | Revisión adversarial del trabajo de Codex |

## Ciclo

```
Claude audita  →  HANDOFF-CLAUDE.md
                        ↓
Codex implementa  →  RESULTADO-ULTIMA-EJECUCION.md
                        ↓
Claude revisa el diff  →  REVIEW-CODEX.md
                        ↓
Codex corrige solo lo confirmado
                        ↓
El usuario revisa y autoriza el commit
```

**Ningún agente commitea.** El commit lo autoriza el usuario.

## Cómo disparar la ejecución

Ninguno de los dos agentes lee estos archivos por su cuenta. Hay que decírselo:

```
Lee .agent/TASK-ACTUAL.md y ejecuta el flujo completo.
Usa el contexto de .agent/REGLAS-Y-LIMITES.md y
docs/revisiones-claude/HANDOFF-CLAUDE.md.
No pidas confirmación intermedia salvo condición de bloqueo.
```
