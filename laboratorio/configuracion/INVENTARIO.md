# Inventario del laboratorio CyberFlow

Generado de la extracción `configuracion` (`_registro.txt` = hora y resultado por equipo).

## bastion
*Bastión de gestión (VM-GESTION): punto de entrada SSH a todo el laboratorio*

- **Hostname:** `VM-GESTION` · **SO:** Debian GNU/Linux 13 (trixie) · **Virtualización:** vmware
- **CPU:** 2 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 1.9Gi
- **Discos:** /dev/sda1 19G /
- **Red:**
  - `ens192           UP             172.17.25.34/24 fe80::5917:b64e:d550:789e/64 `
  - `ens224           UP             10.10.10.30/24 fe80::20c:29ff:fe42:8716/64 `
  - `tailscale0       UNKNOWN        100.68.234.28/32 fd7a:115c:a1e0::c432:ea1d/128 fe80::cd19:ea7b:899e:d21a/64`
- **Servicios relevantes activos:** ninguno de la lista
- **Paquetes instalados:** 559 (lista en `paquetes/dpkg.txt`)

## clientes
*Clientes legítimos (7 IPs en una VM) que generan tráfico normal*

- **Hostname:** `clientesadmin` · **SO:** Ubuntu 24.04.2 LTS · **Virtualización:** vmware
- **CPU:** 2 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 1.9Gi
- **Discos:** efivarfs 256K /sys/firmware/efi/efivars; /dev/mapper/ubuntu--vg-ubuntu--lv 14G /; /dev/sda2 2.0G /boot; /dev/sda1 1.1G /boot/efi
- **Red:**
  - `ens34            UP             10.10.20.20/24 10.10.20.21/24 10.10.20.22/24 10.10.20.23/24 10.10.20.24/24 10.10.20.25/24 10.10.20.26/24 fe80::20c:29ff:fef4:637/64 `
  - `ens35            DOWN`
- **Servicios relevantes activos:** ninguno de la lista
- **Paquetes instalados:** 711 (lista en `paquetes/dpkg.txt`)
- **Firewall del host:** no leído (requiere sudo con contraseña; ver la sección «Lo que falta»)

## esxi-hv-datos

- **Versión:** VMware ESXi 8.0.3 build-24280767
- **VMs:** `LAB-ATACANTE`, `LAB-CLIENTES`
- `.vmx` de cada VM en `vmx/` (CPU, RAM, discos, NIC y portgroup) y red/almacén del host en `host.txt`

## esxi-hv-servicios

- **Versión:** VMware ESXi 8.0.3 build-24280767
- **VMs:** `SRV-DMZ-CYBERFLOW`
- `.vmx` de cada VM en `vmx/` (CPU, RAM, discos, NIC y portgroup) y red/almacén del host en `host.txt`

## esxi-hv-siem

- **Versión:** VMware ESXi 8.0.3 build-24280767
- **VMs:** `SENSOR1-CYBERFLOW`, `SENSOR2-CYBERFLOW`, `VM-SURICATA-CYBERFLOW`
- `.vmx` de cada VM en `vmx/` (CPU, RAM, discos, NIC y portgroup) y red/almacén del host en `host.txt`

## kali
*Atacante (Kali) para las campañas y la demo*

- **Hostname:** `kali` · **SO:** Kali GNU/Linux Rolling · **Virtualización:** vmware
- **CPU:** 2 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 3.8Gi
- **Discos:** /dev/sda1 38G /
- **Red:**
  - `eth0             UP             10.10.20.30/24`
- **Servicios relevantes activos:** ninguno de la lista
- **Paquetes instalados:** 2860 (lista en `paquetes/dpkg.txt`)
- **Firewall del host:** no leído (requiere sudo con contraseña; ver la sección «Lo que falta»)

## sensor1
*Sensor principal: Suricata (solo EVE) + motor CyberFlow + panel + publicador del feed*

- **Hostname:** `cyberflow-sensor` · **SO:** Ubuntu 24.04.2 LTS · **Virtualización:** vmware
- **CPU:** 4 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 7.8Gi
- **Discos:** efivarfs 256K /sys/firmware/efi/efivars; /dev/mapper/ubuntu--vg-ubuntu--lv 76G /; /dev/sda2 2.0G /boot; /dev/sda1 1.1G /boot/efi
- **Red:**
  - `ens34            UP             10.10.60.11/24 fe80::20c:29ff:fe3d:f944/64 `
  - `ens37            UP`
- **Servicios relevantes activos:** `ppi-dashboard.service`, `ppi-motor-capture.service`, `ppi-motor.service`, `ppi-publicar-feed-v2.service`, `ppi-via-rapida@ens37.service`, `suricata.service`
- **Paquetes instalados:** 813 (lista en `paquetes/dpkg.txt`)
- **Firewall del host:** no leído (requiere sudo con contraseña; ver la sección «Lo que falta»)

## sensor2
*Sensor secundario (réplica del sensor)*

- **Hostname:** `cyberflow-sensor2` · **SO:** Ubuntu 24.04.2 LTS · **Virtualización:** vmware
- **CPU:** 4 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 7.8Gi
- **Discos:** efivarfs 256K /sys/firmware/efi/efivars; /dev/mapper/ubuntu--vg-ubuntu--lv 19G /; /dev/sda2 2.0G /boot; /dev/sda1 1.1G /boot/efi
- **Red:**
  - `ens34            UP             10.10.60.12/24 fe80::20c:29ff:fe35:255e/64 `
  - `ens37            UP`
- **Servicios relevantes activos:** `ppi-dashboard.service`, `ppi-motor-capture.service`, `ppi-motor.service`, `suricata.service`
- **Paquetes instalados:** 748 (lista en `paquetes/dpkg.txt`)
- **Firewall del host:** no leído (requiere sudo con contraseña; ver la sección «Lo que falta»)

## srvdmz
*Servidor DMZ atacado: web/servicios + agente de enforcement v2 (nftables)*

- **Hostname:** `srv-dmz` · **SO:** Ubuntu 24.04.5 LTS · **Virtualización:** vmware
- **CPU:** 1 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 1.9Gi
- **Discos:** efivarfs 256K /sys/firmware/efi/efivars; /dev/mapper/ubuntu--vg-ubuntu--lv 17G /; /dev/sda2 1.7G /boot; /dev/sda1 952M /boot/efi
- **Red:**
  - `ens34            DOWN           `
  - `ens35            UP             10.10.30.10/24 fe80::20c:29ff:fe87:7e9f/64`
- **Servicios relevantes activos:** `ppi-enforce-agent-v2-dmz.service`
- **Paquetes instalados:** 698 (lista en `paquetes/dpkg.txt`)

## suricata
*IDS comparador: Suricata con reglas ET Open (replay de PCAP)*

- **Hostname:** `vm-ids-suricata` · **SO:** Ubuntu 24.04.2 LTS · **Virtualización:** vmware
- **CPU:** 4 vCPU (Intel(R) Xeon(R) Bronze 3204 CPU @ 1.90GHz) · **RAM:** 7.8Gi
- **Discos:** efivarfs 256K /sys/firmware/efi/efivars; /dev/mapper/ubuntu--vg-ubuntu--lv 19G /; /dev/mapper/ubuntu--vg-suricata--logs 15G /var/log/suricata; /dev/sda2 2.0G /boot
- **Red:**
  - `ens34            UP             10.10.60.13/24 fe80::20c:29ff:febb:fd5/64 `
  - `ens37            UP`
- **Servicios relevantes activos:** `chrony.service`, `suricata.service`, `wazuh-agent.service`, `zabbix-agent2.service`
- **Paquetes instalados:** 768 (lista en `paquetes/dpkg.txt`)

## sw-access-sw5

- **IOS:** 15.2(7)E10 · **Modelo:** C1000-24P-4G-L
- **VLANs:** `1 default`, `20 USUARIOS`, `80 DISPOSITIVOS`, `85 VOZ`, `88 CUARENTENA`, `95 INVITADOS`, `99 MGMT`, `999 NATIVE_UNUSED`, `1002 fddi-default`, `1003 token-ring-default`, `1004 fddinet-default`, `1005 trnet-default`
- Troncales, SPAN hacia los sensores (`monitor-session-all.txt`) y etherchannel; la running-config completa queda fuera del repo público

## sw-access-sw7

- **IOS:** 15.2(7)E6 · **Modelo:** C1000-24P-4G-L
- **VLANs:** `1 default`, `20 USUARIOS`, `80 DISPOSITIVOS`, `85 VOZ`, `88 CUARENTENA`, `95 INVITADOS`, `99 MGMT`, `999 NATIVE_UNUSED`, `1002 fddi-default`, `1003 token-ring-default`, `1004 fddinet-default`, `1005 trnet-default`
- Troncales, SPAN hacia los sensores (`monitor-session-all.txt`) y etherchannel; la running-config completa queda fuera del repo público

## sw-access-sw8

- **IOS:** 15.2(7)E6 · **Modelo:** C1000-24P-4G-L
- **VLANs:** `1 default`, `20 USUARIOS`, `80 DISPOSITIVOS`, `85 VOZ`, `88 CUARENTENA`, `95 INVITADOS`, `99 MGMT`, `999 NATIVE_UNUSED`, `1002 fddi-default`, `1003 token-ring-default`, `1004 fddinet-default`, `1005 trnet-default`
- Troncales, SPAN hacia los sensores (`monitor-session-all.txt`) y etherchannel; la running-config completa queda fuera del repo público

## sw-core-stack

- **IOS:** 17.09.03 · **Modelo:** C9300L-24T-4G
- **VLANs:** `1 default`, `10 ADMIN`, `20 USUARIOS`, `30 DMZ`, `40 SERVICIOS`, `50 DATOS`, `60 GESTION`, `70 TRANSIT-FORTIGATE`, `80 DISPOSITIVOS`, `85 VOZ`, `88 CUARENTENA`, `90 DMZ_HONEYPOT`, `95 INVITADOS`, `99 MGMT`, `100 PFSENSE_SYNC`, `999 NATIVE_UNUSED`, `1002 fddi-default`, `1003 token-ring-default`, `1004 fddinet-default`, `1005 trnet-default`
- Troncales, SPAN hacia los sensores (`monitor-session-all.txt`) y etherchannel; la running-config completa queda fuera del repo público

## sw-dist-stack

- **IOS:** 17.06.04 · **Modelo:** C9200L-24T-4G
- **VLANs:** `1 default`, `10 ADMIN`, `20 USUARIOS`, `30 DMZ`, `40 SERVICIOS`, `50 DATOS`, `60 GESTION`, `70 TRANSIT-FORTIGATE`, `80 DISPOSITIVOS`, `85 VOZ`, `88 CUARENTENA`, `90 DMZ_HONEYPOT`, `95 INVITADOS`, `99 MGMT`, `100 PFSENSE_SYNC`, `999 NATIVE_UNUSED`, `1002 fddi-default`, `1003 token-ring-default`, `1004 fddinet-default`, `1005 trnet-default`
- Troncales, SPAN hacia los sensores (`monitor-session-all.txt`) y etherchannel; la running-config completa queda fuera del repo público

