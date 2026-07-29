# Primer canario oficial R03 — DNS-VALID-10

Fecha: 29 de julio de 2026. Campaña: `F1N-DNS-VALID-10-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

La tercera repetición de F1 comienza con diez consultas DNS legítimas y secuenciales desde Cliente `10.20.0.20` hacia Servidor `10.30.0.10:53`. Cada consulta solicita `server.ppi.lab/A` y debe resolver `10.30.0.10`. Es un perfil ligero determinista; complementa los perfiles benignos pesados.

El preflight confirmó Git limpio y sincronizado en `7c0d42e53b11e2c73fd4304ffff709fc4de1f71c`, ID y lock libres, almacenamiento oficial `PASS` y 134,505,775,104 bytes disponibles. Las cuatro VM respondieron por SSH. El gate NTP pasó con un desfase absoluto máximo observado de 0.394 ms.

Suricata estaba activo con cero drops e `ifdrops`; dnsmasq resolvió correctamente la consulta de control. Las rutas atravesaban el Sensor, las cuatro NIC externas estaban `DOWN` y el bypass `172.17.25.111–114` quedó bloqueado por ICMP y TCP/22. Cliente y Servidor conservaron iperf3 3.20 según la política de F1. El generador local y remoto coincidió:

```text
d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203
```

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Estrato / escenario | `light` / `dns-valid` |
| Argumentos | `10` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `6e32bc5b03ab4d239b1eff1de30de5007f906dda41e8f720240bbf6481496a60` |

## Resultado DNS

El escenario terminó con código cero, stderr vacío y exactamente diez líneas `10.30.0.10`.

| Control | Resultado |
|---|---:|
| Consultas / respuestas | 10 / 10 |
| Nombre / tipo | `server.ppi.lab` / `A` |
| RCODE | 20 eventos `NOERROR` |
| Respuestas A | 10 × `10.30.0.10` |
| IDs / puertos origen distintos | 10 / 10 |
| Span DNS | 0.228806 s |
| Alertas / NXDOMAIN | 0 / 0 |

EVE acredita cada solicitud y respuesta. La exactitud se limita a este episodio controlado.

## PCAP, Suricata y recursos

| Control | Resultado |
|---|---:|
| Evidencia completa | `true` |
| PCAP capturado / recibido / parseado | 20 / 20 / 20 |
| PCAP | 1 archivo / 2,324 bytes |
| Drops tcpdump | 0 |
| Delta Suricata / PCAP | 20 / 20 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 29 / 29 |
| Transferencia / límite PCAP | verificada / no alcanzado |

Los veinte paquetes son UDP/IPv4 y menores de 500 bytes; la longitud media es 85 y la máxima 87. El 0 % entre 500–1500 bytes es correcto para DNS ligero y no contradice la cobertura pesada agregada de F1.

EVE contiene veinte DNS y nueve `stats`. R01 tuvo diez `stats`; R02 y R03, nueve. Suricata contó 24 paquetes en R01/R02 y 20 en R03. No existe una tolerancia ni se atribuye la diferencia a fase, ruido, ARP, ICMPv6 o flush sin evidencia.

El Sensor produjo 53 muestras: CPU máxima 1.53 %, RSS 781,816 KiB, memoria disponible mínima 13,957,184 KiB y carga máxima 0.39. Son observaciones, no umbrales.

## Features y tres repeticiones

El extractor procesó veinte paquetes, obtuvo diez observaciones de aplicación y produjo una fila elegible:

| Feature | Valor |
|---|---:|
| `packet_rate_10s` | 2.0/s |
| `byte_rate_10s` | 170.0 B/s |
| `mean_ip_len_10s` | 85.0 B |
| `large_ip_ratio_10s` | 0.0 |
| `flow_attempt_count_30s` | 10 |
| `flow_attempt_rate_10s` | 1.0/s |
| `unique_dst_ip_ratio_30s` | 0.1 |
| `unique_dst_port_ratio_30s` | 0.1 |
| `dns_query_count_60s` | 10 |
| `dns_nxdomain_ratio_60s` | 0.0 |
| Resto de las 14 features | 0.0 |

| Métrica | R01 | R02 | R03 |
|---|---:|---:|---:|
| Paquetes / bytes PCAP | 20 / 2,324 | 20 / 2,324 | 20 / 2,324 |
| Span DNS | 0.242729 s | 0.246351 s | 0.228806 s |
| EVE DNS / `stats` | 20 / 10 | 20 / 9 | 20 / 9 |
| Delta Suricata | 24 | 24 | 20 |
| Filas | 1 | 1 | 1 |
| Vector de 14 features | igual | igual | igual |

Los tres episodios tienen PCAP, EVE, manifiestos, ledgers, hashes y tiempos distintos, pero producen el mismo vector. Esto demuestra reproducibilidad funcional y aumenta el peso de esa firma dentro de `train`; no demuestra diversidad, independencia estadística ni reutilización de evidencia. No es autocorrelación temporal porque las filas proceden de campañas separadas.

## Integridad raíz

```text
manifest.json          e3a4fa0b6d2a4250cacc330f6d62d34bc695c100afbd9233fa905467bc3072e6
capture.pcap0          5dc49a14b03f16e3673b972c124d6818bb886c3e341caced92801aa5bac3ed15
eve-slice              39cf480216779917878064cc2ab9d2a44312adcb0efc267fa03316ba9690e986
campaign SHA256SUMS    fa856ff893fdd21103bc6d5f40802143aabe0fc1ff58b563d292062db5add166
multilayer-v1.csv      5913efac5bf01fdfe2a67b24a44dee755305a6e0dade6e06b7559a97ca330b98
extraction-report      4a30b805ea442497e784c9969d7e04e4165f0938033d3c63d66622ab0c3ea35e
feature SHA256SUMS     b50dcc430115dc84d5bdc34325b31e6da2a3719ff0c3cc6281134d7d5bcc8420
ledger                 5634e9ac5a0d449ff988750471d5027db9032886ab7f970bbbbac6572960e45f
```

El ensamblador aceptó 59/145 campañas: R03 1/29, 86 faltantes, cero inválidas/advertencias, una calibración excluida, ocho coincidencias exactas dentro de `train` y cero entre particiones. R02 y R03 de este perfil apuntan al primer vector R01. Validation/test aún no existen, por lo que cero cruces no prueba ausencia futura.

Claude aceptó con limitaciones. Se corrigieron tolerancia NTP, soporte de features, conteo de duplicados/filas, autocorrelación, robustez del modelo, causas de contadores, suficiencia, particiones, umbrales y análisis exploratorios inventados.

**F1N-DNS-VALID-10-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: preflight independiente de `F1N-DNS-VALID-200-R03`; no ejecución ciega de R03.
