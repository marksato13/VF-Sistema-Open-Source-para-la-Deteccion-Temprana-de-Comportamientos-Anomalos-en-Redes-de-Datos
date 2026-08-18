# Decimoquinto canario oficial R03 — HTTP-404-5

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTP-404-5-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco solicitudes HTTP legítimas a recursos inexistentes. El perfil aporta una línea base controlada para `http_error_ratio_60s=1`: cinco respuestas 404 de baja tasa no constituyen por sí solas un ataque. Es un escenario L7 pequeño, no cobertura de tráfico pesado.

El preflight confirmó Git limpio y sincronizado en `2858c90187f765c48d8075020ebe96d422ca8be4`, ID/feature/ledger/lock libres, 130,871,984,128 bytes disponibles y almacenamiento oficial `PASS`. NTP pasó en VM01 más las cuatro VM, con desfase absoluto máximo de 1.091410 ms.

Servidor y Cliente consultaron dos rutas exclusivas de preflight, distintas de las oficiales, y recibieron 404. Servicios, rutas por el Sensor, NIC externas `DOWN`, generador, captura inactiva, contadores Suricata y bypass pasaron. Los 70 s de quietud ocurrieron antes de abrir la captura; el warm-up de 60 s capturado y settle de 9 s son etapas separadas.

Claude/Sonnet autorizó una única ejecución. Se corrigieron su denominación “cinco VM”, la fusión de quietud/warm-up/settle y su alcance de “cadena de custodia”.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `legitimate-error` / `http-missing` |
| Argumento | `5` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

## Conteos exactos e integridad

El Cliente registró exactamente cinco resultados `http_code=404`, uno por request, con stderr vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 6,309 |
| Capturados / recibidos / parseados | 50 / 50 / 50 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 20 / 20 |
| HTTP / fileinfo / `stats` | 5 / 5 / 10 |
| Delta Suricata / PCAP | 52 / 50 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos adicionales son paquetes del contador Suricata, no eventos EVE, y no están identificados. El PCAP, transferencia y ambos bundles de hashes pasaron; EVE quedó `complete_same_inode`.

EVE contiene únicamente `/recurso-inexistente-1` hasta `-5`, cada uno con GET, HTTP/1.1, estado 404 y longitud 162. Los cinco `fileinfo` están `CLOSED`, `gaps=false`, `stored=false` y `size=162`. La búsqueda sobre el segmento EVE completo confirmó que ninguna de las dos rutas exclusivas de preflight aparece.

Los 50 paquetes son menores de 500 bytes, con media IP 95.70 y máximo 378. El 0 % en 500–1500 bytes es correcto para este estrato y no sustituye las campañas pesadas anteriores.

## Feature y repetibilidad R01↔R02↔R03

La única fila R03 es elegible:

| Paquetes | Attempts / SYN | HTTP requests | SYN completion | IP/port ratio | HTTP error ratio |
|---:|---:|---:|---:|---:|---:|
| 50 | 5 / 5 | 5 | 1.0 | 0.2 / 0.2 | 1.0 |

Las tres repeticiones tienen exactamente 50 paquetes, 6,309 bytes, cinco HTTP 404, cinco `fileinfo`, delta Suricata 52 y cero drops. Sus artefactos y hashes son distintos.

R01 cruzó un borde UTC después del primer flujo y produjo dos filas 10/40. R02 y R03 situaron los cinco flujos dentro de una sola ventana y produjeron una fila de 50. Es segmentación por fase frente al borde fijo, no menor duración de R02/R03 ni una causa de red.

La fila R03 coincide exactamente con R02 en las 14 features. El ensamblador registra la coincidencia como duplicado dentro de `train`; aporta una ejecución independiente, pero no diversidad observacional y aumenta el peso de ese vector.

El Sensor produjo 53 muestras: CPU máxima 1.52 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,095,004 KiB y carga máxima 0.16. Son observaciones sin umbrales de presión definidos.

## Integridad raíz

```text
manifest.json          7d7b750f9d76082428b2bb97384ed7a6b5f5808a64fa9d732baa6dc938df9f45
capture.pcap0          4e806f322bfd9a71a2809e3aa36b342a9a709d66eaaad7e182de0bbfbd0759c2
eve-slice              33e491c0a04a2e2196777946f0efe64ae637d1d697df2ef4811543a99c425989
campaign SHA256SUMS    f6cf8e1cb48ff25687c803b3d0e7a88a373b94a437659f2adc28841092945f46
multilayer-v1.csv      9a3eeb53a75002db3f43c5d657deb0629b3851f0cf48eedb37175cd966b5b18b
extraction-report      9fc6dc4c844f8d5369acc079525cb05e929d5e6cb18a3fe795a9700fe615607b
feature SHA256SUMS     8ff4ade984fbbaa95dbdbe1d2d4ce3aee84c93125ab0965d292cf9c36f3dae48
ledger                 35f38012c0d329d4fc5582041e62f267bf5104471cf15fcb57846eadd7732a09
```

El ensamblador aceptó 73/145 campañas: R03 15/29, 72 faltantes, cero inválidas/advertencias y cero cruces observados. Las coincidencias exactas dentro de `train` subieron de once a doce por `HTTP-404-5/R02 ↔ R03`. Validation/test aún no existen.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight de `TLS-SESSIONS-20/R03`. Se corrigieron la fase temporal, el alcance de ausencia de preflight, NTP y secuencia operativa.

**F1N-HTTP-404-5-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-TLS-SESSIONS-20-R03`.
