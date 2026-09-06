---
name: ppi-leakage-validity-audit
description: "Audita fuga de información, pseudorreplicación y validez interna/externa en particiones, ventanas, episodios, selección de modelo y evaluación operacional del PPI."
---

# Auditoría de fuga y validez

Lee primero `docs/agent-context/ppi-data-science-context.md` desde la raíz del repositorio.

## Procedimiento

1. Define la unidad de cada afirmación: ventana, episodio, perfil, familia,
   corrida, host o usuario.
2. Verifica que un episodio no cruce particiones y que el escalador/modelo solo
   usen train; el umbral, validation; y test/evaluation no ajusten decisiones.
3. Busca dependencia por ventanas solapadas, perfiles repetidos R01–R05,
   duplicados y selección posterior entre candidatos.
4. Para inferencia pareada, comprueba independencia entre unidades. Si varias
   ventanas pertenecen a un episodio, agrupa por episodio o usa un método que
   preserve clusters.
5. Separa validez interna, validez de constructo y validez externa. Un gate sin
   fuga no demuestra generalización a otra jornada o red.
6. Contrasta resultados offline con F6 y evita extrapolar el FPR de laboratorio.

## Salida

Clasifica cada riesgo como fuga directa, dependencia, selección, cambio de
distribución o límite externo. Indica evidencia, efecto sobre la afirmación y
la prueba mínima para resolverlo.
