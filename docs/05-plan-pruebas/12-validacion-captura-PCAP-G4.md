# Validación de captura PCAP — G4

Fecha: 21 de julio de 2026. Alcance: DNS benigno y descarga HTTP de 10 MB desde VM05 hacia VM03, capturados sobre `ens35` de VM02.

## Decisión

**G4 PASS.** El orquestador conserva un PCAP completo y acotado, verifica su hash antes/después de la transferencia, lee el archivo completo, compara paquetes capturados/parseados y rechaza evidencia incompleta. Este gate valida el mecanismo de captura; todavía no valida el dataset ni las 14 features.

## Iteraciones

| Campaña | Commit | Resultado | Decisión |
|---|---|---|---|
| `CAL-G4-DNS-001` | `c666efb` | fallo seguro antes del escenario | `tcpdump` no podía atravesar el directorio padre después de bajar privilegios; no se generó tráfico |
| `CAL-G4-DNS-002` | `a395b77` | completada | PCAP DNS correcto; confirmó cierre, copia, tamaños y drops |
| `CAL-G4-HTTP-001` | `399f5fa` | completada | confirmó SHA remoto/local y tráfico legítimo con paquetes IP grandes |
| `CAL-G4-DNS-003` | `3840d64` | completada | validó el resumen automático de longitudes y la igualdad capturados/parseados |

El primer intento dejó un bloqueo local porque el `ERR trap` no limpió ese camino de fallo. Antes de retirarlo se comprobó: ID exacto `CAL-G4-DNS-001`, ausencia de sampler, estado PCAP `inactive` y ausencia de proceso `tcpdump`. Se eliminó únicamente el archivo de bloqueo y su directorio vacío; la evidencia parcial se conservó. `start.sh` ahora limpia explícitamente si el inicio PCAP falla.

La causa del fallo de escritura no fue AppArmor: el perfil permitía extensiones `.pcap0`. El directorio padre era `root:useransible 0750`, por lo que el proceso ya reducido a `tcpdump` no podía atravesarlo. Se corrigió a `root:root 0711`; los subdirectorios siguen privados y solo pasan a grupo `useransible` después del cierre.

## DNS final: `CAL-G4-DNS-003`

| Control | Resultado |
|---|---:|
| commit limpio | `3840d6461de2d300d2fe9d80be456f3059b24e0a` |
| estado | `completed`, `evidence.complete=true` |
| PCAP capturados / parseados | 6 / 6 |
| tamaño remoto / local | 714 / 714 bytes |
| SHA-256 remoto/local | `OK` |
| drops de tcpdump | 0 |
| PCAP inválidos | 0 |
| límite de anillo alcanzado | no |
| drops/ifdrops de Suricata | 0 / 0 |
| errores de decodificación / overflow | 0 / 0 |
| muestras del Sensor | 9 |
| EVE extraído/esperado | 8 / 8 |

Los seis paquetes IPv4 fueron pequeños, como corresponde a tres consultas y tres respuestas DNS. Esto confirma que el resumen no fuerza artificialmente la distribución objetivo.

## HTTP legítimo: `CAL-G4-HTTP-001`

La descarga devolvió HTTP 200, 10,485,760 bytes, 1.504051 segundos y 6,971,678 B/s según curl. La velocidad puede incluir el burst inicial de curl y se interpreta como resultado de esta ejecución, no como límite exacto del servidor.

| Control | Resultado |
|---|---:|
| commit limpio | `399f5fa40f9599de9bd7d9bace66877a82eb117e` |
| PCAP capturados | 8,484 |
| tamaño remoto / local | 11,181,846 / 11,181,846 bytes |
| SHA-256 remoto/local | `OK` |
| drops de tcpdump | 0 |
| paquetes Suricata durante la ventana | 8,486 |
| drops/ifdrops de Suricata | 0 / 0 |
| muestras del Sensor | 10 |
| EVE extraído/esperado | 4 / 4 |

Distribución de longitud total IPv4 recalculada desde el PCAP:

| Rango | Paquetes | Porcentaje |
|---|---:|---:|
| menor que 500 bytes | 1,242 | 14.6393 % |
| 500–1500 bytes | 7,242 | 85.3607 % |
| mayor que 1500 bytes | 0 | 0 % |
| exactamente 1500 bytes | 7,241 | 85.3489 % |

Promedio: 1,287.99 bytes. Máximo: 1,500 bytes. Esto responde directamente a la observación del jurado: el sistema ya puede generar y demostrar tráfico legítimo cuyo rango incluye paquetes grandes sin etiquetarlos por ese único atributo como ataque.

La diferencia 8,486 de Suricata frente a 8,484 de tcpdump es válida: Suricata cuenta todo lo observado en `ens35`, mientras el PCAP aplica el filtro estricto PPI-LAN↔PPI-DMZ. No se debe exigir igualdad entre contadores con filtros distintos. Dentro del PCAP sí se exige igualdad entre `packets_captured` y `total_ipv4_packets`.

## Integridad y residuos

En las campañas aceptadas:

- la lectura completa de cada PCAP terminó sin error;
- `pcap-remote-SHA256SUMS` se calculó en VM02 antes de copiar;
- `pcap-transfer-verification.txt` devolvió `OK` en VM01;
- `SHA256SUMS` validó todos los artefactos de la campaña;
- no quedó `.active`, sampler ni proceso tcpdump;
- el helper informó `inactive` al final.

Los originales permanecen en `/var/lib/ppi-captures/<ID>/` del Sensor. No se eliminan hasta definir y comprobar el procedimiento de respaldo/retención.

## Limitaciones

- El cálculo actual usa la salida estable en inglés de tcpdump y longitud total IPv4. Antes de congelar el extractor se comparará contra una biblioteca de parsing binario y PCAPs de prueba.
- La campaña HTTP es una sola repetición de calibración y no entra al dataset.
- 85.36 % no es una propiedad universal del tráfico HTTP; describe este archivo, este ritmo y esta ejecución.
- El PCAP contiene payload sintético completo. No puede publicarse sin revisión de privacidad.
- Aún faltan concurrencia, HTTPS, DNS variado, SSH/SFTP, iperf y tráfico mixto.

## Siguiente gate

G5 definirá las 14 features con fórmula, unidad, ventana, fuente, valores faltantes, costo en línea y riesgo de fuga. Como mínimo deberá incluir señales L3, L4 y L7 reales. Solo las variables implementadas y verificadas contra PCAP/EVE podrán entrar al modelo candidato.
