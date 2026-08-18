# Duodécimo canario oficial R03 — HTTPS-100MB

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTPS-100MB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 100 MiB limitada a `10M` bytes/s. El escenario pertenece al estrato `medium-transfer` y aporta tasa de bytes, paquetes legítimos grandes y una sesión TLS. Usa TLS 1.3, certificado autofirmado y `curl --insecure`; representa el laboratorio aislado, no una PKI productiva.

El preflight confirmó Git limpio y sincronizado en `65da056b5c43736c8f8a81e41041d5fbd721a650`, ID/feature/ledger/lock libres, 132,678,225,920 bytes disponibles y almacenamiento oficial `PASS`. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.485 ms.

`/srv/ppi/files/100MB.bin` medía 104,857,600 bytes y tenía SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`. NGINX devolvió HTTPS 200, `Content-Length: 104857600` y `ssl_verify_result=18`, esperado para el certificado autofirmado. Servicios, rutas por el Sensor, NIC externas `DOWN`, generador local/remoto y bloqueo ICMP/TCP22 del bypass `172.17.25.111–114` pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `medium-transfer` / `https` |
| Argumentos | `100MB`, `10M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 104,857,600 bytes en 9.520871 s, a 11,013,446 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 111,236,269 |
| Capturados / recibidos / parseados | 75,114 / 75,114 / 75,114 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 12 / 12 |
| TLS / `stats` / HTTP / fileinfo / flow | 1 / 11 / 0 / 0 / 0 |
| Delta Suricata / PCAP | 75,118 / 75,114 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

El PCAP pasó validación, transferencia y hashes; el segmento EVE quedó `complete_same_inode`. Los cuatro paquetes adicionales del contador Suricata no están identificados y no existe una tolerancia definida. No son cuatro eventos EVE ni se atribuyen a AF_PACKET, tcpdump, TCP o ruido sin evidencia.

El evento TLS corresponde a `10.20.0.20 → 10.30.0.10:443` y registra TLS 1.3, JA3, JA3S, JA4 y ALPN `h2`/`http/1.1`. HTTPS impide observar HTTP y fileinfo; sus ceros en features significan opacidad, no ausencia demostrada de requests o errores.

## Cobertura pesada R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 74,858 | 76,721 | 75,114 |
| 500–1500 bytes | 72,575 | 72,590 | 72,576 |
| Porcentaje objetivo | 96.9502 % | 94.6156 % | 96.6211 % |
| Exactamente 1500 bytes | 72,535 | 72,566 | 72,532 |
| Menores de 500 bytes | 2,283 | 4,131 | 2,538 |
| Longitud media IP | 1,455.61 | 1,421.88 | 1,450.90 |
| Duración `curl` | 9.526443 s | 9.529980 s | 9.520871 s |

Las tres repeticiones transfirieron el mismo volumen y conservaron entre 72,575 y 72,590 paquetes en el rango solicitado por el jurado. La duración difiere como máximo 0.009109 s. Es estabilidad descriptiva de estas ejecuciones, no determinismo ni una garantía futura; no se atribuyen las diferencias a una causa no medida.

## Dos ventanas correlacionadas

| Ventana UTC | Paquetes | Media IP | Heavy ratio | Attempts / SYN | SYN completion | TLS rate |
|---|---:|---:|---:|---:|---:|---:|
| `14:07:40` | 54,488 | 1,439.99994494 | 0.95868815 | 1 / 1 | 1.0 | 0.01666667 |
| `14:07:50` | 20,626 | 1,479.69106952 | 0.98608552 | 1 / 0 | 0.0 | 0.01666667 |

Los conteos no solapados de las dos ventanas suman los 75,114 paquetes; sus historiales de 30/60 s sí están correlacionados. El intento permanece por su historia de flujo y la sesión TLS por su historia L7; no son el mismo fenómeno. Solo la primera ventana contiene el SYN. Son dos filas de un episodio, no dos repeticiones independientes. Ninguna agrega un vector exacto según el ensamblador.

El Sensor produjo 64 muestras: CPU máxima 4.51 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,065,904 KiB y carga máxima 0.26. Son observaciones, no umbrales.

## Integridad raíz

```text
manifest.json          92d5a16175365d74642e1ed84c49c010aec823217f5a6a3019efdc69fa8e2659
capture.pcap0          3766a2b083c45a080123db8d7921734fdae66a15993aef3c303bafa617c30d14
eve-slice              ae509be7df041561832252252e6e67b54e64d29e3b4781af53091038ab21df67
campaign SHA256SUMS    96bd9a5ac6e129ec5ad3daf3957505026be908cd4b4debf04e27cdebf5c1fadb
multilayer-v1.csv      667db69c78fafcaa2c20efaa0c364f2c94deb5e1dd9b2996ce053efb0a3a5538
extraction-report      55fd2b540c4e67b3c092c6064aec419d4843ae92351483d171e0852e43d89aee
feature SHA256SUMS     3c5f8cdcf30e74955fe0874479bcf2cf326dfb5310036fb542c6a7bf13316d17
ledger                 49a7cc7a399cf0bbb03a0a47cc529c4a18798ebb2260f3c8317206731b935fa2
```

El ensamblador aceptó 70/145 campañas: R03 12/29, 75 faltantes, cero inválidas/advertencias, once coincidencias exactas dentro de `train` —sin aumento— y cero cruces observados. R04/validation y R05/test todavía no existen.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTPS-500MB/R03`. Se corrigieron sus expresiones de cuatro “eventos” adicionales, historias de intento/TLS y fase como causa del no duplicado.

**F1N-HTTPS-100MB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTPS-500MB-R03`.
