# Decimotercer canario oficial R03 — HTTPS-500MB

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTPS-500MB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 500 MiB limitada a `20M` bytes/s. Es el primer perfil HTTPS `heavy-transfer` de R03 y aporta volumen cifrado sostenido, paquetes legítimos grandes y una sesión TLS. El certificado es autofirmado y `curl` usa `--insecure`; representa el laboratorio aislado, no una PKI productiva.

El preflight confirmó Git limpio y sincronizado en `aeb24973e7e8047aa9dccf29b5ba22dd73b0d334`, ID/feature/ledger/lock libres, 132,566,781,952 bytes disponibles y almacenamiento oficial `PASS`. NTP pasó en VM01 y las cuatro VM, con desfase absoluto máximo de 0.105119 ms. El gate versionado fija `MAX_ABS_OFFSET_SECONDS=0.1`; no es un umbral inventado ni significa que solo cuatro de cinco nodos pasaron.

`/srv/ppi/files/500MB.bin` medía 524,288,000 bytes y tenía SHA-256 `a08a92258f621b55d08ad1e84c90c2ea6286fc6b6c9a4dfa7156afb16c190170`. NGINX devolvió HTTPS 200, `Content-Length: 524288000` y `ssl_verify_result=18`, esperado para el certificado autofirmado. Las cuatro VM, servicios, rutas por el Sensor, NIC externas `DOWN`, generador local/remoto, captura inactiva, contadores Suricata y bloqueo del bypass pasaron.

Claude/Sonnet revisó este preflight y autorizó una única ejecución, condicionada a la auditoría posterior y cero drops. Se corrigió su conteo NTP `4/5`: fueron cinco nodos NTP y cuatro VM por SSH.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `heavy-transfer` / `https` |
| Argumentos | `500MB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f` |

## Transferencia, rotación e integridad

`curl` obtuvo HTTP 200, 524,288,000 bytes en 24.525157 s, a 21,377,559 B/s; stderr quedó vacío. Se registra la velocidad observada sin convertir el máximo de calibración iperf3 TCP en criterio de aceptación de HTTPS.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 555,881,304 |
| Capturados / recibidos / parseados | 371,204 / 371,204 / 371,204 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 17 / 17 |
| TLS / `stats` / HTTP / fileinfo / flow | 1 / 16 / 0 / 0 / 0 |
| Delta Suricata / PCAP | 371,208 / 371,204 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos PCAP pasaron validación, transferencia y hashes; EVE quedó `complete_same_inode`. Los cuatro paquetes adicionales del contador Suricata no están identificados, no son eventos EVE y no existe una tolerancia definida.

El evento TLS corresponde a `10.20.0.20 → 10.30.0.10:443` y registra TLS 1.3, JA3, JA3S, JA4 y ALPN `h2`/`http/1.1`. HTTPS impide observar HTTP y fileinfo; esa opacidad no confirma semántica del contenido.

## Cobertura pesada R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 371,438 | 372,404 | 371,204 |
| 500–1500 bytes | 362,907 | 362,901 | 362,957 |
| Porcentaje objetivo | 97.7033 % | 97.4482 % | 97.7783 % |
| Exactamente 1500 bytes | 362,853 | 362,856 | 362,761 |
| Menores de 500 bytes | 8,531 | 9,503 | 8,247 |
| Longitud media IP | 1,466.70 | 1,463.02 | 1,467.51 |
| Duración `curl` | 24.532030 s | 24.529135 s | 24.525157 s |

Las repeticiones transfirieron el mismo volumen y contienen entre 362,901 y 362,957 paquetes del rango solicitado por el jurado. La duración máxima difiere 0.006873 s. Son observaciones de tres ejecuciones, no una garantía de determinismo ni evidencia causal sobre las diferencias.

## Tres ventanas correlacionadas

| Ventana UTC | Paquetes | Media IP | Heavy ratio | Attempts / SYN | TLS rate |
|---|---:|---:|---:|---:|---:|
| `14:55:10` | 144,012 | 1,450.90573008 | 0.96625976 | 1 / 1 | 0.01666667 |
| `14:55:20` | 147,340 | 1,478.53948690 | 0.98550971 | 1 / 0 | 0.01666667 |
| `14:55:30` | 79,852 | 1,477.09878275 | 0.98430847 | 1 / 0 | 0.01666667 |

Los conteos de las ventanas suman los 371,204 paquetes. Sus historias de 30/60 s se solapan: el intento de flujo permanece en las tres y la única sesión TLS produce `1/60`; son señales distintas. Solo la primera ventana contiene el SYN. Las filas pertenecen a un episodio, no son tres repeticiones independientes.

R01/R03 produjeron tres ventanas y R02 cuatro según su posición respecto de bordes UTC de diez segundos. El ensamblador verifica que R03 no agregó un vector exacto; no se deduce ese resultado únicamente de la fase.

El Sensor produjo 91 muestras: CPU máxima 8.25 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,053,168 KiB y carga máxima 0.51. Sin umbrales contractuales de presión para estas métricas, solo se reportan como observaciones.

## Integridad raíz

```text
manifest.json          b175f2e87bce5930b1fd90567f5a09777880f175a39ed2f546bccbca5cb60490
capture.pcap0          54fd57c442326b9593eadb1c2ec6d9d08da8fec418762d4ec674820c15e781e5
capture.pcap1          874ff60890ad798aca644e482051373e46a6b069780d934c178c42350aaa793d
eve-slice              465204f443b27115a4478ea838d9556e7db0614ca1d4961c4a9ad47108485611
campaign SHA256SUMS    7920bf7b49707c972e38772923d7dbe0e6bc47de8702c7b04a9a0fac5542a07a
multilayer-v1.csv      7146fdb3501fdf850322da57eb6d4872fcdd276c0d303cba17f6c4fea806925a
extraction-report      ae172214915204915706db4db289ec954c6a68f899f0457c0719b39d0428e1b1
feature SHA256SUMS     7726f131f45e4629c884ac5694f8b08118b8927528d6844dfab9e086957f7e50
ledger                 e4208e6456c5984a2bab13021aaf4cd822d4c41ccc32ab6f31d574706e25d4cd
```

El ensamblador aceptó 71/145 campañas: R03 13/29, 74 faltantes, cero inválidas/advertencias, once coincidencias exactas dentro de `train` —sin aumento— y cero cruces observados. R04/validation y R05/test todavía no existen.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTPS-1GB/R03`. Se corrigieron su límite iperf3 improcedente, “recursos sin presión”, conteo NTP y negación errónea del umbral NTP versionado.

**F1N-HTTPS-500MB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTPS-1GB-R03`.
