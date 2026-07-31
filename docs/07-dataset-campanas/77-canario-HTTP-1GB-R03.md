# Décimo canario oficial R03 — HTTP-1GB

Fecha: 30 de julio de 2026. Campaña: `F1N-HTTP-1GB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Mayor transferencia HTTP simple de la matriz: 1 GiB legítimo limitado a `20M` bytes/s. Cierra la progresión HTTP 10/100/500 MiB/1 GiB de R03.

El preflight confirmó Git limpio y sincronizado en `c0c2c3f91229793add1c1c452de8c86ccd007781`, ID/feature/ledger/lock libres, 133,826,134,016 bytes disponibles y almacenamiento oficial `PASS`. SSH y NTP pasaron en las cuatro VM, con desfase absoluto máximo de 0.741493 ms.

`/srv/ppi/files/1GB.bin` medía 1,073,741,824 bytes y tenía SHA-256 `49bc20df15e412a64472421e13fe86ff1c5165e18b2afccf160d4dc19fe68a14`. NGINX devolvió HTTP 200 y `Content-Length` exacto. Suricata, rutas, generador, NIC externas y bypass pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `heavy-transfer` / `http` |
| Argumentos | `1GB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77` |

## Transferencia, rotación e integridad

`curl` obtuvo HTTP 200 y 1,073,741,824 bytes en 51.005882 s, a 21,051,333 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 3 / 1,136,194,787 |
| Capturados / recibidos / parseados | 750,723 / 750,723 / 750,723 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 26 / 26 |
| HTTP / fileinfo / flow / `stats` / alertas | 1 / 1 / 1 / 23 / 0 |
| Delta Suricata / PCAP | 750,733 / 750,723 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los tres PCAP rotados pasaron validación y hashes. Los diez paquetes adicionales del contador Suricata no están identificados y no existe tolerancia definida. `fileinfo=TRUNCATED`, `size=102400` limita inspección Suricata; HTTP no está cifrado y la descarga completa se acredita mediante archivo, `curl` y PCAP.

El Sensor produjo 132 muestras: CPU máxima 26.75 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,002,428 KiB y carga máxima 0.88. Son observaciones, no umbrales.

## Cobertura pesada R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 751,835 | 749,878 | 750,723 |
| 500–1500 bytes | 742,178 | 742,164 | 742,152 |
| Porcentaje objetivo | 98.7155 % | 98.9713 % | 98.8583 % |
| Menores de 500 | 9,657 | 7,714 | 8,571 |
| Longitud media | 1,481.41 | 1,485.11 | 1,483.47 |
| Duración `curl` | 51.010255 s | 51.022895 s | 51.005882 s |

Los tres episodios transfieren el mismo volumen, rotan tres PCAP y aportan alrededor de 742 mil paquetes legítimos en el rango solicitado por el jurado. No se introduce un rango porcentual obligatorio ni se atribuyen diferencias a fase, jitter, TCP u offloading sin evidencia causal.

## Seis ventanas autocorrelacionadas

| Ventana | Paquetes | Media IP | Heavy ratio |
|---|---:|---:|---:|
| 1 | 69,266 | 1,374.69036757 | 0.91344960 |
| 2 | 145,311 | 1,494.54923578 | 0.99623566 |
| 3 | 145,903 | 1,494.55355956 | 0.99623723 |
| 4 | 145,423 | 1,494.65300537 | 0.99630732 |
| 5 | 145,754 | 1,494.49335181 | 0.99619908 |
| 6 | 99,066 | 1,494.29796297 | 0.99607332 |

La primera registra intento, SYN completo y request; las demás conservan el request durante su historia L7. El intento y destino vencen en las últimas ventanas según sus horizontes. Son seis filas de un episodio, no seis repeticiones. Ninguna coincide exactamente con R01/R02 y no se agrega un duplicado.

## Integridad raíz

```text
manifest.json          283529071e809204e3614e42e0d74c64be390ae1213aa26a5ea266601dd5fd18
capture.pcap0          ac9c343dc714ee959c4a90386949c56a25a1a806f19d57c1b695c861e6436069
capture.pcap1          c32e36609f289b5c67c56a6011f12c42ae8a2e5a1ea31ed1dc0a069b1c16513f
capture.pcap2          cc205b7c993f9edb3f0099304c9d0b89da6fee7a76c9557df00a83b27d0dab2f
eve-slice              c5cdd9d3d4f9717f42907213314ea515a73fe6a90e64aa27d7eaa2d8a4ab96d7
campaign SHA256SUMS    ab01f598f87e1cb1a8d99732e0279e09afba4daef407f23d5f3f2d1906dc8d96
multilayer-v1.csv      ce5f99aaf8ded102a301dc3f56e5b5a3d715d74ca5eeac8457698e1494076c72
extraction-report      e84be5ae58b5b53497eaa105d211d7d912207b0e4db6622656f8d99675f58840
feature SHA256SUMS     8b7f216b1cc44e96946e137f72aa2c0b9bb8b2b0276c54388d5ece61cb4ab30d
ledger                 f9438834f1000e6e8138a7313cfca052f13afb8e5941a3b7eab84221eb9f195d
```

El ensamblador aceptó 68/145 campañas: R03 10/29, 77 faltantes, cero inválidas/advertencias, once coincidencias `train` —sin aumento— y cero cruces observados.

Claude aceptó con limitaciones. Se corrigieron referencias R01/R02, paquetes/eventos, conteos pequeños, HTTP/cifrado, unidades de memoria, recursos, causas, tolerancias y afirmaciones ML.

**F1N-HTTP-1GB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-HTTPS-10MB-R03`.
