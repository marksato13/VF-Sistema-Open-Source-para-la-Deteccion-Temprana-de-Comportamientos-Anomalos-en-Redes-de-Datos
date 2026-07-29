# Revisión Claude — DNS-VALID-10 R03

Fecha: 29 de julio de 2026. Claude Code, modelo Haiku.

Claude emitió **ACEPTADA CON LIMITACIONES** y autorizó únicamente el preflight de `DNS-VALID-200/R03`.

Se conservaron:

- preflight, captura, hashes y extracción completos;
- diez solicitudes y diez respuestas `NOERROR`;
- 20/20 paquetes, 2,324 bytes y cero drops;
- una fila elegible idéntica a R01/R02;
- artefactos y tiempos distintos entre las tres campañas;
- 59/145 campañas, R03 1/29, cero inválidas/advertencias;
- ocho coincidencias dentro de `train` y cero cruces observados.

Se corrigieron o descartaron:

- NTP no se evalúa contra una supuesta tolerancia de ventanas de diez segundos;
- el extractor entrega 14 valores, pero no todas las features tienen soporte no cero;
- ocho duplicados globales son dos repeticiones de `DNS-VALID-10` contra R01 más seis coincidencias de otros perfiles;
- validation/test aún no existen, por lo que no están “limpias” por evidencia;
- vectores iguales de campañas separadas no son autocorrelación temporal;
- actualmente hay 153 filas aceptadas entre R01, R02 y R03 parcial, no unas 87;
- no se afirma que Isolation Forest sea robusto a duplicados;
- no se atribuyen los cuatro paquetes adicionales R01/R02 ni la diferencia de `stats`;
- no se califica R03 como ventajosa ni la variación como despreciable;
- no se predice separabilidad ni efecto sobre anomalías;
- se descartan cortes inventados de 60 filas, 50 % de coincidencias y 30 % de similitud;
- PCA/t-SNE no es un gate de esta campaña y no se ejecuta sobre R03 incompleta;
- la documentación correcta es el canario 68, no un archivo 38 ya ocupado por R02.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Solo habilita el preflight independiente de `DNS-VALID-200/R03`.
