# Decimoctavo canario oficial R03 — HTTP-MULTI-5

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTP-MULTI-5-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco solicitudes HTTP legítimas y secuenciales a cada VIP DMZ `10.30.0.10`, `.11` y `.12`: quince conexiones en total. El perfil aporta el punto L3 `unique_dst_ip_ratio_30s=3/15=0.2`; las VIP son identidades lógicas de una sola VM Servidor, no tres hosts físicos ni tráfico concurrente.

El dry-run confirmó Git limpio y sincronizado en `9a88225b1076239c4b7a2754950609ac44968c15`, propósito `experiment`, partición `train`, estrato `multi-destination-repeat`, argumento `5`, 130,871,226,368 bytes disponibles y volumen oficial más reserva `PASS`. ID/feature/ledger/lock estaban libres.

NTP pasó en VM01 más las cuatro VM, con desfase absoluto máximo de 0.079 ms. Las cuatro VM respondieron por SSH; las tres VIP estaban presentes y devolvieron HTTP 200 desde el Cliente. Rutas por el Sensor, NIC externas `DOWN`, bloqueo del bypass `.111–.114`, Suricata y sus contadores, captura inactiva y hash local/remoto del generador pasaron.

Las tres comprobaciones HTTP del preflight ocurrieron antes de los 70 s de quietud y del checkpoint. El warm-up capturado de 60 s y settle de 9 s fueron etapas separadas. Claude/Sonnet autorizó una única ejecución.

| Campo | Valor |
|---|---|
| Escenario / argumento | `http-multi` / `5` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |
| SHA generador local/remoto | `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203` |

## Conteos exactos e integridad

El Cliente produjo exactamente quince resultados `http_code=200`, cinco solicitudes numeradas por cada VIP, con stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 16,749 |
| Capturados / recibidos / parseados | 150 / 150 / 150 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 40 / 40 |
| `stats` / HTTP / `fileinfo` | 10 / 15 / 15 |
| Delta Suricata / PCAP | 152 / 150 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

EVE contiene exactamente cinco GET `/health` HTTP/1.1 con estado 200 y longitud 36 por VIP. Los quince `fileinfo` están `CLOSED`, `gaps=false`, `stored=false` y `size=36`. El checkpoint quedó `complete_same_inode` y ambos bundles SHA-256 pasaron.

Los dos paquetes adicionales del contador Suricata no son eventos EVE y su causa no fue identificada. No se les atribuye retransmisión, benignidad ni otra explicación; tampoco se calcula un porcentaje entre contadores de distinto alcance.

Los 150 paquetes son menores de 500 bytes, con longitud IPv4 media 81.50 y máxima 251. Este perfil multidestino ligero no contribuye paquetes al rango legítimo pesado de 500–1500 bytes.

## Feature y repetibilidad R01↔R02↔R03

R03 produjo una fila elegible:

| Paquetes | Attempts / SYN / HTTP | Packet / byte rate | IP ratio | Port ratio | Completion | HTTP error |
|---:|---:|---:|---:|---:|---:|---:|
| 150 | 15 / 15 / 15 | 15.0 p/s / 1,222.5 B/s | 0.2 | 0.06666667 | 1.0 | 0 |

`unique_dst_ip_ratio_30s=3/15` prueba tres direcciones observadas durante quince intentos. `unique_dst_port_ratio_30s=1/15` representa un solo puerto HTTP. Los ratios large, RST, error HTTP, NXDOMAIN y TLS son cero para el episodio observado.

R01, R02 y R03 tienen 150 paquetes, 16,749 bytes, quince HTTP, quince `fileinfo`, una fila y exactamente las mismas 14 features, excluyendo identidad y tiempo. Sus PCAP, EVE, hashes, timestamps y puertos origen son independientes. Es repetibilidad de un patrón determinista de baja entropía, no diversidad ni tres muestras estadísticas nuevas.

La nueva coincidencia elevó el contador global dentro de `train` de trece a catorce. Esto aumenta el peso de esa firma y deberá evaluarse de forma agregada; no invalida por sí solo la integridad de la campaña. Validation/test aún no existen.

El Sensor produjo 54 muestras: CPU máxima 1.51 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,071,344 KiB y carga máxima 0.30. Sin umbrales definidos, estos valores no permiten afirmar ausencia o presencia de presión.

## Integridad raíz

```text
manifest.json          42e6dbbf0848cc2a34721db0fc02c6a7fd0c2c169881730c15c6fff4a0974ad6
capture.pcap0          1a6370823cf51e1de82920e3983364351f5d8edf3e28d1e4d6df8ef34aa47756
eve-slice              bb1f7ba0df81b968a3e9766e4ead7add4ae2979d5cd601c498a8c809f53b8e12
campaign SHA256SUMS    32b88ccd10971b6102a4212438f4f328bf759fb1a839b0bc7a058899490b0c9f
multilayer-v1.csv      1475e86ac8a2d6d8e1cbeb4dfe2115ca0c891a7dd3ab53c54593dbe0c1b7e723
extraction-report      bf884e65f62456f91f35a7631ebf71640fca14c007a84998027b35e97ab2b2b3
feature SHA256SUMS     59705c2d4becbb9e950e9e586604b751dc734268aada0e51a9d4a3407ebb57f3
ledger                 7585812933db9c1c72f3c533a41cef4dc4ef929b959b6ac5d334bf67993ab994
```

El ensamblador oficial aceptó 76/145 campañas: R03 18/29, 69 faltantes, cero inválidas/advertencias, catorce coincidencias exactas dentro de `train` y cero entre particiones. `ready_to_build=false` permanece correcto mientras falten celdas y no existan validation/test.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTP-C2/R03`. Se corrigió su afirmación de “sin presión”: no hay umbrales para sostenerla. Se conservaron sus límites sobre delta no identificado, VIP lógicas, vector repetido y falta de particiones de evaluación.

**F1N-HTTP-MULTI-5-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTP-C2-R03`; no su ejecución.
