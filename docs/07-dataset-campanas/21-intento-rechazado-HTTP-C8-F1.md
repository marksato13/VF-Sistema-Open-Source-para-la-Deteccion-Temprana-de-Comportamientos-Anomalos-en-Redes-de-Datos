# Intento oficial rechazado — HTTP concurrente C8 R01

Fecha: 23 de julio de 2026. Campaña: `F1N-HTTP-C8-R01`. Commit de captura: `99919343017dedb4c2670fdb29c0f6812c199953`.

## Decisión

**CAMPAÑA RECHAZADA.** `tcpdump` reportó 476 paquetes descartados por el kernel. El contrato de F1 exige cero drops, por lo que el manifiesto quedó `evidence_failed`, `evidence.complete=false`, el ledger quedó `failed` y no se extrajeron features oficiales.

El intento no incrementa las quince campañas aceptadas ni reduce las 130 celdas faltantes. El ensamblador lo identifica explícitamente como una campaña inválida por estado de ledger.

## Preflight

Todos los gates previos pasaron:

- Git limpio y sincronizado; ID libre y ausencia de lock/captura;
- volumen oficial con 145,023,565,824 bytes libres y gate global PASS;
- jerarquía NTP VM01→Sensor→resto con offsets inferiores a 100 ms;
- zona `America/Lima`, NIC externas `DOWN` y bypass de Kali bloqueado;
- rutas Cliente/Kali→Sensor→Servidor y retorno DMZ;
- Suricata activo, cero drops/ifdrops, decoder u overflow;
- servicios del Servidor activos y `100MB.bin` de 104,857,600 bytes;
- HEAD HTTP 200 y generador remoto con el hash versionado.

| Campo | Valor |
|---|---|
| Perfil / repetición | `HTTP-C8` / `R01` |
| Escenario / argumentos | `http-concurrent` / `8 100MB 2M` |
| Propósito / partición | `experiment` / `train` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / no alcanzado |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `048896cb26996464f54cd1f8d12cceb7d61e49246645aea858af30019dec7bdb` |

## Resultado funcional

Las ocho descargas terminaron con HTTP 200, sin stderr:

| Flujo | Bytes | Tiempo | Velocidad |
|---:|---:|---:|---:|
| 1 | 104,857,600 | 49.512809 s | 2,117,787 B/s |
| 2 | 104,857,600 | 49.516284 s | 2,117,638 B/s |
| 3 | 104,857,600 | 49.515113 s | 2,117,688 B/s |
| 4 | 104,857,600 | 49.514959 s | 2,117,695 B/s |
| 5 | 104,857,600 | 49.509603 s | 2,117,924 B/s |
| 6 | 104,857,600 | 49.509539 s | 2,117,927 B/s |
| 7 | 104,857,600 | 49.509294 s | 2,117,937 B/s |
| 8 | 104,857,600 | 49.513294 s | 2,117,766 B/s |

El total fue 838,860,800 bytes. La suma reportada equivale a 135.538896 Mbit/s y bytes sobre el mayor tiempo a 135.528878 Mbit/s, frente a 134.217728 Mbit/s nominales.

Los puertos origen `41570`, `41580`, `41588`, `41596`, `41610`, `41614`, `41616` y `41624` comenzaron en un intervalo de 47.470 ms y se solaparon aproximadamente 49.51 s. Cada flujo contiene un SYN, un SYN/ACK, dos FIN y cero RST.

## Evidencia válida y fallo

| Control | Resultado |
|---|---:|
| Escenario | 8/8 HTTP 200 |
| PCAP capturado/recibido | 596,704 / 597,180 |
| Drops `tcpdump` | **476 — 0.079708 %** |
| PCAP parseado | 596,704 |
| Archivos / bytes | 2 / 887,835,808 |
| Tamaños | 512,000,322; 375,835,486 bytes |
| Límite alcanzado | No |
| Transferencia y SHA remoto/local | PASS |
| EVE esperado/extraído | 37 / 37 |
| Delta Suricata | 597,190 paquetes |
| Drops/ifdrops Suricata | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| Muestras / stderr Sensor | 122 / vacío |

EVE contiene 21 `stats`, ocho `http` y ocho `fileinfo`. Todos los HTTP son GET 200. Cada `fileinfo` quedó `TRUNCATED` a 102,400 bytes por el límite de inspección conocido, no por el fallo del PCAP.

La distribución PCAP conserva 596,704 paquetes IPv4: 579,568 —97.1282 %— entre 500 y 1500 bytes, 578,818 exactamente de 1500 bytes, media 1,457.90 y máximo 1,500. Estos datos son diagnósticos y no entran al entrenamiento.

Suricata alcanzó 44.41 % de CPU y 778,256 KiB RSS; la memoria disponible mínima fue 13,959,920 KiB y la carga máxima 0.55. No existe un techo formal de CPU para aceptar F1.

## Causa demostrada e hipótesis

Está demostrado que el descarte ocurrió en el socket de captura de `tcpdump`, no en Suricata. La causa temporal exacta no puede localizarse con los contadores disponibles.

El primer archivo terminó en `1784822168.615976` y el segundo comenzó en `1784822168.615978`: dos microsegundos. Esto no demuestra ni descarta que la rotación contribuyera.

La hipótesis principal es que el búfer de 4,096 KiB no absorbió una ráfaga o una pausa de escritura. La rotación es una hipótesis secundaria. Por rigor, la primera calibración cambiará solo:

- `tcpdump -B 4096` → `-B 65536`;
- `net.core.rmem_max=4194304` → `67108864`.

La rotación permanece 512 MB × 4 y la capacidad nominal sigue en 2.048 GB.

## Integridad raíz

```text
manifest.json  8977d8fa626ca27ffb4044ee613338b83cdeb74b641acc7792cfedc439dcf5ca
capture.pcap0  d75436e93d3a7155402d14f8a3225accade3743efa2ed56aeae057e3c0a30da4
capture.pcap1  917e0e6e85df9c69a41bf1272d182bb0e08b4a7475b55533b3f458650b79eee8
eve-slice       4e358851ca09d6c9e44ece90723cf2a5cf5038f8f995b90c317a6df6d74fe92b
SHA256SUMS      436395442b08a5340687a055f37a72a866ca7ee86cc2f69a5bf662736a062306
ledger          07df869c7f21636f015d24a6b01908a38c47cd63efb0c451b3a8cdcd37a3e8a1
```

Todos los archivos enumerados en `SHA256SUMS` pasan. Integridad de archivos no equivale a completitud de captura.

## Próximo paso

Se desplegará el aumento de búfer y se ejecutará `HTTP-C8` como calibración `CAL-G6-HTTP-C8-R01`, siempre excluida del dataset. Para diagnosticar, se reportará cualquier drop; para autorizar un reintento oficial se exigirán cero drops.

No se reintentará automáticamente ni se sobrescribirá este bundle. Si la calibración pasa, se definirá y ejecutará un archivado preservando el intento rechazado fuera de las raíces que consume el ensamblador; después el reintento usará nuevamente el único ID canónico `F1N-HTTP-C8-R01`. Un sufijo `RETRY` no es compatible con el contrato actual.

Seguimiento: la calibración de búfer pasó con cero drops y está documentada en `22-calibracion-buffer-HTTP-C8-G6.md`. Posteriormente, este intento se archivó íntegramente como `attempt-01` mediante el procedimiento `../05-plan-pruebas/17-archivado-intentos-fallidos.md`; ya no ocupa las raíces activas. El reintento canónico fue aceptado y se documenta en `23-canario-HTTP-C8-F1.md`.
