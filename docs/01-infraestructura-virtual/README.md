# Infraestructura virtual y recursos del laboratorio

## 1. Propósito

Este documento define las máquinas virtuales y los recursos necesarios para implementar y validar el sistema de detección temprana de comportamientos anómalos. El laboratorio se ejecutará sobre un único hipervisor VMware ESXi y debe soportar tráfico normal, tráfico legítimo pesado, ataques controlados, captura con Suricata, inferencia de los modelos y recolección de evidencias.

Esta es la primera planificación de infraestructura de la versión final. Los valores podrán ajustarse después de medir CPU, memoria, almacenamiento y pérdida de paquetes durante las pruebas de carga.

## 2. Capacidad disponible del hipervisor

La capacidad se obtuvo de la captura del cliente web de ESXi tomada el 16 de julio de 2026.

| Recurso del host | Capacidad | Uso observado | Disponible observado |
|---|---:|---:|---:|
| CPU | 11.4 GHz | 3.5 GHz (31 %) | 7.8 GHz |
| Memoria RAM | 63.63 GB | 5.99 GB (9 %) | 57.63 GB |
| Almacenamiento | 825.75 GB | 64.3 GB (8 %) | 761.45 GB |
| Versión | VMware ESXi 8.0 Update 3 | — | — |

El host está operando en modo de evaluación. Antes de una demostración formal se debe verificar la vigencia de la licencia y las funciones que continuarán disponibles.

## 3. Criterios de dimensionamiento

- No asignar toda la RAM física a las máquinas virtuales.
- Reservar recursos para ESXi, caché, procesos del host y crecimiento temporal.
- Priorizar CPU y RAM para el sensor Suricata/ML.
- Utilizar discos `thin provision` durante el laboratorio y vigilar el crecimiento real del datastore.
- Evitar ejecutar simultáneamente entrenamiento intensivo, generación de gráficas y ataques de máxima tasa.
- Mantener la red administrativa separada del tráfico experimental.
- Ejecutar ataques únicamente dentro de los segmentos aislados del laboratorio.

## 4. Máquinas virtuales propuestas

### VM01 — Administración y Ansible

Corresponde a la máquina Ubuntu administrativa actualmente utilizada para documentación, GitHub y acceso remoto mediante RustDesk.

Funciones:

- Controlador de Ansible.
- Administración de las demás VMs por SSH o WinRM.
- Repositorio Git y documentación.
- RustDesk para acceso remoto.
- Coordinación de pruebas y recolección de evidencias.

Recursos:

| Recurso | Asignación |
|---|---:|
| vCPU | 2 |
| RAM | 8 GB |
| Disco | 80 GB thin |
| Interfaces | 2: red actual y `PPI-MGMT` |
| IP externa propuesta | 172.17.25.20/24 |
| IP de gestión del laboratorio | 10.10.10.10/24 |

### VM02 — Sensor Suricata y motor ML

Es el componente principal del laboratorio y debe recibir la mayor asignación de recursos.

Funciones:

- Captura y análisis con Suricata.
- Agregación temporal de eventos de capas 3, 4 y 7.
- Isolation Forest y predictor complementario.
- Motor de decisión `PERMIT`, `LIMIT` y `BLOCK`.
- Dashboard, alertas y registros.
- Medición de latencia y paquetes descartados.

Recursos:

| Recurso | Asignación |
|---|---:|
| vCPU | 6 |
| RAM | 16 GB |
| Disco | 160 GB thin |
| Interfaces | 3: gestión, LAN experimental y DMZ |
| IP de gestión propuesta | 10.10.10.20/24 |

El sensor tendrá prioridad durante las pruebas. La asignación de 6 vCPU y 16 GB permite procesar eventos multicapa y mantener ventanas temporales. Si Suricata registra pérdida de paquetes sostenida, se revisará primero la configuración de captura, `CPU ready` y afinidad de hilos antes de asignar más vCPU.

### VM03 — Servidor protegido

Funciones:

- Servicios HTTP/HTTPS y SSH.
- Recepción de archivos grandes mediante HTTP, SCP o SFTP.
- Destino de las pruebas normales y de ataque.
- Registro de disponibilidad y tiempos de respuesta.

Recursos:

| Recurso | Asignación |
|---|---:|
| vCPU | 2 |
| RAM | 4 GB |
| Disco | 120 GB thin |
| Interfaces | 2: gestión y `PPI-DMZ` |
| IP de gestión | 10.10.10.30/24 |
| IP de servicio | 10.30.0.10/24 |

El disco de 120 GB permite mantener el sistema operativo, servicios, archivos de prueba de distintos tamaños, cargas y descargas simultáneas, copias temporales y registros del servidor. Durante cada campaña se controlará el espacio libre y se eliminarán solamente los artefactos temporales que ya hayan sido recolectados por la VM administrativa.

### VM04 — Kali Linux

Funciones:

- Generación controlada de SYN flood, UDP flood e ICMP flood.
- Escaneo de puertos.
- Pruebas controladas de intentos de autenticación.
- Abuso HTTP y escenarios mixtos.

Recursos:

| Recurso | Asignación |
|---|---:|
| vCPU | 2 |
| RAM | 6 GB |
| Disco | 60 GB thin |
| Interfaces | 2: gestión y `PPI-LAN` |
| IP de gestión | 10.10.10.40/24 |
| IP de ataque | 10.20.0.100/24 |

La VM debe operar preferentemente sin escritorio durante las corridas para dedicar sus recursos a la generación de tráfico.

### VM05 — Cliente legítimo

Puede utilizar Ubuntu Desktop o Windows según la licencia disponible. Su función es generar tráfico normal independiente del atacante.

Funciones:

- Navegación y solicitudes HTTP/HTTPS.
- Transferencias SCP/SFTP o SMB.
- Descargas de archivos grandes.
- Streaming y tráfico sostenido.
- Pruebas con paquetes de 500 a 1500 bytes.
- Tráfico normal concurrente durante los ataques.

Recursos:

| Recurso | Asignación |
|---|---:|
| vCPU | 4 |
| RAM | 8 GB |
| Disco | 100 GB thin |
| Interfaces | 2: gestión y `PPI-LAN` |
| IP de gestión | 10.10.10.50/24 |
| IP de tráfico legítimo | 10.20.0.20/24 |

## 5. Resumen de recursos asignados

| Máquina | vCPU | RAM | Disco thin |
|---|---:|---:|---:|
| VM01 Administración/Ansible | 2 | 8 GB | 80 GB |
| VM02 Sensor Suricata/ML | 6 | 16 GB | 160 GB |
| VM03 Servidor protegido | 2 | 4 GB | 120 GB |
| VM04 Kali Linux | 2 | 6 GB | 60 GB |
| VM05 Cliente legítimo | 4 | 8 GB | 100 GB |
| **Total** | **16 vCPU** | **42 GB** | **520 GB** |

### Margen conservado

| Recurso | Capacidad del host | Asignación planificada | Margen aproximado |
|---|---:|---:|---:|
| RAM | 63.63 GB | 42 GB | 21.63 GB |
| Almacenamiento | 825.75 GB | 520 GB thin | 305.75 GB lógicos |

Los 16 vCPU representan sobreasignación controlada respecto de la capacidad física expresada en GHz. Es aceptable para este laboratorio siempre que no todas las VMs utilicen el 100 % de CPU simultáneamente. Durante ataques de alta tasa se detendrán tareas no esenciales y se registrará `CPU ready` del hipervisor para comprobar que la contención no invalide los resultados. No se aumentará nuevamente el total de vCPU hasta confirmar el número de sockets, núcleos e hilos físicos del host.

## 6. Segmentos virtuales

| Port group | Red propuesta | Gateway | Uplink físico | Finalidad |
|---|---|---|---|---|
| Red actual de ESXi | 172.17.25.0/24 | Gateway actual de la red | Sí | ESXi, Internet, GitHub y RustDesk |
| `PPI-MGMT` | 10.10.10.0/24 | Sin gateway por defecto | No requerido | Ansible, SSH y administración interna |
| `PPI-LAN` | 10.20.0.0/24 | 10.20.0.1 | No requerido | Origen del tráfico normal y de ataque |
| `PPI-DMZ` | 10.30.0.0/24 | 10.30.0.1 | No requerido | Red del servidor protegido |

El sensor se colocará entre `PPI-LAN` y `PPI-DMZ`. El tráfico administrativo no debe formar parte del dataset de entrenamiento ni de las mediciones operativas.

### 6.1 Matriz de interfaces e IP

Los nombres `ens160`, `ens192` y `ens224` son la convención prevista para Ubuntu. Después de crear cada VM se confirmarán con `ip link`, porque VMware y el sistema operativo pueden asignar nombres diferentes.

| VM | NIC | Interfaz prevista | Port group | Dirección | Gateway predeterminado | Uso |
|---|---:|---|---|---|---|---|
| VM01 Admin/Ansible | 1 | `ens160` | Red actual de ESXi | 172.17.25.20/24 | Gateway actual de 172.17.25.0/24 | Internet, GitHub, RustDesk y acceso al host |
| VM01 Admin/Ansible | 2 | `ens192` | `PPI-MGMT` | 10.10.10.10/24 | Ninguno | Administración de las VMs |
| VM02 Sensor | 1 | `ens160` | `PPI-MGMT` | 10.10.10.20/24 | Ninguno | Ansible, SSH, dashboard y registros |
| VM02 Sensor | 2 | `ens192` | `PPI-LAN` | 10.20.0.1/24 | Ninguno | Entrada desde cliente y Kali |
| VM02 Sensor | 3 | `ens224` | `PPI-DMZ` | 10.30.0.1/24 | Ninguno | Salida hacia el servidor protegido |
| VM03 Servidor | 1 | `ens160` | `PPI-MGMT` | 10.10.10.30/24 | Ninguno | Ansible y SSH administrativo |
| VM03 Servidor | 2 | `ens192` | `PPI-DMZ` | 10.30.0.10/24 | 10.30.0.1 | HTTP/HTTPS, SSH y transferencias de prueba |
| VM04 Kali | 1 | `eth0` | `PPI-MGMT` | 10.10.10.40/24 | Ninguno | Administración entrante desde Ansible |
| VM04 Kali | 2 | `eth1` | `PPI-LAN` | 10.20.0.100/24 | 10.20.0.1 | Generación controlada de ataques |
| VM05 Cliente | 1 | `ens160` o adaptador Windows | `PPI-MGMT` | 10.10.10.50/24 | Ninguno | Ansible, SSH o WinRM |
| VM05 Cliente | 2 | `ens192` o adaptador Windows | `PPI-LAN` | 10.20.0.20/24 | 10.20.0.1 | Generación de tráfico legítimo |

La dirección `172.17.25.28` observada en la captura pertenece al host ESXi y no debe asignarse a ninguna VM. Antes de utilizar `172.17.25.20` en VM01 se comprobará que no exista otro equipo con esa dirección. Si está ocupada, se seleccionará una IP libre de la misma red o se conservará la configuración actual por DHCP.

### 6.2 Administración con Ansible

Ansible utilizará exclusivamente las direcciones de `PPI-MGMT`:

| Grupo Ansible | Host | IP de administración |
|---|---|---|
| `sensor` | VM02 | 10.10.10.20 |
| `servidores` | VM03 | 10.10.10.30 |
| `atacantes` | VM04 | 10.10.10.40 |
| `clientes` | VM05 | 10.10.10.50 |

La VM01 accede directamente a esta red mediante `10.10.10.10`. Las interfaces de gestión de VM02–VM05 no tendrán gateway predeterminado, evitando que el tráfico experimental o de Internet utilice accidentalmente `PPI-MGMT`.

### 6.3 Recorrido del tráfico experimental

```text
Cliente 10.20.0.20  ─┐
                       ├─► Sensor 10.20.0.1 / 10.30.0.1 ─► Servidor 10.30.0.10
Kali    10.20.0.100 ─┘
```

El sensor habilitará el reenvío entre `PPI-LAN` y `PPI-DMZ`. Cliente y Kali utilizarán `10.20.0.1` como gateway, mientras que el servidor utilizará `10.30.0.1`. Esto obliga a que las conexiones experimentales atraviesen Suricata.

### 6.4 El sensor como router y gateway

No se desplegará una VM router adicional en la primera versión del laboratorio. La VM02 Sensor asumirá simultáneamente las funciones de:

- Router entre `PPI-LAN` y `PPI-DMZ`.
- Gateway de los equipos experimentales.
- Sensor Suricata.
- Punto de aplicación de las decisiones `PERMIT`, `LIMIT` y `BLOCK`.

Los dos gateways pertenecen a interfaces diferentes de la misma VM:

| Segmento | Interfaz del sensor | IP usada como gateway |
|---|---|---|
| `PPI-LAN` | `ens192` prevista | 10.20.0.1 |
| `PPI-DMZ` | `ens224` prevista | 10.30.0.1 |

El recorrido lógico será:

```text
PPI-LAN                                            PPI-DMZ
10.20.0.0/24                                       10.30.0.0/24

Cliente 10.20.0.20 ─┐                           ┌─ Servidor 10.30.0.10
                     ├─► Sensor/Router ─────────┘
Kali 10.20.0.100  ─┘   .20.0.1 / .30.0.1
```

Cuando un equipo de `PPI-LAN` intenta llegar a `10.30.0.10`, entrega el paquete a `10.20.0.1`. El sensor lo analiza y, si la política lo permite, lo reenvía por `10.30.0.1`. La respuesta del servidor utiliza `10.30.0.1` y vuelve a atravesar el sensor.

#### Gateway predeterminado por máquina

Cada sistema tendrá como máximo un gateway predeterminado. Las interfaces de `PPI-MGMT` no configurarán gateway.

| VM | Gateway predeterminado | Motivo |
|---|---|---|
| VM01 Admin/Ansible | Gateway actual de `172.17.25.0/24` | Internet, GitHub, ESXi y RustDesk |
| VM02 Sensor | Ninguno durante la prueba aislada | LAN y DMZ están conectadas directamente |
| VM03 Servidor | 10.30.0.1 | Salida y respuestas mediante el sensor |
| VM04 Kali | 10.20.0.1 | Ataques controlados mediante el sensor |
| VM05 Cliente | 10.20.0.1 | Tráfico legítimo mediante el sensor |

No se configurará un segundo gateway predeterminado en las NIC de gestión. Esto evita rutas ambiguas y asegura que el tráfico experimental no evada Suricata.

#### Reenvío IPv4

El sensor deberá habilitar el enrutamiento IPv4 de Linux. La configuración persistente prevista es:

```text
net.ipv4.ip_forward=1
```

La implementación con Ansible deberá:

1. Aplicar el parámetro mediante `sysctl`.
2. Comprobar que continúa activo después de reiniciar.
3. Permitir en el firewall solamente el tráfico requerido entre LAN y DMZ.
4. Permitir el retorno de conexiones establecidas.
5. Registrar y bloquear tráfico no autorizado.
6. Confirmar que el servidor deja de ser alcanzable si se detiene el enrutamiento del sensor.

#### Acceso temporal a Internet

Durante la instalación puede habilitarse temporalmente una ruta de salida, NAT o proxy para descargar paquetes. Durante las capturas y pruebas finales esa salida se desactivará o controlará para que el tráfico externo no contamine el dataset.

### 6.5 Controles de seguridad de gestión

- VM01 podrá iniciar SSH o WinRM hacia todas las IP de `PPI-MGMT`.
- VM04 Kali aceptará administración desde `10.10.10.10`, pero no podrá iniciar conexiones hacia las otras IP administrativas.
- No se ejecutarán ataques contra `10.10.10.0/24` ni `172.17.25.0/24`.
- La red de gestión no se incluirá en las capturas utilizadas por el modelo.
- Las llaves SSH y secretos de Ansible se gestionarán fuera del repositorio.

## 7. Relación con las observaciones del jurado

La VM cliente y el servidor permitirán producir tráfico legítimo pesado mediante descargas, transferencias de archivos, streaming e `iperf3`. Esto ampliará el rango normal del entrenamiento con paquetes entre 500 y 1500 bytes.

La VM sensor dispone de recursos para procesar eventos Suricata de tipo `flow`, `alert`, `http`, `ssh`, `dns` y `tls`. A partir de esos eventos se construirán variables temporales de:

- Capa 3: proporción de IPs únicas y destinos contactados.
- Capa 4: frecuencia de SYN, proporción SYN/SYN-ACK y puertos únicos.
- Capa 7: intentos fallidos de autenticación y frecuencia de solicitudes HTTP.

## 8. Criterios para validar el dimensionamiento

Antes de declarar definitivos los recursos se ejecutará una prueba piloto y se aceptará la configuración si cumple:

- Uso medio de RAM del host menor al 80 %.
- Sin `swap` sostenido en el sensor.
- CPU del sensor menor al 85 % durante la mayor parte de la corrida.
- `CPU ready` sin contención sostenida que afecte las mediciones.
- Sin crecimiento del datastore por encima del 80 %.
- Pérdida de paquetes de Suricata medida y documentada.
- Dashboard y motor disponibles durante las pruebas.
- Servidor protegido capaz de mantener tráfico legítimo pesado concurrente.

Si estos criterios no se cumplen, los recursos se ajustarán usando mediciones reales y el cambio quedará registrado en este documento.

## 9. Inventario real detectado con Ansible

El 19 de julio de 2026 se ejecutó una auditoría sin privilegios sobre las cuatro VMs administradas. Los valores de RAM y disco corresponden a lo visible dentro del sistema invitado; pueden ser ligeramente inferiores a la asignación mostrada por ESXi debido a memoria reservada, particiones y formato del sistema de archivos.

| VM | Sistema | vCPU detectadas | RAM visible | Disco raíz visible | Espacio libre |
|---|---|---:|---:|---:|---:|
| VM02 Sensor | Ubuntu 26.04 | 6 | 15,474 MB | 76.7 GB | 65.9 GB |
| VM03 Servidor | Ubuntu 26.04 | 2 | 3,398 MB | 57.3 GB | 47.3 GB |
| VM04 Kali | Kali 2026.2 | 4 | 5,927 MB | 55.7 GB | 38.3 GB |
| VM05 Cliente | Ubuntu 26.04 | 2 | 3,398 MB | 57.7 GB | 44.8 GB |

### 9.1 Interfaces reales

| VM | Red externa temporal | PPI-MGMT | PPI-LAN | PPI-DMZ |
|---|---|---|---|---|
| Sensor | `ens34` — 172.17.25.111 | `ens39` — 10.10.10.20 | `ens35` — 10.20.0.1 | `ens38` — 10.30.0.1 |
| Servidor | `ens34` — 172.17.25.112 | `ens35` — 10.10.10.30 | — | `ens38` — 10.30.0.10 |
| Kali | `eth0` — 172.17.25.113 | `eth2` — 10.10.10.40 | `eth1` — 10.20.0.100 | — |
| Cliente | `ens34` — 172.17.25.114 | `ens35` — 10.10.10.50 | `ens38` — 10.20.0.20 | — |

### 9.2 Diferencias respecto del diseño

| VM | Recurso | Planificado | Detectado | Acción |
|---|---|---:|---:|---|
| Sensor | Disco | 160 GB | 76.7 GB raíz | Ampliar disco virtual y sistema de archivos |
| Servidor | Disco | 120 GB | 57.3 GB raíz | Ampliar disco virtual y sistema de archivos |
| Kali | vCPU | 2 | 4 | Aceptar 4 o reducir después de medir contención |
| Kali | Disco | 60 GB | 55.7 GB raíz | Sin cambio urgente; verificar tamaño virtual |
| Cliente | vCPU | 4 | 2 | Aumentar a 4 antes de tráfico pesado |
| Cliente | RAM | 8 GB | 3,398 MB visibles | Aumentar asignación antes de tráfico pesado |
| Cliente | Disco | 100 GB | 57.7 GB raíz | Ampliar disco virtual y sistema de archivos |

### 9.3 Interfaces externas temporales

Sensor, servidor, Kali y cliente conservan una NIC en `172.17.25.0/24`. Estas interfaces son útiles para instalar paquetes durante el aprovisionamiento, pero constituyen una ruta alternativa que puede evitar el sensor y contaminar las capturas.

Antes de la validación experimental final se deberá:

1. Confirmar que todas las dependencias están instaladas.
2. Desconectar en ESXi las NIC externas de VM02–VM05, o eliminar sus rutas e IP.
3. Mantener la red externa solamente en VM01 Admin.
4. Confirmar que Cliente y Kali llegan al servidor exclusivamente mediante `10.20.0.1`.
5. Confirmar que el servidor responde exclusivamente mediante `10.30.0.1`.

No se retirarán las NIC externas mediante automatización remota hasta disponer de acceso confirmado por `PPI-MGMT` y un procedimiento de recuperación por consola ESXi.
