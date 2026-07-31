# Decimosexto canario oficial R03 — TLS-SESSIONS-20

Fecha: 31 de julio de 2026. Campaña: `F1N-TLS-SESSIONS-20-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Veinte sesiones HTTPS legítimas, secuenciales y de corta duración contra `/health`. El perfil aporta normalidad de recambio de conexiones y sesiones TLS; no representa concurrencia, variedad de clientes, destinos, implementaciones TLS ni PKI productiva.

El preflight confirmó Git limpio y sincronizado en `df4a399e5c09ae67fc7619ec22b31b47d8a82191`, ID/feature/ledger/lock libres, 130,871,775,232 bytes disponibles y almacenamiento oficial `PASS`. NTP pasó en VM01 más las cuatro VM, con desfase absoluto máximo de 0.752041 ms.

Servidor y Cliente obtuvieron HTTP 200 de `/health` con `ssl_verify_result=18`, esperado para el certificado autofirmado. Las cuatro VM respondieron por SSH; servicios, rutas por el Sensor, NIC externas `DOWN`, generador, captura inactiva, contadores Suricata y bloqueo de bypass pasaron. Los 70 s de quietud ocurrieron antes de abrir la captura; el warm-up de 60 s capturado y settle de 9 s son etapas separadas.

Claude/Sonnet autorizó una única ejecución y exigió conservar el alcance: recambio homogéneo, no concurrencia, diversidad, tráfico pesado ni PKI productiva.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `session-churn` / `https-sessions` |
| Argumento | `20` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `9246e824773fc95ffe7097ebf344e3aef5d4cd76329e4d39a4fd0e79eb8d75c4` |

## Conteos exactos e integridad

El Cliente registró exactamente veinte resultados `session=1..20,http_code=200`, con stderr vacío. Esas son observaciones activas del generador; los veinte eventos TLS de EVE son observaciones pasivas distintas que coinciden en número por el diseño de esta ejecución.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 143,852 |
| Capturados / recibidos / parseados | 424 / 424 / 424 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 30 / 30 |
| `stats` / TLS | 10 / 20 |
| Delta Suricata / PCAP | 426 / 424 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos paquetes adicionales pertenecen al delta del contador Suricata, no son eventos EVE y su naturaleza no fue identificada. No se les atribuye benignidad, retransmisión ni otra causa. El PCAP, la transferencia y ambos bundles de hashes pasaron; el estado final del runner fue `completed`.

EVE contiene exactamente veinte TLS 1.3 entre `2026-07-31T11:07:47.679399-0500` y `2026-07-31T11:07:50.111912-0500`, con veinte puertos origen únicos. No contiene una sesión TLS adicional del preflight. Las veinte observaciones comparten:

- JA3 `7587a1ac9a4f17b4e4e5fe226716f4df`;
- JA3S `15af977ce25de452b96affa2addb1036`;
- JA4 `t13i3012h2_1d37bd780c83_8537cf56674e`.

La igualdad de huellas es coherente con el mismo Cliente, Servidor y stack TLS. Demuestra homogeneidad, no diversidad criptográfica o de aplicaciones.

## Tamaños y features

| Rango IPv4 | Paquetes |
|---|---:|
| Menores de 500 bytes | 364 |
| 500–1500 bytes | 60 (14.1509 %) |
| Exactamente 1500 bytes | 40 |
| Mayores de 1500 bytes | 0 |

La media IP fue 309.22 bytes y el máximo 1,500. Este perfil de sesiones breves complementa, pero no sustituye, las campañas legítimas pesadas.

R03 produjo dos filas elegibles al cruzar un borde fijo UTC:

| Fin UTC | Paquetes | Attempts / SYN | Attempt/SYN rate | Large ratio | IP/port ratio | TLS rate |
|---|---:|---:|---:|---:|---:|---:|
| `16:07:50` | 402 | 19 / 19 | 1.9 / 1.9 s⁻¹ | 0.14179104 | 0.05263158 / 0.05263158 | 0.31666667 |
| `16:08:00` | 22 | 20 / 1 | 0.1 / 0.1 s⁻¹ | 0.13636364 | 0.05 / 0.05 | 0.33333333 |

La segunda fila observa un SYN dentro de sus 10 s y conserva los veinte intentos en la historia de 30 s y las veinte sesiones TLS en la de 60 s. Las dos filas pertenecen al mismo episodio y no son muestras experimentales independientes.

## Repetibilidad R01↔R02↔R03

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| PCAP paquetes / bytes | 431 / 144,426 | 430 / 144,356 | 424 / 143,852 |
| Paquetes 500–1500 | 60 (13.9211 %) | 62 (14.4186 %) | 60 (14.1509 %) |
| Exactamente 1500 | 40 | 40 | 40 |
| Filas / fase por ventana | 2 / 15+5 | 1 / 20 | 2 / 19+1 |

Las tres repeticiones produjeron veinte HTTP 200 activos, veinte TLS EVE, veinte puertos origen y cero drops, con artefactos y hashes independientes. Las diferencias de filas provienen de la posición del mismo episodio frente al borde UTC: no prueban cambios en el escenario ni diversidad de comportamiento.

La comparación de las 14 variables confirma que ninguna fila R03 coincide exactamente con las filas R01 o R02. El auditor global mantuvo doce coincidencias exactas dentro de `train`, el mismo total previo a esta campaña; por tanto, R03 no añadió una coincidencia. Esta comprobación corrige la afirmación no sustentada de Claude sobre una supuesta reproducción exacta de la segunda fila.

El Sensor produjo 55 muestras: CPU máxima 2.26 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,072,224 KiB y carga máxima 0.17. Son observaciones de esta ejecución; no existen umbrales definidos para declarar presión o capacidad.

## Integridad raíz

```text
manifest.json          a1cef75659609f23afd61d1b912767726607ff9b6fe7d6005f7ea53f22d8100a
capture.pcap0          fff744ba9cdbb9e3a558a433ba85299048594fe812171bad1b59fea4b06669c6
eve-slice              ae421e9bf65c864fc6d43f4c25a7c0f8b16fae8629d6e61f66591c5806db5e1f
campaign SHA256SUMS    a53b7f0c146a12fe9c5aa8c15e137f77d46d206ce13e6ba6f80da2ae3889554a
multilayer-v1.csv      08238f0feccfb3d2a1be60b9d51ae17495a2d37c208357b9115a32ebf9a59f82
extraction-report      d7ba0e2ddf58ca367a2c70e8daa55382ecdef3b0e2429a69a73cc8a2d9cfa78e
feature SHA256SUMS     076fb4f807d6ca736c1611579029e2e0a78a131192d0b574d43e35000892a144
ledger                 ecb741db01ce7a3d4360063f2adb4b8db9dc6ce1161dbac59f778759e2c1354c
```

El ensamblador aceptó 74/145 campañas: R03 16/29, 71 faltantes, cero inválidas/advertencias, doce coincidencias exactas dentro de `train` y cero entre particiones. Validation/test aún no existen, por lo que el cero entre particiones no constituye una evaluación de generalización.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTP-MULTI-1/R03`. Se corrigió su atribución de duplicado, y se conservaron sus límites sobre fingerprints homogéneos, conteos por capa, delta no identificado y ausencia de validation/test.

**F1N-TLS-SESSIONS-20-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTP-MULTI-1-R03`; no su ejecución.
