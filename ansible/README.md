# Automatización del laboratorio con Ansible

## Estado

Primera base del controlador Ansible. En esta etapa se incluyen configuración, inventario y verificaciones que no modifican las máquinas remotas. Los roles de red, Suricata, servidor, cliente y generador de tráfico se incorporarán después de crear las VMs y confirmar sus interfaces.

## Requisitos del controlador

- Ubuntu o sistema GNU/Linux.
- Python 3.12–3.14.
- Acceso directo a `PPI-MGMT` desde `10.10.10.10`.
- Llave SSH por host o una llave de automatización protegida.
- Usuario remoto `useransible`, sin contraseñas almacenadas en Git.

Se utiliza `ansible-core` 2.21 porque soporta Python 3.14 en el controlador. Las dependencias se instalan dentro de `.venv`; no se modifica el Python global.

## Estructura inicial

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

## Preparar el controlador

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r ansible/requirements-controller.txt
ansible-galaxy collection install -r ansible/requirements.yml -p ansible/.collections
```

Si Ubuntu informa que `ensurepip` no está disponible, se debe instalar previamente el paquete correspondiente a la versión del controlador, por ejemplo `python3.14-venv`. Como alternativa controlada puede inicializarse `pip` dentro de `.venv` con el bootstrap oficial de PyPA, sin modificar el Python global.

## Validar configuración e inventario

Todos los comandos se ejecutan desde `ansible/` para que se aplique `ansible.cfg`:

```bash
cd ansible
../.venv/bin/ansible-inventory --graph
../.venv/bin/ansible-playbook playbooks/00-validar-controlador.yml
```

Esta validación es local y puede ejecutarse antes de crear las VMs.

## Comprobar VMs

Cuando las cuatro VMs administradas existan y tengan acceso SSH:

```bash
cd ansible
../.venv/bin/ansible-playbook playbooks/01-comprobar-conectividad.yml
```

El playbook solamente espera SSH, ejecuta `ansible.builtin.ping` y consulta `id`. No instala paquetes, no cambia red y no usa `sudo`.

## Primera validación registrada

El 19 de julio de 2026 se validó esta base en VM01:

- `ansible-core`: 2.21.2.
- Python del controlador: 3.14.4.
- Inventario: sensor, servidor, Kali y cliente presentes.
- Redes: `PPI-MGMT`, `PPI-LAN` y `PPI-DMZ` coherentes con la arquitectura.
- Comprobación sintáctica: PASS en los dos playbooks.
- Preflight local: 5 tareas `ok`, 0 cambios, 0 fallos.

La conectividad remota queda pendiente hasta que las cuatro VMs administradas hayan sido creadas y conectadas a `PPI-MGMT`.

## Cuenta técnica del laboratorio

El inventario utiliza la cuenta `useransible` y la clave privada local:

```text
~/.ssh/id_ed25519_ppi_ansible
```

La clave privada existe solamente en VM01 y está excluida de Git. Su huella es:

```text
SHA256:pFBXQ3XD4yfZvhDvuh9CTP4+qPCEPr2Q+F0V7TOnAN4
```

La clave pública que se instala en las VMs administradas es:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB4FMAbIxw5Ddov41uYfLo3vYayyXhrTV/uHhCx8RM76 ppi-ansible-controller
```

Desde la consola de cada VM Linux se creará inicialmente la cuenta y se instalará esa clave pública. No se copiará la clave privada y no se registrará una contraseña en el repositorio.

### Validación de red de sensor y servidor

El 19 de julio de 2026 se comprobó desde VM01:

| Componente | Interfaz/IP de gestión | ICMP | SSH | Huella ED25519 observada |
|---|---|---|---|---|
| VM01 Admin | `ens37` — 10.10.10.10/24 | Local | Local | — |
| VM02 Sensor | 10.10.10.20/24 | 0 % de pérdida | Puerto 22 abierto | `SHA256:s1CuoCRHEeT82iJqoZ2pupT4A5u6tH58TDXevghZG68` |
| VM03 Servidor | 10.10.10.30/24 | 0 % de pérdida | Puerto 22 abierto | `SHA256:vCo7DpwfQbD7KczXGskpmPzpqwDgfPtO1Pdj133Uh2o` |
| VM04 Kali | 10.10.10.40/24 | 0 % de pérdida | Puerto 22 abierto | `SHA256:iEAn7Mbd+mP0tepxP8xkEQXSyyh6F9Gp/OB6SG5FGrU` |
| VM05 Cliente Desktop | 10.10.10.50/24 | 0 % de pérdida | Puerto 22 abierto | `SHA256:Bf4kznuAqHYEHj3pEUYMgrGP1bF173n5KJHKS4mZyu4` |

Latencia ICMP observada:

- Sensor: promedio 0.319 ms.
- Servidor: promedio 0.333 ms.
- Kali: promedio 0.283 ms.
- Cliente Desktop: promedio 0.309 ms.

Las huellas deberán confirmarse desde la consola de cada VM antes de agregarlas al archivo `known_hosts`. La autenticación de Ansible queda pendiente de crear la clave exclusiva del controlador y el usuario remoto.

## Seguridad

- No desactivar `host_key_checking`.
- Registrar previamente las huellas SSH reales de las VMs.
- No guardar contraseñas, claves privadas ni archivos de Vault en Git.
- Utilizar Ansible Vault cuando se incorporen secretos cifrados.
- La VM Kali aceptará administración desde `10.10.10.10`, pero no iniciará conexiones hacia otros nodos de gestión.
