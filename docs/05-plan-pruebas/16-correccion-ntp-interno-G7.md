# Corrección NTP interna con el laboratorio aislado — G7

Fecha de detección y corrección: 23 de julio de 2026. Estado: **NTP_GATE=PASS**; C8 puede repetir su preflight completo.

## Hallazgo

El preflight de `HTTP-C8/R01` se detuvo antes de crear artefactos porque VM02 Sensor reportó `NTPSynchronized=no`. Sus fuentes públicas tenían `reach=0` y no recibían una muestra desde hacía aproximadamente 18 horas, consecuencia esperada de mantener `ens34` sin portadora durante las campañas.

`chronyc tracking` todavía mostraba estrato 3, `Leap status: Normal` y corrección submilisegundo. Servidor, Kali y Cliente seguían sincronizados contra el Sensor. Esto indica deriva todavía pequeña, pero no satisface el gate explícito de sincronización y no autoriza una campaña.

## Diseño corregido

```text
Canonical/Ubuntu NTP
        │ Internet solo en VM01
        ▼
VM01 10.10.10.10
        │ NTP solo por PPI-MGMT
        ▼
Sensor 10.10.10.20
        │ referencia interna existente
        ├────────► Servidor 10.10.10.30
        ├────────► Kali 10.10.10.40
        └────────► Cliente 10.10.10.50
```

VM01 no consulta al Sensor, por lo que no existe un bucle. Su Chrony conserva las fuentes externas y solo autoriza clientes de `10.10.10.0/24`. El Sensor añade `server 10.10.10.10 iburst prefer require` sin `trust`: VM01 debe superar las comprobaciones normales de selección y existir como fuente requerida alcanzable.

Las fuentes públicas del Sensor permanecen declaradas como fallback de mantenimiento, pero son inalcanzables mientras `ens34` esté `DOWN/NO-CARRIER` y no exista ruta externa. No se reconecta ninguna NIC para ejecutar C8.

## Automatización

Archivos versionados:

- `configs/time/chrony-vm01-server.conf`: ACL limitada a PPI-MGMT;
- `configs/time/chrony-sensor-vm01.sources`: fuente interna preferida;
- `ansible/playbooks/08-configurar-ntp-interno.yml`: aplicación idempotente y validación;
- `scripts/f1/check_ntp_gate.sh`: gate de solo lectura para VM01 y las cuatro VM remotas.

El playbook separa las etiquetas `controller`, `sensor` y `verify`, porque VM01 y el Sensor pueden usar credenciales sudo diferentes.

## Gates antes de reanudar C8

1. VM01: `America/Lima`, `NTPSynchronized=yes`, `Leap status: Normal`.
2. Sensor: fuente seleccionada `^* 10.10.10.10`, sincronización positiva y offset absoluto máximo de 100 ms.
3. Servidor, Kali y Cliente: fuente seleccionada `^* 10.10.10.20`, sincronización positiva y el mismo límite.
4. NIC externas de VM02–VM05 en `DOWN`, sin ruta de bypass.
5. Repositorio limpio y nuevo preflight completo.

El gate usa el campo absoluto `System time` de `chronyc tracking`; la palabra `fast` o `slow` no cambia la comparación.

## Revisión de Claude

Claude consideró válida la jerarquía VM01→Sensor→resto y mantuvo C8 condicionado a una aplicación reproducible y offsets medidos. También recomendó no usar `trust`.

Dos observaciones del dictamen se corrigen:

- Chrony actual sí admite la opción `trust`, pero deliberadamente no se configura.
- No es necesario borrar las fuentes públicas del Sensor: el aislamiento se demuestra por enlace, ruta y prueba negativa, y esas fuentes pueden servir durante una ventana futura de mantenimiento.

Durante la primera aplicación, VM01 tardó aproximadamente 65 segundos en volver a seleccionar una fuente NTS después de reiniciar Chrony; un `waitsync` de 60 segundos terminó inmediatamente antes de la selección. No fue pérdida persistente de configuración.

La primera fuente interna usó solo `prefer`. VM01 respondió y acumuló muestras, pero permaneció en estado `W`: el modo predeterminado `authselectmode mix` aplica de forma efectiva `require+trust` a las fuentes NTS y esperaba una fuente requerida. La prueba runtime añadió únicamente `require` a VM01; quedó seleccionada `*`, el Sensor pasó a estrato 4, `Leap status: Normal`, `NTPSynchronized=yes` y corrección inicial de 52.88 ms. No se añadió `trust` ni se cambió `authselectmode`.

La semántica de los estados `W`, `require`, `trust` y `authselectmode mix` se contrastó con la documentación oficial de [Chrony 4.8](https://chrony-project.org/doc/4.8/chrony.conf.html#authselectmode).

## Aplicación y evidencia

El primer intento del playbook local no aplicó ninguna tarea: Ansible agotó el timeout al recibir un segundo prompt localizado de sudo. Para no ocultar ese fallo, VM01 se aplicó con `sudo install` sobre el mismo archivo versionado y se reinició únicamente Chrony. En el Sensor, el archivo versionado se transfirió mediante `useransible` y se instaló por SSH con `sensor_motor`; también se reinició únicamente Chrony.

Los hashes local/desplegado coincidieron:

| Destino | SHA-256 |
|---|---|
| VM01 `/etc/chrony/conf.d/ppi-mgmt-server.conf` | `dc3e4f79e6ff6a85fed6ddc70bc64dc84b4884cef2fe77f8d0da302a45c756b6` |
| Sensor `/etc/chrony/sources.d/ppi-vm01.sources` | `a66c863ba462d551ed222f4229d0de866653016239b0000b39db32f967d7eac0` |

El Sensor seleccionó `^* 10.10.10.10`, estrato 4, `Leap status: Normal` y `NTPSynchronized=yes`. Tres ejecuciones consecutivas de `scripts/f1/check_ntp_gate.sh` dieron PASS:

| Nodo | Fuente | Offset absoluto observado |
|---|---|---:|
| VM01 | Canonical NTS | 0.111 ms máximo |
| Sensor | `10.10.10.10` | 0.0024 ms máximo |
| Servidor | `10.10.10.20` | 0.0061 ms máximo |
| Kali | `10.10.10.20`, `systemd-timesyncd` | 0.404 ms |
| Cliente | `10.10.10.20` | 33.583 ms máximo |

El gate se corrigió para consultar `chronyc` en VM01, Sensor, Servidor y Cliente, y `timedatectl timesync-status` en Kali. Antes asumía incorrectamente que todas las VM tenían Chrony.

Las NIC `ens34` de Sensor/Servidor/Cliente y `eth0` de Kali permanecieron `DOWN` sin portadora. `172.17.25.113` siguió bloqueada por ICMP y TCP/22 desde VM01.

## Decisión

**CORRECCIÓN NTP APLICADA Y VALIDADA.** El hallazgo no generó artefactos de campaña. Se autoriza repetir desde cero el preflight de `HTTP-C8/R01`; esta autorización no sustituye los demás gates de aislamiento, rutas, servicios, capacidad, Suricata, Git e ID libre.

La evidencia de aplicación y el dictamen final se añadirán a este documento después de ejecutar el playbook. Hasta entonces no se afirma que la corrección esté desplegada.
