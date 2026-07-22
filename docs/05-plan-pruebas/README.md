# Plan reproducible de pruebas experimentales

Este plan separa las campañas para que el entrenamiento y la evaluación sean defendibles.

## Precondiciones

1. Confirmar zona horaria `America/Lima` y NTP sincronizado en las cinco VMs.
2. Desconectar en ESXi las NIC externas de Servidor, Kali y Cliente; conservar la del Sensor solo si se necesita para administración/NTP.
3. Verificar `ip route get 10.30.0.10` desde Cliente y Kali: siguiente salto `10.20.0.1`.
4. Registrar antes y después de cada campaña: `capture.kernel_drops`, `decoder.invalid`, `alert_queue_overflow`, CPU, RAM, espacio de disco y número de eventos EVE.

El procedimiento automatizado, la estructura de evidencia y los criterios de aceptación se describen en `09-sistema-campanas-F1.md`.
La validación extremo a extremo y los dos fallos corregidos se registran en `10-validacion-orquestador-G3.md`.
El diseño y la validación PCAP están en `11-diseno-captura-PCAP-G4.md` y `12-validacion-captura-PCAP-G4.md`.
El contrato de las 14 variables causales se define en `../06-features-modelado/01-diccionario-multicapa-G5.md`.
Su validación sintética y real está en `../06-features-modelado/02-validacion-extractor-G5.md`.
La matriz ejecutable F1, su partición y el gate de almacenamiento están en `../07-dataset-campanas/01-matriz-F1-normal-G6.md`.

## Grupo A: tráfico legítimo pesado

Ejecutar desde Cliente hacia Servidor, con una sesión nueva por escenario:

| ID | Escenario | Evidencia mínima |
|---|---|---|
| A1 | ICMP sostenido | pérdida, alertas y contadores |
| A5 | descarga HTTP de archivo de 500 MB o más | bytes, paquetes y evento HTTP |
| A10 | descargas HTTP concurrentes | conexiones simultáneas y falsos positivos |
| A12 | `iperf3` TCP | throughput, tamaño de paquete y drops |
| A13 | `iperf3` UDP controlado | bitrate, pérdida y drops |
| A14 | HTTP + SSH + `iperf3` concurrentes | métricas agregadas y disponibilidad |

Los escenarios A deben incluir tráfico legítimo con paquetes de 500–1500 bytes para ampliar el rango de entrenamiento de Isolation Forest.

## Grupo B: ataques controlados desde Kali

Solo después de cerrar Grupo A: escaneo TCP/UDP limitado, ráfaga de SYN, autenticación HTTP fallida visible en red, consultas DNS anómalas y solicitudes HTTP anómalas. Los intentos SSH fallidos solo se usarán si se integran logs del host, porque su resultado está cifrado. Cada escenario tendrá timestamp, origen, destino, comando, duración y evidencia asociada.

## Grupo C: mixto

Cliente genera A12/A14 mientras Kali ejecuta un único escenario B. Se evalúa separación temporal y por flujo, sin reutilizar sesiones del entrenamiento.

## Criterios de aceptación

- `kernel_drops=0` o una tasa documentada y reproducible bajo carga.
- Ningún bloqueo del tráfico normal de Grupo A.
- Cada ataque de Grupo B debe tener evento o evidencia de red correlacionable.
- Dataset separado por campaña: 60 % entrenamiento, 20 % validación y 20 % prueba.
- No se declara implementada ninguna feature L3/L4/L7 hasta disponer de código, diccionario y prueba.
