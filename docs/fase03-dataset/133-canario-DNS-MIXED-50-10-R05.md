# Cuarto canario oficial R05 — DNS-MIXED-50-10

Fecha: 7 de agosto de 2026. Campaña `F1N-DNS-MIXED-50-10-R05`,
partición `test`. Estado: **ACEPTADA CON LIMITACIONES**.

## Propósito y controles previos

El perfil genera cincuenta resoluciones DNS válidas seguidas de diez nombres
inexistentes por diseño. Es una muestra legítima con errores L7 controlados, no
un ataque ni un escenario DGA. Permite observar
`dns_nxdomain_ratio_60s=10/60` sin convertir el tamaño del paquete en etiqueta.

El preflight continuo pasó sus nueve gates entre `11:01:09.998` y
`11:01:42.164 -05:00` sobre el commit limpio
`4174c049f43682e1230b0efb6984b06d2bdbda21`. Confirmó `experiment/test`,
matriz `ad22ce5f…dfa824`, argumentos `3e1d6b27…ab317`, NTP 5/5 con máximo
absoluto 0.080258 ms, 121,457,958,912 bytes disponibles, SSH 4/4, las cuatro
NIC externas `DOWN`, aislamiento y rutas, contadores Suricata limpios y los
servicios/probes requeridos.

El dry-run fijó explícitamente
`PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts`; ambos gates de almacenamiento,
marker y mountpoint pasaron. Congeló argumentos `50 10`, estimación de 150,000
bytes y tiempos de quietud/warm-up/settle/cooldown `70/60/9/30 s`. Claude leyó
el perfil y autorizó exactamente una captura. Se ejecutó una vez, sin piloto,
reintento, entrenamiento, carga de modelo ni scoring.

## Resultado DNS, PCAP y EVE

La ráfaga ocurrió entre `11:06:00.219706` y `11:06:01.520291 -05:00`. EVE
conserva el orden causal congelado: primero cincuenta pares de
`server.ppi.lab` con respuesta `NOERROR`; después diez pares
`error-legitimo-1..10.ppi.lab`, todos `NXDOMAIN`. Cada uno de los 60 pares tiene
una solicitud y una respuesta; no hay transacciones huérfanas.

| Control | Resultado |
|---|---:|
| Solicitudes / respuestas DNS | 60 / 60 |
| Respuestas válidas / NXDOMAIN | 50 / 10 |
| PCAP archivos / bytes | 1 / 13,866 |
| Capturados / recibidos / parseados | 120 / 120 / 120 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Longitud IPv4 media / máxima | 85.35 / 94 bytes |
| Paquetes de 500–1500 bytes | 0 |
| EVE esperado / extraído | 130 / 130, mismo inode |
| Tipos EVE | 120 DNS + 10 `stats`; 0 `flow` |
| Delta Suricata / PCAP | 124 / 120 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

El escenario terminó con código cero, produjo las cincuenta líneas esperadas
`10.30.0.10` y dejó stderr vacío. A diferencia de
`DNS-MIXED-20-2/R05`, este EVE no contiene flows diferidos de los probes. El
delta Suricata +4 reproduce el patrón observado en las repeticiones previas,
pero los cuatro paquetes no tienen causa atribuida. Con drops cero y el PCAP
reconciliado no se observa un efecto en la fila; no se declara riesgo cero.

Que esta celda no contenga paquetes de 500–1500 bytes es correcto: su propósito
es representar semántica DNS legítima. La observación del jurado sobre tráfico
pesado se cubre con los perfiles HTTP, HTTPS, TCP y UDP, no forzando paquetes
grandes artificiales dentro de DNS.

## Features y repetición estructural

La extracción produjo una fila a partir de 120 observaciones de paquete y 70
de aplicación: 60 consultas más diez marcadores NXDOMAIN.

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 12.0 |
| `byte_rate_10s` | 1,024.2 |
| `mean_ip_len_10s` | 85.35 |
| `flow_attempt_rate_10s` | 6.0 |
| `unique_dst_ip_ratio_30s` | 0.01666667 |
| `unique_dst_port_ratio_30s` | 0.01666667 |
| `dns_nxdomain_ratio_60s` | **0.16666667 = 10/60** |

Las catorce features son idénticas a R01, R02, R03 y R04; sólo cambia el
timestamp de ventana. Los PCAP, EVE, flow IDs, tiempos y hashes son propios de
cada ejecución. Por ello no hay reutilización de archivos ni fuga operacional,
pero sí una limitación científica: el generador determinista mantiene contenido,
orden y conteos fijos, así que esta celda `test` no es una muestra independiente
de diversidad intra-perfil. Se conserva sin deduplicación post hoc y la futura
evaluación debe declararla como repetición estructural `seen`.

Dentro de R05 las cuatro filas disponibles son distintas entre sí; el resumen
de repetición no encontró duplicados internos. R05 acumula 584 observaciones de
paquete y 304 de aplicación en estos cuatro perfiles.

## Recursos, integridad y auditoría

El Sensor registró 53 muestras: CPU 0.00–1.51 %, RSS estable en 782,504 KiB,
memoria disponible 14,082,856–14,151,612 KiB y load1 0.01–0.11. Son valores
descriptivos de este episodio ligero, no umbrales ni SLA.

```text
preflight             130a16e6bf48234d9ce2e5ba8fbb382e70fe25bc6a22005b99b9a5c0b31c11e1
manifest              6bf8a9f96eb57cdc12e90dbeca7e4cf7023228cb3cf6c893a82a07d085e38696
pcap                  62fdca94b17dab64233a2abe565a2f10c38cbc78824f456cea6da3b9c690f756
eve                   dc1addb9c254c6a922219ce46bad81044b6a1678d7aa33e0d1ea7ccf222a6940
campaign SHA256SUMS   b3450deeb5052cc90195f0aca253bc2fb1e3ad8f3fafe0f609dcafe55e9df970
features CSV          c7eac2dd853f7d49734eafa197d4074bd87483658a212a1114e6e38015c9007e
extraction report     58c48257ba068c054752ecce462aaeb877276da476676516be910acf755da9bd
feature SHA256SUMS    f5055bd9f8b85301b0b374fe252f2ac6eb10aca2e2c539e20154f56056a8b5de
ledger                22f70492a7bedc3e0fdc0296d0f8b7b4862dad6086c2dc0a0ac0254069820361
```

Los dos bundles y la copia remota del PCAP pasaron. El auditor oficial aceptó
120/145 campañas: R05 4/29, 25 faltantes, cero inválidas y cero advertencias.
El duplicado exacto elevó los totales a 30 coincidencias y 13 cruces. El gate
global sigue falso exclusivamente porque faltan 25 perfiles; no invalida las
120 campañas aceptadas.

Claude verificó manifest, PCAP, EVE completo, causalidad, extracción,
comparación R01–R05, recursos y bundles. No pudo ejecutar el auditor global y
reportó sus totales como verificados aparte por Codex. También corrigió las
rutas actuales del sistema: el generador DNS vive en `scripts/f1/run-benign.sh`
y el extractor en `scripts/features/extract_multilayer.py`.

**Decisión:** `F1N-DNS-MIXED-50-10-R05` queda cerrado con limitaciones por
repetición estructural y delta +4 no atribuido. Después de publicar este cierre,
el siguiente paso independiente es el preflight de `F1N-PING-10-R05`. R05
permanece sin scoring parcial.
