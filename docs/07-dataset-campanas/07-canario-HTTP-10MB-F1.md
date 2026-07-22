# Segundo canario oficial F1 — HTTP 10 MB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTP-10MB-R01`. Es la segunda ejecución con `purpose=experiment` aceptada por el ensamblador y la primera evidencia oficial F1 que responde directamente a la observación del jurado sobre tráfico legítimo pesado.

## Autorización y preflight

El primer canario DNS ya estaba aceptado y G7 permanecía **APTO PERSISTENTE**. Antes de generar tráfico se confirmó:

- repositorio limpio y sincronizado en `490f53e5ef594bdf58461d6c0ab1436803e14dc3`;
- ninguna campaña local ni captura remota activa y el ID nuevo libre;
- volumen oficial `/srv/ppi-evidence/artifacts` montado desde `/dev/sdb` con `rw,nosuid,nodev,noexec,noatime` y 149,324,308,480 bytes libres;
- gate global de almacenamiento de la matriz en PASS;
- NIC externas de VM02–VM05 aisladas y rutas LAN↔DMZ todavía forzadas por el Sensor;
- `NTPSynchronized=yes` en las cuatro VMs remotas;
- servicio HTTP y archivo `/files/10MB.bin` disponibles en el Servidor; tamaño exacto 10,485,760 bytes;
- Suricata y sus contadores sanos, captura inactiva y generador remoto idéntico al versionado.

El plan congelado fue:

| Campo | Valor |
|---|---|
| Perfil | `HTTP-10MB` |
| Repetición | `R01` |
| Partición | `train` |
| Escenario | `http` |
| Argumentos | `10MB`, límite cliente `2M` |
| Warm-up / settle / cooldown | 60 / 9 / 30 s |
| Matriz | `f1-normal-v2` |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a` |
| PCAP estimado | 12,000,000 bytes |

## Ejecución y transferencia

La campaña comenzó a las `18:32:51` y cerró a las `18:34:13 America/Lima`. El escenario terminó con código 0 y stderr vacío:

```json
{"http_code":200,"bytes":10485760,"seconds":4.504656,"speed_Bps":2327760}
```

La respuesta HTTP 200, el conteo de 10,485,760 bytes y la transferencia verificada del PCAP demuestran que la descarga terminó. Después del cooldown no quedaron locks ni capturas activas.

## Evidencia de captura

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 7,912 / 7,912 paquetes |
| Tamaño PCAP | 11,142,194 bytes |
| Drops tcpdump | 0 |
| Delta de captura Suricata | 7,914 paquetes |
| Drops/ifdrops Suricata | 0 / 0 |
| Decoder invalid / alert overflow | 0 / 0 |
| EVE esperado/extraído | 13 / 13 |
| Muestras de recursos del Sensor | 57 |
| Transferencia y validación PCAP | PASS |
| Límite de rotación PCAP alcanzado | No |
| `SHA256SUMS` campaña | todos PASS |

La distribución de longitudes IPv4 fue:

| Rango | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 664 | 8.3923 % |
| De 500 a 1500 bytes | 7,248 | **91.6077 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 7,244 | 91.5571 % |

La longitud IP media fue 1,378.26 bytes y la máxima 1,500. El resultado demuestra con datos oficiales de entrenamiento que un flujo HTTP benigno puede estar dominado por paquetes grandes. La etiqueta proviene del escenario controlado y no del tamaño del paquete.

## Límite observado en EVE

Suricata produjo un evento HTTP 200 para `/files/10MB.bin` y un evento `fileinfo`, pero este último registró:

```text
state=TRUNCATED
size=102400
stored=false
gaps=false
```

Esto es truncamiento de la **inspección/reensamblado del cuerpo dentro de Suricata**, no truncamiento del PCAP ni de la descarga. La transferencia completa queda respaldada por los 10,485,760 bytes de `curl`, el PCAP de 11,142,194 bytes, 7,912/7,912 paquetes parseados, cero drops y `pcap_limit_reached=false`.

No se afirmará que EVE inspeccionó los 10 MiB completos. Esta limitación no invalida las 14 features actuales: `http_error_ratio_60s` necesita el estado HTTP, mientras las variables de volumen y tamaño se calculan desde el PCAP. Antes de diseñar features futuras basadas en contenido completo deberá revisarse el límite de inspección, su costo de RAM y el riesgo de afectar rendimiento.

## Extracción `multilayer-v1`

El extractor produjo una fila elegible a partir de 7,912 observaciones de paquetes y una observación de aplicación:

| Feature o control | Valor |
|---|---:|
| Filas / elegibles | 1 / 1 |
| Cobertura histórica | 60 s |
| `packet_rate_10s` | 791.2 |
| `byte_rate_10s` | 1,090,481.0 |
| `mean_ip_len_10s` | 1,378.26213347 |
| `large_ip_ratio_10s` | **0.91607685** |
| `flow_attempt_rate_10s` | 0.1 |
| `syn_rate_10s` | 0.1 |
| `syn_completion_ratio_10s` | 1.0 |
| `unique_dst_ip_ratio_30s` | 1.0 |
| `unique_dst_port_ratio_30s` | 1.0 |
| `http_error_ratio_60s` | 0.0 |

La alta razón de paquetes grandes se conserva como comportamiento benigno de entrenamiento; no se convierte en una etiqueta de anomalía.

## Integridad raíz

```text
manifest.json          81552b16a8b5a6863e297f1364386721d6cfa09c5889a1691e7787856bd5b269
capture.pcap0          93634ebe33468fbf0c4f75590dda1797c721665d735eca1aa1906e9bdb287b94
multilayer-v1.csv      f571ce230e8e61d1d8d6343c7f4b76c148d2919ac464fa029b45f1ee72984a30
extraction-report.json 23b21fc6dba20042262b4acd974ee190c4ad5c4e4aa72af90ee0a77d194e0fa5
ledger                 86a5c35db984ccdac8a12fe250c6061bfc3f7b4f154b397353b827f22235b39f
```

Los artefactos runtime permanecen en el volumen dedicado y fuera de Git.

## Resultado del ensamblador

La auditoría posterior reportó:

```text
expected_campaigns=145
accepted_campaigns=2
invalid_campaigns=0
campaign_warnings=0
missing_cells=143
ready_to_build=false
```

Las celdas aceptadas son `DNS-MIXED-20-2/R01/train` y `HTTP-10MB/R01/train`. Todavía no se genera `train.csv` porque el ensamblador exige completar la matriz.

## Revisión cruzada

Se solicitó una revisión adversarial del bundle a Claude Code. El proceso realizó llamadas a la API y terminó, pero la CLI no devolvió contenido final utilizable; por tanto no se atribuye una aprobación a Claude. La decisión se apoya en los gates automatizados, hashes recalculados, cruce manifiesto/ledger/reporte, conteo independiente de PCAP/EVE y aceptación del ensamblador.

## Decisión

**CANARIO HTTP ACEPTADO.** La campaña demuestra que el pipeline oficial soporta tráfico legítimo pesado con 91.6077 % de paquetes IPv4 entre 500 y 1500 bytes, transferencia completa, una fila elegible y cero pérdidas.

Esto valida la primera celda pesada, no toda la observación del jurado ni el dataset completo. El siguiente paso seguro es una escalada por tamaños: ejecutar `HTTP-100MB/R01` con nuevo preflight, auditar rendimiento y drops, y solo entonces evaluar 500 MB y 1 GB. No se autoriza un lote desatendido.
