# Ensamblador seguro de F1

`build_f1_dataset.py` separa auditoría de construcción. La auditoría no escribe datasets y puede ejecutarse aunque F1 esté incompleta:

```bash
export PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts
python3 scripts/dataset/build_f1_dataset.py --audit-only
```

La construcción definitiva omite `--audit-only` y solo ocurre si existen exactamente las 145 celdas válidas de `f1-normal-v2`, no hay campañas inválidas y el repositorio está limpio:

```bash
export PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts
python3 scripts/dataset/build_f1_dataset.py
```

El destino es `$PPI_ARTIFACTS_ROOT/datasets/f1-normal-v2/`, fuera de Git. Sin la variable se conserva `artifacts/` como valor compatible para auditar los pilotos históricos; las campañas y el dataset oficiales requieren el volumen dedicado. Si el destino ya existe, el script se detiene y nunca reemplaza un dataset silenciosamente.

El ensamblador valida bundles SHA-256, manifiesto, ledger, argumentos del escenario, PCAP/EVE, reporte de extracción, CSV, commit Git, matriz, esquema, split y dominio de las 14 features. Una fila requiere historia causal completa, pero eso no sustituye `purpose=experiment` ni la partición oficial.
