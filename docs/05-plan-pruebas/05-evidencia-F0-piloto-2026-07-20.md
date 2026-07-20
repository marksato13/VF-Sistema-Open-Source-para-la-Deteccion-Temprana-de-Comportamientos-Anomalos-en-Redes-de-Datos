# Evidencia F0 piloto — 20 de julio de 2026

Prueba funcional corta ejecutada después de cerrar G0 temporalmente. No pertenece al dataset final.

## Condiciones

- Horario observado: 18:04–18:07 `America/Lima`.
- Cliente: `10.20.0.20`.
- Servidor: `10.30.0.10`.
- Ruta: Cliente → `10.20.0.1` (Sensor) → Servidor.
- NIC externas de Cliente, Kali y Servidor: `DOWN` a nivel del sistema operativo.
- Suricata y nftables: activos; `ip_forward=1`.

## Resultados funcionales

| Prueba | Resultado |
|---|---|
| ICMP Cliente→Servidor | 5/5 respuestas, 0 % pérdida, RTT promedio 0.491 ms |
| TCP/22 | conexión correcta |
| HTTP | `HTTP/1.0 200 OK` mediante `wget` |
| Evento SSH EVE | observado a las 18:07:22 |
| Evento HTTP EVE | método GET, estado 200, longitud 514, agente `Wget/1.25.0` |
| Regla ICMP local | cinco alertas SID `1000001` de la ronda actual |
| Regla ET informativa | SID `2034636`, Python SimpleHTTP ServerBanner |

El intento inicial de HTTP con `curl` falló porque el binario no está instalado en el Cliente. Se utilizó `wget`, que ya estaba disponible. Esta incidencia no representa un fallo de red o detección y deberá resolverse en el baseline de herramientas antes de F1.

## Métricas del Sensor

| Métrica | Antes | Después | Diferencia |
|---|---:|---:|---:|
| `capture.kernel_packets` | 867 | 900 | 33 |
| `capture.kernel_drops` | 0 | 0 | 0 |
| `decoder.invalid` | 0 | 0 | 0 |
| `detect.alert_queue_overflow` | 0 | 0 | 0 |
| Líneas de `eve.json` | 1577 | 1603 | 26 |

Los últimos 200 registros EVE contenían eventos `alert`, `fileinfo`, `flow`, `http`, `ssh` y `stats`. La correlación se comprobó por IP, timestamp y tipo de evento.

## Decisión

Estado: **G1 APTO para preparar F1**. La prueba fue liviana y no demuestra rendimiento bajo carga. Antes de F1 se debe instalar/verificar el conjunto de herramientas, definir los tamaños de archivos y automatizar la recolección de métricas. El aislamiento actual debe revisarse de nuevo tras cualquier reinicio.
