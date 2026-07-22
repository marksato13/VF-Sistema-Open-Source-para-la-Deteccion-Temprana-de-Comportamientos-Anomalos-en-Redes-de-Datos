# Revisión Claude — canario HTTP 100 MB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen y resultados del bundle; sin edición ni operación del laboratorio.

## Evidencia entregada

- campaña oficial `F1N-HTTP-100MB-R01`, Git limpio, `purpose=experiment`, `R01/train`;
- HTTP 200, 104,857,600 bytes descargados en 9.511591 s;
- PCAP de 111,438,325 bytes, 79,114/79,114 paquetes, hashes correctos y cero drops;
- 72,482 paquetes IPv4 de 500–1500 bytes, equivalentes a 91.6172 %;
- delta Suricata de 79,119 paquetes, sin drops, ifdrops, errores de decodificación ni overflow;
- EVE 15/15 y `fileinfo` limitado a 102,400 bytes;
- dos filas extraídas y ambas elegibles;
- ensamblador con tres campañas aceptadas, cero inválidas, cero advertencias y 142 faltantes.

## Dictamen

Claude emitió **VEREDICTO: ACEPTAR**. Consideró verificada la integridad de la captura, el tráfico legítimo pesado, la extracción y la aceptación oficial. Calificó como bajo el riesgo del límite `fileinfo`, siempre que no se declare análisis completo de payload.

También observó que aproximadamente 88 Mbit/s permanecen por debajo del techo TCP calibrado y que la campaña no presentó pérdida.

## Hallazgo corregido

En una frase, Claude describió la campaña como “calibración” y cuestionó la relación entre nomenclatura y `train`. Esa clasificación no coincide con la evidencia primaria:

- el manifiesto registra `purpose=experiment`;
- el ledger registra `purpose=experiment`, repetición 1 y partición `train`;
- el ID canónico usa prefijo `F1N`, no `CAL-G6`;
- el ensamblador aplica el gate anti-calibración y aceptó la celda.

Por tanto, se acepta el dictamen técnico, pero se rechaza esa palabra como un error del revisor. Es una campaña oficial de entrenamiento, no una calibración.

## Límite acordado

Puede afirmarse transferencia completa, PCAP íntegro, tráfico legítimo pesado y features L3/L4/L7 pasivas. No puede afirmarse inspección del cuerpo HTTP completo ni detección semántica del contenido de 100 MiB.
