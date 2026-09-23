# Banco de pruebas — aprovisionamiento

Qué máquinas hacen falta para generar la línea base, con qué recursos y por qué
ese número. **Esto no es el producto**: es el aparato experimental.

Procedencia de cada dato: *medido* = salida de un comando en esta red;
*documentado* = respaldo de configuración del CORE-STACK; *calculado* = cuenta
sobre `clientes_lab.py`; *sin verificar* = no se ha comprobado todavía.

---

## 1. Por dónde ve el sensor

```
monitor session 1 source interface Gi1/0/23
monitor session 1 destination interface Gi2/0/19 encapsulation replicate
```
*(verificado en `show running-config`, 2026-09-22)*

Sin palabra de dirección, IOS toma `both` —rx y tx—, que es lo que hace que el
tráfico entre VLAN se copie dos veces (§3). Confirmar con `show monitor session 1`.

**El CORE no enruta entre VLAN.** La única SVI con dirección es `Vlan99`
(10.10.99.10); `Vlan1` está sin dirección y apagada. Con una sola interfaz de
capa 3 no hay entre qué enrutar, así que **todo el tráfico entre VLAN sube a
pfSense y pasa por el espejo**. Eso es lo que hace viable el banco de pruebas:
no depende de dónde se enchufe el generador, sino de que su tráfico sea *entre
VLAN*.

**Presupuesto del espejo: 100 Mb/s.** Origen y destino negocian ambos a 100 Mb/s
*(documentado)*. Es el techo de todo lo que se genere.

### ~~Punto ciego: el espejo cuelga de un solo enlace de pfSense~~ — cerrado 2026-09-22

```
Source Ports :
    Both     : Gi1/0/23,Gi2/0/23
Destination Ports : Gi2/0/19
    Encapsulation : Replicate
```

Guardado con `wr`. De paso queda **verificado** que la sesión captura en los dos
sentidos (`Both`), que es lo que sostiene el análisis de duplicación del §3.
Queda el porqué:

pfSense A y B son una pareja CARP con un troncal cada uno:

| Puerto | Descripción en el equipo | A dónde va de verdad |
|---|---|---|
| `Gi1/0/23` | `HV-EDGE-B-PFSENSE-LAN-TRUNK` | **pfSense-A**, el MASTER |
| `Gi2/0/23` | `HV-EDGE-A-PFSENSE-LAN-TRUNK` | pfSense-B, el BACKUP |

Las descripciones **están cruzadas** *(documentado, probado con la tabla MAC)*.
La sesión SPAN escucha `Gi1/0/23`, que hoy es el MASTER: correcto.

**Si CARP conmuta a B durante las 72 h, el sensor se queda ciego y no avisa.**
El registro del motor seguiría escribiendo, con las entidades desaparecidas: un
hueco en la línea base que solo se detecta después, al analizar los datos.

Arreglo, **un comando, pendiente de aprobación**:

```
configure terminal
monitor session 1 source interface Gi1/0/23 , Gi2/0/23
end
show monitor session 1
```

Cuesta casi nada: el BACKUP no enruta, solo emite CARP y `pfsync`, y esos dos
protocolos (112 y 240) ya están excluidos en `[red] excluir_protocolos`. A
cambio, la captura sobrevive a una conmutación.

---

## 2. La VLAN 20 ya llega a HV-DATA — resuelto

```
interface GigabitEthernet1/0/20    description HV-DATA-NIC2-TRUNK
interface GigabitEthernet2/0/20    description HV-DATA-NIC1-TRUNK
 switchport trunk native vlan 999
 switchport trunk allowed vlan 20,50,99
```
*(verificado en `show running-config`, 2026-09-22)*

Los **dos** puertos la llevan, que es lo que importa: son las dos NIC del mismo
anfitrión en dos miembros distintos del stack, y con la VLAN en uno solo
funcionaría hasta que ESXi conmutase de uplink. La 50 y la 99 siguen en la
lista: el `add` se aplicó bien. `Gi1/0/23` permite
`10,20,30,40,50,60,70,80,85,88,90,95,99,100`, así que hacia pfSense no hay nada
que tocar.

### 🔴 Pero HV-DATA no tiene enlace

```
Gi1/0/20  HV-DATA-NIC2-TRUNK  notconnect  trunk  auto  auto  10/100/1000BaseTX
Gi2/0/20  HV-DATA-NIC1-TRUNK  notconnect  trunk  auto  auto  10/100/1000BaseTX
```
*(medido 2026-09-22)*

**Las dos NIC.** El troncal está bien configurado y el puerto no está apagado:
simplemente no hay nada al otro lado. Cable ausente o muerto, hipervisor
apagado, o HV-DATA conectado a otro switch. Sin `connected` no hay VM que valga.

No es la primera vez: `RA-8` — *«HV-ID-FILE desconectado del core»* — se cerró
el 2026-09-03 recableando, y `RA-11` fue lo mismo en HIPERVISOR 4. **El patrón
es que la configuración se aplica a puertos antes de que exista el cable.**

Mientras no haya enlace, el anfitrión del banco de pruebas está sin decidir:

| Anfitrión | VLAN 20 | Enlace | Objeción |
|---|---|---|---|
| **HV-DATA** `172.17.25.3` | sí | ❌ `notconnect` | Es el sitio correcto. Requiere acceso físico |
| **HIPERVISOR 3 – ID-FILE** `172.17.25.7` | no (`Gi x/0/21` = 10,30,40,99) | ✅ probado a 1 Gbps | Un `add 20`. Aloja DC1 y el bastión |
| **HIPERVISOR 4 – SIEM** `172.17.25.2` | sí (`Gi x/0/22` = 10,20,30,60,99) | ✅ 779,6 Mbps medidos | Lleva la VLAN 60: **es probablemente el anfitrión del propio sensor** *(sin verificar)* |

Sobre el tercero: que el generador y el sensor compartan anfitrión **no** falsea
la medición —el tráfico sale por la NIC física, cruza el core, sube a pfSense y
vuelve por `Gi2/0/19`, un puerto distinto—, pero sí compiten por CPU. Si el
generador le roba ciclos a Suricata, la línea base sale con agujeros. Eso se
mide, no se supone: `capture.kernel_drops` en las estadísticas de Suricata.

**Por qué no se usa la VLAN 50, que también llega:** VLAN 50 es `DATOS`, las
bases de datos de producción (VM-ERP-DB-A/B). Tráfico sintético y un atacante
ahí es inaceptable. La alternativa sin tocar nada sería HV-SIEM (`Gi x/0/22`
permite `10,20,30,60,99`), pero pone el generador en el mismo anfitrión que el
sensor: compiten por recursos y se mezcla lo que mide con lo que genera.

---

## 3. Carga que va a generar *(calculado desde `clientes_lab.py`)*

| Perfil | acciones/s | KB/acción | kbit/s |
|---|---:|---:|---:|
| `navegacion` | 0,67 | 405,3 | 2 162 |
| `descargas` | 0,12 | 1 472,1 | 1 472 |
| `erratico` | 0,20 | 365,4 | 585 |
| `ofimatica` | 0,33 | 25,2 | 67 |
| `aplicacion` | 0,50 | 2,4 | 9 |
| `ligero` | 0,08 | 1,6 | 1 |
| **TOTAL** | **1,91** | | **4,30 Mbit/s** |

En 72 h con la curva diaria: **272 000 acciones**, **≈77 GB** por la red,
**25 920 ventanas** de 10 s.

### Duplicación en el espejo — el efecto que hay que medir primero

El origen del SPAN es un puerto con `both`. Un paquete de `clientes` (VLAN 20) a
`srv-dmz` (VLAN 30) **entra** a pfSense etiquetado 20 y **sale** etiquetado 30:
el espejo lo copia **dos veces**.

En el tráfico real eso afectaba al 4,8 % *(medido)*, porque casi todo va a
Internet y solo cruza el troncal una vez. Pero **el 100 % del tráfico sintético
es entre VLAN**, así que su duplicación esperada es del 100 %.

- Consumo real del espejo: **8,6 Mbit/s**, el 8,6 % del presupuesto. Sin riesgo.
- **Techo práctico: `--factor 3`** (≈26 Mb/s espejados). Por encima, el destino
  a 100 Mb/s empieza a descartar y la línea base sale con agujeros.
- Las tasas de paquetes y bytes de estas 6 entidades saldrán al doble. Como el
  modelo se *entrena* y se *evalúa* sobre lo mismo, es coherente; pero los
  rasgos de separación entre paquetes verán dos copias a microsegundos, y eso sí
  deforma su distribución.

**Antes de las 72 h hay que medirlo, no suponerlo:**

```bash
sudo tcpdump -i ens37 -nn -e -c 200 'host 10.10.20.21 and port 80' | \
  grep -c 'vlan 20'   # frente a 'vlan 30': si salen parejos, duplicación confirmada
```

---

## 4. Máquinas

### `clientes`

| | Valor | Por qué |
|---|---|---|
| Anfitrión | creada 2026-09-23 | |
| Sistema | Ubuntu 24.04.2 LTS | *medido*. Desktop emitiría tráfico de fondo no controlado; **falta confirmar que es Server** |
| Hostname | `clientesadmin` | *medido*. Se propuso `LAB-CLIENTES`; es cosmético, no se cambia |
| Interfaz | **`ens34`** | *medido*. No `ens160`: el netplan de §6 va con este nombre |
| Disco | 13,16 GB, 35,3 % usado | *medido*. Se pidieron 20 GB; con ~8,5 GB libres **basta** y no se toca |
| vCPU | **2** | No es caudal, es determinismo: con 1 vCPU, mientras `descargas` lee un cuerpo de 4 MB los otros 5 procesos esperan, y los intervalos entre acciones se alargan. La línea base describiría al planificador del hipervisor, no al modelo de tráfico |
| RAM | **2 GB** | 6 CPython con `ssl`+`http.client` ≈ 30 MB cada uno + Ubuntu Server en reposo ≈ 500 MB → **≈0,7 GB** *(estimado, sin verificar)*. 4 GB solo si se va a subir `--factor` |
| Disco | **20 GB** | Ubuntu Server mínimo ≈ 3 GB. No almacena tráfico: lo emite. Lo único que crece es el journal (272 000 líneas ≈ 30 MB) |
| Port group | `PG-VLAN20-CLIENTES`, VLAN ID **20** | No hace falta NIC extra: el troncal ya trae la VLAN etiquetada |
| Encendida | siempre | Es la línea base |

### `atacante`

| | Valor | Por qué |
|---|---|---|
| Anfitrión | el mismo que `clientes` | |
| Sistema | Kali (XFCE) | El escritorio aquí sí vale: solo está encendida durante los ataques, su ruido no toca la línea base, y da capturas para el jurado |
| Hostname | `LAB-ATACANTE` | |
| vCPU / RAM / Disco | **2 · 4 GB · 40 GB** | `msfconsole` manda la RAM: cómodo en 4 GB, lento en 2. Kali completo ≈ 20 GB + `seclists` ≈ 1 GB + capturas |
| Port group | VLAN **20** | |
| Encendida | **solo en la fase de ataques** | Apagada durante las 72 h. Compartir VM con los clientes obligaría a elegir entre apagar todo o contaminar el entrenamiento, y eso invalida un modelo no supervisado |

### `srv-dmz` — ya desplegada

`10.10.30.10`, VLAN 30, con `lab-web-http` y `lab-web-https`.

---

## 5. Usuarios y acceso

**Sin contraseñas en ficheros, commits ni comandos.** Solo clave pública.

| Máquina | Usuario | Acceso |
|---|---|---|
| `srv-dmz` | `adminsrvdmz` | ya operativo desde VM-GESTION |
| `clientes` | **`adminclientes`** | clave pública, la misma que ya entra en `srv-dmz` |
| `atacante` | **`adminatacante`** | clave pública (Kali crea `kali` por defecto; se añade este y se deja `kali` sin contraseña utilizable) |

En las dos nuevas, al terminar:

```bash
sudo usermod -aG sudo adminclientes
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

---

## 6. Direccionamiento

VLAN 20 → `10.10.20.0/24`, puerta de enlace la VIP CARP de pfSense
**`10.10.20.1`** *(documentado en el respaldo de pfSense-A; pendiente de
confirmar en vivo)*. pfSense-A es `.2` y pfSense-B es `.3`.

**Hay DHCP en la VLAN 20**: rango `10.10.20.50`-`.200`, DNS `10.10.10.20`
*(documentado)*. Solo la 10 y la 20 lo tienen; el resto es estático por diseño.
Dos consecuencias:

- Las direcciones del laboratorio (`.20`-`.26`, `.30`) quedan **fuera del
  rango**: no hace falta reserva ni excluir nada del pool.
- Una concesión nueva **es** un cambio de vínculo MAC↔IP, que es justo lo que
  `mac_ip_binding_changes_60s` detecta como sospechoso. La línea base tiene que
  contener rotación normal de arrendamientos o el modelo marcará cada
  renovación como suplantación ARP. Los portátiles Windows, que sí cogen IP por
  DHCP, son los que aportan esa rotación.

| Dirección | Para qué | En `cyberflow.toml` |
|---|---|---|
| `10.10.20.20` | gestión de `clientes` (SSH) | **`[red] excluir`** — tu SSH no es un usuario |
| `10.10.20.21` … `.26` | los 6 perfiles, un alias por perfil | puntuadas |
| `10.10.20.30` | `atacante` | **puntuada**: es lo que hay que detectar |

Los 6 alias van en la misma NIC. El motor puntúa **por IP**: una sola VM produce
**6 entidades** para el modelo.

### 🔴 La VM nació en `10.10.20.55`, dentro del pool DHCP

*(medido 2026-09-23)*. El pool va de `.50` a `.200`, así que pfSense puede
arrendar esa misma dirección a un portátil en cualquier momento de las 72 h. Un
conflicto de IP a mitad de la línea base la invalida, y no da la cara: el
motor seguiría escribiendo.

Se arregla en el mismo netplan que hay que editar de todas formas para añadir
los alias, así que no cuesta un paso extra: la gestión pasa a `.20` y `.55`
desaparece. La alternativa —reservar `.55` en pfSense— toca infraestructura
ajena y deja la dirección dependiendo de un servicio externo.

`/etc/netplan/01-lab.yaml`:

```yaml
network:
  version: 2
  ethernets:
    ens34:
      addresses: [10.10.20.20/24, 10.10.20.21/24, 10.10.20.22/24,
                  10.10.20.23/24, 10.10.20.24/24, 10.10.20.25/24, 10.10.20.26/24]
      routes: [{to: default, via: 10.10.20.1}]
      nameservers: {addresses: [10.10.10.20]}
```

Aplicar con `sudo netplan try` y no con `netplan apply`: si la configuración
deja la máquina incomunicada, `try` la revierte sola a los 120 s. Con `apply`
te quedas fuera y hay que entrar por la consola del hipervisor.

**Reglas en pfSense** *(cambio en infraestructura de Franco's — requiere tu
aprobación)*: VLAN 20 → VLAN 30 en `tcp/80,443`, VLAN 20 → `10.10.10.20:53`, y
VLAN 20 → VLAN 30 en los puertos cerrados que usa el perfil `erratico`
(8081, 9001, 4444, 31337) **rechazados, no descartados**: `puerto_cerrado`
necesita un RST o un SYN sin respuesta, y un `block` silencioso da un rasgo
distinto que un `reject`.

---

## 7. Higiene: Ubuntu Server también habla solo

Cada una de estas es una ráfaga que el modelo aprendería como normal, o marcaría
como anomalía sin que sepas por qué. La importante es la primera: es la única
que mueve megabytes.

```bash
sudo systemctl disable --now unattended-upgrades
sudo sed -i 's/^ENABLED=1/ENABLED=0/' /etc/default/motd-news
sudo apt purge -y snapd
sudo timedatectl set-ntp true          # y apuntar el NTP al pfSense, no a ubuntu.com
echo 'SystemMaxUse=200M' | sudo tee -a /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

---

## 8. Puerta antes de las 72 h

No se lanza el generador a ciegas. Cada punto, con su comando y su salida.

1. ~~VLAN 20 en el troncal~~ — **hecho** (§2, verificado 2026-09-22). Queda el
   estado físico: `show interfaces status | include Gi1/0/20|Gi2/0/20`.
2. **Los dos enlaces de pfSense en el espejo** (§1), o asumir por escrito el
   hueco si CARP conmuta durante las 72 h.
3. **La VM tiene camino:** `ping 10.10.30.10` desde `clientes`.
4. **Una vuelta completa:** `python3 clientes_lab.py --perfil ofimatica --una-vuelta`
   sin errores contra los seis endpoints.
5. **El espejo lo ve:** con el generador corriendo, en el sensor
   `sudo tcpdump -i ens37 -nn -c 20 'host 10.10.20.21'`. Si no sale nada, el
   resto sobra.
6. **Los 6 alias son 6 entidades:** aparecen `.21`–`.26` en el registro del
   motor, y **no** aparece `.20`.
7. **Duplicación medida**, no supuesta (§3).
8. **Disco libre en el sensor.** El anillo de pcap está acotado a 15 min;
   `eve.json` a 72 h **no está medido**.
