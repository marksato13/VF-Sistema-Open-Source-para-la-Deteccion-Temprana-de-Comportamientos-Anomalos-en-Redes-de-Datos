# Extractores multicapa

Solo biblioteca estándar. PCAP clásico Ethernet, con o sin etiquetas 802.1Q.
Otros linktypes se rechazan en vez de interpretarse en silencio.

| Versión | Features | Estado | Para qué |
|---|---|---|---|
| `extract_multilayer.py` (v1) | 14 | histórico | Pilotos anteriores al contrato G5 |
| `extract_multilayer_v2.py` | 28 | **congelado** | El modelo publicado. No se toca |
| `extract_multilayer_v3.py` | 31 | en desarrollo | v2 + 3 variables de capa 2 |

## Por qué v2 está congelado

`artifacts/model/manifest.json` publica el SHA-256 de los CSV con los que se
entrenó el modelo. Cualquier cambio en v2 —incluso uno que parezca inocuo—
rompe la reproducción bit a bit, y el fallo no aparece hasta el siguiente
`scripts/analysis/verificar_reproduccion.py`. Si hace falta una variable nueva,
va en una versión nueva.

## Qué añade v3

Tres variables de capa 2 que el extractor v2 **no puede** calcular, porque
descarta toda trama que no sea IPv4 y por tanto nunca ve una ARP:

| Feature | Qué mide |
|---|---|
| `arp_request_rate_10s` | Peticiones ARP por segundo cuya SPA es la entidad |
| `unique_src_mac_30s` | MAC de origen distintas para esa IP. Normalmente 1 |
| `mac_ip_binding_changes_60s` | Transiciones de esa MAC en orden temporal |

**Lo que aportan a la tesis:** un barrido de la propia VLAN no cruza el
enrutador, así que no aparece en el espejo como tráfico IP atribuible y las 28
features de v2 lo puntúan como silencio. En capa 2 sí se ve. v3 emite fila para
una entidad que solo ha hecho ARP, con las 28 primeras columnas a cero.

**v3 importa a v2, no lo reimplementa.** Las 28 primeras columnas las calcula
el mismo código congelado, así que son idénticas por construcción y no por
coincidencia. `tests/test_multilayer_v3_l2.py::NoAlteraAV2` lo comprueba fila a
fila contra una ejecución de v2 a solas.

### La VLAN nativa

La sesión SPAN captura en los dos sentidos del troncal del cortafuegos, así que
un paquete entre VLAN aparece **dos veces** con la misma IP de origen: una en la
VLAN del emisor con su MAC real, y otra en la del destino ya reescrita por el
cortafuegos. Sin filtrar, `unique_src_mac_30s` valdría 2 para todo el tráfico
normal entre VLAN y no distinguiría nada.

Cada entidad se ancla a su VLAN nativa, que **no** es la etiqueta más frecuente
—las dos copias empatan—: es la más frecuente entre las tramas cuya MAC de
origen aparece en una sola VLAN. Una MAC vista emitiendo en varias VLAN es un
reenviador. El criterio es "MAC en varias VLAN" y no "MAC con varias IP" a
propósito: la máquina de clientes del laboratorio lleva seis alias sobre una
sola MAC y no es un enrutador.

### Deduplicación del espejo

`deduplicar_espejo()` quita la segunda copia de cada trama que la sesión SPAN
enseña dos veces. Ocurre por dos vías, las dos medidas en esta red:

| Vía | Cómo se reconoce |
|---|---|
| Tráfico **entre VLAN** | La sesión captura en los dos sentidos: se ve al entrar al cortafuegos y al salir hacia la VLAN de destino. Las copias difieren en **exactamente 1 de TTL** |
| **Difusión** y multidifusión | Inunda los dos puertos troncales, y la sesión escucha los dos. Copias idénticas byte a byte |

Medido sobre 6396 paquetes del espejo real: 290 pares, con diferencia de TTL
**0 o 1 y nada más** —bimodal, sin una sola excepción en 237 pares— y
separación máxima de 512 µs. La ventana por omisión es de 5 ms, diez veces eso.

**Por qué importa más de lo que parece.** `tcp_retransmission_ratio_10s` marca
como retransmisión un segmento cuya tupla (protocolo, origen, destino, número
de secuencia) ya apareció. Una copia del espejo encaja exactamente en esa
definición. Medido en el sensor:

```
antes de deduplicar : 0.1488  (100 de 672 segmentos con datos)
despues             : 0.0000  (0 de 572)
```

Las 100 «retransmisiones» eran las 100 copias. El motor leía un 14,88 % de
retransmisión TCP —cifra de red seriamente degradada— que era íntegramente un
artefacto de la captura. *La ventana estaba dominada por tráfico de gestión
propio, así que la magnitud hay que reconfirmarla con la línea base.*

El identificador IP entra en la clave a propósito: los anuncios SSDP salen en
ráfagas con `ip_id` consecutivos separados 25 µs, y sin él la deduplicación se
comería tráfico legítimo. Se conserva la copia de **mayor TTL**, la que aún no
ha cruzado el enrutador: es la que lleva el TTL que puso el emisor, que es lo
que `ttl_mean_10s` dice medir.

No toca el extractor congelado: filtra su **entrada**, que es alcance, no
fórmula — el mismo criterio que la exclusión de CARP y pfsync. El motor lo
aplica por omisión y lo cuenta en `duplicados_espejo`; `--sin-deduplicar` lo
desactiva para poder medir la diferencia.

### Dos límites declarados

- **Respuestas ARP incompletas.** Las peticiones son difusión y llegan enteras;
  las respuestas son unidifusión y solo llegan las dirigidas al cortafuegos. Por
  eso la feature se define sobre peticiones y no sobre el par.
- **DHCP produce cambios de vínculo legítimos.** La VLAN 20 tiene DHCP
  (`10.10.20.50`-`.200`). Si la línea base no contiene rotación normal de
  arrendamientos, el modelo marcará cada renovación como suplantación.

## Uso

```bash
python3 scripts/features/extract_multilayer_v3.py \
  --pcap /var/lib/ppi-motor-capture/*.pcap \
  --eve /var/log/suricata/eve.json \
  --campaign-id linea-base-72h \
  --entity-network 10.10.0.0/16 \
  --output artifacts/features/linea-base-72h/multilayer-v3.csv
```

`--entity-network` no hereda el valor de v2 a propósito: v2 conserva por
historia el `10.20.0.0/24` del laboratorio antiguo, y heredarlo dejaría el CSV
vacío sin dar ningún error.

## Pruebas

```bash
python3 -m unittest tests.test_multilayer_features       # v1
python3 -m unittest tests.test_multilayer_v2_features    # v2
python3 -m unittest tests.test_multilayer_v3_l2          # v3 y capa 2
```
