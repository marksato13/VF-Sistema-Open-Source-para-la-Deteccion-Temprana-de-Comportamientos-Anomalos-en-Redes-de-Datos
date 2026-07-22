# Disco dedicado de evidencias en VM01

Fecha de diseño y auditoría: 21 de julio de 2026.

## Decisión

VM01 conservará su disco de sistema de 70 GiB y recibirá un **segundo VMDK thin de 150 GiB** para PCAP, features, ledgers y datasets. No se ampliará ni formateará `/dev/sda`. El volumen nuevo se montará en `/srv/ppi-evidence` y la raíz de artefactos será `/srv/ppi-evidence/artifacts`.

La matriz F1 v2 estima 33,673,250,000 bytes de PCAP y exige conservar 20 GiB libres. El gate requiere en total 55,148,086,480 bytes, aproximadamente 51.36 GiB. Un volumen de 150 GiB deja margen para metadatos, CSV, EVE, repeticiones fallidas conservadas y las fases posteriores. El mínimo automatizado es 100 GiB; 150 GiB es la asignación recomendada para este laboratorio.

## Estado real antes del cambio

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

## Paso físico pendiente en ESXi

1. Confirmar que no hay campaña ni captura activa.
2. En la configuración de VM01, **añadir un disco duro nuevo** de 150 GiB con aprovisionamiento thin. No aumentar el VMDK existente de 70 GiB.
3. Si ESXi no permite añadirlo en caliente, apagar VM01 de forma normal, añadirlo y volverla a encender. La sesión remota caerá durante ese apagado y se retomará tras el arranque.
4. No inicializar, particionar ni formatear el disco desde otra herramienta.

Este paso no fue ejecutado por Codex porque solo puede identificar de forma segura el dispositivo después de que ESXi lo presente al sistema operativo.

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
../.venv/bin/ansible-playbook -K \
  playbooks/07-configurar-almacenamiento-evidencia-vm01.yml \
  -e "ppi_evidence_device=$DISPOSITIVO_EVIDENCIA" \
  -e "ppi_evidence_confirm_format=FORMAT_NEW_EVIDENCE_DISK"
```

El playbook vuelve a ejecutar la auditoría antes de crear ext4. Después monta por UUID con `nodev,nosuid,noexec,noatime`, crea directorios privados con modo `0700` y escribe el marcador no sensible `.ppi-evidence-volume.json`. El dispositivo solo se usa para datos; no aloja ejecutables.

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

## Controles antes de la campaña oficial

Después del montaje aún se debe validar un reinicio de VM01: el volumen debe reaparecer por UUID, el marcador debe seguir legible y el gate debe continuar en PASS. También se registrará el espacio real del datastore ESXi, porque 150 GiB thin representan capacidad lógica y el PCAP hace crecer el VMDK físicamente.
