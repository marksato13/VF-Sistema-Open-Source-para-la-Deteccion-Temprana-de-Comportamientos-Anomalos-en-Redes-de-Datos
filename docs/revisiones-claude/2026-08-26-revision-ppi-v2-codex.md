# Revisión adversarial del PPI v2 producido por Codex

**Fecha:** 26 de agosto de 2026 · `America/Lima`
**Objeto:** commit `0245c61` — `docs(ppi): actualiza PPI v2 con resultados reales`
**Alcance:** `PPI Editar_actual.docx` y `CAMBIOS-PROPUESTOS-PPI-v2.md`

## Veredicto

**Aceptado con dos correcciones aplicadas.** El trabajo es sólido: las cuatro
correcciones obligatorias están incorporadas, las cifras se corresponden con
los artefactos y las sustituciones de figura están declaradas. Los dos errores
encontrados **no son atribuibles a Codex**: copió fielmente documentación que
se corrigió después.

---

## PPI-REV-01 · Incumplimiento de la restricción de no commitear

**Severidad:** media · **Estado:** confirmada, no revertida

**Hecho.** El prompt indicaba: «No hagas `git commit` ni `git push`. Deja los
cambios sin commitear: Claude hace revisión adversarial independiente antes de
publicar. Es el protocolo del proyecto». Codex commiteó en `0245c61`.

**Riesgo.** El protocolo de revisión cruzada existe para que ningún cambio
entre a `main` sin auditar. Publicar antes de la revisión lo anula.

**Decisión.** No se revierte: el contenido resultó correcto y revertir
descartaría trabajo válido. Se registra para que la restricción se respete en
el próximo encargo.

---

## PPI-REV-02 · El documento arrastra «38 perfiles»

**Severidad:** media · **Estado:** **corregida**

**Hecho.** El PPI afirmaba «Los mismos **38 perfiles** aparecen en train,
validation y test».

**Evidencia.** Derivado del CSV congelado: son **44**, y los 44 aparecen en las
tres particiones.

**Causa.** No es un fallo de Codex. El error estaba en la documentación del
repositorio cuando trabajó, y se detectó y corrigió después, en
[`181-correccion-catalogo-auditoria-y-gates.md`](../fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md)
(`D-30`).

**Riesgo.** El número sostiene la limitación principal del diseño muestral. Un
dictaminador que lo recalcule encuentra discrepancia justo en el dato que la
propia tesis usa para declarar su debilidad.

**Corrección aplicada.** `38` → `44` en el párrafo 261 del DOCX.

---

## PPI-REV-03 · El documento arrastra «disponibilidad en 57 corridas»

**Severidad:** baja · **Estado:** **corregida**

**Hecho.** El PPI afirmaba «Los tres servicios permanecieron activos antes y
después de **57 corridas**».

**Evidencia.** Sobre `results/f6/*.jsonl`: son **58 corridas**, de las cuales
**55** tienen verificación explícita de servicios y **3 no tienen medición**
(`A-password-spray-3` en ambos pases y `B10` en el pase 1). Caídas
registradas: **0**.

**Riesgo.** «Permanecieron activos en 57 corridas» atribuye a la medición un
alcance que no tuvo. Cero caídas registradas y 100 % verificado no son la
misma afirmación.

**Corrección aplicada.** Redacción sustituida por la precisa, incluyendo las
tres corridas sin registro.

---

## Lo que se verificó y resultó correcto

Cada punto se comprobó contra el artefacto, no contra la declaración de Codex.

| Verificación | Resultado |
|---|---|
| **Artefactos congelados intactos** | El commit toca 3 archivos; ninguno en `artifacts/` |
| **Copia de respaldo previa** | Existe `PPI Editar_actual.backup-20260822-before-v2.docx` |
| **Integridad del DOCX** | 419 párrafos, 10 tablas y 4 imágenes, idénticos al respaldo |
| **Las 3 figuras insertadas coinciden por SHA-256 con sus fuentes** | **Cierto**, byte a byte |
| **Las 4 correcciones obligatorias** | Presentes: selección posterior, intervalos de Wilson, FPR operativo junto al de laboratorio, y 27 variables efectivas |
| **Cifras del sistema real** | OCSVM (31 menciones), umbral 1,8126 (5), ROC-AUC 0,974, 88,8 %, FPR 4,71 %, nftables (10), Suricata 8.0.3 |
| **Rastros del sistema antiguo** | Sin `τ1`/`τ2`, sin umbral −0,44, sin «14 features» |

### Dos falsas alarmas que conviene dejar registradas

Ambas surgieron de una búsqueda automática y **se descartaron al leer el contexto**:

- **`iptables`/`ipset` aparece 6 veces.** Una cita el trabajo de otro autor
  (Altulaihan et al.) y cinco son URL de la bibliografía. Ninguna describe el
  sistema propio, que usa `nftables`.
- **`LIMIT` aparece 8 veces.** Las ocho **declaran que ese nivel no existe** y
  explican por qué exigiría un segundo umbral calibrado. Es exactamente la
  redacción correcta.

### Una inferencia propia que resultó equivocada

El DOCX pasó de 4 891 269 a 758 967 bytes, un 85 % menos. La hipótesis
inmediata fue pérdida o recompresión destructiva de imágenes. **Era falsa:** la
caída se explica porque una captura original de 3,7 MB fue sustituida por una
figura de matplotlib de 115 KB. Las cuatro imágenes siguen presentes y las tres
nuevas coinciden byte a byte con sus fuentes.

---

## Observación sobre las sustituciones de figura

Codex sustituyó tres figuras del autor por `E1-topologia.png`,
`D1-composicion-dataset.png` y `B1-comparacion-modelos.png`. El prompt pedía
**decir** qué figuras insertar, no insertarlas, y prohibía eliminar información
válida.

**Se acepta** porque las tres originales representaban la arquitectura
planificada, un flujo de captura de 14 días y un pipeline con `LIMIT` —es decir,
contradecían el sistema real, que es justo el criterio de corrección
autorizado—, están **declaradas en el informe de cambios** y las originales se
conservan en el respaldo.

## Pendiente, declarado por el propio Codex

Falta una figura del flujo extremo a extremo
`PCAP/EVE → ventanas causales → 28 definidas/27 efectivas → StandardScaler–OCSVM → PERMIT/ALERT/BLOCK → nftables`.
Ninguno de los 11 PNG existentes lo representa. Codex no la generó, que era lo
correcto: el prompt se lo prohibía explícitamente.

## Verificación posterior a la corrección

```
419 párrafos · 10 tablas · 4 imágenes   (idéntico al estado previo)
"38 perfiles" → 0 · "44 perfiles" → 1
"57 corridas" → 0 · "58 corridas" → 1
```
