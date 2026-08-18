# Noveno canario oficial R02 — HTTP-500MB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTP-500MB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Descarga HTTP legítima de 500 MiB limitada a `20M` bytes/s para representar carga sostenida pesada.

El preflight confirmó Git limpio y sincronizado en `482d77557c07f3fd85cb8c2156498ab6eb22f8ea`, ID libre, 140,902,670,336 bytes disponibles, almacenamiento oficial válido, SSH y NTP en `PASS`. `/srv/ppi/files/500MB.bin` medía 524,288,000 bytes y tenía SHA-256 `a08a92258f621b55d08ad1e84c90c2ea6286fc6b6c9a4dfa7156afb16c190170`. HEAD devolvió HTTP 200 y Content-Length correcto. Servicios, captura, generador, NIC externas y bypass pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `500MB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 524,288,000 bytes en 24.506280 s, a 21,394,026 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 554,857,408 |
| Capturados / parseados / drops | 367,147 / 367,147 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 18 / 18 |
| HTTP 200 / fileinfo / stats / alertas | 1 / 1 / 16 / 0 |
| Delta Suricata / PCAP | 367,151 / 367,147 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los 367,147 paquetes son el total repartido entre dos archivos rotados, no el conteo por archivo. Los cuatro adicionales de Suricata no están identificados. `fileinfo=TRUNCATED`, `size=102400`, `stored=false` limita seguimiento Suricata, no curl ni PCAP.

El Sensor produjo 92 muestras: CPU máxima 18.72 %, RSS 780,308 KiB, memoria disponible mínima 13,932,608 KiB y carga máxima 0.48.

## Cobertura pesada R01↔R02

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 368,467 | 367,147 |
| 500–1500 bytes | 362,387 (98.3499 %) | 362,395 (98.7057 %) |
| Exactamente 1500 bytes | 362,382 | 362,394 |
| Menores de 500 bytes | 6,080 | 4,752 |
| Longitud media IP | 1,476.12 | 1,481.27 |
| Duración curl | 24.517813 s | 24.506280 s |

Ambos episodios contienen más de 362 mil paquetes legítimos del rango solicitado por el jurado, con volumen y duración próximos. No existe un porcentaje mínimo impuesto; tampoco se atribuye la diferencia de paquetes pequeños a una causa TCP sin evidencia.

## Cuatro ventanas autocorrelacionadas

| Ventana | Paquetes | `packet_rate` | Media IP | Heavy ratio |
|---|---:|---:|---:|---:|
| 1 | 16,283 | 1,628.3/s | 1,303.04298962 | 0.86384573 |
| 2 | 150,311 | 15,031.1/s | 1,485.83896056 | 0.99022028 |
| 3 | 145,764 | 14,576.4/s | 1,491.85014132 | 0.99436761 |
| 4 | 54,789 | 5,478.9/s | 1,493.53915932 | 0.99554655 |

La primera registra SYN, conexión completada y request HTTP. Las restantes conservan el request en la historia; la última ya no conserva el intento en 30 s. Son ventanas de un episodio, no cuatro repeticiones.

R01 produjo 9,745/156,370/145,801/56,551 paquetes. El reparto cambia con la fase y ninguna fila coincide exactamente; la transferencia global permanece estable.

## Integridad raíz

```text
manifest.json          e9c0433920530201d706c2338fd9be8c09552a4630c008d9686a04fa59f742b3
capture.pcap0          5d62d8ba7eee741551121a06402f230a8cd2613a5394dcf3c9cffdfcd926e5bf
capture.pcap1          167e892b58db2158e3fa4ffbda35aa6168e817b259020aa46dc157a5b6fd039f
eve-slice              427e7f8864b0b23efd60866b542f8c27fd1fb8c8ee636f56989484c8fe322a3f
campaign SHA256SUMS    91f3532282a6a486fd7c2f4269d7b0b870d320ea715862de256c27eef3f34cf7
multilayer-v1.csv      98a9703f13c71819aa12deea3f5cfa9311b8d95ad94c487e32351f63adfc071d
extraction-report      ea5e1c71b9586efd71dbf620fcbc4102708e621d895d56fab65c3533d2b9ba18
feature SHA256SUMS     c371ce55da64aa6293ae6f0ec58f9b5eab668869ac23788e911829a6989575c1
ledger                 c2887193ca733db186f2ae97d591dfb7bcf28de3dec11de67ba67e88eaa6c8ed
```

Todos los hashes pasaron. El ensamblador aceptó 38/145 campañas, R02 9/29, 107 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó, pero se corrigieron su conteo de PCAP, causas TCP, supuestos de contaminación, eventos faltantes, umbrales y estado R02. Se conserva su autorización de preflight independiente para 1 GiB.

**F1N-HTTP-500MB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-1GB-R02`.
