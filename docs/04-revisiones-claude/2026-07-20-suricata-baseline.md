# Revisión cruzada de la baseline de Suricata

Fecha: 20 de julio de 2026  
Revisor: Claude Code, modo de solo lectura  
Implementación y reproducción: Codex

## Alcance

Claude revisó `CLAUDE.md`, `configs/suricata/` y las modificaciones documentales de la fase. No recibió permisos de escritura ni de operación remota.

## Disposición de hallazgos

| ID | Severidad | Observación | Resultado |
|---|---|---|---|
| H-01 | Alta | Kali estaba incluido en `HOME_NET` | Confirmada y corregida |
| H-02 | Alta | Persistencia de la ruta de retorno no demostrada | Parcial: Netplan confirmado; prueba tras reinicio pendiente |
| H-03 | Alta | Posible doble gateway en otros nodos | Mitigada para destinos experimentales; NIC externas siguen pendientes de desconexión |
| H-04 | Alta | Sin ataque real ni prueba negativa integral | Confirmada; ataques y falsos positivos quedan pendientes |
| H-05 | Media | Offloading no comprobado en `ens38` | Confirmada y corregida en ambas interfaces |
| H-06 | Baja | Tipos EVE afirmados sin evidencia específica | Corregida: se separaron observados de solamente configurados |
| H-07 | Informativa | Kernel pendiente y métrica de pérdida limitada | Reconocida; reinicio y nueva medición pendientes |

## Correcciones reproducidas

### HOME_NET

Se cambió a:

```text
[10.30.0.0/24,10.20.0.20/32]
```

Esto conserva la DMZ y el Cliente legítimo como activos protegidos, pero deja Kali `10.20.0.100` dentro de `EXTERNAL_NET` para las reglas direccionales ET.

### Offloading

La revisión encontró TSO, GSO y GRO activos en `ens38`. Se habilitó un servicio systemd que aplica a `ens35` y `ens38`:

```text
TSO off
GSO off
GRO off
LRO off
```

Después se validó nuevamente la configuración con `suricata -T` y se reinició el servicio exitosamente.

## Límites aún abiertos

- Falta reiniciar el Sensor y el Servidor para validar persistencia con el kernel y las rutas cargadas desde el arranque.
- Falta ejecutar escenarios controlados de ataque desde Kali y comprobar cobertura ET.
- Falta una campaña de tráfico legítimo pesado para medir falsos positivos y pérdida de paquetes.
- Falta validar eventos DNS, TLS, SSH y anomalías con pruebas dedicadas.
- Las NIC externas todavía deben aislarse antes del dataset definitivo.

Estado: **revisión inicial atendida; no se declara cerrada la fase experimental de Suricata**.
