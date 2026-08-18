# Revisión Claude — auditoría agregada R01

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Aportes conservados

Claude destacó correctamente:

- 77 filas no equivalen a 77 episodios independientes;
- 44/77 filas pertenecen a la familia web/TLS y el peso por duración merece análisis;
- RST, error HTTP y NXDOMAIN tienen soporte no cero escaso en R01;
- R01 no permite medir variación entre repeticiones;
- el vector repetido de `PING-100` debe explicarse;
- debe existir política explícita para coincidencias entre particiones.

Estos puntos se incorporaron como condiciones de análisis antes del entrenamiento.

## Errores del dictamen

El `NO APTO` de Claude no se acepta como conclusión porque:

- llamó “calibración” y “dry-run” a una repetición oficial `experiment/train`;
- afirmó que faltaba evidencia pesada pese a 59/77 filas no cero, 19 campañas y mediana 0.95962639;
- dijo que aproximadamente la mitad carecía de soporte pesado, cuando son 18/77 filas con ratio cero;
- confundió la duración de `PING-10` y describió ventanas fijas como adaptativas;
- inventó porcentajes de tolerancia, balance, cuotas por protocolo y duración de trabajo;
- propuso introducir ataques y protocolos fuera de la matriz F1 congelada;
- predijo falsos positivos/negativos sin modelo;
- trató igualdad de vectores como contaminación automática.

También recomendó Pearson con corte `|ρ|>0.90`, reducción web al 35 %, L4 al 40 %, errores mínimos y MD5. Ninguno de esos umbrales procede del diseño ni de evidencia R01.

## Política corregida

El auditor reforzado cuenta coincidencias totales y distingue cruces de partición. Las coincidencias son diagnóstico, no fallo automático de recolección: dos campañas independientes pueden producir el mismo vector discretizado. La fuga se evita manteniendo episodios completos dentro de una sola campaña/repetición y se comprobará con análisis de sensibilidad antes de métricas.

La matriz no cambia después de observar R01. R02 se recolectará oficialmente y permitirá la primera comparación entre repeticiones. No se usará un “piloto R02 completo” con umbrales inventados.

## Dictamen consolidado

Codex determina **APTO CON CONDICIONES PARA R02**, sustentado en el gate reproducible:

- 29/29 perfiles;
- 77/77 filas elegibles;
- 0 inválidas y 0 advertencias;
- 0 duplicados entre campañas/particiones;
- 14/14 features con soporte;
- Git limpio en `373fcba`;
- 39/39 pruebas.

Siguiente: preflight de `DNS-VALID-10/R02`; auditoría agregada y comparación descriptiva al cerrar R02.
