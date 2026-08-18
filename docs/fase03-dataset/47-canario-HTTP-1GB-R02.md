# Décimo canario oficial R02 — HTTP-1GB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTP-1GB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Mayor transferencia HTTP simple: 1 GiB legítimo limitado a `20M` bytes/s.

El preflight confirmó Git limpio y sincronizado en `2fc76d9d69dcafc3ffe9bede063ef1912765d668`, ID libre, 140,347,551,744 bytes disponibles, almacenamiento oficial válido, SSH y NTP en `PASS`. `/srv/ppi/files/1GB.bin` medía 1,073,741,824 bytes, SHA-256 `49bc20df15e412a64472421e13fe86ff1c5165e18b2afccf160d4dc19fe68a14`; HEAD devolvió HTTP 200 y Content-Length correcto. Servicios, captura, generador, NIC externas y bypass pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `1GB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 1,073,741,824 bytes en 51.022895 s, a 21,044,314 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 3 / 1,136,149,045 |
| Capturados / parseados / drops | 749,878 / 749,878 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 26 / 26 |
| HTTP 200 / fileinfo / stats / alertas | 1 / 1 / 23 / 0 |
| Delta Suricata / PCAP | 749,886 / 749,878 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los ocho paquetes adicionales del contador Suricata no están identificados. `fileinfo=TRUNCATED`, `size=102400`, `stored=false` limita seguimiento Suricata, no la descarga o el PCAP.

El Sensor produjo 133 muestras: CPU máxima 28.42 %, RSS 780,308 KiB, memoria disponible mínima 13,827,364 KiB y carga máxima 0.83.

## Cobertura pesada y estabilidad

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 751,835 | 749,878 |
| 500–1500 bytes | 742,178 (98.7155 %) | 742,164 (98.9713 %) |
| Exactamente 1500 bytes | 742,176 | 742,162 |
| Menores de 500 bytes | 9,657 | 7,714 |
| Longitud media IP | 1,481.41 | 1,485.11 |
| Duración curl | 51.010255 s | 51.022895 s |

Las dos repeticiones transfieren el mismo volumen, duran aproximadamente 51 s y contienen unos 742 mil paquetes legítimos pesados. La diferencia de paquetes pequeños se conserva sin atribuir causa TCP, cierre u offloading.

## Seis ventanas

R02 produjo seis filas elegibles:

| Ventana | Paquetes | Media IP | Heavy ratio |
|---|---:|---:|---:|
| 1 | 136,413 | 1,447.98635761 | 0.96405035 |
| 2 | 146,292 | 1,492.86353321 | 0.99507150 |
| 3 | 145,598 | 1,493.36655723 | 0.99541889 |
| 4 | 145,033 | 1,493.60327650 | 0.99558032 |
| 5 | 146,675 | 1,493.57321970 | 0.99556162 |
| 6 | 29,867 | 1,493.67790538 | 0.99564737 |

La primera registra SYN, conexión y request; las siguientes conservan el request en la historia de 60 s. Attempts/destino dejan de estar presentes al vencer sus ventanas causales. Son seis ventanas autocorrelacionadas de un episodio.

R01 produjo 81,847/145,596/145,596/145,527/145,683/87,586. La fase redistribuye las parciales inicial/final; ninguna fila R02 coincide exactamente.

## Integridad raíz

```text
manifest.json          10a1ebad70481b0021efc5ee58f5ab4d98528794042b4b8dc2cbf9b9fe1f105e
capture.pcap0          c4cd0734c91c2a8e27f6702edac77a51e4b923f2b595f971e04a3957c5f1d5f8
capture.pcap1          7f7a0af19d65914511f3c3d88b58466e0cca215702e876e48de19a8d3a633f41
capture.pcap2          52c2b6d2b395bb7b4510622773034e45cb7b346b265e8450cddc976e662b7c2c
eve-slice              a2d253b89e7bca15676ac863a7c43d5a63e56569536f6013726ee8b42ef4162b
campaign SHA256SUMS    fb7bb359a5e3e84a5543f86eea4391937677f57e14c21bc65d368e3666325d21
multilayer-v1.csv      050b260344f390a18f5b6048f138e80df6193205e715649d9060ec824724b22c
extraction-report      45063320d97c1cfc8a0a97117aab24afb52e4174b816d25c1834d81495460486
feature SHA256SUMS     14145c11edf0a5e35a89b7db2481427ad86d613cdd9f285d07a9d23070e20f17
ledger                 4339a420a0a4a9585b9bbc3cc331a81c57097a64265a56094002ebd3e21852bc
```

Todos los hashes pasaron. El ensamblador aceptó 39/145 campañas, R02 10/29, 106 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó, pero se corrigieron causas TCP, márgenes y requisitos inventados, conteos de filas, supuesto de fase requerida, versión Suricata no comprobada, estado global y expectativas JA3/JA4 fuera de las 14 features.

**F1N-HTTP-1GB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTPS-10MB-R02`.
