# Registro de cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Cada entrada dice qué cambió y **con qué se midió**, no solo qué se tocó.

## Sin publicar

### Corregido

- **La documentación pública describía el modelo y la respuesta de la versión
  anterior.** README, system card, configuración, instalación, guía, `CITATION.cff`
  y `.zenodo.json` presentaban como vigentes el OCSVM (`1,8126`), el bloqueo binario
  de 120 s en el propio sensor y un panel sin login. Lo que corre en Sensor1
  (verificado por SSH el 2026-10-09) es un **Isolation Forest recalibrado**
  (`score_samples < −0,568892`), con el sensor por **SPAN** y respuesta
  **PERMIT/LIMIT/BLOCK** aplicada por un agente en el host a partir de un feed
  firmado. Nueva fuente de verdad: `docs/FICHA-TECNICA-DESPLIEGUE-VIGENTE.md`, con
  `docs/RECONCILIACION-MANIFIESTO-MOTOR.md` y
  `docs/dataset/MODEL_CARD_IF_RECALIBRADO.md`. La system card se reorganiza en
  **parte A** (F6, histórica: sus cifras se conservan) y **parte B** (vigente), y se
  corrige en el **generador**, para que regenerarla no devuelva las frases viejas.
  Se declara que **92,4 % → 4,45 % no aísla el efecto de recalibrar** (cambiaron
  modelo, datos y alcance) y que las «cero caídas en 58 corridas» son de F6.

- **El feed se etiquetaba con una versión de heurísticos que no era la aplicada.**
  `publicar_feed.py` copiaba `--umbrales` tal cual; en Sensor1 la unidad pasaba
  `2026-10-06.1` mientras el motor aplicaba `.2`. Ahora la etiqueta sale de
  `heuristicos.VERSION_UMBRALES` y un argumento distinto produce un aviso.
  3 pruebas nuevas en `tests/test_publicar_feed.py`.

- **`main` no tenía los heurísticos desplegados.** Se incorpora
  `VERSION_UMBRALES = "2026-10-06.2"`: ratios de unicidad a 0,45 (el espejo topa los
  ratios «todo único» en ~0,5) y rama OR de `port_scan` para la ráfaga masiva
  (≥ 200 intentos/30 s con ≤ 10 % completados). Validado en el sensor: FPR de la rama
  +5 disparos en 712 450 ventanas. Las 14 pruebas existentes siguen pasando; 4 nuevas
  en `tests/test_heuristicos_port_scan.py`.

- **El panel mostraba «OCSVM» como detector aunque el motor corriera otro.** La
  tarjeta usa ahora el `detector_name` real de `/api/status`, y el recorrido guiado
  ya no afirma «One-Class SVM».

- **Enlaces a informes de investigación que no existían en ningún repositorio
  publicado** (`docs/fase0X-…`, `investigacion/…`). Los 16 informes citados se
  publican en `VF-PPI-TESIS-ORQUESTACION/02-metodologia/historico-laboratorio/` y los
  documentos (y sus generadores) los enlazan fijados al commit `f2f0ffd`.

- **`verificar_consistencia.py` tenía la verdad invertida**: marcaba como obsoleto
  «el detector es un Isolation Forest». Ahora marca lo contrario (OCSVM presentado
  como desplegado) y «no hay nivel intermedio».

- **El motor descartaba el 5,55 % de su propio anillo de captura, en silencio.**
  `tcpdump -G N -W M` sale con estado 0 al completar los M ficheros, y systemd
  lo relanzaba: `NRestarts=1458`, relevos cada 4m02s. En cada arranque, tcpdump
  con `-Z` hace `chown` del **primer** fichero a `tcpdump:tcpdump`, que el
  usuario del motor no puede leer; el resto los crea ya sin privilegios y
  heredan el grupo del directorio setgid. `motor_decision.py` se tragaba el
  `PermissionError` con un `except Exception: pass`. Se quita `-W` —no servía
  para podar, de eso se encarga `cyberflow-limpieza.timer`— y el motor cuenta
  ahora `pcaps_ilegibles` en cada decisión. Efecto secundario cerrado: los ~2 s
  sin capturar de cada relevo, un 0,8 % del tráfico.

- **`tcp_retransmission_ratio_10s` contaba artefactos del espejo como
  retransmisiones de la red.** La sesión SPAN enseña la misma trama dos veces:
  el tráfico entre VLAN se ve al entrar y al salir del cortafuegos (TTL-1), y
  la difusión inunda los dos puertos troncales que la sesión escucha (copia
  idéntica). Medido en el sensor: **0,1488 antes y 0,0000 después** — las 100
  «retransmisiones» eran las 100 copias. Se deduplica la **entrada** del
  extractor congelado, nunca su fórmula. `--sin-deduplicar` desactiva el
  filtro para poder medir la diferencia.

### Añadido

- **`scripts/modeling/verificar_equivalencia_umbral.py`**: comprueba sobre el joblib
  desplegado que `decision_function = score_samples − offset_` y que el umbral del
  manifiesto (escala `score_samples`) y el del informe de calibración (escala
  `decision_function`) son el mismo punto de corte. Escribe un JSON de evidencia con
  hashes. 4 pruebas en `tests/test_verificar_equivalencia_umbral.py`.

- **Extractor `multilayer-v3` con tres variables de capa 2**:
  `arp_request_rate_10s`, `unique_src_mac_30s` y `mac_ip_binding_changes_60s`.
  El extractor v2 descarta toda trama que no sea IPv4 y por tanto nunca ve una
  ARP, así que un barrido de la propia VLAN —que no cruza el enrutador— le
  resulta invisible. Medido en producción: `10.10.20.53` emite 1874 tramas ARP
  y **cero** tráfico IP visible; para las 28 variables de v2 esa máquina no
  existe.

  v3 **importa** a v2 en vez de reimplementarlo, así que las 28 primeras
  columnas son idénticas por construcción y el modelo publicado sigue
  reproduciéndose contra los SHA-256 del manifiesto.

  Cada entidad se ancla a su *VLAN nativa* para que la copia del espejo no
  infle el recuento de MAC. La VLAN nativa no es la etiqueta más frecuente
  —las dos copias empatan— sino la más frecuente entre las tramas cuya MAC de
  origen aparece en una sola VLAN.

- `docs/INVENTARIO.md`: qué máquina, qué dirección, qué VLAN, en qué modo, y
  qué **no** debe estar.

- `scripts/laboratorio/BANCO-DE-PRUEBAS.md`: aprovisionamiento del banco de
  pruebas con la carga calculada y la puerta de verificación previa.

### Pendiente de declarar en las fichas del modelo

`MODEL_CARD_OCSVM.md` y `SYSTEM_CARD_MOTOR.md` todavía no mencionan la
exclusión de CARP y pfsync, el 47 % de ruido restante, ni el punto de
observación. Describen un sistema anterior al que hay.

### Limitaciones medidas que conviene no olvidar

- `unique_src_mac_30s` vale **1 en las 761 ventanas** observadas y
  `mac_ip_binding_changes_60s` vale **0 en las 761**. Sin varianza no aportan
  al modelo no supervisado: son detectores de suplantación ARP a demostrar en
  la fase de ataques, no variables de línea base. Solo `arp_request_rate_10s`
  (recorrido 0 a 2,0) aporta.
- Las respuestas ARP llegan incompletas al espejo: son unidifusión y solo se
  ven las dirigidas al cortafuegos.
- El **86,3 %** de las tramas de capa 2 del espejo son CARP y pfsync.
