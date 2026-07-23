# Archivado trazable de intentos experimentales fallidos

Fecha: 23 de julio de 2026. Estado: procedimiento implementado, desplegado y aplicado a `F1N-HTTP-C8-R01/attempt-01`.

## Objetivo

Una celda oficial fallida debe conservarse como evidencia negativa, pero no puede permanecer en los directorios activos con el mismo identificador canónico: impediría repetir la celda y aparecería como inválida para el ensamblador. El archivado separa ambos conceptos sin borrar, sobrescribir ni alterar el intento original.

No se usa un sufijo nuevo para el reintento oficial. La matriz y el ensamblador esperan el ID canónico `F1N-HTTP-C8-R01`; la distinción entre ejecuciones se conserva mediante `attempt-01` dentro del archivo de fallos.

## Condiciones previas

El script `scripts/campaign/archive-failed-attempt.sh` exige:

- repositorio Git limpio;
- ausencia del bloqueo `campaigns/.active`;
- manifest con el ID solicitado, `purpose=experiment`, `status=evidence_failed` y `evidence.complete=false`;
- ledger del mismo ID con `status=failed`;
- ausencia de features activas del intento rechazado;
- validación completa de `SHA256SUMS`;
- helper remoto idéntico al archivo versionado.

El modo `--dry-run` comprueba estas condiciones y muestra los destinos sin mover evidencia.

## Movimiento recuperable

Para `F1N-HTTP-C8-R01 attempt-01`, las rutas son:

| Elemento | Origen activo | Destino de archivo |
|---|---|---|
| PCAP y salida de `tcpdump` en Sensor | `/var/lib/ppi-captures/F1N-HTTP-C8-R01/` | `/var/lib/ppi-captures-failed/F1N-HTTP-C8-R01/attempt-01/` |
| bundle en VM01 | `/srv/ppi-evidence/artifacts/campaigns/F1N-HTTP-C8-R01/` | `/srv/ppi-evidence/artifacts/failed-attempts/F1N-HTTP-C8-R01/attempt-01/campaign/` |
| ledger en VM01 | `/srv/ppi-evidence/artifacts/g6-ledger/F1N-HTTP-C8-R01.json` | `/srv/ppi-evidence/artifacts/failed-attempts/F1N-HTTP-C8-R01/attempt-01/ledger.json` |

El helper remoto `ppi-pcap-control archive` solo acepta un ID seguro y la etiqueta `attempt-NN`. Rechaza capturas activas y colisiones. Después del movimiento, el controlador verifica los SHA-256 remotos contra `pcap-remote-SHA256SUMS`.

En VM01 se usa primero un directorio de staging. Si falla una comprobación local, un manejador restaura bundle y ledger a sus rutas originales. Al finalizar se crea `archive.json` con fecha, commits, rutas originales, hashes del manifest, lista de hashes y ledger, además del resultado remoto.

## Criterio de autorización del reintento

Después del archivado deben cumplirse conjuntamente:

1. el bundle, ledger y PCAP fallidos existen en sus destinos de archivo;
2. no existen en las raíces activas;
3. `SHA256SUMS` y los hashes remotos continúan válidos;
4. el ensamblador informa 15 celdas aceptadas, 0 inválidas y 130 faltantes;
5. la calibración `CAL-G6-HTTP-C8-R01` continúa excluida por `purpose=calibration`;
6. no existe captura, bloqueo ni proceso residual.

Solo entonces se ejecuta otra vez el ID oficial `F1N-HTTP-C8-R01`. Si se acepta, el estado esperado pasa a 16 aceptadas, 0 inválidas y 129 faltantes. El intento `attempt-01` permanece disponible para auditoría y comparación.

## Comandos

```bash
PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
  scripts/campaign/archive-failed-attempt.sh \
  F1N-HTTP-C8-R01 attempt-01 --dry-run

PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts \
  scripts/campaign/archive-failed-attempt.sh \
  F1N-HTTP-C8-R01 attempt-01
```

Estos comandos no son una política general para descartar resultados. Solo se aplican después de documentar la causa, aceptar formalmente el rechazo y obtener una calibración correctiva que habilite el reintento.

## Ejecución verificada

El procedimiento se publicó en el commit `3860c8648c40ec430b18c0a472be1e61b454a7e0`. Antes de mover evidencia:

- el SHA-256 del helper local y desplegado coincidió en `f4a0bf90d1f348f1173678c717f620fdad99c31325b0c5c7d5b5d47843a74b54`;
- la prueba negativa con etiqueta `../escape` fue rechazada;
- el helper informó captura `inactive`;
- el modo `--dry-run` terminó con `dry_run_pass`.

El archivado finalizó a las `2026-07-23T12:02:47-05:00`. `archive.json` conserva:

| Evidencia | SHA-256 |
|---|---|
| manifest rechazado | `8977d8fa626ca27ffb4044ee613338b83cdeb74b641acc7792cfedc439dcf5ca` |
| archivo `SHA256SUMS` del bundle | `436395442b08a5340687a055f37a72a866ca7ee86cc2f69a5bf662736a062306` |
| ledger fallido | `07df869c7f21636f015d24a6b01908a38c47cd63efb0c451b3a8cdcd37a3e8a1` |

El Sensor confirmó dos PCAP por 887,835,808 bytes. La comprobación remota posterior validó:

- `capture.pcap0`: `d75436e93d3a7155402d14f8a3225accade3743efa2ed56aeae057e3c0a30da4`;
- `capture.pcap1`: `917e0e6e85df9c69a41bf1272d182bb0e08b4a7475b55533b3f458650b79eee8`.

Las rutas activas dejaron de contener bundle, ledger y PCAP de `F1N-HTTP-C8-R01`; las tres copias existen en `attempt-01`. El ensamblador posterior informó exactamente 145 esperadas, 15 aceptadas, 0 inválidas, 0 advertencias y 130 faltantes. `CAL-G6-HTTP-C8-R01` continuó excluida con razón `not_experiment`.

Se intentó obtener una revisión adversarial de Claude antes del despliegue mediante dos ejecuciones de solo lectura con tiempo y presupuesto acotados. Ninguna produjo dictamen y ambas se detuvieron sin editar archivos ni operar el laboratorio. Por tanto, no se atribuye aprobación a Claude. La autorización operacional se sustenta en las pruebas reproducibles anteriores; la revisión cruzada queda pendiente para el resultado del reintento.
