# Registro de cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Cada entrada dice qué cambió y **con qué se midió**, no solo qué se tocó.

## Sin publicar

### Corregido

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
