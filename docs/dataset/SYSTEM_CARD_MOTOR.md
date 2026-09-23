# System card — motor de decisión y control en línea

> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, desde `results/f6/*.jsonl`.

Responde por **el sistema desplegado**: qué decide, qué acción ejerce y cómo se comporta en operación. El modelo está en [`MODEL_CARD_OCSVM.md`](MODEL_CARD_OCSVM.md) y los datos en [`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md).

---

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

> **Esto describe el despliegue que se evaluó**, no necesariamente el que está corriendo hoy. Las cifras de las secciones 4 y 7 se midieron con el sensor en el camino del tráfico. La sección 8 declara en qué difiere el despliegue actual y qué deja de valer por ello.

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

## 3 · Acción de control

| | |
|---|---|
| **Mecanismo** | `nftables` en VM02, vía el ayudante versionado `ppi-enforce` |
| **Alcance** | La IP ofensora de la red de clientes |
| **Duración** | **120 s**, con expiración nativa del conjunto |
| **Reversión** | Automática al expirar; no requiere intervención |
| **Lista blanca** | Direcciones de infraestructura, nunca bloqueables |

**No hay nivel intermedio.** La respuesta es binaria: permitir o bloquear. Un nivel de limitación de caudal exigiría un segundo umbral calibrado, y **inventar ese número sería peor que no tenerlo**.

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

> **Precisión sobre la disponibilidad.** No se registró **ninguna** caída de servicio, pero 3 corridas no tienen medición de servicios. Lo correcto es decir «cero caídas registradas», no «100 % de disponibilidad verificada»: son afirmaciones distintas.

### El resultado incómodo

> **17 de 74 ventanas de tráfico legítimo se marcaron como anómalas: 22,97 %.**

Intervalo de Wilson descriptivo al 95 %: **[14,9 – 33,7]**. El falso positivo medido en evaluación bloqueada fue **4,71 %** [2,8 – 7,9]. Las ventanas están agrupadas por corrida y comparten historia de hasta 60 s; por eso el no solapamiento de estos intervalos por ventana **no demuestra por sí solo** una diferencia inferencial.

De las 12 corridas benignas del pase 2, **5 terminaron bloqueando al cliente legítimo.**

> Quedan fuera de este cálculo las 2 corridas `H*`, que prueban a propósito la **frontera del heurístico de autenticación**: ahí la alerta es el comportamiento buscado, no un falso positivo. Incluirlas subiría la cifra sin que signifique lo mismo.

El pase 1, medido por separado pero contaminado por atraso, dio **25,81 %** [16,6 – 37,9] sobre 62 ventanas. Ambos pases comparten infraestructura y no son réplicas estadísticamente independientes.

La documentación de F6 describe una reproducción **en aislamiento**, sin otro tráfico compitiendo: una transferencia `iperf-tcp` legítima de 200 Mbit/s puntuó **1,689** frente al umbral 1,8126 y cortó al cliente durante 120 s. Otra ventana pasó por **0,0014**.

> **Límite de trazabilidad.** Los scores, PCAP y registro de bloqueo de esa prueba aislada no están versionados en `results/f6/*.jsonl`; estas cifras proceden de `docs/fase07-validacion-final/02-resultados-f6.md` y no pueden regenerarse desde los artefactos publicados.

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

## 6 · Salvaguardas

- **Lista blanca** de infraestructura, imposible de bloquear.
- **Expiración nativa a los 120 s**: ningún bloqueo es permanente, así que un falso positivo se corrige solo.
- **Sin sudo general**: el motor solo puede invocar el ayudante `ppi-enforce`, con argumentos acotados.
- **El panel es de solo lectura**: observa, no ejerce ninguna acción.
- **El motor reutiliza el extractor congelado**, así que las variables de producción son por construcción las mismas del entrenamiento.

---

## 7 · Veredicto

**Demostrado con evidencia:** detectar comportamiento anómalo y **ejercer control en línea real** sobre una red enrutada, con bloqueo en una mediana de 8 s y sin ninguna caída de servicio registrada.

**No demostrado:** hacerlo con una tasa de falso positivo aceptable sobre tráfico legítimo pesado. En esa condición el sistema **todavía no es apto para operación desatendida**.

Delimitar esa frontera con medición es el resultado, no un defecto del informe.

---

## 8 · El despliegue actual difiere del evaluado

La evaluación de F6 se hizo con el sensor **en el camino del tráfico**. El despliegue en la red de la entidad usa un **espejo SPAN**, y eso cambia cuatro cosas que hay que declarar antes de leer cualquier cifra.

### 8.1 · El control es demostrativo, no efectivo

Con un espejo, el sensor **no está en el camino**: recibe una copia. La regla nftables se escribe igual, pero el paquete ya pasó por otro sitio. Por eso el motor corre en `modo = "observacion"`. **La mediana de 8,0 s hasta el bloqueo de la sección 4 no aplica a este despliegue**: mide una acción que aquí no corta nada.

### 8.2 · El umbral viene de otra red

`calibrado_en_esta_red = false`. El umbral de la model card se calibró sobre un conjunto de otra red, así que las alertas de este despliegue deben tratarse como ruido hasta recalibrar con tráfico propio. El panel lo advierte en cada carga.

### 8.3 · Qué se excluye del cálculo, y por qué

| Exclusión | Motivo | Medido |
|---|---|---|
| Protocolos 112 (VRRP/CARP) y 240 (pfsync) | No son tráfico de usuarios: cada interfaz VLAN del cortafuegos emite un anuncio por segundo y pasaba a ser una entidad puntuada | **14 de 23** entidades eran eso. El **86,3 %** de las tramas de capa 2 del espejo |
| Copias que el espejo enseña dos veces | La sesión captura en los dos sentidos del troncal y la difusión inunda los dos puertos origen | `tcp_retransmission_ratio_10s` pasó de **0,1488 a 0,0000**: las 100 «retransmisiones» eran las 100 copias |
| El bastión y el propio sensor | Su SSH de gestión cruza el troncal espejado | Declaradas en `[red] excluir` |

Las tres actúan sobre la **entrada** del extractor congelado, nunca sobre sus fórmulas: son alcance, no modelo. El motor publica los contadores en cada decisión para que la exclusión sea una medición y no una afirmación.

### 8.4 · Lo que el punto de observación no puede ver

- **Tráfico dentro de una misma VLAN.** El espejo tiene origen en los troncales del cortafuegos, así que solo cruza por ahí lo que va **entre** VLAN. Una máquina que solo hable con vecinos de su segmento es invisible para las 28 variables.
- **Respuestas ARP completas.** Las peticiones son difusión y llegan enteras; las respuestas son unidifusión y solo llegan las dirigidas al cortafuegos.
- **Capas 5 y 6.** Sesión y presentación no son observables sin descifrar TLS, lo que exigiría interceptación. Es una decisión de alcance declarada, no un olvido.

El primer punto tiene un caso medido en producción: una máquina que emite **0,73 peticiones ARP por segundo** durante horas y **ni un solo paquete IP** que el espejo pueda atribuirle. Para las 28 variables es silencio absoluto. Ver [`../CASO-CAPA2-ARP.md`](../CASO-CAPA2-ARP.md).
