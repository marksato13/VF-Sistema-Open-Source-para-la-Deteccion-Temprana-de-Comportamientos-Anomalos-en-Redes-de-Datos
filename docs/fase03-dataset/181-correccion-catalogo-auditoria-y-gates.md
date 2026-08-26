# 181 · Corrección del catálogo de anomalías, la auditoría almacenada y los gates

**Fecha:** 25 de agosto de 2026 · `America/Lima`
**Alcance:** Bloque 0 del plan de datasheet. Corrige información publicada que
contradice al dataset congelado. **No modifica el dataset ni el modelo.**

## Motivo

Una evaluación externa del estado del dataset (61/100 sobre rúbrica de
datasheet) señaló que varias fuentes del repositorio ya no describen el corpus
vigente. Se verificaron una por una contra los artefactos antes de actuar:
todas las afirmaciones se confirmaron.

---

## D-30 · El número de perfiles normales estaba mal en cinco documentos

**Severidad:** media · **Estado:** corregida

**Hecho.** Cinco documentos afirmaban que el dataset contiene **38 perfiles**
normales repartidos en las tres particiones.

**Evidencia.** Derivado de `artifacts/dataset/multilayer-v2-normal.csv`
agrupando `campaign_id` sin su sufijo de repetición: **44 perfiles**, y los
**44 aparecen en `train`, `validation` y `test`**.

**Riesgo.** El número sostiene el argumento de validez externa (D-09). Un
dictaminador que lo recalcule encuentra una discrepancia en el dato que la
propia tesis usa para declarar su limitación principal de diseño muestral.

**Corrección.** `38 perfiles` → `44 perfiles` en los cinco documentos y en
`scripts/entregables/generar_informe_word.py`; regenerado el `.docx` de
`02-validacion-y-confiabilidad`.

**No corregido a propósito.**
`docs/fase03-dataset/178-plan-expansion-variantes-N1-N2.md:114` conserva su
`38 perfiles distintos (12 actuales + 26 nuevos)`: es una **proyección
histórica** escrita antes de ejecutar la expansión. Reescribir un plan pasado
para que coincida con su resultado falsifica el registro.

---

## D-31 · El catálogo de anomalías declaraba 3 de 9 familias

**Severidad:** alta · **Estado:** corregida

**Hecho.** `configs/campaigns/multilayer-v2-anomalies.json` declaraba tres
perfiles. El dataset contiene nueve familias.

**Evidencia.** Familias derivadas del CSV congelado:

| Familia | Origen | Ventanas | Episodios |
|---|---|---|---|
| `ANOM-AUTH-FAIL-50` | VM05 reetiquetado | 6 | 4 |
| `ANOM-DNS-NX-200` | VM05 reetiquetado | 6 | 4 |
| `ANOM-SYN-RATE-10` | VM05 reetiquetado | 6 | 4 |
| `ANOM-KALI-DNS-ENTROPY-50` | VM04 Kali | 21 | 20 |
| `ANOM-KALI-PASSWORD-SPRAY-50` | VM04 Kali | 29 | 20 |
| `ANOM-KALI-PORT-SCAN` | VM04 Kali | 20 | 20 |
| `ANOM-KALI-PORT-SCAN-WIDE` | VM04 Kali | 20 | 20 |
| `ANOM-KALI-SYN-RATE-50` | VM04 Kali | 31 | 20 |
| `ANOM-KALI-UDP-PROBE-50` | VM04 Kali | 40 | 20 |
| **Total** | | **179** | **132** |

El reparto resultante —**161 ventanas Kali reales / 18 heredadas**— coincide
exactamente con el ya documentado, lo que confirma la derivación.

**Riesgo.** El archivo no podía usarse como catálogo de procedencia: dos
tercios de la evidencia de ataque no tenían declaración de origen, escenario
ni señales esperadas.

**Corrección.** Las seis familias de Kali se añaden en una clave **separada**,
`kali_profiles`, no en `profiles`.

**Por qué separadas y no en la misma lista.** Son dos contratos distintos y
mezclarlos habría degradado dos garantías reales:

1. `profiles` exige que el `id` termine en el mismo número que aparece en
   `args` — una regresión que capturó un fallo real (`ANOM-SYN-RATE-50`
   declaraba `args=["10"]`). `ANOM-KALI-PORT-SCAN` no tiene conteo, así que
   añadirlo ahí obligaba a **debilitar esa guarda**.
2. `profiles` valida contra `ALLOWED_SCENARIOS`, la lista blanca del generador
   **benigno** `run-benign.sh`. Meter ahí `tcp-syn-rate` o `password-spray`
   habría hecho ejecutable tráfico ofensivo por la ruta benigna. Es una
   regresión de seguridad, no una molestia de esquema.

Se añade `ALLOWED_KALI_SCENARIOS` en `scripts/f1/validate_matrix.py`, poblada
con los seis escenarios del `case` de `scripts/campaign/run-f1-kali.sh:24`.

Cada perfil declara ahora `origin`, `traffic_class`, `runner`,
`observed_windows` y `observed_episodes`; y el archivo lleva un
`dataset_snapshot` con las cifras **derivadas del CSV**, no transcritas.

---

## D-32 · El reporte de auditoría almacenado describía otro dataset

**Severidad:** alta · **Estado:** corregida

**Hecho.** `artifacts/dataset/multilayer-v2-audit-report.json` informaba 75
ventanas normales, 18 anómalas, tres variables constantes y cero duplicados.

**Inferencia (separada del hecho).** Esas cifras corresponden al corpus
congelado del 14 de agosto, que sigue archivado en
`artifacts/dataset/archive/`. El reporte quedó sin regenerar tras la expansión.

**Riesgo.** Es el único artefacto que un tercero leería para juzgar la calidad
del dataset, y afirmaba `gates.pass=true` sobre un corpus que ya no existía.

**Corrección.** Reporte regenerado sobre los CSV vigentes. El anterior se
**archiva, no se borra**, como
`archive/multilayer-v2-audit-report.2026-08-13-stale-75-18.json`.

Resultado vigente: 1 373 / 179 ventanas · 220 / 132 episodios · 28 columnas ·
1 constante · 14 grupos duplicados / 36 filas (22 excedentes) · sin faltantes ·
sin episodios repartidos · `pass = true`.

---

## D-26 · Duplicados y constantes no eran gates

**Severidad:** baja · **Estado:** corregida

**Hecho.** `gates.pass=true` convivía con 22 filas duplicadas y una variable
constante, porque ninguna de las dos condiciones era un gate.

**Corrección.** Cuatro gates nuevos en `scripts/dataset/audit_multilayer_v2.py`:

| Gate | Criterio | Tolerancia |
|---|---|---|
| `constants_declared` | Toda constante debe estar en `DECLARED_CONSTANTS` | Cero |
| `no_duplicate_crossing_label` | Ningún grupo duplicado cruza `normal`/`anomaly` | Cero |
| `no_duplicate_crossing_partition` | Ningún grupo duplicado cruza particiones | Cero |
| `duplicates_within_tolerance` | Filas excedentes / total | 2 % declarado |

**Limitación declarada.** La tolerancia del 2 % es un **presupuesto elegido, no
derivado de los datos**: el valor actual es 1,42 % y pasa. Los gates con dientes
reales son los tres de tolerancia cero — un duplicado que cruza etiqueta o
partición indica fuga y falla siempre, sin importar el volumen.

Una constante **nueva** falla el gate: `DECLARED_CONSTANTS` solo contiene
`tls_handshake_failure_ratio_60s`, cuya no observabilidad está documentada en
[`175-limite-tls-handshake-failure-ratio.md`](175-limite-tls-handshake-failure-ratio.md).

---

## D-35 · Los generadores de Word no eran reproducibles desde un clon

**Severidad:** media · **Estado:** corregida · *Hallazgo colateral, no estaba
en el plan del bloque*

**Hecho.** Al regenerar el `.docx` por el cambio de `38` a `44`, el archivo
resultante pasó de 158 135 a 140 667 bytes. La comparación con la versión
versionada mostró **una imagen menos**: 2 → 1.

**Causa.** `scripts/entregables/generar_informe_word.py:29` y
`generar_ficha_word.py:41` tomaban el logo institucional de un directorio
*scratchpad* de sesión, efímero y externo al repositorio. El directorio se
vació entre sesiones y el logo dejó de existir.

**Por qué pasó desapercibido.** Ambos scripts hacían `if LOGO.exists():` y
omitían la carátula **en silencio** cuando el archivo faltaba. Un fallo que no
grita se convierte en un documento entregado sin portada institucional.

**Riesgo.** Cualquiera que clonara el repositorio y regenerara los entregables
obtenía documentos distintos a los publicados, sin ningún aviso. Es
exactamente la clase de irreproducibilidad que el proyecto exige detectar en
otros componentes.

**Corrección.** El logo se recuperó del `.docx` versionado
(`word/media/image1.png`, PNG 1042 × 251) y se guardó en el repositorio como
`docs/entregables/assets/logo-upeu.png`. Ambos scripts apuntan ahora a esa
ruta relativa a `REPO` y **abortan con error** si falta.

**Verificación.**

| Prueba | Resultado |
|---|---|
| Regenerar con el logo presente | 66 párrafos · 11 tablas · **2 imágenes**, idéntico en estructura a la versión versionada ✅ |
| Regenerar con el logo ausente | `falta el logo: …` · `exit=1` ✅ |

---

## Verificación

**Prueba positiva.** El reporte regenerado da `pass = true` con 1 373 / 179
ventanas, y sus `normal_sha256` / `anomaly_sha256` coinciden con los CSV.

**Prueba negativa.** Sobre copias sintéticas de los CSV:

| Inyección | Gate | Resultado |
|---|---|---|
| Fila clonada de `train` a `test` | `no_duplicate_crossing_partition` | **FAIL** ✅ |
| `syn_rate_10s` forzada constante en ambos CSV | `constants_declared` | **FAIL** ✅ |
| Escenario inexistente en `ALLOWED_KALI_SCENARIOS` | `test_kali_scenario_allowlist_matches_runner` | **FAIL** ✅ |

> El primer intento de la prueba de constantes forzó el valor solo en el CSV
> normal y dio `OK`: el auditor evalúa constancia sobre normal+anómalo unidos.
> Fallo de la prueba, no del gate; se repitió sobre ambos archivos.

**Suite completa:** 88 tests en verde, 14 de ellos en
`tests/test_multilayer_v2_matrix.py` (tres nuevos).

**Integridad del dataset congelado.** SHA-256 idénticos antes y después:

```
3846d44c0fe32ac4…  multilayer-v2-normal.csv
d115ef987cbd8451…  multilayer-v2-anomalies.csv
```

## Qué NO se hizo

- No se tocaron los CSV, el modelo ni el manifiesto.
- No se renombró el dataset a `v2.1`: sigue siendo `multilayer-v2` congelado.
  Marcar una variable como no observable es una anotación documental, no un
  corpus nuevo.
- No se creó todavía el datasheet canónico (D-29): es el bloque 2.
