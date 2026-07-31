# Decimoséptimo canario oficial R03 — HTTP-MULTI-1

Fecha: 31 de julio de 2026. Campaña: `F1N-HTTP-MULTI-1-R03`. Estado: **ACEPTADA CON LIMITACIONES**.

## Objetivo y preflight

Una solicitud HTTP legítima y secuencial a cada VIP DMZ: `10.30.0.10`, `.11` y `.12`. El perfil aporta diversidad de direcciones L3 observable; las tres VIP pertenecen a una sola VM Servidor y no representan tres hosts físicos, enlaces o dominios de fallo independientes.

El dry-run fijó Git limpio y sincronizado en `991f636bf67926515fac54bd1b1ea963c7c2fb1f`, propósito `experiment`, partición `train`, estrato `multi-destination` y argumento `1`. ID/feature/ledger/lock estaban libres, había 130,871,418,880 bytes disponibles y el volumen oficial más la reserva pasaron.

NTP pasó en VM01 más las cuatro VM, con desfase absoluto máximo de 0.906 ms. Las cuatro VM respondieron por SSH; las tres VIP estaban en `ens38` y devolvieron HTTP 200 desde el Cliente. Servicios relevantes, rutas por el Sensor, NIC externas `DOWN`, captura inactiva, generador, contadores Suricata y bloqueo del bypass `.111–.114` pasaron. `iperf3` estaba inactivo, pero no participa en este escenario HTTP y no es un gate aplicable.

Las solicitudes de preflight ocurrieron antes de los 70 s de quietud y del checkpoint oficial. El warm-up capturado de 60 s y settle de 9 s son etapas distintas. Claude/Sonnet autorizó una única ejecución.

| Campo | Valor |
|---|---|
| Escenario / argumento | `http-multi` / `1` |
| Quietud / warm-up / settle / cooldown | 70 / 60 / 9 / 30 s |
| SHA matriz | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| SHA argumentos | `43de3a417d75f4818c5a553268b80ce3a5805109a3bbc6b605e9fb0b8f50b485` |
| SHA generador local/remoto | `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203` |

## Conteos exactos e integridad

El Cliente produjo exactamente tres líneas: `request=1,http_code=200` para `.10`, `.11` y `.12`; stderr quedó vacío.

| Control | Resultado |
|---|---:|
| PCAP archivos / bytes | 1 / 3,369 |
| Capturados / recibidos / parseados | 30 / 30 / 30 |
| Drops tcpdump | 0 |
| Transferencia / límite PCAP | verificada / no alcanzado |
| EVE esperado / extraído | 15 / 15 |
| `stats` / HTTP / `fileinfo` | 9 / 3 / 3 |
| Delta Suricata / PCAP | 30 / 30 |
| Drops / ifdrops / decoder / overflow | 0 / 0 / 0 / 0 |

El PCAP contiene tres conexiones TCP completas mediante tres puertos origen distintos, una por VIP. El segmento EVE contiene exactamente un GET `/health` HTTP/1.1 con estado 200 y longitud 36 para cada destino. Los tres `fileinfo` están `CLOSED`, `gaps=false`, `stored=false` y `size=36`. Sus timestamps coinciden con la ejecución oficial y no hay transacciones adicionales del preflight.

R01 y R02 tuvieron diez eventos periódicos `stats`; R03 tuvo nueve. La diferencia temporal no implica una pérdida de tráfico de aplicación: los tres HTTP y tres `fileinfo` esperados están completos, y el checkpoint `complete_same_inode` coincide 15/15.

Los treinta paquetes son menores de 500 bytes, con media IPv4 81.50 y máximo 251. El 0 % en 500–1500 bytes es propio de tres health checks pequeños y no aporta cobertura de tráfico pesado.

## Feature y repetibilidad R01↔R02↔R03

R03 produjo una fila elegible:

| Paquetes | Attempts / SYN / HTTP | Packet / byte rate | IP ratio | Port ratio | SYN completion | HTTP error |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 3 / 3 / 3 | 3.0 p/s / 244.5 B/s | 1.0 | 0.33333333 | 1.0 | 0 |

`unique_dst_ip_ratio_30s=3/3` prueba tres direcciones destino observadas, no tres hosts físicos ni tres muestras independientes. `unique_dst_port_ratio_30s=1/3` refleja un único puerto para los tres intentos.

Las tres repeticiones tienen 30 paquetes, 3,369 bytes, tres HTTP 200, tres `fileinfo`, una fila y exactamente las mismas 14 features, excluyendo identidad y tiempo. Sus PCAP, EVE, puertos origen, timestamps y hashes son distintos, por lo que la coincidencia representa repetibilidad de un generador determinista de baja entropía, no reutilización de evidencia.

R01/R02 registraron 16 eventos EVE y deltas Suricata de 34/32 frente a 30 paquetes; R03 registró 15 y delta 30/30. Los alcances de los contadores no se convierten en porcentajes ni se usan para atribuir causalidad.

El duplicado exacto elevó el contador global dentro de `train` de doce a trece. Añade peso a esta firma sin diversidad estadística nueva; no se elimina automáticamente, pero deberá considerarse en el análisis agregado y la evaluación posterior. Validation/test aún no existen.

El Sensor produjo 53 muestras: CPU máxima 1.51 %, RSS máximo 781,768 KiB, memoria disponible mínima 14,073,696 KiB y carga máxima 0.32. Son observaciones sin umbrales definidos de presión o capacidad.

## Integridad raíz

```text
manifest.json          517fbfa5d2d460035f218ecbfb130c055c1c97209bc4599d4c15a245111c114e
capture.pcap0          8f16b583fd9afa8f004e35afc9df53decb7e903801d26507996998fe20dbbb79
eve-slice              3fcefd0a3b0d1c6ad02633ed552e7ff77ecefdc79659a0ee49487ef9a23348a6
campaign SHA256SUMS    1bbae82d88dcb6c153d1b92d46ce2d03fe33566feb77ee8d0abf6b5dae0afe69
multilayer-v1.csv      30e02bb0d5625b5b111eb732c84c3067b5997534e89cd11cfb240c3443c429ab
extraction-report      fbba3c0bd5152cdd90a41d4b5e617d4b4b902104c0eeceafbb6610608d5a41b5
feature SHA256SUMS     da1e483abe0775303492b5c1edb05e0beb026c1bea744f3e3171921bf91aa3b5
ledger                 67676e982cff6bf160d073b3648367cbf0a243dd734f4ba277ed410e03d13f7b
```

El primer intento de auditoría global omitió `PPI_ARTIFACTS_ROOT`, inspeccionó el directorio local vacío y devolvió 0/145. Se descartó inmediatamente porque no apuntaba al volumen oficial y no modificó evidencia. La auditoría corregida y explícita sobre `/srv/ppi-evidence/artifacts` aceptó 75/145 campañas: R03 17/29, 70 faltantes, cero inválidas/advertencias, trece coincidencias exactas dentro de `train` y cero entre particiones.

Claude/Sonnet emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `HTTP-MULTI-5/R03`. Conservó los límites sobre VIP lógicas, episodio único, duplicado exacto, `stats` periódico y ausencia de validation/test.

**F1N-HTTP-MULTI-1-R03 ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTP-MULTI-5-R03`; no su ejecución.
