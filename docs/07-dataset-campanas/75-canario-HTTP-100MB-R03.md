# Octavo canario oficial R03 — HTTP-100MB

Fecha: 30 de julio de 2026. Campaña: `F1N-HTTP-100MB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña descarga por HTTP un archivo legítimo de 100 MiB desde Servidor `10.30.0.10`, limitada a `10M` bytes/s. Amplía la línea base de tráfico pesado benigno para las features L3/L4/L7.

El preflight confirmó Git limpio y sincronizado en `5f3eb302da26c38fcb1cff25e117ae6af24c3315`, ID/feature/ledger/lock libres, volumen oficial y capacidad `PASS`, SSH y NTP en las cuatro VM, con desfase absoluto máximo de 0.648435 ms.

El archivo medía 104,857,600 bytes y su SHA-256 era `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`. NGINX respondió HTTP 200 con `Content-Length: 104857600`. Suricata, rutas, generador, NIC externas y bloqueo del bypass pasaron. Una primera comparación local del SHA falló por transcribirlo incompleto; se corrigió antes de abrir la captura y no generó evidencia parcial.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `medium-transfer` / `http` |
| Argumentos | `100MB`, `10M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e` |

## Transferencia e integridad

`curl` obtuvo HTTP 200 y 104,857,600 bytes en 9.506640 s, a 11,029,932 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 77,196 / 77,196 / 77,196 |
| PCAP | 1 archivo / 111,256,113 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 77,200 / 77,196 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 13 / 13 |
| HTTP / fileinfo / `stats` / alertas | 1 / 1 / 11 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los cuatro paquetes adicionales del contador Suricata no están identificados; no se les asigna causa ni tolerancia. EVE registra HTTP 200 y `fileinfo state=TRUNCATED`, `size=102400`. Esa inspección parcial no acredita el cuerpo completo: la descarga se prueba mediante archivo, `curl` y PCAP.

El Sensor produjo 65 muestras: CPU máxima 10.57 %, RSS máximo 781,800 KiB, memoria disponible mínima 14,063,224 KiB y carga máxima 0.55. Son observaciones.

## Cobertura pesada y comparación

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 79,114 | 76,324 | 77,196 |
| 500–1500 bytes | 72,482 | 72,493 | 72,464 |
| Porcentaje objetivo | 91.6172 % | 94.9806 % | 93.8701 % |
| Exactamente 1500 | 72,469 | 72,475 | 72,449 |
| Menores de 500 | 6,632 | 3,831 | 4,732 |
| Longitud media | 1,378.58 | 1,427.23 | 1,411.22 |
| Duración `curl` | 9.511591 s | 9.525596 s | 9.506640 s |

Las tres ejecuciones transfieren el mismo volumen y aportan aproximadamente 72.5 mil paquetes legítimos en el rango solicitado por el jurado. Las diferencias de paquetes pequeños no se atribuyen a ACK, retransmisión, offloading, fase u otra causa sin análisis específico.

## Features y ventanas

El extractor procesó 77,196 paquetes, una observación de aplicación y produjo dos filas correlacionadas:

| Ventana | Paquetes | Packet rate | Byte rate | Media | Heavy ratio |
|---|---:|---:|---:|---:|---:|
| Principal | 77,189 | 7,718.9/s | 10,893,984.5 B/s | 1,411.33898612 | 0.93878661 |
| Cola | 7 | 0.7/s | 36.4 B/s | 52 | 0 |

La principal registra un intento, SYN, conexión completada, request HTTP y error ratio cero. La cola conserva el intento y request en la historia, pero no se le asigna función TCP sin decodificación. Ninguna fila R03 coincide exactamente con R01/R02; la campaña no aumenta los duplicados globales.

## Integridad raíz

```text
manifest.json          32f52c0f9f6200936f932e00a125d5a09ef78584c356628acd2b58dccbcce9f0
capture.pcap0          967aa5533f98cfe8426bdf6c89e874061e1c94787f85de67867437f56e920b2e
eve-slice              be002864996f74bb353b6476c224bbef82c645247a3a852e5dd9285c743c5ae3
campaign SHA256SUMS    6bed3ef812a3ecdc6a0ce63c3be23931f0a764033e18440aaf0660e7f7bc19c3
multilayer-v1.csv      569e67c242c8e5443cb9cf0626dc709fb862bde65a2c1404bab3fb6430b2e2b4
extraction-report      62a196f9ca984a939752af5143e9d2b38356173d6a5bebda75a1f0af275e5c85
feature SHA256SUMS     33f0686d921d2a8a1cb98d51537196a87d1c29837351d3958e00564163e20cc1
ledger                 11df9761fde026389fd524058cfbb7e612387a36b6176942a916266c62ac56ab
```

Todos los hashes pasaron. El ensamblador aceptó 66/145 campañas: R03 8/29, 79 faltantes, cero inválidas/advertencias, once coincidencias dentro de `train` —sin aumento— y cero cruces observados.

Claude aceptó con limitaciones tras un primer intento sin respuesta. Se corrigieron causalidad/tolerancia de paquetes, cola TCP no demostrada, conteo de paquetes pequeños, naturaleza de duplicados, severidad y recomendaciones ML.

**F1N-HTTP-100MB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-HTTP-500MB-R03`.
