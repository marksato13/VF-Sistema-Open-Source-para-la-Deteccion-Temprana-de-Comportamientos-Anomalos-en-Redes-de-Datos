# Validación G3 del orquestador de campañas

Fecha: 20 de julio de 2026. Alcance: campaña DNS benigna corta desde VM05 Cliente hacia VM03 Servidor, observada por VM02 Sensor.

## Resultado

**G3 PASS para el orquestador F1.** Este resultado demuestra que el mecanismo puede abrir, ejecutar, cerrar y verificar una campaña pequeña. No valida todavía el dataset, las 14 features, los escenarios de carga ni el modelo ML.

La validación necesitó tres ejecuciones con IDs distintos. Ningún artefacto fue sobrescrito y las dos primeras ejecuciones se conservaron localmente como evidencia de los fallos detectados.

| Campaña | Commit | Resultado | Hallazgo |
|---|---|---|---|
| `CAL-F1-DNS-001` | `3132864` | rechazada retrospectivamente | serie temporal sin muestras; el segmento EVE incluyó 7 líneas aunque el checkpoint final indicaba 6 |
| `CAL-F1-DNS-002` | `fc31161` | `evidence_failed`, código 3 | el recorte EVE quedó exacto, pero el streaming remoto del sampler seguía entregando solo la cabecera |
| `CAL-F1-DNS-003` | `9f879ad` | `completed` | todos los controles del piloto pasaron |

La primera versión marcaba `CAL-F1-DNS-001` como completada porque aún no verificaba el número de muestras ni la igualdad del segmento EVE con el checkpoint. No debe utilizarse como dataset. La segunda versión incorporó ese control y rechazó correctamente la evidencia incompleta.

## Correcciones aplicadas

1. Se sustituyó `tail` abierto por un rango exacto entre las líneas EVE inicial y final.
2. El manifiesto ahora compara `eve_slice_records` con `expected_eve_records`.
3. El sampler dejó de transmitir un proceso Bash remoto de larga duración. Ahora consulta el Sensor periódicamente y escribe cada muestra en VM01.
4. El cálculo de CPU usa ticks de proceso y nanosegundos reales transcurridos, incluyendo la latencia SSH.
5. Se agregó una espera predeterminada de nueve segundos porque el intervalo de eventos `stats` observado en Suricata es de ocho segundos.
6. Una campaña con evidencia incompleta queda como `evidence_failed` y `stop.sh` devuelve código 3.

## Evidencia de `CAL-F1-DNS-003`

El manifiesto registró:

- propósito `calibration`;
- commit `9f879ad8d81814d0c7b2c66e8d10b2ef8419cdb8`;
- árbol Git limpio;
- escenario `dns-valid`, clase `benign`;
- salida del escenario 0;
- espera de estabilización de 9 segundos;
- estado `completed` y `evidence.complete=true`.

Resultados cuantitativos:

| Control | Resultado |
|---|---:|
| consultas DNS solicitadas | 3 |
| respuestas DNS `NOERROR` observadas | 3 |
| paquetes nuevos según Suricata | 6 |
| `kernel_drops` | 0 |
| `kernel_ifdrops` | 0 |
| `decoder.invalid` | 0 |
| `alert_queue_overflow` | 0 |
| registros EVE esperados/extraídos | 7 / 7 |
| eventos DNS request/response | 3 / 3 |
| eventos `stats` dentro de la ventana | 1 |
| muestras de recursos | 7 |
| bytes de error del sampler | 0 |

Los trece archivos listados en `SHA256SUMS` devolvieron `OK`. Al finalizar no existía el bloqueo `.active` y el PID local del sampler ya no estaba en ejecución.

Los artefactos se encuentran en:

```text
artifacts/campaigns/CAL-F1-DNS-003/
```

Este directorio está excluido de Git. Para verificarlo en VM01:

```bash
cd artifacts/campaigns/CAL-F1-DNS-003
sha256sum -c SHA256SUMS
jq '{status, git, evidence}' manifest.json
jq . deltas.json
```

## Interpretación y límites

- Los seis paquetes corresponden a las tres solicitudes y tres respuestas DNS observadas; el evento `stats` no es un paquete adicional.
- Cero drops es válido para esta ventana y esta carga, no para cargas futuras.
- La serie mide el proceso Suricata desde VM01 sobre PPI-MGMT; esas consultas no atraviesan la interfaz `ens35` capturada y no contaminan el tráfico experimental de PPI-LAN.
- EVE puede contener eventos operativos como `stats`; la futura extracción de features debe filtrar por tipo y ventana, no asumir que cada línea representa un flujo.
- La campaña sigue siendo calibración. No debe entrar en entrenamiento, validación ni prueba.
- El orquestador aún no captura PCAP. Esa función es obligatoria antes de construir features L3/L4 defendibles.

## Revisión cruzada

Se intentó dos veces una revisión no interactiva de Claude Code 2.1.216: una revisión amplia y otra limitada a lectura, con esfuerzo bajo y límite de 90 segundos. Ninguna produjo un informe antes del límite. Por tanto, este cambio **no se declara aprobado por Claude**; la revisión adversarial queda pendiente para una sesión de Claude operativa. Codex realizó las pruebas positivas, negativas y de regresión descritas en este documento.

## Decisión siguiente

No iniciar aún la campaña F1 completa. El siguiente gate es diseñar e implementar captura PCAP acotada por campaña, con rotación, estimación de disco, filtro sobre `ens35`, permisos mínimos y verificación de paquetes de 500–1500 bytes. Después se repetirá G3 con DNS y una descarga HTTP breve antes de producir tráfico legítimo pesado.
