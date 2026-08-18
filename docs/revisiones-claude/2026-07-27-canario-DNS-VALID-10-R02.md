# Revisión Claude — DNS-VALID-10 R02

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Primera respuesta rechazada

Claude afirmó que `F1N-DNS-VALID-10-R02` no tenía artefactos y que solo se había autorizado su preflight. Era falso: la campaña había terminado, y Codex ya había verificado bundle, ledger, PCAP, EVE, CSV y hashes en `/srv/ppi-evidence/artifacts`.

La causa observable fue que Claude no leyó la evidencia ubicada fuera del repositorio y sustituyó esa ausencia de acceso por una conclusión de inexistencia. También describió la coincidencia como si fuera dentro de campaña, aunque ocurre entre R01 y R02.

Ese dictamen no se usó.

## Corrección con hechos explícitos

Se le entregaron los resultados verificados:

- ledger `completed`, `experiment/train`, R02;
- SHA-256 de bundle y features correctos;
- PCAP 20/20, cero drops y transferencia verificada;
- EVE 29/29, diez requests, diez responses, veinte `NOERROR` y cero alertas;
- una fila elegible a partir de 20 paquetes y diez observaciones L7;
- ensamblador con 30 campañas aceptadas, cero inválidas y cero advertencias;
- vector idéntico a R01, pero evidencia cruda, ledger y tiempos distintos.

Claude reconoció el error y cambió su conclusión a **ACEPTADA**. Coincidió en que el mismo generador determinista puede producir el mismo vector sin implicar contaminación y autorizó continuar con un preflight propio de `DNS-VALID-200/R02`.

## Correcciones al segundo dictamen

No se adoptan tres afirmaciones:

1. El gate agregado de repetición no pasa: R02 está 1/29 y `repetition_complete=false`.
2. `request_rate` no forma parte del esquema de 14 features.
3. No se fijan valores aproximados esperados para DNS-VALID-200 sin derivarlos del extractor, ventanas y evidencia.

La separación correcta es:

- **campaña:** aceptada por integridad, causalidad y una fila elegible;
- **repetición R02:** incompleta, por lo que su gate agregado sigue cerrado;
- **coincidencia exacta:** diagnóstico de peso/reproducibilidad, no reutilización automática;
- **particiones:** cero coincidencias cruzadas hasta este punto.

## Dictamen consolidado

Codex y la conclusión corregida de Claude aceptan `F1N-DNS-VALID-10-R02`. Codex conserva como limitación la coincidencia exacta con R01 y exige análisis de sensibilidad antes del entrenamiento.

Siguiente: preflight individual de `F1N-DNS-VALID-200-R02`.
