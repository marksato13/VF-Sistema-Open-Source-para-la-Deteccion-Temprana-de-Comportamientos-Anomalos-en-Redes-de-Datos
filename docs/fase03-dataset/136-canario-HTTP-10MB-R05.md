# Séptimo canario oficial R05 — HTTP-10MB

Fecha: 7 de agosto de 2026. Campaña `F1N-HTTP-10MB-R05`, partición `test`.
Estado: **ACEPTADA CON LIMITACIONES**.

## Propósito y controles previos

Esta celda descarga por HTTP un archivo benigno de 10 MiB a tasa limitada y
responde directamente a la observación del jurado: el dataset debe contener
tráfico legítimo con paquetes de 500–1500 bytes para que el tamaño grande no
sea, por sí solo, señal de ataque. La etiqueta procede del escenario controlado
`experiment/test`, no del tamaño observado.

El preflight continuo pasó sus nueve gates entre `13:05:25.076` y
`13:05:57.544 -05:00` sobre el commit limpio
`d58f692ad402271848b003be4bce201b2aa32c82`. Confirmó matriz
`ad22ce5f…dfa824`, argumentos `aeb9c2b2…0526a`, NTP 5/5 con máximo absoluto
6.329396 ms, 121,457,172,480 bytes disponibles, SSH 4/4, las cuatro NIC
externas `DOWN`, aislamiento/rutas, Suricata limpio y servicios/probes.

El dry-run con volumen oficial explícito pasó ambos storage gates, marker y
mountpoint; fijó argumentos `10MB 2M`, estimación de 12,000,000 bytes y
quietud/warm-up/settle/cooldown `70/60/9/30 s`.

Claude observó que el preflight versionado prueba `/health`, pero no valida el
archivo objetivo. Antes de capturar, Codex verificó por Ansible en Servidor
10,485,760 bytes y SHA-256
`e5b844cc57f57094ea4585e235f36c78c1cd222262bb89d53c94dcb4d6b3e55d`;
desde Cliente obtuvo HTTP 200 y `Content-Length: 10485760`. Esta comprobación
manual actual cerró el control operativo, aunque su salida no quedó incluida en
el bundle inmutable: se conserva como limitación de trazabilidad y mejora
pendiente para automatización posterior a R05. Claude autorizó exactamente una
captura; se ejecutó una sola vez, sin retry, piloto, modelo ni scoring.

## Transferencia y PCAP

| Control | Resultado |
|---|---:|
| HTTP / bytes curl | 200 / 10,485,760 |
| Duración / velocidad | 4.506622 s / 2,326,744 B/s |
| PCAP capturado / recibido / parseado | 8,033 / 8,033 / 8,033 |
| PCAP archivos / bytes | 1 / 11,146,312 |
| Drops / transferencia / límite | 0 / verificada / no alcanzado |
| IPv4 de 500–1500 bytes | **7,244 / 8,033 = 90.1780 %** |
| Exactamente 1,500 bytes | 7,238 |
| Longitud media / máxima | 1,357.56 / 1,500 bytes |

El escenario terminó con código cero y stderr vacío. La descarga completa, el
PCAP íntegro y los 7,244 paquetes del rango objetivo demuestran que una
transferencia HTTP legítima puede estar dominada por paquetes grandes.

## EVE y alcance causal

EVE contiene 14 registros: diez `stats`, un `http`, un `fileinfo` y dos
`flow`. El evento HTTP real registra GET `/files/10MB.bin` y estado 200. El
`fileinfo` conserva `state=TRUNCATED`, `size=102400` y `gaps=false`: refleja el
límite de inspección de archivos de Suricata, no una descarga incompleta. La
prueba de transferencia completa proviene de curl y del PCAP, no del tamaño
parcial de `fileinfo`.

Los dos flows son probes anteriores:

- ICMP de control `13:05:56.133059–13:05:57.197710`, emitido por timeout a
  `13:10:58.386729`;
- DNS de control `13:05:55.872139–.872699`, emitido por timeout a
  `13:11:02.375718`.

Ambos ocurrieron antes del inicio PCAP verificado `13:10:18.395048`; se
preservan en EVE pero no pertenecen al episodio ni entran en features. Suricata
incrementó 8,035 frente a 8,033 paquetes PCAP. El delta +2 queda sin causa
atribuida; con drops cero no se observa impacto, sin declarar riesgo cero.

## Features y fase UTC

La extracción usó 8,033 observaciones PCAP y una observación HTTP. La descarga
cruzó un borde UTC y produjo dos ventanas autocorrelacionadas:

| Fin UTC | Paquetes | Media IP | Ratio 500–1500 | SYN rate / completion | HTTP / error |
|---|---:|---:|---:|---:|---:|
| `18:11:20` | 3,852 | 1,222.23052960 | 0.80815161 | 0.1 / 1.0 | 1 / 0 |
| `18:11:30` | 4,181 | 1,482.24491748 | 0.98804114 | 0.0 / 0.0 | 1 / 0 |

La historia de 60 s mantiene el request HTTP en ambas filas, mientras el SYN y
su completion pertenecen sólo a la primera ventana de tasa. Las dos filas son
ventanas del mismo episodio y no dos descargas independientes. Ninguna coincide
exactamente con HTTP-10MB/R01–R04 ni con otra campaña; añaden diversidad sin
incrementar los duplicados.

## Recursos, integridad y auditoría

El Sensor produjo 56 muestras: CPU 0.00–3.59 %, RSS estable en 782,504 KiB,
memoria disponible 14,080,820–14,162,012 KiB y load1 0.14–0.32. Son cifras
descriptivas, no SLA.

```text
preflight             474b0cfbfc0f35f3f2442aae55a24f0118a4cea8906639644fddc9fc6cce8181
manifest              7b7bdf62d22b8fee25fe4c32d38f416727f391fdc0797ba61671fe1f51a5c010
pcap                  b5c2eb127e6f4b9dbfaeca52e967d4c136a91aa099a584e2afe8bdf0a6c26c76
eve                   6b135be288f66632ea07a31b10db05fe2af8584acdeea135dad849b9cb7ba73c
campaign SHA256SUMS   1235087699aaacce1258892a9b24a297c40a4cc6eae11e90ede1497420e38f49
features CSV          6de2275a6aa30ebe98a55d5535e1b6f8bc46c2b9ebaf88053598057af7507232
extraction report     e9a440295a7acd31d5031e121de77bddf1f64de7f463872318644021547eedd4
feature SHA256SUMS    c4682fbaa690cf432b073cf6bf0494915ca237c87c0edbb43a5b6501bbcc098f
ledger                931482be11a8945a97e997715fe90f975a50851d5efca6bcf2bc04f397bbacd3
```

Ambos bundles y la copia PCAP remota/local pasaron. El auditor limpio aceptó
123/145 campañas: R05 7/29, 22 faltantes, 33 duplicados, 16 cruces y cero
inválidas/advertencias. El resumen R05 contiene siete perfiles, once filas,
8,837 observaciones de paquete y 305 de aplicación; `large_ip_ratio_10s` tiene
soporte en las dos filas de esta campaña y no hay duplicados internos R05.

Claude verificó los artefactos individuales, no reejecutó el auditor, y emitió
**ACEPTAR CON LIMITACIONES** por autocorrelación, delta +2, inspección truncada
y trazabilidad manual del archivo objetivo.

**Decisión:** `F1N-HTTP-10MB-R05` queda cerrado con limitaciones. Después de
publicar, el siguiente paso independiente es el preflight de
`F1N-HTTP-100MB-R05`. R05 permanece sin scoring parcial.
