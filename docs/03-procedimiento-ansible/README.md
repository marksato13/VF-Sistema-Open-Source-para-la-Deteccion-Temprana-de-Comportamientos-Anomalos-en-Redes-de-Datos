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
| Crear `useransible` en sensor | PENDIENTE DE VALIDACIÓN | Comandos entregados para consola ESXi |
| Crear `useransible` en servidor | PENDIENTE DE VALIDACIÓN | Comandos entregados para consola ESXi |
| Conectividad IP con Kali | VALIDADO | 10.10.10.40 responde, 0 % de pérdida |
| Habilitar SSH en Kali | VALIDADO | Puerto 22 abierto el 19 de julio de 2026 |
| Crear `useransible` en Kali | PENDIENTE DE VALIDACIÓN | SSH activo; falta comprobar autenticación por clave |
| Conectividad IP con VM05 Cliente | VALIDADO | 10.10.10.50 responde, 0 % de pérdida |
| Habilitar SSH en VM05 Cliente | VALIDADO | Puerto 22 abierto el 19 de julio de 2026 |
| Crear `useransible` en VM05 Cliente | PENDIENTE DE VALIDACIÓN | SSH activo; falta comprobar autenticación por clave |
| Ejecutar ping de Ansible remoto | PENDIENTE | Requiere cuenta y clave instaladas |
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

La etapa se cerrará cuando sensor y servidor reporten:

```text
unreachable=0
failed=0
```

Después se diseñará un rol de privilegios mínimos y se automatizará la configuración de interfaces, enrutamiento y Suricata.

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
