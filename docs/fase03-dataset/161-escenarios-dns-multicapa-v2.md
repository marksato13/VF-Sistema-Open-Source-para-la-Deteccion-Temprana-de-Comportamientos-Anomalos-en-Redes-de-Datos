# Escenario `dns-multi` — diversidad de nombres DNS (v2, sin ejecutar)

Fecha: 12 de agosto de 2026. Este documento describe código nuevo, no evidencia
de campaña. `dns-multi` fue añadido a `scripts/f1/run-benign.sh` y habilitado
en `scripts/campaign/run-f1.sh`, publicado en Git como commit `77cd330`. **No se ha ejecutado ninguna campaña
`dns-multi`, no tiene `campaign_id`, no aparece en
`configs/campaigns/f1-normal-v2.json` y no forma parte del dataset
`f1-normal-v2` ni de ningún modelo entrenado.**

## Objetivo

Los escenarios DNS existentes (`dns-valid`, `dns-nxdomain`, `dns-mixed`)
consultan siempre el mismo nombre (`server.ppi.lab` o nombres inexistentes
generados) contra el mismo destino `10.30.0.10`. Ese diseño no ejercita
`unique_dst_ip_ratio_30s` con tráfico DNS real, porque todas las respuestas
apuntan a una sola IP y el propio backend de resolución es la misma máquina.

`dns-multi` responde a la brecha identificada en el plan de expansión
`docs/fase03-dataset/160-plan-expansion-dataset-multicapa-v2.md` (grupo
N2, "DNS con dominios únicos, repetidos... y respuestas de distintos
tamaños"): genera consultas DNS legítimas hacia **varios nombres distintos**
que resuelven a **direcciones IPv4 distintas**, para producir episodios donde
la diversidad de destino observada en L3 (`unique_dst_ip_ratio_30s`) y la
futura diversidad de nombre en L7 (`unique_dns_name_ratio_60s`, propuesta en
el plan v2, todavía no implementada en el extractor) puedan diferenciarse de
un acceso repetitivo a un único host. No introduce NXDOMAIN ni ningún patrón
etiquetado como anómalo: todas las consultas esperan respuesta `NOERROR` con
registro `A` válido.

## Parámetros

Código: `scripts/f1/run-benign.sh:135-149`.

```bash
scripts/f1/run-benign.sh dns-multi <count>
```

`count` es un entero cerrado a cuatro valores (`scripts/f1/run-benign.sh:137`):

| Valor permitido | Motivo |
|---:|---|
| 4 | una vuelta completa al ciclo de 5 nombres (queda incompleta, ver abajo) |
| 10 | dos vueltas completas |
| 50 | diez vueltas completas |
| 200 | cuarenta vueltas completas |

Cualquier otro valor produce `ERROR: conteo dns-multi permitido: 4, 10, 50 o
200` y salida 2. El script hereda la guarda global de destino: `TARGET_IP` debe
ser exactamente `10.30.0.10` (`scripts/f1/run-benign.sh:4-8`); no hay forma de
apuntar `dns-multi` a otro resolutor sin modificar el script y romper esa
guarda.

## Nombres consultados y resolución round-robin

El script itera un arreglo fijo de cinco nombres en el mismo orden en cada
ejecución (`scripts/f1/run-benign.sh:138-141`):

```bash
hostnames=(server.ppi.lab web.ppi.lab web-a.ppi.lab web-b.ppi.lab iperf.ppi.lab)
```

La consulta `i` usa `hostnames[(i-1) % 5]`, es decir, round-robin puro y
determinista. Con `count=4` el ciclo no se completa (faltan `iperf.ppi.lab`);
con `count=10`, `50` y `200` el ciclo se completa un número entero de veces y
los cinco nombres quedan igualmente representados.

Estos nombres se resuelven en `configs/server/dnsmasq-ppi.conf:8-12`, que es
la única fuente de verdad de las direcciones:

| Nombre | Dirección A | Comentario |
|---|---|---|
| `server.ppi.lab` | `10.30.0.10` | mismo destino que `dns-valid` |
| `web.ppi.lab` | `10.30.0.10` | alias del mismo host físico |
| `web-a.ppi.lab` | `10.30.0.11` | VIP lógica adicional (una sola VM, ver `CLAUDE.md`) |
| `web-b.ppi.lab` | `10.30.0.12` | VIP lógica adicional |
| `iperf.ppi.lab` | `10.30.0.10` | mismo host físico que `server.ppi.lab` |

Es decir: cinco nombres distintos resuelven a solo **tres direcciones IPv4**
distintas (`.10`, `.11`, `.12`), todas dentro de la misma VM03 física —la
misma limitación de "identidades lógicas, no hosts físicos" que ya aplica a
`HTTP-MULTI-1`/`HTTP-MULTI-5`. Cualquier análisis de `unique_dst_ip_ratio_30s`
producido por este escenario debe citarse con esa limitación explícita.

## Dependencia exclusiva del dnsmasq interno

Todas las consultas usan `dig +short "@$TARGET_IP" "$hostname" A`
(`scripts/f1/run-benign.sh:142`), es decir, se fuerza el servidor `10.30.0.10`
como resolutor explícito en cada llamada; no se usa `/etc/resolv.conf` del
Cliente ni ningún forwarder externo. El servicio que responde es el `dnsmasq`
desplegado en VM03 (`configs/server/dnsmasq-ppi.conf`), sin salida a Internet,
consistente con la restricción del laboratorio de mantener las NIC externas de
VM02–VM05 desconectadas durante campañas oficiales.

El script valida cada respuesta antes de continuar
(`scripts/f1/run-benign.sh:143-147`):

1. extrae la primera línea de `dig +short` que matchea un patrón IPv4;
2. si no hay ninguna dirección IPv4 en la salida, aborta con
   `ERROR: $hostname no devolvió respuesta A desde $TARGET_IP` y código 1.

Esto significa que una ejecución exitosa (`exit 0`) ya certifica que las
`count` consultas obtuvieron una respuesta `A` válida; no certifica por sí
sola `NOERROR` en el sentido EVE (ver siguiente sección) ni la ausencia de
paquetes fuera de la ventana de captura.

## Evidencia esperada

### JSONL en stdout

Por cada consulta exitosa el script emite una línea JSON a stdout
(`scripts/f1/run-benign.sh:148`):

```json
{"scenario":"dns-multi","query":3,"hostname":"web-a.ppi.lab","address":"10.30.0.11"}
```

Este JSONL es el mismo mecanismo de evidencia liviana que usan `http-multi`,
`tcp-refused` y `mixed-light`: no reemplaza el PCAP ni el EVE, sirve para
reconciliar cuántas consultas se completaron y contra qué nombre/dirección,
igual que se hizo en los canarios `HTTP-MULTI-1`/`HTTP-MULTI-5` para las VIP.

### PCAP y EVE

`dns-multi` no tiene captura propia: al integrarse a `scripts/campaign/run-f1.sh`
(línea 18, ya modificada para aceptar el escenario) hereda el mismo
orquestador que el resto de la matriz F1 — helper PCAP raíz en `ens35` con
filtro LAN↔DMZ, snaplen completo, EVE de Suricata y reconciliación de
`kernel_drops`/`decoder_invalid` en cero, tal como se exige para cualquier
campaña aceptada. Como aún no se ejecutó ninguna captura, no existen hashes,
`campaign_id`, bundle ni entrada de ledger que citar en este documento.

Por analogía directa con `dns-valid`/`dns-mixed` (mismo protocolo, mismo
puerto UDP/53, mismo destino físico), se espera que el EVE contenga un evento
`dns` por consulta más los `stats` periódicos de Suricata, y que el PCAP
contenga dos paquetes UDP por consulta (solicitud + respuesta). Esto es una
expectativa de diseño, no evidencia observada.

## Capas OSI involucradas

| Capa | Qué aporta `dns-multi` | Feature relacionada hoy (`multilayer-v1`) |
|---|---|---|
| L3 (red) | tres direcciones IPv4 destino distintas por episodio, en vez de una sola | `unique_dst_ip_ratio_30s` |
| L4 (transporte) | consultas UDP/53 repetidas hacia el mismo puerto destino en las tres IP | `unique_dst_port_ratio_30s` (esperado bajo: el puerto siempre es 53) |
| L7 (aplicación) | nombres de dominio distintos, todos con respuesta `NOERROR`/registro `A` válido | `dns_nxdomain_ratio_60s` (esperado 0.0 porque no hay NXDOMAIN en este escenario) |

Ninguna feature de `multilayer-v1` mide directamente la diversidad de
*nombres* consultados (solo de IP destino y de puerto). El plan v2 propone
`unique_dns_name_ratio_60s` y `dns_query_rate_60s`
(`docs/fase03-dataset/160-plan-expansion-dataset-multicapa-v2.md`,
sección "Esquema de features v2 propuesto") precisamente para capturar esa
señal; ninguna de las dos está implementada en
`scripts/features/extract_multilayer.py` a la fecha de este documento. Hasta
que exista esa feature y su prueba de ablación, `dns-multi` solo puede
evaluarse con el vector de 14 features vigente, en el que su aporte adicional
frente a `dns-valid` se reduce a la diversidad de IP destino.

## Criterio de aceptación (para cuando se ejecute)

Siguiendo el mismo protocolo aplicado a todos los canarios F1N previos, una
ejecución de `dns-multi` solo podrá incorporarse al dataset si:

1. pasa los nueve gates del preflight continuo (`scripts/f1/preflight_profile.sh`)
   sobre un commit Git limpio y sincronizado;
2. termina con código de salida 0 y produce exactamente `count` líneas JSONL,
   una por consulta, con dirección IPv4 no vacía en cada una;
3. el PCAP capturado reconcilia el número de paquetes esperado (2 × `count`
   como mínimo, solicitud + respuesta) contra los recibidos por el filtro y
   los parseados, con `kernel_drops=0`;
4. Suricata reporta `drops=0`, `ifdrops=0`, `decoder_invalid=0` y
   `capture.kernel_packets` sin overflow;
5. el EVE extraído contiene un evento `dns` `NOERROR` por consulta, sin
   `NXDOMAIN`, y su volumen es reconciliable contra el PCAP (se documentará
   cualquier delta Suricata/PCAP no atribuido, como ha ocurrido en otros
   escenarios DNS);
6. la extracción produce al menos una fila con `history_coverage_s ≥ 60` para
   ser `eligible_training=true`, calculada con
   `scripts/features/extract_multilayer.py` contra el esquema `multilayer-v1`
   vigente (no v2, que aún no existe);
7. hashes de manifest, PCAP, EVE, CSV de features y ledger verificados con
   `sha256sum -c`;
8. si se busca incorporar como perfil oficial de la matriz, debe añadirse
   primero a `configs/campaigns/f1-normal-v2.json` con un `id` explícito (por
   ejemplo `DNS-MULTI-10`), repetido R01–R05 igual que el resto de perfiles, y
   pasar por revisión cruzada Codex/Claude según el flujo de `CLAUDE.md`.

## Estado y limitaciones

- El código está implementado y sintácticamente disponible en ambos scripts,
  pero **no auditado por ejecución real**: no hay preflight, captura, EVE ni
  extracción asociados a `dns-multi`.
- `configs/campaigns/f1-normal-v2.json` no contiene ningún perfil `dns-multi`;
  por lo tanto el ensamblador `scripts/dataset/build_f1_dataset.py` lo
  ignorará por completo hasta que se agregue explícitamente.
- La diversidad de IP lograda (tres direcciones) sigue siendo diversidad
  lógica dentro de una sola VM física, la misma limitación ya documentada para
  `HTTP-MULTI-1`/`HTTP-MULTI-5` y las VIP `.10/.11/.12`.
- No debe interpretarse este documento como aceptación de una campaña: es
  documentación de diseño de un escenario nuevo, previa a cualquier
  preflight u orden de ejecución.
