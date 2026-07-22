# Cierre operacional del aislamiento G7 — 22 de julio de 2026

Esta verificación se ejecutó después de desconectar en ESXi las NIC externas de VM02–VM05. No se reinició ninguna VM y no se inició una campaña oficial. El resultado permite separar dos afirmaciones:

- **aislamiento operacional actual:** APTO;
- **persistencia del aislamiento y autorización del canario oficial:** PENDIENTE.

## Estado de interfaces y rutas

| VM | NIC externa | Estado observado | Dirección/ruta externa |
|---|---|---|---|
| Sensor | `ens34`, `00:0c:29:f7:15:80` | `DOWN`, `NO-CARRIER` | sin IP y sin ruta |
| Servidor | `ens34`, `00:0c:29:15:ad:a7` | `DOWN`, `NO-CARRIER` | sin IP y sin ruta |
| Kali | `eth0`, `00:0c:29:52:db:60` | `DOWN` | conserva `.113` configurada, pero sin ruta utilizable |
| Cliente | `ens34`, `00:0c:29:c5:ed:66` | `DOWN` | sin IP y sin ruta |

Desde VM01, cada dirección `172.17.25.111`, `.112`, `.113` y `.114` quedó bloqueada tanto por ICMP como por TCP/22: ocho controles negativos pasaron. El bypass SSH confirmado antes en `.112` dejó de existir.

## Camino interno y servicios

- Kali: `10.30.0.10 via 10.20.0.1 dev eth1`, origen `10.20.0.100`.
- Cliente: `10.30.0.10 via 10.20.0.1 dev ens38`, origen `10.20.0.20`.
- Ambos obtuvieron `3/3` respuestas ICMP, 0 % de pérdida y HTTP `200`.
- El Servidor resolvió el retorno a `10.20.0.20` mediante `10.30.0.1 dev ens38`.
- Sensor: Suricata, chrony y SSH activos; `net.ipv4.ip_forward=1`.
- Servidor: NGINX, dnsmasq, firewall PPI, iperf3, chrony y SSH activos.
- Las cuatro VMs remotas conservaron `America/Lima` y `NTPSynchronized=yes`.
- Desde Cliente y Kali, las VIP `.10`, `.11` y `.12` respondieron HTTP `200`; en `.11` y `.12` permanecieron bloqueados TCP/22, 53, 443 y 5201.

La primera ejecución de la comprobación de VIP se descartó porque las variables del bucle se expandieron en VM01 y llegaron vacías al comando remoto. La repetición protegió correctamente las variables y produjo los resultados anteriores. Esa salida inválida no se utilizó como evidencia de red.

## Correlación de captura

Se ejecutaron únicamente calibraciones con `purpose=calibration` y `partition=excluded_calibration`. No son entrenamiento, validación ni prueba del modelo.

### Intento 001 conservado como fallo

`CAL-G7-ISOLATION-001` quedó `evidence_failed`: PCAP registró 56/56 paquetes, 33 registros EVE y cero drops, pero el muestreador local terminó al cerrarse la sesión que lanzó el comando y produjo cero filas de recursos. El artefacto se conserva sin corregir ni borrar. La causa se comprobó repitiendo inicio, tráfico y cierre dentro de una sola sesión.

### Control definitivo

`CAL-G7-ISOLATION-003`, ejecutada entre `17:49:07` y `17:49:27 America/Lima`, cerró `completed` y `evidence.complete=true`:

| Control | Resultado |
|---|---:|
| PCAP capturados/parseados | 56/56 |
| Tamaño PCAP | 7,503 bytes |
| Drops tcpdump | 0 |
| Delta Suricata `kernel_packets` | 60 |
| `kernel_drops` / `kernel_ifdrops` | 0 / 0 |
| `decoder.invalid` | 0 |
| `alert_queue_overflow` | 0 |
| EVE esperado/extraído | 21/21 |
| Muestras de recursos | 9 |
| Validación y transferencia PCAP | PASS |
| Verificación `SHA256SUMS` | todos los archivos PASS |

Hashes de referencia, sin publicar el PCAP:

```text
manifest.json  306ec065c594c5f9fbb58e3b050a6a83b7c140f823c8754e1d994184c6500515
capture.pcap0  f00626874846855156a53fe4763f0229b629c75ef4449cf7e99c5f6f57991de5
```

El tráfico corto de este control produjo paquetes IPv4 menores de 500 bytes. Su objetivo era demostrar camino y observabilidad, no satisfacer la observación del jurado sobre tráfico pesado; esa cobertura corresponde a las futuras campañas F1/F2.

Los artefactos permanecen en `/srv/ppi-evidence/artifacts/campaigns/` y no se publican en Git. No quedó campaña activa. La auditoría del ensamblador sobre el nuevo volumen continúa con `0` campañas oficiales aceptadas, `145` celdas faltantes y `ready_to_build=false`.

## Revisión cruzada de Claude

Claude Code 2.1.217, modelo Haiku, revisó el resumen de resultados sin editar el repositorio. Su dictamen fue **APTO CONDICIONALMENTE**: acepta el aislamiento actual y exige una prueba de reinicio por el precedente en que VM03 recuperó `.112` y reabrió el bypass.

## Decisión y condición restante

G7 cambia de **NO APTO por bypass activo** a **APTO OPERACIONAL / PERSISTENCIA PENDIENTE**. Todavía no se autoriza el canario oficial.

La última prueba será un reinicio controlado del Servidor, con autorización del usuario, seguido de:

1. acceso por `10.10.10.30`;
2. `ens34` aún `DOWN`/`NO-CARRIER`, sin `.112` ni ruta externa;
3. `.112` bloqueada desde VM01 por ICMP y TCP/22;
4. retorno `10.20.0.0/24 via 10.30.0.1`;
5. NGINX, dnsmasq, firewall, iperf3, chrony y SSH activos;
6. Cliente y Kali con ruta vía `10.20.0.1`, HTTP `200` y controles negativos de VIP;
7. Suricata activo y sin nuevos drops/errores.

Si todos pasan, G7 podrá declararse **APTO PERSISTENTE** y se permitirá una sola campaña canario F1. No se ejecutarán automáticamente las otras 144 campañas.
