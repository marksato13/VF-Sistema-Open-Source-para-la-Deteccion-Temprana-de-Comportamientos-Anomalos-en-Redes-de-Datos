# Primer canario oficial F1 — DNS mixto R01

Fecha: 22 de julio de 2026. Campaña: `F1N-DNS-MIXED-20-2-R01`. Esta es la primera ejecución con `purpose=experiment` aceptada por el ensamblador; no es un piloto ni una calibración.

## Autorización y preflight

G7 estaba **APTO PERSISTENTE** antes de iniciar. El preflight confirmó:

- repositorio limpio y sincronizado en `2c4c591444598bf3b646a6901233162f11c91836`;
- ninguna campaña local ni captura remota activa;
- ID libre en VM01 y Sensor;
- volumen oficial `/srv/ppi-evidence/artifacts`, marcador válido y 149,324,533,760 bytes libres;
- gate global de la matriz en PASS: 33,673,250,000 bytes PCAP estimados más reserva de 20 GiB;
- NIC externas de VM02–VM05 desconectadas y sin rutas utilizables;
- `NTPSynchronized=yes` en las cuatro VMs remotas;
- Suricata activo con cero drops, ifdrops, errores de decodificación y overflow;
- generador remoto idéntico al versionado, SHA-256 `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203`.

El plan oficial congelado fue:

| Campo | Valor |
|---|---|
| Perfil | `DNS-MIXED-20-2` |
| Repetición | `R01` |
| Partición | `train` |
| Escenario | `dns-mixed` |
| Argumentos | 20 consultas válidas, 2 NXDOMAIN benignas |
| Warm-up / settle / cooldown | 60 / 9 / 30 s |
| Matriz | `f1-normal-v2` |
| SHA-256 matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA-256 argumentos | `4086992cb07355511e61bfce11d4c2dbf71be23f526d062154f55c2d707ea157` |

## Ejecución

La campaña comenzó a las `18:22:16` y cerró a las `18:23:35 America/Lima`. El ejecutor respetó los 60 s de historia causal y el cooldown posterior. No quedó lock local ni captura remota activa.

El generador produjo 20 respuestas visibles `10.30.0.10` para nombres válidos. Las consultas NXDOMAIN no imprimen una dirección con `dig +short`; su ejecución se confirmó mediante EVE:

```text
20 NOERROR
 2 NXDOMAIN
```

El stderr del escenario quedó vacío.

## Evidencia de campaña

| Control | Resultado |
|---|---:|
| Estado | `completed` |
| `evidence.complete` | `true` |
| PCAP capturado/parseado | 44/44 paquetes |
| Tamaño PCAP | 5,092 bytes |
| Drops tcpdump | 0 |
| Delta Suricata | 48 paquetes |
| Drops/ifdrops Suricata | 0/0 |
| Decoder invalid / alert overflow | 0/0 |
| EVE esperado/extraído | 54/54 |
| Eventos DNS | 44: 22 solicitudes y 22 respuestas |
| Eventos stats | 10 |
| Muestras de recursos | 53 |
| Transferencia y validación PCAP | PASS |
| `SHA256SUMS` campaña | todos PASS |

Este perfil DNS produjo 44 paquetes IPv4 menores de 500 bytes, longitud media 85.18 y máxima 93 bytes. Es correcto para su estrato; no demuestra aún la observación del jurado sobre tráfico legítimo de 500–1500 bytes.

## Extracción `multilayer-v1`

El extractor produjo una fila y la declaró elegible:

| Campo | Valor |
|---|---:|
| Filas / elegibles | 1 / 1 |
| Cobertura histórica | 60 s |
| Paquetes | 44 |
| Consultas DNS | 22 |
| `packet_rate_10s` | 4.4 |
| `byte_rate_10s` | 374.8 |
| `mean_ip_len_10s` | 85.18181818 |
| `large_ip_ratio_10s` | 0.0 |
| `dns_nxdomain_ratio_60s` | 0.09090909 |

El ratio NXDOMAIN coincide exactamente con `2/22`. No se atribuyen señales L3/L4 que este perfil no ejercitó.

## Integridad raíz

```text
manifest.json          3c0037dbc009b21b677e50eb7acd468009680d4caf062765eab4e2999a9f9ccf
capture.pcap0          2f72f38e96f584413290cfd2edf199621e00885b4a7d8f94ca476dfe8d5b6fcb
multilayer-v1.csv      edd3bc7d0643d0187e78e01ecb335a9cced412825fd4c5e88821bdfd3534e1f8
extraction-report.json b337232d27efd6b99f0c627d4bc6f219eaa2d951ea94117fd1744e151c0a7537
ledger                 6604d04c42ef4efa18fb1dcbe28e4c439c30cf82e2da5a576e9e9c262fb60856
```

Los PCAP, EVE, CSV y logs permanecen fuera de Git en el volumen dedicado.

## Resultado del ensamblador

La auditoría posterior reportó:

```text
accepted_campaigns=1
invalid_campaigns=0
campaign_warnings=0
missing_cells=144
ready_to_build=false
```

La celda aceptada es `DNS-MIXED-20-2/R01/train`. El ensamblador no produce todavía `train.csv`: exige las 145 celdas completas.

## Revisión adversarial

Se solicitaron revisiones de preflight y del bundle a Claude Code. Ambas ejecuciones finalizaron sin emitir contenido, por lo que no se registra una aprobación inexistente. Codex aplicó los gates automatizados, verificó hashes, cruzó manifiesto/ledger/reporte, contó EVE y ejecutó el ensamblador.

## Decisión

**CANARIO ACEPTADO.** Se valida el pipeline oficial completo para un perfil DNS corto: planificación, captura, EVE, métricas, integridad, extracción, ledger y aceptación del ensamblador.

Esto no autoriza ejecutar las 144 campañas restantes en lote. El siguiente perfil recomendado es `HTTP-10MB/R01`: es acotado, ya fue calibrado y debe demostrar tráfico legítimo pesado de 500–1500 bytes con cero drops. Antes de ejecutarlo se repetirá el preflight y se revisará el bundle de forma independiente.

> **Seguimiento:** `HTTP-10MB/R01` fue ejecutado y aceptado con 91.6077 % de paquetes IPv4 entre 500 y 1500 bytes y cero drops. La evidencia está en `07-canario-HTTP-10MB-F1.md`.
