# Vigesimosegundo canario oficial R03 — TCP-REFUSED-5

Fecha: 1 de agosto de 2026. Campaña: `F1N-TCP-REFUSED-5-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Cinco intentos TCP legítimos desde Cliente `10.20.0.20` hacia un servicio ausente en `10.30.0.10:65000`. El perfil aporta normalidad L4 de rechazo activo; no es escaneo, no usa Kali y no demuestra que cualquier RST sea benigno.

El dry-run fijó Git limpio y sincronizado en `26edafb183ffe2fd661a0600323083a3d01d3ba3`, `experiment/train`, estrato `legitimate-error`, argumento `5`, volumen oficial y reserva `PASS`. NTP pasó en VM01 más cuatro VM con máximo absoluto 0.130 ms. SSH 4/4, rutas por Sensor, NIC externas `DOWN`, bypass bloqueado, Suricata, captura inactiva y generador pasaron.

`ss` confirmó que el Servidor no tenía listener en 65000. Desde Cliente, `nc` devolvió rc 1 y `Connection refused`, no timeout. El sondeo ocurrió antes de los 70 s de quietud y del checkpoint. Claude autorizó una ejecución.

| Campo | Valor |
|---|---|
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `5e3322c682b4e46a737ec3a18be48fc20ba87309ae7f942cef08eb51f2a6537e` |

## Resultado TCP e integridad

El generador informó cinco intentos y cinco rechazos esperados, con stderr vacío. El PCAP contiene exactamente cinco SYN hacia 65000 y cinco RST/ACK de respuesta mediante cinco puertos origen; no contiene SYN/ACK ni FIN.

El episodio duró 2.439553 s. Los intervalos entre SYN fueron 0.605191–0.611665 s y las latencias SYN→RST/ACK, 0.241–0.335 ms. Esto prueba rechazo activo del host, no expiración del comando.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 824 |
| Capturados / recibidos / parseados | 10 / 10 / 10 |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| EVE esperado / extraído | 10 / 10 |
| Tipos EVE | 10 `stats`; cero L7 y alertas |
| Delta Suricata / PCAP | 15 / 10 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

Los cinco paquetes adicionales del contador Suricata no están identificados y no son eventos EVE. EVE y PCAP se validan contra sus propios checkpoints; no se exige igualdad entre eventos y paquetes.

Los diez paquetes son menores de 500 bytes, con media IPv4 50 y máximo 60. Es normalidad L4 ligera, no tráfico pesado.

## Feature y repetibilidad

Todo el episodio cayó dentro de una sola ventana R03:

| Paquetes | Attempts / SYN | Packet / byte rate | Attempt/SYN rate | Completion | RST ratio | IP/port ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 5 / 5 | 1.0 p/s / 50 B/s | 0.5 / 0.5 s⁻¹ | 0 | 0.5 | 0.2 / 0.2 |

`completion=0` corresponde a ausencia de SYN/ACK y `rst_ratio=5/10`. Las ratios destino son 1/5; los puertos efímeros de origen no forman parte del ratio de puerto destino.

R01 y R02 produjeron dos filas cada una por distinta alineación UTC; R03 produjo una. La fila R03 no coincide exactamente con ninguna anterior y el contador global de duplicados dentro de `train` permanece en quince. Las ventanas de una campaña no son repeticiones independientes.

El Sensor produjo 55 muestras: CPU máxima 1.51 %, RSS 781,768 KiB, memoria disponible mínima 14,093,056 KiB y carga máxima 0.17. Sin umbrales no se clasifica presión.

## Integridad raíz

```text
manifest.json          8ad9ad63c0c8c336f8e28921104824ed96f21cf8a8bce8495706251a8132daad
capture.pcap0          cedbf8803200f2756f278680ab81dab1daeb2d6b05d2d4aba8afac4908c477b9
eve-slice              4e7d67f6f4a84032a2b0b08f018e18f336689b09f4bf221e12a211e846b46c94
campaign SHA256SUMS    1f580338df9f050f00ec55071f39e7586ee483d429460ed9739fb82d5d38f508
multilayer-v1.csv      f3025ce125913d612cc7107498a967e426e06d73d785057821b5c182f1e98d6e
extraction-report      d1d6aa1c5683f3de4cf864d1de9a0a0a9748bfb5a9608e8448dc0cbfbb844632
feature SHA256SUMS     8fdc4ac92f46a849528a715859c8161b1b233e57406ccd12013bef7eaca27e25
ledger                 25cafa4a0481a79cbb15478a87cc462dadf2bd3cc4feae144d89078f96b9acbe
```

El ensamblador aceptó 80/145 campañas: R03 22/29, 65 faltantes, cero inválidas/advertencias, quince duplicados dentro de `train` y cero cruzados. Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `TCP-50M/R03`. Se corrigió su doble conteo: 80/145 ya incluye esta campaña, no se incrementa a 81.

**F1N-TCP-REFUSED-5-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-TCP-50M-R03`; no su ejecución.
