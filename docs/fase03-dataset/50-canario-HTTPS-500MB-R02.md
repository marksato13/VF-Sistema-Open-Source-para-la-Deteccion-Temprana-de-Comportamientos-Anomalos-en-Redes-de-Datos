# Decimotercer canario oficial R02 — HTTPS-500MB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTPS-500MB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Transferencia HTTPS legítima de 500 MiB limitada a `20M` bytes/s. Usa TLS 1.3, certificado autofirmado y `curl --insecure`; representa el laboratorio, no una PKI productiva.

El preflight confirmó Git limpio y sincronizado en `962b5cdd5c6472418c0dc725e72fbcf632f63859`, ID libre, 139,088,089,088 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.643 ms. El archivo medía 524,288,000 bytes, SHA-256 `a08a92258f621b55d08ad1e84c90c2ea6286fc6b6c9a4dfa7156afb16c190170`; HEAD devolvió HTTPS 200, `Content-Length` correcto y `ssl_verify_result=18`.

Servicios, captura, Suricata, generador, rutas internas, NIC externas y bloqueo del bypass pasaron sus gates.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `500MB`, `20M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `fb20617a24731156f625c1a420f67e2189a940a57121a3b21a699a918b33cc3f` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 524,288,000 bytes en 24.529135 s, a 21,374,092 B/s; stderr quedó vacío. El valor observado se registra sin inventar un margen porcentual sobre la unidad `20M` de curl.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 2 / 556,005,875 |
| Capturados / parseados / drops | 372,404 / 372,404 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 17 / 17 |
| Stats / TLS / flow / HTTP / fileinfo | 16 / 1 / 0 / 0 / 0 |
| Delta Suricata / PCAP | 372,408 / 372,404 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los cuatro paquetes adicionales del contador Suricata no están identificados. Las features se extrajeron del PCAP validado; no se atribuye la diferencia a eventos `stats` ni a otra causa. EVE quedó `complete_same_inode` y todos los hashes pasaron.

El evento TLS corresponde a `10.20.0.20 → 10.30.0.10:443`, con TLS 1.3, JA3, JA3S, JA4 y ALPN. Solo `tls_session_rate_60s` pertenece a las 14 variables. HTTPS oculta HTTP y fileinfo; la ausencia de `flow` no se atribuye al cifrado.

## Cobertura pesada y estabilidad

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 371,438 | 372,404 |
| 500–1500 bytes | 362,907 (97.7033 %) | 362,901 (97.4482 %) |
| Exactamente 1500 bytes | 362,853 | 362,856 |
| Menores de 500 bytes | 8,531 (2.2967 %) | 9,503 (2.5518 %) |
| Longitud media IP | 1,466.70 | 1,463.02 |
| Duración curl | 24.532030 s | 24.529135 s |

R02 demoró 0.002895 s menos, una diferencia de 0.0118 %. Las repeticiones transfirieron el mismo volumen y difieren en solo seis paquetes del rango objetivo. R02 suma 972 paquetes pequeños y 0.2550 puntos porcentuales; la causa no está demostrada.

## Ventanas y fase UTC

R01 transcurrió entre `03:25:14.644515` y `03:25:39.175622` UTC. Comenzó 5.355485 s antes de un borde y produjo tres filas: 95,676/147,232/128,530.

R02 transcurrió entre `02:24:56.691976` y `02:25:21.229201` UTC. Comenzó 3.308024 s antes del borde y produjo cuatro filas:

| Paquetes | Media IP | Heavy ratio | Attempts / SYN | TLS rate |
|---:|---:|---:|---:|---:|
| 67,823 | 1,376.30875957 | 0.91463073 | 1 / 1 | 0.01666667 |
| 152,871 | 1,483.46255339 | 0.98859823 | 1 / 0 | 0.01666667 |
| 146,520 | 1,481.23155883 | 0.98704614 | 1 / 0 | 0.01666667 |
| 5,190 | 1,479.74296724 | 0.98612717 | 0 / 0 | 0.01666667 |

La fase explica tres ventanas R01 frente a cuatro R02. Attempts/destino vencen su historia de 30 s en la cuarta; la sesión TLS permanece en la historia de 60 s. `0.01666667` es una tasa de una sesión por 60 segundos, no 1.67 %. Las filas son ventanas autocorrelacionadas de un episodio, no transacciones duplicadas; ninguna coincide exactamente con R01.

El Sensor produjo 92 muestras: CPU máxima 8.17 %, RSS 780,308 KiB, memoria disponible mínima 13,849,252 KiB y carga máxima 0.52.

## Integridad raíz

```text
manifest.json          a2611354c05b3580e6e865e1abadb029613d1cc9d101ab58d60fe5d4e062d696
capture.pcap0          1e17adfcdd36012104d7f3d1e61f9d1531f32c5904dc2ac7382b649020559a4a
capture.pcap1          22c9e726ae0a1e0997099f17bd78551362f41b4f1694564cb916c40373707469
eve-slice              a76973178631d247c7c7c117558b319906c12d82e7f2844004c01ce1c8f1152c
campaign SHA256SUMS    79673107d4e10ba5bca33e932be2a1c4d8e0ad20b32b71baede329c6c7c83319
multilayer-v1.csv      1422a418215fe717c53386ce7964fe05edee36f06be3a3f55999918096c55317
extraction-report      9b43d840e7d256d17ec75ed463107993b21923a2db57ffa74993e5b83e7b9a70
feature SHA256SUMS     2e4a26cda615cb134c2398ef45eeb4cee3e2eac206ea641233fdc28e4cd860db
ledger                 095d4fbaf8364e4caf9c683465f158b3af123fd5012473969d5b00957bec55cd
```

El ensamblador aceptó 42/145 campañas, R02 13/29, 103 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó con limitaciones y autorizó el siguiente preflight. Se corrigieron la unidad de velocidad, el porcentaje atribuido a la tasa TLS, causas no demostradas, una condición de sensibilidad prematura, la interpretación de ventanas como transacciones y los gates inventados de 0.3 puntos/distribución previa.

**F1N-HTTPS-500MB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTPS-1GB-R02`.
