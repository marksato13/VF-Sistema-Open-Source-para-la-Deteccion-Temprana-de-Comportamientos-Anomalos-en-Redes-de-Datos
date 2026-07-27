# Séptimo canario oficial R02 — HTTP-10MB

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTP-10MB-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Primer perfil web pesado de R02: descarga HTTP legítima de 10 MiB desde Servidor `10.30.0.10`, limitada por el generador a `2M` bytes/s.

El preflight confirmó Git limpio y sincronizado en `a7383377a98a0c7625e6b8a80b2f4e210d6626f9`, ID libre, almacenamiento oficial válido, conectividad SSH y NTP en `PASS`. NGINX y Suricata estaban activos; `/srv/ppi/files/10MB.bin` medía exactamente 10,485,760 bytes y tenía SHA-256 `e5b844cc57f57094ea4585e235f36c78c1cd222262bb89d53c94dcb4d6b3e55d`. La prueba HTTP devolvió 200.

El primer chequeo del archivo falló por consultar dos rutas antiguas. No fue una falla del servidor: se corrigió contra la ruta versionada antes de capturar. Generador, captura, NIC externas y bypass pasaron sus gates.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Argumentos | `10MB`, `2M` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `aeb9c2b281a4803e43ed76ad2ab7f270d6e6e7c1ba15664a5bd764aa2f90526a` |

## Transferencia e integridad

`curl` obtuvo HTTP 200, 10,485,760 bytes en 4.513970 s, a 2,322,957 B/s; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 11,288,090 |
| Capturados / parseados / drops | 9,762 / 9,762 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 12 / 12 |
| HTTP 200 / fileinfo / stats / alertas | 1 / 1 / 10 / 0 |
| Delta Suricata / PCAP | 9,764 / 9,762 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos paquetes adicionales del contador Suricata no están identificados. El Sensor produjo 57 muestras: CPU máxima 8.80 %, RSS 780,308 KiB, memoria disponible mínima 14,103,504 KiB y carga máxima 0.26.

## Observación del jurado y comparación R01↔R02

| Métrica | R01 | R02 |
|---|---:|---:|
| Paquetes IPv4 | 7,912 | 9,762 |
| 500–1500 bytes | 7,248 (91.6077 %) | 7,243 (74.1959 %) |
| Exactamente 1500 bytes | 7,244 | 7,242 |
| Menores de 500 bytes | 664 | 2,519 |
| Longitud media | 1,378.26 | 1,126.33 |
| Duración curl | 4.504656 s | 4.513970 s |

Ambas repeticiones transfirieron íntegramente el mismo volumen y aportan miles de paquetes legítimos en 500–1500 bytes. R02 contiene casi el mismo número de paquetes de 1500 bytes, pero más paquetes pequeños. La evidencia disponible no identifica su causa; no se atribuye automáticamente a ACK, offloading o cierre TCP.

Esto fortalece la respuesta al jurado: un paquete grande es normal en transferencias legítimas, mientras la mezcla con paquetes pequeños varía entre episodios sanos.

## Features y fase

R02 produjo dos filas elegibles:

| Ventana | Paquetes | `packet_rate` | `byte_rate` | Media | Heavy ratio |
|---|---:|---:|---:|---:|---:|
| Principal | 9,758 | 975.8/s | 1,099,499.8 B/s | 1,126.76757532 | 0.74226276 |
| Cola temporal | 4 | 0.4/s | 20.8 B/s | 52 | 0 |

La fila principal registra un SYN, conexión completada, un request HTTP, respuesta no errónea, un destino y un puerto. La segunda contiene cuatro paquetes observados después del borde; su función TCP concreta no se afirma sin decodificación adicional. Ambas pertenecen al mismo episodio.

R01 produjo una fila de 7,912 paquetes con heavy ratio 0.91607685. La variación R02 no es coincidencia exacta y aporta diversidad legítima de L3/L4/L7.

## Integridad raíz

```text
manifest.json          c935b17d09d18073173d8f585034d843a116eaa1d64b90e954f1ff8256f876c6
capture.pcap0          c02e2bb4361d9276a7c9fcf44bd3794d9446321501989a9471bab2ff312b29cb
eve-slice              35c671ec605b147bc3e2a5688263233f6a21f44658c8825ff0b39d2c6b9db10d
campaign SHA256SUMS    c98a899c29cd0347743e530dc4dd04cae9ac673d881c791036751b98d576d888
multilayer-v1.csv      2e1e8f45590c880f94b4b1d21b8535cfd106b276f8c21571bcc06428781f977d
extraction-report      f45e88c7cebb09d60c109a8901e5edad744f7c536d7c03c1dcef01f77ed6e3c1
feature SHA256SUMS     09e19b415bd25b12b527641658c083b0ad1c06d684d08610bcd09517eddf008a
ledger                 e9f46e9d295d3c27d07066957c8a11f5607a1d20d7beeb1e9fc00c03b102f3da
```

Todos los hashes pasaron. El ensamblador aceptó 36/145 campañas, R02 7/29, con 109 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó con limitaciones y reconoció cobertura pesada y variación legítima. Se descartaron sus causas TCP no demostradas y su total global erróneo.

**F1N-HTTP-10MB-R02 ACEPTADA CON LIMITACIONES.** Siguiente: preflight individual de `F1N-HTTP-100MB-R02`.
