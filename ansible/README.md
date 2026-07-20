# Automatización del laboratorio con Ansible

## Estado

Primera base del controlador Ansible. En esta etapa se incluyen configuración, inventario y verificaciones que no modifican las máquinas remotas. Los roles de red, Suricata, servidor, cliente y generador de tráfico se incorporarán después de crear las VMs y confirmar sus interfaces.

## Requisitos del controlador

- Ubuntu o sistema GNU/Linux.
- Python 3.12–3.14.
- Acceso directo a `PPI-MGMT` desde `10.10.10.10`.
- Llave SSH por host o una llave de automatización protegida.
- Usuario remoto `ansible`, inicialmente sin contraseñas almacenadas en Git.

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

## Seguridad

- No desactivar `host_key_checking`.
- Registrar previamente las huellas SSH reales de las VMs.
- No guardar contraseñas, claves privadas ni archivos de Vault en Git.
- Utilizar Ansible Vault cuando se incorporen secretos cifrados.
- La VM Kali aceptará administración desde `10.10.10.10`, pero no iniciará conexiones hacia otros nodos de gestión.
