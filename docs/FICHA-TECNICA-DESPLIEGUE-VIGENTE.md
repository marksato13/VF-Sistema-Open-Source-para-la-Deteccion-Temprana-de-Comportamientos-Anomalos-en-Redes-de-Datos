# Ficha técnica — despliegue vigente de CyberFlow

**Propósito.** Fuente de verdad **única** del sistema tal como está desplegado. La
documentación del repositorio (README, instalación, configuración, replicación, cards)
se alinea a esta ficha. Describe lo que **corre**, no un objetivo.

**Corte:** 2026-10-09. Esta ficha **no modifica** artefactos, umbrales ni servicios.

## Cómo leer el estado de cada dato

- **[S]** verificado en Sensor1 por SSH (reconciliación del 2026-10-09).
- **[C]** verificado en el código de este repositorio.
- **[V]** pendiente de comprobación en vivo.

Evidencia de investigación (fijada al commit
[`bb6e91d784622aab52f8b9f579186e50484dfdf6`](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/tree/bb6e91d784622aab52f8b9f579186e50484dfdf6)
de `VF-PPI-TESIS-ORQUESTACION`):
[L — recalibración](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/L-recalibracion-seco-sensor1-2026-09-29.md) ·
[M — detección Kali](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/M-deteccion-kali-sensor1-2026-09-30.md) ·
[N — BLOCK en banco](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/N-e2e-enforcement-2026-09-30.md) ·
[O — LIMIT en vivo](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/04-evidencias/cyberflow/O-enforcement-vivo-campana-ataque-2026-10-01.md) ·
[31 — ablación](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/02-metodologia/comparacion-cyberflow-suricata/31-ABLACION-RESULTADO.md) ·
[32 — resumen](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/02-metodologia/comparacion-cyberflow-suricata/32-RESUMEN-RESULTADOS.md) ·
[diseño del enforcement](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/bb6e91d784622aab52f8b9f579186e50484dfdf6/01-arquitectura/DISENO-ENFORCEMENT.md).

Documentos de este repositorio: [`RECONCILIACION-MANIFIESTO-MOTOR.md`](RECONCILIACION-MANIFIESTO-MOTOR.md),
[`dataset/MODEL_CARD_IF_RECALIBRADO.md`](dataset/MODEL_CARD_IF_RECALIBRADO.md),
[`dataset/SYSTEM_CARD_MOTOR.md`](dataset/SYSTEM_CARD_MOTOR.md).

---

## 1. Modalidad de despliegue (hay dos; no confundirlas)

| Modalidad | Qué es | Dónde | Estado |
|---|---|---|---|
| **A — Sensor en línea, bloqueo local** | El sensor enruta y aplica `nftables` localmente; bloqueo binario de 120 s | Validación F6 (OCSVM) | **Histórica / laboratorio evaluado** |
| **B — Sensor por SPAN, enforcement distribuido** | El sensor observa por espejo, **sin IP**, y **no bloquea el tráfico copiado**. Decide y publica un **feed firmado**; un **agente en el host protegido** aplica `nftables` | Sensor1 | **Vigente** [S] |

Cadena vigente: **captura SPAN → motor → publicador → feed firmado (ed25519) → relay
(bastión) → agente (host) → `nftables`**, con alertas hacia Wazuh. Los diagramas
«sensor → nftables» describen la modalidad A y se rotulan como laboratorio.

## 2. Modelo activo [S]

| Propiedad | Valor |
|---|---|
| Identificador | `if_recalibrado_2026_09` |
| Tipo | `Pipeline` (escalador + Isolation Forest); el motor puntúa con `score_samples` |
| Artefacto | `artifacts/preliminar/if_recalibrado_desplegable.joblib` (en Sensor1; no se publica) |
| SHA-256 del artefacto vivo | `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a` |
| Manifiesto | `artifacts/preliminar/manifest-if-recalibrado.json` (el que usa el motor) |
| Umbral | `score_samples < −0,568892` **=** `decision_function < −0,068892` |
| Calibración | `alpha = 0,05` sobre validation; umbral **no** elegido sobre test; `calibrado_en_esta_red = true` |

**Tres modelos distintos en los artefactos; cada umbral va con su modelo, conjunto,
fecha y función de score, y nunca se intercambian:**
- **Laboratorio (histórico):** OCSVM `ocsvm_scaled`, umbral `1,8126`, FPR 4,71 % —
  [`MODEL_CARD_OCSVM.md`](dataset/MODEL_CARD_OCSVM.md). Promovido tras ver el test
  (sesgo de selección declarado).
- **Declarado principal en el experimento v2:** `if_primary_weighted` (manifiesto de
  laboratorio).
- **Activo hoy:** `if_recalibrado_2026_09` (esta ficha).

**Equivalencia de escalas (punto 10).** `entrenar_preliminar.py` informa
`decision_function`; el motor usa `score_samples`. En un Isolation Forest de sklearn
`decision_function = score_samples − offset_`, y con `contamination="auto"`
`offset_ = −0,5`; por eso −0,068892 − 0,5 = −0,568892. La comprobación sobre el
artefacto real se hace con
[`scripts/modeling/verificar_equivalencia_umbral.py`](../scripts/modeling/verificar_equivalencia_umbral.py),
que carga el `Pipeline`, lee `offset_`, contrasta ambas funciones y compara el umbral
que lee el motor (`detectors.<nombre>.calibration.threshold`) con el del informe de
calibración. **[S] Ejecutado sobre el artefacto vivo el 2026-10-10: `EQUIVALENTE`**
(`offset_ = −0,5`, desvío 0,0 en la relación entre funciones; el umbral del manifiesto
difiere del calibrado en 2,1·10⁻⁷ porque está redondeado a seis decimales). Evidencia:
[nota P](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/2e4f9accdf0b3b3352baf59b89fbc5934be8b66e/04-evidencias/cyberflow/P-equivalencia-umbral-sensor1-2026-10-10.md);
SHA-256 del manifiesto `564b3a080e22f20731d3a9ec8bde251cc166ce37be8e78e5247e4e3ed1e8fb5e`.

## 3. Contrato de variables [C]

| Esquema | Nº | Qué es | Relación con el modelo |
|---|---|---|---|
| [`configs/features/multilayer-v2.json`](../configs/features/multilayer-v2.json) | **28** | Contrato **del modelo** (L3/L4/L7) | El IF recalibrado **consume estas 28** |
| [`configs/features/multilayer-v3.json`](../configs/features/multilayer-v3.json) | **31** | Esquema del **extractor** (v2 + 3 de capa 2) | El modelo **no** usa las 3 de capa 2 |

- **Observables:** 27 de las 28; `tls_handshake_failure_ratio_60s` es constante
  estructural. La capa 2 queda fuera del scoring.
- El motor exige el contrato v2 (28) para el modelo y usa funciones del extractor v3
  para tratar la entrada.

## 4. Pipeline de datos [C]

El motor **no reparsea todo el anillo** en cada ciclo: mantiene un **buffer
incremental**. PCAP en anillo por tiempo (~240 s) y, de EVE, las líneas de los últimos
`--history-seconds` en memoria. Los atrasos medidos en F6 (mediana 45 s, máximo 208 s)
son de aquella versión; la actual debe medirse de nuevo.

## 5. Respuesta: niveles y condiciones [C]

Tres acciones: **PERMIT · LIMIT · BLOCK** (`scripts/engine/publicar_feed.py`).

| Señal | Acción |
|---|---|
| Ninguna (score ≥ umbral y ningún heurístico) | **PERMIT** (no genera entrada en el feed) |
| ALERT del **modelo** (score < umbral) | **LIMIT** — anomalía sin confirmar; degradar, reversible |
| Heurístico `brute_force` o `port_scan` | **BLOCK** |
| Heurístico `http_abuse` o `dns_entropy` | **LIMIT** |

Por IP gana la acción más severa del lote (BLOCK > LIMIT). Madurez, en tres
afirmaciones separadas:
- **LIMIT automático en vivo**, originado por el modelo: **validado** (nota O).
- **BLOCK aislado** con regla explícita en el host: **validado en banco** (nota N).
- **BLOCK automático de punta a punta** originado por la detección: **pendiente**.

## 6. Escalera de caducidad [C] — `scripts/engine/escalada.py`

| Evento | Caducidad |
|---|---|
| LIMIT | **300 s**, plano |
| BLOCK 1º | **300 s** |
| BLOCK 2º (dentro de 24 h) | **1800 s** |
| BLOCK 3º y siguientes | **3600 s** (tope) + marca de **revisión humana** |

Nunca hay bloqueo infinito automático; el contador decae a las 24 h sin reincidir.
`--ventana-segundos` del publicador (120 s) es la ventana de decisiones que se leen,
**no** un tiempo de bloqueo. El «bloqueo de 120 s» es de la modalidad A.

## 7. Infraestructura protegida [C]

`publicar_feed.py` y `scripts/enforce/agente_enforce.py` comparten una lista
nunca-bloquear (bastión `10.10.10.30`, sensor `10.10.60.11`, gateways `.1` de cada
VLAN, DNS/AD `10.10.10.20`). **Está fijada en el código de ambos** y debe pasar a
configuración por despliegue (mejora abierta).

## 8. Panel

- Servicio `ppi-dashboard`. Acceso vigente con **TLS + login + roles** (`admin`,
  `lector`) en `https://10.10.60.11:8788`, con regla `nftables` que solo admite el
  bastión como segunda capa. El **modo demo** (`--demo`) es distinto: sin login y con
  datos de ejemplo.
- **Solo lectura para todo rol:** no hay endpoints de escritura [C]. El rol `lector`
  recibe **403** en los endpoints de desarrollador.
- Versión desplegada en Sensor1 (2026-10-10) [S]: `dashboard.py` del commit
  `3ce0f01` de la rama `as-deployed-sensor-20261006`, **byte a byte** (SHA-256
  `d4a7358b01657c4d1020b3b4af71375abd77d48b79ff2190873ab40652b93582`); servicio `active` y
  respondiendo por HTTPS desde el bastión (401 sin login). Respaldo de la versión
  anterior: `dashboard.py.bak-20261010-002127`. **[V]** QA autenticada por rol con
  capturas fechadas.

## 9. Servicios y versión de heurísticos

- Sensor: `ppi-motor` (IF recalibrado), `ppi-dashboard`, captura,
  `ppi-publicar-feed.timer`. Bastión: `ppi-relay-feed.timer`. Host DMZ:
  `ppi-enforce-agent.timer`. `OnCalendar=minutely`, sin cron.
- **Versión de heurísticos:** `VERSION_UMBRALES = "2026-10-06.2"` (rama OR de
  `port_scan` y ratios de unicidad 0,45 por el espejo). Desde esta versión del
  repositorio, el publicador **etiqueta el feed con la versión del código**
  (`heuristicos.VERSION_UMBRALES`) y avisa si se le pasa otra por argumento, para que la
  traza no pueda divergir. **[V]** En Sensor1 la unidad del publicador aún pasa
  `--umbrales 2026-10-06.1`: la etiqueta de esos feeds es incorrecta aunque las reglas
  aplicadas sean las de `.2`; se corrige editando la unidad.

## 10. Resultados — siempre con modelo, dataset, denominador y escenario

- **FPR 4,45 %** = IF recalibrado sobre **test normal retenido** (65 421 ventanas). No es
  el FPR del sistema completo (modelo + heurísticos + enforcement), que se mide aparte.
- **92,4 % → 4,45 % no aísla el efecto de recalibrar.** El 92,4 % fue el OCSVM en los
  primeros minutos sobre la red real (92 decisiones en 7 ventanas, mayormente interfaces
  del cortafuegos emitiendo CARP) **antes** de excluir el plano de control y deduplicar
  el espejo; el 4,45 % es otro modelo, sobre otros datos (~70 h de línea base) y con ese
  filtrado aplicado. Para atribuir la mejora a la recalibración habría que puntuar ambos
  modelos sobre el mismo conjunto retenido.
- **Detección del IF:** 54/78 ventanas Kali (69 %); HTTP 27/27; escaneo 27/43; DNS 0/8
  (el ensayo apuntó a un host que no era el resolver: limitación del ensayo).
- **Stack híbrido por episodio** (3 familias × 3): modelo solo 6/9, heurísticos solos
  7/9, combinado 9/9. El 9/9 no es del modelo solo.
- **Históricos (OCSVM, otro modelo/dataset):** 88,3 % (158/179), 88,8 % (143/161), FPR
  F6 22,97–25,81 %, mediana de bloqueo 8,0 s (modalidad A).
- **Disponibilidad:** «cero caídas registradas en 58 corridas, 55 con verificación» es
  de **F6** (OCSVM, modalidad A). **No** demuestra la disponibilidad del despliegue
  vigente, que no se ha medido con ese protocolo.

## 11. Decisiones pendientes

- `configs/cyberflow.toml` es el **perfil genérico histórico** (OCSVM, `1,8126`,
  `calibrado_en_esta_red = false`); Sensor1 usa `configs/cyberflow.local.toml` (IF,
  calibrado). Decidir si se publica un perfil reproducible del despliegue real. **No
  regenerar systemd** en Sensor1 con el genérico.
- La descripción textual de la unidad `ppi-motor` todavía dice «OCSVM»; corregirla al
  planificar un despliegue.
