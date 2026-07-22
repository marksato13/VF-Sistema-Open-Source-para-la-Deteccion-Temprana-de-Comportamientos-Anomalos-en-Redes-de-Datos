# Extractor multicapa v1

El extractor usa únicamente la biblioteca estándar de Python y `tcpdump` para la validación previa realizada por el orquestador. Admite PCAP clásico Ethernet/IPv4, incluso con cabeceras VLAN. Rechaza otros linktypes en lugar de interpretarlos silenciosamente.

Para extraer una campaña cerrada bajo el contrato G5:

```bash
export PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts
scripts/features/extract_campaign.sh ID-DE-CAMPAÑA
```

La salida queda en `$PPI_ARTIFACTS_ROOT/features/<ID>/`. Sin la variable se usa `artifacts/features/<ID>/` para mantener compatibles los pilotos históricos:

- `multilayer-v1.csv`: metadatos, soportes de auditoría y las 14 features en orden fijo;
- `extraction-report.json`: hashes de PCAP, EVE, esquema y CSV;
- `SHA256SUMS`: integridad de ambos productos derivados.

El wrapper exige campaña `completed`, `evidence.complete=true`, hashes originales válidos y `verified_at` en `pcap-start.json`. Las campañas anteriores a G5 no satisfacen este contrato y deben conservarse como calibración, no adaptarse modificando sus artefactos.

Pruebas:

```bash
python3 -m unittest -v tests/test_multilayer_features.py
```
