# Inventario del despliegue

Qué máquina hay, con qué dirección, en qué VLAN y en qué modo debe estar cada
interfaz. Lo que **no** debe estar se declara igual de explícitamente que lo que
sí: casi todos los fallos de este despliegue han sido una interfaz en el sitio
equivocado, no una fórmula mal escrita.

Procedencia: *medido* = salida de un comando el 2026-09-23 · *documentado* =
respaldo de configuración · *por crear* = todavía no existe.

---

## 1. Máquinas del sistema

| Máquina | Interfaz | Dirección | VLAN | Modo | Estado |
|---|---|---|---|---|---|
| **cyberflow-sensor** | `ens34` | `10.10.60.11/24` | **60** GESTION | estática · **no promiscua** | *medido* ✅ |
| | `ens37` | **sin dirección** | — troncal espejado | **promiscua** · MAC `00:0c:29:15:7c:02` | *medido* ✅ |
| **srv-dmz** | — | `10.10.30.10` | **30** DMZ | estática | desplegado ✅ |
| **clientes** | (por confirmar) | `.20` gestión + `.21`–`.26` | **20** USUARIOS | estáticas | *por crear* |
| **atacante** | — | `10.10.20.30` | **20** USUARIOS | estática | *por crear* |

Ruta por defecto del sensor: `10.10.60.1`, la VIP CARP de pfSense en la VLAN 60.
Disco: 27 GB libres de 37 *(medido)*.

### Lo que NO debe estar, y por qué

- **`ens37` no lleva dirección IP.** Con una, el sensor sería alcanzable desde
  el troncal espejado y su propio tráfico entraría en su propia captura.
- **`ens34` no está en modo promiscuo.** Es solo gestión.
- **El sensor no tiene pata en la VLAN 20 ni en la 30.** Las ve por el espejo,
  no por enrutamiento. Una pata ahí lo convertiría en participante de lo que
  mide.
- **`clientes` no usa DHCP.** Las seis entidades tienen que ser estables
  durante 72 h. Sus direcciones caen fuera del pool (`10.10.20.50`-`.200`), así
  que no hace falta reserva ni excluir nada.
- **`atacante` está apagada durante la línea base.** Encendida contaminaría el
  entrenamiento, y eso invalida un modelo no supervisado.

---

## 2. Infraestructura ajena — solo lectura

Regla vigente: leer es libre, escribir requiere aprobación explícita.

| Equipo | Dirección | VLAN | Para qué se usa |
|---|---|---|---|
| VM-GESTION (bastión) | `10.10.10.30` | 10 ADMIN | único camino SSH |
| CORE-STACK | `10.10.99.10` | 99 MGMT | leer configuración y la sesión SPAN |
| pfSense-A / B | `10.10.10.2` / `.3` | 10 ADMIN | pasarela de todas las VLAN y DHCP |
| DNS / AD | `10.10.10.20` | 10 ADMIN | DNS de los clientes del laboratorio |
| HV-DATA | `172.17.25.3` | — | hipervisor destino · **sin enlace** |

---

## 3. Punto de observación

```
monitor session 1 source interface Gi1/0/23 , Gi2/0/23
monitor session 1 destination interface Gi2/0/19 encapsulation replicate
```
*(medido 2026-09-22, guardado con `wr`)*

Origen: los **dos** troncales de pfSense, en los dos sentidos (`Both`). El
CORE no enruta entre VLAN —`Vlan99` es su única SVI con dirección—, así que
todo el tráfico entre VLAN sube a pfSense y pasa por el espejo.

Presupuesto: **100 Mb/s**, porque origen y destino negocian a esa velocidad.

Dos consecuencias que no se pueden ignorar:

- **Cada paquete entre VLAN se copia dos veces**, con la misma IP de origen y
  distinta etiqueta. Medido en tráfico real: 4,8 %. Para el tráfico sintético
  del laboratorio, que es entre VLAN al 100 %, será del 100 %.
- **Las respuestas ARP llegan incompletas**: son unidifusión y solo se ven las
  dirigidas al cortafuegos. Las peticiones, al ser difusión, llegan enteras.

---

## 4. Qué se excluye del análisis

En `configs/cyberflow.toml`:

| Exclusión | Motivo |
|---|---|
| `10.10.10.30/32` | el bastión: su SSH cruza el troncal espejado |
| `10.10.60.11/32` | el propio sensor |
| protocolos `112`, `240` | CARP y pfsync: **el 86,3 %** de las tramas de capa 2 *(medido)* |

**Pendiente de añadir**, por lo medido el 2026-09-23: `10.10.30.1`,
`10.10.40.1`, `10.10.60.1` (VIP de pfSense) y `10.10.100.2`, `10.10.100.3`
(PFSENSE_SYNC). Son infraestructura que v2 no puntuaba y que el extractor v3
sí empezaría a puntuar por la vía de la capa 2.

---

## 5. Modo del motor

`modo = "observacion"`. Con un espejo SPAN el sensor **no está en el camino**
del tráfico, así que un bloqueo con nftables sería demostrativo, no efectivo.
Se declara así en la tesis en vez de presentarlo como contención real.

`calibrado_en_esta_red = false`: el umbral viene de otra red. El panel lo
advierte y pide tratar las alertas como ruido. Solo pasa a `true` después de
recalibrar con la línea base propia.

---

## 6. Estado del instalador

| Guion | Qué hace |
|---|---|
| `scripts/setup/instalar.sh` | Instalación completa en un comando |
| `scripts/setup/desinstalar.sh` | Con `--simular` y `--todo`; no toca red, SPAN ni hipervisor |
| `scripts/setup/cyberflow_config.py` | Genera todas las unidades desde el `.toml` |

Réplica en otra VM: clonar → editar `configs/cyberflow.toml` (interfaz, MAC,
usuario, red) → `cyberflow_config.py --comprobar` → `sudo ./instalar.sh` →
verificación final automática.

**Lo honesto sobre su madurez:** funciona, pero está probado **una sola vez en
una sola VM**, y llegó ahí tras fallar ocho veces. Cada fallo destapó algo que
no se habría anticipado escribiéndolo con cuidado: el huevo y la gallina del
modo promiscuo, Suricata sin instalar, `suricata.rules` inexistente, el entorno
virtual creado con el intérprete equivocado, `logs/` ausente dando
226/NAMESPACE, y el panel cableado a un `/home` de otro despliegue.

Una instalación probada una vez no es un instalador replicable. **La segunda VM
limpia es lo que separa esto de poder etiquetar `v1.0.0`.**
