---
name: ppi-experiment-freezer
description: "Congela una versión nueva de dataset, modelo o experimento con protocolo, manifiesto, entorno, hashes y evidencia. Usar solo cuando el usuario solicite explícitamente crear un congelamiento nuevo."
---

# Congelamiento experimental

Esta habilidad puede producir artefactos irreversibles. Úsala solo con solicitud
explícita. Lee `docs/agent-context/ppi-data-science-context.md` desde la raíz.

## Precondiciones

- El criterio de selección, la unidad, particiones, semillas y métricas deben
  estar fijados antes de mirar la evaluación reservada.
- Nunca sobrescribas `multilayer-v2` ni el OCSVM actual. Crea una versión nueva.
- Resuelve rutas exactas, comprueba árbol limpio y registra hashes previos.

## Congelamiento

1. Registra commit, estado sucio, versiones de runtime y librerías.
2. Conserva configuración, orden de variables, particiones por episodio,
   hiperparámetros, regla de umbral y semillas.
3. Escribe manifiesto con hashes de entradas, salidas y código relevante.
4. Ejecuta gates positivos y negativos y una reproducción desde cero.
5. Evalúa una sola vez el conjunto reservado; no cambies la selección después.
6. Publica un informe que distinga el nuevo artefacto del congelado anterior.

No hagas commit, push, release ni despliegue salvo autorización separada.
