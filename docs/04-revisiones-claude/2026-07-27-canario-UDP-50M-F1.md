# Revisión Claude — canario UDP 50 Mbit/s F1

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: resumen técnico, sin operación, herramientas ni edición.

## Resultado

Claude emitió finalmente **ACEPTAR CON LIMITACIONES** para `F1N-UDP-50M-R01`:

- una transferencia iperf3 entregó 125,007,288 bytes y 86,331 datagramas en ambos extremos;
- el receptor observó 49.985031 Mbit/s, jitter de 0.132158 ms, 0 % de pérdida y cero fuera de orden;
- el PCAP conserva 86,364/86,364 paquetes y cero drops;
- 86,331 paquetes —99.9618 %— están entre 500 y 1500 bytes;
- Suricata tuvo cero drops, errores y overflow;
- tres filas elegibles pertenecen al mismo episodio y no contienen observaciones L7;
- hashes y ensamblador pasaron con 23 aceptadas, 0 inválidas, 0 advertencias y 122 faltantes.

## Hallazgos sobre la revisión

La primera respuesta llamó “anómalo” y después “elevado” al jitter de 0.132158 ms, aunque no existe umbral de aceptación. También describió los recursos como “normales” sin criterio definido y afirmó incorrectamente que las features L7 se validarían en campañas “posteriores”. Estas categorías e inferencias no se incorporaron.

La segunda consulta volvió a incluir toda la evidencia y corrigió el alcance. El jitter es mayor que las tres observaciones históricas de 0.037/0.048/0.040 ms, pero sin umbral ni repeticiones no establece deterioro, causa ni rechazo.

## Límites del dictamen

- La benignidad procede del escenario y manifiesto, no de Suricata ni del tamaño.
- Cero pérdida iperf3 y cero drops de captura son controles diferentes.
- Las tres ventanas pertenecen a una repetición y no forman SLA.
- `application_observations=0`; esta campaña no generaliza a UDP/L7 productivo.
- La cobertura pesada no elimina por sí sola sesgo del dataset.
- El modelo final aún no está entrenado: no se conoce score ni falsos positivos.

Dictamen final: **ACEPTAR CON LIMITACIONES**. Cierra UDP R01 10/25/50 Mbit/s. Siguiente perfil: `MIXED-LIGHT/R01`, con preflight completo.
