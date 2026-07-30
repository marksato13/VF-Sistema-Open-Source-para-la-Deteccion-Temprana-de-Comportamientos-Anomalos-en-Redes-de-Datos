# Noveno canario oficial R03 — HTTP-500MB

Fecha: 30 de julio de 2026. Campaña: `F1N-HTTP-500MB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Descarga HTTP legítima de 500 MiB, limitada a `20M` bytes/s, para representar tráfico pesado sostenido.

El preflight confirmó Git limpio y sincronizado en `fa368d30d1d973299b9de1b0c20b7fd197a867b3`, ID/feature/ledger/lock libres, 134,381,318,144 bytes disponibles y almacenamiento oficial `PASS`. Las cuatro VM y NTP pasaron, con desfase absoluto máximo de 1.424595 ms.

El archivo medía 524,288,000 bytes y tenía SHA-256 `a08a92258f621b55d08ad1e84c90c2ea6286fc6b6c9a4dfa7156afb16c190170`. NGINX devolvió HTTP 200 y `Content-Length` correcto. Suricata, rutas, generador, NIC externas y bypass pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `heavy-transfer` / `http` |
| Argumentos | `500MB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f` |

## Transferencia, rotación e integridad

`curl` obtuvo HTTP 200 y 524,288,000 bytes en 24.507443 s, a 21,393,011 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 554,931,153 |
| Capturados / recibidos / parseados | 371,273 / 371,273 / 371,273 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 17 / 17 |
| HTTP / fileinfo / `stats` / alertas | 1 / 1 / 15 / 0 |
| Delta Suricata / PCAP | 371,277 / 371,273 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Ambos PCAP rotados pasaron validación y hashes. Los cuatro paquetes adicionales de Suricata no están identificados; no existe tolerancia definida. `fileinfo=TRUNCATED`, `size=102400` limita inspección Suricata, no la descarga acreditada por `curl` y PCAP.

El Sensor produjo 91 muestras: CPU máxima 20.23 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,071,544 KiB y carga máxima 0.36. Son observaciones.

## Cobertura pesada R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 368,467 | 367,147 | 371,273 |
| 500–1500 bytes | 362,387 | 362,395 | 362,216 |
| Porcentaje objetivo | 98.3499 % | 98.7057 % | 97.5606 % |
| Menores de 500 | 6,080 | 4,752 | 9,057 |
| Longitud media | 1,476.12 | 1,481.27 | 1,464.67 |
| Duración `curl` | 24.517813 s | 24.506280 s | 24.507443 s |

Los tres episodios transfieren el mismo volumen y aportan más de 362 mil paquetes legítimos del rango solicitado por el jurado. No existe un porcentaje mínimo contratado ni se atribuyen las diferencias a TCP, offloading, fase o carga sin evidencia específica.

## Tres ventanas correlacionadas

| Ventana | Paquetes | Packet rate | Media IP | Heavy ratio |
|---|---:|---:|---:|---:|
| 1 | 104,012 | 10,401.2/s | 1,400.86990924 | 0.93154636 |
| 2 | 145,902 | 14,590.2/s | 1,489.52140478 | 0.99276227 |
| 3 | 121,359 | 12,135.9/s | 1,489.47735232 | 0.99274055 |

La primera registra intento, SYN completo y request HTTP; las demás conservan historia del request. Son ventanas de un solo episodio. R01/R02 produjeron cuatro filas; ninguna fila R03 coincide exactamente y no se agrega un duplicado global.

## Integridad raíz

```text
manifest.json          0510b680c66b01750f034475e1cf97b41dc3c2fc7ed093272b3b217b1873dfac
capture.pcap0          6c420552a99ce1e45085128d1b881f747c50e8c08227f894e4ce01ee475fc465
capture.pcap1          98301246f941dcea3c83b904b0d80367ca46708cb3a6f423cd01f788b853f646
eve-slice              1cfb4b82220960717bd57b8ab028a3e0aea058aec0f2c702ae1501fc8cfe3d7e
campaign SHA256SUMS    6b61c89599fa3ae282d91be1c8cc1ee7ddb5a4b3460751a73232f7d0aad72057
multilayer-v1.csv      f782b06e68ee31b3aeb59363b7949a0a652a83510ba455fce2ff20d23ca46834
extraction-report      bb730e6cf343f84120795bd7764fdfa5fc9b285832a8ede6ab13a45de4ab559e
feature SHA256SUMS     fb24ba8445b28200258fabd638dad2dcb73d57fda973fc18776399ee7b255db4
ledger                 1d1036d6ede29a62e221966d2269cef2e4bef6156dbbbcd3d27f2e175ef3a93d
```

El ensamblador aceptó 67/145 campañas: R03 9/29, 78 faltantes, cero inválidas/advertencias, once coincidencias `train` —sin aumento— y cero cruces observados.

Claude aceptó con limitaciones. Se corrigieron conteos EVE, paquetes/eventos, tolerancias y rangos inventados, referencias R01/R02, causalidad de fase, recursos y efectos ML.

**F1N-HTTP-500MB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-HTTP-1GB-R03`.
