# Tarea prioritaria para Codex — cerrar brechas `fragment_ratio_10s` y `tls_handshake_failure_ratio_60s`

- **Fecha:** 2026-08-14
- **Autor:** Claude (rol: responsable técnico / coordinador metodológico)
- **Canal de coordinación:** no hay plugin/MCP de Codex conectado en esta sesión (`ListAgents` → "No reachable agents"). Este archivo es el canal oficial hasta que exista integración confirmada. No asumas que Codex ya vio esto: notifícalo por el medio habitual (mensaje directo / próxima sesión).
- **Estado del repo al momento de escribir esto:** `main` limpio, un commit local sin publicar (`3c51c25`, no hacer push sin autorización explícita del usuario). No lo incluyas en el push de esta tarea salvo que el usuario lo pida.

## Contexto (verificado, no repetir investigación)

Ya audité el código y la documentación existente (`docs/fase03-dataset/160-172`, `configs/features/multilayer-v2.json`, `scripts/features/extract_multilayer_v2.py`, `scripts/dataset/audit_multilayer_v2.py`, `scripts/modeling/train_multilayer_v2.py`, `tests/test_multilayer_v2_features.py`). Resumen de hechos confirmados, para que no los reinvestigues:

1. **No hay ningún bug en el extractor.** `fragment_ratio_10s` (`scripts/features/extract_multilayer_v2.py:230,595`) y `tls_handshake_failure_ratio_60s` (líneas 444,452,611-613) leen correctamente el header IP (`IP_FLAG_MF`/offset, líneas 109-110) y el campo `tls.version` de EVE. Están constantes en el dataset v2 (75 ventanas normales + 18 anómalas) porque **ningún escenario ejecutado hasta ahora genera tráfico que dispare esas condiciones** — no porque falte lógica. Esto ya está reconocido como brecha en `known_gaps` de `configs/campaigns/multilayer-v2-normal.json` y en el doc 171 (auditoría de calidad v2).
2. **Brecha de tests, además de la de datos.** `tests/test_multilayer_v2_features.py:197-220` solo cubre el caso trivial (`==0.0`) de ambas features. Ningún test ejercita la rama `fragmented=True` (línea 230) ni `tls_incomplete=True` (línea 452).
3. **Precedente ya resuelto para una brecha hermana:** `http_status_5xx_ratio_60s` se validó en `CAL-G7-API-5XX-R02` (doc 172): perfil de calibración único, `purpose=calibration`, `partition=excluded_calibration`, evidencia completa (PCAP+EVE+hashes), **sin incorporarse retroactivamente** al dataset ya congelado. Usa el mismo patrón operativo para las dos tareas de este documento.
4. **Dataset normal v2 está congelado:** 50 episodios / 75 ventanas (train 44, validation 15, test 16) + 12 episodios / 18 ventanas anómalas en `evaluation_only`. **Ninguna acción de este documento debe tocar, reescribir o volver a ejecutar esos episodios.**
5. `scripts/f1/run-benign.sh` es el generador compartido (usado tanto por el dataset F1 v1 como por multilayer-v2). Actualmente NO tiene ningún escenario que fuerce fragmentación IP ni fallo de handshake TLS — hay que añadir dos casos nuevos sin tocar los existentes.
6. `scripts/dataset/audit_multilayer_v2.py:20-24` no valida que el campo `partition` de cada fila esté dentro del conjunto permitido (`train`/`validation`/`test`/`evaluation_only`/`excluded_calibration`); solo detecta episodios repartidos entre valores distintos. Es una brecha de robustez barata de cerrar.

## Restricciones explícitas para esta tarea (no negociables)

- No modificar `artifacts/dataset/multilayer-v2-normal.csv` ni `multilayer-v2-anomalies.csv` ya congelados.
- No añadir los escenarios nuevos a `configs/campaigns/multilayer-v2-normal.json` todavía. Primero se calibran; la decisión de formalizarlos como perfiles oficiales (posible v2.1) es mía, después de revisar la evidencia de calibración.
- No mezclar la evidencia de calibración con `train`/`validation`/`test`. Usa `purpose=calibration` / `partition=excluded_calibration`, igual que `CAL-G7-API-5XX-R02`.
- No re-ejecutar ni tocar ningún episodio de las repeticiones R01-R05 ya cerradas.
- Si el primer intento de calibración TLS no produce la señal esperada (ver Tarea 4), **detente después de un intento, documenta el EVE crudo obtenido y repórtalo** en vez de iterar variantes por tu cuenta sin revisión.

---

## Tarea 1 — Tests unitarios positivos para ambas features (sin VM, sin riesgo)

**Objetivo:** cerrar la brecha de cobertura de tests para `fragment_ratio_10s` y `tls_handshake_failure_ratio_60s`, probando el caso donde el valor SÍ debe ser distinto de cero.

**Motivo:** actualmente ningún test demuestra que la lógica de detección (no solo la fórmula del ratio) funciona correctamente cuando el evento positivo ocurre. Es una brecha de correctitud de código independiente de la brecha de datos, y se puede cerrar sin acceso al laboratorio.

**Archivos a modificar:**
- `tests/test_multilayer_v2_features.py`

**Cambios exactos:**
1. Añade un caso de prueba que construya (sintéticamente, sin capturar tráfico real) un paquete IPv4 con el bit `MF` activo o `fragment offset > 0` dentro de la ventana de 10s, y verifica que `fragment_ratio_10s > 0` y su valor exacto (`fragmentados / total_paquetes_ventana`).
2. Añade un caso de prueba que construya un evento EVE sintético `{"event_type": "tls", "tls": {}}` (sin campo `version`) dentro de la ventana de 60s, junto con al menos un evento TLS completo (con `version`), y verifica que `tls_handshake_failure_ratio_60s` refleje exactamente la proporción esperada (no 0.0 y no 1.0, para distinguir del caso trivial).
3. No cambies la lógica de `extract_multilayer_v2.py` — este task es solo de tests. Si al escribir el test descubres que SÍ hay un bug (por ejemplo, que la ventana de agregación no incluye correctamente el evento), repórtalo como hallazgo aparte antes de "arreglarlo" — no toques el extractor sin decisión mía.

**Comandos exactos:**
```bash
cd /home/m4rk/Documentos/pronteacomopepa/vf-sistema-final
python3 -m pytest tests/test_multilayer_v2_features.py -v
```
(Si `pytest` no está disponible en el entorno de esta VM, instálalo en el `.venv` del proyecto, no globalmente, y documenta el comando usado.)

**Criterios de aceptación:**
- Los dos nuevos casos de test pasan.
- Los tests existentes (incluyendo los que verifican el caso `==0.0`) siguen pasando sin modificación.
- El extractor real (`extract_multilayer_v2.py`) no cambia de línea salvo que reportes y yo autorice un fix.

**Evidencia esperada:** salida completa de `pytest -v` (pegada o adjunta), diff del archivo de test.

**Riesgos:** ninguno — no toca VMs ni datos de producción.

**Permisos requeridos:** ninguno.

**VM involucrada:** ninguna (ejecutar en VM01, entorno local).

---

## Tarea 2 — Endurecer el auditor: validar valores permitidos de `partition` (sin VM, sin riesgo)

**Objetivo:** que `audit_multilayer_v2.py` falle explícitamente si aparece un valor de `partition` fuera del conjunto permitido.

**Motivo:** hoy el auditor solo detecta episodios repartidos entre *distintos* valores de partición (línea 20-21), pero no valida que esos valores pertenezcan al conjunto cerrado `{train, validation, test, evaluation_only, excluded_calibration}`. Un error de tipeo o una fila de calibración mal etiquetada pasaría desapercibido. Esto es relevante ahora porque las Tareas 3 y 4 van a generar filas nuevas con `partition=excluded_calibration` y quiero un gate automático que impida que esas filas terminen alguna vez en `train`/`validation`/`test` por error humano.

**Archivos a modificar:**
- `scripts/dataset/audit_multilayer_v2.py`

**Cambios exactos:**
- Añade una constante `VALID_PARTITIONS = {'train','validation','test','evaluation_only','excluded_calibration'}`.
- Añade un nuevo gate `partition_values_valid` que verifique `set(r['partition'] for r in allrows) <= VALID_PARTITIONS`, incluido en el diccionario `gates` (línea 23) y en el cálculo de `gates['pass']` (línea 24).
- Si detectas valores fuera del conjunto, el reporte debe listarlos explícitamente (nuevo campo `invalid_partition_values`), no solo fallar el booleano.

**Comandos exactos:**
```bash
python3 scripts/dataset/audit_multilayer_v2.py \
  --normal artifacts/dataset/multilayer-v2-normal.csv \
  --anomalies artifacts/dataset/multilayer-v2-anomalies.csv \
  --output /tmp/audit-check.json
cat /tmp/audit-check.json | python3 -m json.tool | grep -A3 partition
```

**Criterios de aceptación:**
- Ejecutado contra el dataset actual (congelado), `partition_values_valid` debe dar `true` y `gates.pass` no debe cambiar de valor respecto a la última auditoría publicada (171).
- Si escribes un test unitario para el auditor con un CSV sintético que incluya un valor inválido (p. ej. `"calibration"` sin `excluded_`), debe fallar correctamente.

**Evidencia esperada:** JSON de auditoría antes/después del cambio (mismo dataset, mismo resultado en los gates preexistentes), y el test sintético si lo agregas.

**Riesgos:** ninguno — es una validación adicional, no cambia datos.

**Permisos requeridos:** ninguno.

**VM involucrada:** ninguna.

---

## Tarea 3 — Calibración de fragmentación IP real (`CAL-FRAG-UDP-01`)

**Objetivo:** demostrar con una captura real que `fragment_ratio_10s` puede tomar un valor distinto de 0.0 cuando existe tráfico IP genuinamente fragmentado, usando el mismo pipeline de extracción que el dataset oficial.

**Motivo:** la MTU del laboratorio es 1500 en todos los segmentos y ningún escenario existente envía payloads UDP mayores a eso, por lo que el valor es estructuralmente 0.0 en today's dataset. Un datagrama UDP con payload > 1472 bytes (1500 − 20 IP − 8 UDP) fuerza al kernel a fragmentar en el origen (VM05), salvo que el socket tenga `IP_PMTUDISC_DO`; `iperf3` no lo fija por defecto, así que debería fragmentar de forma nativa.

**Archivos a modificar:**
- `scripts/f1/run-benign.sh` — añadir un nuevo caso `frag-udp` al `case "$scenario" in ... esac` (líneas 29-239), siguiendo exactamente el mismo estilo de validación por lista blanca que los demás casos (ver `iperf-udp`, líneas 212-218, como plantilla más cercana).

**Especificación exacta del nuevo caso:**
```bash
frag-udp)
  length="${1:-}"
  duration="${2:-}"
  case "$length" in 2000|3000) ;; *) echo "ERROR: longitud UDP permitida: 2000 o 3000 bytes" >&2; exit 2;; esac
  require_duration "$duration"
  iperf3 -c "$TARGET_IP" -u -b 5M -l "$length" -t "$duration" -J
  ;;
```
- Actualiza el mensaje de `usage()` (línea 11) para incluir `frag-udp`.
- No modifiques ningún caso existente.

**Ejecución (calibración única, NO oficial):**
1. Confirma que el servidor `iperf3` sigue escuchando en VM03 (10.30.0.10) — es el mismo que usan `iperf-tcp`/`iperf-udp`, no requiere despliegue nuevo.
2. Reutiliza exactamente el mecanismo de captura/evidencia que documentaste para `CAL-G7-API-5XX-R02` en `docs/fase03-dataset/172-brecha-api-5xx-y-permisos.md` (preflight, PCAP+EVE del Sensor con hash, ledger con `purpose=calibration`, `partition=excluded_calibration`, ID `CAL-FRAG-UDP-01-R01`).
3. Ejecuta **una sola vez**: `./run-benign.sh frag-udp 3000 10` desde VM05 hacia 10.30.0.10.
4. Pasa el PCAP/EVE resultante por `scripts/features/extract_multilayer_v2.py` igual que cualquier otro perfil, y confirma en el CSV/JSON de salida que al menos una ventana de 10s tiene `fragment_ratio_10s > 0`.

**Criterios de aceptación:**
- Cero drops de Suricata/tcpdump (mismo estándar que todas las campañas previas).
- Al menos una ventana con `fragment_ratio_10s > 0`, con el valor exacto documentado.
- Evidencia con `purpose=calibration` y `partition=excluded_calibration`, hashes SHA-256 de PCAP/EVE/CSV.
- El dataset congelado (`multilayer-v2-normal.csv`/`-anomalies.csv`) permanece con el mismo hash que antes de esta tarea — verifícalo explícitamente con `sha256sum` antes y después.

**Evidencia esperada:** documento nuevo en `docs/fase03-dataset/` (siguiente número correlativo tras 172) siguiendo el mismo formato que los cierres de canario anteriores; ledger/manifest de la calibración; salida de `extract_multilayer_v2.py` mostrando el valor no-cero.

**Riesgos:** tráfico UDP a 5 Mbit/s durante 10s (~6.25 MB) — muy por debajo del techo calibrado de 50 Mbit/s UDP (G2). Riesgo de red: ninguno nuevo. Riesgo de captura: ninguno distinto a las campañas ya ejecutadas cientos de veces con este mismo generador.

**Permisos requeridos:** ninguno nuevo — mismo usuario `useransible` sin sudo, mismos servicios ya corriendo. Si algo exige sudo, detente y repórtalo en vez de solicitarlo tú mismo.

**VM involucrada:** VM05 (Cliente, origen), VM03 (Servidor, destino, servicio `iperf3` ya activo), VM02 (Sensor, captura).

---

## Tarea 4 — Calibración de fallo de handshake TLS (`CAL-TLS-HANDSHAKE-FAIL-01`)

**Objetivo:** demostrar con una captura real que `tls_handshake_failure_ratio_60s` puede tomar un valor distinto de 0.0 cuando Suricata registra un evento `tls` sin campo `version` resuelto.

**Motivo:** el único escenario TLS existente (`https-sessions`) siempre completa el handshake con éxito. Se necesita una negociación TLS que llegue a la red (para que Suricata la vea) pero que el servidor rechace antes de completar `ServerHello`/certificado — por ejemplo, forzando una versión de protocolo obsoleta que nginx ya no ofrezca. **Esto es una hipótesis a validar, no un hecho confirmado**: no sé con certeza qué versiones de TLS tiene habilitadas/deshabilitadas el nginx de VM03 ni si Suricata emite el evento `tls` en este caso concreto — por eso es calibración, no ejecución directa a dataset.

**Archivos a modificar:**
- `scripts/f1/run-benign.sh` — añadir un nuevo caso `tls-handshake-fail`.

**Especificación exacta del nuevo caso:**
```bash
tls-handshake-fail)
  protocol="${1:-}"
  count="${2:-}"
  case "$protocol" in tls1|tls1_1) ;; *) echo "ERROR: protocolo permitido: tls1 o tls1_1" >&2; exit 2;; esac
  case "$count" in 1|3) ;; *) echo "ERROR: conteo permitido: 1 o 3" >&2; exit 2;; esac
  for ((i=1; i<=count; i++)); do
    if openssl s_client -connect "$TARGET_IP:443" "-$protocol" -brief < /dev/null > /tmp/tls-fail-$i.log 2>&1; then
      echo "ERROR: la conexión $protocol tuvo éxito; se esperaba rechazo" >&2
      exit 1
    fi
    printf '{"scenario":"tls-handshake-fail","attempt":%d,"protocol":"%s"}\n' "$i" "$protocol"
    sleep 0.5
  done
  ;;
```
- Actualiza `usage()`.
- **Antes de correr la calibración oficial**, primero verifica manualmente (sin capturar campaña, solo un `openssl s_client -connect 10.30.0.10:443 -tls1 -brief` suelto) qué versiones TLS acepta/rechaza el nginx real. Si nginx SÍ acepta `tls1`/`tls1_1` (posible si no se endureció explícitamente), esta técnica no producirá el fallo esperado — en ese caso detente, documenta la configuración TLS real de nginx (`nginx -T` o el config versionado en `configs/server/`), y repórtame el resultado en vez de probar otra técnica por tu cuenta.

**Ejecución (calibración única, NO oficial):**
1. Verificación manual previa (paso anterior) — documenta el resultado exacto.
2. Si el rechazo se confirma, reutiliza el mismo mecanismo operativo de `CAL-G7-API-5XX-R02` (preflight, PCAP+EVE con hash, `purpose=calibration`, `partition=excluded_calibration`, ID `CAL-TLS-HANDSHAKE-FAIL-01-R01`).
3. Ejecuta **una sola vez**: `./run-benign.sh tls-handshake-fail tls1 3` desde VM05.
4. Extrae features y confirma si el evento `tls` de Suricata realmente carece de `version`. Si Suricata no emite ningún evento `tls` para un handshake que falla tan temprano (posible, según el docstring del extractor líneas 25-28), documenta el EVE crudo obtenido y repórtalo — puede que se necesite una técnica distinta (p. ej. cipher suite incompatible en vez de versión de protocolo) que yo diseñaré con esa evidencia.

**Criterios de aceptación:**
- Cero drops de Suricata/tcpdump.
- O bien (a) al menos una ventana con `tls_handshake_failure_ratio_60s > 0` con evidencia del evento EVE exacto, o (b) si no se logra, un reporte claro de qué ocurrió realmente en EVE (para rediseñar la técnica), sin inventar ni forzar el resultado.
- El dataset congelado permanece con el mismo hash que antes de esta tarea.

**Evidencia esperada:** documento nuevo en `docs/fase03-dataset/`; salida cruda de `openssl s_client`; fragmento del evento `tls` en EVE (JSON); resultado de `extract_multilayer_v2.py`.

**Riesgos:** ninguno operativo — es tráfico de diagnóstico TLS estándar, no ofensivo, tres intentos de handshake fallido en ~2 segundos totales. Riesgo real es solo de **resultado incierto** (que la hipótesis no se confirme), lo cual es aceptable y esperado en una calibración.

**Permisos requeridos:** ninguno nuevo. Si `nginx -T` requiere sudo que ya no tienes (fue retirado tras el despliegue de la API), usa en su lugar el archivo versionado `configs/server/nginx-ppi.conf` y repórtalo como limitación de evidencia, no como bloqueo.

**VM involucrada:** VM05 (Cliente, origen), VM03 (Servidor, destino, nginx TLS ya activo), VM02 (Sensor, captura).

---

## Tarea 5 — Investigar por qué el pipeline de modelado no aprovecha la separación univariante existente (sin tocar el dataset)

**Objetivo:** explicar la brecha entre la separación univariante fuerte que ya existe en 18 de las 28 features oficiales y el AUC multivariante bajo del modelo (0.6007 por ventana, 0/12 por episodio), antes de asumir que la causa es "falta de datos".

**Motivo:** hice un análisis rápido, no destructivo (solo lectura de `artifacts/dataset/multilayer-v2-normal.csv` y `-anomalies.csv`, sin tocar nada), restringido a las 28 features del esquema oficial (`configs/features/multilayer-v2.json`). Resultado (Cohen's d aproximado con medias/desviación pooled entre normal y anomalía, sin ajustar por correlación entre features):

- **3/28 constantes en ambas clases** (ya cubiertas en Tareas 3-4): `fragment_ratio_10s`, `tls_handshake_failure_ratio_60s`, `http_status_5xx_ratio_60s`.
- **18/28 con separación univariante notable (d>0.5)**, varias muy fuertes: `large_ip_ratio_10s` d=1.60, `mean_ip_len_10s` d=1.57, `flow_duration_mean_30s` d=1.36, `dns_nxdomain_ratio_60s` d=1.32, `byte_rate_10s` d=1.23, `packet_rate_10s` d=1.21, `flow_attempt_rate_10s` d=1.19, `dns_query_rate_60s` d=1.17, `unique_dns_name_ratio_60s` d=0.94, `http_request_rate_60s` d=0.74, `http_auth_failure_ratio_60s` d=0.70, `tls_version_ratio_60s` d=0.69, `rst_ratio_10s` d=0.68, `syn_rate_10s` d=0.68, `tls_session_rate_60s` d=0.66, `icmp_ratio_10s` d=0.64, `unique_dst_ip_ratio_30s` d=0.56, `http_method_entropy_60s` d=0.53.
- **7/28 con separación débil (d<0.5):** `http_error_ratio_60s`, `ttl_mean_10s`, `protocol_diversity_30s`, `tcp_retransmission_ratio_10s`, `unique_dst_port_ratio_30s`, `syn_completion_ratio_10s`, `tx_rx_byte_ratio_30s`.

Con esta cantidad de señal univariante, un AUC multivariante de apenas 0.6007 es sospechoso. No sé todavía si la causa es del **pipeline** (escalado ausente, hiperparámetros de Isolation Forest, redundancia/correlación entre las 18 features separables) o si es genuinamente un techo por **composición de la muestra** (18 ventanas anómalas de solo 3 familias tipo flood, correlacionadas dentro de episodio). Esta tarea es para acotarlo con evidencia — no para "arreglar" el modelo oficial todavía.

**Archivos a revisar (diagnóstico, no reemplazar nada oficial):**
- `scripts/modeling/train_multilayer_v2.py` (`episode_mean()`, ajuste de `IsolationForest(n_estimators=500, contamination='auto', max_features=1.0, random_state=20260813)`, umbral por percentil de `validation`).
- `artifacts/dataset/multilayer-v2-normal.csv`, `multilayer-v2-anomalies.csv`, `multilayer-v2-model-report-expanded.json`.

**Análisis exactos a realizar (todos de solo lectura/diagnóstico):**

1. **Escalado.** Confirma si `train_multilayer_v2.py` aplica `StandardScaler`/equivalente antes de `IsolationForest.fit()`. Si no lo hace, en un script *experimental aparte* prueba si escalar las 28 features cambia el AUC. Reporta la cifra exacta, no la estimes.
2. **`max_samples`.** Con solo 44 filas de train, revisa qué valor efectivo toma `max_samples` (por defecto `min(256, n_samples)` en sklearn → 44 aquí, es decir cada árbol ve casi siempre las mismas 44 filas, reduciendo la diversidad entre los 500 árboles). Prueba con un `max_samples` explícito menor (p. ej. 32) en el mismo script experimental y reporta el efecto.
3. **Redundancia entre features.** Calcula la matriz de correlación (Pearson) entre las 18 features con separación univariante notable, sobre `train`+`validation` únicamente (nunca sobre `test`). Si varias están altamente correlacionadas (p. ej. `packet_rate_10s`/`byte_rate_10s`/conteos derivados todos del mismo volumen de tráfico), documenta cuántas dimensiones *independientes* de señal existen realmente — puede que "18 features separables" sean en la práctica 4-5 señales independientes.
4. **Selección/reducción de features (solo diagnóstico).** En el script experimental, entrena variantes de Isolation Forest usando únicamente las top-N features por separación univariante (N=5, 10, 15) y compara AUC/AP contra el modelo de 28 features. Esto es solo diagnóstico — no se declara como nuevo modelo oficial.
5. **Reconfirmar la dilución por episodio.** Cuantifica cuántas de las 18 ventanas anómalas quedan "diluidas" cuando `episode_mean()` las promedia con ventanas de cola/calma del mismo episodio (fork previo ya confirmó que la agregación por episodio da peor resultado — 0/12 vs 7/18 por ventana; esta tarea es cuantificar el mecanismo, no repetir la comprobación de que existe).

**Comandos exactos:**
```bash
cd /home/m4rk/Documentos/pronteacomopepa/vf-sistema-final
# Crea un script experimental NUEVO, no toques train_multilayer_v2.py:
# scripts/modeling/experiments/diagnose_v2_pipeline.py
python3 scripts/modeling/experiments/diagnose_v2_pipeline.py \
  --normal artifacts/dataset/multilayer-v2-normal.csv \
  --anomalies artifacts/dataset/multilayer-v2-anomalies.csv \
  --schema configs/features/multilayer-v2.json \
  --output artifacts/dataset/multilayer-v2-pipeline-diagnosis.json
```

**Criterios de aceptación:**
- El modelo oficial congelado (`train_multilayer_v2.py` y `multilayer-v2-model-report-expanded.json`) no se modifica ni se sobrescribe.
- El script experimental es nuevo, vive en `scripts/modeling/experiments/`, y está marcado explícitamente como diagnóstico, no como candidato a producción.
- El reporte de salida incluye, con cifras exactas: efecto del escalado, efecto de `max_samples`, matriz/resumen de correlación entre las 18 features separables, efecto de selección top-N, y cuantificación de la dilución por episodio.
- No se declara "modelo mejorado" ni se cambia ningún umbral oficial — la decisión de adoptar cualquier cambio al pipeline oficial es mía, después de revisar esta evidencia.

**Evidencia esperada:** `artifacts/dataset/multilayer-v2-pipeline-diagnosis.json` + un documento nuevo en `docs/fase04-modelado/` resumiendo los 5 hallazgos con cifras exactas.

**Riesgos:** ninguno — análisis puramente computacional sobre datos ya congelados, sin tocar VMs ni generar tráfico.

**Permisos requeridos:** ninguno.

**VM involucrada:** ninguna (VM01, entorno local).

---

## Orden sugerido

1. Tarea 1 (tests) → 2. Tarea 2 (auditor) → 3. Tarea 5 (diagnóstico del pipeline, sin VM, informa si vale la pena seguir) → 4. Tarea 3 (calibración fragmentación) → 5. Tarea 4 (calibración TLS, mayor incertidumbre).

Adelanté la Tarea 5 antes que las calibraciones de laboratorio (3 y 4) a propósito: si el diagnóstico muestra que el techo de AUC es sobre todo culpa del pipeline (escalado/`max_samples`/redundancia) y no de features faltantes, puede cambiar la prioridad relativa de correr calibraciones de laboratorio vs. ajustar el modelo. Aun así, ejecuta 3 y 4 salvo que yo indique lo contrario — cerrar las features constantes es necesario de cualquier forma.

Las Tareas 1, 2 y 5 no requieren autorización adicional del usuario (son seguras, reversibles, documentales, sin VM). Las Tareas 3 y 4 tampoco deberían requerirla si no aparece ninguna necesidad de sudo/cambio de red — pero si `preflight_profile.sh` u otro gate exige algo que no tienes, detente y repórtalo en vez de improvisar.

## Qué necesito de vuelta al cerrar el ciclo

Para cada tarea: qué verificaste, qué evidencia adjuntaste (ruta exacta), y si algún criterio de aceptación no se cumplió. Yo reviso, decido si se acepta, y preparo la siguiente tarea (probablemente: diseño formal de perfiles v2.1 `FRAG-UDP-V2`/`TLS-HANDSHAKE-FAIL-V2` para incorporarlos a `multilayer-v2-normal.json` si la calibración es exitosa, y/o ajustes al pipeline oficial de modelado si el diagnóstico de la Tarea 5 los justifica).
