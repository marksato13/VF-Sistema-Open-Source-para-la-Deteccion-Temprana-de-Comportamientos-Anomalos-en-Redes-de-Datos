# Decimonoveno canario oficial R04 — HTTP-C2

Fecha: 6 de agosto de 2026. Campaña `F1N-HTTP-C2-R04`, partición `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Dos descargas HTTP concurrentes de `100MB.bin` desde un Cliente hacia un Servidor, limitadas nominalmente a `10M` bytes/s por flujo. Mide concurrencia, tasa de bytes y tráfico pesado legítimo; dos conexiones de un mismo proceso no representan dos usuarios, clientes o destinos.

El preflight completo pasó en un único proceso entre `11:19:14.258` y `11:19:37.763 -05:00` sobre commit limpio `e98f196cf8b34391037e3079663182ca74cfcc66`. Pasaron contrato, volumen oficial con 124,350,451,712 bytes disponibles, NTP 5/5 (máximo absoluto 0.598 ms), IDs, SSH, NIC externas `DOWN`, bypass, rutas, Suricata, captura, servicios, DNS, ICMP y generador. El archivo midió 104,857,600 bytes, SHA-256 `20492a4d0d84f8beb1767f6616229f85d44c2827b64bdbfb260ee12fa1109e0e`; HEAD desde Cliente devolvió 200 y Content-Length correcto. El log por gate tiene SHA-256 `2e0b31410e44bae9fc7a15d89cb01fa9b240a9c43ba496ea2f70af9921d365b8`.

Claude autorizó exactamente una captura, con techo agregado predefinido de 200 Mbit/s. No hubo reintento ni scoring.

## Transferencias y concurrencia

| Flujo | HTTP | Bytes | Tiempo | Velocidad |
|---|---:|---:|---:|---:|
| 1 | 200 | 104,857,600 | 9.506924 s | 11,029,603 B/s |
| 2 | 200 | 104,857,600 | 9.514152 s | 11,021,223 B/s |

Los SYN se separaron 8.181 ms. Los intervalos PCAP fueron 9.509974 y 9.508417 s, con aproximadamente 9.502 s de solapamiento: la concurrencia fue real. La suma reportada fue 176.406608 Mbit/s y los bytes totales sobre el mayor tiempo, 176.339583 Mbit/s; ambos están bajo el techo. `curl --limit-rate` no se interpreta como shaper exacto.

## Integridad, EVE y features

| Control | Resultado |
|---|---:|
| PCAP capturado / recibido / parseado | 153,707 / 153,707 / 153,707 |
| PCAP | 1 archivo / 222,580,772 bytes |
| Drops / límite / transferencia | 0 / no alcanzado / verificada |
| Suricata / PCAP | 153,712 / 153,707 |
| drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |
| EVE stats / HTTP / fileinfo / flow | 12 / 2 / 2 / 1 |
| Paquetes de 500–1500 bytes | 145,016 / 153,707 (94.3457 %) |
| Paquetes de 1,500 bytes | 144,984 |
| longitud media / máxima | 1,418.08 / 1,500 bytes |

El delta Suricata +5 queda sin causa atribuida. Los dos HTTP son GET `/files/100MB.bin` con estado 200. Los dos `fileinfo` están `TRUNCATED`, `size=102400`, `gaps=false`: es el límite de inspección de Suricata, no truncamiento de las descargas ni del PCAP. Los valores `http.length` tampoco sustituyen los bytes completos medidos activamente.

EVE conserva un `flow` IPv6 link-local de un único paquete, iniciado durante warm-up y emitido por timeout. Está fuera del filtro PCAP de las IP del experimento y del alcance del extractor para `10.20.0.20`; no alteró los 153,707 paquetes IPv4 ni las features. Se conserva sin borrarlo.

La única fila elegible contiene 153,707 paquetes, dos intentos/SYN/HTTP, 15,370.7 pkt/s, 21,796,953.8 B/s, media 1,418.08465457, ratio pesado 0.94345736, finalización 1.0 y ratios IP/puerto 0.5. La alineación temporal produjo una sola ventana, no la fila de cierre observada en R02/R03. No coincide exactamente con R01–R03 ni con otro vector global; aporta diversidad observacional nueva. Sigue siendo una sola ejecución y un solo episodio.

El Sensor produjo 68 muestras: CPU 0–31.26 %, RSS 781,720 KiB, memoria disponible 14,040,836–14,161,116 KiB y load1 0.04–0.28. Ambos bundles pasaron. Hashes: manifest `b1fa91d9…`, PCAP `ea924746…`, EVE `60a6e989…`, CSV `e59944fd…`, extraction report `98227275…` y ledger `cb710a5b…`.

El auditor limpio aceptó 106/145, R04 19/29, 39 faltantes, 24 coincidencias, siete cruces y cero inválidas/advertencias.

**ACEPTADA CON LIMITACIONES.** Demuestra dos flujos HTTP concurrentes, íntegros y pesados de un mismo Cliente; no múltiples usuarios. Conserva delta +5 y un flow ambiental fuera del PCAP/features. No hubo scoring. Claude autorizó únicamente el preflight independiente `F1N-HTTP-C4-R04`; no su captura.
