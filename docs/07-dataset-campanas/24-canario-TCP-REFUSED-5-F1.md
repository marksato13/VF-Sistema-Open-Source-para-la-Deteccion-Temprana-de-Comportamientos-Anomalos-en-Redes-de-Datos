# Decimoséptimo canario oficial F1 — TCP REFUSED 5 R01

Fecha: 23 de julio de 2026. Campaña: `F1N-TCP-REFUSED-5-R01`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo

La celda representa cinco intentos legítimos de una aplicación hacia un servicio temporalmente ausente. Su función es evitar una regla implícita defectuosa: un RST o un SYN sin SYN/ACK no es ataque por sí solo.

Todos los intentos proceden del Cliente `10.20.0.20`, atraviesan el Sensor y llegan al único destino `10.30.0.10:65000`. No es un escaneo, no usa Kali y no pretende representar diversidad de orígenes ni puertos destino.

## Contrato y preflight

El perfil versionado fija:

| Campo | Valor |
|---|---|
| Perfil / repetición | `TCP-REFUSED-5` / `R01` |
| Escenario / argumentos | `tcp-refused` / `5` |
| Estrato | `legitimate-error` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| Commit | `b909f7c6bf1c223a2e281c0fcbd310b25e586b0d` |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

El preflight confirmó Git limpio/sincronizado, ID libre, captura inactiva, 142,356,746,240 bytes disponibles y almacenamiento oficial PASS. NTP pasó en las cinco VMs con offset máximo de 17.111 ms. Las cuatro NIC externas permanecieron `DOWN` y `172.17.25.111-.114` siguieron bloqueadas.

La comprobación específica verificó dos hechos:

1. `ss` no encontró listener en `10.30.0.10:65000`;
2. desde Cliente, `nc` devolvió explícitamente `Connection refused`, no timeout.

Ese sondeo ocurrió antes de los 70 s de quietud y no aparece en el PCAP oficial.

## Resultado de red

El generador informó:

```json
{"scenario":"tcp-refused","attempts":5,"expected_refusals":5}
```

El PCAP contiene exactamente diez paquetes:

| Control | Resultado |
|---|---:|
| SYN Cliente→Servidor | 5 |
| RST/ACK Servidor→Cliente | 5 |
| SYN/ACK | 0 |
| FIN | 0 |
| Puertos efímeros de origen | `34612`, `34626`, `34630`, `34642`, `34650` |
| Puerto destino | `65000` |
| Span del episodio | 2.449771 s |
| Latencia SYN→RST/ACK | 0.242–0.274 ms |

Los intentos están separados aproximadamente 0.61 s; el generador aplica `sleep 0.5` después de cada intento. La respuesta inmediata RST/ACK prueba rechazo activo del host y descarta que los cinco resultados sean simples expiraciones del comando.

## Integridad y observabilidad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado / recibido / parseado | 10 / 10 / 10 |
| PCAP | 1 archivo / 824 bytes |
| Drops `tcpdump` | 0 |
| Delta Suricata | 14 paquetes |
| Drops / `ifdrops` Suricata | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado / extraído | 10 / 10 |
| Muestras Sensor / stderr | 56 / vacío |
| Transferencia PCAP / límite | verificada / no alcanzado |
| Lock / captura residual | ausente / inactiva |

EVE contiene diez eventos `stats` y ningún evento L7. Es correcto: las conexiones se rechazan en capa 4 antes de establecer una sesión de aplicación. Las cuatro unidades de diferencia entre el delta de Suricata y el PCAP filtrado no son drops; ambos mecanismos declaran cero pérdidas.

Los diez paquetes IPv4 son menores de 500 bytes, longitud media 50 y máxima 60. Esta celda no aporta tráfico pesado; aporta normalidad L4 y complementa, no sustituye, las campañas HTTP/HTTPS pesadas.

Suricata registró CPU puntual máxima 1.53 %, RSS constante de 780,304 KiB, memoria disponible mínima de 14,109,872 KiB y carga máxima 0.22.

## Features L4

El extractor produjo dos filas elegibles con 60 s de historia:

| Ventana UTC | Paquetes 10 s | Intentos 30 s | SYN 10 s | Tasa SYN | Completitud SYN | Ratio RST | Ratio IP destino | Ratio puerto destino |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `17:37:40` | 2 | 1 | 1 | 0.1 | 0 | 0.5 | 1.0 | 1.0 |
| `17:37:50` | 8 | 5 | 4 | 0.4 | 0 | 0.5 | 0.2 | 0.2 |

La segunda ventana contiene cuatro pares en sus 10 s, pero su historia de 30 s incluye los cinco intentos. Las fórmulas son:

```text
unique_dst_ip_ratio_30s   = IP destino únicas / intentos = 1/5 = 0.2
unique_dst_port_ratio_30s = puertos destino únicos / intentos TCP+UDP = 1/5 = 0.2
rst_ratio_10s             = paquetes RST / paquetes TCP = 4/8 = 0.5
```

Los cinco puertos efímeros de origen no cambian `unique_dst_port_ratio_30s`, que mide puertos **destino**. El diccionario G5, las líneas 397–398 del extractor y la prueba sintética confirman la fórmula.

Las dos filas son ventanas autocorrelacionadas del mismo episodio, no dos repeticiones independientes. El split y la evaluación deben agrupar por `campaign_id`.

## Integridad raíz

```text
manifest.json          4232b12088d3f7fd274340060b48591120d6a746b6329c5d01f7af204155a9fa
capture.pcap0          63255a8b99d857b291001c6ccd157719c0f552dc575015477cf2ca3ed3486f76
eve-slice              2991ca8f4c1b98d04a55da11c631b4769e87c6e2d48fc9ec291c1f237f0deffc
campaign SHA256SUMS    379487c7776d67fc5c47335aff5849c2ffc69289d7fb90b7a05c16cec7eee4a7
multilayer-v1.csv      bfa18fac810d77118a5ee72515fe3630d76bbf74943b9e43a21b0ae3c1253ddd
extraction-report      1cda64cd7f27eeb86b8ee679a07dae2d3ba4ca2c72c98b3aceee5a800a685a7c
feature SHA256SUMS     933a5b92a459f20d598650dfb479cce56fc35cd6bffd08f4f6d52c8e2e4a25ee
ledger                 524b4b2b693bc59264d08020ce2e48ec0f7242b35d5935e87c3d87da199d3a7b
```

Todos los hashes internos pasaron.

## Decisión y límites

Claude condicionó inicialmente la aceptación a confirmar la fórmula de diversidad de puertos. La condición se cerró contra diccionario, código y prueba; luego emitió **ACEPTAR**. También se corrigieron tres extrapolaciones de su revisión: hay un solo origen, los puertos efímeros no son destinos y el ensamblador real quedó en 17 aceptadas.

La celda cubre una sola IP, un solo puerto cerrado, cinco intentos y una cadencia. No caracteriza toda la normalidad de fallos ni debe usarse para afirmar que cualquier patrón de RST es benigno. Las fases de anomalías deberán contrastarla con mayor frecuencia y diversidad de puertos/IP, manteniendo separación por campaña.

El ensamblador informó 145 esperadas, 17 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 128 faltantes.

**CANARIO TCP-REFUSED-5 ACEPTADO CON LIMITACIONES.** El siguiente perfil exacto es `TCP-50M/R01`, con preflight nuevo y sin ejecución por lote.
