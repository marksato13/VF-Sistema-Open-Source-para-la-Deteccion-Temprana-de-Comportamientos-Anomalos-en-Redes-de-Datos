# Validación de diversidad legítima L3 — F1 v2

Fecha: 21 de julio de 2026. Commit ejecutado: `2cd53839ac7deee7b76957f180f4f193f0b1606f`. Matriz SHA-256: `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824`.

## Decisión

**PASS para infraestructura multidestino y piloto L3.** VM03 conserva tres IP de servicio después de reiniciar, las respuestas atraviesan el Sensor, el firewall limita las VIP y el extractor observó tres destinos legítimos con ratio 1.0. El dato sigue siendo calibración. El bloqueo de almacenamiento se resolvió el 22 de julio de 2026; G6 continúa pendiente por la recolección oficial.

## Aplicación con Ansible

El primer intento administrativo no llegó a ejecutar tareas porque el inventario mantuvo `useransible`. El segundo autenticó como `server`, pero el prompt sudo personalizado no fue reconocido por Ansible. Ambos terminaron durante `Gathering Facts`, antes de copiar o aplicar archivos.

Se siguió entonces el procedimiento de privilegio temporal ya usado en el laboratorio:

1. crear `/etc/sudoers.d/useransible-ansible` mediante la cuenta administrativa;
2. validar el archivo con `visudo`;
3. ejecutar el playbook por la clave Ed25519 de `useransible`;
4. eliminar inmediatamente la autorización;
5. verificar que `sudo -n id` vuelve a ser rechazado.

Resultado del playbook:

```text
ppi-server : ok=28 changed=6 unreachable=0 failed=0
```

Validaron correctamente Netplan, NGINX, dnsmasq y nftables. Los SHA-256 remotos de NGINX, dnsmasq y firewall coincidieron con los archivos versionados.

## Estado aplicado

```text
ens38 UP 10.30.0.10/24 10.30.0.11/24 10.30.0.12/24
```

Los servicios `systemd-networkd`, `nginx`, `dnsmasq`, `ppi-server-firewall` y `ppi-iperf3` quedaron `active`. Para cada IP origen `.10/.11/.12`, `ip route get 10.20.0.20` devolvió:

```text
gateway=10.30.0.1 dev=ens38
```

Desde VM05, las tres direcciones seleccionaron `10.20.0.1` como siguiente salto, respondieron ICMP y devolvieron HTTP 200. DNS resolvió:

```text
web-a.ppi.lab -> 10.30.0.11
web-b.ppi.lab -> 10.30.0.12
```

En `.11` y `.12`, TCP 22, 53, 443 y 5201 fueron inaccesibles; solo HTTP/80 quedó publicado. Esta prueba negativa pasó antes y después del reinicio.

## Persistencia

VM03 se reinició de forma controlada sin campaña/captura activa. El arranque registrado fue `2026-07-21 23:23:19 -05:00`. Después:

- `.10/.11/.12` reaparecieron en `ens38`;
- las rutas de retorno de `.11/.12` conservaron `10.30.0.1`;
- los cinco servicios quedaron activos;
- el generador completó 3/3 solicitudes HTTP;
- el sudo temporal continuó ausente.

## Piloto `HTTP-MULTI-1`

Campaña: `CAL-G6-HTTP-MULTI-1-R01`. Propósito: `calibration`. Partición: `excluded_calibration`.

| Control | Resultado |
|---|---:|
| estado / evidencia | `completed` / `complete=true` |
| commit limpio | `2cd5383` / `dirty=false` |
| warm-up / settle | 60 s / 9 s |
| respuestas HTTP | 3/3, una por destino |
| paquetes capturados / parseados | 30 / 30 |
| bytes PCAP remoto / local | 3,369 / 3,369 |
| drops tcpdump / Suricata | 0 / 0 |
| `decoder.invalid` / overflow | 0 / 0 |
| EVE extraído / esperado | 18 / 18 |
| muestras del Sensor | 53 |
| observaciones HTTP | 3 |
| intentos / SYN | 3 / 3 |
| `syn_completion_ratio_10s` | 1.0 |
| `unique_dst_ip_ratio_30s` | **1.0 = 3 destinos / 3 intentos** |
| `unique_dst_port_ratio_30s` | 0.33333333 = 1 puerto / 3 intentos |
| `http_error_ratio_60s` | 0.0 |

PCAP, EVE, manifiesto y CSV superaron sus listas SHA-256. El helper quedó `inactive` y no permaneció `.active`.

Este tráfico tiene paquetes pequeños porque `/health` devuelve una respuesta breve. Su función es ampliar diversidad L3; los perfiles HTTP/HTTPS pesados cubren por separado el rango de 500–1500 bytes. No se exige que un único perfil active simultáneamente todas las features.

## Auditoría del ensamblador

Después del piloto:

```text
expected_campaigns = 145
accepted_campaigns = 0
excluded_campaigns = 5
invalid_campaigns = 0
missing_cells = 145
current_git_dirty = false
ready_to_build = false
```

El quinto piloto no fue reinterpretado como entrenamiento aunque su fila es causalmente elegible.

## Limitaciones

- Las tres IP pertenecen a una sola VM y comparten kernel, NIC y NGINX.
- El ratio 1.0 se validó en una sola calibración; `HTTP-MULTI-5` y las cinco repeticiones oficiales siguen pendientes.
- No se ha demostrado generalización hacia múltiples hosts físicos.
- VM01 posee el disco de evidencias requerido y su montaje por UUID pasó la prueba de reinicio.

Por tanto, el hueco de variación legítima L3 está corregido a nivel lógico y reproducible, pero no debe describirse como diversidad física de servidores.
