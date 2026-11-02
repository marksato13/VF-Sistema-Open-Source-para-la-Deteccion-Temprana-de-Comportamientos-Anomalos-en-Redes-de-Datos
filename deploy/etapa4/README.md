# Etapa 4: instalación en sombra, verificación y reversión (preparado; NO ejecutado)

Código que se instala: **ec78ca5** (`ec78ca56a3a8f4bb17fda967a7f0abe0e9a2c742`), sin cambios. Este
directorio y `scripts/etapa4/` solo añaden herramientas; `laptop/paquete_candidata.sh` aborta si el código
del paquete difiere de ec78ca5.

El procedimiento completo, con etiquetas de máquina, quién ejecuta, resultados esperados y paradas, está
en el repositorio de documentación:
`03-entregables/13-respuesta-observaciones-validacion-interna/seccion4-resultados/campana-2026-10-26-deteccion-respuesta/etapa4-preparacion-2026-11-02/PROCEDIMIENTO-ETAPA4.md`.

| Directorio | Contenido |
|---|---|
| `laptop/` | `paquete_candidata.sh`: tar de ec78ca5 + herramientas, con `SHA256SUMS` |
| `sensor1/` | `respaldo_sensor1.sh`, `instalar_sensor1_sombra.sh` (fases 0–5 y `llave-rele`), `comprobar_importaciones.sh`, `verificar_sensor1.sh`, `revertir_sensor1.sh` |
| `bastion/` | `respaldo_bastion.sh`, `instalar_bastion_sombra.sh` (`llaves`, `instalar`), `verificar_bastion.sh`, `revertir_bastion.sh` |
| `srvdmz/` | `respaldo_srvdmz.sh`, `instalar_srvdmz_sombra.sh`, `verificar_srvdmz.sh`, `revertir_srvdmz.sh` |
| `unidades/` | drop-ins de `ppi-motor` (candidato, `--disparo eventos`, `_state-e4`) y `ppi-motor-capture` (`-G 5`); `ppi-publicar-feed-v2`, `ppi-via-rapida@`, `cf-tcpdump-estadisticas` (.service/.timer), logrotate; relé sin DC1; agente v2 dmz sin `--aplicar` |
| `banco/` | `ensayo_tcpdump_estadisticas.sh` (SIGUSR1 sin parar la captura), `ensayo_unidades_importaciones.sh` (systemd-analyze y origen de los módulos), `observado-sensor1/` (copia literal de las unidades base leídas el 2026-11-02) |

Sensor1 **no** tiene checkout de git: `~/cyberflow` es el despliegue anterior (motor 24f8a80; publicador,
escalada y panel de f57ca00). La candidata se instala al lado, en `/home/m4rk/cyberflow-e4/ec78ca5`, y la
reversión retira los drop-ins y vuelve a las unidades copiadas en el respaldo, sin depender de git.

DC1 no se toca. El LIMIT DNS no se aplica en ningún sitio. Ningún agente lleva `--aplicar`.
