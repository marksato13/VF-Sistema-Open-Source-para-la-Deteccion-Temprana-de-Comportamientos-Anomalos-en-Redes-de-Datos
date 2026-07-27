# Duodécimo canario oficial R02 — HTTPS-100MB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTPS-100MB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 100 MiB limitada a `10M` bytes/s. Usa TLS 1.3, certificado autofirmado y `curl --insecure`; representa el laboratorio, no una PKI productiva.

El preflight confirmó Git limpio y sincronizado en `998b34a06ea37fd9d6a90bb6ac8d0b11b6ab0a4a`, ID libre, 139,199,684,608 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.269 ms. El archivo medía 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD devolvió HTTPS 200, `Content-Length` correcto y `ssl_verify_result=18`.

Servicios, captura, Suricata, generador, rutas internas, NIC externas y bloqueo del bypass pasaron sus gates.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `100MB`, `10M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 104,857,600 bytes en 9.529980 s, a 11,002,919 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 111,389,697 |
| Capturados / parseados / drops | 76,721 / 76,721 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 12 / 12 |
| Stats / TLS / flow / HTTP / fileinfo | 11 / 1 / 0 / 0 / 0 |
| Delta Suricata / PCAP | 76,725 / 76,721 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los cuatro paquetes adicionales del contador Suricata no están identificados. El segmento EVE quedó `complete_same_inode` y todos los hashes pasaron.

El único evento TLS corresponde a `10.20.0.20 → 10.30.0.10:443`, con TLS 1.3, JA3, JA3S, JA4 y ALPN. Solo `tls_session_rate_60s` forma parte del esquema de 14 variables. HTTPS oculta HTTP y fileinfo; la ausencia de `flow` no se atribuye al cifrado.

## Cobertura pesada y estabilidad

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 74,858 | 76,721 |
| 500–1500 bytes | 72,575 (96.9502 %) | 72,590 (94.6156 %) |
| Exactamente 1500 bytes | 72,535 | 72,566 |
| Menores de 500 bytes | 2,283 | 4,131 |
| Longitud media IP | 1,455.61 | 1,421.88 |
| Duración curl | 9.526443 s | 9.529980 s |

R02 demoró 0.003537 s más, una diferencia de 0.0371 %. Las dos repeticiones transfirieron el mismo volumen y contienen prácticamente el mismo número de paquetes del rango objetivo. R02 suma 1,848 paquetes pequeños: su proporción sube de 3.0498 % a 5.3844 %, 2.3347 puntos porcentuales. La causa no está demostrada y no se atribuye a TCP, fragmentación, ACK ni cifrado.

## Dos ventanas y fase UTC

| Repetición | Inicio–fin UTC | Paquetes por ventana |
|---|---|---:|
| R01 | `03:15:57.897741`–`03:16:07.426580` | 21,783 / 53,075 |
| R02 | `22:22:46.399191`–`22:22:55.926737` | 42,762 / 33,959 |

Ambas transferencias cruzan un borde UTC fijo de diez segundos. R01 comenzó 2.102259 s antes del suyo y R02, 3.600809 s antes; esto explica el distinto reparto inicial/final. No se comparan sus fechas como si fueran una diferencia de minutos ni se exige una fase particular.

Las dos filas R02 son elegibles:

| Paquetes | Media IP | Heavy ratio | Attempts / SYN | SYN completion | TLS rate |
|---:|---:|---:|---:|---:|---:|
| 42,762 | 1,374.52670595 | 0.91340442 | 1 / 1 | 1.0 | 0.01666667 |
| 33,959 | 1,481.50805383 | 0.98739657 | 1 / 0 | 0.0 | 0.01666667 |

El intento y la sesión TLS permanecen en sus historias causales; el SYN solo pertenece a la primera ventana. Los ceros HTTP representan opacidad por cifrado, no ausencia demostrada. Las filas están autocorrelacionadas dentro de un episodio y ninguna coincide exactamente con R01.

El Sensor produjo 64 muestras: CPU máxima 8.20 %, RSS 780,308 KiB, memoria disponible mínima 14,003,480 KiB y carga máxima 0.31.

## Integridad raíz

```text
manifest.json          ce182debe888cc56a43d43bec5b954934b10c76376511a1732055565e8677a5b
capture.pcap0          707f4500c45deef4f627bfbe1308e2a367aafeef64ec9575ab5c052a9eb62932
eve-slice              a7cc798ca8735d09464ccda4a0965f920dec3c3e2e5db777961abf1884e2daeb
campaign SHA256SUMS    c2daabdf7773de9b639235ec2df331c1af49ca658c28cbd545fa0c1965394ff6
multilayer-v1.csv      bf6a1ef6d464d5f7086ecc888862058e23b2654a83f384da2eb5a380a95a2873
extraction-report      4b13f4acee4db012bc7d7c97863eec85e59378fccf48dc963afb7cf536f164fc
feature SHA256SUMS     8b48388dfbbaa26c57ffe8a5918a2d9193846ac90a6177427dba427040cd526d
ledger                 db47bf4d5259e1bc0137c87e9c0ab0d15d53c54689da92233772e5af17063936
```

El ensamblador aceptó 41/145 campañas, R02 12/29, 104 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó con limitaciones y autorizó continuar, pero se corrigieron el signo de la duración, el porcentaje de paquetes pequeños, la ventana de 10 s, la comparación temporal entre fechas, la causa inventada de los cuatro paquetes Suricata, el perfil HTTP escrito por error y el gate de 1 % inexistente.

**F1N-HTTPS-100MB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTPS-500MB-R02`.
