# Séptimo canario oficial F1 — HTTPS 100 MB R01

Fecha: 22 de julio de 2026. Campaña: `F1N-HTTPS-100MB-R01`. Es la séptima campaña aceptada y escala en diez veces el volumen del primer canario HTTPS.

## Alcance y preflight

El escenario mantiene TLS 1.3 con certificado autofirmado de laboratorio y Cliente `curl --insecure`. No representa una PKI productiva; busca normalidad de volumen cifrado y señal TLS pasiva.

El preflight confirmó Git limpio en `705aceb488bd25b8fbb6fe1df9ca1e4ceecfabcc`, 147,498,102,784 bytes disponibles, gate de disco PASS, NTP y zona correctos, NIC externas en `DOWN`, rutas por el Sensor, NGINX activo, archivo de 104,857,600 bytes, HTTPS 200, generador remoto íntegro y Suricata sin pérdidas ni errores.

El runner esperó 70 segundos de quietud antes de abrir la campaña y después capturó 60 segundos de warm-up.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTPS-100MB` / `R01` |
| Propósito / partición | `experiment` / `train` |
| Argumentos | `100MB`, límite `10M` bytes/s |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `635178aab4823454458df3365c4a23f997293939e18208fa584b073482370d5e` |

## Ejecución y evidencia

La campaña comenzó a las `22:14:51` y cerró a las `22:16:26 America/Lima`. El escenario terminó sin stderr:

```json
{"http_code":200,"bytes":104857600,"seconds":9.526443,"speed_Bps":11007004}
```

| Control | Resultado |
|---|---:|
| Estado / evidencia completa | `completed` / `true` |
| PCAP capturado/parseado | 74,858 / 74,858 paquetes |
| Tamaño PCAP | 111,210,058 bytes |
| Drops tcpdump | 0 |
| Delta Suricata | 74,862 paquetes |
| Drops / ifdrops | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 15 / 15 |
| Transferencia PCAP | verificada |
| Límite PCAP alcanzado | No |
| Muestras del Sensor | 64, stderr vacío |
| SHA campaña/features | todos PASS |

## Distribución y recursos

| Rango IPv4 | Paquetes | Proporción |
|---|---:|---:|
| Menores de 500 bytes | 2,283 | 3.0498 % |
| De 500 a 1500 bytes | 72,575 | **96.9502 %** |
| Mayores de 1500 bytes | 0 | 0 % |
| Exactamente 1500 bytes | 72,535 | 96.8968 % |

La longitud media fue 1,455.61 bytes y la máxima 1,500. Los 2,283 paquetes pequeños son todos TCP, 2,266 sin payload y cero fragmentados.

Suricata alcanzó 4.43 % CPU, RSS de 776,372 KiB, memoria disponible mínima de 14,177,132 KiB y carga máxima de 0.20.

## EVE, mDNS y features

EVE contiene 12 stats, una sesión TLS 1.3 y dos flows mDNS nacidos durante la quietud:

- `10.20.0.20 → 224.0.0.251`;
- IPv6 link-local del Cliente → `ff02::fb`.

Ambos se emitieron por timeout dentro de la campaña. No son preflight ni descarga; quedan fuera del PCAP LAN↔DMZ y el extractor ignora `event_type=flow`. La única observación de aplicación consumida es el TLS 1.3 a `10.30.0.10`, con JA3, JA3S y JA4.

El extractor produjo dos filas elegibles:

| Ventana UTC | Paquetes | `mean_ip_len_10s` | `large_ip_ratio_10s` | `tls_session_rate_60s` |
|---|---:|---:|---:|---:|
| `03:16:00` | 21,783 | 1,393.42432172 | 0.92650232 | 0.01666667 |
| `03:16:10` | 53,075 | 1,481.13673104 | 0.98715026 | 0.01666667 |

La tasa representa una sesión por 60 segundos. No existe evento HTTP ni fileinfo: el contenido está cifrado. `http_error_ratio_60s=0` es valor por ausencia de observaciones HTTP, no evidencia de que Suricata leyó un HTTP 200.

## Integridad raíz

```text
manifest.json          ba0bb6c0981c52862480813526cf0274612d3e17361c9b17f6ba9e5446be6ff4
capture.pcap0          d67f9fd503ea722336339a7fe62ea78cd1c4389979d2b12a76c273e0219a0002
multilayer-v1.csv      f42ab056cf286b22b676d6c2130e6d604f0b28f0d5fe41081bbea1893434eb4f
extraction-report.json 0c38a6703ba1f3ad9db9ab28fe357621519bd359c84660b1060c293528102af1
ledger                 4288007e9f47179607ef20dbd919812fdd2657eae68ba92d2454d206f67355cc
```

## Revisión y decisión

Claude Code/Haiku emitió **ACEPTAR CONDICIONADO** y autorizó `HTTPS-500MB/R01` si conserva integridad, filas elegibles y cero pérdidas. Ratificó los límites del certificado autofirmado y la baja diversidad de una sola sesión.

El dictamen mencionó truncamiento fileinfo y disponibilidad exclusiva L3/L4; se corrige: HTTPS no produjo fileinfo porque el cuerpo es opaco, y EVE sí aporta la señal L7 pasiva `tls_session_rate_60s`. No se observa semántica HTTP.

El ensamblador acepta siete campañas, cero inválidas, cero advertencias y 138 faltantes.

**CANARIO HTTPS 100 MB ACEPTADO CON LIMITACIONES.** Siguiente perfil: `HTTPS-500MB/R01`.

Revisión: `../04-revisiones-claude/2026-07-22-canario-HTTPS-100MB-F1.md`.

> **Seguimiento:** `HTTPS-500MB/R01` fue ejecutado y aceptado con 97.7033 % de paquetes en rango, tres filas elegibles y cero drops. Ver `13-canario-HTTPS-500MB-F1.md`.
