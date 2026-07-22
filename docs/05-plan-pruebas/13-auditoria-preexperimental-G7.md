# Auditoría preexperimental G7 — 22 de julio de 2026

Esta auditoría de solo lectura se ejecutó desde VM01 después de reiniciar y validar el nuevo volumen de evidencias. Su objetivo fue decidir si la topología podía comenzar las 145 campañas oficiales `f1-normal-v2`. Sustituye cualquier condición temporal de aptitud registrada en G0: el reinicio demostró que bajar interfaces únicamente dentro del sistema operativo no es un aislamiento persistente.

## Alcance y trazabilidad

- Fecha de ejecución: `2026-07-22`, zona `America/Lima`.
- Controlador: VM01, `10.10.10.10` en PPI-MGMT y `172.17.25.155` en la red externa.
- Inventario: `ansible/inventories/lab/hosts.yml`.
- Comprobaciones base: `01-comprobar-conectividad.yml` y `02-auditar-recursos.yml`.
- Los JSON runtime se guardaron en `artifacts/preflight/`, ruta excluida de Git.
- No se inició ninguna campaña ni captura oficial. Los pings, conexiones TCP y solicitudes HTTP de esta auditoría son tráfico de control y no pertenecen al dataset.

Comandos base reproducibles desde la raíz del repositorio:

```bash
cd ansible
../.venv/bin/ansible-playbook playbooks/01-comprobar-conectividad.yml
../.venv/bin/ansible-playbook playbooks/02-auditar-recursos.yml
../.venv/bin/ansible all -m shell -a 'ip -br link; ip -br -4 address; ip route'
```

El módulo `shell` puede presentar `CHANGED` porque ejecutó la consulta; no significa que haya modificado interfaces o rutas. Las pruebas de ruta y puerto se ejecutaron con `ip route get`, `ping`, `curl` y `nc` usando tiempos de espera acotados.

## Recursos observados

| VM | Sistema | vCPU | RAM observada | Raíz total/libre | IP experimentales y de gestión |
|---|---|---:|---:|---:|---|
| VM02 Sensor | Ubuntu 26.04 | 6 | 15,474 MB | 153.9/139.1 GiB | `10.10.10.20`, `10.20.0.1`, `10.30.0.1` |
| VM03 Servidor | Ubuntu 26.04 | 2 | 3,398 MB | 114.8/101.2 GiB | `10.10.10.30`, `10.30.0.10-.12` |
| VM04 Kali | Kali 2026.2 | 4 | 5,927 MB | 55.7/38.3 GiB | `10.10.10.40`, `10.20.0.100` |
| VM05 Cliente | Ubuntu 26.04 | 4 | 7,423 MB | 97.1/82.0 GiB | `10.10.10.50`, `10.20.0.20` |

VM01 conserva 4 vCPU, aproximadamente 11 GiB de RAM y 51 GiB libres en la raíz. El volumen dedicado `/dev/sdb` está montado en `/srv/ppi-evidence` con 140 GiB libres y opciones `rw,nosuid,nodev,noexec,noatime`. RustDesk se encontró `active` y `enabled`.

## Resultados positivos

1. Ansible alcanzó las cuatro VMs por PPI-MGMT. `ping` e identidad de `useransible` pasaron sin fallos.
2. Los cinco equipos usan `America/Lima` y reportan NTP sincronizado.
3. Cliente y Kali resolvieron `10.30.0.10` mediante `10.20.0.1`, por lo que el camino de datos atraviesa el Sensor.
4. Cliente y Kali obtuvieron `3/3` respuestas ICMP y HTTP `200` desde `10.30.0.10`.
5. Las VIP `10.30.0.10`, `.11` y `.12` respondieron HTTP `200`. En `.11` y `.12` continuaron cerrados desde LAN los puertos 22, 53, 443 y 5201.
6. Sensor: `Suricata`, `chrony` y SSH activos; `net.ipv4.ip_forward=1`.
7. Servidor: NGINX, dnsmasq, iperf3, firewall PPI, chrony y SSH activos.
8. Checkpoint de Suricata: `capture.kernel_packets=5776496`, `kernel_drops=0`, `decoder.invalid=0` y `alert_queue_overflow=0`.

## Hallazgo bloqueante: ruta externa que evita el Sensor

El Servidor recuperó después del reinicio su interfaz externa `ens34=172.17.25.112/24`, MAC `00:0c:29:15:ad:a7`, y una ruta por defecto por esa interfaz. VM01 alcanzó directamente esa IP:

- ICMP: `3/3`, 0 % de pérdida.
- TCP/22: abierto.
- TCP/53, 80, 443 y 5201: bloqueados.

El acceso SSH abierto es suficiente para demostrar la evasión. El flujo `172.17.25.155 -> 172.17.25.112` permanece en la red externa y no cruza `ens35`, interfaz que Suricata captura en el Sensor. No es válido alegar que todo el tráfico hacia VM03 es observable mientras esa ruta exista.

También permaneció activa `ens34=172.17.25.111/24` en el Sensor. Aunque esta interfaz sirve para mantenimiento, durante una campaña oficial agrega tráfico ajeno a la topología experimental y amplía la superficie de administración. VM01 ya puede administrar el Sensor por `10.10.10.20`, por lo que la interfaz externa no es necesaria durante las ventanas de captura.

Kali conservó configurada `172.17.25.113` en `eth0`, pero el enlace estaba `DOWN`. El Cliente tenía `ens34` `DOWN` y sin dirección. Desde ambos nodos, `172.17.25.112` produjo `Network is unreachable`. Esto reduce el riesgo inmediato, pero un estado `DOWN` del huésped no prueba que la NIC esté desconectada de forma persistente en ESXi.

## Decisión G7

**NO APTO para campañas oficiales.** La capacidad, el tiempo, los servicios y el camino interno pasan; el aislamiento topológico falla. No se ejecutará el canario oficial ni se construirán muestras de entrenamiento hasta cerrar el hallazgo.

Los cinco pilotos existentes son de propósito `calibration`. El ensamblador informa `0` campañas oficiales aceptadas, `5` calibraciones excluidas y `145` campañas `f1-normal-v2` faltantes. Por tanto, este hallazgo no contamina un dataset oficial ya aceptado; bloquea preventivamente su creación.

## Corrección requerida en ESXi

Antes de cambiar adaptadores, conservar acceso a la consola de cada VM. En **Editar configuración**, identificar por MAC y desmarcar **Conectado** y **Conectar al encender** para las NIC externas:

| VM | Interfaz | MAC externa | IP externa | Acción durante campañas |
|---|---|---|---|---|
| Sensor | `ens34` | `00:0c:29:f7:15:80` | `172.17.25.111` | desconectar |
| Servidor | `ens34` | `00:0c:29:15:ad:a7` | `172.17.25.112` | desconectar |
| Kali | `eth0` | `00:0c:29:52:db:60` | `172.17.25.113` | confirmar desconectada |
| Cliente | `ens34` | `00:0c:29:c5:ed:66` | antigua `.114` | confirmar desconectada |

No desconectar PPI-MGMT (`10.10.10.x`), PPI-LAN (`10.20.0.0/24`) ni PPI-DMZ (`10.30.0.0/24`). VM01 conserva Internet/RustDesk por su NIC externa y administra las demás VMs por PPI-MGMT.

La interfaz externa del Sensor puede reconectarse solo en una ventana de mantenimiento sin campaña activa. Después debe volver a desconectarse y repetirse el gate.

## Gate posterior a la corrección

Codex repetirá, en este orden:

1. Confirmar por `ip -br link` que las NIC externas están `DOWN`/sin portadora y por ESXi que **Conectado** y **Conectar al encender** están desmarcados. Una IP estática puede seguir visible en el huésped sin enlace; si ocurre, también se deshabilitará su perfil persistente.
2. Confirmar por `ip route` y una prueba negativa que ninguna de esas VMs posee una ruta externa utilizable.
3. Verificar SSH de VM01 a las cuatro IP PPI-MGMT.
4. Verificar desde VM01 que `172.17.25.111-.114` no son alcanzables por ICMP ni TCP/22.
5. Verificar desde Cliente y Kali que `ip route get 10.30.0.10` usa `10.20.0.1`.
6. Repetir ICMP, HTTP y controles negativos de las VIP.
7. Correlacionar un flujo interno acotado con el incremento de contadores/PCAP/EVE en `ens35` y comprobar cero drops.
8. Reiniciar o apagar/encender una VM representativa y confirmar que ESXi mantiene la NIC externa desconectada.
9. Ejecutar el ensamblador en modo auditoría y confirmar `0` oficiales aceptadas antes del canario.

Solo si los nueve controles pasan, G7 cambia a **APTO** y se autoriza una única campaña canario F1; las otras 144 siguen bloqueadas hasta validar su bundle.
