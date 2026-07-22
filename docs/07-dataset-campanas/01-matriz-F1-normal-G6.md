# Matriz F1 de normalidad representativa — G6

> **Seguimiento:** el volumen dedicado resolvió el gate de capacidad y el primer canario oficial `F1N-DNS-MIXED-20-2-R01` fue aceptado. Quedan 144 celdas; ver `06-primer-canario-oficial-F1.md`.

Fecha de congelación del diseño inicial: 21 de julio de 2026. Contrato oficial vigente: `configs/campaigns/f1-normal-v2.json`. La versión `v1` permanece inmutable para reproducir los cuatro pilotos anteriores, pero fue sustituida antes de iniciar campañas oficiales para incorporar diversidad legítima de destinos.

## Decisión actual

**G6 está listo para piloto, pero no está aprobado para recolección completa.** La matriz ya es versionada, validable y ejecutable perfil por perfil. Aún faltan la validación empírica de todos los generadores, ampliar el almacenamiento/definir archivado y resolver dos huecos de diversidad. No se debe entrenar un modelo final con calibraciones ni con una F1 incompleta.

## Objetivo experimental

F1 construye la distribución de normalidad que verá Isolation Forest. Incluye transferencias legítimas pesadas, errores operativos benignos y concurrencia segura para evitar la regla errónea «paquete grande = ataque». Los techos provienen de G2: TCP 200 Mbit/s, UDP 50 Mbit/s y HTTP/HTTPS 20 MiB/s agregados. Los perfiles que alcanzan esos límites siguen siendo benignos porque no produjeron pérdida del Sensor durante calibración.

Cada campaña usa:

- 60 s de warm-up para completar las ventanas causales de 60 s;
- 9 s de asentamiento antes de cerrar captura;
- 30 s de cooldown entre ejecuciones oficiales;
- PCAP completo, segmento EVE, métricas del Sensor, inventario, manifiesto y hashes;
- extracción `multilayer-v1` inmediatamente después de cerrar la campaña.

## Estratos y perfiles

| Estrato | Perfiles | Propósito |
|---|---|---|
| DNS normal/error legítimo | `DNS-VALID-10`, `DNS-VALID-200`, `DNS-MIXED-20-2`, `DNS-MIXED-50-10` | establecer tasa normal y NXDOMAIN benigno bajo |
| ICMP | `PING-10`, `PING-100` | cubrir ICMP esporádico y ráfaga legítima |
| HTTP | 10 MB, 100 MB, 500 MB y 1 GB | cubrir tamaños pequeños y paquetes grandes legítimos |
| HTTPS | 10 MB, 100 MB, 500 MB y 1 GB | repetir carga pesada con cifrado y sesiones TLS |
| Error HTTP/TLS | `HTTP-404-5`, `TLS-SESSIONS-20` | impedir que todo 404 o recambio TLS sea anomalía por sí solo |
| HTTP multidestino | 1 y 5 solicitudes por cada IP `.10`, `.11` y `.12` | variar de forma legítima el ratio de IP destino |
| Concurrencia HTTP | 2, 4 y 8 flujos; agregado máximo 20 MiB/s | modelar usuarios concurrentes sin sobrepasar G2 |
| TCP rechazado | cinco conexiones a puerto cerrado | producir SYN/RST benignos y controlados |
| Throughput TCP | 50, 100 y 200 Mbit/s durante 20 s | rango normal pesado hasta el máximo seguro |
| Throughput UDP | 10, 25 y 50 Mbit/s durante 20 s | rango normal UDP hasta el máximo seguro |
| Mezcla legítima | HTTP + TCP + DNS | interacción entre servicios sin Kali |

Son 29 perfiles con cinco repeticiones: **145 campañas**. El JSON contiene los argumentos exactos y una estimación conservadora por PCAP; no se aceptan parámetros libres.

## Partición sin fuga

La partición es previa a la captura y se hace por campaña completa, nunca por filas o ventanas:

| Repetición | Partición | Uso |
|---|---|---|
| R01–R03 | `train` | ajuste de Isolation Forest solo con normalidad F1 |
| R04 | `validation` | selección de umbral y falsos positivos normales |
| R05 | `test` | evaluación normal retenida; no ajustar hiperparámetros |

Todas las ventanas derivadas de una campaña heredan su partición. Los pilotos usan `purpose=calibration` y `partition=excluded_calibration`; aunque una fila tenga historia suficiente, no entra a ningún split.

F2 y F4 serán pruebas de generalización fuera de F1. Esta separación evita presentar como generalización una simple división aleatoria de ventanas casi idénticas.

## Gate de almacenamiento

Medición de VM01 al congelar la matriz:

| Concepto | Bytes | Aproximado |
|---|---:|---:|
| espacio libre local | 53,925,744,640 | 50.22 GiB |
| PCAP estimado de F1 | 33,673,250,000 | 31.36 GiB |
| libre estimado al terminar | 20,252,494,640 | 18.86 GiB |
| reserva mínima exigida | 21,474,836,480 | 20.00 GiB |
| requerido PCAP + reserva | 55,148,086,480 | 51.36 GiB |

Resultado: `storage_gate_pass=false`. Además, VM02 conserva temporalmente otra copia de cada PCAP y todavía falta dimensionar features, índices, F2–F4 y respaldo. Las estimaciones no son una autorización para llenar la raíz.

Antes de la campaña oficial se debe elegir y probar una de estas opciones:

1. añadir a VM01 un disco de evidencias de al menos 100 GiB útiles, montado en una ruta dedicada; o
2. ejecutar por lotes con verificación SHA-256, copia a almacenamiento externo y borrado remoto mediante un procedimiento de retención aún por implementar.

La primera opción es preferible para la defensa porque preserva originales y reduce operaciones manuales. El ejecutor bloquea campañas oficiales mientras falle el gate global; los pilotos acotados sí pueden ejecutarse.

## Cobertura de las 14 features

La matriz declara perfiles para las 14 variables L3/L4/L7, pero esa declaración no sustituye la verificación estadística. Después de cada estrato se comprobarán soporte, rango, nulos, varianza y diferencias entre repeticiones.

- L3: volumen, tamaños, ICMP y baseline de destino.
- L4: intentos de flujo, SYN, completitud, RST y diversidad de puerto.
- L7: 404 benigno, NXDOMAIN benigno y recambio de sesiones TLS.

La cobertura pesada incluye 10 MB–1 GB, concurrencia y throughput. G6 solo pasará si una proporción sustancial de paquetes IP cae entre 500 y 1500 bytes sin pérdida de captura y sin convertir ese tamaño en etiqueta.

## Huecos conocidos y acciones

1. **Diversidad L3 lógica, no física.** `v2` incorpora `10.30.0.10`, `.11` y `.12` como servicios persistentes de VM03. Esto amplía el ratio de destinos, pero no simula tres hosts ni tres fallos independientes; esa limitación debe mantenerse en la defensa.
2. **SSH/SFTP pendiente.** No se usará una contraseña en scripts. Debe crearse una identidad técnica exclusiva, datos no sensibles y límites de transferencia antes de añadir el perfil.
3. **Retención pendiente.** Sensor y VM01 guardan copias; no existe todavía eliminación remota automatizada ni backup verificado.
4. **Duración real pendiente.** El mínimo teórico supera cuatro horas por warm-up/cooldown y carga. Transferencia, validación y extracción de PCAP pueden elevarlo; se medirá en pilotos antes de reservar la ventana oficial.

Estos huecos impiden declarar G6 `PASS`, pero no impiden probar de forma segura el contrato y un perfil corto.

## Comandos reproducibles

Validar estructura, cobertura y capacidad:

```bash
python3 scripts/f1/validate_matrix.py
python3 scripts/f1/validate_matrix.py --require-storage
```

Simular un único perfil:

```bash
python3 scripts/f1/run_matrix_profile.py \
  --profile DNS-MIXED-20-2 --repetition 1 --pilot --dry-run
```

Ejecutar el piloto, después de desplegar el generador y con Git limpio:

```bash
python3 scripts/f1/run_matrix_profile.py \
  --profile DNS-MIXED-20-2 --repetition 1 --pilot --no-cooldown
```

No existe una opción `--all`. Lanzar toda la matriz requiere una decisión explícita posterior a los gates de almacenamiento, diversidad y pilotos.
