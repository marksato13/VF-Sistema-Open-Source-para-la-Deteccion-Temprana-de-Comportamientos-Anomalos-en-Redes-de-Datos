# Ficha técnica única — despliegue vigente de CyberFlow

**Propósito.** Fuente de verdad **única** del sistema tal como está desplegado hoy.
Toda la documentación (README, instalación, configuración, replicación, cards,
diagramas, resultados) debe alinearse a esta ficha, no al revés. No describe un
objetivo ni un plan: describe lo que **corre**.

**Corte:** 2026-10-09. **No modifica** artefactos, umbrales ni servicios.

## Cómo leer el estado de cada dato

- **[S]** verificado en Sensor1 por SSH (reconciliación 2026-10-09).
- **[C]** verificado en el código de este repositorio.
- **[V]** pendiente de comprobación en vivo por Mark (hash, arranque, servicio).

Fuentes base: `docs/RECONCILIACION-MANIFIESTO-MOTOR.md`,
`docs/dataset/MODEL_CARD_IF_RECALIBRADO.md`, evidencia L/M de orquestación.

---

## 1. Modalidad de despliegue (hay DOS; no confundirlas)

| Modalidad | Qué es | Dónde se usó | Estado |
|---|---|---|---|
| **A — Sensor en línea, bloqueo local** | El sensor enruta (`ip_forward`) y aplica `nftables` localmente. Bloqueo de laboratorio. | Banco F6 (resultados históricos: 8 s mediana, 120 s de bloqueo) | **Histórico / laboratorio evaluado** |
| **B — Sensor por SPAN, enforcement distribuido** | El sensor **observa por espejo (SPAN), sin IP, no bloquea tráfico copiado**. Decide y publica un **feed firmado**; un **agente en el host protegido** aplica `nftables`. | Despliegue vigente en Sensor1 | **VIGENTE** [S] |

> Precisión obligatoria (puntos 1 y 4): en la modalidad B el sensor **no bloquea
> directamente** el tráfico espejado; **emite decisiones que aplica el host**. La
> cadena completa es: **captura SPAN → motor → publicador → feed firmado → relay →
> agente → nftables**, con alerta a Wazuh. El diagrama antiguo `sensor → nftables`
> describe la modalidad A y debe rotularse como laboratorio.

## 2. Modelo activo [S]

| Propiedad | Valor |
|---|---|
| Identificador | `if_recalibrado_2026_09` |
| Tipo | `Pipeline` (escalador + Isolation Forest); puntúa con `score_samples` |
| Artefacto | `artifacts/preliminar/if_recalibrado_desplegable.joblib` |
| SHA-256 (vivo) | `d27f68711fcb0f6657611bd7feb17759bc4fae36b9e61fbd5ca8d1190128125a` [S] |
| Manifiesto | `artifacts/preliminar/manifest-if-recalibrado.json` (el que usa el motor) |
| Umbral | `score_samples < −0,568892` **=** `decision_function < −0,068892` (offset −0,5) |
| Calibración | `alpha=0,05` en validation (umbral NO elegido sobre test); `calibrado_en_esta_red=true` |

**Tres modelos distintos — no mezclar (puntos 7, 8, 9):**
- **Publicado/histórico:** OCSVM (`ocsvm_scaled`), umbral `1,8126`, FPR 4,71 % — ficha `MODEL_CARD_OCSVM.md`. Promovido tras ver el test (sesgo de selección declarado).
- **Declarado principal en el experimento v2:** `if_primary_weighted` (manifiesto de laboratorio).
- **Activo hoy:** `if_recalibrado_2026_09` (esta ficha). **Cada umbral va con su modelo, conjunto, fecha y función de score; nunca se intercambian.**

**Promoción al motor (punto 10):** `entrenar_preliminar.py` reporta
`decision_function`; el motor puntúa con `score_samples`. Ambas escalas difieren en el
offset fijo −0,5 de sklearn; el desplegable ya lleva el umbral en la escala
`score_samples` (−0,568892). **Verificar en vivo** que el modelo promovido transforma
correctamente modelo+umbral a la función del motor [V]; la diferencia de escala por sí
sola no es un fallo.

## 3. Contrato de variables (puntos 11 y 12) [C]

| Esquema | Nº | Qué es | Relación con el modelo |
|---|---|---|---|
| `multilayer-v2.json` | **28** | Contrato **del modelo** (L3/L4/L7) | El IF recalibrado **consume estas 28** |
| `multilayer-v3.json` | **31** | Esquema del **extractor** (v2 + 3 de capa 2/enlace) | El extractor emite 31; **el modelo NO usa las 3 de L2** |

- **Observables:** 27 de las 28; `tls_handshake_failure_ratio_60s` no tiene
  observabilidad efectiva (constante estructural). L2 queda **fuera del scoring**.
- El motor revisado **exige el contrato v2 (28)** para el modelo, aunque usa
  **funciones del extractor v3** para el tratamiento de la entrada.
- ⚠️ **Inconsistencia a corregir:** la GUI (arista `variables → modelo`) y la ficha
  de artefactos dicen «31 variables»; el modelo recibe **28**. Debe decir «31 extraídas
  / 28 al modelo» o «28 (v2)». Afecta también a los diagramas Mermaid derivados.

## 4. Pipeline de datos (punto 13) [C]

El motor **no reparsea todo el anillo** en cada ciclo: mantiene un **buffer
incremental**. PCAP en anillo por tiempo (~240 s, ampliado desde ~120 s); de EVE
mantiene en memoria las líneas de los últimos `--history-seconds` y las vuelca por
ciclo sin tocar la lógica del extractor. Los atrasos históricos (p. ej. atribución de
flujos > ~240 s) son **resultados de la versión anterior**; la versión actual debe
medirse de nuevo.

## 5. Respuesta: niveles y condiciones (puntos 2 y 21) [C]

Tres acciones (no «sin nivel intermedio»): **PERMIT · LIMIT · BLOCK**.

| Señal | Acción | Motivo |
|---|---|---|
| Sin veredicto / score ≥ umbral | **PERMIT** | tráfico normal (no genera entrada en el feed) |
| ALERT del **modelo** (score < umbral) | **LIMIT** | anomalía sin confirmar → degradar (reversible) |
| ALERT de **heurístico** (`brute_force`, `port_scan`, `http_abuse`, `dns_entropy`) | **BLOCK** | confirmado por regla determinista |

Por IP gana **la acción más severa** del lote (`BLOCK > LIMIT`). Estado de madurez
de la respuesta (mantener separado):
- **BLOCK en banco** (F6): probado.
- **LIMIT automático en vivo:** probado (2026-10-06).
- **BLOCK automático desde detección de punta a punta:** **pendiente** según PENDIENTES.

## 6. Escalera de caducidad (punto 3) [C] — `escalada.py`

Nunca `∞` automático. Decaimiento del contador a las **24 h** sin reincidir.

| Evento | Caducidad |
|---|---|
| LIMIT | **300 s** (plano, no escala, reversible) |
| BLOCK 1º | **300 s** |
| BLOCK 2º (dentro de ventana) | **1800 s** |
| BLOCK 3º+ | **3600 s** (tope automático) + marca de **revisión humana** |

El `--ventana-segundos` del publicador (120 s por defecto) es la **ventana de
decisiones recientes** que se leen, **no** el tiempo de bloqueo. El «bloqueo de 120 s»
de docs viejos es de la modalidad A (laboratorio), no de esta escalera.

## 7. Infraestructura protegida (punto 26) [C]

`publicar_feed.py` y el agente comparten una lista **nunca-bloquear**: bastión
`10.10.10.30`, sensor `10.10.60.11`, gateways VLAN (`.1`), DNS/AD `10.10.10.20`.
⚠️ **Están hardcodeadas** en ambos componentes → deben moverse a **configuración por
despliegue** y comprobarse que publicador y agente aplican la misma política.

## 8. Panel (punto 5)

- Servicio `ppi-dashboard.service`. Acceso vigente con **TLS + login + roles**
  (`admin`, `lector`); `https://10.10.60.11:8788`. El **modo demo** (`--demo`, sin
  login, datos de ejemplo) es distinto del despliegue [V: confirmar en vivo].
- **Solo lectura para todo rol:** no existen endpoints de escritura en el código [C];
  el panel no bloquea ni desbloquea. El rol `lector` recibe **403** en los endpoints de
  desarrollador; el `admin` ve además Topología/Variables/Alcance/Modelo [C, test
  `test_dashboard_gui_contract.py`].

## 9. Servicios y timers (punto 27) [S parcial / V]

- Sensor: `ppi-motor.service` (IF recalibrado), `ppi-dashboard.service`,
  captura, `ppi-publicar-feed.timer`.
- Bastión: `ppi-relay-feed.timer`. Host DMZ: `ppi-enforce-agent.timer`.
  `OnCalendar=minutely` (sin cron). **Versión de heurísticos efectiva:**
  `VERSION_UMBRALES=2026-10-06.2` (código, autoritativo); la etiqueta `--umbrales
  2026-10-06.1` del publicador es solo traza del feed (cosmética, se fija en la unidad
  del sensor) → corregir a `.2` [V].

## 10. Resultados — siempre con modelo, dataset, denominador y escenario

Detalle y límites en `MODEL_CARD_IF_RECALIBRADO.md`. Resumen (no intercambiar):
- **FPR 4,45 %** = IF recalibrado sobre **test normal retenido** (65 421 ventanas). **No**
  es el FPR operativo del sistema con heurísticos+enforcement (medir aparte). **No**
  borra el F6 histórico **22,97–25,81 %** (otro modelo/escenario).
- **69 % global = 54/78** ventanas Kali; **HTTP 27/27**; **escaneo 27/43**; **DNS 0/8**
  (el piloto apuntó a un host que no era el resolver → limitación del ensayo, verificar
  en PCAP/EVE antes de concluir fallo del modelo).
- **9/9** = **stack híbrido por episodio** (3 familias × 3); modelo solo 6/9,
  heurísticos solos 7/9. **No** atribuir 9/9 al IF.
- **88,3 % / 88,8 %** = OCSVM histórico (158/179 y 143/161), **otro modelo/dataset**.
- **Disponibilidad:** «cero caídas en 58 corridas; 55 con verificación explícita»
  (no «disponibilidad verificada siempre»).

## 11. Deriva pendiente de decisión de Mark

- `configs/cyberflow.toml` genérico apunta a OCSVM/1,8126/calibrado=false; Sensor1 usa
  `cyberflow.local.toml` (IF, calibrado=true). Decidir: plantilla histórica vs perfil
  reproducible del despliegue real. **No regenerar systemd** con el genérico.
- Corregir descriptor de `ppi-motor` (texto «OCSVM») al planificar un despliegue, no en
  caliente para una demo.
