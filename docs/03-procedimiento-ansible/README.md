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

Estado: **auditoría validada; quedan pendientes los ajustes de CPU, RAM y disco del Cliente antes de las pruebas de carga**.

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
