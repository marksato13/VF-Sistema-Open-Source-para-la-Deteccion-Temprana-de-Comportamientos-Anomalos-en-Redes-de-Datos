# Sexto canario oficial R02 — PING-100

Fecha: 27 de julio de 2026. Campaña: `F1N-PING-100-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil genera cien echo request ICMP a intervalo de 0.2 s y sus cien replies. Amplía la línea base ICMP durante unos veinte segundos y permite observar varias ventanas fijas.

El preflight confirmó Git limpio y sincronizado en `adedf34426d618e101c1b00bfa8f048197bb9d03`, ID libre, almacenamiento oficial válido, las cuatro VMs accesibles y NTP en `PASS` con desfase absoluto máximo aproximado de 0.28 ms. Ruta ICMP, servicios, Suricata y captura estaban sanos; generador remoto idéntico, NIC externas `DOWN` y bypass bloqueado.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | 100 ecos / 0.2 s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `412ee9eb50fba97316261a06e934257bc6a9467e24d73f56a2530aa368886fe0` |

## Resultado e integridad

| Control | Resultado |
|---|---:|
| Echo request / reply | 100 / 100 |
| Secuencias distintas | 1–100 |
| Pérdida | 0 % |
| Duración informada | 20.541 s |
| PCAP archivos / bytes | 1 / 22,824 |
| Capturados / parseados | 200 / 200 |
| Drops tcpdump | 0 |
| EVE extraído / esperado | 112 / 112 |
| Alertas SID `1000001` / `stats` | 100 / 12 |
| Delta Suricata / PCAP | 204 / 200 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| Evidencia / transferencia / límite | completa / verificada / no alcanzado |

SID `1000001` es telemetría permitida `PPI LAB ICMP TEST`, no una etiqueta de ataque. Los cuatro paquetes adicionales del contador Suricata no están identificados.

Los 200 paquetes IPv4 miden 84 bytes. El Sensor produjo 68 muestras, con CPU máxima 1.52 %, RSS 780,308 KiB, memoria disponible mínima 14,113,652 KiB y carga máxima 0.25; son observaciones.

## Ventanas y comparación R01↔R02

El extractor produjo tres filas elegibles:

| Ventana UTC | Paquetes | `packet_rate_10s` | `byte_rate_10s` | Attempt rate | ICMP ratio |
|---|---:|---:|---:|---:|---:|
| `18:28:10` | 48 | 4.8/s | 403.2 B/s | 0.1/s | 1.0 |
| `18:28:20` | 96 | 9.6/s | 806.4 B/s | 0.0/s | 1.0 |
| `18:28:30` | 56 | 5.6/s | 470.4 B/s | 0.0/s | 1.0 |

Todas conservan un intento canónico en la historia, `mean_ip_len_10s=84`, `unique_dst_ip_ratio_30s=1` y ratio de puertos cero. Son tres ventanas autocorrelacionadas de un solo episodio.

| Repetición | Filas | Reparto de paquetes |
|---|---:|---:|
| R01 | 4 | 6 / 96 / 96 / 2 |
| R02 | 3 | 48 / 96 / 56 |

La fase UTC cambió las ventanas parciales inicial/final. La ventana interior de 96 paquetes conserva el régimen estable y coincide exactamente con un vector de R01. Esto no prueba reutilización: PCAP, EVE, ledger, hashes y tiempos son independientes. Sí crea peso repetido y se incluye en el análisis de sensibilidad.

## Integridad raíz

```text
manifest.json          eba7af1410028a2c3481ffd59b0eb4ae0fbf810ee9f2b73939867afd67a85be0
capture.pcap0          fbae4a7b6948e16451bf8dc2ef7a078bf6842747dc189edbbc8948bf2a783cd4
eve-slice              32d2c654e10fc945f11f9d8720ef874b5c8155b7f6434f5f34c7db45ca27bdd9
campaign SHA256SUMS    f8b991a6e819b3629d909da63ce829134fe7eb0770634b73ec72da472e89beea
multilayer-v1.csv      96711e39660daf720c2552a590b9d2d5afd2f1e6815396439a72a1ac23c46a8b
extraction-report      305f811e0afaee1af70bf9436154d3e7b87ee8dd81c448fb55bd59bae51ff973
feature SHA256SUMS     370876ed721252788a06ea6c1f4c4da827dae61e648a1caf6fa20456b79ef500
ledger                 fa426110cb9af679a993cf195f57728c79ed9e5c2d6e0ffbdd4d5366dc620e27
```

Todos los hashes pasaron.

## Ensamblador, Claude y decisión

El ensamblador aceptó 35/145 campañas, con 110 faltantes, cero inválidas y cero advertencias. R02 queda 6/29 y conserva 23 perfiles pendientes. La coincidencia estable de PING-100 eleva a cuatro las coincidencias entre campañas dentro de `train`; ninguna cruza particiones.

Claude aceptó con limitaciones y explicó correctamente integridad, fase, autocorrelación y la fila estable. Se corrigió que la cuarta coincidencia es ICMP —no todas son DNS—, que R02 conserva 23 gaps y que la fase puede afectar el peso aunque no invalide la captura.

**F1N-PING-100-R02 ACEPTADA CON LIMITACIONES.** El siguiente paso autorizado es el preflight individual de `F1N-HTTP-10MB-R02`.
