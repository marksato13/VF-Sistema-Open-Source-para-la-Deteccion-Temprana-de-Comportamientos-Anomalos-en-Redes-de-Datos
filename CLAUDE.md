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
- G6 usa `f1-normal-v2`: 29 perfiles, cinco repeticiones y partición fija R01–R03/R04/R05. `v1` queda preservada para cuatro pilotos DNS/HTTP/RST/TLS. `v2` añadió HTTP hacia las VIP DMZ `.10/.11/.12`; persistieron tras reinicio y el piloto obtuvo `unique_dst_ip_ratio_30s=1.0` con cero drops. Son diversidad lógica en una sola VM, no tres hosts físicos. El gate de disco continúa fallando. Evidencia: `docs/07-dataset-campanas/05-validacion-diversidad-L3-v2.md`.
- El ensamblador `scripts/dataset/build_f1_dataset.py` exige las 145 campañas `v2`, verifica bundles, recalcula matriz/esquema desde el commit, rechaza calibraciones y reconstruye el split por repetición. En el volumen oficial reporta 1 aceptada (`F1N-DNS-MIXED-20-2-R01`), 0 inválidas, 0 advertencias y 144 faltantes; los cinco pilotos históricos permanecen excluidos en la raíz heredada. Revisión inicial: `docs/04-revisiones-claude/2026-07-21-ensamblador-F1.md`.
- El gate G3 del orquestador pasó con `CAL-F1-DNS-003`: 6 paquetes, cero drops/errores/overflow, 7 registros EVE exactos y 7 muestras del Sensor. Esta ejecución es calibración y no pertenece al dataset.
- VM01 conserva su disco raíz de 70 GiB y ya posee un segundo VMDK thin de 150 GiB: ext4 por UUID en `/srv/ppi-evidence`, aproximadamente 140 GiB disponibles. El montaje persistió tras reiniciar VM01 con el mismo UUID y opciones `rw,nosuid,nodev,noexec,noatime`; RustDesk volvió `active/enabled`. Los gates de capacidad e identidad de F1 están en PASS. Diseño y evidencia: `docs/08-almacenamiento/01-disco-evidencias-vm01.md`.
- La auditoría inicial G7 confirmó el bypass: después del reinicio, VM03 recuperó `ens34=172.17.25.112` y VM01 alcanzó SSH directamente sin cruzar la captura `ens35` del Sensor. Ese estado histórico **NO APTO** está en `docs/05-plan-pruebas/13-auditoria-preexperimental-G7.md`; revisión inicial: `docs/04-revisiones-claude/2026-07-22-gate-preexperimental-G7.md`.
- G7 está **APTO PERSISTENTE**: VM03 reinició con un `boot_id` nuevo, `ens34` siguió `DOWN/NO-CARRIER`, `.112` no reapareció y continuó bloqueada desde VM01. Persistieron PPI-MGMT, retorno DMZ, servicios, NTP, VIP, restricciones y el camino Cliente/Kali→Sensor→Servidor; Suricata terminó con cero drops/errores. Se autoriza solamente un canario F1, no el lote completo. Evidencia: `docs/05-plan-pruebas/15-validacion-persistencia-G7.md`; revisión condicional previa: `docs/04-revisiones-claude/2026-07-22-cierre-operacional-G7.md`.
- El primer canario oficial `F1N-DNS-MIXED-20-2-R01` fue aceptado: 44/44 paquetes, 20 NOERROR + 2 NXDOMAIN, delta Suricata 48, 54 EVE exactos, cero drops/errores, una fila elegible y `dns_nxdomain_ratio_60s=2/22`. El ensamblador acepta la celda `train` y mantiene 144 faltantes. Este perfil no cubre paquetes grandes; el siguiente candidato es `HTTP-10MB/R01`, sujeto a nuevo preflight. Evidencia: `docs/07-dataset-campanas/06-primer-canario-oficial-F1.md`.

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
