# Cuarto canario oficial F1 — HTTP 500 MB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-500MB-R01`. Es la cuarta campaña oficial aceptada y la primera del estrato `heavy-transfer`.

## Preflight

Antes de ejecutar se confirmó:

- Git limpio y sincronizado en `bdda4bd84572c3b751ea86e81c247c3578247ea5`;
- ID, directorio de features y ledger libres; ninguna campaña o captura activa;
- `/srv/ppi-evidence` montado desde `/dev/sdb`, ext4 con opciones endurecidas y 149,201,313,792 bytes disponibles;
- gate global de almacenamiento en PASS;
- las cuatro VMs remotas con `NTPSynchronized=yes`, zona `America/Lima` y NIC externas en `DOWN`;
- rutas Cliente/Kali→DMZ mediante `10.20.0.1` y retorno del Servidor mediante `10.30.0.1`;
- NGINX activo, HTTP 200 y `/srv/ppi/files/500MB.bin` con 524,288,000 bytes;
- generador remoto idéntico al versionado, SHA-256 `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`;
- Suricata activo con cero drops, ifdrops, errores de decodificación y overflow.

Plan congelado:

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-500MB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `500MB`, límite cliente `20M` bytes/s |
| Warm-up / settle / cooldown | 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f` |
| PCAP estimado | 575,000,000 bytes |

## Ejecución

La campaña capturó desde `19:00:36` hasta `19:02:45 America/Lima`. El escenario terminó con código 0 y stderr vacío:

```json
{"http_code":200,"bytes":524288000,"seconds":24.517813,"speed_Bps":21383962}
```

El ledger cerró a las `19:03:12` después de extracción y cooldown. No quedó captura ni lock activo.

## Evidencia e integridad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 368,467 / 368,467 paquetes |
| PCAP total | 554,956,808 bytes |
| Archivos PCAP | 2: 512,001,333 y 42,955,475 bytes |
| Drops tcpdump | 0 |
| Delta de captura Suricata | 368,471 paquetes |
| Drops / ifdrops Suricata | 0 / 0 |
| Decoder invalid / alert overflow | 0 / 0 |
| EVE esperado/extraído | 19 / 19 |
| Transferencia PCAP | verificada |
| Límite PCAP total alcanzado | No |
| Muestras del Sensor | 92, stderr vacío |
| `SHA256SUMS` campaña/features | todos PASS |

La rotación en dos archivos es el comportamiento esperado del helper al aproximarse al límite por archivo. El gate relevante `pcap_limit_reached=false`, la suma remota/local, los hashes y el parseo total confirman que no se perdió el segmento entre archivos.

## Paquetes grandes y control TCP

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 6,080 | 1.6501 % |
| De 500 a 1500 bytes | 362,387 | **98.3499 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 362,382 | 98.3486 % |

La longitud media fue 1,476.12 bytes y la máxima 1,500.

Claude solicitó comprobar que los 6,080 paquetes pequeños no ocultaran fragmentación o tráfico extraño. El análisis independiente de ambos PCAP obtuvo:

```text
protocol=TCP                 6080
fragmented                      0
TCP payload igual a cero     6075
TCP payload positivo            5
flags ACK (0x10)             6071
longitud IP 52 bytes         5775
```

Los restantes corresponden a SYN, SYN/ACK, FIN/ACK y cinco segmentos PSH/ACK pequeños. Por tanto, la cola menor de 500 bytes representa control TCP legítimo necesario para la transferencia y no contradice la observación del jurado.

## Recursos del Sensor

| Métrica | Máximo o mínimo observado |
|---|---:|
| CPU Suricata máxima | 26.20 % |
| RSS máxima | 776,372 KiB |
| Memoria disponible mínima | 14,013,896 KiB |
| Carga de un minuto máxima | 0.70 |

La carga creció de forma controlada respecto de 100 MB, sin presión de memoria ni pérdida de captura.

## Features

El extractor procesó 368,467 paquetes y una observación HTTP. Produjo cuatro filas y las cuatro registran `eligible_training=True`:

| Ventana UTC | Paquetes | `byte_rate_10s` | `mean_ip_len_10s` | `large_ip_ratio_10s` |
|---|---:|---:|---:|---:|
| `00:01:40` | 9,745 | 1,326,228.9 | 1,360.93268343 | 0.90395074 |
| `00:01:50` | 156,370 | 22,885,651.2 | 1,463.55766451 | 0.97480335 |
| `00:02:00` | 145,801 | 21,749,967.2 | 1,491.75706614 | 0.99430731 |
| `00:02:10` | 56,551 | 8,428,427.7 | 1,490.41178759 | 0.99338650 |

La apertura SYN aparece solo en la primera ventana porque existe una única conexión persistente. Las ventanas posteriores sin SYN nuevo no significan conexión fallida.

## Límite EVE

EVE produjo 16 eventos stats, un flow, un HTTP 200 y un `fileinfo` con `TRUNCATED`, `size=102400`, `gaps=false`. La descarga y los dos PCAP están completos; el límite afecta la inspección del cuerpo por Suricata. Esta campaña no demuestra análisis de contenido completo.

## Integridad raíz

```text
manifest.json          0e0861e994fd5dea0a45ea74c678d3cbe8a40fd52377d78c1f11e68a0a02e60d
capture.pcap0          e0697c66938deadcbbc9835d0a6569d722ff170036c5f7e83e530619e1733cfa
capture.pcap1          fe237d9831d4ad7be28d232401085c669f1b6efc88af36b3a748764ffd0510c2
multilayer-v1.csv      fdc51512850c41f088659baf15da2114df13f5282ae9db4020fc841a759b0a4a
extraction-report.json 440bdc2add5bf53269640fbbfc1ed17c003f903e65e6543c9d4ad3ae074c8225
ledger                 a8599a23bd77b194e2ba1f33bf3e40ac1cf2d8cf8af6237b7adbc580540f20d2
```

## Ensamblador y revisión cruzada

La auditoría reportó cuatro campañas aceptadas, cero inválidas, cero advertencias, cero vectores duplicados y 141 celdas faltantes. `ready_to_build=false` continúa siendo correcto.

Claude Code/Haiku emitió **ACEPTAR con observaciones críticas** y autorizó el siguiente canario. Sus dudas sobre elegibilidad y paquetes pequeños fueron cerradas contra CSV, manifiesto, ensamblador y análisis de PCAP. La revisión está en `../04-revisiones-claude/2026-07-22-canario-HTTP-500MB-F1.md`.

## Decisión

**CANARIO HTTP 500 MB ACEPTADO.** Valida el primer estrato pesado, la rotación íntegra del PCAP y cuatro ventanas benignas con cero pérdidas. El siguiente escalón en orden es `HTTP-1GB/R01`, sujeto a un nuevo preflight.

> **Seguimiento:** `HTTP-1GB/R01` fue ejecutado y aceptado con una no conformidad EVE cerrada. Ver `10-canario-HTTP-1GB-F1.md`.
