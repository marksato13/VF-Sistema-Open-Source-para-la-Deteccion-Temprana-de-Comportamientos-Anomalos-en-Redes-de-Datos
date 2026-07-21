# Generador benigno F1

`run-benign.sh` se ejecuta exclusivamente en VM05 Cliente. Obliga a declarar bitrate y duración, y rechaza valores fuera de la matriz calibrada.

Ejemplos:

```bash
./run-benign.sh http 100MB 20M
./run-benign.sh https 500MB 20M
./run-benign.sh dns-valid 20
./run-benign.sh dns-nxdomain 20
./run-benign.sh iperf-tcp 100M 10
./run-benign.sh iperf-udp 25M 10
```

No ampliar los valores permitidos hasta medir deltas de `kernel_drops`, `decoder.invalid` y `alert_queue_overflow`. La salida JSON de iperf3 se conserva fuera de Git junto con el manifiesto de campaña.

La calibración G2 fijó máximos de 200 Mbit/s para TCP y 50 Mbit/s para UDP. Valores superiores quedaron excluidos del ejecutor de producción.

En HTTP/HTTPS el tercer argumento limita bytes por segundo. Para pruebas individuales se admite hasta `20M`; en pruebas concurrentes la suma de todos los flujos no debe superar `20M` sin una nueva calibración.
