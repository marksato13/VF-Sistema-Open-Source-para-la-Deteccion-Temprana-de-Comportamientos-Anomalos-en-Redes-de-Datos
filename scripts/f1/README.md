# Generador benigno y matriz F1

`run-benign.sh` se ejecuta exclusivamente en VM05 Cliente. Obliga a declarar bitrate y duración, y rechaza valores fuera de la matriz calibrada.

Ejemplos:

```bash
./run-benign.sh http 100MB 20M
./run-benign.sh https 500MB 20M
./run-benign.sh dns-valid 20
./run-benign.sh dns-nxdomain 20
./run-benign.sh dns-mixed 20 2
./run-benign.sh ping 100 0.2
./run-benign.sh http-concurrent 4 100MB 5M
./run-benign.sh http-multi 1
./run-benign.sh http-missing 5
./run-benign.sh https-sessions 20
./run-benign.sh tcp-refused 5
./run-benign.sh iperf-tcp 100M 10
./run-benign.sh iperf-udp 25M 10
./run-benign.sh mixed-light
```

No ampliar los valores permitidos hasta medir deltas de `kernel_drops`, `decoder.invalid` y `alert_queue_overflow`. La salida JSON de iperf3 se conserva fuera de Git junto con el manifiesto de campaña.

La calibración G2 fijó máximos de 200 Mbit/s para TCP y 50 Mbit/s para UDP. Valores superiores quedaron excluidos del ejecutor de producción.

En HTTP/HTTPS el tercer argumento limita bytes por segundo. Para pruebas individuales se admite hasta `20M`; en pruebas concurrentes la suma de todos los flujos no debe superar `20M` sin una nueva calibración.

## Ejecución versionada

La fuente oficial de perfiles es `configs/campaigns/f1-normal-v2.json`. `v1` se conserva únicamente para reproducir los cuatro pilotos anteriores. El ejecutor acepta exactamente un perfil y una repetición para impedir el lanzamiento accidental de toda la matriz:

```bash
python3 scripts/f1/validate_matrix.py
python3 scripts/f1/run_matrix_profile.py \
  --profile DNS-MIXED-20-2 --repetition 1 --pilot --dry-run
```

Una campaña definitiva elimina `--pilot`. Exige árbol Git limpio y que el almacenamiento soporte la matriz completa más la reserva declarada. Cada manifiesto registra el hash SHA-256 de la matriz, el perfil y la repetición.

`--no-cooldown` solo existe para pilotos. No se permite en recolección oficial porque una campaña no debe contaminar temporalmente a la siguiente.

Las campañas oficiales esperan además 70 segundos de quietud **antes** de abrir el checkpoint EVE y comenzar el PCAP. Este margen drena eventos `flow` que Suricata puede emitir por timeout después de una comprobación de preflight ya cerrada. El valor queda en el ledger como `pre_capture_quiet_seconds`; no sustituye los 60 segundos de warm-up capturado ni los 30 segundos de cooldown posterior. Los pilotos conservan quietud cero.

La quietud no silencia tráfico periódico que nazca durante esos 70 segundos, por ejemplo control IPv6 link-local del propio Sensor. EVE se conserva sin borrar esos registros; el auditor debe distinguir eventos fuera de alcance y confirmar que el extractor solo utilice tipos y entidades previstos.
