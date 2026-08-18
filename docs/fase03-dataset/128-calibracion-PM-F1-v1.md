# Calibración atómica PM-F1-v1 y congelamiento de R04

Fecha: 6 de agosto de 2026. Estado: **CALIBRACIÓN EJECUTADA UNA VEZ, VERIFICADA Y CONGELADA**.

## Alcance y secuencia

El calibrador publicado en el commit
`b94035e9b343c0da3144169fb970eb5c096ae0f0` pasó primero un preflight completo:

| Gate | Resultado |
|---|---:|
| Train R01–R03 | 87 campañas / 224 ventanas |
| Validation R04 | 29 campañas / 72 ventanas |
| Selección SHA-256 | `bd280425…ad9331` |
| Git | limpio, commit exacto |
| Entorno | CPython 3.14.4 / requisitos exactos |
| Destino y lock | ausentes |
| Artefactos R05 enumerados o leídos | no |

Claude/Haiku autorizó el comando exacto después del preflight. Se ejecutó
`--execute-once` una sola vez, sin reintentos, y terminó correctamente a las
`2026-08-06T19:13:54.949961-05:00`. El resultado se publicó atómicamente en:

```text
/srv/ppi-evidence/artifacts/models/pm-f1-v1-calibration
```

La carpeta ocupa 6.2 MiB y contiene `manifest.json`, tres CSV sellados, seis
modelos `joblib` y un `SHA256SUMS` exhaustivo. R05 no se enumeró ni se leyó.

## Resultado principal congelado

`if_window` conserva las 224 ventanas train, las catorce features sin escala y
los parámetros pre-registrados. Sobre las 72 ventanas R04:

```text
alpha = 0.05
n = 72 ventanas
k = floor(0.05 * 72) = 3
threshold = s(4) = -0.5667565423690721
alerta si score < threshold
```

La cuarta observación define el umbral y permanece normal. El campo
`threshold_tie_count=1` cuenta esa misma observación; no existió un empate
múltiple en el umbral. Las tres alertas normales de calibración fueron:

| Orden | Índice validation | Campaña | Ventana UTC | Vector |
|---:|---:|---|---|---|
| 1 | 36 | `TLS-SESSIONS-20/R04` | `2026-08-05T17:57:30Z` | unseen |
| 2 | 37 | `TLS-SESSIONS-20/R04` | `2026-08-05T17:57:40Z` | unseen |
| 3 | 4 | `DNS-MIXED-50-10/R04` | `2026-08-05T02:23:00Z` | seen |

La fila normal que fija `s(4)` es el índice 44 de `HTTP-C8/R04`, score
`-0.5667565423690721`. La cola inferior procede de sólo 2/29 campañas: queda
marcada como **sensible al agrupamiento**. El 3/72 observado es consecuencia
mecánica de la regla de calibración y no demuestra FPR poblacional, detección,
precisión, recall o generalización.

## Sensibilidades y comparadores

| Pipeline | Rol | Filas de ajuste | Umbral R04 | Alertas / campañas |
|---|---|---:|---:|---:|
| `if_window` | principal | 224 | -0.5667565423690721 | 3 / 2 |
| `if_scaled` | sensibilidad | 224 | -0.5667565423690721 | 3 / 2 |
| `if_campaign_expanded` | sensibilidad | 7,308 | -0.5605501161648438 | 3 / 2 |
| `if_exact_collapsed` | sensibilidad | 206 | -0.5886583526588292 | 3 / 2 |
| `lof_scaled` | comparador | 224 | -2.1660296358363205 | 3 / 3 |
| `ocsvm_scaled` | comparador | 224 | 0.9891357852802896 | 3 / 3 |

`if_scaled` y `if_window` comparten umbral y cola principal, pero sus arrays no
son idénticos: la diferencia absoluta máxima fue `7.802013962310284e-05`. No se
presentan como equivalentes matemáticos. Ninguna sensibilidad o comparador puede
reemplazar al IF principal por este resultado.

En las diez semillas `20260804..20260813`, el umbral `if_window` tuvo mínimo
`-0.5715227526806155`, mediana `-0.5654700477457223` y máximo
`-0.5593051553420559`. Todas conservaron tres alertas en dos campañas, pero no
la misma identidad: `TLS-SESSIONS-20/R04` apareció siempre y la otra campaña
alternó entre `DNS-MIXED-50-10`, `HTTP-C8` y `TCP-REFUSED-5`. Esto demuestra
estabilidad del conteo observado, no estabilidad completa del ranking.

## Cruces exactos seen

La selección sellada confirma 10/72 filas validation con igualdad decimal exacta
de las catorce features respecto de train:

| Fila R04 | Coincidencia train |
|---|---|
| `DNS-VALID-10`, fila 0 | R01/R02/R03, fila 0 |
| `DNS-MIXED-20-2`, fila 0 | R01/R02/R03, fila 0 |
| `DNS-MIXED-50-10`, fila 0 | R01/R02/R03, fila 0 |
| `PING-100`, fila 1 | R03, fila 1 |
| `HTTP-404-5`, fila 0 | R02/R03, fila 0 |
| `HTTP-MULTI-1`, fila 0 | R01/R02/R03, fila 0 |
| `HTTP-MULTI-5`, fila 0 | R01/R02/R03, fila 0 |
| `TCP-REFUSED-5`, fila 0 | R03, fila 0 |
| `UDP-25M`, fila 1 | R02, fila 1 |
| `UDP-50M`, fila 1 | R01, fila 1 |

La única alerta principal `seen` es `DNS-MIXED-50-10/R04`; las otras dos son
las ventanas `unseen` de `TLS-SESSIONS-20/R04`. No se eliminan ni se recalcula
el umbral sobre 62 filas porque eso violaría el protocolo congelado.

## Integridad y reproducción

`sha256sum -c SHA256SUMS` validó los diez archivos. Una reconstrucción
independiente desde `validation-scores.csv` reprodujo exactamente los seis
umbrales, índices y alertas. Los seis modelos se recargaron en el entorno
congelado y sus `score_samples` sobre R04 fueron idénticos bit a bit a los CSV.

Hashes principales:

| Artefacto | SHA-256 |
|---|---|
| `selection.csv` | `bd28042520e77989a0824b2a5a8c029051aae3c3031b5ef5735e429cddad9331` |
| `validation-scores.csv` | `ede866dd3e0fb66534e58e7dfa263da139d93e073e5cf78f4523714b9a139101` |
| `stability-scores.csv` | `6f6be0e9e933c648d93286d49c5152f0f30386da6a301c4a7e81ee452ddd3fe5` |
| `models/if_window.joblib` | `366629337fac39094d6872b8097d4398d1259518c76b451214862a2bd87d0f83` |
| calibrador | `61c000bf0302c6bc1e75aa85f018fefc116418c33c75ba0360817cd658a70325` |
| ensamblador | `7735784d12507c8239afb562d9335b73dbe6100b5e8875ed35c2a44d3f122add` |

Los tiempos guardados son descriptivos de VM01 y no un benchmark productivo.
Los `joblib` sólo se cargarán con las versiones exactas del manifest.

## Declaración de congelamiento

**PM-F1-v1 queda congelado** con `if_window`, seed `20260804`, las catorce
features, el preprocesamiento publicado y el umbral principal exacto
`-0.5667565423690721`. No se recalibra, reentrena, selecciona ni modifica a
partir de R05, F2, F3 o F4.

Esta publicación cierra el requisito previo de calibración. No abre R05 por sí
sola: el siguiente paso es preparar y revisar el procedimiento de ejecución
única de R05, incluyendo separación de lectura, scoring sin `fit`, hashes y
política de fallo. No se inicia ninguna campaña R05 hasta cerrar ese gate.
