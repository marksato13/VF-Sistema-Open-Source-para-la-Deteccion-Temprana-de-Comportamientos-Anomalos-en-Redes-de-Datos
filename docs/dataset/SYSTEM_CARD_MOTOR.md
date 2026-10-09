# System card — motor de decisión y respuesta

> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, desde `results/f6/*.jsonl` (secciones 1–7) y la reconciliación del despliegue (sección 8).

Responde por **el sistema**: qué decide, qué acción ejerce y cómo se comporta. Tiene **dos partes que no deben mezclarse**:

| Parte | Secciones | Qué describe | Modelo |
|---|---|---|---|
| **A — Laboratorio evaluado (histórico)** | 1–7 | Validación F6: sensor **en línea**, bloqueo local con `nftables`, 120 s | OCSVM ([model card](MODEL_CARD_OCSVM.md)) |
| **B — Despliegue vigente** | 8 | Sensor por **SPAN** con **enforcement distribuido** (feed firmado → relay → agente en el host) | Isolation Forest recalibrado ([model card](MODEL_CARD_IF_RECALIBRADO.md)) |

Las cifras de la parte A se midieron y valen **para lo que se midió**; no se trasladan a la parte B. Fuente de verdad del despliegue vigente: [`FICHA-TECNICA-DESPLIEGUE-VIGENTE.md`](../FICHA-TECNICA-DESPLIEGUE-VIGENTE.md). Los datos están en [`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md).

---

# Parte A — Laboratorio evaluado en F6 (histórico)

## 1 · Qué hace

Cada 10 s, para cada IP iniciadora activa, el motor extrae las 28 variables con el **mismo extractor congelado** que produjo el dataset —sin duplicar fórmulas—, puntúa la ventana y decide.

```text
PCAP en anillo + eve.json
        │
        ▼
extract_multilayer_v2  ──►  28 variables
        │
        ▼
OCSVM  ó  heurísticos L7   ──►  PERMIT / ALERT
        │
        ▼
nftables en el propio Sensor  ──►  bloqueo 120 s
```

El Sensor **es** el router entre la red de clientes y la de servicio, así que el bloqueo se aplica en el punto de paso: no hace falta SSH a otra máquina ni un agente en el servidor.

> **Esto describe el despliegue que se evaluó en F6**, no el que está corriendo hoy. Las cifras de las secciones 4 y 7 se midieron con el sensor en el camino del tráfico y con el OCSVM. El despliegue vigente está en la sección 8.

---

## 2 · Detectores

| Detector | Qué dispara | Por qué existe |
|---|---|---|
| `ocsvm_scaled` | `score < 1,8126` | El modelo de la model card |
| `auth_failure_heuristic` | ≥ 5 peticiones HTTP y ≥ 80 % con estado 401/403 en 60 s | El modelo es débil justo en fuerza bruta; esta regla lo cubre por la vía L7 |
| `empty_window_heuristic` | Ventana sin datos | Devuelve `PERMIT`: no se puntúa lo que no se observó |
| `no_live_packets_heuristic` | Ventana sin paquetes en vivo | Igual: `PERMIT` |

**Los dos heurísticos de ventana vacía existen por un falso positivo real.** Sin ellos, una ventana sin tráfico producía un vector de ceros que el modelo puntuaba como anómalo y bloqueaba a un cliente inocente.

Reparto observado en las 58 corridas de F6:

| Detector | Ventanas |
|---|---:|
| `empty_window_heuristic` | 97 |
| `ocsvm_scaled` | 84 |
| `no_live_packets_heuristic` | 70 |
| `auth_failure_heuristic` | 10 |

> El heurístico de autenticación **no es decorativo**: disparó en producción y detectó un rociado de contraseñas **por sí solo**, sin ayuda del modelo, con 6,1 s de adelanto. Valida en un ataque real el camino L7.

---

## 3 · Acción de control (modalidad evaluada)

| | |
|---|---|
| **Mecanismo** | `nftables` en VM02, vía el ayudante versionado `ppi-enforce` |
| **Alcance** | La IP ofensora de la red de clientes |
| **Duración** | **120 s**, con expiración nativa del conjunto |
| **Reversión** | Automática al expirar; no requiere intervención |
| **Lista blanca** | Direcciones de infraestructura, nunca bloqueables |

En esta modalidad la respuesta era **binaria**: permitir o bloquear 120 s. El despliegue vigente sí tiene un nivel intermedio, **LIMIT**, y una escalera de caducidad distinta (sección 8.2); los 120 s de aquí no describen el sistema actual.

---

## 4 · Desempeño en operación

Dos pases con el motor activo, **58 corridas** en total.

> **Solo el pase 2 sirve para medir tiempos.** El pase 1 usó un asentamiento fijo en vez de esperar a que el motor se pusiera al día, así que sus tiempos mezclan atraso con detección; está archivado como contaminado. Se usa únicamente para disponibilidad, donde esa contaminación no aplica.

### Lo que funciona

| | |
|---|---|
| **Tiempo hasta el bloqueo** (ataques) | mediana **8,0 s** · rango 6,1–13,7 s · `n = 8` bloqueos observables |
| **Caídas de servicio registradas** | **0** en 58 corridas |
| Corridas con servicios verificados | 55/58 |

> **Precisión sobre la disponibilidad.** No se registró **ninguna** caída de servicio, pero 3 corridas no tienen medición de servicios. Lo correcto es decir «cero caídas registradas», no «100 % de disponibilidad verificada»: son afirmaciones distintas. Además, es una medición **de F6** (OCSVM, sensor en línea): **no demuestra la disponibilidad del despliegue vigente**, que no se ha medido con este protocolo.

### El resultado incómodo

> **17 de 74 ventanas de tráfico legítimo se marcaron como anómalas: 22,97 %.**

Intervalo de Wilson descriptivo al 95 %: **[14,9 – 33,7]**. El falso positivo medido en evaluación bloqueada fue **4,71 %** [2,8 – 7,9]. Las ventanas están agrupadas por corrida y comparten historia de hasta 60 s; por eso el no solapamiento de estos intervalos por ventana **no demuestra por sí solo** una diferencia inferencial.

De las 12 corridas benignas del pase 2, **5 terminaron bloqueando al cliente legítimo.**

> Quedan fuera de este cálculo las 2 corridas `H*`, que prueban a propósito la **frontera del heurístico de autenticación**: ahí la alerta es el comportamiento buscado, no un falso positivo. Incluirlas subiría la cifra sin que signifique lo mismo.

El pase 1, medido por separado pero contaminado por atraso, dio **25,81 %** [16,6 – 37,9] sobre 62 ventanas. Ambos pases comparten infraestructura y no son réplicas estadísticamente independientes.

La documentación de F6 describe una reproducción **en aislamiento**, sin otro tráfico compitiendo: una transferencia `iperf-tcp` legítima de 200 Mbit/s puntuó **1,689** frente al umbral 1,8126 y cortó al cliente durante 120 s. Otra ventana pasó por **0,0014**.

> **Límite de trazabilidad.** Los scores, PCAP y registro de bloqueo de esa prueba aislada no están versionados en `results/f6/*.jsonl`; estas cifras proceden del [informe de resultados F6](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/f2f0ffdb8f423cf9ac7ec48fb8390011a0d0eece/02-metodologia/historico-laboratorio/fase07-validacion-final/02-resultados-f6.md) del registro de investigación, y no pueden regenerarse desde los artefactos publicados.

**Causa.** El tráfico legítimo de alto volumen produce puntuaciones apiñadas justo en el margen del umbral. No es un fallo de implementación: es el umbral, calibrado sobre un conjunto donde ese tráfico estaba subrepresentado.

**Es la limitación más importante del sistema y se declara antes que cualquier resultado favorable.**

---

## 5 · Modos de fallo conocidos

| Modo | Estado | Detalle |
|---|---|---|
| Falso positivo sobre tráfico pesado | 🔴 **Abierto** | Sección 4. Solo lo resuelve una recalibración con tráfico pesado como normalidad |
| Atraso del motor bajo carga | 🟠 **Mitigado** | El parseo incremental redujo el atraso; en F6 la mediana fue 45 s con un máximo de 208 s. **El tiempo de bloqueo de la sección 4 aplica con el motor al día** |
| Falso positivo por ventana sin paquetes | ✅ Corregido | Con prueba positiva y negativa en producción |
| Reproceso del historial al reiniciar | ✅ Corregido | El motor descarta capturas más antiguas que su ventana |
| Bucle de re-bloqueo infinito | ✅ Corregido | La poda de memoria era por reloj y pasó a ser por dato |
| Artefactos del espejo leídos como retransmisiones | ✅ Corregido | La sesión SPAN duplicaba tramas y `tcp_retransmission_ratio_10s` las contaba: **0,1488 antes, 0,0000 después**. Se deduplica la entrada, no la fórmula |
| Parte del anillo descartada en silencio | ✅ Corregido | `tcpdump -W` hacía salir el proceso cada 4 min y el primer fichero de cada arranque quedaba ilegible para el motor: **5,55 %** de los bytes. El motor lo cuenta ahora en `pcaps_ilegibles` |
| Bloqueo por suplantación de IP | ⚪ **No evaluado** | Un tercero podría provocar el bloqueo de un cliente legítimo falsificando su origen. No se probó |
| Evasión del detector | ⚪ **No evaluado** | No se intentó eludirlo deliberadamente |

---

## 6 · Salvaguardas (modalidad evaluada)

- **Lista blanca** de infraestructura, imposible de bloquear.
- **Expiración nativa a los 120 s**: ningún bloqueo es permanente, así que un falso positivo se corrige solo.
- **Sin sudo general**: el motor solo puede invocar el ayudante `ppi-enforce`, con argumentos acotados.
- **El panel es de solo lectura**: observa, no ejerce ninguna acción.
- **El motor reutiliza el extractor congelado**, así que las variables de producción son por construcción las mismas del entrenamiento.

---

## 7 · Veredicto (F6)

**Demostrado con evidencia, en F6:** detectar comportamiento anómalo y **ejercer control en línea real** sobre una red enrutada, con bloqueo en una mediana de 8 s y sin ninguna caída de servicio registrada.

**No demostrado:** hacerlo con una tasa de falso positivo aceptable sobre tráfico legítimo pesado. En esa condición el sistema **todavía no es apto para operación desatendida**.

Delimitar esa frontera con medición es el resultado, no un defecto del informe.

---

# Parte B — Despliegue vigente

## 8 · Sensor por SPAN con enforcement distribuido

La evaluación de F6 se hizo con el sensor **en el camino del tráfico**. El despliegue vigente en la red de la entidad usa un **espejo SPAN** y aplica la respuesta **en el host protegido**. Lo que sigue describe ese despliegue; ninguna cifra de la parte A se traslada aquí.

### 8.1 · Dónde se ejerce el control

Con un espejo, el sensor **no está en el camino**: recibe una copia y **no bloquea el tráfico copiado**. Lo que hace es **decidir y publicar**: un feed firmado (ed25519) que un relay en el bastión lleva al host, donde un **agente** lo verifica y sincroniza una tabla `nftables` propia y aislada (`inet cyberflow`, sets `cyberflow_bloqueados` y `cyberflow_limitados`, con caducidad nativa). Cadena: **captura SPAN → motor → publicador → feed firmado → relay → agente → nftables**. Publicador, relay y agente corren con timers systemd (`OnCalendar=minutely`).

| Afirmación | Estado |
|---|---|
| LIMIT automático de punta a punta, originado por el modelo | **Validado en vivo** (campaña del 1-oct, nota `O` de orquestación) |
| BLOCK aislado con regla explícita en el host | **Validado en banco** (nota `N`) |
| BLOCK automático de punta a punta originado por la detección | **Pendiente** |

**La mediana de 8,0 s de la sección 4 no aplica a este despliegue.** Aquí el tiempo hasta la acción está dominado por la cadencia de los timers (del orden de minutos), no por el cómputo; debe medirse de punta a punta sobre esta cadena.

### 8.2 · Detectores y respuesta

| Señal | Acción | Caducidad |
|---|---|---|
| Modelo: `score_samples < −0,568892` (Isolation Forest recalibrado) | **LIMIT** | 300 s, plano |
| Heurístico `brute_force` o `port_scan` | **BLOCK** | 300 s → 1800 s → 3600 s si reincide |
| Heurístico `http_abuse` o `dns_entropy` | **LIMIT** | 300 s, plano |
| Ninguna señal | **PERMIT** | — |

Por IP gana la acción más severa (BLOCK > LIMIT). Desde el tercer BLOCK se marca **revisión humana**; **nunca hay bloqueo infinito automático** y el contador decae a las 24 h sin reincidir (`scripts/engine/escalada.py`). La versión de los umbrales heurísticos se registra en el feed (`VERSION_UMBRALES` de `scripts/engine/heuristicos.py`). Una lista nunca-bloquear (gateways, DNS, sensor, bastión) protege la infraestructura.

### 8.3 · El umbral se recalibró en esta red

`calibrado_en_esta_red = true`. El detector es un Isolation Forest recalibrado con tráfico normal de esta red; su umbral se fijó con `alpha = 0,05` **sobre validación** y se evaluó una sola vez sobre **test normal retenido**: FPR **4,45 %** (65 421 ventanas). Sobre ataques reales de la Kali detectó **54/78 ventanas** (HTTP 27/27, escaneo 27/43, DNS 0/8). Detalle en [`MODEL_CARD_IF_RECALIBRADO.md`](MODEL_CARD_IF_RECALIBRADO.md).

> **La caída 92,4 % → 4,45 % no aísla el efecto de recalibrar.** El 92,4 % se midió con el OCSVM en los primeros minutos sobre la red real (92 decisiones en 7 ventanas, en su mayoría interfaces del cortafuegos emitiendo CARP) y **antes** de excluir el plano de control y deduplicar el espejo; el 4,45 % se midió con otro modelo, otros datos (línea base de ~70 h) y ese filtrado ya aplicado. Cambiaron a la vez modelo, datos y alcance: para atribuir la mejora a la recalibración habría que puntuar ambos modelos sobre el mismo conjunto retenido.

### 8.4 · Qué se excluye del cálculo, y por qué

| Exclusión | Motivo | Medido |
|---|---|---|
| Protocolos 112 (VRRP/CARP) y 240 (pfsync) | No son tráfico de usuarios: cada interfaz VLAN del cortafuegos emite un anuncio por segundo y pasaba a ser una entidad puntuada | **14 de 23** entidades eran eso. El **86,3 %** de las tramas de capa 2 del espejo |
| Copias que el espejo enseña dos veces | La sesión captura en los dos sentidos del troncal y la difusión inunda los dos puertos origen | `tcp_retransmission_ratio_10s` pasó de **0,1488 a 0,0000**: las 100 «retransmisiones» eran las 100 copias |
| El bastión y el propio sensor | Su SSH de gestión cruza el troncal espejado | Declaradas en `[red] excluir` |

Las tres actúan sobre la **entrada** del extractor congelado, nunca sobre sus fórmulas: son alcance, no modelo. El motor publica los contadores en cada decisión para que la exclusión sea una medición y no una afirmación.

### 8.5 · Lo que el punto de observación no puede ver

- **Tráfico dentro de una misma VLAN.** El espejo tiene origen en los troncales del cortafuegos, así que solo cruza por ahí lo que va **entre** VLAN. Una máquina que solo hable con vecinos de su segmento es invisible para las 28 variables.
- **Respuestas ARP completas.** Las peticiones son difusión y llegan enteras; las respuestas son unidifusión y solo llegan las dirigidas al cortafuegos.
- **Capas 5 y 6.** Sesión y presentación no son observables sin descifrar TLS, lo que exigiría interceptación. Es una decisión de alcance declarada, no un olvido.

El primer punto tiene un caso medido en producción: una máquina que emite **0,73 peticiones ARP por segundo** durante horas y **ni un solo paquete IP** que el espejo pueda atribuirle. Para las 28 variables es silencio absoluto. Ver [`../CASO-CAPA2-ARP.md`](../CASO-CAPA2-ARP.md).

### 8.6 · Lo que todavía no se ha medido en este despliegue

- **FPR del sistema completo** (modelo + heurísticos + enforcement) en operación: el 4,45 % es del modelo sobre test normal, no del sistema.
- **Disponibilidad** con el protocolo de F6: las «cero caídas en 58 corridas» son de la parte A.
- **Tiempo de punta a punta** hasta BLOCK automático originado por la detección.
- **DNS**: el ensayo de septiembre apuntó a un host que no era el resolver; el 0/8 no basta para concluir que el modelo falla en DNS.
