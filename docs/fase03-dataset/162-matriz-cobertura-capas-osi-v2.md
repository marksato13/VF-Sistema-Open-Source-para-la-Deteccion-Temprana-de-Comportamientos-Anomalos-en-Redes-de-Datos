# Matriz honesta de cobertura por capas OSI

Fecha: 2026-08-12. Este inventario distingue evidencia existente de cobertura
planificada; una capa no se considera cubierta sólo porque el protocolo pueda
aparecer incidentalmente en un PCAP.

## Estado actual (F1-R05 y contrato `multilayer-v1`)

| Capa | Estado | Evidencia o límite |
|---|---|---|
| L1 Física | Fuera de alcance por decisión de alcance | VMware/ESXi transporta los paquetes; no se medirán señal, errores físicos ni negociación de enlace en esta versión. |
| L2 Enlace | Fuera de alcance por decisión de alcance | La captura se analizará desde IP; no se añadirán features de MAC, VLAN, ARP o errores Ethernet en esta versión. Podrá retomarse en una fase posterior. |
| L3 Red | Cubierta | 6 features: tasa y bytes IP, longitud media, paquetes grandes, diversidad de IP destino e ICMP. Escenarios HTTP, DNS, ping y mezclas ya aportan tráfico real de laboratorio. |
| L4 Transporte | Cubierta | 5 features: intentos, SYN, finalización SYN, RST y diversidad de puertos. TCP/UDP, conexiones rechazadas, iperf y HTTPS ejercitan estos casos. |
| L5 Sesión | Parcial | Hay sesiones TCP/TLS, pero no existe una feature explícita de duración, reanudación o cierre de sesión. |
| L6 Presentación | Parcial | TLS 1.2/1.3 y HTTPS están presentes; no se mide explícitamente versión, fallos de handshake, codificación o compresión. |
| L7 Aplicación | Parcial pero real | HTTP, DNS y TLS aportan 3 features: errores HTTP, NXDOMAIN y tasa de sesiones TLS. Falta instrumentar métodos, autenticación, nombres DNS y respuestas API. |

Por tanto, el MVP/fase F1 sí demuestra señales defendibles de L3, L4 y L7,
pero no permite afirmar cobertura completa del modelo OSI.

## Qué se cubrirá en la expansión v2

1. **L3:** TTL medio, fragmentación y diversidad de protocolos, además de más
   destinos internos y variación legítima de tamaños.
2. **L4:** retransmisiones, duración media de flujo y relación bytes enviados/
   recibidos; se conservarán TCP, UDP, ICMP y puertos rechazados.
3. **L5/L6:** duración y churn de sesiones, fallos de handshake y proporción
   TLS 1.2/1.3. Estas capas se tratarán como observables derivados, no como
   promesa de inspección completa del estado interno de cada protocolo.
4. **L7:** API local con GET/POST/PUT/DELETE, respuestas 200/201/204/301/400/
   401/403/404/500, logins válidos y fallidos; DNS multi-destino, diversidad de
   nombres y tasa de consultas. Todo quedará reconciliado con EVE y logs.

## Qué falta antes de afirmar cobertura ampliada

- Desplegar la API y validar dnsmasq en VM03; aún falta el permiso temporal
  `sudo` para `useransible`.
- Añadir el contrato `multilayer-v2`, extractor y pruebas sintéticas para cada
  feature; el plan actual sólo las propone.
- Crear matrices versionadas con episodios independientes y ejecutar pilotos,
  no reutilizar las 145 campañas F1-R05.
- Diseñar, capturar y reservar anomalías controladas para evaluación ciega;
  no deben contaminar el entrenamiento normal.
- Mantener L1/L2 fuera del alcance; no se debe inferir cobertura de esas capas
  desde una captura IP.

La secuencia defendible es: desplegar servicios internos → validar un piloto
por capa → revisar evidencia y causalidad → congelar normales → construir v2
→ calibrar → evaluar anomalías reservadas.
