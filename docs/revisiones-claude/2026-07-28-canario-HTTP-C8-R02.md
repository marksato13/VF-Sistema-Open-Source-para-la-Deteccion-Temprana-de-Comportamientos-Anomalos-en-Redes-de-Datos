# Revisión Claude — HTTP-C8 R02

Fecha: 28 de julio de 2026. Claude Code 2.1.217, modelo Haiku.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó el preflight de `TCP-REFUSED-5/R02`. Reconoció la rotación íntegra, cero drops, ocho transferencias solapadas, cobertura pesada, seis ventanas del mismo episodio y truncamiento de inspección.

Se conservaron:

- configuración de captura corregida y verificada;
- dos PCAP íntegros y 592,548 paquetes sin pérdidas;
- ocho flujos solapados de un Cliente;
- 97.8996 % de paquetes en 500–1500 bytes;
- variación R01/R02 sin causa medida;
- seis ventanas correlacionadas, no repeticiones;
- CPU descriptiva y `fileinfo` truncado.

Se corrigieron o descartaron:

- el margen hasta 200 se expresa en Mbit/s, no “paquetes-segundo”;
- no se atribuye la reducción de paquetes pequeños a “condensación de fase”;
- −1.2631 % no se declara tolerancia normal o marginal sin criterio;
- los seis duplicados previos son tres DNS, una ventana `PING-100` y dos HTTP-MULTI; C2 no añadió uno;
- las 14 features son válidas, pero no todas tienen soporte no nulo en esta campaña;
- CPU 47.29 % no está “dentro de límites” porque no existe umbral formal;
- los ocho flujos se solapan, pero no son patrones experimentales independientes;
- el hash `f4a0...` corresponde al controlador PCAP, no al generador;
- no se exige una línea base CPU adicional, una causa persistente ni congelar toda configuración para el siguiente perfil;
- no se proyecta 51/145 como evidencia: el estado actual es 50/145.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Estado global 50/145; R02 21/29.
