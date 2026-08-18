# Diseño de captura PCAP por campaña — G4

Fecha: 20 de julio de 2026. Última actualización: 23 de julio de 2026. Estado: implementado y validado extremo a extremo.

## Razón

EVE entrega eventos normalizados de Suricata, pero no conserva todos los campos necesarios para reconstruir y auditar variables L3/L4. El PCAP permite recalcular tamaño de paquete, direcciones, puertos, flags TCP, tiempos entre paquetes y estadísticas de flujo sin depender de una única versión del extractor.

PCAP no resuelve por sí solo semántica cifrada de capa 7. Por ejemplo, un login SSH fallido continúa necesitando logs del host; HTTPS permite metadatos TLS y de flujo, no el código HTTP interno.

## Parámetros fijos

El helper `/usr/local/sbin/ppi-pcap-control` no acepta interfaz, filtro ni ruta proporcionados por el operador:

| Parámetro | Valor |
|---|---|
| interfaz | `ens35` de VM02 Sensor |
| filtro | tráfico bidireccional entre `10.20.0.0/24` y `10.30.0.0/24` |
| resolución de nombres | desactivada (`-n`) |
| snaplen | paquete completo (`-s 0`) |
| escritura | inmediata (`-U`) |
| búfer de captura | 65,536 KiB; originalmente 4,096 KiB |
| rotación | 4 archivos de 512 millones de bytes |
| capacidad nominal máxima | 2.048 GB por campaña |
| usuario del proceso tras abrir interfaz | `tcpdump` |
| ruta remota activa | `/var/lib/ppi-captures/<ID>/` |
| archivo remoto de intentos rechazados | `/var/lib/ppi-captures-failed/<ID>/attempt-NN/` |

Si el total alcanza 1,945,600,000 bytes, equivalente al 95 % de la capacidad nominal, el orquestador marca la evidencia incompleta. Esto evita aceptar silenciosamente un anillo que pudo comenzar a sobrescribir sus primeros paquetes.

El búfer aumentó a 64 MiB después de que el intento oficial `F1N-HTTP-C8-R01` registrara 476 drops de `tcpdump` con ocho flujos y el búfer anterior de 4 MiB. `net.core.rmem_max=67108864` se instala mediante `/etc/sysctl.d/99-ppi-pcap-buffer.conf`. La rotación permanece deliberadamente en 512 MB × 4 durante la primera calibración diagnóstica para cambiar una sola variable causal.

`CAL-G6-HTTP-C8-R01` repitió el perfil con 605,266/605,266 paquetes y cero drops. La calibración apoya mantener el nuevo búfer y conservar la rotación actual; no entra al dataset ni garantiza que toda campaña futura esté libre de pérdida.

La opción `-B` está expresada en KiB y `-C` en millones de bytes, según el manual oficial de [tcpdump](https://www.tcpdump.org/manpages/tcpdump.1.html). `-W` puede sobrescribir archivos al alcanzar el límite; por eso continúa vigente el umbral preventivo de 95 %.

## Flujo

```text
start.sh
  ├─ contadores iniciales de Suricata
  ├─ ppi-pcap-control start <ID>
  └─ sampler del Sensor

escenario desde VM05

stop.sh
  ├─ espera 9 s para checkpoint de Suricata
  ├─ SIGINT y cierre limpio de tcpdump
  ├─ SHA-256 remoto de cada PCAP
  ├─ copia por SSH/TAR a artifacts/campaigns/<ID>/pcap/
  ├─ verificación del SHA-256 remoto y lectura completa con tcpdump
  ├─ resumen de longitud IPv4 y comparación con paquetes capturados
  ├─ comparación de cantidad/tamaño remoto y local
  ├─ contadores finales y segmento EVE
  └─ SHA256SUMS de toda la campaña
```

## Privilegios y pruebas negativas

El archivo ejecutable y sus directorios padre son propiedad de `root`. Sudoers permite invocar el helper, pero el helper limita las acciones a `start`, `stop`, `status` y `archive`. Las tres primeras exigen exactamente un ID de 3–64 caracteres seguros. `archive` exige además una etiqueta estricta `attempt-NN`. Internamente usa rutas absolutas, no acepta rutas del operador y valida que el PID corresponda tanto a `tcpdump` como al directorio de la campaña antes de enviar `SIGINT`.

`archive` no elimina ni modifica los archivos de evidencia: mueve atómicamente el directorio cerrado a la zona de intentos fallidos dentro del mismo sistema de archivos. Rechaza la operación si hay una captura activa, si origen y destino coexisten o si la etiqueta no es válida. El procedimiento completo, incluida la verificación de hashes y el movimiento del bundle y ledger locales, está en `17-archivado-intentos-fallidos.md`.

El directorio padre `/var/lib/ppi-captures` usa modo `0711`: permite atravesar una ruta conocida, pero no listar campañas. Durante la captura, el subdirectorio pertenece a `tcpdump:tcpdump`; al cerrar cambia a `root:useransible` con modo `0750` para permitir únicamente la copia autenticada. Este detalle también permite que el usuario sin privilegios de `tcpdump` atraviese el directorio padre después de la caída de privilegios.

Pruebas ejecutadas:

- `status CHECK-PCAP-001`: permitido, estado `inactive`;
- ID `../../etc`: rechazado;
- tercer argumento: rechazado;
- `sudo -n /usr/bin/tcpdump --version`: rechazado.

La regla no entrega permiso directo sobre `tcpdump`. La superficie adicional es el helper fijo, cuyo código está versionado y debe revisarse cada vez que cambie.

## Capacidad y retención

Capacidad observada antes de G4:

| Nodo | Libre | Límite por campaña | Comentario |
|---|---:|---:|---|
| VM02 Sensor | 140 GB | 2.048 GB | espacio temporal suficiente |
| VM01 Administración | 51 GB | 2.048 GB | cuello de botella para conservar muchas repeticiones |

Tanto VM01 como VM02 deben tener al menos 3 GiB libres al iniciar. El cierre copia el PCAP, pero no elimina automáticamente el original remoto: primero debe verificarse `SHA256SUMS` y existir una copia de respaldo. La limpieza se implementará como procedimiento administrativo separado, con ID exacto, nunca como borrado amplio.

Para una campaña final de decenas de repeticiones, 51 GB no basta para conservar simultáneamente todos los PCAP, datasets derivados y copias. Antes de F1 final se debe elegir una de estas medidas: disco adicional dedicado en VM01, almacenamiento NFS controlado o política de transferencia a almacenamiento externo con hash verificado.

## Privacidad e integridad

El snaplen completo puede conservar payload, nombres, URIs o credenciales transmitidas sin cifrar. Por eso:

- los PCAP quedan excluidos de Git;
- el laboratorio debe usar únicamente datos sintéticos;
- no se capturan redes externas ni PPI-MGMT;
- cualquier publicación futura usará dataset derivado y anonimizado, no PCAP crudo;
- `SHA256SUMS` prueba integridad desde el cierre de campaña, no anonimización ni ausencia de datos sensibles.

## Criterios G4

G4 pasa únicamente si una campaña DNS de calibración produce PCAP legible de extremo a extremo, tamaños y SHA-256 remoto/local iguales, cero drops de tcpdump y Suricata, segmento EVE exacto, serie de recursos válida, hashes correctos y ningún proceso/bloqueo residual. Después se repetirá con HTTP de 10 MB para confirmar paquetes cercanos a MTU y calcular la proporción de longitudes de 500–1500 bytes.
