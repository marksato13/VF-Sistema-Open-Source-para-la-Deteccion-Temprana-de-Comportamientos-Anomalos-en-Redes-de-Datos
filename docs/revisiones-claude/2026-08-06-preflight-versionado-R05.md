# Revisión Claude — preflight versionado R05

Fecha: 6 de agosto de 2026. Dictamen final: **PREFLIGHT AUTORIZADO PARA EJECUCIÓN**.

Claude revisó en modo de sólo lectura el script, sus pruebas y el README. La
primera revisión encontró dos rutas de falso PASS reales:

- `pgrep tcpdump` dentro de `if` ocultaba si el SSH al Sensor había fallado;
- el probe Kali→iperf3 podía confundir transporte SSH fallido con firewall
  bloqueando correctamente.

Codex corrigió ambas rutas capturando el código remoto: `0` representa condición
prohibida, `1` ausencia/rechazo esperado, `124` timeout esperado sólo para el
probe de Kali y cualquier otro código bloquea el gate. Se añadieron pruebas
específicas, `umask 077`, lock atómico y validación del temporal.

En la segunda lectura Claude confirmó que errores SSH ya no pueden convertirse
en PASS y levantó el bloqueo. Su sugerencia de ignorar un fallo al liberar el
lock no se adoptó: el código definitivo trata esa condición como fallo y no
publica el log oficial.

La revisión autoriza únicamente ejecutar el preflight no capturante. No autoriza
iniciar `DNS-VALID-10/R05`, leer scores test ni evaluar el modelo.
