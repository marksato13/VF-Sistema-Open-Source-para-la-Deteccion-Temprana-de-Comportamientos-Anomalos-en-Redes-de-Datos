# Cierre de captura y construcción del dataset F1 R05

Fecha: 9 de agosto de 2026. La matriz normal F1 queda completa: **145/145
campañas aceptadas**, R05 29/29, cero celdas faltantes, cero campañas
inválidas/advertencias y `ready_to_build=true`.

El ensamblador generó `/srv/ppi-evidence/artifacts/datasets/f1-normal-v2/` y
verificó sus bundles con `sha256sum -c SHA256SUMS`. El resultado contiene 224
filas de entrenamiento, 72 de validación y 75 de prueba, más la cabecera en
cada CSV (225/73/76 líneas físicas). Hashes: `train.csv`
`c6c1028977da3b9d17b192df4c74de71e081a5e93232ed4bda34529a73a0da07`,
`validation.csv`
`979536f4f9eed09baee08d79511a49137ab5bfef598c37986446a521c8b25f8d`,
`test.csv` `1482a1ca406ee830aed172b4c692dfb8825163dae505b892e359572ded7af07b`,
manifest `8e825830957c55bff763a5962c740e3bb91df1703ce12d1ae91d559a4899d378`.

La auditoría final registra 41 vectores duplicados y 24 cruces entre
particiones. En particular, una ventana de `UDP-50M-R05` coincide exactamente
con `UDP-50M-R03`; se conserva para reproducibilidad, pero debe excluirse o
ponderarse al estimar independencia. Las ventanas de una misma campaña también
son autocorrelacionadas.

Este cierre sólo construye el dataset; no ejecuta scoring, calibración ni
reentrenamiento. El siguiente paso autorizado es la revisión de duplicados y la
definición documentada de la política de exclusión/ponderación antes de medir
Isolation Forest y comparar modelos.
