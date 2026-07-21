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

Las NIC externas de `172.17.25.0/24` todavía existen temporalmente para instalación y recuperación. Son una posible ruta de evasión; deberán desconectarse o bloquearse antes de obtener evidencia experimental definitiva.

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
