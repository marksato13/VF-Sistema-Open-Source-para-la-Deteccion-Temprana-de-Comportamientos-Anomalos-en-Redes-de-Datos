# Capturas de las guías

Cada figura de las guías apunta a un PNG de esta carpeta. Mientras no exista la
captura real, el PNG es un marcador gris («Captura pendiente»). **Para completarla,
guarde la captura con el mismo nombre**: la guía no se toca.

Reglas: terminal con fuente legible y sin datos personales; **ninguna contraseña,
clave ni token a la vista**; recortar a la parte útil; PNG, ancho 1200–1600 px.

| Figura | Fichero | Guía | Qué capturar | Quién | Estado |
|---|---|---|---|---|---|
| 2.1 | [`instalacion/02-01-span-switch.png`](instalacion/02-01-span-switch.png) | `docs/INSTALACION.md` | `show monitor session 1` en el Catalyst: origen, destino y `encapsulation replicate` | Mark (switch) | pendiente |
| 2.2 | [`instalacion/02-02-outdiscards.png`](instalacion/02-02-outdiscards.png) | `docs/INSTALACION.md` | `show interfaces Gi2/0/19 counters errors` | Mark (switch) | pendiente |
| 2.3 | [`instalacion/02-03-grupo-puertos.png`](instalacion/02-03-grupo-puertos.png) | `docs/INSTALACION.md` | Pantalla del grupo de puertos en ESXi (o el puente en Proxmox) | Mark (hipervisor) | pendiente |
| 3.1 | [`instalacion/03-01-ip-br-link.png`](instalacion/03-01-ip-br-link.png) | `docs/INSTALACION.md` | `ip -br link` y `ip -br addr` en el sensor | Claude/Mark (VM2) | pendiente |
| 4.1 | [`instalacion/04-01-rx-packets.png`](instalacion/04-01-rx-packets.png) | `docs/INSTALACION.md` | Las dos lecturas de `/sys/class/net/ens37/statistics/rx_packets` | Mark (VM2) | pendiente |
| 4.2 | [`instalacion/04-02-tcpdump-vlan.png`](instalacion/04-02-tcpdump-vlan.png) | `docs/INSTALACION.md` | `sudo tcpdump -i ens37 -e -nn -c 20` | Mark (VM2) | pendiente |
| 5.1 | [`instalacion/05-01-suricata-test.png`](instalacion/05-01-suricata-test.png) | `docs/INSTALACION.md` | `sudo suricata -T -c /etc/suricata/suricata.yaml -v` y `systemctl status suricata` | Mark (VM2) | pendiente |
| 5.2 | [`instalacion/05-02-eve-crece.png`](instalacion/05-02-eve-crece.png) | `docs/INSTALACION.md` | Las dos lecturas de `wc -l` separadas por 60 s | Mark (VM2) | pendiente |
| 6.1 | [`instalacion/06-01-asistente.png`](instalacion/06-01-asistente.png) | `docs/INSTALACION.md` | `bash scripts/setup/configurar.sh` completo, con lo que propone y lo que se acepta | Mark (VM2) | hecha |
| 6.2 | [`instalacion/06-02-instalar-comprobar.png`](instalacion/06-02-instalar-comprobar.png) | `docs/INSTALACION.md` | `sudo bash scripts/setup/instalar.sh --comprobar` | Mark (VM2) | pendiente |
| 6.3 | [`instalacion/06-03-instalar.png`](instalacion/06-03-instalar.png) | `docs/INSTALACION.md` | `sudo bash scripts/setup/instalar.sh` (puede ir en dos capturas) | Mark (VM2) | pendiente |
| 6.4 | [`instalacion/06-04-instalado.png`](instalacion/06-04-instalado.png) | `docs/INSTALACION.md` | Últimas líneas de `instalar.sh` | Mark (VM2) | pendiente |
| 6.5 | [`instalacion/06-05-sha256.png`](instalacion/06-05-sha256.png) | `docs/INSTALACION.md` | `sha256sum -c docs/dataset/SHA256SUMS` | Mark (VM2) | hecha |
| 6.6 | [`instalacion/06-06-config-mostrar.png`](instalacion/06-06-config-mostrar.png) | `docs/INSTALACION.md` | `cyberflow_config.py --comprobar` y `--mostrar` | Mark (VM2) | pendiente |
| 6.7 | [`instalacion/06-07-cuentas-panel.png`](instalacion/06-07-cuentas-panel.png) | `docs/INSTALACION.md` | Los cuatro comandos de `cyberflow_usuarios.py` (la contraseña NO debe verse) | Mark (VM2) | pendiente |
| 7.1 | [`instalacion/07-01-doctor.png`](instalacion/07-01-doctor.png) | `docs/INSTALACION.md` | `bash scripts/setup/doctor.sh` completo | Claude/Mark (VM2) | pendiente |
| 7.2 | [`instalacion/07-02-anillo.png`](instalacion/07-02-anillo.png) | `docs/INSTALACION.md` | `ls -la /var/lib/ppi-motor-capture/` dos veces | Claude/Mark (VM2) | pendiente |
| 7.3 | [`instalacion/07-03-decisiones.png`](instalacion/07-03-decisiones.png) | `docs/INSTALACION.md` | `tail -f logs/motor_decision.log` | Claude/Mark (VM2) | pendiente |
| 7.4 | [`instalacion/07-04-panel-login.png`](instalacion/07-04-panel-login.png) | `docs/INSTALACION.md` | Navegador en `https://<sensor>:8788/login` | Mark (navegador) | pendiente |
| 8.1 | [`instalacion/08-01-recalibracion.png`](instalacion/08-01-recalibracion.png) | `docs/INSTALACION.md` | Salida del entrenamiento y la promoción del paso 8 | Mark (cuando se recalibre) | pendiente |
| A.1 | [`instalacion/A-01-bundle.png`](instalacion/A-01-bundle.png) | `docs/INSTALACION.md` | `preparar-bundle.sh` terminado y `ls bundle/` | Mark (máquina con red) | pendiente |
| A.2 | [`instalacion/A-02-offline.png`](instalacion/A-02-offline.png) | `docs/INSTALACION.md` | El paso «7. Entorno de Python» de `instalar.sh` usando las ruedas locales | Mark (VM2) | pendiente |
| R.1 | [`readme/R-01-demo.png`](readme/R-01-demo.png) | `README.md` | Navegador en `http://127.0.0.1:8788` tras `bash scripts/demo.sh` | Claude (local) | hecha |
| R.2 | [`readme/R-02-desinstalar.png`](readme/R-02-desinstalar.png) | `README.md` | `desinstalar.sh --simular` y `desinstalar.sh` | Mark (VM2) | pendiente |
| G.1 | [`guia/G-01-decisiones.png`](guia/G-01-decisiones.png) | `docs/GUIA-USUARIO.md` | `tail -f logs/motor_decision.log` | Claude/Mark | pendiente |
| G.2 | [`guia/G-02-panel-operativo.png`](guia/G-02-panel-operativo.png) | `docs/GUIA-USUARIO.md` | Panel tras entrar como `admin` | Mark (navegador) | pendiente |
| G.3 | [`guia/G-03-panel-desarrollador.png`](guia/G-03-panel-desarrollador.png) | `docs/GUIA-USUARIO.md` | Botón de modo en la cabecera → desarrollador | Mark (navegador) | pendiente |
| G.4 | [`guia/G-04-panel-lector.png`](guia/G-04-panel-lector.png) | `docs/GUIA-USUARIO.md` | Panel tras entrar como `lector` | Mark (navegador) | pendiente |
| G.5 | [`guia/G-05-desbloquear.png`](guia/G-05-desbloquear.png) | `docs/GUIA-USUARIO.md` | `nft list set` de los dos sets en el host DMZ | Mark (host DMZ) | pendiente |
| G.6 | [`guia/G-06-config.png`](guia/G-06-config.png) | `docs/GUIA-USUARIO.md` | `--comprobar`, `--escribir` y el reinicio | Mark (VM2) | pendiente |
