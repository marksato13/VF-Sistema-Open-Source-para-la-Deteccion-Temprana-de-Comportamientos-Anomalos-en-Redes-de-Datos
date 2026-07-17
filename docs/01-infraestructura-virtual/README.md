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
| Interfaces | 1 en `PPI-MGMT` |
| IP propuesta | 10.10.10.10/24 |

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
| Disco | 60 GB thin |
| Interfaces | 1 en `PPI-DMZ` |
| IP propuesta | 10.30.0.10/24 |

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
| Interfaces | 1 en `PPI-LAN` |
| IP propuesta | 10.20.0.100/24 |

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
| Interfaces | 1 en `PPI-LAN` |
| IP propuesta | 10.20.0.20/24 |

## 5. Resumen de recursos asignados

| Máquina | vCPU | RAM | Disco thin |
|---|---:|---:|---:|
| VM01 Administración/Ansible | 2 | 8 GB | 80 GB |
| VM02 Sensor Suricata/ML | 6 | 16 GB | 160 GB |
| VM03 Servidor protegido | 2 | 4 GB | 60 GB |
| VM04 Kali Linux | 2 | 6 GB | 60 GB |
| VM05 Cliente legítimo | 4 | 8 GB | 100 GB |
| **Total** | **16 vCPU** | **42 GB** | **460 GB** |

### Margen conservado

| Recurso | Capacidad del host | Asignación planificada | Margen aproximado |
|---|---:|---:|---:|
| RAM | 63.63 GB | 42 GB | 21.63 GB |
| Almacenamiento | 825.75 GB | 460 GB thin | 365.75 GB lógicos |

Los 16 vCPU representan sobreasignación controlada respecto de la capacidad física expresada en GHz. Es aceptable para este laboratorio siempre que no todas las VMs utilicen el 100 % de CPU simultáneamente. Durante ataques de alta tasa se detendrán tareas no esenciales y se registrará `CPU ready` del hipervisor para comprobar que la contención no invalide los resultados. No se aumentará nuevamente el total de vCPU hasta confirmar el número de sockets, núcleos e hilos físicos del host.

## 6. Segmentos virtuales

| Port group | Red propuesta | Máquinas | Finalidad |
|---|---|---|---|
| `PPI-MGMT` | 10.10.10.0/24 | Admin y NIC de gestión del sensor | Ansible, SSH, Git y administración |
| `PPI-LAN` | 10.20.0.0/24 | Cliente, Kali y NIC LAN del sensor | Origen del tráfico experimental |
| `PPI-DMZ` | 10.30.0.0/24 | Servidor y NIC DMZ del sensor | Servicios protegidos |

El sensor se colocará entre `PPI-LAN` y `PPI-DMZ`. El tráfico administrativo no debe formar parte del dataset de entrenamiento ni de las mediciones operativas.

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
