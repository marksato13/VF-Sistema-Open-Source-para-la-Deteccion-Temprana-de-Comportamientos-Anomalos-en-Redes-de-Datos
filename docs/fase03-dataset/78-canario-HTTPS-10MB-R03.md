# Undécimo canario oficial R03 — HTTPS-10MB

Fecha: 30 de julio de 2026. Campaña: `F1N-HTTPS-10MB-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 10 MiB limitada a `2M` bytes/s. El escenario pertenece al estrato `small-transfer` y aporta volumen L3, establecimiento L4 y una sesión TLS L7. Usa TLS 1.3, certificado autofirmado y `curl --insecure`; representa el laboratorio aislado, no una PKI productiva.

El preflight confirmó Git limpio y sincronizado en `46feb130ee3b2a38f7e8f6473f8de1ac49228fc4`, ID/feature/ledger/lock libres, 132,689,604,608 bytes disponibles y almacenamiento oficial `PASS`. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.531 ms.

`/srv/ppi/files/10MB.bin` medía 10,485,760 bytes y tenía SHA-256 `e5b844cc57f57094ea4585e235f36c78c1cd222262bb89d53c94dcb4d6b3e55d`. NGINX devolvió HTTPS 200, `Content-Length: 10485760` y `ssl_verify_result=18`, esperado para el certificado autofirmado. Suricata, NGINX, dnsmasq, `ppi-server-firewall`, `ppi-iperf3`, chrony y SSH pasaron sus comprobaciones aplicables. Las rutas Cliente↔Servidor atravesaban el Sensor, las NIC externas estaban `DOWN`, el generador local/remoto coincidía y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `small-transfer` / `https` |
| Argumentos | `10MB`, `2M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 10,485,760 bytes en 4.520960 s, a 2,319,365 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 11,178,030 |
| Capturados / recibidos / parseados | 8,200 / 8,200 / 8,200 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 12 / 12 |
| TLS / flow / `stats` / HTTP / fileinfo | 1 / 1 / 10 / 0 / 0 |
| Delta Suricata / PCAP | 8,203 / 8,200 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

El único PCAP pasó validación, transferencia y hashes. Los tres paquetes adicionales del contador Suricata no están identificados y no existe una tolerancia contratada. El segmento EVE quedó `complete_same_inode`.

## Cobertura pesada R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes IPv4 | 7,608 | 8,175 | 8,200 |
| 500–1500 bytes | 7,259 | 7,261 | 7,256 |
| Porcentaje objetivo | 95.4127 % | 88.8196 % | 88.4878 % |
| Exactamente 1500 bytes | 7,240 | 7,245 | 7,249 |
| Menores de 500 bytes | 349 | 914 | 944 |
| Longitud media IP | 1,432.98 | 1,339.08 | 1,333.17 |
| Duración `curl` | 4.528286 s | 4.519138 s | 4.520960 s |

Las tres repeticiones transfirieron el mismo volumen y conservaron aproximadamente 7.26 mil paquetes legítimos en el rango solicitado por el jurado. R03 difiere de R02 en cinco paquetes del rango objetivo y treinta pequeños adicionales. Se conserva la diferencia sin atribuirla a TCP, fase, jitter u offloading.

R01 cruzó un borde UTC de diez segundos y produjo dos filas; R02 y R03 quedaron dentro de una sola ventana. Esta diferencia de fase cambia la granularidad de filas, no el número de repeticiones.

## EVE, feature multicapa y recursos

El evento TLS corresponde a `10.20.0.20 → 10.30.0.10:443` y registra TLS 1.3, JA3, JA3S, JA4 y ALPN `h2`/`http/1.1`. HTTPS impide observar HTTP y fileinfo en EVE; la descarga completa se demuestra en el Cliente y el PCAP. Los ceros HTTP de la fila significan opacidad por cifrado, no ausencia demostrada de solicitudes o errores.

EVE también conservó un `flow` ICMPv6 link-local originado por el Sensor: nació durante el warm-up y fue emitido por timeout. Está fuera del filtro IPv4 del PCAP, no pertenece a la entidad `10.20.0.20` y el extractor no lo convierte en observación de aplicación. No se atribuye su presencia a HTTPS.

La única fila R03 es elegible:

| Paquetes | Media IP | Heavy ratio | Attempts / SYN | SYN completion | TLS rate |
|---:|---:|---:|---:|---:|---:|
| 8,200 | 1,333.17146341 | 0.88487805 | 1 / 1 | 1.0 | 0.01666667 |

La fila combina volumen L3, establecimiento/finalización L4 y una sesión TLS L7. No coincide exactamente con R01/R02 y no agregó un duplicado.

El Sensor produjo 57 muestras: CPU máxima 2.96 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,087,096 KiB y carga máxima 0.23. Son observaciones de esta ejecución, no umbrales.

## Integridad raíz

```text
manifest.json          fbfc3e4a8264ab2bf8f7eec725fb5336bf9234ea5f3c8b8a34f46af65765c261
capture.pcap0          f04884bdc6bbfb38858eac78023043801641057e32a8734207a0d73f88d24c0c
eve-slice              14ac719a0cfaa6f2f8dc406c2e115f262cf60bd46f250de1509601c6ec72d296
campaign SHA256SUMS    de1df2fb23476708b9be10b32e2f8d09812981280bde35510a02f0357efc604b
multilayer-v1.csv      e90078af48d72aaa20a109d3a380eca271169254810d264b4e605d3bc54a926e
extraction-report      5f6a7f6a9062822f78284c493382a69a3abb7bc2df347c64bf890f7c189e2909
feature SHA256SUMS     2879ea5d8d71c6f00c7b1cfee7eecf748310f7494aa20c608b2353269ad0a458
ledger                 13e7255616f60bf2f56453ae85de08d9c58684bb5fcc4b616612d19ec6a5f87a
```

El ensamblador aceptó 69/145 campañas: R03 11/29, 76 faltantes, cero inválidas/advertencias, once coincidencias exactas dentro de `train` —sin aumento— y cero cruces observados. R04/validation y R05/test todavía no existen, por lo que el cero actual no demuestra ausencia futura de contaminación.

Tras renovar la sesión, Claude Code 2.1.217/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTPS-100MB/R03`. Ratificó integridad, opacidad HTTPS, PKI de laboratorio, `flow` IPv6 fuera de alcance y ausencia todavía de validation/test. Se descartó su inferencia de que diferencias de alcance entre AF_PACKET y tcpdump explican el delta +3: los artefactos no demuestran esa causa. La revisión técnica de Codex también corrigió el cálculo de CPU y mantuvo separados paquetes PCAP, eventos EVE e inferencias.

**F1N-HTTPS-10MB-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTPS-100MB-R03`.
