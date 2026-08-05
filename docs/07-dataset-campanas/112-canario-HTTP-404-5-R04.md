# Decimoquinto canario oficial R04 — HTTP-404-5

Fecha: 5 de agosto de 2026. Campaña `F1N-HTTP-404-5-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco solicitudes HTTP legítimas a recursos inexistentes. El perfil aporta `http_error_ratio_60s=1`: cinco respuestas 404 de baja tasa no constituyen por sí solas un ataque.

El preflight pasó en un proceso continuo entre `10:18:59.322` y `10:19:20.795 -05:00` sobre commit limpio `a6d53852a583245281bee1e5f1dde2b421ca4d4e`. Pasaron contrato, almacenamiento, NTP 5/5 (máximo 0.405463 ms), aislamiento, bypass, SSH, rutas, Suricata, servicios, captura, IDs, DNS, ICMP y generador. Cliente y Servidor recibieron 404 únicamente en `/preflight-client-r04-404` y `/preflight-server-r04-404`, rutas distintas de las oficiales. Claude autorizó una captura. No hubo reintento ni scoring.

## Evidencia y feature

La salida registra exactamente cinco resultados `http_code=404`, uno por request, y stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 50 / 50 / 50 |
| PCAP | 1 archivo / 6,309 bytes |
| Drops tcpdump | 0 |
| Suricata / PCAP | 52 / 50 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Paquetes menores de 500 | 50 / 50 |
| longitud media / máxima | 95.70 / 378 bytes |

El delta Suricata +2 queda sin causa atribuida. EVE contiene diez stats, cinco HTTP 404 y cinco fileinfo `CLOSED`, `size=162`, `gaps=false`. Las URLs son exclusivamente `/recurso-inexistente-1` a `-5`; ninguna ruta de preflight aparece en el segmento.

La única fila elegible contiene 50 paquetes, cinco intentos, cinco SYN, cinco requests, tasas attempt/SYN 0.5/s, finalización 1.0, ratios IP/puerto 0.2 y error HTTP 1.0. Coincide exactamente con R02 y R03. Se conserva como ejecución independiente y quinto cruce `seen` train↔validation; no añade diversidad observacional y no se elimina post hoc.

El Sensor produjo 53 muestras: CPU 0–1.52 %, RSS 781,720 KiB, memoria disponible 14,078,820–14,157,184 KiB y load1 0.03–0.18. Ambos bundles pasaron: manifest `e0747cfd…`, EVE `9ed90d9f…`, CSV `a56613eb…`, ledger `f50f00f0…`.

El auditor limpio aceptó 102/145, R04 15/29, 43 faltantes, 22 coincidencias, cinco cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Es un vector `seen`, no diversidad nueva; conserva delta +2. No hubo scoring. Siguiente autorizado: sólo preflight `F1N-TLS-SESSIONS-20-R04`.
