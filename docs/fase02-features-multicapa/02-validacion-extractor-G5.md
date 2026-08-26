# Validación del extractor multicapa — G5

> ⚠️ **Documento histórico.** Registra el estado al cerrar la puerta G5, cuando
> el contrato tenía 14 variables y no existían ni el motor en línea ni el
> modelo final. Ambos existen hoy, y la ablación **ya se ejecutó**. Se conserva
> sin editar porque reescribir la validación de una puerta pasada falsearía el
> registro. Estado vigente:
> [`03-diccionario-multicapa-v2.md`](03-diccionario-multicapa-v2.md) y
> [`07-ablacion-multicapa.md`](../fase04-modelado/07-ablacion-multicapa.md).


Fecha: 21 de julio de 2026. Esquema probado: `multilayer-v1`.

## Decisión

**G5 PASS para diccionario y extractor offline.** Existen 14 variables en orden fijo, fórmulas causales, parser PCAP/EVE sin dependencias externas, hashes de entradas/salida y pruebas sintéticas/reales. El motor online y la selección por ablación siguen pendientes; no se ha entrenado aún un modelo final.

## Pruebas sintéticas

`tests/test_multilayer_features.py` construye un PCAP Ethernet/IPv4 conocido con TCP, UDP e ICMP, además de eventos HTTP 404, DNS NXDOMAIN y TLS.

Se comprobaron exactamente:

- 14 nombres y orden idéntico al esquema JSON;
- 8 paquetes, 295.8 bytes/s y longitud media 369.75 bytes;
- ratio de paquetes grandes 0.25;
- ratio de IP destino 1/3 e ICMP 0.25;
- tres intentos, SYN 0.1/s y completitud 1.0;
- ratio de puertos únicos 1.0;
- HTTP error 1.0, DNS NXDOMAIN 1.0 y TLS 1/60 sesiones/s;
- un evento HTTP 500 en `t=1011` no modifica la fila cerrada en `t=1010`;
- una historia conocida desde `t=940` vuelve elegible la fila de `t=1010`.

Resultado:

```text
Ran 2 tests in 0.003s
OK
```

## Regresión sobre G4

La extracción directa de `CAL-G4-HTTP-001` leyó 8,484 observaciones PCAP y un evento HTTP. Produjo dos ventanas, ambas no elegibles porque esa calibración es anterior al timestamp verificado de G5.

La primera ventana registró:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 848.0 paquetes/s |
| `byte_rate_10s` | 1,092,709.4 bytes/s |
| `mean_ip_len_10s` | 1,288.57 bytes |
| `large_ip_ratio_10s` | 0.85400943 |
| `flow_attempt_rate_10s` | 0.1/s |
| `syn_rate_10s` | 0.1/s |
| `syn_completion_ratio_10s` | 1.0 |
| `http_error_ratio_60s` | 0.0 |

El wrapper de campaña rechazó correctamente `CAL-G4-DNS-003` porque su `pcap-start.json` no contenía `verified_at`. No se modificaron artefactos antiguos para hacerlos compatibles retrospectivamente.

## Iteraciones G5

| Campaña | Commit | Resultado |
|---|---|---|
| `CAL-G5-DNS-001` | `ce2b4dc` | falló antes del escenario: la implementación `date` del Sensor no admite `--iso-8601=microseconds` |
| `CAL-G5-DNS-002` | `9f9308d` | campaña/extracción completas; fila no elegible con warm-up de 1 s |
| `CAL-G5-DNS-W60-001` | `9f9308d` | campaña/extracción completas; fila elegible con warm-up de 60 s |

El primer fallo no dejó `.active`, sampler ni tcpdump. Se conservó la evidencia parcial. El formato se cambió a `--iso-8601=ns`; Python acepta la coma decimal producida por esta implementación y conserva precisión de microsegundos.

## Resultado con warm-up corto

`CAL-G5-DNS-002` registró `verified_at=2026-07-21T00:38:49,897659811-05:00`. La única fila tuvo cobertura 10.102341 s debido al siguiente límite temporal de 10 s y quedó `eligible_training=false`.

La campaña pasó todos los controles: 6 paquetes capturados/parseados, 714 bytes remoto/local, SHA correcto, cero drops, 9 muestras del Sensor y EVE 8/8. El extractor contó 6 paquetes, 3 observaciones de aplicación y 1 fila.

## Resultado con 60 segundos

`CAL-G5-DNS-W60-001` usó `PPI_CAMPAIGN_WARMUP_SECONDS=60` y registró:

| Control | Resultado |
|---|---:|
| estado de campaña | `completed` |
| evidencia | `complete=true` |
| commit limpio | `9f9308da3de6cad7a896b90d7d5dfd19c4cb3533` |
| paquetes capturados/parseados | 6 / 6 |
| drops tcpdump/Suricata | 0 / 0 |
| muestras del Sensor | 54 |
| EVE extraído/esperado | 15 / 15 |
| filas extraídas/elegibles | 1 / 1 |
| cobertura de historia | 60.0 s |
| consultas DNS | 3 |
| longitud IP media | 85.0 bytes |
| ratio IP destino | 0.33333333 |
| ratio NXDOMAIN | 0.0 |

Las 54 muestras no significan una pérdida: el intervalo nominal del sampler es un segundo más la latencia SSH, y la fórmula de CPU usa el tiempo real transcurrido. La cobertura de features proviene del timestamp PCAP verificado, no del número de muestras de recursos.

`extraction-report.json` guarda SHA-256 de PCAP, EVE, esquema y CSV. Los hashes derivados y originales devolvieron `OK`. No quedó bloqueo ni proceso de captura.

## Limitaciones abiertas

- La implementación offline busca eventos directamente por ventana; es correcta para validación, pero debe convertirse a colas de 60 s antes de operar en línea.
- El parser solo soporta PCAP clásico Ethernet/IPv4. IPv6 y PCAP-NG requieren pruebas separadas.
- Una captura iniciada a mitad de flujo usa el primer emisor observado; las campañas oficiales evitan esto iniciando PCAP antes del escenario.
- Reutilización rápida de la misma 5-tupla y fragmentación avanzada requieren fixtures adicionales.
- `tls_session_rate_60s` deduplica por `flow_id`/`community_id`, pero aún debe probarse con campañas HTTPS repetidas.
- El vector todavía no ha pasado análisis de varianza, correlación, estabilidad, ablación ni comparación de modelos.
- Los datos de esta validación tienen propósito `calibration`; incluso la fila elegible por historia queda fuera del dataset final.

## Siguiente paso

G6 debe congelar la matriz F1 normal, añadir warm-up de 60 s a todas las repeticiones oficiales y recolectar diversidad HTTP/HTTPS/DNS/SSH/iperf/concurrencia. Antes de entrenar se verificará distribución, soportes L7, duplicados, drift entre campañas y separación por campaña.
