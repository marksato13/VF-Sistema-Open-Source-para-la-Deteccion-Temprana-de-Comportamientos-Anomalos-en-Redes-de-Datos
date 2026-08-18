# Undécimo canario oficial R02 — HTTPS-10MB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTPS-10MB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 10 MiB limitada a `2M` bytes/s. El escenario usa TLS 1.3, certificado autofirmado y `curl --insecure`; representa el laboratorio, no una PKI productiva.

El preflight confirmó Git limpio y sincronizado en `4848a8ea83de62cdf36a7013fab7d389c200eb4a`, ID libre, 139,211,071,488 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.77 ms. El archivo medía 10,485,760 bytes, SHA-256 `e5b844cc57f57094ea4585e235f36c78c1cd222262bb89d53c94dcb4d6b3e55d`; HEAD devolvió HTTPS 200, `Content-Length` correcto y `ssl_verify_result=18`, esperado para el certificado autofirmado.

NGINX, dnsmasq, firewall, iperf3, Suricata, chrony y SSH estaban activos; la captura residual estaba inactiva. El generador remoto coincidió por SHA-256, las NIC externas permanecieron `DOWN`, las rutas atravesaron el Sensor y el bypass `172.17.25.111-.114` quedó bloqueado.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `10MB`, `2M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 10,485,760 bytes en 4.519138 s, a 2,320,300 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 11,192,226 |
| Capturados / parseados / drops | 8,175 / 8,175 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 11 / 11 |
| Stats / TLS / HTTP / fileinfo / flow | 10 / 1 / 0 / 0 / 0 |
| Delta Suricata / PCAP | 8,177 / 8,175 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos paquetes adicionales del contador Suricata no están identificados. El segmento EVE quedó `complete_same_inode`. Todos los hashes de ambos bundles pasaron.

El evento TLS corresponde a `10.20.0.20 → 10.30.0.10:443`, registra TLS 1.3, JA3, JA3S, JA4 y ALPN `h2`/`http/1.1`. HTTPS impide observar HTTP y fileinfo en EVE; la integridad del cuerpo se demuestra en el extremo Cliente y el PCAP. La ausencia de un evento `flow` en este segmento no se atribuye al cifrado.

## Cobertura pesada y comparación

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 7,608 | 8,175 |
| 500–1500 bytes | 7,259 (95.4127 %) | 7,261 (88.8196 %) |
| Exactamente 1500 bytes | 7,240 | 7,245 |
| Menores de 500 bytes | 349 | 914 |
| Longitud media IP | 1,432.98 | 1,339.08 |
| Duración curl | 4.528286 s | 4.519138 s |

Las repeticiones transfirieron el mismo volumen en aproximadamente 4.52 s y produjeron casi el mismo número de paquetes del rango objetivo. R02 contiene 565 paquetes pequeños adicionales; se conserva la diferencia sin atribuir una causa TCP no demostrada.

R01 comenzó a `02:56:58.681454` y terminó a `02:57:03.210480` UTC, por lo que cruzó un borde UTC de diez segundos y produjo dos filas de 4,086/3,522 paquetes. R02 transcurrió entre `21:56:04.413511` y `21:56:08.933397` UTC, dentro de una sola ventana.

## Feature multicapa

La única fila R02 es elegible:

| Paquetes | Media IP | Heavy ratio | Attempts / SYN | SYN completion | TLS rate |
|---:|---:|---:|---:|---:|---:|
| 8,175 | 1,339.07669725 | 0.88819572 | 1 / 1 | 1.0 | 0.01666667 |

`tls_session_rate_60s=1/60` representa una sesión TLS observada. `http_request_count_60s=0` y `http_error_ratio_60s=0` significan que HTTP no es visible dentro del cifrado, no que se haya demostrado ausencia de solicitudes o errores. La fila combina volumen L3, establecimiento y finalización L4 y sesión TLS L7. No coincide exactamente con las filas R01.

El Sensor produjo 57 muestras: CPU máxima 1.90 %, RSS 780,308 KiB, memoria disponible mínima 14,050,284 KiB y carga máxima 0.26.

## Integridad raíz

```text
manifest.json          c8d69bf50e3c5293dd6aa157f7a7c19e658ba1a2a0555cfca74ceb01d021d8e7
capture.pcap0          7e20f1edd644df8c328c23430d6cac0d6570f918eabcf08c79308d64d6498084
eve-slice              6bb9c406df32c9014f24a04bb989b8bfff24d51a19ea347fc36192a6de45d3b9
campaign SHA256SUMS    52edba36a22fc387562bd1bd0041f3e3e9b651bf54c8f6404d399a3ddfbc6770
multilayer-v1.csv      a7a639514ff8eed15004690375b7287e3611fa9bb31a86c1c3f873912c543427
extraction-report      674e2894597714c0a9273378154d91703904536766e4de9329b331a93527c8f4
feature SHA256SUMS     d5719ca8bf8d8ca5e9b71a7adbe8109a7892da8587874ee173d4deab4991cb63
ledger                 a8927dfc7ced30ae6486d0ae950de3d4f073bb7584d7dec6d8f926df28c3c219
```

El ensamblador aceptó 40/145 campañas, R02 11/29, 105 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó con limitaciones y autorizó el siguiente preflight. Se corrigieron su `fileinfo` truncado inexistente en HTTPS, su afirmación contradictoria de que R01 no cruzó ventana, el rango 88–96 % inventado, la condición TCP de 200 Mbit/s no aplicable y la atribución de ausencia de `flow` al cifrado.

**F1N-HTTPS-10MB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTPS-100MB-R02`.
