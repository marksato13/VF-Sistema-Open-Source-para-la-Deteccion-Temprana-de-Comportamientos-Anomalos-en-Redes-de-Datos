# Decimosexto canario oficial F1 — HTTP concurrente C8 R01

Fecha: 23 de julio de 2026. Campaña: `F1N-HTTP-C8-R01`. Estado: **ACEPTADA CON LIMITACIONES** después de archivar íntegramente el primer intento rechazado y repetir el perfil con el búfer PCAP corregido.

## Objetivo y separación de intentos

El perfil ejecuta ocho descargas simultáneas de `100MB.bin` desde el Cliente `10.20.0.20` hacia NGINX `10.30.0.10`, siempre a través del Sensor. Cada flujo usa `--limit-rate 2M`; el agregado nominal es 16 MiB/s o 134.217728 Mbit/s.

No se cambió el ID de matriz. La evidencia fallida original permanece fuera de las raíces activas como:

```text
/srv/ppi-evidence/artifacts/failed-attempts/F1N-HTTP-C8-R01/attempt-01/
/var/lib/ppi-captures-failed/F1N-HTTP-C8-R01/attempt-01/
```

Ese intento conserva el commit de evidencia `99919343017dedb4c2670fdb29c0f6812c199953`. El reintento aceptado es una generación diferente: está en las raíces activas, usa el commit `3916240194977b1f8d7d335ef6df6bc3c56b98ef` y su manifest tiene `status=completed`, `purpose=experiment` y `partition=train`.

## Preflight

Antes de ejecutar se comprobó:

- Git limpio, `HEAD=origin/main=3916240194977b1f8d7d335ef6df6bc3c56b98ef`;
- ID, feature, ledger y lock activos ausentes;
- volumen oficial ext4 montado con 143,245,873,152 bytes disponibles y gate de almacenamiento PASS;
- cinco nodos con NTP válido; offsets absolutos inferiores a 31 ms;
- captura inactiva y Suricata activo, con drops, `ifdrops`, inválidos y overflow en cero;
- NIC externas de Sensor, Servidor, Kali y Cliente `DOWN`; las cuatro direcciones `172.17.25.111-.114` bloqueadas por ICMP y TCP/22;
- rutas Cliente/Kali→`10.30.0.10` mediante `10.20.0.1` y retorno por `10.30.0.1`;
- NGINX HTTP 200, archivo remoto de 104,857,600 bytes y generador local/remoto con el mismo SHA-256.

El contrato quedó congelado:

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-C8` / `R01` |
| Escenario / argumentos | `http-concurrent` / `8 100MB 2M` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `048896cb26996464f54cd1f8d12cceb7d61e49246645aea858af30019dec7bdb` |

## Transferencia y concurrencia

La campaña se capturó entre `12:10:21` y `12:13:13 America/Lima`. Las ocho descargas devolvieron HTTP 200, cero stderr y 104,857,600 bytes cada una:

| Métrica | Resultado |
|---|---:|
| Bytes totales | 838,860,800 |
| Duración mínima / máxima informada por Cliente | 49.504427 / 49.509342 s |
| Throughput agregado por suma de velocidades | 135.555656 Mbit/s |
| Throughput por bytes / mayor duración | 135.547881 Mbit/s |
| Nominal agregado | 134.217728 Mbit/s |
| Margen hasta el techo de 200 Mbit/s | 64.444344 Mbit/s |

El observado fue aproximadamente 1.00 % mayor que el nominal. `curl --limit-rate` limita un promedio y no constituye shaping exacto; el valor sigue muy por debajo del techo operativo calibrado.

Los puertos origen fueron `48964`, `48974`, `48990`, `48996`, `48998`, `49004`, `49018` y `49024`. Los ocho SYN iniciales aparecieron en una ventana de 46.726 ms. Cada flujo tuvo un SYN, un SYN/ACK, dos FIN y cero RST; sus spans estuvieron entre 49.505143 y 49.510974 s. Esto demuestra solapamiento real de ocho conexiones, no ocho usuarios ni ocho destinos.

## Integridad

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado / recibido / parseado | 600,128 / 600,128 / 600,128 |
| Drops `tcpdump` | **0** |
| Archivos / bytes PCAP | 2 / 888,809,952 |
| Tamaños PCAP | 512,000,572; 376,809,380 bytes |
| Transferencia remota/local | verificada |
| Límite de rotación alcanzado | No |
| Delta Suricata | 600,134 paquetes |
| Drops / `ifdrops` Suricata | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado / extraído | 37 / 37 |
| Muestras Sensor / stderr | 122 / vacío |
| Lock y captura residuales | ausentes / inactiva |

Los seis paquetes de diferencia entre el delta de Suricata y el PCAP IPv4 no son drops: ambos mecanismos declaran cero pérdidas y el resumen PCAP cuenta únicamente IPv4 dentro del filtro LAN↔DMZ.

EVE contiene 21 `stats`, ocho `http` y ocho `fileinfo`. Los ocho HTTP corresponden a GET 200 de `/files/100MB.bin`. Cada `fileinfo` termina `TRUNCATED` en 102,400 bytes y `gaps=false`: es el límite de inspección de archivo de Suricata, no truncamiento de la descarga ni del PCAP.

## Tráfico pesado y recursos

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 20,096 | 3.3486 % |
| De 500 a 1500 bytes | 580,032 | **96.6514 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 579,349 | 96.5376 % |

La longitud media fue 1,451.03 bytes y la máxima 1,500. Esta celda añade tráfico legítimo pesado concurrente al rango normal solicitado por el jurado; el tamaño grande no es etiqueta de ataque.

Suricata alcanzó 31.53 % en la métrica puntual del proceso, 780,304 KiB de RSS, 13,880,052 KiB de memoria disponible mínima y carga máxima de un minuto 0.65. La CPU es descriptiva, no porcentaje agregado de seis vCPU ni gate formal.

## Features y dependencia entre filas

El extractor generó seis filas, todas con 60 s de historia y `eligible_training=true`. La primera ventana contiene:

- 79,644 paquetes;
- ocho SYN y ocho intentos;
- ocho solicitudes HTTP;
- `flow_attempt_rate_10s=0.8`;
- `syn_completion_ratio_10s=1`;
- `unique_dst_ip_ratio_30s=1/8=0.125`;
- `large_ip_ratio_10s=0.83801667`.

Las siguientes ventanas de carga alcanzan ratios de paquetes grandes entre 0.97214786 y 0.99157102. Las seis filas pertenecen al mismo episodio, Cliente, servidor, archivo y protocolo. Son ventanas autocorrelacionadas y no seis repeticiones independientes; el modelado y cualquier split deben agrupar por `campaign_id`.

## Comparación controlada

| Ejecución | Rol | Capturados / recibidos | Drops | Decisión |
|---|---|---:|---:|---|
| primer oficial | evidencia negativa archivada | 596,704 / 597,180 | 476 | rechazado |
| `CAL-G6-HTTP-C8-R01` | calibración excluida | 605,266 / 605,266 | 0 | PASS diagnóstico |
| reintento oficial | experimento `train` | 600,128 / 600,128 | 0 | aceptado |

La comparación apoya el aumento de búfer a 65,536 KiB bajo estas condiciones. Tres ejecuciones no demuestran que jamás habrá pérdida; cada campaña futura conserva el gate de cero drops.

## Integridad raíz

```text
manifest.json          dc107dd585ec5af59a2eca73ea5d8f4e5ce5237bd2aeb8a9054add478b370905
capture.pcap0          96d3e23ca1d3233243210b7e865b0ec90bd46e7de905cb64afb58b394da88ff3
capture.pcap1          979f8e2122c25682f1af5c390335e29890f959b17c7bc9f87a304cfe435d272c
eve-slice              c95de5a9f8dc5879e7d89dffb8690e9df05419a1a3b94cabeca076edb189aa26
campaign SHA256SUMS    e06feacc3d0a04586de29885ab340200081ab88bbc31e6457d9cc5d9eb85c49e
multilayer-v1.csv      1a19f9df66bad0787af11f7b8f5cc3c2b0e1105807dd4783e900809e12ea0f76
extraction-report      c4351636c478e58be63a5271ed32736f6082d18adb35a431ab67402b8c54a3b8
feature SHA256SUMS     2ff113cc03ed160826ee8c010846abc8eed4815953ec4fff7904113cfad4bd81
ledger                 b78e2e37d83598fac1ae15d65e06d2d45af71799f5eb025db7483ab52e1089b4
```

Los paquetes de hashes de campaña y features pasaron completamente.

## Decisión

El ensamblador posterior informó 145 celdas esperadas, 16 aceptadas, 0 inválidas, 0 advertencias, 0 duplicados y 129 faltantes. `CAL-G6-HTTP-C8-R01` sigue excluida por `not_experiment`; el intento fallido sigue fuera de las raíces activas y conserva sus hashes.

Claude emitió aceptación después de separar las tres generaciones y corregir cifras arrastradas de C4, la calibración y el primer intento. Sus condiciones finales —preflight G7 e integridad de hashes— ya estaban satisfechas antes del dictamen.

**CANARIO HTTP C8 ACEPTADO CON LIMITACIONES.** El siguiente perfil por orden de matriz es `TCP-REFUSED-5/R01`; exige un preflight nuevo y no se ejecuta como lote.
