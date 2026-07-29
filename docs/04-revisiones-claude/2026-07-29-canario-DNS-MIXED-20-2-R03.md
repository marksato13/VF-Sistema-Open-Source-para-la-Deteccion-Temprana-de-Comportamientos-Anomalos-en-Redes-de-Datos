# Revisión Claude — DNS-MIXED-20-2 R03

Fecha: 29 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Aportes conservados

Claude emitió **ACEPTADA CON LIMITACIONES** y autorizó únicamente el preflight de `DNS-MIXED-50-10/R03`.

Se conservaron:

- la integridad 44/44/44, EVE 53/53 y cero drops;
- la distinción entre 22 transacciones y 24 observaciones internas del extractor;
- la independencia de artefactos frente a la coincidencia exacta del vector R01/R02/R03;
- el orden determinista de veinte consultas válidas seguido por dos NXDOMAIN;
- el aumento de peso empírico dentro de `train` sin diversidad adicional;
- la ausencia de evidencia de separabilidad frente a anomalías DNS.

## Correcciones

No se adoptó el cálculo de que nueve coincidencias representan 10.3 % de los perfiles: el ensamblador reporta pares de vectores coincidentes, no esa proporción.

Tampoco se adoptó el total de 77 filas como estado de R01–R03 ni el porcentaje Web/TLS citado; 77 correspondió al cierre histórico de R01 y no describe el agregado actual.

La revisión calificó el sobreajuste con severidad media sin una evaluación de modelo. Se conserva como riesgo a medir mediante ablación o sensibilidad por campaña, no como efecto demostrado.

Finalmente, no se acepta la expectativa de que `DNS-MIXED-50-10/R03` aporte un vector no repetido: R01 y R02 de ese perfil ya coincidieron exactamente. Su resultado R03 deberá medirse, no anticiparse.

## Dictamen consolidado

**ACEPTADA CON LIMITACIONES.** La campaña aporta una tercera ejecución íntegra e independiente del patrón benigno 20+2, pero no amplía el rango de sus 14 features. El ensamblador queda 61/145, R03 3/29, cero inválidas/advertencias y cero cruces observados.

Siguiente: solo el preflight independiente de `F1N-DNS-MIXED-50-10-R03`.
