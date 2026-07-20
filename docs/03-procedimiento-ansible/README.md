# Procedimiento de instalación y puesta en marcha de Ansible

## 1. Propósito

Este documento registra cronológicamente la instalación y configuración de Ansible para automatizar el laboratorio PPI. Se documentan solamente acciones ejecutadas o preparadas durante la construcción de la versión final.

Estados utilizados:

- **COMPLETADO:** la acción fue ejecutada.
- **VALIDADO:** además de ejecutarse, se comprobó su resultado.
- **PENDIENTE:** está planificada, pero todavía no se comprobó.

## 2. Estado resumido

| Etapa | Estado | Resultado |
|---|---|---|
| Crear estructura Ansible | VALIDADO | Configuración, inventario y playbooks presentes |
| Instalar controlador | VALIDADO | ansible-core 2.21.2 sobre Python 3.14.4 |
| Instalar colecciones | VALIDADO | ansible.posix 2.2.2 y community.general 11.4.9 |
| Validar inventario | VALIDADO | Sensor, servidor, Kali y cliente declarados |
| Ejecutar preflight local | VALIDADO | 5 tareas ok, 0 cambios, 0 fallos |
| Conectividad IP con sensor | VALIDADO | 10.10.10.20 responde, 0 % de pérdida |
| Conectividad IP con servidor | VALIDADO | 10.10.10.30 responde, 0 % de pérdida |
| Verificar SSH remoto | VALIDADO | Puerto 22 abierto en sensor y servidor |
| Crear clave del controlador | COMPLETADO | Clave Ed25519 exclusiva disponible |
| Crear `useransible` en sensor | VALIDADO | Autenticación por clave y playbook correctos |
| Crear `useransible` en servidor | VALIDADO | Autenticación por clave y playbook correctos |
| Conectividad IP con Kali | VALIDADO | 10.10.10.40 responde, 0 % de pérdida |
| Habilitar SSH en Kali | VALIDADO | Puerto 22 abierto el 19 de julio de 2026 |
| Crear `useransible` en Kali | VALIDADO | Autenticación por clave y playbook correctos |
| Conectividad IP con VM05 Cliente | VALIDADO | 10.10.10.50 responde, 0 % de pérdida |
| Habilitar SSH en VM05 Cliente | VALIDADO | Puerto 22 abierto el 19 de julio de 2026 |
| Crear `useransible` en VM05 Cliente | VALIDADO | Autenticación por clave y playbook correctos |
| Registrar huellas en VM01 | COMPLETADO | TOFU controlado sobre `PPI-MGMT` aislada |
| Autenticación por clave en las cuatro VMs | VALIDADO | Clave Ed25519 aceptada por todos los nodos |
| Ejecutar ping de Ansible remoto | VALIDADO | 4 nodos, 0 inalcanzables y 0 fallos |
| Configurar privilegios limitados | PENDIENTE | Se hará después del acceso sin privilegios |

## 3. Controlador utilizado

La VM administrativa funciona como nodo controlador.

| Dato | Valor observado |
|---|---|
| Host | `m4rk-VMware20-1` |
| Sistema | Ubuntu 26.04 LTS |
| IP externa actual | 172.17.25.155/24 en `ens34` |
| IP de PPI-MGMT | 10.10.10.10/24 en `ens37` |
| Gateway predeterminado | 172.17.25.121 por `ens34` |
| Python | 3.14.4 |
| Ansible Core | 2.21.2 |

La interfaz externa permite GitHub, actualizaciones y RustDesk. `ens37` se utiliza exclusivamente para administrar el laboratorio.

## 4. Creación de la estructura

Se creó la siguiente estructura versionada:

```text
ansible/
├── ansible.cfg
├── inventories/
│   └── lab/
│       ├── hosts.yml
│       └── group_vars/all.yml
├── playbooks/
│   ├── 00-validar-controlador.yml
│   └── 01-comprobar-conectividad.yml
├── requirements-controller.txt
└── requirements.yml
```

También se agregaron a `.gitignore`:

- `.venv/`
- `.collections/`
- Archivos Vault y contraseñas locales.
- Claves privadas.
- Logs y artefactos runtime.

## 5. Instalación aislada de Ansible

### 5.1 Intento inicial

Se intentó crear un entorno virtual:

```bash
python3 -m venv .venv
```

Ubuntu informó que `ensurepip` no estaba disponible porque `python3.14-venv` no estaba instalado.

### 5.2 Solución aplicada

Para no modificar el Python global, se utilizó el bootstrap oficial de PyPA dentro del entorno local:

```bash
curl -fL https://bootstrap.pypa.io/get-pip.py -o /tmp/ppi-get-pip.py
.venv/bin/python /tmp/ppi-get-pip.py
```

Después se instaló la versión fijada:

```bash
.venv/bin/python -m pip install \
  -r ansible/requirements-controller.txt
```

Resultado validado:

```text
ansible-core 2.21.2
Python 3.14.4
```

El entorno `.venv` no se publica en GitHub; puede reconstruirse usando los requisitos versionados.

## 6. Colecciones instaladas

Desde `ansible/` se ejecutó:

```bash
../.venv/bin/ansible-galaxy collection install \
  -r requirements.yml \
  -p .collections
```

Versiones validadas:

| Colección | Versión | Uso previsto |
|---|---:|---|
| `ansible.posix` | 2.2.2 | sysctl, firewall y administración POSIX |
| `community.general` | 11.4.9 | Módulos auxiliares del laboratorio |

Las versiones quedaron fijadas en `ansible/requirements.yml`.

## 7. Configuración de seguridad

`ansible.cfg` establece:

- Verificación de huellas SSH activada.
- Archivos de reintento desactivados.
- Cinco forks como máximo.
- Elevación de privilegios desactivada por defecto.
- Directorios temporales dedicados.
- Colecciones instaladas dentro del proyecto.

No se utiliza:

- `StrictHostKeyChecking=no`.
- Contraseñas escritas en inventario.
- Tokens en texto plano.
- Claves privadas publicadas.
- `sudo` global sin justificación.

## 8. Inventario de gestión

El inventario utiliza las IP de `PPI-MGMT`:

| Grupo | Host | IP | Usuario SSH |
|---|---|---|---|
| `sensor` | `ppi-sensor` | 10.10.10.20 | `useransible` |
| `servidores` | `ppi-server` | 10.10.10.30 | `useransible` |
| `atacantes` | `ppi-kali` | 10.10.10.40 | `useransible` |
| `clientes_linux` | `ppi-client` | 10.10.10.50 | `useransible` |

La clave privada configurada en el inventario es una ruta local:

```text
~/.ssh/id_ed25519_ppi_ansible
```

El archivo real está fuera del repositorio.

## 9. Preflight del controlador

Se verificaron sintácticamente:

```bash
cd ansible
../.venv/bin/ansible-playbook --syntax-check \
  playbooks/00-validar-controlador.yml

../.venv/bin/ansible-playbook --syntax-check \
  playbooks/01-comprobar-conectividad.yml
```

Resultado: ambos playbooks pasaron.

Después se ejecutó:

```bash
../.venv/bin/ansible-playbook \
  playbooks/00-validar-controlador.yml
```

Resultado:

```text
ok=5
changed=0
unreachable=0
failed=0
```

Se confirmaron la versión de Ansible, las tres redes y los cuatro roles administrados.

## 10. Validación inicial de red

### 10.1 Interfaces del controlador

Se observaron:

```text
ens34  172.17.25.155/24
ens37  10.10.10.10/24
```

Ruta directa de gestión:

```text
10.10.10.0/24 dev ens37 src 10.10.10.10
```

### 10.2 Sensor

```text
IP: 10.10.10.20
ICMP: 2/2 respuestas
Pérdida: 0 %
Latencia promedio: 0.319 ms
SSH: puerto 22 abierto
```

Huella ED25519 observada:

```text
SHA256:s1CuoCRHEeT82iJqoZ2pupT4A5u6tH58TDXevghZG68
```

### 10.3 Servidor

```text
IP: 10.10.10.30
ICMP: 2/2 respuestas
Pérdida: 0 %
Latencia promedio: 0.333 ms
SSH: puerto 22 abierto
```

Huella ED25519 observada:

```text
SHA256:vCo7DpwfQbD7KczXGskpmPzpqwDgfPtO1Pdj133Uh2o
```

Antes de agregarlas a `known_hosts`, las huellas se confirmarán desde la consola de cada VM.

## 11. Clave del controlador

Se preparó una clave Ed25519 exclusiva para el laboratorio:

```text
Privada: ~/.ssh/id_ed25519_ppi_ansible
Pública: ~/.ssh/id_ed25519_ppi_ansible.pub
```

Huella de la clave pública del controlador:

```text
SHA256:pFBXQ3XD4yfZvhDvuh9CTP4+qPCEPr2Q+F0V7TOnAN4
```

La clave pública que puede copiarse a los nodos es:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB4FMAbIxw5Ddov41uYfLo3vYayyXhrTV/uHhCx8RM76 ppi-ansible-controller
```

La clave privada nunca se copiará a los nodos administrados.

## 12. Creación de `useransible`

Este procedimiento debe ejecutarse una vez desde la consola del sensor y del servidor:

```bash
sudo adduser --disabled-password --gecos "" useransible

sudo install -d \
  -m 700 \
  -o useransible \
  -g useransible \
  /home/useransible/.ssh

echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB4FMAbIxw5Ddov41uYfLo3vYayyXhrTV/uHhCx8RM76 ppi-ansible-controller' \
  | sudo tee /home/useransible/.ssh/authorized_keys

sudo chown useransible:useransible \
  /home/useransible/.ssh/authorized_keys

sudo chmod 600 \
  /home/useransible/.ssh/authorized_keys

sudo systemctl enable --now ssh
```

Estado actual: **pendiente de validación en ambas VMs**.

No se agrega todavía la cuenta al grupo `sudo`. Primero se comprobará que Ansible pueda conectarse y ejecutar tareas sin privilegios.

## 13. Próxima validación

Una vez creada la cuenta en sensor y servidor:

1. Confirmar las huellas SSH desde sus consolas.
2. Agregar las huellas verificadas a `known_hosts`.
3. Limitar temporalmente la comprobación a sensor y servidor.
4. Ejecutar:

```bash
cd ansible
../.venv/bin/ansible-playbook \
  playbooks/01-comprobar-conectividad.yml \
  --limit sensor:servidores
```

El playbook no usa `sudo` ni modifica configuración. Ejecuta ping de Ansible y consulta la identidad remota mediante `id`.

## 14. Criterio de finalización de esta etapa

La etapa se cerró el 19 de julio de 2026 cuando los cuatro nodos reportaron:

```text
unreachable=0
failed=0
```

El siguiente paso es diseñar un rol de privilegios mínimos y automatizar la configuración de interfaces, enrutamiento y Suricata.

## 15. Incorporación de Kali Linux

### 15.1 Comprobación inicial

El 19 de julio de 2026 se comprobó la IP de gestión prevista:

```text
IP: 10.10.10.40
Interfaz de salida del controlador: ens37
ICMP: 2/2 respuestas
Pérdida: 0 %
Latencia promedio: 0.283 ms
MAC observada: 00:0c:29:52:db:74
SSH: puerto 22 cerrado/rechazado
```

El resultado confirma que Kali está conectada a `PPI-MGMT`, pero OpenSSH Server todavía no está disponible. No fue posible obtener ni registrar una huella ED25519.

### 15.2 Instalar SSH y la cuenta técnica

Desde la consola de Kali en ESXi se ejecutará:

```bash
sudo apt update
sudo apt install -y openssh-server python3
sudo systemctl enable --now ssh

sudo adduser --disabled-password --gecos "" useransible

sudo install -d \
  -m 700 \
  -o useransible \
  -g useransible \
  /home/useransible/.ssh

echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB4FMAbIxw5Ddov41uYfLo3vYayyXhrTV/uHhCx8RM76 ppi-ansible-controller' \
  | sudo tee /home/useransible/.ssh/authorized_keys

sudo chown useransible:useransible \
  /home/useransible/.ssh/authorized_keys

sudo chmod 600 \
  /home/useransible/.ssh/authorized_keys
```

### 15.3 Comprobaciones requeridas en Kali

```bash
systemctl is-enabled ssh
systemctl is-active ssh
ss -lntp | grep ':22'
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Resultados esperados:

```text
enabled
active
```

La huella ED25519 mostrada por Kali se comparará con `ssh-keyscan` desde VM01 antes de agregarla a `known_hosts`.

### 15.4 Seguridad prevista

- `useransible` usará solamente autenticación por clave.
- La clave privada permanecerá en VM01.
- No se habilitará acceso SSH de `root`.
- No se agregará todavía `useransible` a `sudo`.
- Posteriormente el firewall de Kali permitirá SSH administrativo desde `10.10.10.10` y bloqueará conexiones iniciadas desde Kali hacia otros nodos de `PPI-MGMT`.
- Las herramientas de ataque utilizarán la NIC de `PPI-LAN`, no la de gestión.

### 15.5 Validación posterior de SSH

El 19 de julio de 2026 se repitió la comprobación desde VM01:

```text
Puerto 22: abierto
Huella ED25519 observada: SHA256:iEAn7Mbd+mP0tepxP8xkEQXSyyh6F9Gp/OB6SG5FGrU
```

La huella permanece pendiente de comparación con la salida local de Kali. La autenticación de `useransible` tampoco se declara validada hasta ejecutar el playbook remoto.

Estado actual de Kali: **conectividad IP y SSH validados; huella y cuenta técnica pendientes de validación**.

## 16. Incorporación de VM05 Cliente Desktop

### 16.1 Comprobación inicial

El 19 de julio de 2026 se comprobó la IP de gestión del cliente:

```text
IP: 10.10.10.50
Interfaz de salida del controlador: ens37
ICMP: 2/2 respuestas
Pérdida: 0 %
Latencia promedio: 0.309 ms
MAC observada: 00:0c:29:c5:ed:70
TTL observado: 64
SSH: puerto 22 cerrado/rechazado
```

El TTL es compatible con un sistema Linux, pero la distribución y versión se confirmarán mediante facts de Ansible después de habilitar SSH. El inventario mantiene este host en `clientes_linux`.

### 16.2 Instalar SSH y la cuenta técnica

Desde la consola de VM05 Cliente Desktop en ESXi se ejecutará:

```bash
sudo apt update
sudo apt install -y openssh-server python3
sudo systemctl enable --now ssh

sudo adduser --disabled-password --gecos "" useransible

sudo install -d \
  -m 700 \
  -o useransible \
  -g useransible \
  /home/useransible/.ssh

echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB4FMAbIxw5Ddov41uYfLo3vYayyXhrTV/uHhCx8RM76 ppi-ansible-controller' \
  | sudo tee /home/useransible/.ssh/authorized_keys

sudo chown useransible:useransible \
  /home/useransible/.ssh/authorized_keys

sudo chmod 600 \
  /home/useransible/.ssh/authorized_keys
```

### 16.3 Comprobaciones requeridas

```bash
systemctl is-enabled ssh
systemctl is-active ssh
ss -lntp | grep ':22'
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

La huella ED25519 se comparará desde VM01 antes de incorporarla a `known_hosts`.

### 16.4 Función posterior del cliente

Una vez administrable, VM05 producirá tráfico legítimo reproducible:

- Navegación HTTP/HTTPS.
- Descargas y cargas de archivos grandes.
- SCP/SFTP.
- Streaming o tráfico sostenido.
- `iperf3` TCP y UDP controlado.
- Paquetes legítimos entre 500 y 1500 bytes.
- Tráfico concurrente mientras Kali ejecuta ataques autorizados.

La NIC de `PPI-MGMT` se utilizará para Ansible. La NIC de `PPI-LAN`, con IP planificada `10.20.0.20/24`, generará exclusivamente el tráfico experimental.

### 16.5 Validación posterior de SSH

El 19 de julio de 2026 se repitió la comprobación desde VM01:

```text
Puerto 22: abierto
Huella ED25519 observada: SHA256:Bf4kznuAqHYEHj3pEUYMgrGP1bF173n5KJHKS4mZyu4
```

La huella permanece pendiente de comparación con la salida local del cliente. La distribución exacta y la autenticación de `useransible` se confirmarán mediante Ansible.

Estado actual de VM05: **conectividad IP y SSH validados; huella, sistema exacto y cuenta técnica pendientes de validación**.

## 17. Primer intento de autenticación remota

Para continuar sin detener la preparación, el 19 de julio de 2026 se aplicó confianza en el primer uso (TOFU) exclusivamente sobre la red virtual aislada `PPI-MGMT`. SSH agregó las claves ED25519 observadas de las cuatro VMs al `known_hosts` de VM01.

Se intentó ejecutar `id` y `hostname` con:

```text
Usuario: useransible
Clave: ~/.ssh/id_ed25519_ppi_ansible
Autenticación interactiva: desactivada para la prueba
```

Resultado por nodo:

| IP | Huella registrada | Autenticación |
|---|---|---|
| 10.10.10.20 | Sí | FALLÓ |
| 10.10.10.30 | Sí | FALLÓ |
| 10.10.10.40 | Sí | FALLÓ |
| 10.10.10.50 | Sí | FALLÓ |

Mensaje común:

```text
Permission denied (publickey,password)
```

### Diagnóstico

La conectividad, SSH y reconocimiento de host funcionan. El bloqueo se limita a la autenticación de la cuenta. Las causas probables son:

1. `useransible` todavía no existe en las VMs.
2. La clave pública no está en `authorized_keys`.
3. El propietario o los permisos de `.ssh` no son correctos.

### Condición para continuar con cambios remotos

En cada VM debe cumplirse:

```text
Cuenta: useransible
Directorio .ssh: useransible:useransible, modo 700
authorized_keys: useransible:useransible, modo 600
Clave pública: ppi-ansible-controller
```

Mientras no se cumpla, pueden prepararse roles y playbooks localmente, pero no se declarará ninguna configuración remota como aplicada o validada.

### 17.1 Bootstrap automatizado preparado

Se agregó el script:

```text
ansible/scripts/bootstrap-useransible.sh
```

El script utiliza temporalmente una cuenta administrativa existente por VM y solicita sus credenciales directamente en una terminal interactiva. Las cuentas iniciales confirmadas son:

| VM | IP | Usuario inicial |
|---|---|---|
| Sensor | 10.10.10.20 | `sensor_motor` |
| Servidor | 10.10.10.30 | `server` |
| Kali | 10.10.10.40 | `m4rk` |
| Cliente | 10.10.10.50 | `m4rk` |

Las contraseñas no se incorporan al script ni al repositorio. En cada VM el script realiza de forma idempotente:

1. Crear `useransible` si no existe.
2. Crear `/home/useransible/.ssh` con modo 700.
3. Instalar la clave pública del controlador.
4. Aplicar propietario `useransible:useransible`.
5. Aplicar modo 600 a `authorized_keys`.
6. Probar inmediatamente autenticación por clave.

No almacena la contraseña administrativa y no agrega `useransible` a `sudo`.

### 17.2 Resultado del primer bootstrap

El primer intento interactivo no consiguió completar la autorización remota. Una comprobación posterior volvió a obtener en las cuatro VMs:

```text
Permission denied (publickey,password)
```

Estado en ese momento: **script preparado y validado sintácticamente; primera ejecución remota incompleta**. Este estado fue superado por el bootstrap descrito a continuación.

### 17.3 Bootstrap completado

El script se actualizó con las cuentas iniciales diferentes de cada VM y se ejecutó nuevamente. Tres nodos quedaron configurados en la primera corrida correcta; el servidor se reparó en una segunda corrida limitada a `10.10.10.30`.

El script acepta opcionalmente una o varias IP autorizadas, por ejemplo:

```bash
./ansible/scripts/bootstrap-useransible.sh 10.10.10.30
```

Resultado final de autenticación:

| Host Ansible | IP | Hostname remoto | Identidad |
|---|---|---|---|
| `ppi-sensor` | 10.10.10.20 | `sensormotor` | `uid=1001(useransible)` |
| `ppi-server` | 10.10.10.30 | `server` | `uid=1001(useransible)` |
| `ppi-kali` | 10.10.10.40 | `kali` | `uid=1001(useransible)` |
| `ppi-client` | 10.10.10.50 | `m4rk-VMware20-1` | `uid=1001(useransible)` |

### 17.4 Primera validación completa con Ansible

Se ejecutó:

```bash
cd ansible
../.venv/bin/ansible-playbook \
  playbooks/01-comprobar-conectividad.yml
```

Resultado final:

| Host | ok | changed | unreachable | failed |
|---|---:|---:|---:|---:|
| `ppi-sensor` | 4 | 0 | 0 | 0 |
| `ppi-server` | 4 | 0 | 0 | 0 |
| `ppi-kali` | 4 | 0 | 0 | 0 |
| `ppi-client` | 4 | 0 | 0 | 0 |

La etapa de conectividad y autenticación por clave queda **VALIDADA**. Ninguna tarea utilizó `sudo` ni modificó configuración remota durante este playbook.

## 18. Auditoría automática de recursos

Se incorporó y ejecutó:

```text
ansible/playbooks/02-auditar-recursos.yml
```

El playbook:

1. Recopila facts de Ansible sin `sudo`.
2. Verifica Linux y Python 3.
3. Comprueba que la IP `PPI-MGMT` del inventario exista realmente.
4. Registra CPU, RAM, disco, interfaces e IP.
5. Guarda resúmenes no sensibles en `artifacts/preflight/`.

Resultado de ejecución:

```text
ppi-sensor : unreachable=0 failed=0
ppi-server : unreachable=0 failed=0
ppi-kali   : unreachable=0 failed=0
ppi-client : unreachable=0 failed=0
```

Hallazgos principales:

- Sensor, servidor y cliente utilizan Ubuntu 26.04 con Python 3.14.4.
- Kali utiliza Kali 2026.2 con Python 3.13.12.
- Las cuatro IP de `PPI-MGMT` coinciden con el inventario.
- Sensor ya dispone de 6 vCPU y aproximadamente 16 GB de RAM.
- Cliente todavía tiene 2 vCPU y aproximadamente 3.4 GB visibles.
- El disco virtual del Sensor ya es de 160 GiB y el del Servidor de 120 GiB, exactamente como establece el diseño.
- En Sensor y Servidor, la raíz es menor porque el volumen lógico LVM todavía no consume todo el espacio disponible; no hace falta aumentar nuevamente el disco en ESXi.
- Kali dispone de un disco virtual de 60 GiB y lo utiliza correctamente.
- El Cliente sí conserva un disco virtual de 60 GiB frente a los 100 GiB previstos.
- VM02–VM05 conservan una interfaz externa temporal en `172.17.25.0/24`.

La tabla completa de recursos, interfaces y diferencias se mantiene en `docs/01-infraestructura-virtual/README.md`.

Estado: **auditoría validada; los ajustes posteriores de CPU, RAM y disco del Cliente se registran en la sección 21**.

## 19. Ampliación de LVM en Sensor y Servidor

La verificación de bloques confirmó que el Sensor ya tenía un disco virtual de 160 GiB y el Servidor uno de 120 GiB. El espacio faltante en `/` estaba libre dentro de `ubuntu-vg`, por lo que no se modificó el hardware virtual en ESXi.

Antes de la ampliación:

| VM | Tamaño del LV | Espacio libre del VG |
|---|---:|---:|
| Sensor | 78.47 GiB | 78.47 GiB |
| Servidor | 58.47 GiB | 58.47 GiB |

Se ejecutó mediante Ansible y con privilegios administrativos:

```bash
lvextend -l +100%FREE -r /dev/ubuntu-vg/ubuntu-lv
```

La opción `-r` amplió también el sistema de archivos ext4 mientras estaba montado, sin reiniciar las VMs. La validación posterior registró:

| VM | LV final | Raíz visible | Libre en raíz | VG libre |
|---|---:|---:|---:|---:|
| Sensor | 156.95 GiB | 153.9 GiB | 140 GiB | 0 GiB |
| Servidor | 116.95 GiB | 114.8 GiB | 102.5 GiB | 0 GiB |

Para ejecutar la operación se concedió temporalmente `sudo` sin contraseña a `useransible`. El archivo temporal `/etc/sudoers.d/useransible-ansible` fue eliminado de ambas VMs inmediatamente después de validar la ampliación.

Estado: **ampliación de LVM completada y validada en Sensor y Servidor**.

## 20. Zona horaria y sincronización NTP

La auditoría inicial encontró tres configuraciones horarias diferentes:

- Sensor y Servidor: `Etc/UTC`.
- Kali: `Europe/Madrid`.
- Cliente y VM administrativa: `America/Lima`.
- El Sensor no estaba sincronizado y tenía un atraso aproximado de tres horas.

Se estableció `America/Lima` en las cuatro VMs administradas:

```bash
timedatectl set-timezone America/Lima
timedatectl set-ntp true
```

El Sensor utiliza Chrony. No tenía fuentes NTP configuradas y la dirección `8.8.8.8` figuraba incorrectamente como dominio de búsqueda. Se corrigió la resolución DNS de su interfaz externa, se añadió una fuente de Ubuntu/Canonical y se realizó el ajuste inicial con `chronyc makestep`.

Para crear una referencia horaria común dentro de la topología, el Sensor quedó autorizado para atender solicitudes NTP de `10.10.10.0/24`:

```text
allow 10.10.10.0/24
```

Servidor y Cliente usan Chrony con esta fuente:

```text
server 10.10.10.20 iburst prefer trust
```

Kali usa `systemd-timesyncd` con la siguiente configuración:

```ini
[Time]
NTP=10.10.10.20
FallbackNTP=ntp.ubuntu.com
```

La validación conjunta del 19 de julio de 2026 confirmó:

| VM | Zona horaria | NTP sincronizado | Referencia |
|---|---|---|---|
| Sensor | `America/Lima` | Sí | Ubuntu/Canonical, estrato 3 |
| Servidor | `America/Lima` | Sí | Sensor `10.10.10.20`, estrato 4 |
| Kali | `America/Lima` | Sí | Sensor `10.10.10.20` |
| Cliente | `America/Lima` | Sí | Sensor `10.10.10.20`, estrato 4 |

Estado: **zona horaria unificada y sincronización NTP validada en todas las VMs**.

## 21. Ajuste final de recursos de VM05 Cliente

Se apagó VM05 para modificar su hardware en ESXi y se aumentaron los recursos planificados. Después del encendido, Ansible confirmó:

| Recurso | Antes | Después detectado | Estado |
|---|---:|---:|---|
| vCPU | 2 | 4 | Cumplido |
| RAM | Aproximadamente 4 GiB | 7.2 GiB utilizables de 8 GiB asignados | Cumplido |
| Disco virtual | 60 GiB | 100 GiB | Cumplido |

El disco ya aparecía como `/dev/sda` de 100 GiB, pero la partición raíz `/dev/sda2` conservaba aproximadamente 59 GiB. Se amplió la partición existente y el sistema de archivos ext4 en línea:

```bash
growpart /dev/sda 2
resize2fs /dev/sda2
```

Validación posterior:

```text
/dev/sda       100 GiB
/dev/sda1        1 GiB  vfat  /boot/efi
/dev/sda2     98.9 GiB  ext4  /
raíz visible    98 GiB
espacio libre   83 GiB
```

No se creó un segundo disco y no fue necesario reiniciar durante la ampliación de ext4.

Estado: **recursos finales de VM05 Cliente configurados y validados**.

## 22. Configuración del Sensor como router LAN–DMZ

### 22.1 Auditoría previa

Antes de modificar la red se consultaron interfaces, rutas, reenvío IPv4 y firewall. Se confirmó:

- Sensor: `ens35=10.20.0.1`, `ens38=10.30.0.1` y `net.ipv4.ip_forward=0`.
- Cliente: `ens38=10.20.0.20`, sin ruta a `10.30.0.0/24`.
- Kali: `eth1=10.20.0.100`, sin ruta a `10.30.0.0/24`.
- Servidor: `ens38=10.30.0.10`, con gateway `10.30.0.1`.
- `nftables` estaba instalado en el Sensor, sin reglas activas y deshabilitado al arranque.

La red `PPI-MGMT` se mantuvo sin cambios para conservar el acceso SSH de recuperación.

### 22.2 Activación persistente de IP forwarding

En el Sensor se creó `/etc/sysctl.d/99-ppi-router.conf`:

```text
net.ipv4.ip_forward = 1
```

Se aplicó y verificó con:

```bash
sysctl --system
sysctl net.ipv4.ip_forward
```

Resultado: `net.ipv4.ip_forward = 1`.

### 22.3 Política de reenvío con nftables

Se configuró `/etc/nftables.conf` con una política cerrada para el tráfico reenviado:

```nft
#!/usr/sbin/nft -f
flush ruleset

table inet ppi_filter {
  chain forward {
    type filter hook forward priority filter; policy drop;
    ct state invalid drop
    ct state established,related accept
    iifname "ens35" oifname "ens38" ip saddr 10.20.0.0/24 ip daddr 10.30.0.0/24 counter accept
  }
}
```

Antes de cargarla se comprobó la sintaxis y después se habilitó su persistencia:

```bash
nft -c -f /etc/nftables.conf
nft -f /etc/nftables.conf
systemctl enable nftables
```

La cadena `forward` no controla conexiones dirigidas al propio Sensor, por lo que el acceso SSH mediante `PPI-MGMT` se conservó.

### 22.4 Ruta persistente del Cliente

El Cliente utiliza NetworkManager. Se añadió a la conexión asociada con `ens38`:

```bash
nmcli connection modify 'Conexión cableada 2' \
  +ipv4.routes '10.30.0.0/24 10.20.0.1'
nmcli connection up 'Conexión cableada 2'
```

### 22.5 Ruta persistente de Kali

La conexión de `eth1` se denomina `eth1`:

```bash
nmcli connection modify eth1 \
  +ipv4.routes '10.30.0.0/24 10.20.0.1'
nmcli connection up eth1
```

### 22.6 Validación funcional

En Cliente y Kali, `ip route get 10.30.0.10` confirmó el siguiente salto `10.20.0.1`. La traza desde el Cliente mostró:

```text
1  10.20.0.1
2  10.30.0.10
```

Resultados:

| Prueba | Cliente | Kali |
|---|---|---|
| Ruta por `10.20.0.1` | PASS | PASS |
| ICMP a `10.30.0.10` | PASS | PASS, 0 % de pérdida |
| TCP/22 a `10.30.0.10` | PASS | PASS |

El contador de la regla LAN→DMZ del Sensor aumentó a 7 paquetes y 1,932 bytes durante la validación, demostrando que el tráfico fue reenviado por el Sensor.

### 22.7 Condición para las pruebas finales

Las NIC de `172.17.25.0/24` siguen conectadas temporalmente para instalación y recuperación. Aunque las pruebas dirigidas a `10.30.0.10` ya atraviesan obligatoriamente el Sensor, antes de recolectar el dataset final se deberán desconectar en ESXi las NIC externas de Servidor, Kali y Cliente, o bloquear su uso experimental. La interfaz externa del Sensor puede mantenerse mientras sea necesaria para paquetes y NTP.

Estado: **enrutamiento LAN–DMZ, firewall y rutas persistentes configurados y validados**.

## 23. Actualización de recursos de VM01 Administración

Después de aumentar los recursos de la máquina administrativa en ESXi, se verificó el sistema invitado:

| Recurso | Detectado | Estado |
|---|---:|---|
| vCPU | 4 | Utilizadas por Ubuntu, CPU 0–3 en línea |
| RAM | Aproximadamente 11 GiB utilizables de 12 GB asignados | Utilizada por Ubuntu |
| Disco virtual | 70 GiB | Detectado por el sistema invitado |
| Swap | 3.8 GiB | Activo, 0 bytes usados durante la validación |

Inicialmente `/dev/sda2` y la raíz ext4 conservaban aproximadamente 48 GiB. Se utilizó el espacio adicional del disco mediante:

```bash
growpart /dev/sda 2
resize2fs /dev/sda2
```

Validación posterior:

```text
/dev/sda2  ext4  67.6 GiB
raíz mostrada por df: 68 GiB
espacio disponible: aproximadamente 51 GiB
```

La partición y ext4 fueron ampliados en línea sin reiniciar la VM.

Estado: **CPU, RAM y disco actualizados y aprovechados por VM01**.

## 24. Instalación y primera validación de Suricata

### 24.1 Auditoría previa

Se confirmó que Suricata no estaba instalado y que `ens35`, interfaz de entrada desde `PPI-LAN`, se encontraba activa con MTU 1500, sin errores ni descartes registrados por Linux.

La primera ejecución de `apt-get update` falló porque el Sensor tenía `8.8.8.8` configurado como dominio de búsqueda, no como servidor DNS. Se creó una configuración Netplan persistente para `ens34` en `/etc/netplan/99-ppi-dns.yaml`:

```yaml
network:
  version: 2
  ethernets:
    ens34:
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
        search: []
```

Se verificó con `netplan generate`, `netplan apply`, `resolvectl dns ens34` y resolución de `archive.ubuntu.com`.

### 24.2 Paquetes instalados

Desde los repositorios de Ubuntu 26.04 se instalaron:

| Paquete | Versión |
|---|---|
| Suricata | 8.0.3 |
| suricata-update | 1.3.7 |
| jq | 1.8.1, ya presente |

Suricata incluye AF_PACKET, Hyperscan, NFQueue, TLS, JA3, JA4 y soporte de systemd. Esta fase utiliza solamente AF_PACKET en modo IDS.

### 24.3 Configuración inicial

Se conservó una copia de fábrica:

```text
/etc/suricata/suricata.yaml.factory-8.0.3
```

Cambios aplicados en `/etc/suricata/suricata.yaml`:

```yaml
HOME_NET: "[10.30.0.0/24,10.20.0.20/32]"
EXTERNAL_NET: "!$HOME_NET"
community-id: true

af-packet:
  - interface: ens35
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes
```

Se mantuvieron activos `fast.log`, `eve.json`, `stats.log` y los eventos EVE necesarios para alertas, anomalías, HTTP, DNS, TLS, SSH, flujos y estadísticas.

Kali (`10.20.0.100`) queda fuera de `HOME_NET`. Así, las reglas ET con dirección `$EXTERNAL_NET -> $HOME_NET` pueden evaluar sus pruebas contra la DMZ. El Cliente legítimo se incluye explícitamente como `10.20.0.20/32`.

Se comprobó que `ens38` mantenía TSO, GSO y GRO activos. Se creó y habilitó `/etc/systemd/system/ppi-disable-offload.service` para deshabilitar TSO, GSO, GRO y LRO tanto en `ens35` como en `ens38`, antes de iniciar Suricata. `ethtool -k` confirmó los cuatro valores en `off` para ambas interfaces. Esto reduce el riesgo de que agregaciones del sistema invitado distorsionen tamaños y conteos de paquetes usados después por el pipeline de features.

### 24.4 Reglas

`suricata-update` descargó Emerging Threats Open para Suricata 8.0.3:

```text
67,977 reglas totales procesadas
52,043 reglas habilitadas
15 reglas deshabilitadas
136 reglas habilitadas por dependencias flowbit
```

Se añadió `local.rules` con SID `1000001` para una prueba controlada de ICMP. Esta regla identifica tráfico de validación y no debe interpretarse como ataque.

Los archivos reproducibles se guardan en `configs/suricata/`.

### 24.5 Prueba de configuración y servicio

Se ejecutó:

```bash
suricata -T -c /etc/suricata/suricata.yaml
systemctl enable --now suricata
```

Resultados:

```text
52,044 reglas cargadas correctamente, incluyendo la regla local
0 reglas fallidas
servicio active y enabled
6 hilos de captura AF_PACKET sobre ens35
aproximadamente 428 MiB de RAM al inicio
```

El Sensor tiene una actualización de kernel pendiente, desde `7.0.0-14` hacia `7.0.0-27`. No se reinició durante esta fase para no mezclar la validación de Suricata con un cambio de kernel.

### 24.6 Prueba positiva de alerta

Desde el Cliente se enviaron tres solicitudes ICMP hacia `10.30.0.10`. `eve.json` registró tres alertas:

```text
signature_id: 1000001
signature: PPI LAB ICMP TEST
action: allowed
src_ip: 10.20.0.20
dest_ip: 10.30.0.10
```

La acción `allowed` confirma que Suricata funciona como IDS pasivo y no como IPS.

### 24.7 Hallazgo de enrutamiento y corrección

La primera solicitud HTTP llegó al Servidor, pero su respuesta tomó la ruta externa debido a la presencia de dos gateways predeterminados. `ip route get 10.20.0.20` seleccionaba `172.17.25.121` por `ens34`, creando tráfico asimétrico.

Se creó `/etc/netplan/99-ppi-return-route.yaml` con una ruta de retorno:

```yaml
network:
  version: 2
  ethernets:
    ens38:
      routes:
        - to: 10.20.0.0/24
          via: 10.30.0.1
```

La ruta aplicada es:

```text
10.20.0.0/24 via 10.30.0.1 dev ens38
```

Después de aplicarla, `ip route get 10.20.0.20` confirmó origen `10.30.0.10` y siguiente salto `10.30.0.1`. Esta ruta explícita reemplaza la suposición anterior de que el gateway DMZ sería seleccionado siempre. Su presencia en Netplan demuestra configuración persistente, pero la validación posterior a reinicio sigue pendiente.

Cliente y Kali conservan un gateway externo, pero `ip route get 10.30.0.10` selecciona sus rutas más específicas mediante `10.20.0.1`. El Sensor tiene ambas redes conectadas directamente. Esto asegura el camino para destinos experimentales; no elimina la posibilidad de usar deliberadamente las direcciones `172.17.25.x`, por lo que las NIC externas deberán desconectarse antes del dataset final.

### 24.8 Prueba de capa 7

Se levantó temporalmente `python3 -m http.server` en `10.30.0.10:8080` y se realizó desde el Cliente:

```text
GET /?ppi=suricata-validation-2 HTTP/1.1
```

El servidor respondió `200` con 510 bytes. Suricata registró:

- `event_type=http`;
- origen `10.20.0.20` y destino `10.30.0.10:8080`;
- método, URL, agente de usuario, tipo de contenido, estado y longitud;
- `flow_id` y `community_id` para correlación.

Emerging Threats generó `ET INFO Python SimpleHTTP ServerBanner`, severidad 3. Es una alerta informativa coherente con el servidor temporal y no evidencia un ataque. La regla ICMP SID `1000001` no coincidió con el flujo HTTP.

Esta última comprobación funciona como prueba negativa específica de la regla local: un flujo TCP/HTTP legítimo no produjo el SID ICMP `1000001`. Todavía no constituye una prueba integral de falsos positivos del ruleset ET.

### 24.9 Salud inicial

La estadística posterior registró:

```text
capture.kernel_drops: 0
decoder.invalid: 0
detect.alert_queue_overflow: 0
```

Estos valores corresponden a tráfico liviano de validación. Todavía deben repetirse bajo tráfico legítimo pesado y concurrencia antes de afirmar que el Sensor no pierde paquetes.

Durante la validación se observaron realmente eventos `alert`, `http`, `fileinfo`, `flow` y `stats`. DNS, TLS, SSH y anomalías están configurados, pero aún requieren pruebas específicas antes de declararlos validados.

Estado: **baseline de Suricata instalado, activo y validado con ICMP y HTTP; reinicio controlado, ataques reales, protocolos restantes y pruebas de carga pendientes**.
