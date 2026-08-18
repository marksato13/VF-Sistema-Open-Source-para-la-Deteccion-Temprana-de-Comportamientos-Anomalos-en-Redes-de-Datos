# Octavo canario oficial F1 — HTTPS 500 MB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTPS-500MB-R01`. Es la octava campaña aceptada y la primera HTTPS del estrato `heavy-transfer`.

## Alcance y preflight

El perfil mide una transferencia TLS 1.3 persistente de gran volumen. Conserva el certificado autofirmado y `curl --insecure`; no representa PKI productiva ni diversidad de clientes.

El preflight confirmó Git limpio en `7d8b4639c4b03e83f072dbfe5e8c0dc01ef1989e`, 147,386,679,296 bytes disponibles, ID libre, gate global PASS, NTP/zona correctos, NIC externas `DOWN`, rutas por el Sensor, NGINX activo, archivo de 524,288,000 bytes, HTTPS 200, generador íntegro y Suricata sin errores. El runner aplicó 70 segundos de quietud y 60 segundos de warm-up capturado.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTPS-500MB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `500MB`, límite `20M` bytes/s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f` |

## Ejecución e integridad

La campaña comenzó a las `22:24:08` y cerró a las `22:26:20 America/Lima`. El escenario terminó sin stderr:

```json
{"http_code":200,"bytes":524288000,"seconds":24.532030,"speed_Bps":21371570}
```

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 371,438 / 371,438 paquetes |
| PCAP total | 555,929,941 bytes |
| Archivos PCAP | 2: 512,001,223 y 43,928,718 bytes |
| Drops tcpdump | 0 |
| Delta Suricata | 371,442 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 17 / 17 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras Sensor | 92, stderr vacío |
| SHA campaña/features | todos PASS |

## Distribución y recursos

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 8,531 | 2.2967 % |
| De 500 a 1500 bytes | 362,907 | **97.7033 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 362,853 | 97.6887 % |

La longitud media fue 1,466.70 bytes y la máxima 1,500. Todos los paquetes pequeños son TCP, 8,488 sin payload y cero fragmentados.

Suricata alcanzó 7.51 % CPU, RSS de 776,372 KiB, memoria disponible mínima de 13,994,064 KiB y carga máxima de 0.58.

## EVE y features

Esta vez EVE quedó limitado a 16 stats y una sesión TLS 1.3 relevante: no aparecieron flows de preflight, mDNS ni IPv6. La quietud y el intervalo resultaron limpios dentro del alcance observado.

El extractor produjo tres filas elegibles:

| Ventana UTC | Paquetes | `mean_ip_len_10s` | `large_ip_ratio_10s` | `tls_session_rate_60s` |
|---|---:|---:|---:|---:|
| `03:25:20` | 95,676 | 1,429.71348091 | 0.95150299 | 0.01666667 |
| `03:25:30` | 147,232 | 1,479.79895675 | 0.98608998 | 0.01666667 |
| `03:25:40` | 128,530 | 1,479.21672761 | 0.98566094 | 0.01666667 |

La única sesión persiste durante todo el escenario; la tasa TLS se repite causalmente en las ventanas de 60 segundos. No existe visibilidad de HTTP dentro del cifrado.

## Integridad raíz

```text
manifest.json          5e2788f62abb3a25d8060115ba00c7852a30388f8ab6ac154bae7e3249553a50
capture.pcap0          546e57a1da0a2ad2265237dba7c467296cd7182322d7180ac9544d7fc8c13cd7
capture.pcap1          718ec1cecf971e95e8458e4271059a5fd89c0e799f6dd6472b5208598b259460
multilayer-v1.csv      61022a1c0909e0e0a22793018d76cce46372dc1aaf6b25715945a4e03f46de6f
extraction-report.json bd7c7aeb975d0fae389eceb804bbcafe803ff97bbcca02e62473f5085e4d46f7
ledger                 843c57c56f01ac00e00a1d5f19aac46fb3938b572723102d6668b421692cd74b
```

## Revisión y resolución de diversidad

Claude Code/Haiku emitió **ACEPTAR CONDICIONADO**. Confirmó integridad, cero pérdidas y recursos holgados. Pidió que el siguiente escenario de 1 GB forzara dos o tres sesiones TLS concurrentes.

No se modificará `HTTPS-1GB`: su contrato congelado representa una transferencia persistente y alterar argumentos contaminaría la comparación por tamaño. La matriz ya separa `TLS-SESSIONS-20`, cuyo objetivo es medir 20 sesiones cortas. Se mantiene así una variable causal por campaña:

- `HTTPS-1GB`: volumen y duración de una sesión;
- `TLS-SESSIONS-20`: churn y tasa de sesiones.

La carencia de múltiples certificados/JA3 sigue abierta como limitación y eventual perfil suplementario, sin reescribir F1 v2.

El ensamblador acepta ocho campañas, cero inválidas, cero advertencias y 137 faltantes.

**CANARIO HTTPS 500 MB ACEPTADO CON LIMITACIONES.** Siguiente perfil: `HTTPS-1GB/R01` con el contrato original. Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTPS-500MB-F1.md`.

> **Seguimiento:** `HTTPS-1GB/R01` fue ejecutado y aceptado; completa los tamaños HTTPS individuales. Ver `14-canario-HTTPS-1GB-F1.md`.
