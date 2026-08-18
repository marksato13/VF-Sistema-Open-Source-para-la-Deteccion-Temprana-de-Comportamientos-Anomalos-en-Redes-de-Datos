# Preparación de R05 y preflight versionado

Fecha: 6 de agosto de 2026. Estado: **PREPARACIÓN APROBADA; CAPTURA R05 NO INICIADA**.

## Gate posterior a calibración

Después de publicar el congelamiento `PM-F1-v1` en `a86c562`, el agregador
oficial auditó la repetición R05 sin `--require-complete`. El estado fue el
esperado: 0/29 perfiles test, 116/145 campañas globales aceptadas, 29 faltantes
exactamente R05, cero inválidas, cero advertencias y Git limpio. `gate_pass=false`
significa repetición vacía, no defecto de R01–R04.

El dry-run de `DNS-VALID-10/R05` fijó:

| Campo | Valor |
|---|---|
| ID | `F1N-DNS-VALID-10-R05` |
| Propósito / partición | `experiment` / `test` |
| Escenario / argumentos | `dns-valid` / `10` |
| Matriz | `ad22ce5f…dfa824` |
| Argumentos | `6e32bc5b…496a60` |
| Warm-up / quietud / settle / cooldown | 60 / 70 / 9 / 30 s |
| Volumen oficial / capacidad | válido / válido |
| Commit del dry-run | `a86c562d9d8305162c6811d340f382068af5fe48` |

No se abrió checkpoint EVE, tcpdump, ledger, campaña ni score del modelo.

## Preflight continuo

Se versionó `scripts/f1/preflight_profile.sh` para sustituir bloques temporales
de terminal. Recibe exactamente un perfil y repetición, ejecuta nueve gates en
orden y publica un log sólo si todos pasan:

1. Git limpio y sincronizado con upstream;
2. dry-run de contrato, almacenamiento, split y ausencia de ID;
3. capacidad y NTP de las cinco VMs;
4. SSH e identidad `useransible` en cuatro nodos;
5. las cuatro NIC externas `DOWN` por MAC y bypass ICMP/TCP bloqueado;
6. rutas Cliente/Kali→DMZ, retorno del Servidor e `ip_forward` del Sensor;
7. Suricata limpio, ninguna captura/tcpdump y ausencia de PCAP remoto del ID;
8. servicios, listener único iperf3, Cliente permitido y Kali bloqueado;
9. probes HTTP/DNS/ICMP y hash local/remoto del generador.

El preflight no contiene llamadas a `run-f1.sh`, `start.sh`,
`ppi-pcap-control start` o `--execute-once`. Los probes preceden la quietud
oficial de 70 segundos que aplica después el ejecutor de campaña.

El log usa `umask 077`, temporal 0600, lock atómico entre preflights y rename
final. Un log oficial existente nunca se reemplaza; un fallo conserva un nombre
`failed-<timestamp>`. Los códigos remotos distinguen explícitamente proceso o
bloqueo esperado (`0/1/124`) de error SSH, evitando falsos PASS.

## Verificación y revisión

`bash -n`, `git diff --check` y 58/58 pruebas en Python del sistema y `.venv`
pasaron. Las pruebas congelan orden de gates, MAC, ausencia de lanzadores,
política no-overwrite, lock y discriminación de errores de transporte.

Claude bloqueó la primera versión porque dos condicionales podían interpretar
un error SSH como ausencia de tcpdump o bloqueo de Kali. Tras la corrección,
releyó el código y emitió **PREFLIGHT AUTORIZADO PARA EJECUCIÓN**. La autorización
no cubre la captura R05.

Siguiente paso: publicar el script, ejecutarlo una vez para
`DNS-VALID-10/R05`, verificar su log y solicitar autorización independiente para
una única captura. R05 no se puntúa parcial ni se usa para depurar el modelo.
