# Revisión Claude — canario UDP 10 Mbit/s F1

Fecha: 26 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico, sin operación, herramientas ni edición.

## Resultado

Claude emitió finalmente **ACEPTAR CON LIMITACIONES** para `F1N-UDP-10M-R01`:

- una transferencia iperf3 produjo 17,267 datagramas enviados y recibidos, 25,002,616 bytes, 9.997181 Mbit/s en receptor, jitter de 0.027371 ms, 0 % de pérdida y cero fuera de orden;
- el PCAP conserva 17,298/17,298 paquetes con cero drops;
- 17,267 paquetes —99.8208 %— están entre 500 y 1500 bytes;
- Suricata tuvo cero drops, errores y overflow;
- tres filas elegibles pertenecen al mismo episodio y no contienen observaciones L7;
- hashes y ensamblador pasaron con 21 aceptadas, 0 inválidas, 0 advertencias y 124 faltantes.

## Hallazgos sobre la propia revisión

La primera respuesta de Claude introdujo tolerancias de bitrate y gates de ratio/carga que no existen en el contrato, exigió una carga de 40 Mbit/s ausente de la matriz y afirmó que el ratio alto no elevaría el score de Isolation Forest. Se rechazaron esas conclusiones: el modelo final todavía no ha sido entrenado.

La segunda respuesta mezcló `UDP-10M` con el futuro `UDP-25M`, dejó variables sin completar, inventó ocho transferencias y saltó a `UDP-50M`. También fue descartada.

La tercera respuesta corrigió perfil, conteos y alcance. Este episodio confirma que Claude funciona como revisor, no como fuente de verdad: cada dictamen se contrasta contra manifiesto, iperf3, PCAP, EVE, features y ensamblador.

## Límites del dictamen

- La etiqueta benigna proviene del escenario controlado y del manifiesto, no de la ausencia de alertas.
- Cero pérdida reportada por iperf3 y cero drops de captura son controles diferentes.
- Las tres filas son ventanas autocorrelacionadas de una repetición.
- `application_observations=0`: iperf3 UDP no aporta semántica L7 en esta campaña.
- La cobertura benigna pesada ayuda al futuro entrenamiento, pero no prueba el score ni el falso positivo del modelo aún inexistente.
- Una ejecución no define SLA ni generaliza a aplicaciones UDP reales.

Dictamen final: **ACEPTAR CON LIMITACIONES**. Siguiente perfil: `UDP-25M/R01`, con preflight completo y sin umbrales inventados.
