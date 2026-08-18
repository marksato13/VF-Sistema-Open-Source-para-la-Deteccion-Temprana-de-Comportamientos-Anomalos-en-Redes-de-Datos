# Revisión Claude — HTTPS-500MB R02

Fecha: 27 de julio de 2026. Claude Code 2.1.217, modelo Haiku.

Claude emitió **ACEPTAR CON LIMITACIONES**. Reconoció transferencia íntegra, cero drops, TLS 1.3, cuatro filas autocorrelacionadas, cobertura pesada y estado correcto del ensamblador. Autorizó el preflight individual de `HTTPS-1GB/R02`.

Se conservaron:

- mismo volumen y duración estable respecto a R01;
- solo seis paquetes de diferencia en el rango 500–1500;
- 972 paquetes pequeños adicionales sin causa demostrada;
- cuatro filas pertenecientes a un solo episodio;
- opacidad HTTP y alcance no productivo del certificado.

Se corrigieron o descartaron:

- la velocidad es 21,374,092 B/s, no 21.374092 B/s;
- no existe en el contrato un margen aceptable de 6.87 % sobre `20M`;
- `tls_session_rate_60s=1/60` es una tasa, no 1.67 %;
- no se excluyen retransmisiones, fragmentación o timestamps como causas sin análisis;
- la sensibilidad futura del modelo no condiciona la integridad de esta campaña;
- las cuatro filas son ventanas, no transacciones duplicadas;
- los cuatro adicionales son paquetes Suricata sin identificar, no `stats`;
- no puede medirse la distribución de la campaña antes de capturarla;
- el gate de divergencia de 0.3 puntos y la estabilidad TLS añadida no pertenecen al contrato.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Estado global 42/145; R02 13/29.
