# Laboratorio CyberFlow: configuración extraída y cómo replicarlo

Esta carpeta guarda **cómo está montado el laboratorio** donde corre CyberFlow, sacado de los
equipos reales (solo lectura) el 20-nov-2026. El código del producto está en la raíz del repo;
aquí está todo lo que lo rodea: especificaciones de cada VM, red, paquetes, servicios
systemd, configuración de Suricata, scripts de laboratorio, VLANs y SPAN de los switches.

| Carpeta | Qué hay |
|---|---|
| `extraccion/` | El extractor (se puede volver a correr) |
| `configuracion/INVENTARIO.md` | Resumen por equipo: rol, SO, vCPU, RAM, discos, IPs, servicios |
| `configuracion/<equipo>/` | Todo lo extraído de ese equipo (detalle abajo) |

## Equipos

| Equipo | VM (ESXi) | IP | Rol |
|---|---|---|---|
| `sensor1` | SENSOR1-CYBERFLOW (hv-siem) | 10.10.60.11 | Suricata (solo EVE) + motor + panel + publicador del feed; `ens37` recibe el SPAN |
| `sensor2` | SENSOR2-CYBERFLOW (hv-siem) | 10.10.60.12 | Sensor secundario |
| `suricata` | VM-SURICATA-CYBERFLOW (hv-siem) | 10.10.60.13 | Suricata con ET Open: comparador por replay de PCAP |
| `srvdmz` | SRV-DMZ-CYBERFLOW (hv-servicios) | 10.10.30.10 | Servidor atacado + agente de enforcement v2 (nftables) |
| `kali` | LAB-ATACANTE (hv-datos) | 10.10.20.30 | Atacante |
| `clientes` | LAB-CLIENTES (hv-datos) | 10.10.20.20–26 | Tráfico legítimo (7 IPs en una VM) |
| `bastion` | VM-GESTION (hv-servicios) | 10.10.10.30 | Entrada SSH y relés del feed y de eventos (`ppi-relay-*`) |
| `sw-*` | Catalyst (core, dist, acceso) | VLAN 99 | VLANs 10–60, troncales y SPAN hacia los sensores |
| `esxi-*` | ESXi 8.0.3 | 172.17.25.x | Hosts de las VMs anteriores |

Cada carpeta de un equipo Linux tiene:
- `sistema/`: SO, CPU, RAM, discos, hora y usuarios.
- `red/`: IPs, rutas, puertos en escucha, `/etc/hosts`, DNS y netplan.
- `paquetes/`: `dpkg`, paquetes manuales y `pip freeze` de cada venv.
- `servicios/`: unidades activas y habilitadas, timers y el `systemctl cat` de cada servicio propio.
- `files/`: copia de los ficheros de configuración con su ruta original (`/etc/...`, `/home/...`).

En los ESXi está el `.vmx` de cada VM de CyberFlow (vCPU, RAM, disco, NIC y portgroup) y la
red del host (vSwitch y portgroups, entre ellos `PG-CYBERFLOW-SPAN`, VLAN 4095).

## Cómo levantarlo en otro sitio

1. **Red.** Crear las VLANs de `sw-core-stack/vlan-brief.txt` y, si no hay switch físico,
   portgroups equivalentes. Llevar una copia del tráfico (SPAN o portgroup en modo
   promiscuo, VLAN 4095) a la segunda NIC del sensor (`sw-core-stack/monitor-session-all.txt`).
2. **VMs.** Crear cada VM con los recursos de su `.vmx` (`numvcpus`, `memSize`,
   `ethernetN.networkName`) e instalar el SO de `sistema/os-release.txt`.
3. **Red de cada VM.** Netplan e IPs de `red/` y `files/etc/netplan/`.
4. **Paquetes.** `apt install` de la lista de `paquetes/apt-manual.txt`; en los venv,
   `pip install -r paquetes/venv-*.txt`.
5. **Suricata del sensor.** `files/etc/suricata/suricata.yaml` y el drop-in de captura.
6. **CyberFlow.**
   - Código: este repo (`main`, etiqueta `estado-lab-2026-11-18`).
   - Procedimiento y hashes de lo desplegado: `deploy/laboratorio-2026-11-18/`.
   - Unidades systemd: `files/etc/systemd/system/ppi-*` del `sensor1`, del `bastion` y de `srvdmz`.
7. **Comprobar.** Los escenarios de la demo (`tools/demo-director/`) deben dar
   `port_scan` → BLOCK, `brute_force` → BLOCK y `http_abuse` → LIMIT, y el tráfico legítimo, PERMIT.

`ansible/` automatiza parte de los pasos 3–5 sobre un inventario anterior a esta extracción;
las IPs vigentes son las de esta carpeta.

## Lo que falta o no está aquí, a propósito

- **SRV-DMZ no se extrajo:** la VM estaba apagada (`Powered off` en hv-servicios). Están su
  `.vmx`, y su unidad systemd y sus scripts en `deploy/laboratorio-2026-11-18/`. Para
  completarlo, encenderla y ejecutar: `bash extraer_laboratorio.sh /tmp/x srvdmz`.
- **Firewall de cada host (nftables) y netplan de algunos equipos:** solo se leen con sudo con
  contraseña. Donde no se pudo, el fichero dice `[sin sudo -n]`.
- **Secretos:** no se copian claves privadas, `.env` ni `shadow`. `sanear.py` cambia
  contraseñas, claves y comunidades SNMP por «REDACTADO» y falla si queda algo sospechoso.
- **Infraestructura ajena a CyberFlow** (running-config completa de los switches, otras VMs
  de los ESXi, scripts del bastión de otros proyectos): queda fuera del repo, que es
  público. Hay una copia completa privada fuera de git.
- **pfSense, Wazuh y Zabbix** no tienen acceso SSH desde el bastión: no se extrajeron.
- **Datos:** modelos `.joblib`, registros, PCAP y `eve.json` no están aquí.

## Volver a extraer

Desde el bastión:

```bash
bash extraer_laboratorio.sh /tmp/cf-ext            # todos los equipos
bash extraer_laboratorio.sh /tmp/cf-ext sensor1    # uno solo
```

Después, en la copia local:
1. `python sanear.py <carpeta>` (sale con código 1 si queda algo sospechoso).
2. `python inventario.py <carpeta>`.
3. Separar lo público, como se hizo aquí.
