# Revisión Claude — HTTPS-500MB R03

Fecha: 31 de julio de 2026. Claude Code 2.1.217, modelo Sonnet.

## Autorización previa

Claude evaluó el preflight y autorizó **EJECUTAR UNA VEZ**, condicionado a cero drops y revisión posterior. Se corrigió su afirmación `NTP 4/5`: el gate pasó en VM01, Sensor, Servidor, Kali y Cliente; SSH pasó en las cuatro VM.

Claude presentó `<100 ms` como umbral histórico no documentado. En realidad el valor sí está versionado directamente en `scripts/f1/check_ntp_gate.sh` como máximo absoluto predeterminado de `0.1 s`; no se adopta como inferencia de campañas anteriores.

## Dictamen final

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó únicamente el preflight independiente de `F1N-HTTPS-1GB-R03`.

Ratificó 500 MiB completos, dos PCAP íntegros, cero drops, 362,957 paquetes en el rango objetivo, TLS 1.3, tres filas correlacionadas, hashes válidos, delta Suricata +4 sin causa y ausencia todavía de validation/test.

Se corrigieron:

- el máximo de calibración iperf3 TCP de 200 Mbit/s no es gate de este perfil HTTPS;
- los hashes permiten afirmar integridad verificada bajo el contrato, no una “cadena de custodia intacta” universal;
- CPU/RSS/memoria/carga son observaciones sin umbrales para declarar “sin presión”;
- el dictamen final negó que existiera un umbral NTP fijo, pero el script versionado fija `0.1 s`;
- cero cruces observados no equivale a validar contaminación futura: validation/test aún no existen.

No se adoptan causas, tolerancias, resultados ML ni garantías de determinismo.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Siguiente autorizado: solo preflight independiente de `F1N-HTTPS-1GB-R03`; no su ejecución.
