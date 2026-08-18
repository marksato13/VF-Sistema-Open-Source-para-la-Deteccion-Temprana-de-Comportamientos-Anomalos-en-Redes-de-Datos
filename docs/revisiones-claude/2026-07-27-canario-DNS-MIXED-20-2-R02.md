# Revisión Claude — DNS-MIXED-20-2 R02

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Aportes conservados

Claude aceptó integridad, causalidad y extracción, y distinguió correctamente:

- 22 consultas/respuestas de red frente a 24 observaciones internas del extractor;
- evidencia cruda independiente de R01 pese al vector idéntico;
- reproducibilidad exacta frente a reutilización de artefactos;
- posible sobrepeso futuro de vectores repetidos;
- R02 todavía insuficiente para evaluar su diversidad agregada;
- autorización del preflight individual de `DNS-MIXED-50-10/R02`.

## Errores no adoptados

La revisión presentó “22 Q+R NOERROR” aunque son 20 respuestas `NOERROR` y dos NXDOMAIN. Después proyectó que cinco repeticiones podrían ser idénticas y que 145 campañas equivaldrían aproximadamente a 145 filas; ninguna conclusión está observada y R01 ya produjo 77 filas para 29 campañas.

Claude afirmó que Isolation Forest pesa puntos repetidos una sola vez internamente. No existe ese contrato en el diseño: las filas duplicadas pueden afectar el muestreo y la distribución empírica. Por eso se realizará análisis de sensibilidad en vez de asumir robustez.

También introdujo un corte arbitrario de 50 %, una fase F5 inexistente, UUID de disco, contadores nftables y un límite NTP nuevo. No forman parte del gate congelado y no se adoptan.

Finalmente, después de `DNS-MIXED-50-10/R02` R02 quedará 4/29; `PING-10/R02` sería la quinta campaña, no la tercera.

## Dictamen consolidado

**ACEPTADA CON LIMITACIONES.** La campaña pasa sus gates, ejerce NXDOMAIN benigno y añade la segunda coincidencia exacta R01↔R02. El ensamblador queda 32/145, R02 3/29, cero inválidas/advertencias y cero cruces de partición.

Siguiente: preflight individual de `F1N-DNS-MIXED-50-10-R02`.
