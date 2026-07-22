# Disco dedicado de evidencias en VM01

Fecha de diseño: 21 de julio de 2026. Aplicación: 22 de julio de 2026.

## Decisión

VM01 conserva su disco de sistema de 70 GiB y recibió un **segundo VMDK thin de 150 GiB** para PCAP, features, ledgers y datasets. No se amplió ni formateó `/dev/sda`. El volumen nuevo está montado en `/srv/ppi-evidence` y la raíz de artefactos es `/srv/ppi-evidence/artifacts`.

La matriz F1 v2 estima 33,673,250,000 bytes de PCAP y exige conservar 20 GiB libres. El gate requiere en total 55,148,086,480 bytes, aproximadamente 51.36 GiB. Un volumen de 150 GiB deja margen para metadatos, CSV, EVE, repeticiones fallidas conservadas y las fases posteriores. El mínimo automatizado es 100 GiB; 150 GiB es la asignación recomendada para este laboratorio.

## Estado real antes del cambio — evidencia histórica

La comprobación de solo lectura registró:

| Elemento | Resultado |
|---|---:|
| Disco visible | `/dev/sda`, 75,161,927,680 bytes = 70 GiB |
| Partición raíz | `/dev/sda2`, ext4, 74,033,643,008 bytes |
| Uso de `/` | 15 GiB usados, 51 GiB disponibles |
| Segundo disco | **no existe todavía** |
| Montaje `/srv/ppi-evidence` | no existe |
| Gate F1 sobre el destino | FAIL; ruta inexistente y 0 bytes disponibles |

VMware no expone actualmente un identificador `by-id` para `/dev/sda`; sí expone la ruta SCSI estable `/dev/disk/by-path/pci-0000:02:00.0-scsi-0:0:0:0`. Por ello el auditor admite `by-id` o `by-path`, pero nunca `/dev/sdb` directamente ni una ruta terminada en `-partN`.

## Paso físico en ESXi — completado

1. Confirmar que no hay campaña ni captura activa.
2. En la configuración de VM01, **añadir un disco duro nuevo** de 150 GiB con aprovisionamiento thin. No aumentar el VMDK existente de 70 GiB.
3. Si ESXi no permite añadirlo en caliente, apagar VM01 de forma normal, añadirlo y volverla a encender. La sesión remota caerá durante ese apagado y se retomará tras el arranque.
4. No inicializar, particionar ni formatear el disco desde otra herramienta.

El operador añadió el VMDK desde ESXi. Ubuntu lo detectó como `/dev/sdb`, SCSI `0:1`, con ruta estable `/dev/disk/by-path/pci-0000:02:00.0-scsi-0:0:1:0`. El disco raíz permanece en SCSI `0:0` y resuelve a `/dev/sda`.

## Identificación y auditoría sin escritura

Después de añadir el VMDK:

```bash
cd /home/m4rk/Documentos/pronteacomopepa/vf-sistema-final
lsblk --bytes --output NAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL
ls -l /dev/disk/by-id /dev/disk/by-path
```

Se debe localizar el disco completo nuevo de 150 GiB. Su ruta exacta se copia en la variable siguiente; el ejemplo es ilustrativo y no debe suponerse correcto:

```bash
DISPOSITIVO_EVIDENCIA=/dev/disk/by-path/RUTA_SCSI_REAL_DEL_DISCO_NUEVO
sudo ./scripts/storage/audit_evidence_disk.py --device "$DISPOSITIVO_EVIDENCIA"
```

La salida JSON debe contener `eligible_new_disk: true` y todos los checks en `true`. El auditor solo consulta `findmnt`, `lsblk` y `wipefs`; no escribe en el dispositivo. Rechaza:

- el disco que respalda `/`;
- rutas inestables como `/dev/sdb`;
- particiones en lugar de discos completos;
- discos menores de 100 GiB;
- cualquier partición, montaje, sistema de archivos o firma previa.

Si un check falla, se detiene el procedimiento. No se debe usar `force`, borrar firmas ni cambiar el auditor para hacer pasar un disco reutilizado sin una revisión humana separada.

## Formateo y montaje controlado

Este es el primer paso que sí modifica el disco. Solo se ejecuta después de revisar el JSON anterior:

```bash
cd /home/m4rk/Documentos/pronteacomopepa/vf-sistema-final/ansible
sudo env ANSIBLE_LOG_PATH=/tmp/ppi-storage-apply-3.log \
  ../.venv/bin/ansible-playbook \
  playbooks/07-configurar-almacenamiento-evidencia-vm01.yml \
  -e "ppi_evidence_device=$DISPOSITIVO_EVIDENCIA" \
  -e "ppi_evidence_confirm_format=FORMAT_NEW_EVIDENCE_DISK"
```

El playbook vuelve a ejecutar la auditoría antes de crear ext4. Después monta por UUID con `nodev,nosuid,noexec,noatime`, crea directorios privados con modo `0700` y escribe el marcador no sensible `.ppi-evidence-volume.json`. El dispositivo solo se usa para datos; no aloja ejecutables.

En esta VM, dos intentos previos terminaron antes de escribir porque Ansible no pudo reutilizar correctamente el prompt sudo interactivo: `changed=0` en ambos casos. La ejecución final elevó el proceso completo con un único `sudo`; terminó `ok=12 changed=5 unreachable=0 failed=0`.

La verificación posterior de `fstab` encontró cero errores de sintaxis. Mostró que systemd todavía conservaba en memoria la versión anterior; el playbook quedó corregido para ejecutar `daemon-reload` en instalaciones futuras. En esta aplicación, el reinicio de persistencia pendiente cargará directamente la entrada nueva por UUID.

## Validación posterior y uso por las campañas

```bash
findmnt --target /srv/ppi-evidence
df -hT /srv/ppi-evidence
cat /srv/ppi-evidence/.ppi-evidence-volume.json

export PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts
python3 scripts/f1/validate_matrix.py --require-storage
python3 scripts/f1/run_matrix_profile.py \
  --profile DNS-VALID-10 --repetition 1 --dry-run
```

Una campaña oficial requiere simultáneamente:

- la ruta exacta `/srv/ppi-evidence/artifacts`;
- que `/srv/ppi-evidence` sea un punto de montaje real, no un directorio del disco raíz;
- un marcador compatible con `configs/storage/evidence-v1.json`;
- espacio libre suficiente para toda F1 v2 y la reserva.

Los cinco pilotos históricos permanecen en `artifacts/` dentro del repositorio de trabajo y siguen excluidos del entrenamiento. El ensamblador y el extractor respetan `PPI_ARTIFACTS_ROOT`, por lo que el dataset oficial se construirá en el volumen dedicado sin mover ni reinterpretar las calibraciones.

## Resultado aplicado

La auditoría privilegiada previa al formateo devolvió todos los controles en `true`:

```text
eligible_new_disk=true
device_resolved=/dev/sdb
root_disk_resolved=/dev/sda
size_bytes=161061273600
minimum_bytes=107374182400
partitions=0, filesystem=null, mountpoints=0, signatures=0
```

Estado posterior:

| Control | Resultado |
|---|---|
| Sistema de archivos | ext4 |
| UUID | `b676aa52-55b2-422d-b77a-4cde1d36d37f` |
| Montaje | `/srv/ppi-evidence` |
| Opciones | `rw,nosuid,nodev,noexec,noatime` |
| Persistencia | entrada por UUID en `/etc/fstab` |
| Capacidad utilizable | aproximadamente 147 GiB |
| Disponible inicial | aproximadamente 140 GiB = 149,324,984,320 bytes |
| Directorios runtime | propietario `m4rk:m4rk`, modo `0700` |
| Gate de capacidad F1 v2 | PASS |
| Gate de identidad del ejecutor | PASS |

El plan completo estima 33,673,250,000 bytes de PCAP y, después de reservarlos, proyecta 115,651,734,320 bytes libres. El `dry-run` oficial seleccionó `/srv/ppi-evidence/artifacts`, reconoció el marcador y devolvió `official_storage.gate_pass=true` sin generar tráfico.

## Checkpoint previo al reinicio

Checkpoint tomado el `2026-07-22T01:53:12-05:00`, antes del reinicio autorizado por el usuario:

| Control | Resultado previo |
|---|---|
| Arranque de VM01 observado | `2026-07-22 01:34:39` |
| RustDesk | `active` y `enabled` |
| Campaña/bloqueo local | ausentes |
| Proceso de campaña o PCAP | ausente |
| Volumen | `/dev/sdb` → `/srv/ppi-evidence`, ext4 |
| UUID | `b676aa52-55b2-422d-b77a-4cde1d36d37f` |
| Opciones activas | `rw,nosuid,nodev,noexec,noatime` |
| Bytes disponibles | `149324984320` |
| Gate de capacidad | PASS |
| Gate de identidad | PASS |
| Git local/remoto | sincronizados en `51290b75b04951c9fc09ece8a2f4920651f84b84` |

La sesión de RustDesk/Codex se interrumpirá por diseño. Después del arranque se volverán a comprobar hora de boot, UUID, opciones, marcador, permisos, bytes disponibles, ambos gates y sincronización Git. No se ejecutará una campaña durante esta prueba de persistencia.

## Validación posterior al reinicio

**PASS.** VM01 arrancó nuevamente el `2026-07-22 01:56:13 -05:00`. La validación se realizó a las `01:59:09 -05:00` sin ejecutar tráfico ni campañas.

| Control | Resultado posterior |
|---|---|
| RustDesk | `active` y `enabled` |
| Disco raíz | `/dev/sda2`, ext4, `rw` |
| Volumen de evidencias | `/dev/sdb`, ext4, montado automáticamente |
| UUID observado | `b676aa52-55b2-422d-b77a-4cde1d36d37f`, idéntico al checkpoint |
| Montaje | `/srv/ppi-evidence` |
| Opciones reales fuera del sandbox | `rw,nosuid,nodev,noexec,noatime` |
| Prueba de escritura del directorio | `ARTIFACTS_WRITABLE=PASS` |
| Marcador | legible, esquema `evidence-v1` y UUID coherente |
| Propiedad/permisos | `m4rk:m4rk`, modo `0700` en los cinco directorios |
| Bytes disponibles | `149324984320`, igual al checkpoint |
| Verificación de `fstab` | 0 errores de parseo y 0 errores |
| Gate de capacidad F1 v2 | PASS |
| Gate de identidad del ejecutor | PASS |
| Git antes de documentar el resultado | local y remoto sincronizados en `c45d747` |

La primera lectura desde la sesión automatizada mostró `ro` tanto para `/` como para el volumen por las restricciones del sandbox de herramientas. La verificación fuera de ese sandbox confirmó que ambos sistemas de archivos estaban realmente `rw`; no se registró ese artefacto del entorno como fallo del sistema operativo.

## Controles antes de la campaña oficial

El reinicio de persistencia ya pasó. Antes de cada lote oficial todavía se registrará el espacio real del datastore ESXi, porque 150 GiB thin representan capacidad lógica y el PCAP hace crecer el VMDK físicamente. También se conservarán los gates de capacidad e identidad como precondiciones automáticas de cada ejecución.
