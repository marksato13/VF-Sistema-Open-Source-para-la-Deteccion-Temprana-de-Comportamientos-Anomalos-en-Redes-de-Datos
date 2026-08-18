# Decimonoveno canario oficial R02 — HTTP concurrente C2

Fecha: 28 de julio de 2026. Campaña: `F1N-HTTP-C2-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

El perfil descarga simultáneamente dos copias de `100MB.bin` desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10`. Cada `curl` usa `--limit-rate 10M`: son dos flujos del mismo cliente y destino, no dos usuarios ni dos equipos.

El preflight confirmó Git limpio y sincronizado en `a2e3f313da67534b342df084c01d32f4c9ef39a0`, ID libre, almacenamiento oficial válido y 137,392,185,344 bytes disponibles. El archivo midió 104,857,600 bytes, con SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió HTTP 200 y `Content-Length` correcto.

Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.768 ms. Servicios, captura y generador pasaron. Cliente y Kali conservaron la ruta por el Sensor; las cuatro NIC externas permanecieron `DOWN` y `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumentos | `http-concurrent` / `2 100MB 10M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `1c65572c683bb319db50f0e8a31d65ac0ee998bd62b7fdc92c459d972436b976` |

## Transferencias y concurrencia

El escenario terminó con código cero y stderr vacío:

| Flujo | HTTP | Bytes | Tiempo | Velocidad |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 9.510383 s | 11,025,591 B/s |
| 2 | 200 | 104,857,600 | 9.511103 s | 11,024,757 B/s |

Los SYN de los puertos origen `58316` y `58324` aparecieron con solo 0.000194 s de diferencia. En el PCAP, ambos flujos permanecieron activos 9.513984 y 9.512493 s: el solapamiento es real, no una ejecución secuencial.

La suma reportada es 176.402784 Mbit/s; bytes totales divididos por el mayor tiempo dan 176.396113 Mbit/s. Ambos cálculos están aproximadamente 5.14 % sobre el nominal agregado de 167.77216 Mbit/s y por debajo de 200 Mbit/s. `curl --limit-rate` no se presenta como un shaper exacto.

## Integridad, tamaños y EVE

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 222,636,558 |
| Capturados / parseados / drops | 154,784 / 154,784 / 0 |
| TCP SYN / SYN-ACK / FIN / RST | 2 / 2 / 4 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| Delta Suricata / PCAP | 154,788 / 154,784 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE extraído / esperado | 16 / 16 |
| Stats / HTTP / fileinfo | 12 / 2 / 2 |

Los cuatro paquetes adicionales de Suricata no están identificados; no se les atribuye protocolo ni causa porque su contador y el PCAP filtrado tienen alcances distintos.

Los dos eventos HTTP son `GET /files/100MB.bin` con estado 200. Ambos `fileinfo` quedaron `TRUNCATED` a 102,400 bytes y `gaps=false`. Este límite de inspección no invalida las descargas ni la captura, pero impide afirmar que Suricata inspeccionó el cuerpo completo.

| Longitud IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 9,795 | 6.3282 % |
| De 500 a 1500 bytes | 144,989 | **93.6718 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 144,958 | 93.6518 % |

La longitud media fue 1,408.37 bytes y la máxima, 1,500. La campaña aporta tráfico pesado legítimo concurrente al rango solicitado por el jurado.

## Features y borde temporal

El extractor produjo dos filas elegibles:

| Fin UTC | Paquetes | Packet rate | Byte rate | Mean IP | Large ratio | SYN / attempts / HTTP |
|---|---:|---:|---:|---:|---:|---:|
| `17:02:00` | 154,778 | 15,477.8 s⁻¹ | 21,799,270.2 B/s | 1,408.42175245 | 0.93675458 | 2 / 2 / 2 |
| `17:02:10` | 6 | 0.6 s⁻¹ | 31.2 B/s | 52 | 0 | 0 / 2 / 2 |

Los seis paquetes de la segunda fila son exactamente los cuatro FIN y dos ACK posteriores a `12:02:00`. No representan un intento fallido: los SYN y datos quedaron en la primera ventana; los horizontes causales de 30/60 s conservan dos attempts y dos HTTP. Por ello la segunda fila tiene `syn_completion_ratio_10s=0`, mientras ambas descargas están verificadas.

Las dos filas conservan `unique_dst_ip_ratio_30s=0.5` y `unique_dst_port_ratio_30s=0.5`: un destino y un puerto sobre dos intentos.

## Comparación R01↔R02

R01 y R02 completaron la misma carga en aproximadamente 9.52 y 9.51 s, sin drops, con dos filas elegibles. Sus PCAP, EVE, CSV y ledger son independientes y no existen vectores exactos coincidentes.

R02 contiene 3,317 paquetes más: 3,290 pequeños, 27 en el rango objetivo y 25 exactamente de 1,500 bytes. La proporción objetivo pasó de 95.7053 % a 93.6718 %, una diferencia de −2.0335 puntos, y la media de 1,437.75 a 1,408.37 bytes. No se midió la causa y no se atribuye a retransmisiones, buffers, offloading ni virtualización.

La alineación respecto del borde UTC sí está observada: R01 repartió 62,566/88,901 paquetes entre dos ventanas; R02 concentró 154,778 en la primera y dejó seis paquetes de cierre en la segunda. Las filas son ventanas del mismo episodio y no muestras independientes.

El Sensor produjo 68 muestras: CPU máxima 33.60 %, RSS 780,308 KiB, memoria disponible mínima 14,035,356 KiB y carga de un minuto máxima 0.46.

## Integridad raíz

```text
manifest.json          e3671aac8f02c442a6e4f6ed8712087656e7abb6c9db6c7574137d92a81cdc27
capture.pcap0          e6f1dddd2cb7bf2c8ccd14486c7245bad706f5d7de21dbf6f4e47b9cb3cd0af0
eve-slice              66201d5d945348a856091b610c27d9953cbe1c43a3a194099ca79ea8c216d284
campaign SHA256SUMS    da9cb896f3903fcda6ff377b80f12f14a159ccba055386e8b9b755dbf325d82e
multilayer-v1.csv      9c1a39c592def8507519be1a67909b01d3e37b51183d6b580a04c0053b33a34c
extraction-report      1bdbb03c215f0e4116b172672fd95dd47d1a7491205bc360f40946e16215b5ee
feature SHA256SUMS     3813927e6e110c0e0f1c85c94fe01258efa1a0d9f65a4e8b4b4c83ca3ce60ac0
ledger                 d0bfc31c4a0e3d31acaaf8f1dcede4a58cfa9daee6ea9f7f6b93a40f809ba8d3
```

El ensamblador aceptó 48/145 campañas, R02 19/29, 97 faltantes globales y 10 de R02, cero inválidas/advertencias, seis coincidencias dentro de `train` y cero entre particiones. C2 no añadió coincidencias.

Claude aceptó con limitaciones y autorizó un nuevo preflight de C4. Se descartaron sus causas TCP especulativas, parámetros equivocados de C4, proyección de 555 GB, mínimo inventado de 140 GiB y umbrales no versionados.

**F1N-HTTP-C2-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-C4-R02`, cuatro flujos de 100 MB a `5M` cada uno.
