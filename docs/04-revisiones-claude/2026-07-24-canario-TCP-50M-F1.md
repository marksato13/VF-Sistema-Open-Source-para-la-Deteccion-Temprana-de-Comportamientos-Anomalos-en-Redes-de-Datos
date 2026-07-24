# Revisión Claude — canario TCP 50 Mbit/s F1

Fecha: 24 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen técnico, sin operación ni edición.

## Dictamen inicial

Claude emitió **ACEPTAR CONDICIONADO**. Determinó que una retransmisión no bloquea una transferencia íntegra de 20 s, que el evento `APPLAYER_PROTO_DETECTION_SKIPPED` no es una detección maliciosa y que las tres ventanas pueden incorporarse si se declara su autocorrelación.

Las condiciones fueron:

1. documentar que las tres filas pertenecen a un episodio;
2. explicar la diferencia entre bytes de aplicación y tamaño PCAP sin afirmar pérdida;
3. confirmar ensamblador y ausencia de duplicación.

Las tres pasaron antes del cierre.

## Correcciones al dictamen

La primera respuesta contenía afirmaciones inexactas:

- la desviación real fue +0.025648 % emisor y +0.015408 % receptor, no inferior a 0.01 %;
- la diferencia `90,834` Suricata frente a `90,832` PCAP no se atribuye a eventos `stats`; son dominios de conteo diferentes y ambos declararon cero drops;
- el PCAP no debe igualar bytes iperf3: incorpora cabeceras de captura/red/transporte, ACK, control y ambos sentidos;
- el ensamblador quedó en 18 aceptadas y 127 faltantes, no 19/126;
- la matriz continúa con `TCP-100M/R01`, no R02 ni UDP 50.

Claude aceptó las correcciones y emitió **ACEPTAR**.

## Interpretación de la alerta

La alerta SID `2260003` tuvo `action=allowed`, categoría genérica, severidad 3 y se acompañó de la anomalía de clasificación `APPLAYER_PROTO_DETECTION_SKIPPED`. No hubo drop, decoder invalid ni interrupción.

La documentación oficial de Suricata describe este evento como una salida de la detección de protocolo. En el dataset:

- permanece en EVE para auditoría;
- no se usa como etiqueta de ataque;
- no entra en las 14 features;
- queda documentado como telemetría correcta pero falso positivo si se interpreta como alarma de seguridad.

## Límites aceptados

- una ejecución iperf3 no representa tráfico de usuario productivo;
- las tres filas no son muestras independientes;
- un flujo TCP LAN estable no generaliza a WAN;
- una retransmisión se conserva como variación normal, no como umbral universal;
- la alerta muestra que los eventos IDS no son ground truth por sí solos.

Dictamen final: **ACEPTAR CON LIMITACIONES**.
