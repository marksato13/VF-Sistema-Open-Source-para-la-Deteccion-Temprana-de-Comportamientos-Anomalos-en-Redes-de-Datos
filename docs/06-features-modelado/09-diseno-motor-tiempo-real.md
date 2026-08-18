# Diseño del motor de decisión en tiempo real — bloqueo de infraestructura encontrado

- **Fecha:** 2026-08-17
- **Estado:** confirmaste la opción 1 (acceso root temporal en VM02). Los cuatro artefactos ya están escritos, versionados y probados con un smoke test sintético contra el modelo congelado real — falta únicamente el despliegue, que requiere el acceso root que ya autorizaste.

## Actualización — artefactos listos (2026-08-17, después de tu confirmación)

Los cuatro artefactos que se listaban abajo como "lo que puedo hacer ahora mismo" ya están escritos:

1. `configs/sensor/ppi-motor-capture.service` — captura continua en anillo (`tcpdump -G 15 -W 8`, ~120s de historia, mismo patrón de privilegios que `ppi-pcap-control` ya validado en 145+ campañas: arranca root, suelta a `tcpdump` con `-Z`). Directorio `/var/lib/ppi-motor-capture` con setgid a `useransible` para que el motor pueda leer sin sudo.
2. `configs/sensor/ppi-motor.service` — corre como `useransible`, sin privilegios nuevos, con `ProtectSystem=strict` y solo lectura sobre captura/EVE.
3. `configs/sensor/install-ppi-motor.sh` — instalación única e idempotente (unidades systemd, ACL de lectura sobre `/var/log/suricata`, venv con las versiones exactas de `requirements-model.txt`, copia del `.joblib` verificando su SHA-256 real contra el manifiesto de calibración). Requiere root real, no sudo de `useransible` — **no se agregó ninguna línea nueva al sudoers**, porque el diseño final no la necesita (ver siguiente punto).
4. `scripts/engine/motor_decision.py` — el motor mismo: tail incremental de `eve.json` con detección de rotación/truncamiento, lectura de los PCAP ya cerrados del anillo (excluye siempre el más reciente, que tcpdump sigue escribiendo), llamadas directas a `load_packet_observations`/`load_app_observations`/`build_rows` del extractor congelado (cero fórmulas reimplementadas), umbral leído del `manifest.json` de la calibración (no hardcodeado — mismo principio que el MVP aplicaba con `metricas_offline.txt`), log JSONL de decisiones.

**Cambio de diseño respecto al plan original:** no hace falta una línea sudoers nueva para `useransible`. `ppi-motor-capture.service` corre siempre activo como servicio systemd (arranca solo, no requiere que `useransible` lo controle en cada ejecución) y `ppi-motor.service` corre como `useransible` sin sudo, leyendo captura y EVE por ACL (`setfacl`, no por pertenencia a grupo ni por sudo). Root real solo se necesita **una vez**, para la instalación.

**Verificación hecha antes de darlo por bueno** (no solo "compila"): smoke test con PCAP y EVE sintéticos que ejercita el pipeline completo — exclusión del archivo PCAP activo, parseo real de paquetes, tail incremental de EVE, `build_rows` produciendo filas elegibles, carga del umbral real (`1.8126087939765134`) desde el manifiesto real, y scoring real con `ocsvm_scaled.joblib` sin excepciones. `systemd-analyze verify` sobre ambas unidades no reportó errores de sintaxis (solo la advertencia esperada de que el venv de VM02 todavía no existe en esta máquina).

**Limitación declarada, no oculta:** el anillo de ~120s de PCAP es más corto que una campaña offline completa. Un flujo que ya llevaba más de ~120s abierto la primera vez que el motor lo ve puede tener su IP iniciadora mal atribuida si el paquete que abrió el flujo ya rotó fuera del buffer — documentado en el docstring de `motor_decision.py`. Para tráfico de ataque real (ráfagas cortas, según la evaluación bloqueada) esto no debería aplicar en la práctica, pero no se afirma como resuelto sin medirlo en producción.

**Pendiente exclusivamente de tu acceso root en VM02:**
- Completar `EXPECTED_PYTHON_MAJOR_MINOR` en `install-ppi-motor.sh` si la versión de Python de VM02 difiere de 3.14 (verificar con `python3 --version` antes de correr el script).
- Ejecutar `install-ppi-motor.sh` como root.
- Verificar manualmente que `ppi-motor-capture.service` está activo y que `useransible` puede leer los archivos rotados.
- Habilitar `ppi-motor.service` a mano (deliberadamente NO automático dentro del script de instalación) y observar `journalctl -u ppi-motor.service -f` un rato antes de dejarlo desatendido.

## Despliegue real en VM02 (2026-08-17/18) — hallazgos y correcciones

Instalado con acceso root temporal (cuenta `sensor_motor`, otorgado por el usuario y luego revocado). Tres fallos reales encontrados y corregidos durante el despliegue, ninguno visible en el smoke test sintético previo:

1. **`python3.14-venv` no instalado y VM02 sin internet.** `install-ppi-motor.sh` fallaba en la creación del venv. Se descargaron los `.deb` exactos (`python3.14-venv`, `python3-pip-whl`, `python3-setuptools-whl`) en VM01 —misma Ubuntu 26.04 "resolute", mismo CPython 3.14.4— y se instalaron offline con `dpkg -i` (no `apt-get install ./archivo.deb`: ese comando usa un usuario sandbox `_apt` sin permiso para leer el home de `useransible`). Igual para las dependencias Python (`joblib`, `numpy`, `scikit-learn`, `scipy`, etc. de `requirements-model.txt`): se descargaron como wheels en VM01 y se instalaron con `pip install --no-index --find-links=artifacts/wheels`.
2. **`capture_start` implícito causaba `eligible_training=False` tras cualquier pausa de tráfico.** Corregido fijando `capture_epoch` al arrancar el proceso. Luego se encontró que esto por sí solo causaba un **bucle de reinicio real** (`ValueError` en `build_rows`) porque el anillo de captura sigue corriendo aunque el motor se reinicie, y puede tener paquetes más viejos que ese piso fijo. Corrección final: `min(capture_epoch, primera_observación_real_del_ciclo)` — evita la excepción y además aprovecha el historial genuino del anillo en vez de descartarlo en cada reinicio.
3. **`EveTail` releía el `eve.json` completo (162 MB) en el primer ciclo** en vez de arrancar desde el final del archivo — coincidía con una memoria inicial de 429 MB frente a ~80 MB tras el fix.

**Validación real end-to-end**: tras los fixes, el motor procesó una ráfaga real de 10 ICMP echo (generada con `scripts/f1/run-benign.sh ping 10 0.5` desde VM05) y produjo la decisión correcta: `packet_count_10s=20`, `score=2.0678`, `threshold=1.8126` → **PERMIT**, con el `.joblib` congelado real, no un mock.

**Cuarto hallazgo, de diseño no de bug**: 774/774 alertas iniciales fueron ventanas sin ningún paquete (`packet_count_10s=0`) — el modelo OCSVM nunca vio vectores "todo ceros" en el entrenamiento offline (las campañas siempre tenían algo de tráfico dentro de su ventana), así que las clasifica como fuera de distribución. El usuario decidió (opción recomendada) agregar un heurístico explícito: si `packet_count_10s=0` y no hay observaciones de aplicación (HTTP/DNS/TLS) en la ventana, se registra `PERMIT` sin llamar al modelo — mismo patrón que los detectores heurísticos ya previstos en la hoja de ruta (complementan al modelo, nunca lo reemplazan). Queda registrado en el log con `detector_name="empty_window_heuristic"` para distinguirlo de una decisión real del modelo.

Acceso root temporal revocado al cerrar esta sesión de despliegue: se eliminó `/etc/sudoers.d/90-temporal-claude-motor` y se vació `~/.ssh/authorized_keys` de `sensor_motor`. Verificado con una conexión SSH real que ahora es rechazada (`Permission denied (publickey,password)`), no solo asumido. El motor y la captura siguen corriendo de forma autónoma (systemd, `Restart=always`), sin necesitar ningún acceso privilegiado adicional para operar día a día.

## Enforcement inline (2026-08-18) — desplegado, con dos fallos reales corregidos en producción

Implementado `configs/sensor/ppi-enforce` (helper raíz local en VM02, sin SSH entre VMs porque el Sensor ya es el router LAN↔DMZ), tabla nftables separada y aditiva (`inet ppi_enforce`, hook forward prioridad -300), bloqueo con expiración nativa (120s, confirmado con el usuario), whitelist interna. Motor integrado con `--enforce` y `NoNewPrivileges=false` (necesario para que `sudo` funcione desde el proceso).

**Validación real de bloqueo/desbloqueo** (no solo el helper, el efecto real en la red): con el cliente real (`10.20.0.20`), ping baseline 0% pérdida → bloqueo aplicado → ping durante el bloqueo **100% de pérdida real** → expiración natural a los 20s → ping después **0% de pérdida otra vez**, sin intervención manual. El ciclo completo automático (Suricata → features → modelo → ALERT → enforcement) también se disparó solo, sin que yo invocara nada manualmente, confirmando la integración de punta a punta.

**Fallo 1 — `validate_ip` moría en silencio para el caso normal.** Bajo `set -e`, la última instrucción del bucle de whitelist (`[[ "$ip" == "$whitelisted" ]] && die ...`) devuelve código 1 cuando la IP NO coincide (el caso normal, no bloqueado), y como es la última instrucción de la función, ese código se propagaba como el retorno de la función completa, matando el script para CUALQUIER IP válida sin pasar por `die()` ni imprimir nada. Las pruebas locales previas solo cubrían casos de rechazo (donde `die()` sí se ejecuta), nunca el camino de éxito — por eso no se detectó hasta probar contra una IP real ya desplegado. Corregido con `return 0` explícito al final de `validate_ip` y `ensure_setup` (el mismo patrón de riesgo aplicaba ahí para llamadas repetidas con la tabla ya creada).

**Fallo 2 — bucle real de re-bloqueo infinito en producción.** Después de corregir el fallo 1, el motor quedó re-bloqueando a `10.20.0.20` en cada ciclo (cada 10s), indefinidamente, para la MISMA ventana histórica (`window_end_utc` de más de una hora atrás, mismo score exacto repetido). Causa: `scored_windows` se podaba por antigüedad relativa al reloj real (`anchor < cutoff`), asumiendo que ninguna ventana relevante podía ser más vieja que `history_seconds`. Esa suposición se rompe porque `tcpdump -G` solo rota de archivo al llegar un paquete nuevo — en tramos ociosos, un archivo del anillo puede tardar mucho en rotar y seguir aportando paquetes con timestamps antiguos ciclo tras ciclo. La poda por reloj borraba esa ventana de la memoria de deduplicación justo después de registrarla, permitiendo que se repuntuara y re-bloqueara para siempre. El log llegó a 51,988 líneas (archivado, no borrado, en `motor_decision.log.pre-fix-scored-windows-bug-2026-08-18` en VM02) antes de corregirlo. Fix: `scored_windows` ahora se acota por tamaño (FIFO, `MAX_SCORED_WINDOWS=20000`), no por antigüedad de reloj — una vez puntuada, una ventana queda recordada sin importar su timestamp. Verificado tras el fix: de 51,988 líneas duplicadas a 640 líneas normales tras reiniciar, sin ninguna ventana repetida.

**Hallazgo operativo, no un bug:** ráfagas de ping pequeñas (2–6 paquetes) generadas durante estas pruebas puntuaron de forma inconsistente cerca o por debajo del umbral (`1.24`, `0.38`, `0.0000187`, todas `< 1.8126`) frente a otras similares que pasaron (`1.87`). Consistente con el FPR ya documentado (4.71%) y con que el modelo fue calibrado contra el *escenario completo* `PING-10` (diez ecos en una ráfaga específica), no contra fragmentos sueltos de 2-6 paquetes como los generados aquí de forma ad-hoc para pruebas. No se cambió el modelo ni el umbral por esto — es una limitación declarada, no una corrección silenciosa.

Acceso root temporal para este segundo despliegue (mismo patrón: llave SSH a `sensor_motor` + sudoers NOPASSWD) revocado al cerrar esta sesión.

## Estado original de este documento (antes de tu confirmación), para trazabilidad

## Lo que ya está resuelto (sin bloqueos)

- **EVE continuo:** Suricata en VM02 ya corre `service_state=active` de forma permanente (58.5M paquetes procesados, cero drops), generando `/var/log/suricata/eve.json` sin interrupción. El motor puede hacer `tail -f` de este archivo tal cual, ahora mismo, sin cambios de infraestructura.
- **Reutilización del extractor:** revisé `scripts/features/extract_multilayer_v2.py` a fondo. Está bien factorizado — `attribute_packets()`, `load_app_observations()` y `build_rows()` son funciones puras e importables, no código enterrado dentro de un script de línea de comandos. El motor puede **importar y llamar exactamente estas funciones**, alimentándolas con un buffer continuo (últimos ~60-120s) en vez de un PCAP/EVE de campaña completa, sin reescribir ni una fórmula. Esto evita el error del MVP anterior (duplicación manual de la lógica de features entre entrenamiento y motor, con riesgo real de que se desincronicen).
- **Modelo congelado:** `ocsvm_scaled.joblib` ya está listo para cargar y puntuar (`08-modelo-final-congelado-ocsvm.md`).

## El bloqueo real: no existe captura de paquetes continua

Para calcular features a nivel de paquete (SYN, RST, TTL, fragmentación, retransmisión) el motor necesita PCAP en vivo, no solo EVE. Revisé el mecanismo de captura existente (`configs/sensor/ppi-pcap-control`, desplegado como helper raíz que `useransible` puede invocar vía sudo) y **es deliberadamente de una sola captura activa a la vez, por campaña** (`start|stop ID`, falla si ya hay una activa). Si el motor usara este mismo mecanismo de forma permanente, **bloquearía cualquier futura campaña del dataset** (y viceversa: iniciar una campaña pararía al motor).

Necesito un mecanismo de captura **separado**, exclusivo para el motor, corriendo en paralelo al de campañas. Eso implica:

1. Un nuevo servicio systemd en VM02 (`ppi-motor-capture.service` o similar) con `tcpdump` en rotación continua (buffer, tamaño de archivo y filtro similares a los ya calibrados: interfaz `ens35`, filtro LAN↔DMZ, snaplen completo, rotación acotada — mismos parámetros ya validados en `docs/05-plan-pruebas/11-diseno-captura-PCAP-G4.md`, solo que perpetuo en vez de por campaña).
2. Una nueva regla en el sudoers de `useransible` en VM02 para poder iniciar/detener/consultar ese servicio (el archivo actual, `configs/sensor/useransible-ppi-metrics.sudoers`, solo autoriza exactamente `ppi-suricata-metrics` y `ppi-pcap-control` — nada más, sin comodines).

**`useransible` no tiene sudo general en VM02** (confirmado, mismo patrón que bloqueó el fix de `/api/error` y el ajuste del servicio iperf3 anteriormente en este proyecto). Desplegar un servicio nuevo + una regla sudoers nueva requiere acceso root real en VM02, que no tengo.

## Lo que puedo hacer ahora mismo (sin permisos nuevos)

Puedo escribir y dejar listo, versionado en el repo, para que se despliegue en cuanto haya acceso:

1. `configs/sensor/ppi-motor-capture` — helper de captura continua (mismo estilo que `ppi-pcap-control`, rotación fija, sin parámetros abiertos).
2. Unidad systemd correspondiente.
3. La línea sudoers nueva a agregar al archivo ya versionado.
4. El motor de decisión mismo (`scripts/engine/motor_decision.py` o ubicación similar): tail de EVE + lectura de la rotación de PCAP del nuevo helper + `attribute_packets`/`build_rows` reusados + scoring con el `.joblib` congelado + logging de decisiones — todo esto **no necesita permisos nuevos para escribirse**, solo para desplegarse y ejecutarse de verdad contra tráfico en vivo.

## Lo que necesito de ti

Una de estas dos rutas:

1. **Conseguir acceso root temporal en VM02** (como se hizo para el fix de `/api/error` en VM03) para desplegar el helper + systemd + sudoers nuevos, dejándolo persistente — la vía "correcta" y ya usada varias veces en este proyecto.
2. **Alternativa sin cambios de infraestructura:** degradar el motor para que use *solo* EVE (sin PCAP en vivo) para el primer despliegue — Suricata's EVE `flow` events ya traen `pkts_toserver/toclient`, `bytes_toserver/toclient`, banderas TCP resumidas. Esto permitiría un motor funcional YA, pero **con una limitación real y declarada**: no sería exactamente el mismo camino de cálculo que se usó para entrenar el modelo (violaría el principio de "mismo código en train y en producción" que me propuse evitar) — features como TTL exacto, fragmentación real y detección de retransmisión por número de secuencia no están disponibles solo con EVE. Sería una aproximación, no una réplica fiel del modelo entrenado.

**Mi recomendación:** la opción 1. Es más trabajo de coordinación ahora, pero evita construir el motor sobre una aproximación que ya sé que es distinta al modelo que acabamos de congelar con tanto cuidado.

¿Cuál prefieres, o hay una tercera opción (por ejemplo, tú mismo aplicando los cambios de infraestructura por consola) que no estoy viendo?
