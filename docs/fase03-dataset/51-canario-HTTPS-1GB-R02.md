# Decimocuarto canario oficial R02 — HTTPS-1GB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTPS-1GB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 1 GiB limitada a `20M` bytes/s. Usa TLS 1.3, certificado autofirmado y `curl --insecure`; representa el laboratorio, no una PKI productiva ni verificación de identidad remota.

El preflight confirmó Git limpio y sincronizado en `9ecb52705a861a34e3d85a174eef413121685eff`, ID libre, 138,531,827,712 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.643 ms. El archivo medía 1,073,741,824 bytes, SHA-256 `49bc20df15e412a64472421e13fe86ff1c5165e18b2afccf160d4dc19fe68a14`; HEAD devolvió HTTPS 200, `Content-Length` correcto y `ssl_verify_result=18`.

Servicios, captura, Suricata, generador, rutas internas, NIC externas y bloqueo del bypass pasaron sus gates.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `1GB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6666c4e3e11f640a662a83aca3bbdb6688e9dd372b6f6ef1983125b593ecaf77` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 1,073,741,824 bytes en 51.029984 s, a 21,041,390 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 3 / 1,138,324,513 |
| Capturados / parseados / drops | 758,673 / 758,673 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 25 / 25 |
| Stats / TLS / flow / HTTP / fileinfo | 22 / 1 / 2 / 0 / 0 |
| Delta Suricata / PCAP | 758,682 / 758,673 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los nueve paquetes adicionales del contador Suricata no están identificados. EVE quedó `complete_same_inode` y todos los hashes pasaron.

Un flow TCP cerrado corresponde a la transferencia observada: 15,392 paquetes al Servidor, 743,281 al Cliente, edad 51 s y `tx_cnt=1`. El otro es un control IPv6-ICMP `fe80:: → ff02::2`, nacido durante la campaña y emitido por timeout. Está fuera del filtro PCAP IPv4, de la entidad y de los tipos consumidos por el extractor; se conserva en EVE sin contaminar las filas.

El evento TLS registra TLS 1.3, JA3, JA3S, JA4 y ALPN para `10.20.0.20 → 10.30.0.10:443`. Solo `tls_session_rate_60s` pertenece a las 14 variables. HTTPS no produjo HTTP ni fileinfo en EVE; no existe un `fileinfo` truncado a 102,400 bytes en esta campaña.

## Cobertura pesada y estabilidad

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 757,999 | 758,673 |
| 500–1500 bytes | 743,169 (98.0435 %) | 743,214 (97.9624 %) |
| Exactamente 1500 bytes | 743,055 | 743,064 |
| Menores de 500 bytes | 14,830 (1.9565 %) | 15,459 (2.0376 %) |
| Longitud media IP | 1,471.61 | 1,470.42 |
| Duración curl | 51.021313 s | 51.029984 s |

R02 demoró 0.008671 s más, una diferencia de 0.0170 %. Transfirió el mismo volumen y sumó 45 paquetes del rango objetivo, nueve exactos de 1,500 bytes y 629 pequeños. La proporción pequeña aumentó 0.0812 puntos; no se atribuye causa.

## Ventanas y fase UTC

R01 transcurrió entre `03:36:49.114598` y `03:37:40.137374` UTC. Empezó 0.885402 s antes del borde y produjo siete filas: 24,259/160,564/147,028/146,815/146,822/132,507/4. La última contiene cuatro paquetes y `tls_session_rate_60s=0` porque la observación TLS ya había salido de la historia de 60 s.

R02 transcurrió entre `02:42:43.667108` y `02:43:34.697736` UTC. Empezó 6.332892 s antes del borde y produjo seis filas:

| Paquetes | Media IP | Heavy ratio | Attempts / SYN | TLS rate |
|---:|---:|---:|---:|---:|
| 104,773 | 1,447.03521900 | 0.96350205 | 1 / 1 | 0.01666667 |
| 147,346 | 1,478.87892444 | 0.98547636 | 1 / 0 | 0.01666667 |
| 147,103 | 1,481.22781996 | 0.98708388 | 1 / 0 | 0.01666667 |
| 160,719 | 1,453.92492487 | 0.96824271 | 0 / 0 | 0.01666667 |
| 145,071 | 1,482.57675207 | 0.98799898 | 0 / 0 | 0.01666667 |
| 53,661 | 1,479.69340862 | 0.98602337 | 0 / 0 | 0.01666667 |

La fase explica siete ventanas R01 frente a seis R02. Las filas son autocorrelacionadas dentro de cada episodio y ninguna R02 coincide exactamente con R01. Ambas repeticiones pertenecen a `train`; no corresponde describir esta comparación como un cruce de particiones.

El Sensor produjo 133 muestras: CPU máxima 7.39 %, RSS 780,308 KiB, memoria disponible mínima 14,007,228 KiB y carga máxima 0.66.

## Integridad raíz

```text
manifest.json          542faba774131a6783454f0a4a8529e9e50f838c484b699a0f8b4961964ddaf8
capture.pcap0          9ac058adb4ca37d27ccd73218c2cc5cc763b40acd38d42d0f09602133344c13a
capture.pcap1          1760840c75afa459e5898a72418939775576c9790f2c48e0434649223922d946
capture.pcap2          c3fca6f7435a3e18e3908e135e94842c5f370951e683115e7b267963cd327eac
eve-slice              1142b83c2912d8940633cdd098a9f9ae37844252992fb2742ea657476e4dc0a3
campaign SHA256SUMS    c9f2acaa1c2e7e065646d3a77f9db7771b0d60ddb6103b08073517ef39952106
multilayer-v1.csv      18048490db1f1fd94183aaa90b59c8feb0e4c5c1c8644e431de9a4ec7848d1e1
extraction-report      010fcc85b5ea22c811d2381dd9e5b1574356c178dac75be0ef725d5b2e734751
feature SHA256SUMS     074653533e821bf32a5d9fc855f360905232a61dbd8ad4fa3aff4d972eef265f
ledger                 7573c026b1894e774c6d28e9d5cb12546a2ef4eb28a72cfaab77b5952f626648
```

El ensamblador aceptó 43/145 campañas, R02 14/29, 102 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

## Qué falta

R02 conserva 15 perfiles, en orden de matriz:

1. `HTTP-404-5`
2. `TLS-SESSIONS-20`
3. `HTTP-MULTI-1`
4. `HTTP-MULTI-5`
5. `HTTP-C2`
6. `HTTP-C4`
7. `HTTP-C8`
8. `TCP-REFUSED-5`
9. `TCP-50M`
10. `TCP-100M`
11. `TCP-200M`
12. `UDP-10M`
13. `UDP-25M`
14. `UDP-50M`
15. `MIXED-LIGHT`

Después faltarán las 29 campañas de cada repetición R03, R04 y R05. Por tanto, las 102 celdas globales pendientes son `15 + 29 + 29 + 29`.

Claude aceptó con limitaciones y autorizó `HTTP-404-5/R02`. Se corrigieron su `fileinfo` truncado inexistente, el supuesto cruce de particiones, el margen de captura no contratado y la denominación del control IPv6.

**F1N-HTTPS-1GB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-404-5-R02`.
