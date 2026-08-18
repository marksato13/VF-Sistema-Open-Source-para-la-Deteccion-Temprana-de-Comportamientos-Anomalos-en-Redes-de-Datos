# Revisión Claude — canario UDP 25 Mbit/s F1

Fecha: 26 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico, sin operación, herramientas ni edición.

## Resultado

Claude emitió finalmente **ACEPTAR CON LIMITACIONES** para `F1N-UDP-25M-R01`:

- una transferencia iperf3 entregó 62,504,368 bytes y 43,166 datagramas en ambos extremos;
- el receptor observó 24.999210 Mbit/s, jitter de 0.068925 ms, 0 % de pérdida y cero fuera de orden;
- el PCAP conserva 43,195/43,195 paquetes y cero drops;
- 43,166 paquetes —99.9329 %— están entre 500 y 1500 bytes;
- Suricata tuvo cero drops, errores y overflow;
- tres filas elegibles pertenecen al mismo episodio y no contienen observaciones L7;
- hashes y ensamblador pasaron con 22 aceptadas, 0 inválidas, 0 advertencias y 123 faltantes.

## Hallazgos sobre la revisión

La primera respuesta añadió “cero fragmentados” sin disponer de un conteo de fragmentación, afirmó que la distribución descartaba sesgos de muestreo y atribuyó el jitter al laboratorio. Los tres puntos excedían la evidencia y no se incorporaron.

La segunda consulta, ejecutada sin persistencia, perdió el contexto y respondió que `UDP-25M` no se había ejecutado porque intentó buscar un archivo en lugar de corregir el texto proporcionado. Este resultado también se descartó.

La tercera consulta volvió a incluir toda la evidencia y produjo un dictamen consistente. La revisión cruzada se usa como crítica, no como sustituto de los artefactos.

## Límites del dictamen

- Benignidad proviene del escenario y manifiesto, no de Suricata.
- Cero pérdida iperf3 y cero drops de captura son controles distintos.
- Las tres filas están autocorrelacionadas dentro de una repetición.
- `application_observations=0`; iperf3 no generaliza a aplicaciones UDP/L7.
- La cobertura de paquetes grandes no descarta por sí sola sesgo del dataset.
- El modelo final no está entrenado: no se conoce su score ni falsos positivos.

Dictamen final: **ACEPTAR CON LIMITACIONES**. Siguiente perfil: `UDP-50M/R01`, con preflight completo.
