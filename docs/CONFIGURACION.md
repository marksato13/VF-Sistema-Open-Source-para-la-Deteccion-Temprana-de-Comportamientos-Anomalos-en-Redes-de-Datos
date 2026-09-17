# Referencia de configuración

Todo lo que cambia entre una instalación y otra vive en **un solo fichero**:
`configs/cyberflow.toml`. Las unidades de systemd se generan desde él.

```bash
python3 scripts/setup/cyberflow_config.py --comprobar   # valida
python3 scripts/setup/cyberflow_config.py --mostrar     # imprime las unidades
sudo python3 scripts/setup/cyberflow_config.py --escribir
```

Las unidades generadas llevan una cabecera que lo advierte: **no se editan a
mano**, porque la siguiente generación se lleva el cambio por delante. Para
cambiar algo, edite el `.toml` y vuelva a generar.

---

## `[captura]`

| Clave | Qué es |
|---|---|
| `interfaz` | La que recibe el espejo. **Sin dirección IP.** |
| `mac_esperada` | La MAC de esa interfaz. Se documenta aquí porque Linux renumera las interfaces al añadir o quitar adaptadores, y el nombre no es estable |
| `anillo_archivos` · `anillo_segundos` | Búfer en anillo de PCAP. Su producto es la historia disponible: `16 × 15 = 240 s` |
| `directorio` | Dónde viven esos PCAP |
| `filtro_bpf` | Vacío = capturar todo |

### El filtro BPF y las etiquetas VLAN

**Es la trampa más silenciosa de todo el sistema.** Si el espejo conserva la
etiqueta 802.1Q, un filtro de capa 3 escrito de la forma normal **no casa con
nada**:

```toml
filtro_bpf = "ip and host 10.10.60.10"          # NO funciona con tramas etiquetadas
filtro_bpf = "vlan and ip and host 10.10.60.10" # sí
```

El anillo se queda vacío, el motor no puntúa nada y **no hay ningún error en
ninguna parte**. El validador rechaza un filtro que no mencione `vlan`
precisamente por esto.

Con caudales bajos, lo más seguro es dejarlo vacío y filtrar después.

---

## `[red]`

| Clave | Qué es |
|---|---|
| `red_entidades` | El rango del que se extraen las entidades a puntuar. El motor agrupa por IP dentro de esta red |
| `excluir` | Tráfico propio del despliegue, que se captura pero se marca para excluirlo del cálculo |

### Por qué existe `excluir`

Si su sesión de gestión al sensor cruza el mismo enlace espejado, **el sensor se
captura a sí mismo**. Sin excluirlo, el modelo aprende su propio SSH como
tráfico normal.

La recomendación es **no filtrarlo en la captura sino excluirlo en el cálculo**,
y declarar la exclusión: así puede decir «se excluyeron N flujos de gestión, un
X % del total», con la cifra medida. Un filtro invisible en la captura no se
puede defender igual.

---

## `[motor]`

| Clave | Por omisión | Qué es |
|---|---|---|
| `modo` | `"observacion"` | `observacion` puntúa y registra · `bloqueo` añade `--enforce` |
| `paso_segundos` | `10` | Cada cuánto se evalúa una ventana |
| `historia_segundos` | `230` | Cuánta historia pide el motor. **Debe ser menor que el anillo** |
| `umbral` | `1.8126…` | Por debajo es `ALERT`. Sale del manifiesto del modelo |
| `bloqueo_segundos` | `120` | Expiración nativa del bloqueo en `nftables`. Solo en modo bloqueo |

> `historia_segundos` mayor o igual que `anillo_archivos × anillo_segundos`
> significa pedir historia que **ya rotó fuera del búfer**. El validador lo
> rechaza.

### `modo = "bloqueo"` solo si el sensor está en el camino

Con un espejo SPAN el sensor observa pero no enruta: `nftables` en esa máquina
solo afecta a lo que entra y sale de ella misma. El motor decidiría
correctamente y no cortaría nada, **sin dar ningún error**.

El modo `bloqueo` además cambia el endurecimiento de la unidad:
`NoNewPrivileges` pasa a `false`, porque `sudo` necesita escalar al ayudante
`ppi-enforce`. En `observacion` se queda en `true`, que es mejor.

---

## `[rutas]`

| Clave | Qué es |
|---|---|
| `usuario` | Usuario con el que corren el motor y el panel |
| `raiz` | Dónde está clonado el repositorio |
| `entorno` | Nombre del entorno virtual dentro de `raiz` |
| `eve` | Ruta de `eve.json` de Suricata |
| `modelo` · `manifiesto` · `esquema` | Relativos a `raiz` |
| `registro` | Dónde escribe el motor sus decisiones |

---

## `[panel]`

| Clave | Por omisión | Qué es |
|---|---|---|
| `activo` | `false` | Si `true`, genera también `ppi-dashboard.service` |
| `direccion` | `127.0.0.1` | **Déjelo en loopback.** Para verlo desde fuera, túnel SSH |
| `puerto` | `8788` | |

```bash
ssh -L 8788:127.0.0.1:8788 usuario@sensor
```

---

## Lo que valida el comprobador

`--comprobar` no toca la máquina; solo lee el `.toml`. Detecta:

- `red_entidades` o una entrada de `excluir` que no sean redes válidas
- `modo` distinto de `observacion` o `bloqueo`
- `historia_segundos` mayor o igual que el tamaño del anillo
- un `filtro_bpf` de capa 3 que no mencione `vlan`
- rutas de modelo, manifiesto o esquema que no existan *(solo si se ejecuta en
  la propia máquina de destino)*

Devuelve código 1 si algo falla, así que sirve en un `pre-flight` de despliegue.
