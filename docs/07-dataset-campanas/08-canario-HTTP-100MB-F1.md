# Tercer canario oficial F1 — HTTP 100 MB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-100MB-R01`. Es la tercera campaña `purpose=experiment` aceptada y la segunda celda oficial de tráfico HTTP legítimo pesado.

## Ubicación dentro del proyecto

El proyecto ya está en **simulación controlada y captura del dataset oficial F1**. Las fases de infraestructura, automatización, aislamiento persistente, orquestación, PCAP, esquema de 14 features y ensamblador ya pasaron sus gates. Aún no corresponde entrenar el modelo final: primero debe completarse el dataset normal sin mezclar repeticiones ni particiones.

## Preflight

Antes de ejecutar se comprobó:

- Git limpio y sincronizado en `cdcef054bd02c469d187f61d445511eb79ac081f`;
- ID, directorio de features y ledger libres; ninguna campaña o captura activa;
- volumen `/srv/ppi-evidence` en `/dev/sdb`, ext4 con `rw,nosuid,nodev,noexec,noatime` y 149,312,966,656 bytes disponibles;
- gate global de almacenamiento en PASS;
- las cuatro VMs remotas en `America/Lima` y `NTPSynchronized=yes`;
- NIC externas de Sensor, Servidor, Kali y Cliente en estado `DOWN` y rutas internas conservadas;
- Cliente y Kali con ruta a DMZ mediante `10.20.0.1`; Servidor con retorno mediante `10.30.0.1`;
- NGINX activo, `/srv/ppi/files/100MB.bin` con 104,857,600 bytes y HTTP 200 desde el Cliente;
- generador remoto y versionado con SHA-256 `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`;
- Suricata activo, `kernel_drops=0`, `kernel_ifdrops=0`, `decoder_invalid=0` y `alert_queue_overflow=0`.

El plan versionado fue:

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-100MB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `100MB`, límite cliente `10M` bytes/s |
| Estrato | `medium-transfer` |
| Warm-up / settle / cooldown | 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e` |
| PCAP estimado | 115,000,000 bytes |

## Ejecución

La captura comenzó a las `18:48:02` y cerró a las `18:49:35 America/Lima`. El escenario terminó con código 0 y stderr vacío:

```json
{"http_code":200,"bytes":104857600,"seconds":9.511591,"speed_Bps":11024191}
```

El ledger cerró a las `18:49:41` después de extracción y el cooldown final terminó sin dejar captura ni lock activo.

## Integridad y captura

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 79,114 / 79,114 paquetes |
| Tamaño PCAP | 111,438,325 bytes |
| Drops tcpdump | 0 |
| Delta de captura Suricata | 79,119 paquetes |
| Drops / ifdrops Suricata | 0 / 0 |
| Decoder invalid / alert overflow | 0 / 0 |
| EVE esperado/extraído | 15 / 15 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras de recursos | 65, stderr vacío |
| `SHA256SUMS` campaña y features | todos PASS |

Distribución de longitud IPv4:

| Rango | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 6,632 | 8.3828 % |
| De 500 a 1500 bytes | 72,482 | **91.6172 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 72,469 | 91.6007 % |

La longitud media fue 1,378.58 bytes y la máxima 1,500. La campaña amplía en un orden de magnitud el volumen del canario anterior y conserva la misma conclusión: una transferencia legítima puede estar dominada por paquetes grandes.

Durante el muestreo, Suricata alcanzó 21.62 % de CPU, RSS estable de 776,248 KiB y carga de un minuto máxima de 0.87. La memoria disponible mínima del Sensor fue 14,155,496 KiB. No se observó presión de recursos ni pérdida asociada.

## Features extraídas

El extractor procesó 79,114 observaciones de paquetes y una observación de aplicación. Produjo dos ventanas y ambas son elegibles:

| Ventana UTC | Paquetes | `byte_rate_10s` | `mean_ip_len_10s` | `large_ip_ratio_10s` |
|---|---:|---:|---:|---:|
| `23:49:10` | 49,019 | 6,409,135.7 | 1,307.47989555 | 0.86703115 |
| `23:49:20` | 30,095 | 4,497,352.4 | 1,494.38524672 | 0.99621200 |

La primera ventana registra la apertura TCP (`syn_completion_ratio_10s=1.0`). La segunda no contiene un SYN nuevo dentro de sus 10 segundos y por eso su tasa SYN es cero; no representa un fallo de conexión. Ambas conservan `http_error_ratio_60s=0.0`.

## Límite de inspección EVE

EVE contiene un evento HTTP 200 y un `fileinfo` con `state=TRUNCATED`, `size=102400`, `gaps=false` y `stored=false`. Igual que en HTTP 10 MB, esto limita el cuerpo inspeccionado por Suricata, no la descarga ni la captura. Los 104,857,600 bytes recibidos, el PCAP completo, los conteos 79,114/79,114, los hashes y cero drops respaldan la transferencia.

La campaña sirve para volumen, tamaños, flujo TCP y semántica HTTP pasiva. No demuestra inspección completa del contenido de 100 MiB ni detección basada en payload.

## Integridad raíz

```text
manifest.json          a16425e969730bca0ee3d1e59652a6e3214e5110b30008ffa0a206ca24cbc454
capture.pcap0          ce80090e1ed1b3e2435194303d5fa1ed2a1c64811ae45d3a2d92932d0b620e0b
multilayer-v1.csv      4c37ab3792dfb1a90d73b5419a38b955f1997c4ac8be1e273ce3b214acc30d22
extraction-report.json c2f40defabb4b7ff164bb0cb39f293ec27541abbfc04de256fe41f80eee5bf0a
ledger                 45fbd7aa0c7ff603332909fda81b9f0914a26e201f0ef8912ac3b4ca2c0c4516
```

## Ensamblador

```text
expected_campaigns=145
accepted_campaigns=3
invalid_campaigns=0
campaign_warnings=0
missing_cells=142
ready_to_build=false
```

Acepta `DNS-MIXED-20-2/R01`, `HTTP-10MB/R01` y `HTTP-100MB/R01`, todas en `train`. No existen ventanas ni vectores duplicados reportados.

## Revisión Claude

Claude Code 2.1.217 con Haiku emitió **VEREDICTO: ACEPTAR**. Reconoció integridad del PCAP, cero pérdidas, cobertura del rango solicitado y dos filas elegibles. Su límite principal coincide con la auditoría local: no declarar análisis L7 de contenido completo.

El texto de Claude llamó “calibración” a la ejecución en una frase y pidió aclarar la nomenclatura. La evidencia primaria resuelve el punto: manifiesto y ledger registran `purpose=experiment`, repetición `R01`, partición `train`; el ensamblador rechaza calibraciones y aceptó esta celda. La revisión completa y esta corrección están en `../04-revisiones-claude/2026-07-22-canario-HTTP-100MB-F1.md`.

## Decisión

**CANARIO HTTP 100 MB ACEPTADO.** Es la tercera celda oficial y la segunda evidencia pesada. El siguiente escalón propuesto es `HTTP-500MB/R01`, pero requiere un nuevo preflight y una ejecución aislada; no se autoriza todavía el lote ni el entrenamiento final.
