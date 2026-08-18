# Primer canario oficial R04 — DNS-VALID-10

Fecha: 4 de agosto de 2026. Campaña: `F1N-DNS-VALID-10-R04`. Partición: `validation`. Estado: **ACEPTADA CON LIMITACIONES**.

## Gate previo de modelado

R04 no comenzó inmediatamente después de R03. Primero se publicó `PM-F1-v1` en el commit `b7769a5ede5c73b85e1b9e78aa73d65dc90e110d`, con revisión adversarial de Claude, requisitos exactos y 43 pruebas. El protocolo resuelve G5↔G6: R01–R03 ajustan pipeline/modelo y R04 completa calibrará sólo el umbral. Ningún score se calcula durante la recolección perfil por perfil.

El verificador versionado revalidó desde un árbol limpio 87 campañas/224 ventanas train, hashes de matriz/esquema, scikit-learn 1.9.0 y tres seeds. `sample_weight=1/n_filas_campaña` no cambió scores ni estructuras de Isolation Forest; por eso la sensibilidad secundaria usará expansión determinista. `verification_pass=true`, `git_dirty=false`.

## Plan y preflight

El dry-run fijó exactamente:

| Elemento | Valor |
|---|---|
| Perfil / repetición | `DNS-VALID-10` / R04 |
| Propósito / partición | `experiment` / `validation` |
| Argumentos | `dns-valid 10` |
| Warm-up / quietud / settle / cooldown | 60 / 70 / 9 / 30 s |
| Matriz SHA-256 | `ad22ce5f8b41110b201f0eeacd2b5f13cc9f945c92cf539e9913e87fefdfa824` |
| Argumentos SHA-256 | `6e32bc5b03ab4d239b1eff1de30de5007f906dda41e8f720240bbf6481496a60` |
| Generador local/remoto | SHA-256 `d4cd42b65f1b22cea0a3f585c2df760af68a8557799c3859eabc803d4f9b4203` |
| Espacio disponible | 127,985,336,320 bytes |

El gate NTP pasó en las cinco VMs; el máximo absoluto fue 0.353 ms en Kali. Ansible confirmó SSH 4/4 como `useransible`. Las NIC externas Sensor/Servidor/Kali/Cliente estaban `DOWN` y sus MAC coincidían con el inventario; ICMP y TCP/22 a `172.17.25.111-.114` quedaron bloqueados.

Suricata, NGINX, dnsmasq, el firewall del Servidor e iperf3 estaban activos. Cliente y Kali resolvieron la DMZ mediante `10.20.0.1`, y el retorno del Servidor usó `10.30.0.1`. El probe DNS devolvió `10.30.0.10`, HTTP `/health` respondió, los contadores Suricata eran cero, el PCAP estaba inactivo y no existían ID, ledger ni lock. Los probes ocurrieron antes de la quietud oficial de 70 s.

## Resultado DNS y correlación

El generador emitió diez veces `10.30.0.10`. PCAP y EVE confirman diez consultas `A server.ppi.lab` y diez respuestas autoritativas `NOERROR`, cada una con `rdata=10.30.0.10`.

| Evidencia | Resultado |
|---|---:|
| Requests / responses DNS EVE | 10 / 10 |
| Respuestas `NOERROR` / destino esperado | 10 / 10 |
| Paquetes PCAP capturados / recibidos / parseados | 20 / 20 / 20 |
| PCAP | 2,324 bytes, un archivo |
| Drops tcpdump | 0 |
| EVE | 29: 20 DNS + 9 stats |
| Alertas / anomalías EVE | 0 / 0 |

El tráfico DNS causal ocurrió entre `20:29:52.909587` y `20:29:53.114473 -05:00`, un intervalo de 0.204886 s. Cada request y response del PCAP coincide en tiempo, IP, puerto e ID con EVE. El filtro sólo contiene Cliente `10.20.0.20`↔Servidor `10.30.0.10`; no aparecen probes de preflight.

Los veinte paquetes IPv4 son menores de 500 bytes, con longitud media 85 y máxima 87. Es correcto para este control DNS ligero. La observación del jurado sobre tráfico pesado ya está cubierta en train por otros estratos; no se debe exigir paquetes grandes a cada perfil ni confundir tamaño pequeño con benignidad.

## Sensor, recursos e integridad

Suricata pasó de 20,164,846 a 20,164,870 paquetes, delta 24 frente a 20 en PCAP. Los cuatro adicionales no están identificados y no se convierten en eventos del escenario ni en pérdida. `kernel_drops`, `kernel_ifdrops`, `decoder_invalid` y `alert_queue_overflow` permanecieron en cero; no hubo reinicio de contador y el checkpoint EVE coincidió en el mismo inode.

El muestreador produjo 53 filas y stderr vacío. CPU de Suricata varió 0–1.51 %, RSS permaneció en 781,720 KiB, memoria disponible en 14,091,660–14,165,264 KiB y load1 en 0.02–0.42. Son observaciones de esta campaña ligera, no límites de capacidad.

Los dos bundles `SHA256SUMS` pasaron completos. El PCAP remoto/local conservó SHA verificado. Los 149/165 bytes de stderr son los banners de lectura/cierre de tcpdump; registran 20 capturados/recibidos y cero drops. `scenario-stderr` y `sensor-timeseries.stderr` están vacíos.

## Feature y vector visto

El extractor leyó 20 observaciones de paquete y 10 de aplicación, y produjo una fila elegible con historia causal de 60 s. Esta selección muestra ocho señales relevantes; el CSV conserva las catorce en el orden contractual:

```text
packet_rate_10s=2.00000000
byte_rate_10s=170.00000000
mean_ip_len_10s=85.00000000
large_ip_ratio_10s=0.00000000
unique_dst_ip_ratio_30s=0.10000000
flow_attempt_rate_10s=1.00000000
unique_dst_port_ratio_30s=0.10000000
dns_nxdomain_ratio_60s=0.00000000
```

Los contadores auxiliares son 20 paquetes, diez intentos y diez queries. El vector de catorce features coincide exactamente con `DNS-VALID-10/R01`, R02 y R03, pero las fechas, PCAP, EVE, puertos, IDs DNS y hashes pertenecen a episodios independientes.

Con la política congelada, esta igualdad no se borra ni se considera fuga operacional. Es el primer vector `seen` de validation y obliga a reportar R04/R05 por visto/no visto. Tampoco se usa para cambiar features, pesos, modelo o umbral durante R04.

## Auditoría agregada y decisión

El ensamblador aceptó 88/145 campañas: R04 1/29, 57 celdas pendientes, cero inválidas y cero advertencias. Las coincidencias entre campañas subieron de 17 a 18 y el contador cruzado de 0 a 1, exactamente por `DNS-VALID-10/R04` contra R01 train. `ready_to_build=false` significa F1 incompleta, no rechazo de la campaña.

**F1N-DNS-VALID-10-R04 ACEPTADA CON LIMITACIONES.** La evidencia causal e integridad pasan; se conserva la discrepancia Suricata+4 no atribuida y la repetibilidad exacta del vector. Siguiente permitido: preflight independiente de `F1N-DNS-VALID-200-R04`. No se puntúa el modelo ni se ejecuta R04 en lote.
