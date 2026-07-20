# Plantilla de evidencia F0 — línea base

Completar una copia por campaña. No rellenar resultados por estimación.

## Identificación

- ID de campaña:
- Fecha/hora local (`America/Lima`):
- Fecha/hora UTC:
- Operador:
- Commit del repositorio:
- Configuración Suricata/hash:

## Precondiciones

| Verificación | Sensor | Servidor | Kali | Cliente |
|---|---|---|---|---|
| Zona horaria `America/Lima` | | | | |
| `NTPSynchronized=yes` | | | | |
| Ruta hacia `10.30.0.10` por `10.20.0.1` | n/a | n/a | | |
| NIC externa aislada | | | | |

## Contadores antes/después

| Métrica | Antes | Después | Diferencia |
|---|---:|---:|---:|
| `capture.kernel_drops` | | | |
| `decoder.invalid` | | | |
| `alert_queue_overflow` | | | |
| Eventos EVE | | | |
| Espacio libre raíz | | | |

## Escenarios F0

| Escenario | Comando/servicio | Duración | Pérdida | RTT promedio | Alertas | Observaciones |
|---|---|---:|---:|---:|---:|---|
| ICMP | | | | | | |
| SSH legítimo | | | | | | |
| HTTP legítimo | | | | | | |

## Criterio de decisión

- [ ] Todas las VMs tienen hora sincronizada.
- [ ] El tráfico llega al Servidor únicamente por el Sensor.
- [ ] No hubo pérdida sostenida ni desbordamiento de colas.
- [ ] Los eventos EVE se pueden correlacionar por `timestamp`, `flow_id` y `community_id`.
- [ ] Se conservaron comandos, logs y hashes fuera del repositorio público.

Decisión: `APTO` / `NO APTO`  
Justificación:
