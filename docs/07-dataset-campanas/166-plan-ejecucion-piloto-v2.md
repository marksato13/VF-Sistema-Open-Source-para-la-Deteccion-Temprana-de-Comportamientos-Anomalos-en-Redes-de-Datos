# Plan ordenado de ejecución v2

Fecha: 2026-08-12. Estado: primer intento detenido por dos defectos de
integración (permisos ejecutables del extractor y fase v2 no propagada). La
captura produjo PCAP/EVE íntegros, pero no se acepta como dataset. Ambos
defectos ya fueron corregidos. El artefacto fallido fue puesto en cuarentena
en `/srv/ppi-evidence/artifacts/quarantine/` y no forma parte del dataset.

El piloto de calibración `CAL-G6-DNS-MULTI-10-R01` pasó: fase `F2`, evidencia
completa, 20 paquetes PCAP, 30 eventos EVE reconciliados, `kernel_drops=0`,
`decoder_invalid=0`, CSV v2 con 28 columnas y una fila elegible. Queda fuera
de train/test por `partition=excluded_calibration`.

La batería completa de pilotos normales v2 también pasó. Perfiles aceptados:
`DNS-MULTI-10`, `API-NORMAL-20`, `API-AUTH-FAIL-20`, `TCP-100M-V2`,
`HTTPS-SESSIONS-V2`, `MIXED-V2`, `PING-V2`, `HTTP-404-V2`, `DNS-MIXED-V2` y
`TCP-REFUSED-V2`. Cada uno tiene fase `F2`, evidencia completa, CSV v2 y al
menos una fila elegible. Las filas siguen excluidas de entrenamiento por ser
calibración.

El primer intento oficial `F2N-DNS-MULTI-10-R01` no se acepta: el proceso del
orquestador terminó antes de ejecutar el cierre `stop.sh`, dejando manifiesto
`running` y captura parcial. El sensor quedó inactivo y la evidencia fue puesta
en cuarentena como `F2N-DNS-MULTI-10-R01-official-aborted`. No se avanzará a
R02 ni a otro perfil hasta corregir y probar este cierre de proceso.

## Orden obligatorio

1. Confirmar Git limpio, volumen `/srv/ppi-evidence` montado y margen mínimo.
2. Ejecutar `F2N-DNS-MULTI-10-R01` como piloto normal.
3. Revisar manifiesto, PCAP, EVE, métricas, JSONL, extracción v2 y hashes.
4. Si el piloto pasa, ejecutar un piloto de cada perfil normal.
5. Congelar el contrato y lanzar cinco repeticiones por perfil.
6. Construir el dataset por `episode_id`; no repartir episodios entre particiones.
7. Reservar anomalías de Kali para evaluación ciega posterior.

## Gate de piloto

El piloto se acepta sólo con `status=completed`, `evidence.complete=true`,
`kernel_drops=0`, `decoder_invalid=0`, PCAP remoto/local coincidente, EVE
reconciliado, al menos una fila v2 elegible, reporte de extracción y hashes.
Un fallo detiene la secuencia y se documenta antes de continuar.

## Comando reproducible

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
  scripts/f1/run_matrix_profile_v2.sh \
  --profile DNS-MULTI-10 --repetition 1
```

El piloto usa la partición `train` sólo como clasificación provisional; no se
congela ni se entrena hasta completar la auditoría del ciclo normal.

Se añadió un cierre `EXIT` defensivo en `scripts/campaign/run-f1.sh`: si el
escenario o el proceso termina antes de invocar explícitamente `stop.sh`, se
intenta cerrar la captura y conservar el estado de evidencia. Las pruebas de
sintaxis y las 25 pruebas v2 pasan; debe repetirse `R01` para validar este
comportamiento en una captura real.

La revisión posterior endureció también `stop.sh`: ante un fallo de cierre
marca `close_failed` y conserva deliberadamente el lock, evitando iniciar una
nueva captura sobre evidencia remota incierta. Los intentos oficiales
abortados permanecen en cuarentena y no cuentan para el dataset.

## Primer piloto oficial aceptado (R01-B)

El piloto `F2N-DNS-MULTI-10-R01-B` se ejecutó con el orquestador persistente
en `tmux`, usando el sufijo de intento `B` para evitar reutilizar evidencia
de los intentos abortados. El resultado superó el gate:

- manifiesto `status=completed`, `phase=F2`, `scenario_exit_code=0`;
- `evidence.complete=true`, PCAP remoto/local verificado (2.300 bytes, 20
  paquetes), `kernel_drops=0` y cero fallos de validación;
- 30 eventos EVE reconciliados y 53 muestras del sensor, sin errores de
  `stderr`;
- extracción `multilayer-v2` con 28 columnas y una ventana elegible para
  entrenamiento (`rows=1`, `eligible_training_rows=1`).

El artefacto queda en la partición provisional `train` y todavía no se
congela el dataset. La fila se conserva en
`/srv/ppi-evidence/artifacts/features-v2/F2N-DNS-MULTI-10-R01-B/`; las
campañas abortadas anteriores siguen en cuarentena y no se mezclan.
