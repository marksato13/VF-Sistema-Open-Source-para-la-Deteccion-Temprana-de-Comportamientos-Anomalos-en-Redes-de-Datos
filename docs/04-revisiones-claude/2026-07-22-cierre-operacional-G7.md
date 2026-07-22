# Revisión Claude — cierre operacional G7

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo que emitió el dictamen: Haiku. Alcance: revisión del resumen técnico, sin edición ni acciones sobre el laboratorio.

## Evidencia entregada al revisor

- las cuatro NIC externas estaban `DOWN`; Sensor y Servidor mostraban `NO-CARRIER`;
- las cuatro IP externas estaban bloqueadas desde VM01 por ICMP y TCP/22;
- Cliente y Kali alcanzaban al Servidor solamente mediante `10.20.0.1`;
- rutas, HTTP, NTP y servicios pasaban;
- `CAL-G7-ISOLATION-003` registró 56/56 paquetes PCAP, delta Suricata de 60 paquetes, 21 registros EVE, nueve muestras, hashes correctos y cero drops/errores;
- el control estaba marcado como calibración excluida;
- no se había realizado un reinicio posterior al cambio en ESXi.

## Dictamen

Claude calificó el estado como **APTO CONDICIONALMENTE**. Consideró confirmados el aislamiento actual, el cierre del bypass, la ruta forzada por el Sensor, la integridad de captura y la continuidad de servicios.

No autorizó una campaña oficial sin reinicio previo. La razón no es hipotética: en la auditoría anterior, el Servidor recuperó `ens34=172.17.25.112` después de reiniciar y permitió SSH directo desde VM01.

## Estado de hallazgos

| ID | Estado actualizado | Evidencia/condición |
|---|---|---|
| `CLA-G7-01` | corregida operacionalmente | `.112` bloqueada; falta persistencia tras reinicio |
| `CLA-G7-02` | corregida operacionalmente | Sensor externo sin portadora; falta persistencia tras reinicio |
| `CLA-G7-03` | mitigada | flujo interno visible en PCAP/EVE y ruta externa bloqueada; no se reintroducirá el bypass solo para recrear tráfico histórico |
| `CLA-G7-04` | rechazada para dataset oficial histórico | siguen existiendo cero campañas oficiales aceptadas |

## Recomendación aceptada

Reiniciar primero el Servidor, comprobar que su NIC externa continúa aislada y repetir rutas, servicios y controles positivos/negativos. Hasta entonces, G7 es operacionalmente apto, pero el canario oficial permanece bloqueado.
