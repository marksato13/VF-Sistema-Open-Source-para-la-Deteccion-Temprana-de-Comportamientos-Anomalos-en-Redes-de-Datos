# Diversidad legítima L3 y matriz F1 v2

Fecha de diseño: 21 de julio de 2026. Estado: **aplicado, persistente y validado mediante piloto**. Evidencia: `05-validacion-diversidad-L3-v2.md`.

## Problema

`f1-normal-v1` enviaba todo el tráfico a `10.30.0.10`. La feature `unique_dst_ip_ratio_30s` podía calcularse, pero casi no observaba diversidad legítima. Un modelo entrenado así podría interpretar cualquier segundo destino como anomalía, reproduciendo el mismo problema señalado por el jurado para los paquetes grandes.

No se crearán direcciones ficticias sin servicio. VM03 tendrá tres direcciones persistentes en `ens38`:

| Dirección | Función | Servicio permitido |
|---|---|---|
| `10.30.0.10/24` | servicio principal existente | HTTP, HTTPS, DNS, iperf3 y SSH controlado |
| `10.30.0.11/24` | VIP web A | HTTP/80 e ICMP de diagnóstico |
| `10.30.0.12/24` | VIP web B | HTTP/80 e ICMP de diagnóstico |

Son tres identidades de red en una sola VM. Aportan diversidad lógica de destinos, no diversidad física, de sistema operativo ni de fallo. Esa limitación debe explicarse al jurado.

## Persistencia y seguridad

`configs/server/99-ppi-service-vips.yaml` añade `.11` y `.12` a `ens38`. Netplan documenta que `addresses` acepta múltiples direcciones y que, al combinar archivos con nombres diferentes, las secuencias se concatenan. Por ello el archivo nuevo añade direcciones sin sustituir `.10` ni la ruta de retorno existente ([Netplan: múltiples direcciones](https://netplan.readthedocs.io/en/0.105/examples.html), [Netplan: combinación de archivos](https://netplan.readthedocs.io/en/1.0/netplan-generate/)).

La validación local con `netplan generate --root-dir` produjo:

```text
Address=10.30.0.11/24
Address=10.30.0.12/24
```

El playbook primero ejecuta `netplan generate`, aplica únicamente cuando cambia el archivo y después exige `.10/.11/.12` en `ens38`. También confirma que la ruta a `10.20.0.20` continúa mediante `10.30.0.1 dev ens38`; la interfaz administrativa `ens35` no se redefine.

NGINX escucha HTTP en las tres direcciones. El firewall limita `.11` y `.12` a TCP/80 y bloquea UDP, evitando que SSH, iperf3 u otros listeners globales se expongan accidentalmente en las VIP. Suricata y el helper PCAP ya cubren `10.30.0.0/24`, por lo que no requieren ampliar su filtro.

## Comprobación de direcciones libres

Antes de asignarlas, VM03 intentó resolver ambas por ARP mediante dos pings independientes:

```text
10.30.0.11 dev ens38 INCOMPLETE, ping_rc=1
10.30.0.12 dev ens38 INCOMPLETE, ping_rc=1
```

El Sensor solo tenía una entrada vecina para `.10`. En la red DMZ aislada esto es evidencia razonable de que `.11` y `.12` no estaban ocupadas. Después de aplicar se repetirá la comprobación desde Cliente y se verificará la MAC esperada de VM03.

## Matriz `f1-normal-v2`

`v1` se conserva sin editar para reproducir los cuatro pilotos anteriores. `v2` añade:

| Perfil | Solicitudes | Valor L3 esperado |
|---|---:|---|
| `HTTP-MULTI-1` | una a cada `.10/.11/.12` | ratio de destinos cercano a 3/3 = 1.0 |
| `HTTP-MULTI-5` | cinco a cada destino | ratio cercano a 3/15 = 0.2 |

Los valores exactos se medirán, no se impondrán como resultado. La atribución de flujo, retransmisiones o tráfico auxiliar puede cambiar los denominadores.

La matriz oficial pasa de 27 a 29 perfiles y de 135 a **145 campañas**. Mantiene cinco repeticiones y partición por campaña. Su estimación PCAP aumenta solo 3 MB agregados, hasta 33,673,250,000 bytes; el gate de almacenamiento continúa fallando.

## Controles del generador

`http-multi`:

- usa una lista fija `.10/.11/.12` y no acepta destinos proporcionados por el operador;
- permite solamente 1 o 5 solicitudes por destino;
- exige HTTP 200 en cada solicitud;
- conserva target, número de solicitud y código HTTP en la salida;
- no utiliza Kali ni Internet.

## Procedimiento de aplicación

La cuenta `useransible` no posee sudo general, de acuerdo con el endurecimiento previo. Se habilitó privilegio temporal en VM03, se ejecutó:

```bash
cd ansible
../.venv/bin/ansible-playbook playbooks/03-configurar-servicios-servidor.yml \
  --limit ppi-server --ask-become-pass
```

La contraseña no se guardó en inventario, Git ni línea de comandos. Al terminar se eliminó la autorización temporal y `sudo -n id` volvió a fallar para `useransible`, siguiendo el procedimiento usado en G1/G2.

## Gate para aprobar el cambio

1. Netplan, NGINX, dnsmasq y nftables validan sintaxis.
2. `.10/.11/.12` están presentes tras aplicar y después de reiniciar VM03.
3. Cliente llega a las tres por `10.20.0.1`; la respuesta vuelve por `10.30.0.1`.
4. HTTP devuelve 200 en las tres.
5. `.11/.12:22`, `:443`, `:53` y `:5201` no están disponibles.
6. El piloto `CAL-G6-HTTP-MULTI-1-R01` registra tres destinos, SHA correcto y cero drops.
7. El CSV produce un ratio L3 no nulo y la auditoría lo excluye como calibración.

Los siete controles pasaron. La infraestructura multidestino queda **APROBADA para F1 v2**; la campaña completa sigue condicionada al gate de almacenamiento.
