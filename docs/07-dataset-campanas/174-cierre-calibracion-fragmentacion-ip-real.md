# Cierre de la calibración CAL-FRAG-UDP-01-R01 — fragmentación IP real

- **Fecha:** 2026-08-14
- **Ejecutor:** Claude, de forma manual y directa (no vía Codex), tras cuatro intentos fallidos delegados a Codex documentados en `173-calibracion-fragmentacion-ip-real.md` — todos bloqueados por causas del entorno del plugin de Codex (sandbox de red y una condición de carrera con D-Bus), no del laboratorio ni del código del proyecto.
- **Estado:** **ACEPTADA.** `fragment_ratio_10s` toma valores no nulos con evidencia real, cero drops, integridad verificada.

## Contexto: por qué se ejecutó manualmente

Los cuatro intentos de Codex (documentados en `173-...md`) fallaron todos en el preflight, nunca llegaron a abrir campaña ni generar tráfico. Diagnostiqué dos causas reales y distintas en el entorno de Codex (no en el laboratorio):

1. El sandbox `workspace-write` de Codex bloqueaba red saliente y fallaba al leer `/etc/ssh/ssh_config.d/` — corregido con `.codex/config.toml` (commit `fe4abe6`) y `-F /dev/null` en las conexiones SSH.
2. Con esos dos fixes aplicados, el gate NTP siguió fallando específicamente dentro del runtime de tarea/rescate de Codex (`Failed to connect to system scope bus via local transport`), sin que yo pudiera reproducirlo fuera de ese contexto ni diagnosticarlo más sin acceso root (`dmesg`/auditoría AppArmor).

Autorizado por el usuario a ejecutar esta calibración directamente, sin pasar por Codex, dado que el bloqueo era del entorno del plugin, no del proyecto.

## Hallazgo adicional durante la ejecución manual: bug real de locale en `check_ntp_gate.sh`

Al correr el gate NTP yo mismo, encontré una causa real (no relacionada con Codex) de un falso negativo en la validación de Kali: `check_timesyncd()` convierte el offset de `timedatectl timesync-status` a segundos con `awk 'BEGIN {printf "%.12f", ...}'`. Bajo el locale activo en VM01 (`LC_NUMERIC=es_ES.UTF-8`), `awk` imprime el separador decimal como coma (`-0,000786000000`), y la regex de validación posterior (`^[+-]?[0-9]+([.][0-9]+)?$`) exige punto — produciendo el falso error `offset NTP inválido en kali` pese a que Kali estaba correctamente sincronizado (offset real: -786 µs, muy por debajo del límite de 0.1 s).

**Corrección aplicada:** `export LC_ALL=C` al inicio de `scripts/f1/check_ntp_gate.sh`. Verificado: el gate pasa limpio para los 5 hosts (`vm01=0.001531782`, `sensor=0.000012845`, `server=0.000002409`, `kali=-0.000786000000`, `client=0.000006506`, `NTP_GATE=PASS`). Este bug solo afecta a hosts validados vía `check_timesyncd()` (actualmente solo Kali, ya que Sensor/Servidor/Cliente usan `chronyc`, cuyo formato de salida no pasa por el `printf` de `awk`). Es un bug preexistente del script, no introducido por esta tarea; probablemente explica intermitencias de gate NTP no diagnosticadas en corridas anteriores donde el locale del shell no era `C`.

## Ejecución

1. Verifiqué hashes del dataset congelado antes de empezar (sin cambios al terminar, ver abajo).
2. Confirmé que `scripts/f1/run-benign.sh` (repo) tenía el escenario `frag-udp` agregado por Codex en un intento anterior — revisado y aceptado previamente, sin cambios adicionales aquí.
3. Encontré que la copia desplegada en VM05 (`/home/useransible/bin/ppi-run-benign`) estaba desactualizada (sin `frag-udp`) — la re-desplegué desde el repo (`cat | ssh ... > archivo temporal + mv atómico`), verifiqué diff idéntico, validé sintaxis remota (`bash -n`) y el rechazo negativo (`frag-udp 1500 10` → `ERROR: longitud UDP permitida: 2000 o 3000 bytes`, exit 2, sin generar tráfico).
4. Verifiqué estado de Suricata en el Sensor (`service_state=active`, cero drops/decoder_invalid/alert_queue_overflow) y espacio libre (105 GiB) antes de abrir campaña.
5. Abrí la campaña: `PPI_ARTIFACTS_ROOT=/srv/ppi-evidence/artifacts PPI_CAMPAIGN_PARTITION=excluded_calibration scripts/campaign/start.sh CAL-FRAG-UDP-01-R01 F2 frag-udp udp-fragmentation calibration`.
6. Ejecuté el escenario una sola vez desde VM05: `/home/useransible/bin/ppi-run-benign frag-udp 3000 10` hacia `10.30.0.10` — iperf3 UDP, blksize 3000 (> MTU), 10 s, 5 Mbit/s. Advertencia esperada de iperf3: *"UDP block size 3000 exceeds TCP MSS 1448, may result in fragmentation / drops"*. Resultado: 6,252,000 bytes, 2,084 paquetes, 0% pérdida, exit code 0.
7. Cerré la campaña: `scripts/campaign/stop.sh CAL-FRAG-UDP-01-R01 0` → **`Estado: completed`** (el nivel más estricto: todos los gates de integridad automáticos pasaron).
8. Extraje features: `python3 scripts/features/extract_multilayer_v2.py --pcap .../capture.pcap0 --eve .../eve-slice.jsonl --campaign-id CAL-FRAG-UDP-01-R01 --output ... --pcap-start-json .../pcap-start.json --entity-network 10.20.0.0/24`.

## Evidencia e integridad

- PCAP: 1 archivo, 6,584,488 bytes, 6,281 paquetes capturados = 6,281 parseados (coincide exacto).
- Suricata (delta): `kernel_packets=2117`, `kernel_drops=0`, `kernel_ifdrops=0`, `decoder_invalid=0`, `alert_queue_overflow=0`, `counter_reset_detected=false`.
- EVE: 6 registros, slice coincide exacto con el checkpoint (`slice_matches_checkpoint=true`).
- Transferencia PCAP remoto→local verificada por hash (`pcap_transfer_verified=true`), sin alcanzar el límite de rotación (`pcap_limit_reached=false`).
- `manifest.json`: `evidence.complete=true`, `status=completed`.
- `SHA256SUMS` de la campaña calculado sobre los 20 archivos de evidencia (manifest, deltas, PCAP, EVE, inventarios, series temporales del Sensor, etc.) — ver `/srv/ppi-evidence/artifacts/campaigns/CAL-FRAG-UDP-01-R01/SHA256SUMS`.
- `git.commit` en el manifiesto: `fe4abe63202db75241bca49bbe6efaffce24d296`, `git.dirty=true` (esperado: hay cambios locales sin commitear de esta misma tarea — `run-benign.sh`, `common.sh`, `check_ntp_gate.sh` — es una calibración, no una campaña oficial, por lo que no se exige árbol limpio).

## Resultado: `fragment_ratio_10s`

Dos ventanas de 10 s producidas (`eligible_training_rows=0` en ambas — no califican para entrenamiento, es esperado y correcto ya que es evidencia de calibración, nunca se van a incorporar al dataset):

| Ventana (window_end_utc) | packet_count_10s | fragment_ratio_10s |
|---|---|---|
| 2026-08-14T18:16:20Z | 4732 | **0.99661877** |
| 2026-08-14T18:16:30Z | 1549 | **0.99160749** |

**Objetivo de la Tarea 3 cumplido:** `fragment_ratio_10s` deja de ser estructuralmente constante en 0.0 cuando existe tráfico IP genuinamente fragmentado en el PCAP. El extractor (`scripts/features/extract_multilayer_v2.py`, líneas ~230/595) funciona correctamente — la brecha era enteramente de generación de tráfico, como ya se había concluido en el análisis previo (`docs/06-features-modelado/05-diagnostico-pipeline-multilayer-v2.md`), no de código.

## Verificación de no contaminación

- Hashes del dataset congelado **antes y después**, idénticos:
  - `multilayer-v2-normal.csv`: `be8b71104bda5200a04ee77bdda5c3e164c5ed9a753bfc8c7dae9bb41003e99e`
  - `multilayer-v2-anomalies.csv`: `d8bf293d6427398c5091344397ec1aea3303f277cae32d0988a0dc164ada761a`
- `configs/campaigns/multilayer-v2-normal.json` **no modificado** — `frag-udp` no se agregó como perfil oficial; esta sigue siendo evidencia de calibración excluida (`purpose=calibration`, `partition=excluded_calibration`), pendiente de una decisión aparte sobre si se formaliza como perfil v2.1.
- Sin `git commit` ni `git push` de la evidencia de campaña (vive en `/srv/ppi-evidence/artifacts`, fuera de Git, como toda la evidencia runtime del proyecto).

## Cambios de código incluidos en este cierre

- `scripts/f1/run-benign.sh`: escenario `frag-udp` (agregado por Codex en un intento previo, revisado y aceptado).
- `scripts/campaign/common.sh`, `scripts/f1/check_ntp_gate.sh`: `-F /dev/null` en las conexiones SSH (agregado por Codex, alcance ampliado más allá de lo pedido inicialmente, revisado y aceptado — es un cambio mínimo, correcto, y necesario para que el sandbox de Codex pueda operar en el laboratorio en el futuro).
- `scripts/f1/check_ntp_gate.sh`: `export LC_ALL=C` (agregado por mí en esta sesión) — corrige el bug de locale descrito arriba, independiente de todo lo anterior.

## Siguiente paso

No se toma ninguna decisión aquí sobre incorporar `FRAG-UDP-V2` como perfil oficial en `configs/campaigns/multilayer-v2-normal.json` — eso queda pendiente de revisión aparte, junto con la calibración equivalente de TLS (Tarea 4, `CAL-TLS-HANDSHAKE-FAIL-01`, todavía no ejecutada).
