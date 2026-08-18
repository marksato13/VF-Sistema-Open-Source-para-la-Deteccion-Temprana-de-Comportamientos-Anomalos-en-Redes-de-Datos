# Revisión Claude — canario HTTP 1 GB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del bundle resumido y del evento EVE previo; sin edición ni operación del laboratorio.

## Dictamen inicial

Claude emitió **ACEPTAR CON NO CONFORMIDAD**. Consideró demostrables la transferencia completa, integridad de tres PCAP, cero drops, cobertura de paquetes grandes y salud del Sensor. Condicionó el cierre a demostrar que el flow diferido del preflight no entró en las seis filas.

## Pruebas solicitadas y resultado

| Prueba | Resultado |
|---|---|
| Inicio de cada ventana de 10 s posterior a `19:45:22` | PASS, seis de seis |
| Filas elegibles | PASS, seis `True` |
| Extractor excluye `event_type=flow` | PASS, solo admite HTTP/DNS/TLS |
| Evento de aplicación dentro del slice | solo HTTP `/files/1GB.bin` a `19:46:26` |
| Flow de preflight presente en PCAP | No |

El evento cuestionado tenía `flow.start=19:45:11` y se escribió a `19:46:14` por timeout. No fue una observación usada por el extractor y no alteró las features.

## Resolución

La condición de Claude está satisfecha y el bundle es aceptable. No se afirma que el segmento EVE contenga exclusivamente flujos iniciados después del checkpoint; sí se afirma que las filas elegibles provienen solo del PCAP de campaña y del HTTP correspondiente.

Como acción preventiva, las campañas oficiales futuras incorporan 70 segundos de quietud antes de abrir EVE/PCAP. Esto drena eventos diferidos producidos por comprobaciones de preflight.

## Límite

La campaña demuestra transferencia legítima de 1 GB, captura completa, operación sin pérdidas y seis ventanas benignas. No demuestra inspección de payload completo ni diversidad suficiente del dataset por sí sola.
