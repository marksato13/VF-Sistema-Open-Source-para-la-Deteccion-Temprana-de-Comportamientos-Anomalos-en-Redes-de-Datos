# Contexto de trabajo para Claude Code

## Propósito

## Estado vigente — 2026-08-18

**Dataset multilayer-v2 consolidado y auditado**: 220 episodios normales /
1,373 ventanas (train 824, validation 273, test 276) + 179 ventanas de
anomalías reales para evaluación (161 genuinamente originadas en Kali, 18
heredadas de una generación anterior). **28 features definidas, 27 con
variación observable**: diccionario científico completo —fórmula, denominador,
comportamiento con denominador cero, fuente, rangos teórico y observado,
observabilidad, coste y estado— generado desde el extractor congelado en
`docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md`, y
**datasheet canónico** con las once secciones de la rúbrica en
`docs/dataset/DATASHEET_MULTILAYER_V2.md` — ambos generados desde los
artefactos, no redactados a mano.
`gates.pass=true` con gates de duplicados y constantes (`constants_declared`,
`no_duplicate_crossing_label`, `no_duplicate_crossing_partition`,
`duplicates_within_tolerance`), sin episodios repartidos entre particiones.
Limitación declarada y no resuelta:
`tls_handshake_failure_ratio_60s` es **no observable** en esta configuración y
sigue constante en todo el dataset (ver
`docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md`). El
tamaño real queda por debajo de la meta aspiracional de 2,000–3,000 ventanas
independientes (`docs/fase03-dataset/160-plan-expansion-dataset-multicapa-v2.md`).

**Modelo congelado: OCSVM** (`ocsvm_scaled`, `nu=0.05`, sobre features
estandarizadas). Umbral `score < 1.8126` (calibrado con `alpha=0.05`).
Desempeño en evaluación bloqueada de un solo paso: FPR benigno 4.71%,
detección global 88.3%, detección Kali-real 88.8%. Punto débil declarado:
familias de fallo de autenticación (`ANOM-AUTH-FAIL-50` 50%,
`ANOM-KALI-PASSWORD-SPRAY-50` 55%). Elegido sobre Isolation Forest por
desempeño empírico medido (instrucción explícita del usuario), no por regla
por defecto — IF tiene puntos ciegos reales y medidos en `tcp-syn-rate` y
`udp-probe` (0% de detección) que OCSVM sí resuelve. Detalle completo:
`docs/fase04-modelado/05-resultado-calibracion-multilayer-v2-v1.md` y
`docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md`.

**Motor de decisión en tiempo real y enforcement inline: desplegados y
activos en VM02** (`ppi-motor-capture.service` + `ppi-motor.service`).
Reusa directamente el extractor congelado (`scripts/features/extract_multilayer_v2.py`)
sin duplicar fórmulas. En `ALERT` real (no en el heurístico de ventana sin
tráfico) bloquea la IP LAN ofensora vía nftables en el propio Sensor —sin
SSH entre VMs, el Sensor ya es el router LAN↔DMZ—, con expiración nativa de
120 s, validado con corte y restauración de tráfico real. Dos fallos reales
de producción encontrados y corregidos (no en pruebas sintéticas): un
`set -e` que silenciaba el script para el caso normal, y un bucle real de
re-bloqueo infinito por una poda de memoria basada en reloj en vez de
tamaño. Detalle completo, incluidas las limitaciones declaradas (sin nivel
`LIMIT` intermedio porque exigiría un segundo umbral sin calibrar; ~120 s de
buffer en anillo, menor que una campaña offline completa):
`docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md`.

**Dashboard operativo del motor: desplegado** (`ppi-dashboard.service`, VM02,
puerto `8788` solo en loopback, acceso remoto exclusivamente por túnel SSH).
Solo lectura, complementario a otras herramientas de monitoreo — no ejecuta
ninguna acción. Muestra salud de servicios, contexto del modelo (umbral y
métricas leídas del `manifest.json` congelado, no hardcodeadas), IPs
bloqueadas en vivo y actividad reciente. Validado end-to-end contra tráfico
real (una IP bloqueada automáticamente por el motor apareció en el panel con
su expiración exacta). Arquitectura completa, justificación técnica y manual
de instalación/usuario: `docs/fase06-dashboard/01-diseno-dashboard-motor.md`.

**Validación final F6: ejecutada** (`docs/fase07-validacion-final/`): 2 pases
de 29 corridas con el motor activo + 2 pruebas de aislamiento. Confirmado:
detección + bloqueo inline con lead-time ~8 s (motor al día), heurístico de
fuerza bruta disparando en producción, cero caídas de servicio registradas en 58 corridas, 55 de ellas con verificación explícita.
**Dos limitaciones nuevas medidas y declaradas** (no ocultas): (1) el FPR
benigno offline de 4.71 % **no se sostiene** sobre tráfico legítimo pesado —
`iperf-tcp 200M` en aislamiento produjo un FP genuino que bloqueó al cliente
legítimo (scores del tráfico pesado apiñados en el margen del umbral); es la
debilidad más importante para el jurado. (2) el motor se atrasa bajo carga
sostenida (hasta 161 s) por reparsear el anillo de PCAP completo cada ciclo.
Detalle: `docs/fase07-validacion-final/02-resultados-f6.md`; mejoras
candidatas (recalibración con tráfico pesado, parseo incremental) en
`docs/07-mejoras-futuras/01-debilidades-y-mejoras.md` filas #11 y #12, sin
implementar sin calibración nueva. No hay campañas de recolección activas.
Los artefactos runtime (modelos, PCAP, datasets) permanecen fuera de Git; la
evidencia agregada de F6 (`results/f6/*.jsonl`, pequeña) sí se versiona.

**Debilidades y mejoras futuras** recolectadas punto por punto, cada una con
su evidencia y costo/riesgo de mejora (sin implementar ninguna sin
calibración/evaluación nueva): `docs/07-mejoras-futuras/01-debilidades-y-mejoras.md`.

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
2. Leer `docs/fase00-infraestructura/virtualizacion/README.md`.
3. Leer `docs/requisitos-jurado/README.md`.
4. Leer `docs/fase00-infraestructura/ansible/README.md`.
5. Leer `ansible/README.md`, el inventario y los playbooks relacionados con la tarea.
6. Para el historial detallado de una campaña o revisión específica, buscarla en
   `docs/fase03-dataset/README.md` o `docs/revisiones-claude/README.md`
   antes de asumir que no existe evidencia — este archivo ya no repite ese
   historial en prosa, solo el estado vigente.
7. Distinguir entre diseño planificado, configuración aplicada y evidencia validada.
8. Ejecutar `git remote -v` y confirmar que `origin` apunta al repositorio oficial antes de publicar.

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
- En VM02–VM05, `useransible` puede ejecutar únicamente el reinicio exacto `/usr/bin/systemctl reboot --no-wall`; en el Sensor también puede usar los helpers versionados `ppi-suricata-metrics`, `ppi-pcap-control` y, desde el despliegue del motor, `ppi-enforce` (bloqueo nftables, ver `docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md`). No dispone de sudo general ni de permiso directo sobre `tcpdump`; la prueba negativa con `/usr/bin/id` falla en las cuatro VMs. `ppi-motor-capture.service` y `ppi-motor.service` corren de forma autónoma vía systemd, sin necesitar sudo en operación diaria.
- G4 incorpora PCAP por campaña mediante un helper raíz que fija `ens35`, filtro LAN↔DMZ, snaplen completo y rotación máxima aproximada de 2.048 GB. El diseño y riesgos están en `docs/fase01-diseno-experimental/11-diseno-captura-PCAP-G4.md`.
- G4 pasó con DNS y HTTP. En `CAL-G4-HTTP-001`, 7,242 de 8,484 paquetes IPv4 (85.36 %) midieron 500–1500 bytes, con cero drops y SHA remoto/local verificado. Resultados: `docs/fase01-diseno-experimental/12-validacion-captura-PCAP-G4.md`.
- G5 define `multilayer-v1`: 14 features causales por IP iniciadora, con ventanas de 10/30/60 s y tres señales L7 pasivas. Diccionario: `docs/fase02-features-multicapa/01-diccionario-multicapa-G5.md`; extractor: `scripts/features/`.
- G5 pasó pruebas sintéticas, regresión HTTP y una campaña DNS con warm-up de 60 s. La fila resultó `eligible_training=true`, pero conserva propósito `calibration` y no entra al dataset. Evidencia: `docs/fase02-features-multicapa/02-validacion-extractor-G5.md`.
- El gate G3 del orquestador pasó con `CAL-F1-DNS-003`: 6 paquetes, cero drops/errores/overflow, 7 registros EVE exactos y 7 muestras del Sensor. Esta ejecución es calibración y no pertenece al dataset.
- VM01 conserva su disco raíz de 70 GiB y ya posee un segundo VMDK thin de 150 GiB: ext4 por UUID en `/srv/ppi-evidence`, aproximadamente 140 GiB disponibles. El montaje persistió tras reiniciar VM01 con el mismo UUID y opciones `rw,nosuid,nodev,noexec,noatime`; RustDesk volvió `active/enabled`. Los gates de capacidad e identidad de F1 están en PASS. Diseño y evidencia: `docs/fase00-infraestructura/almacenamiento/01-disco-evidencias-vm01.md`.
- El preflight de `HTTP-C8/R01` se detuvo sin crear artefactos porque el Sensor perdió la marca `NTPSynchronized=yes` después de unas 18 horas sin alcanzar sus fuentes públicas por la NIC externa aislada. Se aplicó la jerarquía VM01 `10.10.10.10`→Sensor→VM03–VM05. `prefer require` —sin `trust`— resolvió la espera causada por `authselectmode mix`: el Sensor seleccionó VM01, pasó a estrato 4 y recuperó `Leap status: Normal`. Tres gates consecutivos pasaron con offsets máximos inferiores a 100 ms; Kali se valida mediante `systemd-timesyncd`, no `chronyc`. Hashes desplegados y Git coinciden, las NIC externas siguen abajo y el bypass continúa bloqueado. Se autoriza repetir el preflight completo de C8. Evidencia: `docs/fase01-diseno-experimental/16-correccion-ntp-interno-G7.md`.
- El intento rechazado `F1N-HTTP-C8-R01` se archivó sin eliminación como `attempt-01` en VM01 y Sensor mediante el commit `3860c864`. Los hashes del manifest, ledger, lista del bundle y ambos PCAP se volvieron a verificar; las rutas activas quedaron libres. El ensamblador regresó al estado esperado: 15 aceptadas, 0 inválidas, 0 advertencias y 130 faltantes; la calibración sigue excluida. El reintento debe reutilizar el ID canónico y ejecutar nuevamente todos los gates. Evidencia: `docs/fase01-diseno-experimental/17-archivado-intentos-fallidos.md`.

Historial completo campaña por campaña (180 documentos) en [`docs/fase03-dataset/README.md`](docs/fase03-dataset/README.md); cada uno con su revisión adversarial independiente en [`docs/revisiones-claude/README.md`](docs/revisiones-claude/README.md).

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
docs/revisiones-claude/
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

Antes de ejecutar escenarios, Claude debe leer `docs/fase01-diseno-experimental/01-diseno-defendible.md` y `docs/fase01-diseno-experimental/README.md`. La campaña vigente se organiza como F0 (calibración), F1 (normalidad para entrenamiento), F2 (estrés legítimo), F3 (anomalías L3/L4/L7) y F4 (mixto). No se deben ejecutar ataques ni capturar el dataset final mientras Kali no tenga NTP sincronizado y las NIC externas estén aisladas.

El propósito es producir ventanas etiquetadas y reproducibles para Isolation Forest y modelos futuros. Las features nuevas deben demostrar código, diccionario, prueba y ablación; nunca deben marcarse como implementadas solo por estar planificadas. Claude debe revisar cada campaña contra MITRE ATT&CK, NIST y la documentación oficial de Suricata, y cuestionar tamaño de muestra, contaminación entre particiones, falsos positivos y pérdida de paquetes.

VM03 dispone ahora de NGINX HTTP/HTTPS, DNS local, iperf3 y SSH/SFTP; VM05 tiene las herramientas de cliente. La prueba iperf3 sin pacing de 2.58 Gbit/s produjo 389,932 descartes y está excluida del dataset. AF_PACKET fue ajustado y 100 Mbit/s durante 10 s obtuvo cero drops. Claude debe rechazar cualquier escenario iperf3 sin bitrate explícito y recordar que fallos de login SSH no son visibles en EVE sin integrar logs del host.

La calibración posterior fijó máximos F1 de 200 Mbit/s TCP y 50 Mbit/s UDP. TCP 250 tuvo retransmisiones y solo una ronda, TCP 300 fue abortado por la guardia, y UDP 75/100 presentó pérdida. `scripts/f1/run-benign.sh` rechaza esos valores superiores. La calibración no pertenece al dataset final.

HTTP/HTTPS quedó calibrado con 10 MB, 100 MB, 500 MB y 1 GB, además de 2/4/8 flujos concurrentes. Suricata terminó con cero drops y una muestra tcpdump registró 90.84 % de payloads TCP entre 500 y 1500 bytes. Los detalles están en `08-resultados-http-https-G2.md`; estos datos también son calibración y no entrenamiento.

Historial completo de calibraciones y canarios R01–R05 (180 documentos) en [`docs/fase03-dataset/README.md`](docs/fase03-dataset/README.md); revisión adversarial de cada uno en [`docs/revisiones-claude/README.md`](docs/revisiones-claude/README.md).