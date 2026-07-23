# Quinto canario oficial F1 — HTTP 1 GB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-1GB-R01`. Es la quinta campaña aceptada, la segunda del estrato `heavy-transfer` y el cierre de los tamaños HTTP individuales de R01.

## Preflight y plan

El preflight confirmó Git limpio en `eed1fc34bdd8558c3591bf01066874784f63443d`, volumen oficial con 148,646,092,800 bytes disponibles, ID libre, ausencia de captura activa, NTP sincronizado, zona `America/Lima`, NIC externas en `DOWN`, rutas forzadas por el Sensor, NGINX activo, HTTP 200 y generador remoto idéntico al versionado.

El archivo `/srv/ppi/files/1GB.bin` midió 1,073,741,824 bytes. Suricata comenzó activo con cero drops, ifdrops, errores de decodificación y overflow.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-1GB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `1GB`, límite cliente `20M` bytes/s |
| Warm-up / settle / cooldown | 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77` |
| PCAP estimado | 1,150,000,000 bytes |

## Ejecución

La captura comenzó a las `19:45:22` y cerró a las `19:48:28 America/Lima`. El escenario terminó con código 0 y stderr vacío:

```json
{"http_code":200,"bytes":1073741824,"seconds":51.010255,"speed_Bps":21049528}
```

La extracción y el cooldown finalizaron sin dejar captura ni lock activo.

## Captura e integridad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 751,835 / 751,835 paquetes |
| PCAP total | 1,136,327,873 bytes |
| Archivos PCAP | 3 |
| Tamaños | 512,001,527; 512,001,052; 112,325,294 bytes |
| Drops tcpdump | 0 |
| Delta de captura Suricata | 751,843 paquetes |
| Drops / ifdrops Suricata | 0 / 0 |
| Decoder invalid / alert overflow | 0 / 0 |
| EVE esperado/extraído | 27 / 27 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras del Sensor | 133, stderr vacío |
| `SHA256SUMS` campaña/features | todos PASS |

La rotación en tres archivos fue continua; los tres hashes remotos/locales coinciden y la lectura completa no perdió paquetes.

## Distribución IPv4

| Rango | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 9,657 | 1.2845 % |
| De 500 a 1500 bytes | 742,178 | **98.7155 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 742,176 | 98.7153 % |

La longitud media fue 1,481.41 bytes y la máxima 1,500. Los 9,657 paquetes pequeños son todos TCP; 9,653 no llevan payload, 9,649 usan ACK, 9,425 miden 52 bytes y ninguno está fragmentado. Son control normal de la sesión.

## Recursos

| Métrica | Máximo o mínimo observado |
|---|---:|
| CPU Suricata máxima | 28.92 % |
| RSS máxima | 776,372 KiB |
| Memoria disponible mínima | 13,868,612 KiB |
| Carga de un minuto máxima | 0.56 |

El escalamiento 10 MB→100 MB→500 MB→1 GB no produjo presión de memoria ni pérdida de captura.

## Features

El extractor procesó 751,835 paquetes y una observación HTTP. Produjo seis filas, todas con 60 segundos de historia y `eligible_training=True`:

| Ventana UTC | Paquetes | `byte_rate_10s` | `mean_ip_len_10s` | `large_ip_ratio_10s` |
|---|---:|---:|---:|---:|
| `00:46:30` | 81,847 | 11,312,371.9 | 1,382.13641306 | 0.91857979 |
| `00:46:40` | 145,596 | 21,740,705.2 | 1,493.22132476 | 0.99531581 |
| `00:46:50` | 145,596 | 21,747,596.8 | 1,493.69466194 | 0.99564548 |
| `00:47:00` | 145,527 | 21,746,948.4 | 1,494.35832526 | 0.99610382 |
| `00:47:10` | 145,683 | 21,748,773.2 | 1,492.88339751 | 0.99508522 |
| `00:47:20` | 87,586 | 13,080,879.6 | 1,493.48978147 | 0.99550156 |

## No conformidad EVE y cierre

EVE registró 23 stats, un HTTP, un fileinfo y dos flow. El HTTP y uno de los flow corresponden a la descarga de 1 GB. El segundo flow comenzó a las `19:45:11`, durante el `/health` del preflight, pero Suricata lo emitió por timeout a las `19:46:14`, después de abierto el checkpoint de campaña.

La revisión comprobó:

- las seis ventanas de 10 s empiezan después de `campaign.started_at=19:45:22`;
- el único evento HTTP/DNS/TLS consumido por el extractor es el HTTP de `/files/1GB.bin`, a las `19:46:26`;
- `extract_multilayer.py` descarta explícitamente cualquier `event_type` distinto de HTTP, DNS o TLS;
- el flow previo no está en el PCAP y no modifica ninguna feature.

Por tanto, el bundle no está contaminado en sus filas, pero el segmento EVE contiene un evento diferido de preflight y debe declararse. Claude emitió **ACEPTAR CON NO CONFORMIDAD** condicionado a esta auditoría, que resultó PASS.

### Mitigación aplicada para campañas futuras

`run_matrix_profile.py` ahora impone 70 segundos de quietud antes de abrir una campaña oficial. El valor se registra como `pre_capture_quiet_seconds`; después siguen los 60 segundos de warm-up capturado. La matriz y el esquema no cambiaron, de modo que las campañas previas siguen siendo compatibles.

## Límite EVE de contenido

`fileinfo` mantuvo `TRUNCATED`, `size=102400`, `gaps=false`. Esto limita la inspección del cuerpo HTTP, no la descarga ni los PCAP. No se afirmará inspección completa del contenido de 1 GB.

## Integridad raíz

```text
manifest.json          07a252d31e733786b4e61495a5ae9bacc7f4bcedea191833615b26fb18f0628a
capture.pcap0          9e386b7b1ac3ba9dc6357a3bf24adefe7548315c075aedf5ccab2256c3771478
capture.pcap1          e3941d331ca6f7791d17a22cd2b6b38a9f0c5ffbaf3d71be3333210a5df67ebf
capture.pcap2          d9e175d7920a38e6a25f2574eecad0cfc8ed50f3e2bcec42bd094f61658002dc
multilayer-v1.csv      bfb8be4944dce02f1618a60cfb1ae561cf5c2d276e8c9a0df17b96525f4eaf0e
extraction-report.json 090dff8beaafe00aee011899ecee47c42730b79ae85a082167f5a5c790407bc9
ledger                 58ac75e828e6ff522e736a439bd941e741a63b809d709cd8cf12388c566e8fe9
```

## Ensamblador y decisión

El ensamblador acepta cinco campañas, reporta cero inválidas, cero advertencias, cero duplicados y 140 celdas faltantes. `ready_to_build=false` es correcto.

**CANARIO HTTP 1 GB ACEPTADO CON NO CONFORMIDAD CERRADA.** Se valida el máximo tamaño HTTP individual de la matriz. La revisión Claude y la resolución están en `../04-revisiones-claude/2026-07-22-canario-HTTP-1GB-F1.md`.

El siguiente perfil en orden es `HTTPS-10MB/R01`, ya protegido por la quietud previa automática.
