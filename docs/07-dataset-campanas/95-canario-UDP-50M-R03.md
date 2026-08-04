# Vigesimoctavo canario oficial R03 — UDP 50 Mbit/s

Fecha: 4 de agosto de 2026. Campaña: `F1N-UDP-50M-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Iperf3 genera un stream UDP benigno de 50 Mbit/s durante 20 s, con bloques de 1,448 bytes, desde Cliente hacia Servidor a través del Sensor. Es el techo UDP calibrado para F1 y aporta normalidad L3/L4 pesada; no representa un SLA.

El dry-run fijó `experiment/train`, quietud/warm-up/settle/cooldown `70/60/9/30 s`, commit limpio `40177cafb2ffbcbf143fc5e803f5191066996e9e`, matriz SHA `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` y argumentos SHA `7b6496223b57502ffb482ccf32fdc28990b008ba20a1fb176139c9d7790b852f`.

El almacenamiento pasó con 128,293,380,096 bytes disponibles. NTP pasó en cinco nodos con máximo absoluto 2.122 ms, SSH 4/4, las cuatro NIC externas estaban `DOWN`, el bypass quedó bloqueado y las rutas pasaron por Sensor. Suricata estaba sano y la captura inactiva. Iperf3 3.20 estaba instalado en ambos extremos y escuchaba solo en `10.30.0.10:5201`, sin sesión establecida después del sondeo.

La versión 3.20 conserva comparabilidad con R01/R02, pero existe una corrección posterior en 3.21 para un caso de reporte erróneo de pérdida cero. No se ha demostrado que ese defecto explique la discrepancia de R02. Por ello se autorizó exactamente una ejecución, condicionada a auditar la secuencia binaria del payload UDP.

## Resultado UDP

| Métrica | Emisor | Receptor |
|---|---:|---:|
| Bytes | 125,004,392 | 125,004,392 |
| Datagramas | 86,329 | 86,329 |
| Duración | 20.001880 s | 20.002633 s |
| Bitrate | 49.997057 Mbit/s | 49.995175 Mbit/s |
| Jitter | 0 ms | 0.104768 ms |
| Perdidos / fuera de orden | 0 / 0 | 0 / 0 |
| Pérdida | 0 % | 0 % |

El escenario terminó con código cero y stderr vacío. Bytes y datagramas coinciden entre extremos en esta ejecución. La auditoría binaria de solo lectura encontró las secuencias `1..86,329`: 86,329 observadas, 86,329 únicas, cero faltantes y cero duplicadas.

La secuencia prueba continuidad en el punto Sensor. La igualdad del reporte receptor aporta evidencia separada de recepción de aplicación en el Servidor para R03. Ninguna permite generalizar el comportamiento de iperf3 3.20 ni resolver causalmente R02.

## Composición e integridad

Los 86,359 paquetes del PCAP se reconciliaron exactamente:

- 86,329 UDP de datos con payload de 1,448 bytes;
- dos UDP de inicialización con payload de cuatro bytes;
- 28 TCP de control, con 1 SYN, 1 SYN/ACK, 2 FIN, 0 RST y span 20.009614 s.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 130,014,785 |
| Capturados / recibidos / parseados | 86,359 / 86,359 / 86,359 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| Delta Suricata / PCAP | 86,363 / 86,359 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE esperado / extraído | 13 / 13 `stats` |
| Muestras Sensor / stderr | 72 / vacío |
| Lock / captura residual | ausente / inactiva |

Los cuatro paquetes adicionales del contador Suricata no tienen causa identificada. La pérdida reportada por la aplicación y los drops de observación son controles distintos. EVE sin alertas no prueba benignidad; esta procede del escenario controlado.

El PCAP supera el payload UDP en 5,010,393 bytes —4.008174 %— por estructura, cabeceras, inicialización y control; no mide pérdida.

De 86,359 paquetes IPv4, 86,329 —**99.9653 %**— midieron 500–1500 bytes; 30 fueron menores de 500, ninguno superó 1,500 y ninguno midió exactamente 1,500. La media fue 1,475.51 y la máxima, 1,476 bytes.

## Features, comparación y recursos

| Fin UTC | Paquetes | Packet rate | Byte rate | Media IP | Ratio grande | Intentos de flujo / SYN / completion |
|---|---:|---:|---:|---:|---:|---:|
| `23:38:10` | 21,011 | 2,101.1 | 3,098,961.6 | 1,474.9234 | 0.99923849 | 2 / 1 / 1 |
| `23:38:20` | 43,162 | 4,316.2 | 6,370,711.2 | 1,476.0000 | 1.00000000 | 2 / 0 / 0 |
| `23:38:30` | 22,186 | 2,218.6 | 3,272,724.9 | 1,475.1307 | 0.99936897 | 2 / 0 / 0 |

Las tres filas suman 86,359 y están correlacionadas con la captura. Ninguna coincide exactamente con R01 o R02. Los bordes UTC explican su distribución temporal, no una causa de las pequeñas diferencias entre repeticiones.

| Repetición | Emisor / receptor | Jitter receptor | PCAP | Ratio 500–1500 |
|---|---:|---:|---:|---:|
| R01 | 86,331 / 86,331 | 0.132158 ms | 86,364 | 99.9618 % |
| R02 | 86,331 / 86,330 | 0.099880 ms | 86,360 | 99.9664 % |
| R03 | 86,329 / 86,329 | 0.104768 ms | 86,359 | 99.9653 % |

R03 no reproduce la contradicción emisor/receptor de R02, cuyos campos de pérdida reportaron cero. Tampoco demuestra que esa contradicción proceda —o no proceda— del defecto corregido en iperf3 3.21. R03 emitió dos datagramas menos que R01/R02; no se atribuye causa ni tendencia.

El Sensor registró CPU máxima 5.17 %, RSS máxima 781,720 KiB, memoria disponible entre 14,068,464 y 14,155,816 KiB y carga entre 0.06 y 0.46. No existe umbral formal para declarar capacidad o SLA.

## Integridad y decisión

```text
manifest              79906de40aa3d61430efdb71f982e77bd6c6b755938f2b7434091f7de0a17b3b
pcap                  836aafbd4e75c2ed47df94ca51366bb69010bfc21cc4eb6424d59786dfc23f91
eve                   ddce1e500a61910497026824c3793ab961aef2ba0500bb664e2975ea97196bdd
campaign SHA256SUMS   b8dbd960ae2e11a017959a9b07b6be7c8c425b17858a2862dedf8dfaf62d9987
features CSV          529e0c0eb7d4ba36f7f41a8ae02c96251fc37d5c2dbd70ccf120f37c4bbdb417
extraction report     58ef920720c94b6bb88d7409ec6f647a6d3eef1c92961ce14e045712a6c96570
feature SHA256SUMS    246c8804488de73b7ead524c284dc47f2653aa2b2189b7663bb377bdf32eaaee
ledger                a3c09619af72612b6cd5a83b0e4e1f3db41e657dae2d40018d9f9ea587ec1b68
```

Todos los hashes pasaron. El ensamblador aceptó 86/145: R03 28/29, 59 faltantes, cero inválidas/advertencias, diecisiete duplicados exactos dentro de `train` y cero cruzados. Esta campaña no añadió duplicados.

Claude emitió **ACEPTAR CON LIMITACIONES**. Se consolidó por separado el alcance del PCAP en Sensor y del reporte receptor en Servidor, sin convertirlos en una garantía general de entrega. También se mantuvieron abiertos el delta Suricata y la discrepancia histórica de R02.

**F1N-UDP-50M-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-MIXED-LIGHT-R03`; no su ejecución.
