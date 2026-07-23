# Contexto de trabajo para Claude Code

## Propósito

Este repositorio documenta y construye la versión final de un sistema open source para la detección temprana de comportamientos anómalos en redes de datos. Es un proyecto ingenieril desplegado en un laboratorio virtualizado sobre VMware ESXi.

Repositorio oficial:

```text
https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos.git
```

Remoto esperado: `origin`. Rama estable: `main`.

Claude debe trabajar como revisor técnico adversarial y segundo ingeniero. Codex actúa principalmente como implementador y operador del laboratorio. El objetivo no es que ambos produzcan respuestas similares, sino utilizar revisión cruzada para encontrar errores antes de las pruebas y la defensa ante el jurado.

## Lectura obligatoria antes de opinar o modificar

Al comenzar una sesión:

1. Ejecutar `git status --short --branch` y no sobrescribir cambios ajenos.
2. Leer `docs/01-infraestructura-virtual/README.md`.
3. Leer `docs/02-mejoras-observadas-por-el-jurado/README.md`.
4. Leer `docs/03-procedimiento-ansible/README.md`.
5. Leer `ansible/README.md`, el inventario y los playbooks relacionados con la tarea.
6. Distinguir entre diseño planificado, configuración aplicada y evidencia validada.
7. Ejecutar `git remote -v` y confirmar que `origin` apunta al repositorio oficial antes de publicar.

No asumir que una tarea está completada solo porque está descrita. Buscar la evidencia registrada y, cuando exista acceso autorizado, proponer una prueba reproducible.

## Arquitectura actual

| VM | Función | PPI-MGMT | PPI-LAN | PPI-DMZ |
|---|---|---|---|---|
| VM01 | Administración, Ansible, Codex y Claude Code | `10.10.10.10` | — | — |
| VM02 | Sensor, router, Suricata y motor ML | `10.10.10.20` | `10.20.0.1` | `10.30.0.1` |
| VM03 | Servidor protegido | `10.10.10.30` | — | `10.30.0.10` |
| VM04 | Kali, generación controlada de ataques | `10.10.10.40` | `10.20.0.100` | — |
| VM05 | Cliente legítimo y tráfico pesado | `10.10.10.50` | `10.20.0.20` | — |

Flujo experimental:

```text
Cliente 10.20.0.20 ─┐
                     ├─► Sensor 10.20.0.1 / 10.30.0.1 ─► Servidor 10.30.0.10
Kali 10.20.0.100 ───┘
```

El Sensor tiene `ip_forward=1` y una política de reenvío con nftables. Cliente y Kali poseen una ruta persistente a `10.30.0.0/24` mediante `10.20.0.1`. El Servidor posee una ruta explícita de retorno a `10.20.0.0/24` mediante `10.30.0.1`.

Las NIC externas de `172.17.25.0/24` todavía existen para instalación y recuperación. El bypass ya no es hipotético: VM01 alcanzó TCP/22 del Servidor por `172.17.25.112` sin cruzar el Sensor. Todas las NIC externas de VM02–VM05 deben permanecer desconectadas en ESXi durante campañas oficiales; VM01 conserva Internet/RustDesk y administra el laboratorio por PPI-MGMT.

## Estado validado

- Acceso SSH mediante la cuenta técnica `useransible` y claves Ed25519.
- Conectividad administrativa con las cuatro VMs.
- Sensor: 6 vCPU, 16 GiB de RAM y disco virtual de 160 GiB; raíz ampliada a aproximadamente 154 GiB.
- Servidor: 2 vCPU, 4 GiB de RAM y disco virtual de 120 GiB; raíz ampliada a aproximadamente 115 GiB.
- Kali: 4 vCPU, aproximadamente 6 GiB de RAM y disco de 60 GiB.
- Cliente: 4 vCPU, 8 GiB de RAM y disco de 100 GiB; raíz ampliada a aproximadamente 98 GiB.
- Todas las VMs usan `America/Lima` y NTP sincronizado.
- El Sensor `10.10.10.20` sirve como referencia NTP interna.
- Enrutamiento Cliente/Kali hacia Servidor probado mediante ICMP, TCP/22, traza y contadores de nftables.
- Suricata 8.0.3 está instalado como IDS AF_PACKET sobre `ens35`, con `HOME_NET=[10.30.0.0/24,10.20.0.20/32]`, Emerging Threats Open, EVE JSON y una regla local de validación.
- La captura se validó con alertas ICMP y un evento HTTP completo. Sensor y Servidor superaron reinicios controlados con configuración persistente; todavía faltan ataques reales, protocolos restantes y pruebas de carga.
- La calibración segura fijó techos de F1 en 200 Mbit/s TCP, 50 Mbit/s UDP y 20 MB/s por transferencia HTTP/HTTPS; todas las pruebas acotadas posteriores registraron cero drops de Suricata.
- Existe un orquestador reproducible en `scripts/campaign/`: manifiesto, inventario, contadores, serie temporal del Sensor, segmento EVE y hashes por campaña. Los artefactos runtime permanecen fuera de Git.
- En VM02–VM05, `useransible` puede ejecutar únicamente el reinicio exacto `/usr/bin/systemctl reboot --no-wall`; en el Sensor también puede usar los helpers versionados `ppi-suricata-metrics` y `ppi-pcap-control`. No dispone de sudo general ni de permiso directo sobre `tcpdump`; la prueba negativa con `/usr/bin/id` falla en las cuatro VMs.
- G4 incorpora PCAP por campaña mediante un helper raíz que fija `ens35`, filtro LAN↔DMZ, snaplen completo y rotación máxima aproximada de 2.048 GB. El diseño y riesgos están en `docs/05-plan-pruebas/11-diseno-captura-PCAP-G4.md`.
- G4 pasó con DNS y HTTP. En `CAL-G4-HTTP-001`, 7,242 de 8,484 paquetes IPv4 (85.36 %) midieron 500–1500 bytes, con cero drops y SHA remoto/local verificado. Resultados: `docs/05-plan-pruebas/12-validacion-captura-PCAP-G4.md`.
- G5 define `multilayer-v1`: 14 features causales por IP iniciadora, con ventanas de 10/30/60 s y tres señales L7 pasivas. Diccionario: `docs/06-features-modelado/01-diccionario-multicapa-G5.md`; extractor: `scripts/features/`.
- G5 pasó pruebas sintéticas, regresión HTTP y una campaña DNS con warm-up de 60 s. La fila resultó `eligible_training=true`, pero conserva propósito `calibration` y no entra al dataset. Evidencia: `docs/06-features-modelado/02-validacion-extractor-G5.md`.
- G6 usa `f1-normal-v2`: 29 perfiles, cinco repeticiones y partición fija R01–R03/R04/R05. `v1` queda preservada para cuatro pilotos DNS/HTTP/RST/TLS. `v2` añadió HTTP hacia las VIP DMZ `.10/.11/.12`; persistieron tras reinicio y el piloto obtuvo `unique_dst_ip_ratio_30s=1.0` con cero drops. Son diversidad lógica en una sola VM, no tres hosts físicos. El gate de disco falló en ese piloto histórico y luego se resolvió con el volumen dedicado descrito abajo. Evidencia: `docs/07-dataset-campanas/05-validacion-diversidad-L3-v2.md`.
- El ensamblador `scripts/dataset/build_f1_dataset.py` exige las 145 campañas `v2`, verifica bundles, recalcula matriz/esquema desde el commit, rechaza calibraciones y reconstruye el split por repetición. En el volumen oficial reporta 15 aceptadas (`DNS-MIXED-20-2/R01`, los ocho tamaños HTTP/HTTPS R01, `HTTP-404-5/R01`, `TLS-SESSIONS-20/R01`, `HTTP-MULTI-1/R01`, `HTTP-MULTI-5/R01`, `HTTP-C2/R01` y `HTTP-C4/R01`), 0 inválidas, 0 advertencias y 130 faltantes; los cinco pilotos históricos permanecen excluidos en la raíz heredada. Revisión inicial: `docs/04-revisiones-claude/2026-07-21-ensamblador-F1.md`.
- El gate G3 del orquestador pasó con `CAL-F1-DNS-003`: 6 paquetes, cero drops/errores/overflow, 7 registros EVE exactos y 7 muestras del Sensor. Esta ejecución es calibración y no pertenece al dataset.
- VM01 conserva su disco raíz de 70 GiB y ya posee un segundo VMDK thin de 150 GiB: ext4 por UUID en `/srv/ppi-evidence`, aproximadamente 140 GiB disponibles. El montaje persistió tras reiniciar VM01 con el mismo UUID y opciones `rw,nosuid,nodev,noexec,noatime`; RustDesk volvió `active/enabled`. Los gates de capacidad e identidad de F1 están en PASS. Diseño y evidencia: `docs/08-almacenamiento/01-disco-evidencias-vm01.md`.
- La auditoría inicial G7 confirmó el bypass: después del reinicio, VM03 recuperó `ens34=172.17.25.112` y VM01 alcanzó SSH directamente sin cruzar la captura `ens35` del Sensor. Ese estado histórico **NO APTO** está en `docs/05-plan-pruebas/13-auditoria-preexperimental-G7.md`; revisión inicial: `docs/04-revisiones-claude/2026-07-22-gate-preexperimental-G7.md`.
- G7 está **APTO PERSISTENTE**: VM03 reinició con un `boot_id` nuevo, `ens34` siguió `DOWN/NO-CARRIER`, `.112` no reapareció y continuó bloqueada desde VM01. Persistieron PPI-MGMT, retorno DMZ, servicios, NTP, VIP, restricciones y el camino Cliente/Kali→Sensor→Servidor; Suricata terminó con cero drops/errores. Se autoriza avanzar canario por canario, con preflight y auditoría entre ejecuciones; no el lote completo. Evidencia: `docs/05-plan-pruebas/15-validacion-persistencia-G7.md`; revisión condicional previa: `docs/04-revisiones-claude/2026-07-22-cierre-operacional-G7.md`.
- El primer canario oficial `F1N-DNS-MIXED-20-2-R01` fue aceptado: 44/44 paquetes, 20 NOERROR + 2 NXDOMAIN, delta Suricata 48, 54 EVE exactos, cero drops/errores, una fila elegible y `dns_nxdomain_ratio_60s=2/22`. Evidencia: `docs/07-dataset-campanas/06-primer-canario-oficial-F1.md`.
- El segundo canario `F1N-HTTP-10MB-R01` también fue aceptado: descarga HTTP 200 de 10,485,760 bytes, PCAP de 11,142,194 bytes, 7,912/7,912 paquetes y cero drops. 7,248 paquetes (91.6077 %) midieron 500–1500 bytes y la fila benigna obtuvo `large_ip_ratio_10s=0.91607685`. EVE limitó la inspección del archivo a 102,400 bytes (`fileinfo.state=TRUNCATED`), pero la descarga y el PCAP no fueron truncados; no afirmar inspección completa de contenido. El ensamblador suma 2 aceptadas y 143 faltantes. Evidencia: `docs/07-dataset-campanas/07-canario-HTTP-10MB-F1.md`.
- El tercer canario `F1N-HTTP-100MB-R01` fue aceptado: HTTP 200 de 104,857,600 bytes, PCAP de 111,438,325 bytes, 79,114/79,114 paquetes, 91.6172 % entre 500–1500 bytes, dos ventanas elegibles y cero drops. Suricata llegó a 21.62 % CPU y 776,248 KiB RSS sin presión. El límite `fileinfo=102400/TRUNCATED` se mantiene: no afirmar inspección completa del cuerpo. El ensamblador suma 3 aceptadas y 142 faltantes. Claude/Haiku emitió ACEPTAR, con una palabra “calibración” corregida contra manifiesto y ledger. Evidencia: `docs/07-dataset-campanas/08-canario-HTTP-100MB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-100MB-F1.md`.
- El cuarto canario `F1N-HTTP-500MB-R01` fue aceptado: 524,288,000 bytes HTTP 200, dos PCAP íntegros de 554,956,808 bytes, 368,467/368,467 paquetes, 98.3499 % en 500–1500 bytes, cuatro filas elegibles y cero drops. CPU máxima 26.20 %, RSS 776,372 KiB. Los 6,080 paquetes pequeños son todos TCP, 6,075 sin payload y cero fragmentados. El ensamblador suma 4 aceptadas y 141 faltantes. Claude/Haiku emitió ACEPTAR con observaciones, cerradas contra CSV y PCAP. Evidencia: `docs/07-dataset-campanas/09-canario-HTTP-500MB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-500MB-F1.md`.
- El quinto canario `F1N-HTTP-1GB-R01` fue aceptado con no conformidad cerrada: 1,073,741,824 bytes HTTP 200, tres PCAP íntegros de 1,136,327,873 bytes, 751,835/751,835 paquetes, 98.7155 % en 500–1500 bytes, seis filas elegibles y cero drops. Un flow `/health` previo fue emitido dentro de EVE por timeout, pero empezó antes, no está en PCAP, el extractor ignora flows y todas las ventanas empiezan después de la campaña. Claude/Haiku condicionó la aceptación a esa prueba, que pasó. Desde el commit posterior, el runner aplica 70 s de quietud previa oficial sin cambiar matriz/esquema. Ensamblador: 5 aceptadas, 140 faltantes. Evidencia: `docs/07-dataset-campanas/10-canario-HTTP-1GB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-1GB-F1.md`.
- El sexto canario `F1N-HTTPS-10MB-R01` fue aceptado con limitaciones: 10,485,760 bytes HTTPS 200 confirmados por Cliente, PCAP íntegro de 11,130,372 bytes, 7,608/7,608 paquetes, 95.4127 % en 500–1500 bytes, dos filas elegibles, `tls_session_rate_60s=1/60` y cero drops. EVE observó TLS 1.3 con JA3/JA3S/JA4, pero no HTTP/fileinfo cifrado. El certificado es autofirmado y `curl` usa `--insecure`; no representa PKI productiva. Un flow IPv6 link-local nacido durante la quietud quedó en EVE crudo pero fuera de PCAP/features. Claude/Haiku emitió ACEPTAR CONDICIONADO y las condiciones se documentaron. Ensamblador: 6 aceptadas, 139 faltantes. Evidencia: `docs/07-dataset-campanas/11-canario-HTTPS-10MB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTPS-10MB-F1.md`.
- El séptimo canario `F1N-HTTPS-100MB-R01` fue aceptado con limitaciones: 104,857,600 bytes HTTPS 200, PCAP íntegro de 111,210,058 bytes, 74,858/74,858 paquetes, 96.9502 % en 500–1500 bytes, dos filas elegibles, una sesión TLS 1.3 y cero drops. Dos flows mDNS nacidos durante la quietud quedaron fuera del PCAP/features. Claude/Haiku autorizó HTTPS 500 MB condicionado a integridad; se corrigió su mención de fileinfo porque HTTPS no produjo uno y se conserva `tls_session_rate_60s` como L7 pasiva. Ensamblador: 7 aceptadas, 138 faltantes. Evidencia: `docs/07-dataset-campanas/12-canario-HTTPS-100MB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTPS-100MB-F1.md`.
- El octavo canario `F1N-HTTPS-500MB-R01` fue aceptado con limitaciones: 524,288,000 bytes HTTPS 200, dos PCAP íntegros de 555,929,941 bytes, 371,438/371,438 paquetes, 97.7033 % en 500–1500 bytes, tres filas elegibles, TLS 1.3 y cero drops. EVE quedó limpio: 16 stats y un TLS. Claude/Haiku pidió concurrencia para HTTPS 1 GB; se mantiene el contrato de una sola transferencia y la diversidad se medirá separadamente con `TLS-SESSIONS-20`. Ensamblador: 8 aceptadas, 137 faltantes. Evidencia: `docs/07-dataset-campanas/13-canario-HTTPS-500MB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTPS-500MB-F1.md`.
- El noveno canario `F1N-HTTPS-1GB-R01` fue aceptado: 1,073,741,824 bytes HTTPS 200, tres PCAP íntegros de 1,138,215,605 bytes, 757,999/757,999 paquetes, 98.0435 % en 500–1500 bytes, siete filas elegibles, TLS 1.3 y cero drops. La séptima fila contiene cuatro FIN/ACK y se conserva como cola normal de baja actividad; no hay duplicados. Claude/Haiku emitió ACEPTAR y confirmó que `HTTP-404-5/R01` sigue en orden antes de `TLS-SESSIONS-20/R01`. Ensamblador: 9 aceptadas, 136 faltantes. Evidencia: `docs/07-dataset-campanas/14-canario-HTTPS-1GB-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTPS-1GB-F1.md`.
- El décimo canario `F1N-HTTP-404-5-R01` fue aceptado con límites declarados: cinco GET secuenciales produjeron cinco HTTP 404 y cinco `fileinfo CLOSED`; el PCAP íntegro contiene 50/50 paquetes, 5 SYN, 5 SYN/ACK, 10 FIN, 0 RST y cero drops. Las dos filas elegibles tienen `http_error_ratio_60s=1`; comparten historia y no representan muestras independientes. El 0 % de paquetes pesados es correcto para este estrato pequeño. Kali conservaba `.113` configurada, pero su NIC externa estaba `DOWN`, sin ruta y bloqueada desde VM01; debe mantenerse como gate. Claude/Haiku emitió ACEPTAR. Ensamblador: 10 aceptadas, 135 faltantes. Siguiente perfil: `TLS-SESSIONS-20/R01`, veinte sesiones secuenciales. Evidencia: `docs/07-dataset-campanas/15-canario-HTTP-404-5-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-404-5-F1.md`.
- El undécimo canario `F1N-TLS-SESSIONS-20-R01` fue aceptado con limitaciones: veinte conexiones HTTPS secuenciales en 2.46 s produjeron veinte HTTP 200 en Cliente, veinte eventos TLS 1.3 y 431/431 paquetes; 20 SYN, 20 SYN/ACK, 40 FIN, 0 RST y cero drops. Las dos filas elegibles alcanzan `tls_session_rate_60s=0.25` y `0.33333333`, pero comparten el episodio. Todas las sesiones usan un cliente, destino y huella JA3/JA3S/JA4; certificado autofirmado y `--insecure`. Claude/Haiku emitió ACEPTAR CONDICIONADO y sus condiciones quedaron declaradas. Ensamblador: 11 aceptadas, 134 faltantes. Siguiente: `HTTP-MULTI-1/R01`, secuencial y multidestino; la concurrencia pertenece a C2/C4/C8. Evidencia: `docs/07-dataset-campanas/16-canario-TLS-SESSIONS-20-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-TLS-SESSIONS-20-F1.md`.
- El duodécimo canario `F1N-HTTP-MULTI-1-R01` fue aceptado con limitaciones: tres GET `/health` secuenciales alcanzaron `.10/.11/.12`, produjeron tres HTTP 200, tres `fileinfo CLOSED` y 30/30 paquetes; 3 SYN, 3 SYN/ACK, 6 FIN, 0 RST y cero drops. La fila elegible obtuvo `unique_dst_ip_ratio_30s=3/3=1`, `unique_dst_port_ratio_30s=1/3` y completitud SYN 1.0. Las VIP son identidades lógicas en una sola VM, no hosts físicos. Claude/Haiku emitió ACEPTAR CONDICIONADO; se corrigió que la fila es oficial `experiment/train` y que ratio 1.0 no es exclusivo. Ensamblador: 12 aceptadas, 133 faltantes. Siguiente: `HTTP-MULTI-5/R01`, esperado 3/15=0.2. Evidencia: `docs/07-dataset-campanas/17-canario-HTTP-MULTI-1-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-MULTI-1-F1.md`.
- El decimotercer canario `F1N-HTTP-MULTI-5-R01` fue aceptado con limitaciones: quince GET `/health` secuenciales —cinco por VIP— produjeron quince HTTP 200, quince `fileinfo CLOSED` y 150/150 paquetes; 15 SYN, 15 SYN/ACK, 30 FIN, 0 RST y cero drops. La fila elegible obtuvo `unique_dst_ip_ratio_30s=3/15=0.2`, `unique_dst_port_ratio_30s=1/15` y completitud SYN 1.0. El episodio duró 1.67 s y las VIP siguen siendo lógicas. Claude/Haiku emitió ACEPTAR CONDICIONADO; se corrigieron conteo de flows, propósito y unidades del siguiente perfil. Ensamblador: 13 aceptadas, 132 faltantes. Siguiente: `HTTP-C2/R01`, dos flujos de 100 MB a `10M` bytes/s cada uno. Evidencia: `docs/07-dataset-campanas/18-canario-HTTP-MULTI-5-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-MULTI-5-F1.md`.
- El decimocuarto canario `F1N-HTTP-C2-R01` fue aceptado con limitaciones: dos descargas concurrentes de 100 MB se solaparon durante 9.52 s, completaron 209,715,200 bytes y produjeron 151,467/151,467 paquetes; 95.7053 % en 500–1500 bytes, 2 SYN, 2 SYN/ACK, 4 FIN, 0 RST y cero drops. El agregado observado fue 176.15 Mbit/s frente a 167.77 nominal, aún bajo 200. Dos filas elegibles registran carga concurrente; la segunda tiene completitud SYN 0 porque no contiene SYN nuevos. `fileinfo` truncó a 102,400 bytes sin truncar descarga/PCAP. Claude/Haiku emitió ACEPTAR y autorizó C4 con gates. Ensamblador: 14 aceptadas, 131 faltantes. Evidencia: `docs/07-dataset-campanas/19-canario-HTTP-C2-F1.md` y `docs/04-revisiones-claude/2026-07-22-canario-HTTP-C2-F1.md`.
- El decimoquinto canario `F1N-HTTP-C4-R01` fue aceptado con limitaciones: cuatro descargas concurrentes de 100 MB se iniciaron en 13.772 ms, se solaparon unos 19.5 s y completaron 419,430,400 bytes. El PCAP íntegro contiene 301,517/301,517 paquetes, 96.1803 % entre 500–1500 bytes, 4 SYN, 4 SYN/ACK, 8 FIN, 0 RST y cero drops. El agregado observado fue 171.94 Mbit/s, 2.48 % sobre el nominal pero 28.06 Mbit/s bajo el techo. Dos filas representan carga y una tercera conserva trece FIN/ACK de cierre; no son repeticiones independientes. Dos mDNS quedaron fuera del PCAP/features y cuatro `fileinfo` se limitaron a 102,400 bytes sin truncar transferencias. Claude/Haiku emitió ACEPTAR CONDICIONADO y autorizó C8; se descartaron como evidencia su predicción de CPU y una progresión incorrecta de tres flujos. Ensamblador: 15 aceptadas, 130 faltantes. Evidencia: `docs/07-dataset-campanas/20-canario-HTTP-C4-F1.md` y `docs/04-revisiones-claude/2026-07-23-canario-HTTP-C4-F1.md`.
- El preflight de `HTTP-C8/R01` se detuvo sin crear artefactos porque el Sensor perdió la marca `NTPSynchronized=yes` después de unas 18 horas sin alcanzar sus fuentes públicas por la NIC externa aislada. Se aplicó la jerarquía VM01 `10.10.10.10`→Sensor→VM03–VM05. `prefer require` —sin `trust`— resolvió la espera causada por `authselectmode mix`: el Sensor seleccionó VM01, pasó a estrato 4 y recuperó `Leap status: Normal`. Tres gates consecutivos pasaron con offsets máximos inferiores a 100 ms; Kali se valida mediante `systemd-timesyncd`, no `chronyc`. Hashes desplegados y Git coinciden, las NIC externas siguen abajo y el bypass continúa bloqueado. Se autoriza repetir el preflight completo de C8. Evidencia: `docs/05-plan-pruebas/16-correccion-ntp-interno-G7.md`.
- El intento oficial `F1N-HTTP-C8-R01` fue rechazado: las ocho descargas HTTP 200 completaron 838,860,800 bytes y Suricata tuvo cero drops, pero `tcpdump` capturó 596,704 de 597,180 paquetes y descartó 476 (0.079708 %). El bundle quedó `evidence_failed`, el ledger `failed` y no existen features. Dos PCAP íntegros conservan 97.1282 % de paquetes entre 500–1500 bytes, solo como diagnóstico. Claude/Haiku confirmó el rechazo y recomendó aislar el cambio de búfer. Se versionan `-B 65536` y `net.core.rmem_max=67108864`; la rotación sigue 512 MB × 4. Próximo paso: desplegar y ejecutar `CAL-G6-HTTP-C8-R01`; el retry oficial exige cero drops y una política de archivado preservando el ID canónico. Evidencia: `docs/07-dataset-campanas/21-intento-rechazado-HTTP-C8-F1.md` y `docs/04-revisiones-claude/2026-07-23-intento-rechazado-HTTP-C8-F1.md`.
- La calibración `CAL-G6-HTTP-C8-R01` con el mismo perfil/rotación y solo el búfer ampliado fue completada: 605,266/605,266 paquetes, cero drops de tcpdump/Suricata, ocho HTTP 200, 838,860,800 bytes, 38/38 EVE, dos PCAP íntegros y seis filas. `purpose=calibration` y `partition=excluded_calibration` impiden incorporarla a F1. Claude/Haiku autorizó condicionalmente el retry después de documentar hashes, archivar de forma recuperable el fallido, obtener auditoría 15 aceptadas/0 inválidas/130 faltantes y repetir preflight. La rotación no cambia y el retry aún no se ejecutó. Evidencia: `docs/07-dataset-campanas/22-calibracion-buffer-HTTP-C8-G6.md` y `docs/04-revisiones-claude/2026-07-23-calibracion-buffer-HTTP-C8-G6.md`.
- El intento rechazado `F1N-HTTP-C8-R01` se archivó sin eliminación como `attempt-01` en VM01 y Sensor mediante el commit `3860c864`. Los hashes del manifest, ledger, lista del bundle y ambos PCAP se volvieron a verificar; las rutas activas quedaron libres. El ensamblador regresó al estado esperado: 15 aceptadas, 0 inválidas, 0 advertencias y 130 faltantes; la calibración sigue excluida. El reintento debe reutilizar el ID canónico y ejecutar nuevamente todos los gates. Evidencia: `docs/05-plan-pruebas/17-archivado-intentos-fallidos.md`.
- El reintento oficial `F1N-HTTP-C8-R01` fue aceptado con limitaciones: ocho HTTP 200 transfirieron 838,860,800 bytes; los ocho SYN comenzaron dentro de 46.726 ms y cada flujo duró aproximadamente 49.51 s. El PCAP íntegro contiene 600,128/600,128 paquetes, cero drops y 96.6514 % entre 500–1500 bytes; Suricata procesó un delta de 600,134 con cero drops/errores. Se extrajeron seis filas elegibles, autocorrelacionadas dentro de un episodio. El ensamblador suma 16 aceptadas, 0 inválidas y 129 faltantes; calibración e intento fallido permanecen separados. Claude aceptó tras corregir una mezcla inicial de generaciones y cifras históricas. Siguiente perfil: `TCP-REFUSED-5/R01`, siempre con nuevo preflight. Evidencia: `docs/07-dataset-campanas/23-canario-HTTP-C8-F1.md` y `docs/04-revisiones-claude/2026-07-23-canario-HTTP-C8-F1.md`.
- `F1N-TCP-REFUSED-5-R01` fue aceptado con limitaciones: cinco intentos legítimos al único puerto cerrado `10.30.0.10:65000` produjeron exactamente cinco SYN y cinco RST/ACK en 2.449771 s, cero drops y ninguna sesión L7. Dos filas elegibles obtuvieron `syn_completion_ratio_10s=0` y `rst_ratio_10s=0.5`; la fila final usa correctamente `unique_dst_port_ratio_30s=1/5=0.2`. Son ventanas autocorrelacionadas de un episodio. El ensamblador suma 17 aceptadas, 0 inválidas y 128 faltantes. Claude aceptó después de verificar la fórmula y corregir confusiones entre puertos origen/destino. Siguiente perfil: `TCP-50M/R01`. Evidencia: `docs/07-dataset-campanas/24-canario-TCP-REFUSED-5-F1.md` y `docs/04-revisiones-claude/2026-07-23-canario-TCP-REFUSED-5-F1.md`.

## Observaciones obligatorias del jurado

### Tráfico legítimo pesado

El dataset debe incluir tráfico legítimo con paquetes grandes, aproximadamente de 500 a 1500 bytes. Un paquete grande no puede convertirse por sí solo en señal de ataque. Se deben generar cargas legítimas reproducibles, concurrentes y variadas, separando correctamente entrenamiento, validación y prueba.

### Features multicapa

Las 14 variables de entrada deben incluir comportamiento útil de las capas 3, 4 y 7. Como mínimo se deben evaluar:

- Capa 3: ratio o cantidad de IP únicas, diversidad de origen/destino u otra medida por ventana.
- Capa 4: frecuencia o ratio de flags SYN, estados TCP y tasas por flujo/ventana.
- Capa 7: intentos fallidos de autenticación u otra señal semántica del servicio.

No aceptar una feature solo porque su nombre menciona una capa. Exigir definición matemática, ventana temporal, fuente de datos, tratamiento de valores faltantes, costo de cálculo en línea y justificación de por qué representa comportamiento.

## Reparto de responsabilidades

### Codex: implementación y operación

Codex se encarga principalmente de:

- configurar las VMs y servicios;
- crear y ejecutar playbooks de Ansible;
- implementar Suricata, captura, extracción de features y modelo;
- ejecutar pruebas positivas, negativas y de regresión;
- recolectar evidencia no sensible;
- mantener documentación y commits pequeños y trazables.

### Claude: revisión adversarial

Claude se encarga principalmente de:

- revisar arquitectura, configuración, código, dataset y metodología;
- buscar rutas que eviten el Sensor y puntos ciegos de captura;
- detectar fuga de datos, sesgo, etiquetas débiles y métricas engañosas;
- cuestionar si las 14 features son calculables en tiempo real;
- evaluar falsos positivos con tráfico legítimo pesado;
- diseñar pruebas que intenten refutar las conclusiones;
- simular observaciones y preguntas difíciles del jurado.

Claude puede implementar cambios cuando el usuario lo solicite expresamente. Antes debe explicar el alcance, evitar competir con cambios activos de Codex y trabajar en archivos o ramas claramente delimitados.

Claude también está autorizado para validar trabajo realizado por Codex y, cuando el usuario se lo pida, crear o actualizar documentación y publicarla en el repositorio oficial siguiendo el protocolo Git de este archivo.

## Formato obligatorio de las revisiones

Cada observación debe contener:

1. Identificador y título.
2. Severidad: crítica, alta, media o baja.
3. Hecho observado y evidencia concreta.
4. Inferencias separadas de los hechos.
5. Riesgo para seguridad, funcionamiento o validez científica.
6. Prueba reproducible para confirmar o refutar el problema.
7. Corrección propuesta y posibles efectos secundarios.
8. Estado: pendiente, confirmada, rechazada o corregida.

No presentar preferencias de estilo como fallos técnicos. No aceptar afirmaciones de otro agente sin comprobarlas.

## Flujo de revisión cruzada

```text
Codex implementa y entrega evidencia
                │
                ▼
Claude revisa de forma adversarial
                │
                ▼
Claude propone pruebas reproducibles
                │
                ▼
Codex reproduce y corrige hallazgos confirmados
                │
                ▼
Claude realiza la segunda revisión
```

Cada hallazgo debe terminar como confirmado mediante una prueba, rechazado mediante evidencia o pendiente con una razón concreta.

## Validación del trabajo realizado por Codex

Cuando el usuario pida revisar algo implementado por Codex, Claude debe:

1. Leer el commit, documentación y archivos relacionados.
2. Revisar `git log --oneline -10` y `git show --stat <commit>`.
3. Comparar lo documentado con la configuración o evidencia disponible.
4. Ejecutar primero verificaciones no destructivas.
5. No repetir una operación destructiva solo para comprobar que ocurrió.
6. Diseñar al menos una prueba positiva y una negativa.
7. Registrar discrepancias con el formato obligatorio de hallazgos.
8. No declarar un hallazgo corregido hasta verificarlo nuevamente.

Claude no debe aprobar automáticamente un cambio porque tenga un commit exitoso. Un commit demuestra trazabilidad, no funcionamiento.

## Publicación de documentación en GitHub

Claude puede crear y publicar documentación cuando el usuario lo autorice. El destino oficial es:

```text
origin  git@github.com:marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos.git
```

Antes de editar o publicar:

```bash
git status --short --branch
git remote -v
git log -5 --oneline
```

Reglas de publicación:

- No usar tokens escritos en comandos, archivos o mensajes de commit.
- Utilizar la autenticación SSH ya configurada en la VM administrativa.
- No hacer `push --force`.
- No reescribir commits publicados.
- No usar `git reset --hard` ni descartar cambios ajenos.
- No publicar datasets, PCAP, logs o secretos sin revisar tamaño y contenido.
- Ejecutar `git diff --check` antes del commit.
- Crear commits pequeños con mensajes descriptivos.
- Hacer `push` solamente después de revisar el diff y cuando el usuario haya autorizado publicar.

Si el árbol está limpio y no existe trabajo concurrente, Claude puede usar una rama propia:

```bash
git switch -c claude/revision-<tema>
```

Las revisiones de Claude deben guardarse preferentemente en:

```text
docs/04-revisiones-claude/
```

Si el usuario solicita una corrección documental directa y no hay cambios concurrentes, puede actualizar el documento correspondiente. Para cambios de código, infraestructura, firewall, red, Suricata o ML, se recomienda una rama separada y revisión de Codex antes de integrar a `main`.

Después de publicar, Claude debe informar:

- rama utilizada;
- hash y mensaje del commit;
- archivos modificados;
- verificaciones ejecutadas;
- limitaciones o tareas pendientes.

## Reglas de seguridad y repositorio

- No guardar contraseñas, tokens, cookies, claves privadas ni secretos en Git.
- No repetir en archivos credenciales expuestas en conversaciones.
- Solicitar rotación de cualquier secreto expuesto.
- No cambiar simultáneamente `main` desde dos agentes.
- Antes de editar, revisar `git status` y los diffs existentes.
- No eliminar ni revertir cambios ajenos sin autorización.
- No desconectar interfaces administrativas sin acceso de recuperación por consola ESXi.
- No ejecutar tráfico ofensivo fuera de las redes y máquinas explícitamente autorizadas del laboratorio.
- Sanitizar PCAP, `eve.json`, logs y capturas antes de publicarlos.
- Separar artefactos runtime y datasets grandes del código fuente.

## Criterio de finalización

Una fase solo se considera terminada cuando existen:

1. configuración persistente;
2. prueba funcional positiva;
3. prueba negativa o de fallo;
4. evidencia con fecha y zona horaria;
5. evaluación de riesgos y limitaciones;
6. documentación reproducible;
7. commit identificable sin secretos.

El objetivo final no es demostrar que el sistema siempre tiene razón, sino delimitar con evidencia qué detecta, bajo qué condiciones funciona, cuáles son sus falsos positivos y falsos negativos, y qué limitaciones conserva.

## Rediseño experimental vigente

Antes de ejecutar escenarios, Claude debe leer `docs/05-plan-pruebas/01-diseno-defendible.md` y `docs/05-plan-pruebas/README.md`. La campaña vigente se organiza como F0 (calibración), F1 (normalidad para entrenamiento), F2 (estrés legítimo), F3 (anomalías L3/L4/L7) y F4 (mixto). No se deben ejecutar ataques ni capturar el dataset final mientras Kali no tenga NTP sincronizado y las NIC externas estén aisladas.

El propósito es producir ventanas etiquetadas y reproducibles para Isolation Forest y modelos futuros. Las features nuevas deben demostrar código, diccionario, prueba y ablación; nunca deben marcarse como implementadas solo por estar planificadas. Claude debe revisar cada campaña contra MITRE ATT&CK, NIST y la documentación oficial de Suricata, y cuestionar tamaño de muestra, contaminación entre particiones, falsos positivos y pérdida de paquetes.

VM03 dispone ahora de NGINX HTTP/HTTPS, DNS local, iperf3 y SSH/SFTP; VM05 tiene las herramientas de cliente. La prueba iperf3 sin pacing de 2.58 Gbit/s produjo 389,932 descartes y está excluida del dataset. AF_PACKET fue ajustado y 100 Mbit/s durante 10 s obtuvo cero drops. Claude debe rechazar cualquier escenario iperf3 sin bitrate explícito y recordar que fallos de login SSH no son visibles en EVE sin integrar logs del host.

La calibración posterior fijó máximos F1 de 200 Mbit/s TCP y 50 Mbit/s UDP. TCP 250 tuvo retransmisiones y solo una ronda, TCP 300 fue abortado por la guardia, y UDP 75/100 presentó pérdida. `scripts/f1/run-benign.sh` rechaza esos valores superiores. La calibración no pertenece al dataset final.

HTTP/HTTPS quedó calibrado con 10 MB, 100 MB, 500 MB y 1 GB, además de 2/4/8 flujos concurrentes. Suricata terminó con cero drops y una muestra tcpdump registró 90.84 % de payloads TCP entre 500 y 1500 bytes. Los detalles están en `08-resultados-http-https-G2.md`; estos datos también son calibración y no entrenamiento.
