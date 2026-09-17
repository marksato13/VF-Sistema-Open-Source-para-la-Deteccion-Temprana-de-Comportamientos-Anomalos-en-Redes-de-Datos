# Configuración reproducible de Suricata

## Alcance

Suricata se ejecuta inicialmente como IDS pasivo en VM02 Sensor. Captura la entrada de `PPI-LAN` mediante `ens35`; no bloquea ni modifica paquetes.

## Valores aplicados

En `/etc/suricata/suricata.yaml`:

```yaml
vars:
  address-groups:
    HOME_NET: "[10.30.0.0/24,10.20.0.20/32]"
    EXTERNAL_NET: "!$HOME_NET"

outputs:
  - fast:
      enabled: yes
      filename: fast.log
  - eve-log:
      enabled: yes
      filename: eve.json
      community-id: true

af-packet:
  - interface: ens35
    threads: 4
    tpacket-v3: yes
    ring-size: 32768
    block-size: 1048576
    buffer-size: 1048576
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes

rule-files:
  - suricata.rules
  - local.rules
```

La configuración EVE distribuida con Suricata 8 mantiene activos `alert`, `anomaly`, `http`, `dns`, `tls`, `files`, `ssh`, `stats` y `flow`, entre otros eventos. Cualquier cambio posterior debe validarse con `suricata -T`.

Kali (`10.20.0.100`) queda fuera de `HOME_NET` para que las reglas direccionales de Emerging Threats puedan tratarlo como origen externo. El Cliente legítimo (`10.20.0.20/32`) y la DMZ protegida permanecen dentro de `HOME_NET`.

## Offloading

El servicio reproducible `configs/suricata/ppi-disable-offload.service` amplía el ring RX de `ens35` a 4096 y deshabilita TSO, GSO, GRO y LRO en `ens35` y `ens38` antes de iniciar Suricata. Debe copiarse a `/etc/systemd/system/`, habilitarse y verificarse con `ethtool -g` y `ethtool -k`.

## Reglas

- Reglas comunitarias: Emerging Threats Open, gestionadas mediante `suricata-update`.
- Regla de validación local: `configs/suricata/local.rules`.
- Destino operativo de la regla local: `/var/lib/suricata/rules/local.rules`.

## Validación

```bash
sudo suricata-update
sudo suricata -T -c /etc/suricata/suricata.yaml
sudo systemctl restart suricata
systemctl is-active suricata
sudo jq -r '.event_type' /var/log/suricata/eve.json | sort | uniq -c
```

No publicar `eve.json` completo ni PCAP sin sanitizarlos.
