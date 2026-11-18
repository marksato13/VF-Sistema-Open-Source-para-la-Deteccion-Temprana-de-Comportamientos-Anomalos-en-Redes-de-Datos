# Foto del laboratorio — 18-nov-2026

Copia en solo lectura de lo que corre en cada equipo el día de la demo, para que el repo
refleje el estado real. `MANIFIESTO-ESTADO-2026-11-18.json` dice qué commit corre dónde;
`hashes-sha256.txt` son los SHA-256 tomados en los equipos.

| Carpeta | Origen en el laboratorio |
|---|---|
| `sensor1/cf-demo/` | `~/cf-demo/` del Sensor1 (vista del motor para la demo) |
| `sensor1/d5/` | `/home/m4rk/cf-b/d5/`: publicador v2 D5 con lista blanca y su drop-in |
| `sensor1/systemd/` | `systemctl cat` de los servicios `ppi-*` |
| `srv-dmz/cf-demo/` | `~/cf-demo/` del SRV-DMZ: `fw.sh`, `lib.sh`, `instalar-sincronizar.sh`, `revertir-sincronizar.sh` |
| `srv-dmz/systemd/` | unidad del agente v2 con el drop-in `aplicar.conf` (`--aplicar --sincronizar`) |

Ojo: el SRV-DMZ está **aplicando** (no en sombra) por la exposición. Para volver a sombra:
`sudo rm /etc/systemd/system/ppi-enforce-agent-v2-dmz.service.d/aplicar.conf && sudo systemctl daemon-reload && sudo systemctl restart ppi-enforce-agent-v2-dmz`.
