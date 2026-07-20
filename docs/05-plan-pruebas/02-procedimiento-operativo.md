# Procedimiento operativo de la campaña

Este procedimiento debe ejecutarse en orden y registrarse con fecha, zona horaria y responsable.

## 1. Preparación y control de cambios

Desde VM01:

```bash
cd /home/m4rk/Documentos/pronteacomopepa/vf-sistema-final
git status --short --branch
date --iso-8601=seconds
```

Crear un identificador de campaña, por ejemplo `F1-2026-07-21-a`, y no mezclar sesiones de campañas diferentes.

## 2. Precondiciones técnicas

Verificar en todas las VMs:

```bash
timedatectl show -p Timezone --value
timedatectl show -p NTPSynchronized --value
```

El valor esperado es `America/Lima` y `yes`. En Kali, si el valor es `no`, desde la consola ESXi o una sesión administrativa autorizada ejecutar `sudo systemctl restart systemd-timesyncd`, esperar el siguiente sondeo y volver a comprobar `timedatectl timesync-status`.

Comprobar rutas desde Cliente y Kali:

```bash
ip route get 10.30.0.10
ping -c 3 10.30.0.10
```

El siguiente salto debe ser `10.20.0.1`; no se acepta una ruta por `172.17.25.0/24`.

## 3. Aislamiento de las NIC externas

Con acceso de recuperación por consola ESXi, desconectar temporalmente las NIC `172.17.25.x` de Servidor, Kali y Cliente. Mantener la NIC externa del Sensor solo si se necesita para NTP o instalación. Después repetir las pruebas de rutas y documentar el inventario de adaptadores en una captura o tabla.

## 4. Línea base F0

Antes de cada ventana, guardar:

```bash
sudo suricatasc -c dump-counters | tee f0-counters-before.txt
df -h /
free -h
nproc
```

Generar ICMP, SSH y HTTP de baja intensidad desde Cliente durante cinco minutos. Exportar los eventos EVE correspondientes y anotar pérdida, latencia, número de flujos y alertas.

## 5. Ejecución de una ventana

Para cada escenario:

1. Registrar ID, origen, destino, comando, duración y bitrate.
2. Iniciar captura EVE/PCAP y anotar timestamp UTC y local.
3. Ejecutar una sola carga controlada.
4. Detenerla al finalizar la duración o antes si afecta disponibilidad.
5. Guardar contadores posteriores, hashes de archivos y espacio libre.
6. Etiquetar la ventana como `benign`, `benign_stress`, `anomaly_l3`, `anomaly_l4`, `anomaly_l7` o `mixed`.

## 6. Orden obligatorio

Ejecutar F0, luego F1 completo, después F2, y revisar pérdida/falsos positivos. Solo si F1/F2 son estables se ejecuta F3 desde Kali. F4 se ejecuta al final. Un fallo de sincronización, pérdida sostenida o agotamiento de disco obliga a detener la campaña y abrir una incidencia.

## 7. Evidencias y cierre

Para cada campaña conservar un manifiesto con: commit del código, configuración de Suricata, reglas activas, versión de kernel, inventario de VMs, timestamps, comandos, resultados, hashes y limitaciones. No subir PCAP, EVE ni credenciales al repositorio público; almacenar artefactos grandes fuera de Git y publicar solo resúmenes sanitizados.
