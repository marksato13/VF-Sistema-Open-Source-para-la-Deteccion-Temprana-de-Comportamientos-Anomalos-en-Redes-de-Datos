---
name: preparacion-defensa
description: "Prepara la defensa del PPI simulando las preguntas difíciles del jurado y comprobando que cada respuesta tenga evidencia. Usar antes de la defensa del 24 de octubre de 2026 y al preparar diapositivas o guiones."
---

# Preparación de la defensa

Defensa: **24 de octubre de 2026**.

El objetivo no es que el sistema parezca infalible. Es **delimitar con
evidencia** qué detecta, bajo qué condiciones, cuáles son sus falsos positivos
y qué limitaciones conserva.

## Las preguntas que van a hacer

### 1 · «Su FPR de laboratorio es 4,71 %. ¿Por qué en operación es 25 %?»

**La más probable, y la más peligrosa.** No hay respuesta que la elimine; hay
una que la sostiene:

Los scores del tráfico legítimo pesado se apiñan en el margen del umbral. Un
`iperf-tcp 200M` legítimo, en aislamiento, produjo un falso positivo genuino
que bloqueó al cliente. Está medido, documentado y **no se ocultó**. Corregirlo
exige recalibrar con tráfico pesado, y recalibrar sin evaluación nueva
invalidaría el congelamiento.

Fuente: `docs/fase07-validacion-final/02-resultados-f6.md`.

### 2 · «¿Por qué OCSVM si su política declaraba Isolation Forest?»

Por desempeño empírico medido, no por regla por defecto. IF tiene puntos
ciegos reales: **0 % de detección** en `tcp-syn-rate` y `udp-probe`, 71
ventanas, que OCSVM resuelve con 84 % y 100 %.

Y se declara la tensión: el manifiesto registra `ocsvm_scaled` con
`role = sensitivity_or_comparator`. **El artefacto congelado contradice su
política registrada, y consta.**

### 3 · «¿Cómo sé que no eligió los resultados que le convenían?»

Nada se borra. El intento rechazado `F1N-HTTP-C8-R01` se archivó como
`attempt-01` sin eliminarlo. En F6 se conserva
`f6_resultados.pass1-contaminado.jsonl`, un pase descartado. Y una fuga real
se detectó, se corrigió y se marcó «no debe citarse».

### 4 · «¿Validó con usuarios reales?»

**No todavía.** `respuestas-sus.csv` tiene cero filas. Es `REQ-013` y estaba
agendado para el 9 de septiembre. Decirlo sin rodeos es mejor que un rodeo que
el jurado desmonte.

### 5 · «¿Las 28 variables aportan algo?»

La ablación lo mide: 66,5 % → 88,8 %, p < 0,001, con McNemar y corrección de
Holm sobre 21 pares. Y se declara que **27 de 28** tienen variación
observable: `tls_handshake_failure_ratio_60s` es constante.

### 6 · «¿Esto funciona fuera de su laboratorio?»

**No está demostrado.** No existe jornada de holdout temporal externa; es
`REQ-005`. La partición es disjunta por episodio, lo que evita fuga entre
particiones, pero no sustituye a datos de otra red o de otra fecha.

## Cómo se responde

1. La cifra exacta, con su denominador.
2. Dónde está la evidencia.
3. La limitación, antes de que la pregunten.

Una respuesta que promete más de lo medido se desmonta con una repregunta. Una
que declara su límite, no.

## Antes de la defensa

Comprueba con `ppi_pendientes` qué sigue abierto, y que ninguna diapositiva
afirme algo con estado `PLANIFICADO` o `REFUTADO`.
