# Validación de persistencia y cierre G7 — 22 de julio de 2026

Esta prueba cierra la condición pendiente de `14-cierre-operacional-G7.md`: demostrar mediante un reinicio real que la NIC externa del Servidor no vuelve a habilitar el bypass hacia VM03.

## Privilegio usado

En VM02–VM05 se instaló una regla sudo de comando exacto:

```text
useransible ALL=(root) NOPASSWD: /usr/bin/systemctl reboot --no-wall
```

Cada archivo pasó `visudo -cf`. Desde `useransible`, `sudo -n -l` mostró solamente esa orden en Servidor, Kali y Cliente; el Sensor mostró además sus helpers restringidos de métricas y PCAP. La prueba negativa `sudo -n /usr/bin/id` fue bloqueada en las cuatro VMs. No se concedió `NOPASSWD: ALL`, pertenencia al grupo `sudo` ni una consola root.

El primer intento de reinicio, antes de instalar la regla, fue rechazado por systemd por falta de autenticación interactiva y no cambió el `boot_id`. Esto confirma que la cuenta no poseía privilegios generales implícitos.

## Reinicio controlado de VM03

Estado previo:

```text
boot_id: 9b900e07-9686-4624-8f71-f80f95876cb9
inicio:   2026-07-21 23:23:19 America/Lima
```

Ansible ejecutó exclusivamente:

```bash
sudo -n /usr/bin/systemctl reboot --no-wall
```

Estado posterior:

```text
boot_id: f6077fcc-557d-4f42-8db9-a5ebd0edd829
inicio:   2026-07-22 18:11:33 America/Lima
```

El cambio de `boot_id` demuestra que no fue una simple reconexión SSH. Durante el arranque, varios sondeos rápidos produjeron temporalmente el mensaje SSH `Not allowed at this time`; se detuvieron los sondeos, se esperó y OpenSSH volvió a entregar su banner normal. No se modificó la configuración SSH. Para futuros reinicios se usará un sondeo menos frecuente.

## Persistencia del aislamiento

Después del reinicio:

- `ens34`, MAC `00:0c:29:15:ad:a7`, permaneció `DOWN` y `NO-CARRIER`;
- no reapareció `172.17.25.112`;
- no reapareció la ruta conectada a `172.17.25.0/24` ni el gateway externo;
- desde VM01, `.112` quedó bloqueada por ICMP y TCP/22;
- PPI-MGMT `10.10.10.30` volvió a responder.

El bypass que motivó G7 permaneció cerrado después del arranque.

## Persistencia funcional

| Control | Resultado |
|---|---|
| VIP DMZ | `.10`, `.11` y `.12` presentes |
| Retorno a Cliente | `10.20.0.20 via 10.30.0.1 dev ens38` |
| Zona/NTP | `America/Lima`, sincronizado |
| Servicios | NGINX, dnsmasq, firewall PPI, iperf3, chrony y SSH activos |
| Cliente→Servidor | vía `10.20.0.1`, 3/3 ICMP, HTTP `200` |
| Kali→Servidor | vía `10.20.0.1`, 3/3 ICMP, HTTP `200` |
| Ruta externa Cliente/Kali | inexistente hacia `.112` |
| HTTP VIP | `200` en `.10`, `.11` y `.12` |
| Puertos restringidos `.11/.12` | TCP/22, 53, 443 y 5201 bloqueados |

Suricata permaneció activo en el Sensor con `ip_forward=1`:

```text
capture.kernel_packets=5777116
kernel_drops=0
kernel_ifdrops=0
decoder.invalid=0
alert_queue_overflow=0
```

La correlación PCAP/EVE completa anterior permanece en `CAL-G7-ISOLATION-003`; el reinicio no generó una campaña oficial ni agregó muestras al dataset.

## Revisión cruzada

El dictamen anterior de Claude fue **APTO CONDICIONALMENTE** y exigió exactamente un reinicio con verificación de NIC, rutas y servicios. Esas condiciones pasaron. Se solicitaron dos revisiones finales adicionales a Claude Code, pero ambas terminaron sin emitir contenido; por integridad metodológica no se registra una aprobación nueva inexistente.

## Decisión final G7

**G7 APTO PERSISTENTE.** El bypass externo está cerrado, el aislamiento sobrevivió al reinicio y el camino observable LAN→Sensor→DMZ continúa funcional.

Se autoriza como siguiente paso **una sola campaña canario F1**. Antes de iniciarla deberán confirmarse repositorio limpio, ausencia de campaña activa, capacidad del volumen, tiempo sincronizado y estado de Suricata. Las otras 144 campañas permanecen bloqueadas hasta validar el bundle del canario.
