# Revisión Claude — implementación del calibrador PM-F1-v1

Fecha: 6 de agosto de 2026. Dictamen final: **CÓDIGO AUTORIZADO PARA PREFLIGHT**.

Claude participó en modo de solo lectura. Se preservan todos los intentos:

1. Opus agotó 180 s sin dictamen.
2. Sonnet, sin acceso a archivos, emitió un bloqueo basado en premisas falsas:
   interpretó el colapso train como decisión post hoc, propuso excluir las
   ventanas `seen` y afirmó que faltaban reglas ya escritas. El congelamiento y
   el protocolo demuestran lo contrario. Se retuvieron como mejoras útiles el
   desempate estable y un timing descriptivo.
3. La solicitud de reconsideración agotó 120 s sin dictamen.
4. Sonnet agotó 240 s al intentar leer el código, sin cambios.
5. Haiku leyó `calibrate_pm_f1_v1.py` y su prueba, verificó los invariantes y
   emitió `CÓDIGO AUTORIZADO`.

El dictamen final confirmó con referencias de línea que el selector sólo crea
R01–R04; se exigen 87/224 y 29/72; los scalers ajustan sólo train; el umbral usa
`floor`, `s(k+1)` y desigualdad estricta; los hashes de scores preceden a
`lower_tail`; el destino no se reemplaza y se publica por `rename`; Git se
verifica antes y después. También reconoció la prueba que impide construir una
ruta R05.

La autorización se limita al preflight. Claude no ejecutó comandos, no abrió
`/srv`, no puntuó R04 y no autoriza R05. Un nuevo dictamen sobre el JSON del
preflight es obligatorio antes de la ejecución única.
