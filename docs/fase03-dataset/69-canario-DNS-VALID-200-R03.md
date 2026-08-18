# Segundo canario oficial R03 — DNS-VALID-200

Fecha: 29 de julio de 2026. Campaña: `F1N-DNS-VALID-200-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La campaña repite doscientas consultas DNS legítimas secuenciales desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:53`, solicitando `server.ppi.lab/A` y esperando `10.30.0.10`.

El preflight confirmó Git limpio y sincronizado en `deddc4610f204d1b231aadae694fa43efc3008c7`, ID/lock libres, volumen oficial `PASS` con 134,505,574,400 bytes disponibles y NTP `PASS` con desfase absoluto máximo de 0.202 ms. Las cuatro VM, dnsmasq, Suricata y rutas estaban sanos; las NIC externas estaban `DOWN`, el bypass `.111–.114` bloqueado y el generador local/remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `burst` / `dns-valid` |
| Argumentos | `200` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `4d83a1f3e47b09a57f011d4bd69c80eaaed35d7122fbd598fca53a56f2f82d95` |

## Resultado e integridad

El escenario terminó con código cero, stderr vacío y 200 líneas `10.30.0.10`.

| Control | Resultado |
|---|---:|
| Consultas / respuestas | 200 / 200 |
| RCODE `NOERROR` / NXDOMAIN | 400 / 0 |
| Respuestas A correctas | 200 |
| IDs / puertos origen distintos | 200 / 200 |
| Span requests / tasa descriptiva | 4.046017 s / 49.431330 consultas/s |
| PCAP capturado / recibido / parseado | 400 / 400 / 400 |
| PCAP archivos / bytes | 1 / 46,024 |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 404 / 400 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 409 / 409 |

Los 400 paquetes son UDP/IPv4 menores de 500 bytes, con media 85 y máximo 87. EVE contiene 400 DNS y nueve `stats`. Los cuatro paquetes adicionales de Suricata no están identificados y no se les atribuye causa.

El Sensor produjo 56 muestras: CPU máxima 3.02 %, RSS 781,816 KiB, memoria disponible mínima 13,908,268 KiB y carga máxima 0.47. Son observaciones, no umbrales.

## Ventanas y comparación R01↔R02↔R03

El extractor procesó 400 paquetes, obtuvo 200 observaciones de aplicación y produjo dos filas elegibles:

| Fin UTC | Paquetes nuevos | Consultas historia | Attempts historia | Packet rate | Attempt rate |
|---|---:|---:|---:|---:|---:|
| `06:22:20` | 64 | 32 | 32 | 6.4/s | 3.2/s |
| `06:22:30` | 336 | 200 | 200 | 33.6/s | 16.8/s |

| Repetición | Span | Puertos distintos | Reparto paquetes | EVE | Delta Suricata |
|---|---:|---:|---:|---:|---:|
| R01 | 4.076892 s | 199 | 228 / 172 | 411 | 404 |
| R02 | 4.110662 s | 200 | 24 / 376 | 410 | 404 |
| R03 | 4.046017 s | 200 | 64 / 336 | 409 | 404 |

R01 reutilizó una 5-tupla; R02/R03 no. Los tres episodios conservan los mismos totales DNS, PCAP y longitudes, pero su fase frente al borde UTC redistribuye las filas. R03 no añade un vector exacto. Las dos filas de cada campaña comparten episodio e historia causal, por lo que están correlacionadas y no son repeticiones independientes.

## Integridad raíz

```text
manifest.json          da8e2156575b39e832af2d067723994601bc209772036b3233121a5b15f71b18
capture.pcap0          d8bbcdc43a5d46a6a3064f341992380cbfeeed8b3c642be087cc619a00a1848c
eve-slice              57592add30bf095707a7828514c6493b14e4c838633dfeca9b82ba4584c2795c
campaign SHA256SUMS    d4b91287ca59ace52e24b06e4dac1ec75c378b83211650825eee5131f3202ca0
multilayer-v1.csv      fe3c5184e70784aa8967ef2331a7d4176612adcb96d7c5d2890af253eea27925
extraction-report      11f08b14a7198d5ac3b932b2218559da19fe00b248ac9f6f5da1d4dfd34d196c
feature SHA256SUMS     4bafc1a6f24b36c018e2e46d10876e263743c8080b1e05144abd8ce351306007
ledger                 18d178940933f812450fe8aa940efcf25129a545db9153cb7da13f87808149d2
```

El ensamblador aceptó 60/145 campañas: R03 2/29, 85 faltantes, cero inválidas/advertencias, ocho coincidencias dentro de `train` sin una nueva y cero cruces observados.

Claude aceptó con limitaciones. Se corrigió su afirmación de puerto reutilizado/fijo en R03 y se restringió la falta de diversidad al nombre, destino y respuesta controlados; no se infiere separabilidad.

**F1N-DNS-VALID-200-R03 ACEPTADA CON LIMITACIONES.** Siguiente: preflight independiente de `F1N-DNS-MIXED-20-2-R03`.
