# Calibración de fragmentación IP real CAL-FRAG-UDP-01

Fecha: 2026-08-14. Estado: **detenida en preflight; no hubo captura ni ejecución del escenario**.

## Cuarto y último intento

El cuarto intento comenzó a las `2026-08-14T11:19:19,930400103-05:00`.
El estado local pasó con `51428634624` bytes disponibles. La invocación
directa de `scripts/f1/check_ntp_gate.sh` volvió a fallar dentro de esta
ejecución antes del primer SSH:

```text
Failed to connect to system scope bus via local transport: Operation not permitted (consider using --machine=<user>@.host --user to connect to bus of other user)
ERROR: VM01 no usa America/Lima
```

El preflight terminó con código `1`. Los cuatro hosts quedaron sin ejecutar,
no se desplegó el generador y no se creó PCAP, EVE ni manifest. Conforme a la
instrucción explícita, no se realizó otro intento. Log:
`artifacts/preflight/CAL-FRAG-UDP-01-R01.fourth-preflight.log`, SHA-256
`afe81895770d0ae270d053c2b25c3d7f3bf7e97757082e074b45bfd0a9c8259d`.

Además del caso `frag-udp` en `scripts/f1/run-benign.sh`, quedaron modificados
sin commit dos scripts compartidos para incorporar `-F /dev/null`:
`scripts/campaign/common.sh` y `scripts/f1/check_ntp_gate.sh`. No se modificó
la matriz de campañas ni ningún CSV congelado.

## Tercer intento con red habilitada y `-F /dev/null`

El commit `fe4abe63202db75241bca49bbe6efaffce24d296` habilitó la red del
sandbox y se añadió `-F /dev/null` al transporte SSH compartido. El preflight
continuo comenzó a las `2026-08-14T11:07:17,349622134-05:00`. El gate local
de estado pasó con `51425427456` bytes disponibles, pero el gate NTP abortó
antes de contactar las cuatro VMs. Salida literal:

```text
Failed to connect to system scope bus via local transport: Operation not permitted (consider using --machine=<user>@.host --user to connect to bus of other user)
ERROR: VM01 no usa America/Lima
```

El comando `timedatectl` de `scripts/f1/check_ntp_gate.sh` no pudo acceder al
bus systemd desde el sandbox y la comprobación posterior interpretó la salida
vacía como una zona horaria incorrecta. Esta es la hipótesis basada en el
orden y la salida real; no se modificó ni repitió el gate. Sensor, Servidor,
Kali y Cliente quedaron `NO EJECUTADO` por la regla de detención inmediata.
No se desplegó el generador, no se abrió campaña, no se ejecutó tráfico y no
se lanzó el extractor.

Log: `artifacts/preflight/CAL-FRAG-UDP-01-R01.third-preflight.log`, SHA-256
`28bdf0e049e8e0e3d9045b95ed4da69af2871eefe136b39a119fa4b2a914ca92`.
El estado del tercer intento es `RECHAZAR` por ausencia de captura y features.

## Reintento autorizado del 2026-08-14

El usuario autorizó repetir desde cero el mismo ID porque el primer fallo no
había abierto captura. Antes del reintento se calcularon los hashes de los CSV
F1 congelados (`train`, `validation`, `test`) y de los dos CSV v2. El primer
gate volvió a ejecutar literalmente:

```bash
ssh -i /home/m4rk/.ssh/id_ed25519_ppi_ansible -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 useransible@10.10.10.20 'printf "host="; hostname; printf "user="; id -un'
```

Resultado real: exit code `255`, duración observada `0.000009024` segundos y
stderr literal:

```text
Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf
```

El fallo ocurre localmente antes de establecer conexión. En este entorno de
ejecución, `stat -L` presentó el archivo incluido como `nobody:nogroup`, aunque
la revisión humana externa lo verificó como `root:root`. La hipótesis es una
vista/mapeo de propiedad específica del sandbox que hace fallar la validación
estricta de OpenSSH; no se probó ningún workaround porque habría constituido
un cambio de técnica no autorizado después del fallo.

Estado por host: Sensor VM02 `10.10.10.20` = `FAIL`; Servidor VM03
`10.10.10.30`, Kali VM04 `10.10.10.40` y Cliente VM05 `10.10.10.50` =
`NO EJECUTADO` por la regla de detención inmediata. No se desplegó el
generador, no se abrió PCAP, no se produjo EVE, no se ejecutó
`./run-benign.sh frag-udp 3000 10` y no se lanzó el extractor.

Los hashes F1 antes/después permanecieron idénticos: `train.csv`
`c6c1028977da3b9d17b192df4c74de71e081a5e93232ed4bda34529a73a0da07`,
`validation.csv`
`979536f4f9eed09baee08d79511a49137ab5bfef598c37986446a521c8b25f8d` y
`test.csv`
`1482a1ca406ee830aed172b4c692dfb8825163dae505b892e359572ded7af07b`.
`configs/campaigns/multilayer-v2-normal.json` coincidió con Git HEAD:
`9e4fb34eac0a27c6711bd77c5e6eca8e9108b536ce9ab7fa8424dbec0f780359`.
El reintento se clasifica `RECHAZAR`: no existe evidencia de calibración.

## 1. Pasos ejecutados (qué hiciste, en orden).

1. Se leyeron completos `docs/revisiones-claude/NEXT-TASK-FOR-CODEX.md` y `docs/fase03-dataset/172-brecha-api-5xx-y-permisos.md`.
2. Se calcularon los SHA-256 iniciales de los dos CSV congelados.
3. Se inspeccionó la evidencia real de `CAL-G7-API-5XX-R02` y el mecanismo `start.sh`/`stop.sh`, PCAP remoto/local, EVE, hashes y extracción v2.
4. Se añadió a `scripts/f1/run-benign.sh` el caso `frag-udp` y su entrada en `usage()`, exactamente con la lista blanca especificada. No se modificó ningún caso existente.
5. `bash -n`, `git diff --check` y la prueba local negativa de longitud inválida pasaron. Esta prueba no produjo tráfico.
6. Se inició el preflight de acceso SSH y servicios. Falló en el primer acceso, antes de desplegar el generador, crear un manifest, iniciar PCAP o ejecutar `frag-udp`.
7. Conforme a la regla de un solo intento y detención ante fallo de preflight, no se reintentó ni se cambió la técnica.
8. Se registró el fallo en un log y un ledger con `purpose=calibration`, `partition=excluded_calibration`, `capture_started=false` y `scenario_executed=false`.
9. Se verificó que no existen directorios de campaña/features para el ID y se recalcularon los SHA-256 de los CSV congelados.

## 2. Comandos exactos ejecutados (texto literal).

Hashes iniciales:

```bash
sha256sum artifacts/dataset/multilayer-v2-normal.csv artifacts/dataset/multilayer-v2-anomalies.csv
```

Validación del cambio sin tráfico:

```bash
bash -n scripts/f1/run-benign.sh
git diff --check -- scripts/f1/run-benign.sh
git diff -- scripts/f1/run-benign.sh
set +e
scripts/f1/run-benign.sh frag-udp 1500 10 >/tmp/frag-udp-invalid.stdout 2>/tmp/frag-udp-invalid.stderr
rc=$?
set -e
printf 'invalid_rc=%s\n' "$rc"
cat /tmp/frag-udp-invalid.stderr
```

Preflight que falló:

```bash
set -euo pipefail
ssh_opts=(-i /home/m4rk/.ssh/id_ed25519_ppi_ansible -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)
for host in 10.10.10.20 10.10.10.30 10.10.10.40 10.10.10.50; do
  ssh "${ssh_opts[@]}" "useransible@$host" 'printf "host="; hostname; printf "user="; id -un'
done
ssh "${ssh_opts[@]}" useransible@10.10.10.50 'ls -l /home/useransible/bin/ppi-run-benign /home/useransible/bin/run-benign.sh 2>&1 || true; sha256sum /home/useransible/bin/ppi-run-benign; ip route get 10.30.0.10'
ssh "${ssh_opts[@]}" useransible@10.10.10.30 'systemctl is-active ppi-iperf3; ss -H -ltn "sport = :5201"; iperf3 --version | head -n1; ip route get 10.20.0.20'
ssh "${ssh_opts[@]}" useransible@10.10.10.20 'sudo -n /usr/local/sbin/ppi-suricata-metrics; sysctl -n net.ipv4.ip_forward'
```

Comprobación final:

```bash
date --iso-8601=ns
sha256sum artifacts/preflight/CAL-FRAG-UDP-01-R01.failed.log
sha256sum scripts/f1/run-benign.sh
sha256sum artifacts/dataset/multilayer-v2-normal.csv artifacts/dataset/multilayer-v2-anomalies.csv
for path in \
  artifacts/campaigns/CAL-FRAG-UDP-01-R01 \
  artifacts/features-v2/CAL-FRAG-UDP-01-R01 \
  /srv/ppi-evidence/artifacts/campaigns/CAL-FRAG-UDP-01-R01 \
  /srv/ppi-evidence/artifacts/features-v2/CAL-FRAG-UDP-01-R01; do
  if [[ -e "$path" ]]; then printf 'EXISTS %s\n' "$path"; else printf 'ABSENT %s\n' "$path"; fi
done
git status --short
git diff --check
```

El comando de captura prescrito no se ejecutó:

```bash
./run-benign.sh frag-udp 3000 10
```

## 3. Rutas de evidencia generada: PCAP, EVE, ledger, manifest.

- PCAP: no generado; el preflight falló antes de iniciar captura.
- EVE: no generado; el preflight falló antes de iniciar captura.
- Ledger: `artifacts/g6-ledger/CAL-FRAG-UDP-01-R01.json`.
- Manifest: no generado; no se abrió una campaña.
- Log de preflight: `artifacts/preflight/CAL-FRAG-UDP-01-R01.failed.log`, SHA-256 `9cb8514ee908284ee285a6b0b00e8d9a80ef1aa5e72797ffae39d796d1a6efcf`.

Las cuatro rutas de campaña/features, tanto bajo `artifacts/` como bajo `/srv/ppi-evidence/artifacts/`, resultaron `ABSENT`.

## 4. Valor exacto de fragment_ratio_10s obtenido por ventana.

No hay ventanas producidas y, por tanto, no existe un valor de `fragment_ratio_10s`: el extractor no se ejecutó porque no hubo PCAP/EVE. No se declara éxito de calibración.

## 5. Errores, bloqueos o limitaciones encontradas (si los hubo, con el error literal).

El primer comando SSH del preflight terminó con el error literal:

```text
Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf
```

No se reintentó, no se ignoró la configuración SSH, no se desplegó el generador y no se consumió el intento único de captura. Se requiere revisión humana del propietario/permisos de `/etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf` antes de autorizar una nueva ejecución.

## 6. Confirmación explícita de que los hashes SHA-256 de multilayer-v2-normal.csv y multilayer-v2-anomalies.csv NO cambiaron (mostrar hash antes y después).

| Archivo | SHA-256 antes | SHA-256 después | Resultado |
|---|---|---|---|
| `artifacts/dataset/multilayer-v2-normal.csv` | `be8b71104bda5200a04ee77bdda5c3e164c5ed9a753bfc8c7dae9bb41003e99e` | `be8b71104bda5200a04ee77bdda5c3e164c5ed9a753bfc8c7dae9bb41003e99e` | No cambió |
| `artifacts/dataset/multilayer-v2-anomalies.csv` | `d8bf293d6427398c5091344397ec1aea3303f277cae32d0988a0dc164ada761a` | `d8bf293d6427398c5091344397ec1aea3303f277cae32d0988a0dc164ada761a` | No cambió |

No se modificó `configs/campaigns/multilayer-v2-normal.json`. No se hizo commit ni push.
