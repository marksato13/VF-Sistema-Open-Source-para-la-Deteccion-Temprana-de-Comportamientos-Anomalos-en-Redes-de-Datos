# Cuarto canario oficial R04 — DNS-MIXED-50-10

Fecha: 4 de agosto de 2026. Campaña: `F1N-DNS-MIXED-50-10-R04`. Partición: `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y autorización

El perfil genera cincuenta resoluciones válidas seguidas de diez NXDOMAIN controlados. Es error DNS benigno y amplía la proporción observada de nombres inexistentes; no convierte `dns_nxdomain_ratio_60s>0` en etiqueta de ataque.

El preflight fijó `dns-mixed 50 10`, repetición 4, commit limpio `e783d877d5a1e4b5010bc38e66022a4b08f34b0f`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `3e1d6b27aac4e5297c7bddae4dbf13d0c28ef3ae116ffc99e8162b8486aab317`. El almacenamiento oficial pasó y NTP quedó sincronizado en las cinco máquinas con máximo absoluto de 1.091399 ms. NIC externas, bypass, servicios, rutas, DNS, generadores, contadores, identificadores y captura pasaron. Claude revisó el perfil y autorizó exactamente una ejecución, sin scoring ni acceso a R05.

## Resultado DNS y causalidad

La campaña terminó con código cero. La salida contiene cincuenta líneas `10.30.0.10`; `dig +short` no imprime una dirección para NXDOMAIN y stderr está vacío. PCAP y EVE demuestran las sesenta transacciones completas y su orden.

| Evidencia | Resultado |
|---|---:|
| DNS requests / responses | 60 / 60 |
| `NOERROR` / NXDOMAIN | 50 / 10 |
| Respuestas A correctas | 50 × `10.30.0.10` |
| Puertos origen / IDs DNS distintos | 60 / 60 |
| Primera request / última response | `21:22:56.137348` / `21:22:57.376920 -05:00` |
| Intervalo causal completo | 1.239572 s |
| Alertas / anomalías | 0 / 0 |

Las respuestas 1–50 son `NOERROR` para `server.ppi.lab`; las 51–60 son NXDOMAIN para `error-legitimo-1..10.ppi.lab`. No hubo respuestas válidas posteriores al primer NXDOMAIN. El intervalo no cruzó un borde de 10 s.

## PCAP, EVE y Sensor

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 120 / 120 / 120 |
| PCAP | 1 archivo / 13,866 bytes |
| Drops tcpdump | 0 |
| EVE esperado / extraído | 130 / 130 |
| Tipos EVE | 120 DNS + 10 stats |
| Delta Suricata / PCAP | 124 / 120 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

EVE no contiene `flow` diferido, alertas ni anomalías en este slice. Suricata contabilizó cuatro paquetes adicionales que el PCAP causal no identifica. Se conserva como limitación sin atribuirle una causa: el PCAP contiene exactamente las 120 tramas DNS, fue recibido y parseado íntegramente y no tuvo pérdidas.

Los 120 IPv4 son menores de 500 bytes, con longitud media 85.35 y máxima 94; este perfil ligero no aporta tráfico pesado. El muestreador produjo 54 filas: CPU 0–2.27 %, RSS constante 781,720 KiB, memoria disponible 14,068,452–14,168,228 KiB y load1 0.01–0.09. Son observaciones de ejecución, no umbrales de capacidad.

## Feature y repetibilidad

El extractor produjo una fila elegible con historia de 60 s:

```text
packet_count_10s=120
flow_attempt_count_30s=60
dns_query_count_60s=60
packet_rate_10s=12.00000000
byte_rate_10s=1024.20000000
mean_ip_len_10s=85.35000000
unique_dst_ip_ratio_30s=1/60=0.01666667
flow_attempt_rate_10s=6.00000000
unique_dst_port_ratio_30s=1/60=0.01666667
dns_nxdomain_ratio_60s=10/60=0.16666667
resto_de_features=0.00000000
```

`application_observations=70` significa sesenta objetos de consulta más diez marcadores NXDOMAIN internos; no son setenta transacciones. PCAP/EVE contienen sesenta transacciones y 120 mensajes/paquetes.

Las catorce columnas del vector coinciden decimal y exactamente con R01, R02 y R03. Los artefactos, timestamps, puertos e IDs son independientes, pero la firma observada es `seen` en `train`. Se conserva y se reportará estratificada; no se deduplica, recalibra ni modifica el modelo durante R04.

## Integridad y auditoría

Ambos `SHA256SUMS` pasaron completos y el PCAP remoto/local comparte SHA-256 `9f5aac6d81780472264192e7dfa18777c595e9883c04d897e27b7fd0d44b4307`. Referencias principales:

```text
manifest.json          5282fdcf93adb5f698c9a44e0e4323addc736cd78b0dcb5b65322ae3b89825a0
eve-slice.jsonl        eeefd44e2acc5cae85f394ac2c3618d4a018ccbbc7a7fc3b4df15d644eab2ed3
campaign SHA256SUMS    ad2ff72b9bd27f275fc9020689b8ae8221f4c3ddd81ab910eb56aacdae5426bd
multilayer-v1.csv      846d6bbff65034f8c27d5d05a4ebc993e1d59261c94a35385f2766e8e5a889a0
feature SHA256SUMS     0ee962981d84e27efa9cbb886de1f106953ea67d93eebbd937ea566589720a4b
```

El auditor ejecutado desde Git limpio aceptó 91/145, R04 4/29, 54 faltantes, cero inválidas/advertencias, veinte coincidencias entre campañas y tres cruces train↔validation: `DNS-VALID-10`, `DNS-MIXED-20-2` y esta campaña. `ready_to_build=false` significa únicamente que F1 sigue incompleta.

**F1N-DNS-MIXED-50-10-R04 ACEPTADA CON LIMITACIONES.** Valida el error benigno `10/60`, una captura íntegra y el tercer vector `seen`; conserva un delta Suricata +4 sin causa atribuida. No se calcularon scores ni umbrales. Siguiente autorizado: sólo preflight independiente de `F1N-PING-10-R04`.
