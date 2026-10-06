# Enforcement como systemd (reemplaza los crons ad-hoc)

El pipeline de enforcement corría con **crons de usuario** (añadidos a mano). Esto
lo convierte en **units + timers systemd**: arrancan solos tras reinicio, logean al
journal, y quedan versionados y reproducibles. Un rol por host.

| Host | Unit | Qué hace |
|---|---|---|
| Sensor1 `m4rk@10.10.60.11` | `ppi-publicar-feed` | publica y firma el feed desde las decisiones del motor |
| Bastión `gadmin@10.10.10.30` | `ppi-relay-feed` | pull del feed (sensor) → push al host DMZ |
| Host DMZ `adminsrvdmz@10.10.30.10` | `ppi-enforce-agent` | verifica el feed y aplica nftables (`--aplicar --sudo`) |

Cada timer corre **cada minuto** (`OnCalendar=minutely`). La instalación necesita
**sudo con contraseña** en cada host (no automatizable sin la clave de Mark).

## Instalar (por host; copiar los .service/.timer a /etc/systemd/system)

### Sensor1
```bash
sudo cp ppi-publicar-feed.service ppi-publicar-feed.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ppi-publicar-feed.timer
crontab -l | grep -v publicar_feed | crontab -      # quita el cron viejo
```

### Bastión
```bash
sudo cp ppi-relay-feed.service ppi-relay-feed.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ppi-relay-feed.timer
crontab -l | grep -v relay-feed | crontab -
```

### Host DMZ
```bash
sudo cp ppi-enforce-agent.service ppi-enforce-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ppi-enforce-agent.timer
crontab -l | grep -v agente_enforce | crontab -
```

## Verificar
```bash
systemctl list-timers | grep ppi          # los 3 timers activos con su proximo disparo
journalctl -u ppi-publicar-feed -n 10 --no-pager
journalctl -u ppi-enforce-agent -n 10 --no-pager   # debe decir "aplicado","errores":0
sudo nft list table inet cyberflow        # en el host DMZ: sets/reglas
```

## Rollback (volver al cron)
```bash
sudo systemctl disable --now ppi-<rol>.timer
# re-añadir la linea de cron correspondiente con 'crontab -e'
```

## Notas
- `ppi-enforce-agent.service` **no** debe llevar `NoNewPrivileges=yes`: rompería el
  `sudo -n nft` (que es el que corta/limita). El `sudo` del `nft` es NOPASSWD solo
  para ese binario en el host DMZ.
- Para **modo sombra** (medir sin aplicar), quitar `--aplicar` del
  `ppi-enforce-agent.service` y recargar.
- `--umbrales 2026-10-06.1` en `ppi-publicar-feed` refleja los umbrales corregidos
  (port_scan/dns_entropy a 0,45 por el doblado del espejo).
