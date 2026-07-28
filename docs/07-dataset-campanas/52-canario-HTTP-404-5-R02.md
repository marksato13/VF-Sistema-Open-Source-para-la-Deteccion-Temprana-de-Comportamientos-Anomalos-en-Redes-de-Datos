# Decimoquinto canario oficial R02 — HTTP-404-5

Fecha: 27 de julio de 2026. Campaña: `F1N-HTTP-404-5-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco solicitudes HTTP legítimas a recursos inexistentes. El perfil enseña una línea base controlada para `http_error_ratio_60s`: una respuesta 404 no es un ataque por sí sola.

El preflight confirmó Git limpio y sincronizado en `6bba36220cf5dbc50223b90ef7c1668d68b2b778`, ID libre, 137,393,180,672 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.812 ms. Una ruta exclusiva de preflight devolvió 404; los servicios, captura, generador, rutas, aislamiento y Suricata pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumento | `http-missing` / `5` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

## Conteos exactos e integridad

El Cliente registró exactamente cinco resultados `http_code=404`, uno por request, con stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 6,309 |
| Capturados / parseados / drops | 50 / 50 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 20 / 20 |
| Stats / HTTP / fileinfo | 10 / 5 / 5 |
| Delta Suricata / PCAP | 52 / 50 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos adicionales son paquetes del contador Suricata, no eventos EVE, y no están identificados.

EVE contiene únicamente `/recurso-inexistente-1` hasta `-5`, cada uno con GET, HTTP/1.1, estado 404 y longitud 162. Los cinco `fileinfo` están `CLOSED`, `gaps=false`, `stored=false` y `size=162`. La ruta exclusiva de preflight no aparece en EVE. Todos los hashes pasaron.

Los 50 paquetes son menores de 500 bytes: media IP 95.70 y máximo 378. Este perfil aporta señal L7 de error legítimo; no está diseñado para cobertura pesada.

## Feature y comparación R01

R02 produjo una fila elegible:

| Paquetes | Attempts / SYN | HTTP requests | SYN completion | IP/port ratio | HTTP error ratio |
|---:|---:|---:|---:|---:|---:|
| 50 | 5 / 5 | 5 | 1.0 | 0.2 / 0.2 | 1.0 |

R01 y R02 tienen los mismos totales: 50 paquetes, 6,309 bytes, cinco HTTP 404, cinco `fileinfo`, delta Suricata 52 y cero drops. La diferencia es temporal:

- R01: `03:53:49.897499`–`03:53:50.784400` UTC; cruzó el borde tras el primer flujo y produjo dos filas de 10/40 paquetes.
- R02: `04:53:46.575281`–`04:53:47.452313` UTC; quedó dentro de una ventana y produjo una fila de 50.

La fase explica el reparto. Ninguno de los tres vectores coincide exactamente. Una sola fila pertenece a un episodio determinista, pero no se denomina autocorrelación entre filas porque no existe una segunda fila R02.

El Sensor produjo 54 muestras: CPU máxima 2.27 %, RSS 780,308 KiB, memoria disponible mínima 14,089,688 KiB y carga máxima 0.16.

## Tamaño de la evidencia

Después de esta campaña:

| Elemento | Uso / estimación |
|---|---:|
| PCAP F1 actuales | 10,143,006,390 bytes en 58 archivos |
| Bundles F1 actuales | 10,149,619,590 bytes |
| Features F1 actuales | 97,702 bytes |
| PCAP totales, incluidas calibraciones | 11,032,245,016 bytes |
| PCAP estimado para F1 completa | 33,673,250,000 bytes |
| PCAP estimado aún pendiente | 23,233,650,000 bytes |
| Espacio libre actual | 137,392,971,776 bytes |

La proyección usa `estimated_pcap_bytes` de la matriz, no reemplaza la medición final. El volumen crudo será de decenas de GB, mientras las features agregadas permanecen en el orden de KB/MB. Hay capacidad suficiente; no se alterarán los bundles durante la recolección porque sus hashes forman parte de la trazabilidad.

## Integridad raíz

```text
manifest.json          875a29f35e29e4d22663a62d2b1506458c191f8bd868f24e3a5aaf20fd5a268b
capture.pcap0          8d219620f27cab1268a17dbabe493d6a8f36e257bf6d3ca4f7397f5cf80b5282
eve-slice              643b4ebfd2a0ba94bb69caa65721732fca0b0d00b4f0eda9213bef5c4e0069f2
campaign SHA256SUMS    e184aa1b8cabdeda67598c6d23ff2903ac2ace2f53ac6437a5edce8d79b7eca2
multilayer-v1.csv      9e5926f8f940fa41ad6f9e862b6feb81e31c3269345ecf4da153218d629daa0c
extraction-report      9ef490d966c2c64988736dfcbc5a32b44c946a642f4b1d4d411db72cd27f3e76
feature SHA256SUMS     b765b39c933b5a82c65a26574b93139ddb0168f6f3177932b3e82b185f0a7bf2
ledger                 e7258f4e7b56b657341ec8b7f124104363d8fd090521f52e0cccfc8560949e98
```

El ensamblador aceptó 44/145 campañas, R02 15/29, 101 faltantes, cero inválidas/advertencias, cuatro coincidencias dentro de `train` y cero entre particiones.

Claude aceptó y autorizó `TLS-SESSIONS-20/R02`. Se corrigieron sus paquetes/eventos, flags inventadas, certificado TLS ajeno al perfil, autocorrelación de una fila, contradicción sobre vectores y afirmaciones generales sobre tráfico real.

**F1N-HTTP-404-5-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-TLS-SESSIONS-20-R02`.
