# Checklist de ejecución

Ordenado por **cuándo conviene hacerlo**, no por número de identificador. Marcar solo cuando exista evidencia reproducible: un punto descrito no es un punto resuelto.

Referencia completa de cada punto en [`01-registro-debilidades.md`](01-registro-debilidades.md).

---

## ✅ Hecho — 25 de agosto de 2026

Corrección de información publicada que contradecía al dataset congelado.
Evidencia: [`181-correccion-catalogo-auditoria-y-gates.md`](../../fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md).

- [x] **D-30 · `38 perfiles` → `44 perfiles`** en cinco documentos y en el generador del Word.
- [x] **D-31 · Catálogo de anomalías de 3 a 9 familias**, separando `profiles` (VM05) de `kali_profiles` (VM04) sin debilitar la lista blanca benigna.
- [x] **D-32 · Reporte de auditoría regenerado** a 1 373/179; el de 75/18 archivado, no borrado.
- [x] **D-26 · Cuatro gates nuevos** de duplicados y constantes, con prueba positiva y negativa. Suite: 88 tests en verde.
- [x] **D-35 · Generadores de Word reproducibles** — el logo vivía en un directorio efímero y la carátula se omitía en silencio.
- [x] **D-14 · Diccionario científico de las 28 variables**, generado desde el extractor congelado. Cierra un requisito explícito del jurado.
- [x] **D-12 · `tls_handshake_failure_ratio_60s` declarada no observable** — se reportan **27 efectivas de 28 definidas**.
- [x] **D-34 · Model card y system card** separadas del datasheet, generadas desde el manifiesto y las corridas de F6.
- [x] **D-08 · Dataset, manifiesto y los 7 modelos candidatos publicados** (5,7 MB), verificables con `sha256sum -c`.
- [x] **D-33 · Licencias, responsables, contacto, retención y usos prohibidos** declarados.
- [x] **D-29 · Datasheet canónico** con las once secciones de la rúbrica, generado desde los artefactos y con guardián contra reportes desactualizados.

SHA-256 de los CSV congelados idénticos antes y después.

---

## 🔥 Bloque 0 — Con fecha límite

- [ ] **D-20 · Actualizar el PPI y subirlo a LAM Research** — vence el miércoles. Contrastar contra la tabla de correspondencia de [`../05-ppi/README.md`](../05-ppi/README.md), que ya mapea cada aspecto del proyecto con su evidencia real.

---

## ⚡ Bloque 1 — Minutos y horas · máximo retorno

Ninguna requiere capturar datos, reentrenar ni repetir campañas. **Cierran dos requisitos del jurado y la principal objeción metodológica.**

- [ ] **D-01 · Declarar la selección posterior del modelo** *(horas)*
  Escribir en tesis y PPI que la detección reportada es una estimación optimista por haberse elegido el modelo tras ver el conjunto de prueba.
- [ ] **D-15 · Cerrar y actualizar la matriz de cumplimiento de requisitos** *(horas)*
  4 filas sin cerrar y rutas rotas tras la reorganización documental.
- [ ] **D-03 · Ejecutar validación cruzada sobre el modelo congelado** *(horas)*
  → *Ficha ítem 1.3: de 1 a 3*
- [ ] **D-05 · Estabilidad por remuestreo del OCSVM** *(horas)*
  Dar una banda de variabilidad al umbral 1,8126.
- [ ] **D-06 · Documentar determinismo y semillas como protocolo** *(horas)*
  → *Ficha ítem 2.4: de 2 a 3*
- [ ] **D-22 · Revertir el acceso administrativo permanente** *(horas)*
  Volver al sudoers estrecho para que la evidencia de aislamiento vuelva a ser cierta en la defensa.

> **Efecto acumulado del bloque 1:** la ficha de auditoría pasa de **62,7 % a 76,5 %** sin experimentación nueva.

---

## 📐 Bloque 2 — Uno o dos días

- [ ] **D-02 · Ejecutar la ablación por capas L3/L4/L7 y la comparación 14 vs 28 variables**
  Requisito explícito del jurado, aún sin ejecutar. Dataset, modelo y protocolo ya existen: es un script de comparación, no una campaña.
- [ ] **D-17 · Redactar el manual de implementación técnica**
  Instalación reproducible desde cero; los comandos ya están probados en los despliegues documentados. → *Ficha ítem 2.6: de 2 a 3*
- [ ] **D-04 · Prueba de significancia entre modelos** *(McNemar o bootstrap pareado)*

---

## 🧪 Bloque 3 — Días, si el calendario lo permite

- [ ] **D-18 · Validación con usuarios** — instrumento SUS con 5–8 evaluadores sobre el panel. → *Ficha ítems 3.1 y 3.2: de 0 a 2*
- [ ] **D-09 · Capturar una jornada nueva como holdout temporal externo**
  Resuelve simultáneamente el problema de la división por repetición y parte del tamaño muestral.
- [ ] **D-19 · Dos pruebas adversariales** — evasión del detector y abuso del bloqueo por suplantación de IP.
- [ ] **D-10 · Capturar los escenarios legítimos faltantes** — SSH, SCP/SFTP, SMB, respaldo, streaming, actualizaciones.

---

## 🔬 Bloque 4 — Semanas · trabajo futuro declarado

- [ ] **D-11 · Recalibrar el umbral incluyendo tráfico legítimo pesado** y repetir la validación operativa.
      *Es la única solución real al error operativo del 23–26 %.*
- [ ] **D-13 · Calibrar un segundo umbral intermedio** (`LIMIT`) con el mismo método de cuantil.

---

## 📄 Bloque 5 — Presentación de los entregables

- [ ] **D-23 · Añadir gráficos a la ficha de auditoría** — barras de las tres dimensiones y comparación antes/después del puntaje.
- [ ] **D-24 · Ajustar la extensión del informe de validación** — de ~5,2 páginas a las 3–4 pedidas.
- [ ] **D-07 · Calcular la comparación con el criterio de Youden**, o retirar la promesa del protocolo.

---

## 📌 Se declaran, no se resuelven

Estos puntos se documentan como límite del alcance. Declararlos con evidencia es defendible; ocultarlos no lo es.

- [ ] **D-21** · Control por identidad más robusta que la IP — limitación estructural.
- [ ] **D-16** · Monitoreo de deriva del modelo — documentar el procedimiento, no implementarlo.
- [ ] **D-25** · Tamaño muestral bajo la meta — reportar el efectivo por episodio junto al de ventanas.
- [ ] **D-27** · El heurístico de fuerza bruta no está calibrado estadísticamente.
- [ ] **D-28** · Sin evaluación por jueces expertos.

---

## Mínimo defendible

Si el tiempo obliga a elegir:

> **Bloque 0 + Bloque 1 + D-02** (la ablación).

Cubre los dos requisitos formales incumplidos, corrige la principal deficiencia de inferencia y actualiza el PPI a tiempo — todo **sin experimentación nueva**.
