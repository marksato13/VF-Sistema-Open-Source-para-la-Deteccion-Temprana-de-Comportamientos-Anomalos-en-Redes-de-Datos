# Guía de instalación

Cómo poner CyberFlow a funcionar sobre una red real, de principio a fin.

Está escrita desde un despliegue real, no desde la teoría: cada tropiezo que
aparece aquí ocurrió de verdad y tiene su comprobación al lado.

---

## Antes de empezar: los dos modos

CyberFlow puede instalarse de dos formas, y **hay que elegir antes**, porque
cambian el cableado y lo que el sistema puede hacer.

| | **Observación (IDS)** | **Bloqueo (IPS)** |
|---|---|---|
| Dónde va el sensor | fuera del camino, recibe un espejo | **en el camino**, es el router |
| Qué hace | puntúa y registra | puntúa, registra **y corta** |
| `nftables` | no se toca | bloquea con expiración de 120 s |
| Riesgo | ninguno sobre la red | un falso positivo corta tráfico legítimo |
| `motor.modo` en la configuración | `"observacion"` | `"bloqueo"` |

> **El error más caro es elegir «bloqueo» con un espejo.** Con un puerto SPAN el
> sensor **observa pero no está en el camino del tráfico**: las reglas de
> `nftables` en esa máquina solo afectan a lo que entra y sale de ella misma. El
> motor decidiría bien y no cortaría nada, sin dar ningún error.

Si su sensor recibe un espejo, el modo es `observacion`. Punto.

---

## 1 · Requisitos

```
Linux con systemd            Ubuntu 24.04 y Debian 13 probados
Python 3.12 o superior       ver la nota sobre versiones al final
Suricata 7 u 8
tcpdump
nftables                     solo en modo bloqueo
2 interfaces de red          una de gestión, una de captura
4 vCPU y 8 GiB               medido: suficiente hasta ~200 Mb/s
40 GB de disco               los PCAP y eve.json crecen rápido
```

**Dos interfaces, ni una más.** Es un error de diseño frecuente dar al sensor
una pata en cada VLAN «para verlas todas». No funciona y es peligroso:

- **No da visibilidad.** Una pata en una VLAN solo ve su propio tráfico más el
  difundido. El unicast entre dos equipos cualesquiera no llega nunca.
- **Convierte al sensor en un puente que se salta el cortafuegos.** Con patas
  simultáneas en varios segmentos, la máquina es un camino entre ellos.

La respuesta a «quiero ver la VLAN X» es el espejo, no otra interfaz.

---

## 2 · Preparar el punto de captura

### 2.1 En el switch

Un espejo local (SPAN) del enlace por el que pasa el tráfico que quiere
observar. En un Catalyst:

```
monitor session 1 source interface Gi1/0/23 both
monitor session 1 destination interface Gi2/0/19 encapsulation replicate
```

**`encapsulation replicate` no es opcional**: conserva la etiqueta 802.1Q
original, y sin ella se pierde la distribución por VLAN.

Elija como origen **el enlace del cortafuegos**, no un puerto de acceso: si el
enrutamiento entre VLAN vive en el borde, todo el tráfico entre segmentos cruza
por ahí.

**Vuelta atrás, tres comandos:**

```
no monitor session 1
interface GigabitEthernet2/0/19
 shutdown
```

> Un puerto destino de SPAN **deja de reenviar tráfico normal**. No use uno que
> esté en servicio.

### 2.2 Vigile la capacidad del espejo

Espejar **ambos sentidos** de un enlace de 100 Mb/s hacia un destino de 100 Mb/s
puede superar la capacidad en los picos, y **el switch descarta en silencio**.
No aparece como error: aparece como paquetes que no llegan, y sesga todas las
variables de tasa.

```
show interfaces GigabitEthernet2/0/19 counters errors
```

**Si `OutDiscards` deja de ser 0, el dataset de esa sesión está contaminado.**
Compruébelo antes y después de cada captura y regístrelo: es evidencia.

### 2.3 Si el sensor es una máquina virtual

Este es el punto donde más gente se queda atascada. El switch envía, el sensor
no recibe, y no hay ningún error en ninguna parte.

En **VMware ESXi**, el grupo de puertos al que conecta la interfaz de captura
necesita los cuatro valores:

| Ajuste | Valor |
|---|---|
| Id. de VLAN | **4095** (todas las VLAN) |
| Modo promiscuo | **Aceptar** |
| Cambios de dirección MAC | **Aceptar** |
| Transmisiones falsificadas | **Aceptar** |

**Lo que manda es el ajuste del grupo de puertos, no el del vSwitch.** Ponerlo
en el vSwitch y no en el grupo de puertos es la causa más común del fallo.

Con `encapsulation replicate` las tramas llegan **etiquetadas**; un grupo de
puertos con una VLAN concreta descarta todo lo que venga de otra. De ahí el
4095.

En **Proxmox / KVM**, el equivalente es un puente sin filtrado de VLAN y la
interfaz en modo promiscuo.

---

## 3 · Preparar la interfaz de captura

```bash
ip -br link            # identifique la interfaz POR SU MAC, no por su nombre
```

> **Linux renumera las interfaces.** Al añadir o quitar un adaptador, lo que hoy
> es `ens37` puede no serlo mañana. Anote la MAC y compárela con la que muestra
> el hipervisor. Este proyecto ya perdió días por un desplazamiento de tarjetas.

La interfaz de captura **no debe tener dirección IP, ni IPv4 ni IPv6**, y no
debe pedir DHCP. Una sonda pasiva que emite no es pasiva.

```yaml
# /etc/netplan/50-cloud-init.yaml
    ens37:
      dhcp4: false
      dhcp6: false
      accept-ra: false
      link-local: []
      optional: true
```

```bash
sudo netplan generate && sudo netplan apply
```

> En Ubuntu, `cloud-init` puede regenerar ese fichero en cada arranque y
> deshacer el cambio. Si su instalación viene de `subiquity`, compruebe
> `/etc/cloud/cloud.cfg.d/90-installer-network.cfg` y desactive la gestión de
> red de cloud-init:
> ```bash
> echo 'network: {config: disabled}' | \
>   sudo tee /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
> ```

El resto —modo promiscuo, descargas de la NIC, IPv6— lo deja puesto la unidad
`cyberflow-capture-nic.service`, que se genera en el paso 6.

---

## 4 · Comprobar que llega el espejo

**No siga sin esto.** Instalar Suricata sobre una interfaz muda es perder el
tiempo.

```bash
sudo ip link set ens37 up promisc on
cat /sys/class/net/ens37/statistics/rx_packets; sleep 10
cat /sys/class/net/ens37/statistics/rx_packets
sudo tcpdump -i ens37 -e -nn -c 20
```

Tiene que cumplirse **todo**:

1. `rx_packets` **crece** de forma sostenida
2. `tcpdump -e` muestra **MAC de origen y destino**
3. aparecen **etiquetas `vlan N`** *(o queda registrado que no, y por qué)*
4. `OutDiscards` del puerto del switch **sigue en 0**

### Si `rx_packets` no crece

Por orden de probabilidad:

| Causa | Comprobación |
|---|---|
| Grupo de puertos sin VLAN 4095 | paso 2.3 |
| Grupo de puertos sin modo promiscuo | paso 2.3 |
| Interfaz del invitado sin promiscuo | `ip -d link show ens37 \| grep promisc` |
| La vNIC no está en ese grupo de puertos | mire la configuración de la VM |
| El switch no está espejando | `show monitor session all` |

> `promiscuity 0` mientras `tcpdump` **no** está corriendo es normal: `tcpdump`
> lo activa él mismo. No es síntoma de nada.

### Si aparecen tramas pero sin etiqueta `vlan N`

No es catastrófico. Las demás variables de capa 2 —MAC, ARP, EtherType, tamaño
de trama— siguen siendo viables; solo la distribución por VLAN se queda sin
fuente. Anótelo y siga.

---

## 5 · Suricata

```bash
sudo apt-get install -y suricata
sudo cp /etc/suricata/suricata.yaml /etc/suricata/suricata.yaml.orig
```

Tres cambios en `/etc/suricata/suricata.yaml`:

```yaml
vars:
  address-groups:
    HOME_NET: "[10.10.0.0/16]"      # sus redes reales

af-packet:
  - interface: ens37                # su interfaz de captura
    checksum-checks: no             # ver abajo
```

**`checksum-checks: no` importa.** En tráfico espejado las sumas de verificación
vienen calculadas por la NIC del emisor y llegan inválidas; validarlas
descartaría paquetes buenos.

```bash
sudo suricata -T -c /etc/suricata/suricata.yaml -v   # tiene que pasar limpio
sudo systemctl enable --now suricata
wc -l /var/log/suricata/eve.json; sleep 60; wc -l /var/log/suricata/eve.json
```

El fichero tiene que **crecer** y contener direcciones de su red.

> El paquete de Ubuntu trae `/etc/default/suricata` con `RUN=no`,
> `LISTENMODE=nfqueue` e `IFACE=eth0`. **La unidad de systemd no lo lee.**
> Es un fichero vestigial que induce a error; no lo toque.

### Ponga un tope a los registros

`eve.json` puede llenar la raíz en una ráfaga, y un `/` lleno tumba la máquina
entera, incluido el acceso por SSH. El `logrotate` del paquete **no trae ni
frecuencia ni límite de tamaño**:

```
# /etc/logrotate.d/suricata
        daily
        maxsize 500M
        rotate 7
```

---

## 6 · Instalar CyberFlow

> **La vía corta.** Si los pasos 1 a 5 están hechos, todo lo que sigue lo hace
> un comando, y antes se diagnostica solo:
> ```bash
> sudo bash scripts/setup/instalar.sh --comprobar
> sudo bash scripts/setup/instalar.sh
> ```
> El resto de esta sección explica qué hace por dentro, por si prefiere ir a
> mano o algo falla.


```bash
git clone <este-repositorio> cyberflow && cd cyberflow
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-model.txt
```

> Si `python3 -m venv` falla con *«No module named pip»*, instale
> `python3-venv`. En una máquina sin salida a Internet, vea el anexo A.

**Compruebe que los artefactos son los publicados:**

```bash
sha256sum -c docs/dataset/SHA256SUMS
```

Si un solo hash no cuadra, pare.

**Configure.** Todo lo que cambia entre instalaciones vive en un fichero:

```bash
cp configs/cyberflow.toml configs/cyberflow.local.toml
$EDITOR configs/cyberflow.local.toml
```

Lo mínimo: `captura.interfaz`, `red.red_entidades`, `rutas.usuario`,
`rutas.raiz` y `motor.modo`. Ver [CONFIGURACION.md](CONFIGURACION.md).

**Valide antes de escribir nada:**

```bash
python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --comprobar
python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --mostrar
```

**Genere e instale las unidades:**

```bash
sudo python3 scripts/setup/cyberflow_config.py --config configs/cyberflow.local.toml --escribir
sudo systemctl daemon-reload
sudo systemctl enable --now cyberflow-capture-nic ppi-motor-capture ppi-motor
```

Guarda una copia `.anterior` de cada unidad que sobrescribe.

---

## 7 · Comprobar que funciona

```bash
systemctl is-active cyberflow-capture-nic ppi-motor-capture ppi-motor
ls -la /var/lib/ppi-motor-capture/          # ficheros live-*.pcap rotando
tail -f logs/motor_decision.log             # decisiones, una por línea JSON
```

Una decisión tiene esta forma:

```json
{"decision":"PERMIT","entity_ip":"10.10.40.10","score":2.41,
 "threshold":1.8126,"packet_count_10s":184,"window_end_utc":"..."}
```

En modo bloqueo, además:

```bash
sudo nft list set inet ppi_enforce bloqueadas
```

---

## 8 · Recalibre. No se salte este paso

**El modelo publicado está entrenado con tráfico de un laboratorio concreto.**
En otra red, lo que allí era normal aquí puede no serlo.

Medición real de un despliegue sobre una red distinta, **sin ningún ataque en
curso**:

```
decisiones : 92 en 7 ventanas
  ALERT     85    92,4 %
  PERMIT     7     7,6 %
```

Las entidades señaladas eran las interfaces del propio cortafuegos emitiendo
sus anuncios CARP. **El 92,4 % eran falsos positivos.**

No es un defecto del motor: es lo que pasa cuando se aplica un umbral calibrado
en otro sitio. Recalibre con tráfico normal **de su red**:

```bash
python3 scripts/features/extract_multilayer_v2.py --help
python3 scripts/modeling/calibrate_multilayer_v2_v1.py --help
```

Use solo datos de validación para fijar el umbral, nunca los de prueba.

> **Y antes de recalibrar, asegúrese de tener tráfico que merezca llamarse
> línea base.** En una red sin usuarios, el 87 % de lo que ve el sensor es plano
> de control —STP, CARP, pfsync— y el modelo aprendería que lo normal es el
> latido de los switches.

---

## Anexo A · Instalar sin salida a Internet

Un sensor sin salida a Internet es una buena postura de seguridad, y es
compatible con instalarlo. Dos vías.

**Paquetes del sistema**, con un túnel desde una máquina que sí tenga salida:

```bash
# desde el bastión, el túnel vive solo mientras dura el comando
ssh -R 18080:archive.ubuntu.com:80 -R 18081:security.ubuntu.com:80 \
    usuario@sensor "sudo apt-get update && sudo apt-get install -y suricata"
```

Apuntando temporalmente `/etc/apt/sources.list.d/ubuntu.sources` a
`http://127.0.0.1:18080/ubuntu/`.

> Use `archive.ubuntu.com`, no un espejo nacional: los espejos con
> *virtual host* rechazan la petición porque la cabecera `Host` pasa a ser
> `127.0.0.1:18080`.

**Dependencias de Python**, descargándolas donde haya red:

```bash
pip download --platform manylinux2014_x86_64 --python-version 3.12 \
    --only-binary=:all: --implementation cp \
    -r requirements-model.txt -d ruedas
# transfiera la carpeta y luego, en el sensor:
.venv/bin/python -m pip install --no-index --find-links ruedas -r requirements-model.txt
```

---

## Anexo B · La versión de Python importa, y más de lo que parece

`requirements-model.txt` fija CPython **3.14.4**. No es una formalidad ni una
preferencia: es un requisito medido.

### Lo que pasa si lo baja a 3.12

Para Python 3.12 no existe ninguna de las versiones fijadas:

| Fijado | Máximo para cp312 |
|---|---|
| `numpy==2.5.1` | 2.2.6 |
| `scikit-learn==1.9.0` | 1.7.2 |
| `scipy==1.18.0` | 1.16.3 |

El modelo **carga igual** con las versiones disponibles, y scikit-learn avisa:

```
Trying to unpickle estimator OneClassSVM from version 1.9.0 when using
version 1.7.2. This might lead to breaking code or invalid results.
```

Eso es lo visible. **Lo que no se ve es peor.**

### El fallo silencioso

Se recalibró el protocolo completo bajo 3.12 para comprobarlo. El OCSVM
desplegado conservó su resultado —158/179— y su umbral, y el LOF también. Los
otros cinco detectores cambiaron de umbral, aunque tres mantuvieron el mismo
número de detecciones, y **ningún modelo salió con el mismo hash**. Dos ramas
de Isolation Forest cambiaron incluso el resultado:

```
if_primary_weighted   97/179  ->  103/179
if_scaled_weighted    97/179  ->  103/179
```

Y el umbral del modelo ponderado pasó a ser **idéntico** al del no ponderado:

```
if_primary_weighted   antes -0.50606563   ahora -0.55456155
if_exact_collapsed    (sin ponderar)      ahora -0.55456155
```

La causa, comprobada directamente:

```python
>>> import sklearn; sklearn.__version__
'1.7.2'
>>> inspect.signature(IsolationForest.fit)
(self, X, y=None, sample_weight=None)
>>> # 300 filas, peso 20x en las primeras 50
>>> abs(sin_peso - con_peso).max()
0.0
```

**`IsolationForest.fit` acepta `sample_weight`, no avisa, no falla, y lo
ignora.** El protocolo de calibración pondera cada fila por
`1/filas_por_episodio` para corregir un desbalance medido —5 de 132 episodios
concentran el 31,7 % de las filas de entrenamiento—, y bajo 1.7.2 esa
corrección sencillamente no ocurre.

El resultado sigue saliendo. Los números siguen siendo plausibles. Nada indica
que la ponderación se haya perdido.

### Qué hacer

- **Para desplegar y ver el sistema funcionando**, 3.12 sirve. El OCSVM, que es
  lo que corre el motor, reproduce exacto.
- **Para calibrar, reentrenar o publicar cualquier cifra**, use 3.14.4. El
  guardarraíl `EXPECTED_PYTHON` del script de calibración se lo va a exigir, y
  está ahí por esto.
- Si cambia de entorno, **no se fíe de que los números salgan**: compruebe que
  salen *los mismos*. Un parámetro ignorado en silencio no se detecta de
  ninguna otra forma.

### Instalar CPython 3.14.4

Ubuntu 24.04 solo trae 3.12, y el PPA *deadsnakes* publica 3.14.6 — que el
guardarraíl rechaza, porque compara la versión completa. Hay que compilarla:

```bash
sudo apt-get install -y build-essential zlib1g-dev libssl-dev libffi-dev     libbz2-dev liblzma-dev libsqlite3-dev libreadline-dev libncurses-dev     uuid-dev libgdbm-dev pkg-config

curl -LO https://www.python.org/ftp/python/3.14.4/Python-3.14.4.tgz
tar xzf Python-3.14.4.tgz && cd Python-3.14.4
./configure --prefix=/opt/python3.14 --with-ensurepip=install
make -j"$(nproc)"
sudo make altinstall          # altinstall: no toca el python3 del sistema
```

Unos diez minutos en 4 vCPU. Después:

```bash
/opt/python3.14/bin/python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-model.txt
```

> En una máquina sin salida a Internet, descargue el `.tgz` y las ruedas de
> `cp314` donde haya red y transfiéralos. Ver el anexo A.

### Verificado

El protocolo completo se reejecutó sobre un CPython 3.14.4 recién compilado, en
una máquina distinta y con otra versión de glibc (2.39 frente a 2.43). Los
siete detectores reprodujeron su resultado y su umbral **hasta el último
decimal**, y los siete modelos salieron con **hash idéntico**:

```
if_primary_weighted   97/179 ->  97/179   umbral -0.506065635 -> -0.506065635
ocsvm_scaled         158/179 -> 158/179   umbral +1.812608794 -> +1.812608794
REPRODUCCION EXACTA DEL PROTOCOLO: SI
```

Con el entorno correcto, lo publicado se reproduce. Con el entorno equivocado,
casi — y ese *casi* es el problema.
