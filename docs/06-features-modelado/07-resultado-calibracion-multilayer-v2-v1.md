# Resultado de la calibración `PM-multilayer-v2-v1`

- **Fecha:** 2026-08-17
- **Ejecutor:** Claude
- **Estado:** calibración completa, evaluación en un solo paso bloqueado, hashes verificados. **Decisión de modelo final pendiente de tu confirmación** (ver sección final).
- **Artefacto:** `/srv/ppi-evidence/artifacts/models/pm-multilayer-v2-v1-calibration/` (fuera de Git), `manifest.json` + 6 modelos `.joblib`, `SHA256SUMS` verificado íntegro.

## Resumen ejecutivo

Se calibraron y evaluaron 6 pipelines (Isolation Forest en 4 variantes + LOF + OCSVM) sobre el dataset ampliado (824 filas train / 273 validation / 276 test / 179 evaluación de anomalías), en un único paso bloqueado siguiendo `PM-multilayer-v2-v1` (`06-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md`). Ningún modelo se re-entrenó después de ver resultados.

**Hallazgo principal: OCSVM detecta sustancialmente mejor que todas las variantes de Isolation Forest, con FPR comparable.**

| Modelo | Umbral (score) | FPR test (276 ventanas) | Detección anomalías (179 ventanas) | Detección Kali real (161 ventanas) |
|---|---|---|---|---|
| `if_primary_weighted` (principal, ponderado por episodio) | -0.5061 | 4.35% | 54.2% (97/179) | 52.8% |
| `if_uniform` (sin ponderar) | -0.5543 | 5.07% | 57.5% (103/179) | 55.9% |
| `if_scaled_weighted` | -0.5042 | 4.35% | 54.2% (97/179) | 52.8% |
| `if_exact_collapsed` | -0.5543 | 5.07% | 57.5% (103/179) | 55.9% |
| `lof_scaled` (comparador) | -2.9405 | 3.62% | 43.0% (77/179) | 40.4% |
| **`ocsvm_scaled` (comparador)** | **1.8126** | **4.71%** | **88.3% (158/179)** | **88.8%** |

## Desviación documentada del protocolo original (`PM-F1-v1`)

La rama de sensibilidad "expansión exacta por MCM" del protocolo anterior es matemáticamente inviable en este dataset: los episodios de train van de 1 a 53 filas (antes 1 a 7), el MCM de todos los valores distintos es 15,915,900, lo que produciría ~2.1 mil millones de filas expandidas. Verificado **antes** de fijar el protocolo (no después de ver resultados): `sample_weight=1/filas_por_episodio` sí cambia los scores en este dataset (delta máximo absoluto 0.1194), a diferencia del dataset anterior donde no cambiaba nada — 5 de 132 episodios (3.8%) concentran el 31.7% de las filas de train (las descargas de 1GB). Por eso el modelo "principal" declarado es `if_primary_weighted`, no el IF sin ponderar. Esta decisión se tomó y se registró en el manifiesto **antes** de ejecutar la calibración, no se ajustó después de ver que OCSVM ganaba.

## El hallazgo más importante: dónde falla Isolation Forest

Desglose por familia de ataque (`if_primary_weighted`):

| Familia | Detectadas / ventanas |
|---|---|
| `ANOM-DNS-NX-200` (heredada) | 6/6 (100%) |
| `ANOM-KALI-DNS` (dns-entropy) | 21/21 (100%) |
| `ANOM-KALI-PORT-SCAN` | 20/20 (100%) |
| `ANOM-KALI-PORT-SCAN-WIDE` | 20/20 (100%) |
| `ANOM-AUTH-FAIL-50` (heredada) | 5/6 (83%) |
| `ANOM-KALI-PASSWORD-SPRAY-50` | 24/29 (83%) |
| `ANOM-SYN-RATE-10` (heredada) | 1/6 (17%) |
| **`ANOM-KALI-SYN-RATE-50`** | **0/31 (0%)** |
| **`ANOM-KALI-UDP-PROBE-50`** | **0/40 (0%)** |

Isolation Forest **no detecta absolutamente nada** de las familias `tcp-syn-rate` (intentos rápidos de conexión, mi sustituto sin privilegios de `nping --tcp`) ni `udp-probe` (sondas UDP al puerto 53). Esto responde directamente la pregunta que dejé abierta en el protocolo: *¿`unique_dst_port_ratio_30s` ya resuelve el punto ciego de port-scan que el MVP necesitó parchar con un heurístico?* — **sí, completamente** (port-scan y port-scan-wide: 100% de detección). Pero aparece un punto ciego **nuevo y distinto**: ráfagas de baja intensidad tipo SYN-flood/UDP-probe.

**OCSVM sí detecta estas dos familias:** `ANOM-KALI-SYN-RATE-50` 26/31 (84%), `ANOM-KALI-UDP-PROBE-50` 40/40 (100%). Su punto débil es el opuesto: `ANOM-AUTH-FAIL-50` 3/6 (50%) y `ANOM-KALI-PASSWORD-SPRAY-50` 16/29 (55%), donde IF es más fuerte (83%).

## Estabilidad entre semillas

10 semillas (`20260817`-`20260826`) para `if_primary_weighted`: umbral estable entre -0.502 y -0.512, siempre 13 alertas exactas (por diseño del cuantil `alpha=0.05`), 7-9 episodios distintos originando esas alertas. Sin inestabilidad preocupante.

## Verificación de integridad

- `SHA256SUMS` de los 6 modelos + manifiesto: verificado íntegro con `sha256sum -c` (sin fallos).
- Auditoría del dataset re-ejecutada en caliente dentro del calibrador (no confía en un reporte viejo): `gates.pass=true`.
- `git_dirty_before_and_after=false`, commit `97f0675` verificado antes y después de calibrar.
- Entorno congelado verificado exacto: CPython 3.14.4, scikit-learn 1.9.0, todas las dependencias de `requirements-model.txt` coinciden.

## Decisión pendiente: ¿qué modelo es el resultado final?

`PM-F1-v1` (el protocolo original que sirvió de plantilla) tenía la regla explícita "IF sigue siendo la conclusión principal aunque un comparador gane una métrica posterior". Pero **tu instrucción explícita para este proyecto** fue: *"la elección del modelo será de acuerdo a pruebas, ver con cuál funciona mejor"* — lo cual contradice esa regla heredada a propósito.

Dado ese mandato tuyo, mi recomendación es: **OCSVM como modelo líder** — detecta 88% de las anomalías reales (incluyendo las dos familias que IF no detecta en absoluto) con un FPR comparable (4.71% vs 4.35%). No es un caso de "espiar el test y elegir a posteriori": los 6 modelos se evaluaron una sola vez, en el mismo paso bloqueado, sin re-entrenar nada después de ver resultados — esto es exactamente la comparación empírica que pediste, no una fuga.

Advertencia honesta: OCSVM con `nu=0.05` está diseñado para considerar ~5% del propio train como atípico, lo que lo hace estructuralmente más "agresivo" — su FPR en test (dato nunca visto) sigue siendo bajo (4.71%), así que no parece ser solo agresividad sin fundamento, pero es una diferencia de naturaleza del modelo que vale la pena declarar, no ocultar.

**Necesito tu confirmación antes de declarar esto como resultado final** y avanzar a la siguiente fase (motor de decisión), porque cambia cuál modelo se congela y qué joblib se carga en producción.
