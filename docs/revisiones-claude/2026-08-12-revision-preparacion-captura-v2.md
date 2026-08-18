# Revisión adversarial: preparación de captura multicapa v2

Fecha: 2026-08-12. Alcance: `configs/server/ppi-api.py`, `ppi-api.service`,
`nginx-ppi.conf`, `ansible/playbooks/03-configurar-servicios-servidor.yml`,
`scripts/features/extract_multilayer_v2.py`, `configs/features/multilayer-v2.json`,
`configs/campaigns/multilayer-v2-normal.json` y
`configs/campaigns/multilayer-v2-anomalies.json`. Sin despliegue de VMs, sin
captura real, sin acceso a Internet.

**Nota de coordinación**: a mitad de esta revisión, `git log` mostró un commit
nuevo (`957a96e docs: registrar despliegue y pilotos v2`) que Codex publicó en
paralelo, registrando que la API ya fue desplegada en VM03 y que los pilotos
`api-normal`, `api-auth-fail` y `dns-multi 10` ya se ejecutaron contra el
código **previo** a las correcciones F2, F5 y F6 de este documento. Ese
commit sólo tocó `docs/fase03-dataset/163-ejecucion-v2-y-bloqueos.md`, no
los archivos de código revisados aquí, así que no hubo conflicto de edición.
Pero las correcciones de este documento (endpoint `/api/error`, rotación de
seis casos en `api-normal`, fin del cuerpo en 204, los cuatro perfiles nuevos
de la matriz) **no están reflejadas en el despliegue ya registrado**: hace
falta volver a ejecutar el playbook del servidor (y publicar la copia nueva de
`run-benign.sh` en VM05) antes de que cualquier piloto o campaña oficial las
ejercite. Esta revisión no modificó ni sobrescribió el commit de Codex.

## Hallazgo 1 — `tls_session_rate_60s` atribuida a un perfil sin tráfico TLS

- **Severidad**: alta.
- **Hecho observado**: `configs/campaigns/multilayer-v2-normal.json` (antes de
  esta revisión) declaraba `tls_session_rate_60s` en `feature_coverage` de
  `MIXED-V2` (escenario `mixed-light`). `scripts/f1/run-benign.sh` muestra que
  `mixed-light` sólo invoca `http`, `iperf-tcp` y `dns-valid`; ninguno abre una
  sesión TLS. `HTTPS-SESSIONS-V2` (que sí ejecuta `https-sessions`, veinte
  sesiones HTTPS reales) no declaraba esa feature.
- **Inferencias**: la reclamación de cobertura era falsa. `validate_matrix.py`
  sólo comprueba que el nombre exista en el esquema, no que el escenario
  produzca la señal, así que aceptó la matriz sin poder refutarla.
- **Riesgo**: al construirse el dataset v2, cualquier fila "cubierta" por
  `MIXED-V2` para esta feature tendría valor estructuralmente 0.0, sin
  variabilidad real; presentar eso como evidencia de una feature TLS ante el
  jurado sería exactamente el error que CLAUDE.md prohíbe ("no aceptar una
  feature solo porque su nombre menciona una capa").
- **Prueba reproducible**: `grep -n 'http \|iperf-tcp\|dns-valid' scripts/f1/run-benign.sh` en el bloque `mixed-light` (líneas 218-236) confirma la ausencia de cualquier llamada TLS.
- **Corrección propuesta**: mover `tls_session_rate_60s` de `MIXED-V2` a `HTTPS-SESSIONS-V2`.
- **Estado**: corregida en `configs/campaigns/multilayer-v2-normal.json`; verificado con `tests/test_multilayer_v2_matrix.py::test_tls_session_rate_declared_on_tls_producing_profile`.

## Hallazgo 2 — `http_status_5xx_ratio_60s` sin ningún camino de código capaz de producirlo

- **Severidad**: crítica.
- **Hecho observado**: la versión previa de `configs/server/ppi-api.py` no
  tenía ningún `send_json`/`send_response` con código 5xx en ninguna rama de
  `do_GET`, `do_POST`, `do_PUT` ni `do_DELETE`. `docs/161` ya advertía que un
  5xx sólo se probaría "controlado... en un piloto", es decir, fuera de la
  matriz repetible. Aun así, `API-NORMAL-20` y `MIXED-V2` declaraban
  `http_status_5xx_ratio_60s` en `feature_coverage`.
- **Inferencias**: la feature nunca podía observarse con valor distinto de
  0/0→0.0 en ninguna repetición oficial planeada; la reclamación de cobertura
  era estructuralmente irrealizable, no sólo estadísticamente rara (a
  diferencia de features "escasas" ya documentadas en el dataset v1, como RST
  o NXDOMAIN, que sí tienen un perfil dedicado capaz de producirlas).
- **Riesgo**: el contrato `multilayer-v2.json` agrega esta feature
  explícitamente como "octava feature L7 nueva"; entrenar/evaluar con una
  columna que jamás varía en el conjunto normal la vuelve inútil para
  discriminación y es una vulnerabilidad directa ante la pregunta del jurado
  "¿esta feature es calculable con evidencia real?".
- **Prueba reproducible**: antes de la corrección, `grep -n "50[0-9]" configs/server/ppi-api.py` no encontraba ningún envío de status 5xx.
- **Corrección propuesta**: agregar `GET /api/error` → 500 determinista, y añadirlo como sexto caso (índice 5, ciclo módulo 6) en la rotación de `api-normal`.
- **Estado**: corregida en `configs/server/ppi-api.py:31` y `scripts/f1/run-benign.sh` (caso `api-normal`); cubierta por `tests/test_ppi_api_server.py::test_error_endpoint_produces_deterministic_5xx` y `::test_api_normal_rotation_reaches_every_case_at_count_20`. **Pendiente de desplegar en VM03/VM05** — el despliegue registrado en `957a96e` usó la versión anterior sin este endpoint.

## Hallazgo 3 — cuatro features heredadas de v1 sin perfil que las ejercite

- **Severidad**: alta.
- **Hecho observado**: de los seis perfiles originales de
  `multilayer-v2-normal.json`, ninguno ejecutaba `ping`, `tcp-refused`,
  `http-missing` ni `dns-nxdomain`/`dns-mixed`. `MIXED-V2` declaraba
  `icmp_ratio_10s`, `rst_ratio_10s`, `http_error_ratio_60s` y
  `dns_nxdomain_ratio_60s` sin que `mixed-light` pueda producirlas: no envía
  ICMP, su única solicitud HTTP siempre es 200, su DNS siempre es NOERROR y no
  hay RST en un flujo TCP/iperf exitoso.
- **Inferencias**: mismo patrón que el Hallazgo 1 — cobertura declarada pero
  estructuralmente irrealizable con el diseño de seis perfiles.
- **Riesgo**: cuatro de las catorce features heredadas de v1 (ya validadas
  exhaustivamente en 145 campañas F1-R01–R05) quedarían sin evidencia real
  específica del dataset v2.
- **Prueba reproducible**: inspección de `scripts/f1/run-benign.sh`, caso
  `mixed-light` (líneas 218-236): sólo invoca `http`, `iperf-tcp`,
  `dns-valid`.
- **Corrección propuesta**: agregar cuatro perfiles nuevos —`PING-V2`,
  `HTTP-404-V2`, `DNS-MIXED-V2`, `TCP-REFUSED-V2`— que reutilizan escenarios
  ya implementados y no modificados (`ping`, `http-missing`, `dns-mixed`,
  `tcp-refused`), con `estimated_pcap_bytes` tomado de evidencia histórica real
  de esos mismos escenarios en F1-R01–R05 (PING-10, HTTP-404-5,
  DNS-MIXED-20-2, TCP-REFUSED-5), no inventado.
- **Estado**: corregida. La matriz queda en diez perfiles; `validate_matrix.py --feature-schema configs/features/multilayer-v2.json` confirma 28/28 features con cobertura declarada. Ningún perfil nuevo fue ejecutado: son planes, no evidencia.

## Hallazgo 4 — inconsistencia de nombres en `ANOM-SYN-RATE-50`

- **Severidad**: media.
- **Hecho observado**: `configs/campaigns/multilayer-v2-anomalies.json`
  declaraba `{"id":"ANOM-SYN-RATE-50","scenario":"tcp-refused","args":["10"]}`.
  `tcp-refused` sólo admite conteos 3, 5 o 10 (`scripts/f1/run-benign.sh`), así
  que el id no puede corresponder a una ejecución real de "50" intentos.
- **Inferencias**: probable copia del patrón usado en `ANOM-AUTH-FAIL-50` sin
  actualizar el sufijo numérico al valor real de `args`.
- **Riesgo**: bajo operacionalmente (`args` ya era válido para el escenario),
  alto en trazabilidad — un id mal etiquetado puede llevar a atribuir
  resultados de evaluación ciega a "50 intentos" cuando en realidad fueron 10.
- **Prueba reproducible**: comparar el sufijo numérico del id contra el último
  elemento de `args` en cada perfil; ahora cubierto por
  `tests/test_multilayer_v2_matrix.py::test_profile_id_numeric_suffix_matches_its_own_argument`.
- **Corrección propuesta**: renombrar a `ANOM-SYN-RATE-10`.
- **Estado**: corregida.

## Hallazgo 5 — `204 No Content` con cuerpo de mensaje (viola RFC 9110 §15.3.5)

- **Severidad**: media.
- **Hecho observado**: `do_PUT` en `ppi-api.py` enviaba
  `self.send_json(204, {})`: un status 204 acompañado de un cuerpo JSON de 2
  bytes con `Content-Length`. RFC 9110 §15.3.5 prohíbe explícitamente cuerpo
  de mensaje en una respuesta 204.
- **Inferencias**: detectado al escribir `tests/test_ppi_api_server.py`: un
  cliente HTTP estricto (`urllib`/`http.client` de Python) falla con
  `JSONDecodeError` al intentar leer ese cuerpo. `curl` con
  `--output /dev/null`, usado por `run-benign.sh`, no lo nota porque descarta
  el cuerpo sin parsearlo — por eso el defecto pasó inadvertido en los
  pilotos manuales ya ejecutados en VM03.
- **Riesgo**: cualquier cliente HTTP más estricto que `curl` (bibliotecas de
  otros lenguajes, algunos proxies) podría fallar o comportarse de forma
  indefinida ante esta respuesta; es un defecto real de protocolo, no de
  estilo.
- **Prueba reproducible**: `tests/test_ppi_api_server.py::test_put_profile_204_has_no_body` reproduce la petición con `urllib` y confirma cuerpo vacío tras la corrección.
- **Corrección propuesta**: `do_PUT` ahora usa `self.send_response(204); self.end_headers()` sin cuerpo ni `Content-Length`.
- **Estado**: corregida. Pendiente de desplegar en VM03 (mismo aviso que Hallazgo 2).

## Hallazgo 6 — `ppi-api.py` no era probable localmente sin privilegios

- **Severidad**: media (bloqueaba explícitamente el punto 5 de la tarea).
- **Hecho observado**: `LOG` estaba fijado a `/var/log/ppi-api/auth.jsonl`;
  `record()` llama `os.makedirs(os.path.dirname(LOG), exist_ok=True)` en cada
  request, lo que falla con `PermissionError` para un usuario sin privilegios
  de escritura en `/var/log`.
- **Inferencias**: esto impedía ejercitar la lógica de `ppi-api.py` fuera de
  VM03 (por ejemplo en este repositorio o en CI) sin `root`.
- **Riesgo**: bajo en producción, pero bloqueaba pruebas automatizadas y la
  detección temprana de defectos como el Hallazgo 5.
- **Prueba reproducible**: `tests/test_ppi_api_server.py` levanta el servidor
  completo en `127.0.0.1` con puerto efímero, fijando `PPI_API_LOG_PATH` a un
  directorio temporal, sin `sudo`.
- **Corrección propuesta**: `LOG = os.environ.get("PPI_API_LOG_PATH", "/var/log/ppi-api/auth.jsonl")`. El valor por defecto no cambia porque `ppi-api.service` no define esa variable, así que el comportamiento en producción es idéntico.
- **Estado**: corregida.

## Verificación de las 14 features v1 dentro del extractor v2

Se comparó fórmula por fórmula `scripts/features/extract_multilayer_v2.py`
contra `scripts/features/extract_multilayer.py`: las catorce features
originales (`packet_rate_10s` … `tls_session_rate_60s`) usan exactamente las
mismas ventanas, el mismo criterio de atribución de flujo y las mismas
fórmulas de `safe_ratio`/conteo. No se encontró divergencia. El docstring del
extractor v2 que afirma esta equivalencia es correcto.

## Estado final de la matriz normal v2

```
python3 scripts/f1/validate_matrix.py \
  --matrix configs/campaigns/multilayer-v2-normal.json \
  --feature-schema configs/features/multilayer-v2.json \
  --storage-path /tmp
```

10 perfiles, 50 campañas planeadas, 28/28 features con cobertura declarada y
verificable contra el escenario que las produce. `storage_gate_pass` da
`false` contra `/tmp` porque este entorno de revisión no tiene 20 GiB libres
reservados; es el comportamiento correcto del gate, no un defecto — en
`/srv/ppi-evidence` (VM01) debe evaluarse de nuevo antes de cualquier campaña
oficial.

## Limitación no corregida (documentada, no resuelta)

`fragment_ratio_10s` sigue declarada en `MIXED-V2` sin que ningún perfil de la
matriz v2 pueda forzar fragmentación IP real: la MTU de laboratorio (1500) y
los tamaños de payload usados por todos los escenarios actuales nunca
fragmentan un paquete. El valor esperado es 0.0 de forma estructural. No se
agregó un escenario nuevo (p. ej. ping con payload > MTU) para forzarla porque
eso excede el alcance de "preparación sin desplegar VMs" de esta revisión y
requeriría calibración propia. Queda registrado en `known_gaps` de
`configs/campaigns/multilayer-v2-normal.json`.
