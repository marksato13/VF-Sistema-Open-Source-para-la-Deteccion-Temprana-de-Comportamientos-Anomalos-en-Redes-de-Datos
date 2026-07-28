# Decimoséptimo canario oficial R02 — HTTP-MULTI-1

Fecha: 28 de julio de 2026. Campaña: `F1N-HTTP-MULTI-1-R02`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Una solicitud HTTP legítima a cada VIP DMZ: `10.30.0.10`, `.11` y `.12`. El perfil aporta diversidad L3 lógica mediante tres IP en la misma VM Servidor; no representa tres hosts físicos.

El preflight confirmó Git limpio y sincronizado en `5acdd5cfff64491168825d98bfb0353b4ca6eab5`, ID libre, 137,392,615,424 bytes disponibles y almacenamiento oficial válido. Las cuatro VM respondieron por SSH y NTP pasó con desfase absoluto máximo de 0.091 ms. Las tres VIP estaban configuradas y devolvieron HTTP 200 desde Cliente. Servicios, captura, generador, rutas, aislamiento y Suricata pasaron.

| Campo | Valor |
|---|---|
| Propósito / partición | `experiment` / `train` |
| Escenario / argumento | `http-multi` / `1` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `43de3a417d75f4818c5a553268b80ce3a5805109a3bbc6b605e9fb0b8f50b485` |

## Conteos exactos

El Cliente produjo tres líneas: una por `.10`, `.11` y `.12`, todas con request 1 y HTTP 200; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 3,369 |
| Capturados / parseados / drops | 30 / 30 / 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE extraído / esperado | 16 / 16 |
| Stats / HTTP / fileinfo | 10 / 3 / 3 |
| Delta Suricata / PCAP | 32 / 30 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los dos paquetes adicionales del contador Suricata no están identificados; no se calcula un porcentaje contra PCAP porque los contadores tienen alcances diferentes.

Cada VIP tiene exactamente un GET `/health`, HTTP 200 y longitud 36. Los tres `fileinfo` están `CLOSED`, `gaps=false` y `size=36`. No existen eventos adicionales del preflight. Todos los hashes pasaron.

Los 30 paquetes son menores de 500 bytes, con media IP 81.50 y máximo 251. Es un perfil multidestino ligero, no cobertura de tráfico pesado.

## Feature y repetibilidad

La fila R02 es elegible:

| Paquetes | Attempts / SYN / HTTP | Packet rate | Attempt/SYN rate | IP ratio | Port ratio | HTTP error |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 3 / 3 / 3 | 3.0 s⁻¹ | 0.3 / 0.3 s⁻¹ | 1.0 | 0.33333333 | 0 |

`unique_dst_ip_ratio_30s=3/3` demuestra tres direcciones destino. `unique_dst_port_ratio_30s=1/3` refleja un único puerto HTTP para tres intentos.

R01 y R02 tienen resultados idénticos: PCAP 30 paquetes/3,369 bytes, tres HTTP, tres `fileinfo`, distribución de tamaños y una fila con las mismas 14 features. R01 duró 0.262204 s y R02, 0.265720 s. Sus PCAP, EVE, puertos origen, timestamps, ledger y hashes son independientes.

La coincidencia exacta añade el quinto vector repetido dentro de `train`; no existe cruce de partición. Es repetibilidad del generador determinista, no reutilización de evidencia ni una orden automática de eliminar filas. Las cuatro coincidencias previas son `DNS-VALID-10`, `DNS-MIXED-20-2`, `DNS-MIXED-50-10` y una ventana estable de `PING-100`.

R01 tuvo delta Suricata 34 frente a PCAP 30; R02, 32 frente a 30. Los adicionales no se identifican ni se relacionan entre sí.

El Sensor produjo 53 muestras: CPU máxima 1.52 %, RSS 780,308 KiB, memoria disponible mínima 14,099,708 KiB y carga máxima 0.23.

## Integridad raíz

```text
manifest.json          8e2267115d17d65a537f9c96ee12758ed635960838e2937ef98c604f2f31355e
capture.pcap0          34a1f2baabcb1402e58b6611afd6ec6ba1510cfea4dd8ae67cce135850c7796b
eve-slice              75a0dc7c7ae39bffa4032161041bd399a5d6b57d5b2067bbd8047890f9c4c046
campaign SHA256SUMS    301e8516b4ff9d4539e9ffb35d8614e917d072e31c38620b72978e7b62696e60
multilayer-v1.csv      9fd8a873c5e16e3e833ddacf23780f1701548b2e4fe48c838d4518288df7cd88
extraction-report      1a8e1fa1da0748aebe52558dfd6d19572aa3af39eed206eeb1606f025223286a
feature SHA256SUMS     e963f6319c54a6d2868f5a59a0911befc9ec175f65d8ed296d2d0255d156a196
ledger                 53e5f788bed297661fa13c3e72f8b21c8819956a50ffc4e31e9e73c4535bee20
```

El ensamblador aceptó 46/145 campañas, R02 17/29, 99 faltantes, cero inválidas/advertencias, cinco coincidencias dentro de `train` y cero entre particiones.

Claude aceptó y autorizó `HTTP-MULTI-5/R02`. Se corrigieron packet rate, inventario de duplicados, autocorrelación de una fila, porcentaje entre alcances, recursos y gates de firewall inexistentes.

**F1N-HTTP-MULTI-1-R02 ACEPTADA CON LIMITACIONES.** Siguiente: `F1N-HTTP-MULTI-5-R02`.
