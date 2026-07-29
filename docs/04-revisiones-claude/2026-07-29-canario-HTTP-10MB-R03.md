# Revisión Claude — HTTP-10MB R03

Fecha: 29 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Aportes conservados

Claude emitió **ACEPTADA CON LIMITACIONES** y autorizó el preflight de `HTTP-100MB/R03`.

Se conservaron integridad de descarga, cero drops, cobertura pesada 92.6499 %, `fileinfo` parcial, evidencia independiente y separabilidad pendiente.

## Correcciones

- R03 no coincide exactamente con R01: difieren paquetes, tasas, media y ratio pesado.
- El delta 7,826 frente a 7,823 son paquetes de captura, no eventos EVE, y no existe una tolerancia de 0.04 %.
- No se adoptan ACK deferral, GRO, TSO ni otra causa TCP no demostrada.
- Durar menos de diez segundos no garantiza una fila; R02 cruzó un borde UTC y produjo dos.
- No se incorporan rangos nuevos de duración, CPU, RAM o ratio pesado.
- No se bloquean 500 MB o concurrencia hasta cerrar R03; cada perfil seguirá su gate individual.
- El estado correcto es 65/145, R03 7/29 y 80 faltantes, no el estado adelantado por Claude.

## Dictamen consolidado

**ACEPTADA CON LIMITACIONES.** La campaña prueba una descarga íntegra y legítima con 7,248 paquetes en el rango 500–1500 bytes, sin pérdida, pero no demuestra por sí sola rendimiento del modelo.

Siguiente: solo el preflight independiente de `F1N-HTTP-100MB-R03`.
