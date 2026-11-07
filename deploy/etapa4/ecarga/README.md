# E-carga v2: guiones de preparación, muestreo y derivación (ubicación canónica)

**Estado: PREPARADO. E-carga NO se ha ejecutado ni programado.** Ejecutarla exige una autorización posterior y explícita
de Mark. Nada de esta carpeta arranca generadores por sí solo, ataca, activa restricciones ni toca el modelo IF,
las 28 características, α, los heurísticos o la política de respuesta.

Esta carpeta es la **única** copia de trabajo del código. El repositorio de documentación solo referencia el commit y
los sha256 (ver `SHA256SUMS`). Las copias `guiones-c7f24510/` y `evaluacion-e83f4be6/` del repo de documentación
quedan como evidencia sellada **sustituida**: no se usan.

| Fichero | Versión | Dónde corre | Qué hace |
|---|---|---|---|
| `generadores.sh` | 2026-11-06.2 | clientes (por ssh desde el bastión, entra por stdin) | `estado`, `permisos`, `configuracion`, `arrancar`, `parar`, `comprobar-parado`; rc 0/2/3/4/5 inequívocos |
| `muestreo_bastion.sh` | 2026-11-07.1 | bastión | muestreo cada 30 s y guardia §3.7; parada con estados solicitada/fallida/confirmada/agotada/reabierta; no sale del bucle sin intentar la parada ni sin comprobarla; `DIR/RESULTADO-PARADA`; rc 4 si no se confirma. Modo seco: ninguna orden |
| `arrancar_c1.sh` | 2026-11-07.2 | bastión | paso C1: espera a T_g y, dentro del cerrojo `ordenes.lock`, pasa la puerta, relee la hora y emite `arrancar`; al volver, relee y para si hace falta; rc 0/2/3/4 |
| `puerta_c1.py` | 2026-11-07.1 | bastión | decide C1: muestreador vivo, ninguna solicitud de parada y lectura de la guardia válida y reciente (<= 60 s). No añade condiciones a §3.7 |
| `guardia.py` | 2026-11-06.2 | bastión | condiciones de parada §3.7; avisa `SIN_LECTURA` |
| `sensor1_muestreadores.sh` | 2026-11-06.4 | Sensor1 | `comprobar` (anillo ≥ 900 s, PSI, vmstat, diskstats, USER_HZ), `arrancar`/`parar` de los 4 muestreadores (con S14). 2026-11-06.3: `comprobar` ya no escribe en el paquete (`python3 -I -B` en la consulta de VERSION y en `obs_pcap --en-seco`; la .2 dejaba `__pycache__/evaluar_ecarga.cpython-312.pyc`). 2026-11-06.4: los muestreadores en marcha se identifican por el argv de `/proc/<pid>/cmdline` (intérprete python + guion `muestreo_fino.py`, `obs_pcap.py`, `muestreo_s14.py` o `salud_captura.py muestrear`), no con `pgrep -af`, que coincidía con el propio intérprete al ejecutarse como `bash -c "$txt"`; tres estados: ausencia confirmada, presencia y DESCONOCIDO (nunca aprobado) |
| `muestreo_s14.py` | 2026-11-06.1 | Sensor1 | lectura a 1 s de PSI, /proc/stat, softnet, diskstats, MemAvailable, vmstat e hilos W# de Suricata |
| `sensor1_post.sh` | 2026-11-06.2 | Sensor1 | `DIR DESDE HASTA BASE_DESDE BASE_HASTA`: deriva S2/S3 (con `obs_pcap.log`) y S14 (con línea base) y sella |
| `derivar_pcap.py` | 2026-11-06.2 | Sensor1 / portátil | S2 y S3 con cobertura de bordes, continuidad y lectura completa |
| `evaluar_s14.py` | 2026-11-06.2 | Sensor1 / portátil | S14 según PROTOCOLO-CARGA-v2 r3 §3.6.1 y tiempo desconocido según r4 §3.6.1.1 (línea temporal S/N/U; posible episodio con datos ausentes = `null`) |
| `derivar_bastion.py` | 2026-11-06.2 | portátil | S1, S6, S8, S9, S10; `ERROR` -> sin medida |
| `derivar_s7.py` | 2026-11-07.1 | bastión | S7 desde las trazas y las muestras: `true` solo con entregas, recepciones y secuencia respaldadas; lista vacía, una lectura o lectura fallida -> `null`; incumplimiento observado -> `false` |
| `s7_post.sh` | 2026-11-07.1 | bastión | paso D4: copia las trazas y deja `s7.json` |
| `construir_entrada.py` | 2026-11-07.1 | portátil | entrada de `../sensor1/evaluar_ecarga.py veredicto` (2026-11-06.4, sin cambios); S14 y S7 ya no son manuales; exige `evaluar_s14 2026-11-06.2` y `derivar_s7 2026-11-07.1` |

Pruebas aisladas: `tests/test_etapa4_ecarga_prep.py` con los dobles de `tests/ecarga_banco/bin` (systemctl, sudo, ssh,
curl, nft, pgrep). Las pruebas `*regresion*` fallan con la versión que corrigen y pasan con esta: las de arranque,
parada, lecturas y PCAP con `c7f24510`/`e83f4be6`; las de S14 con tiempo desconocido con `a12deae`
(`evaluar_s14 2026-11-06.1`, que no contaba el hueco inmediatamente anterior al primer par saturado).

`tests/test_etapa4_ecarga_guardia_s7.py` cubre C1, la parada al salir del bucle y S7, con reloj simulado (`date` y `sleep`
del banco); sus pruebas `*regresion*` fallan con `975e715`. `tests/reproducir_ecarga_guardia_s7.py` imprime el antes y el
después. Todo esto son dobles: no demuestra el comportamiento en los hosts.

**Los hosts conservan `paquete-902991e`**, que no se edita. Los cambios de 2026-11-07.1 y .2 solo corren en el bastión y llegan
en una carpeta aparte, con un traslado que necesita su propia autorización.
