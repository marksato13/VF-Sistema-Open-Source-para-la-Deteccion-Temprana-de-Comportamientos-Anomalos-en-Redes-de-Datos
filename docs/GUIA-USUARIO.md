# Guía de usuario

Para quien ya tiene CyberFlow instalado y necesita usarlo, entenderlo y saber
cuándo no fiarse de él.

Si aún no está instalado, vaya a [INSTALACION.md](INSTALACION.md).

---

## Qué hace, en una frase

Cada 10 segundos agrupa el tráfico por IP, calcula 28 variables de las capas 3,
4 y 7, y puntúa cada IP con un modelo **no supervisado**. Si la puntuación baja
del umbral, la marca como anómala — y, en modo bloqueo, corta esa IP durante
120 segundos.

**No supervisado** significa que aprendió de tráfico normal, sin ejemplos
etiquetados de cada ataque. Por eso puede señalar comportamientos que nadie le
enseñó. Y por eso **señala también cosas que son simplemente distintas, sin ser
un ataque**.

---

## El día a día

### Ver qué está decidiendo

```bash
tail -f logs/motor_decision.log
journalctl -u ppi-motor.service -f
```

Cada decisión es una línea JSON:

```json
{"decision":"PERMIT","entity_ip":"10.10.40.10","score":2.41,
 "threshold":1.8126,"packet_count_10s":184,
 "history_coverage_s":230.0,"window_end_utc":"2026-09-17T19:46:20+00:00"}
```

| Campo | Qué significa |
|---|---|
| `decision` | `PERMIT` normal · `ALERT` anómala |
| `entity_ip` | La IP evaluada en esa ventana |
| `score` | Puntuación del modelo. **Más bajo = más anómalo** |
| `threshold` | El umbral. Sale del manifiesto, no está escrito en el código |
| `packet_count_10s` | Paquetes de esa IP en la ventana |
| `history_coverage_s` | Cuánta historia tenía el motor. Si es baja, desconfíe |

### Comprobar la salud

```bash
systemctl is-active cyberflow-capture-nic ppi-motor-capture ppi-motor suricata
ls -la /var/lib/ppi-motor-capture/          # los live-*.pcap deben rotar
cat /sys/class/net/<interfaz>/statistics/rx_packets   # debe crecer
```

**La métrica que de verdad importa**, porque la pérdida de captura no da error:

```bash
grep '"event_type":"stats"' /var/log/suricata/eve.json | tail -1 | \
  python3 -c "import sys,json; c=json.load(sys.stdin)['stats']['capture']; print(c)"
```

`kernel_drops` tiene que ser **0**. Si no lo es, está perdiendo paquetes y
cualquier medición de ese periodo está sesgada.

### El panel

Escucha solo en loopback. Desde otra máquina:

```bash
ssh -L 8788:127.0.0.1:8788 usuario@sensor
# y abra http://127.0.0.1:8788
```

Es de **solo lectura**: no ejecuta ninguna acción.

### Desbloquear una IP antes de tiempo

Solo en modo bloqueo:

```bash
sudo nft list set inet ppi_enforce bloqueadas
sudo nft delete element inet ppi_enforce bloqueadas { 10.10.20.15 }
```

### Cambiar algo de la configuración

Nunca edite las unidades de systemd: se regeneran. Edite el `.toml`:

```bash
$EDITOR configs/cyberflow.local.toml
python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --comprobar
sudo python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --escribir
sudo systemctl daemon-reload && sudo systemctl restart ppi-motor
```

---

## Cuándo NO fiarse

Tres limitaciones **medidas**, no estimadas.

### 1 · El falso positivo sube mucho fuera del laboratorio

| Escenario | Falsos positivos |
|---|---|
| Laboratorio, con el umbral calibrado allí | 4,71 % |
| Campaña real, mismo umbral | 25,81 % y 22,97 % |
| **Red distinta, sin recalibrar** | **92,4 %** |

Ese último caso es real: un despliegue sobre otra red marcó como anómalas el
92,4 % de las ventanas **sin ningún ataque en curso**. Las entidades señaladas
eran las interfaces del propio cortafuegos emitiendo sus anuncios CARP.

Un `iperf` legítimo a 200 Mbit/s llegó a bloquear al cliente.

> **Si no ha recalibrado con tráfico de su red, trate cada ALERT como ruido.**

### 2 · Se atrasa bajo carga sostenida

Hasta 161 s de retraso medidos, porque reparsea el anillo de PCAP. Un bloqueo
que llega 161 segundos tarde se aplica sobre tráfico que ya pasó.

### 3 · Una de las 28 variables no es observable

`tls_handshake_failure_ratio_60s` está definida pero no se mide en esta
configuración y queda constante. **Son 27 efectivas y 1 no observable.** Las
otras 27 tienen variación.

---

## Lo que el sistema NO ve

Saber esto evita conclusiones falsas.

- **Capas 1, 2, 5 y 6.** Las variables cubren las capas 3, 4 y 7. No analiza
  MAC, ARP, VLAN ni tramas Ethernet, así que **no puede afirmarse que detecte
  ataques de capa 2**.
- **El tráfico que no cruza el punto de captura.** Si el espejo está en el
  enlace del cortafuegos, ve lo que pasa *entre* segmentos, no lo que se queda
  dentro de uno. Dos equipos de la misma VLAN hablando entre sí son invisibles.
- **El contenido cifrado.** TLS se registra, no se descifra.

---

## Resolución de problemas

| Síntoma | Causa más probable | Comprobación |
|---|---|---|
| `rx_packets` no crece | Grupo de puertos del hipervisor sin VLAN 4095 o sin promiscuo | [INSTALACION.md §2.3](INSTALACION.md) |
| El anillo de PCAP está vacío | `filtro_bpf` de capa 3 sin `vlan` sobre tráfico etiquetado | [CONFIGURACION.md](CONFIGURACION.md) |
| Todo sale `ALERT` | Umbral de otra red, o ventanas casi vacías | Recalibrar |
| `score` siempre `0.0` | Ventanas con 1 o 2 paquetes | No hay tráfico que analizar |
| El motor no arranca | Rutas del `.toml`, o el modelo no carga | `--comprobar`, y `journalctl -u ppi-motor` |
| Avisos al cargar el modelo | Versión de scikit-learn distinta a la del manifiesto | [INSTALACION.md, anexo B](INSTALACION.md) |
| `kernel_drops` > 0 | El sensor no da abasto, o el espejo satura | Bajar el caudal o subir recursos |
| `OutDiscards` > 0 en el switch | El espejo supera la capacidad del puerto destino | Enlace de 1 Gb en el destino |
| El bloqueo no corta nada | Modo `bloqueo` con un sensor que solo observa | El sensor tiene que estar **en el camino** |

---

## Para publicar resultados

Si va a reportar cifras en un trabajo académico:

1. **Registre `OutDiscards` y `kernel_drops`** antes y después de cada captura.
   Si no son 0, ese periodo está contaminado y hay que descartarlo.
2. **Use la versión de Python del manifiesto**, o recongele y publique el
   manifiesto nuevo. Ver el anexo B de la guía de instalación.
3. **Declare el punto de observación** y lo que implica: un espejo en el enlace
   del cortafuegos no ve el tráfico intra-VLAN.
4. **Separe el origen de los datos del origen de los ataques.** No es lo mismo
   tráfico real con ataques simulados que un conjunto de datos sintético, y hay
   que decir cuál es cuál.
5. **Fije la versión del conjunto de reglas de Suricata** si las usa. Un
   ruleset que se actualiza solo entre dos experimentos rompe la
   reproducibilidad sin avisar.
