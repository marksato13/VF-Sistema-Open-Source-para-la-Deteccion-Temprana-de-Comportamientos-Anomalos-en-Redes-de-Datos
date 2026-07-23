# Corrección NTP interna con el laboratorio aislado — G7

Fecha de detección: 23 de julio de 2026. Estado inicial: **C8 BLOQUEADO** hasta aplicar y validar la corrección.

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

VM01 no consulta al Sensor, por lo que no existe un bucle. Su Chrony conserva las fuentes externas y solo autoriza clientes de `10.10.10.0/24`. El Sensor añade `server 10.10.10.10 iburst prefer` sin `trust`: VM01 debe superar las comprobaciones normales de selección.

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

La evidencia de aplicación y el dictamen final se añadirán a este documento después de ejecutar el playbook. Hasta entonces no se afirma que la corrección esté desplegada.
