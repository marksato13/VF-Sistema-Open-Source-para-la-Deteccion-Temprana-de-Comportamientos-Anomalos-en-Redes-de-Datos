# Revisión adversarial Claude — almacenamiento de VM01

Fecha: 21 de julio de 2026. Claude Code 2.1.217, revisión de solo lectura con modelo Haiku. Codex implementó y verificó las correcciones.

## CLA-STO-01 — Selección y formateo del dispositivo

1. **Severidad:** crítica si fallara; no se encontró un fallo confirmable.
2. **Hecho:** el playbook exige ruta estable de disco completo, confirmación literal, auditoría elegible y `force=false` antes de crear ext4.
3. **Inferencia evaluada:** un nombre `/dev/sdX` reordenado o una ruta a partición podría apuntar al destino incorrecto.
4. **Riesgo:** destrucción del sistema operativo o de un volumen existente.
5. **Prueba:** presentar nombres inestables, una ruta `-partN`, el disco raíz, un disco de 80 GiB, un disco montado y firmas previas.
6. **Corrección:** el auditor rechaza esos casos y Ansible vuelve a ejecutarlo con privilegio antes del formateo.
7. **Efecto secundario:** un disco reutilizado se rechaza aunque el operador pretenda borrarlo; requiere un procedimiento humano diferente y explícito.
8. **Estado:** controles aceptados; cubiertos por pruebas negativas automatizadas. El disco físico todavía no existe y no se ejecutó el formateo.

## CLA-STO-02 — Resolución del disco que respalda `/`

1. **Severidad:** alta por impacto potencial.
2. **Hecho:** la primera implementación consultaba un solo `PKNAME` de la fuente montada en `/`.
3. **Inferencia de Claude:** un layout futuro con LVM podría requerir recorrer más de un ancestro de bloque.
4. **Riesgo:** identificar de forma incompleta el disco físico raíz y debilitar el gate principal.
5. **Prueba:** topología sintética `/dev/mapper/root` → `/dev/sda2` → `/dev/sda` y comprobación real de VM01.
6. **Corrección:** recorrer recursivamente la salida inversa de `lsblk` y aceptar el análisis solo si `/` resuelve a exactamente un disco físico.
7. **Efecto secundario:** una raíz distribuida entre varios discos se rechaza de forma conservadora en lugar de seleccionar uno.
8. **Estado:** corregida. La prueba sintética pasa y VM01 resuelve actualmente `/dev/sda2` → `/dev/sda` sin LVM.

## Resultado

Claude no encontró una ruta verificable que evada la cadena de guardas ni un error confirmado de Ansible. La comprobación sintáctica del playbook pasó con las colecciones fijadas por el proyecto. La suite completa quedó en 29 pruebas. Esta revisión valida el diseño del control, no autoriza formatear: falta añadir el VMDK nuevo en ESXi, volver a auditar su identidad real y revisar `eligible_new_disk=true`.
