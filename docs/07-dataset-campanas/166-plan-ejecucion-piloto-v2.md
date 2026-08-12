# Plan ordenado de ejecución v2

Fecha: 2026-08-12. Estado: primer intento detenido por dos defectos de
integración (permisos ejecutables del extractor y fase v2 no propagada). La
captura produjo PCAP/EVE íntegros, pero no se acepta como dataset. Ambos
defectos ya fueron corregidos; debe repetirse el piloto desde cero con un ID
nuevo o archivando el artefacto fallido.

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
