# Archivado trazable de intentos experimentales fallidos

Fecha: 23 de julio de 2026. Estado: procedimiento implementado; ejecución sobre `F1N-HTTP-C8-R01` pendiente de la validación y despliegue descritos aquí.

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
