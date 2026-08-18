# Revisión Claude — DNS-VALID-200 R02

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Aportes conservados

Claude concluyó que la integridad de campaña pasa y destacó correctamente:

- 400/400 paquetes, cero drops y EVE 410/410;
- doscientas transacciones `NOERROR` con evidencia independiente de R01;
- la distribución 24/376 frente a 228/172 está influida por la fase de inicio respecto a las ventanas fijas;
- las dos filas de cada campaña están autocorrelacionadas;
- la variación entre repeticiones no exige cambiar la matriz congelada;
- procede un preflight individual de `DNS-MIXED-20-2/R02`.

## Errores corregidos

La respuesta afirmó que una ráfaga de 4.1 s cayó íntegramente dentro de una ventana. Es falso: R02 empezó a `17:32:29.709857Z` y cruzó el borde `17:32:30Z`. Los 24 paquetes iniciales corresponden aproximadamente a 0.29 s, no a tres segundos.

También afirmó una política histórica de seleccionar una fila por campaña. El ensamblador conserva ambas filas; la dependencia se controla manteniendo el episodio completo en una partición y mediante análisis de sensibilidad previo al entrenamiento.

La ausencia de cruces entre particiones procede del ensamblador, no del ledger. Además, R01 y R02 pertenecen ambas a `train`, por lo que todavía no prueban separación frente a validation/test.

Para el siguiente perfil, Claude calculó aproximadamente 0.095 para dos NXDOMAIN. El contrato nominal contiene 20 consultas válidas y 2 inválidas: `2/22 = 0.090909…`. No se fijará la fila observada antes de ejecutar.

## Dictamen consolidado

**ACEPTADA CON LIMITACIONES.** La campaña es íntegra y aporta variación real de alineación temporal. Sus dos ventanas no son dos repeticiones independientes. El ensamblador queda en 31/145 y R02 en 2/29, sin inválidas ni advertencias.

Siguiente: preflight individual de `F1N-DNS-MIXED-20-2-R02`.
