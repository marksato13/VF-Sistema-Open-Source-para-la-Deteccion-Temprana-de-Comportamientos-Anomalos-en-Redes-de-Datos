# Calibración del búfer PCAP para HTTP-C8

Fecha: 23 de julio de 2026. Campaña: `CAL-G6-HTTP-C8-R01`. Commit: `e3122fd15dbc06f90eb6a635e4130a6df1d77248`.

## Objetivo

Esta calibración intenta refutar una sola hipótesis surgida del intento oficial rechazado `F1N-HTTP-C8-R01`: que el búfer de 4 MiB de `tcpdump` fue insuficiente para absorber ráfagas o pausas de escritura.

Solo cambiaron:

- `tcpdump -B 4096` → `-B 65536`;
- `net.core.rmem_max=4194304` → `67108864`.

La rotación siguió en 512 MB × 4, el límite nominal continuó en 2.048 GB y se conservaron perfil, matriz, topología, generador, archivo, filtro, snaplen y Sensor.

## Separación del dataset

| Campo | Valor |
|---|---|
| Propósito | `calibration` |
| Partición | `excluded_calibration` |
| Estado | `completed` |
| Evidencia completa | `true` |
| Filas extraídas | 6 |
| Filas con historia suficiente | 6 |
| Elegibles para F1 | **No: anti-calibración** |

`eligible_training_rows=6` solo indica historia temporal y valores válidos dentro del extractor. El ensamblador vuelve a evaluar propósito y partición, por lo que estas ventanas no pueden ingresar a `train`, `validation` o `test`.

## Resultado funcional

Las ocho descargas HTTP 200 completaron 838,860,800 bytes en aproximadamente 49.52 s. La suma de velocidades fue 135.549048 Mbit/s y bytes sobre el mayor tiempo 135.527895 Mbit/s.

| Control | Resultado |
|---|---:|
| `buffer_kib` registrado | 65,536 |
| Rotación | 512 MB × 4 |
| PCAP capturado/recibido | 605,266 / 605,266 |
| Drops `tcpdump` | **0** |
| PCAP parseado | 605,266 |
| Archivos / bytes | 2 / 889,216,132 |
| Tamaños | 512,001,310; 377,214,822 bytes |
| Transferencia y SHA remoto/local | PASS |
| Límite alcanzado | No |
| Delta Suricata | 605,272 paquetes |
| Drops/ifdrops Suricata | 0 / 0 |
| Decoder invalid / overflow | 0 / 0 |
| EVE esperado/extraído | 38 / 38 |
| Muestras / stderr Sensor | 123 / vacío |

EVE contiene 22 `stats`, ocho `http` y ocho `fileinfo`. Todos los HTTP devolvieron 200. El límite `fileinfo=102400/TRUNCATED` permanece como límite de inspección y no indica una transferencia incompleta.

## Paquetes y recursos

De 605,266 paquetes IPv4, 580,001 —95.8258 %— midieron entre 500 y 1500 bytes; 579,372 midieron exactamente 1500 bytes. La longitud media fue 1,439.13 bytes y la máxima 1,500.

Suricata registró un máximo puntual de 61.71 % en la métrica del proceso, RSS máxima de 780,020 KiB, memoria disponible mínima de 13,580,948 KiB y carga máxima 0.46. La métrica de CPU no es porcentaje del total de seis vCPU ni un gate formal.

## Integridad raíz

```text
manifest.json          fefdcf5a86f9a9261bad0b729998bdf755a685bac6b95c001715f1d735368b67
capture.pcap0          8f4039a158b5b33557a51eb6a254ac387fad4e0beb1129497c57826649331c2c
capture.pcap1          11073d346204daf845f55ae380cacf0ea148b544311096691cbabeb508e94c6d
eve-slice              3bd6ad8e2a4979563e43f5b4348d62b781cf52c812c16a0f37ddfa1f89fce1f2
campaign SHA256SUMS    3d17b3959318a90584b27f73bd335bfc564b9f433183a2290e667a670fb0055d
multilayer-v1.csv      c292e7bb11e6cff01ca5721e3d4baea811efaa88e4730b807f7233e66cdb858b
extraction-report      2c164e9b56045f07847795f2a918c8eada512361b7d69876add676cf0ad79e1f
feature SHA256SUMS     51ef8f97ed105330c29f952acd5934d3e0b000842ce548d38f609f7549f5bd1d
ledger                 42c00cd5784941a7e35a284ba40609fcfa103a95fc99282093159c7478cd5790
```

Todos los paquetes de hashes pasaron.

## Interpretación

Comparación controlada:

| Configuración | Recibidos | Drops | Resultado |
|---|---:|---:|---|
| Oficial, búfer 4 MiB | 597,180 | 476 | RECHAZADO |
| Calibración, búfer 64 MiB | 605,266 | 0 | PASS diagnóstico |

El resultado apoya que 64 MiB basta para este perfil bajo las condiciones observadas. Una sola calibración no demuestra ausencia futura de drops ni que la rotación sea óptima. Como la rotación actual pasó con cero drops, no se modificará antes del retry.

## Decisión

**CALIBRACIÓN DE BÚFER PASS Y EXCLUIDA.** Se autoriza preparar, pero no ejecutar automáticamente, el retry oficial.

Antes del retry:

1. versionar un procedimiento de archivado recuperable;
2. mover sin editar el bundle y ledger fallidos fuera de `campaigns/` y `g6-ledger/`;
3. verificar hashes en el archivo;
4. auditar el ensamblador: 15 aceptadas, 0 inválidas y 130 faltantes;
5. repetir preflight completo y ejecutar nuevamente el ID canónico `F1N-HTTP-C8-R01`.

El retry solo será aceptado con cero drops.
