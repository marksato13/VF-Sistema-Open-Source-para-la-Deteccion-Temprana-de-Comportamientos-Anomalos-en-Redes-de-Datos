# Revisión adversarial de `feat/shared-data-science-skills`

**Fecha:** 26 de agosto de 2026 · `America/Lima`
**Objeto:** commit `97581ac` — 10 habilidades compartidas, contexto común y auditoría
**Estado del PR:** abierto, **sin fusionar**

## Veredicto

**Apto para fusionar**, con una actualización previa y una resolución manual de
conflicto. El trabajo es de buena calidad: el diseño es correcto, el contexto
compartido es **factualmente exacto** y no toca nada congelado.

---

## Verificaciones superadas

| Comprobación | Resultado |
|---|---|
| ¿Toca artefactos congelados? | **No.** Ni `artifacts/`, ni `configs/`, ni `scripts/engine`, `features`, `modeling` o `dataset` |
| ¿Toca código de producción? | **No.** Solo documentación, `AGENTS.md`, `CLAUDE.md` y las habilidades |
| Diseño de las habilidades | **Correcto.** Una sola fuente en `agent-skills/`, expuesta por **enlaces simbólicos** desde `.claude/skills/` y `.agents/skills/`. Evita la duplicación que habría divergido |
| Contenido de una habilidad, revisado a fondo (`ppi-dataset-audit`) | Manda verificar `sha256sum -c` **antes** de abrir un `.joblib`, regenerar solo a ruta temporal, y distinguir duplicados dentro de una partición de fuga entre particiones. Es exactamente el criterio del proyecto |

### El contexto compartido, cifra por cifra

Se contrastó `ppi-data-science-context.md` contra los artefactos, no contra
otros documentos:

| Dato | En el contexto | Contra el artefacto |
|---|---|---|
| Modelo, `nu`, umbral | `ocsvm_scaled`, 0.05, `1.8126087939765134` | ✅ |
| Variables | 28 definidas, 27 efectivas | ✅ |
| Dataset | 1 373 / 179 ventanas, 220 / 132 episodios, 44 perfiles | ✅ |
| Evaluación | ROC-AUC 0,974 · 158/179 · 143/161 · 13/276 | ✅ |
| FPR operativo | 22,97 % y 25,81 % | ✅ |

**Sin rastros obsoletos**: ni τ1/τ2, ni iptables, ni «38 perfiles», ni el
puntaje superado de la ficha.

**Dos aciertos que conviene destacar.** Cita **recuentos** (`158/179`) y no solo
porcentajes, que es la práctica correcta. Y declara que el contexto «es un
índice, no una fuente numérica», obligando a verificar en el artefacto
primario: eso impide justamente que un error se propague entre agentes.

---

## RAMA-01 · Las tres contradicciones listadas ya están cerradas

**Severidad:** media · **Estado:** pendiente de actualizar antes de fusionar

**Hecho.** El contexto compartido y la auditoría listan tres contradicciones
abiertas. Las tres se cerraron **después** de que se escribieran:

| Contradicción listada | Estado real |
|---|---|
| El datasheet dice que la ablación no se ejecutó | **Corregido** el 26-08-2026 |
| Tres entregables dicen «100 % en 57 corridas» | **Corregido** el 26-08-2026 |
| McNemar usa ventanas correlacionadas del mismo episodio | **Atendido**: el análisis se repite por episodio |

**Riesgo.** Un agente que lea el contexto tras la fusión saldría a buscar
problemas que ya no existen, y podría «corregir» texto correcto.

**Corrección propuesta.** Actualizar esa sección tras fusionar, dejando
constancia de que se cerraron y con qué evidencia.

## RAMA-02 · Conflicto en `CLAUDE.md`

**Severidad:** baja · **Estado:** confirmado, resoluble a mano

**Hecho.** `git merge-tree` confirma conflicto: **ambos agentes corregimos las
mismas líneas** —la de «disponibilidad 100 % en 57 corridas» y la de artefactos
fuera de Git— con redacción distinta y el mismo sentido.

**Riesgo.** Una fusión automática descartaría uno de los dos conjuntos de
cambios. En `main` hay además contenido posterior sobre el diccionario y el
datasheet que la rama no conoce.

**Corrección propuesta.** Resolución manual conservando **ambos**: la redacción
de la rama sobre corridas y artefactos publicados, y la de `main` sobre el
diccionario y el datasheet canónico.

---

## Sobre los tres hallazgos altos de la auditoría

Verificados uno por uno **contra los artefactos**, no contra la afirmación:

| Hallazgo | Veredicto |
|---|---|
| El datasheet afirma que la ablación no se ejecutó | ✅ **Cierto.** Aparecía en dos sitios. Corregido. Además, **el verificador de consistencia de Claude no lo detectaba**: su patrón no cubría esa redacción, y se amplió |
| McNemar sobre ventanas correlacionadas | ✅ **Cierto y metodológicamente correcto.** Se atendió midiendo, no argumentando: repetido por episodio con dos reglas, **conclusión idéntica** (15/21 y 6/6). El agrupamiento es leve —conglomerado máximo de dos ventanas— |
| Tres entregables con «100 % en 57 corridas» | ✅ **Cierto en su momento.** Corregido en un commit posterior a la auditoría |

**Los tres hallazgos eran válidos.** Dos apuntaban a trabajo propio de Claude,
incluido un fallo en su propia herramienta de verificación. La revisión cruzada
funcionó en la dirección contraria a la habitual, y conviene registrarlo.

---

## Recomendación

Fusionar, en este orden:

1. `git merge origin/feat/shared-data-science-skills` desde `main`.
2. Resolver `CLAUDE.md` a mano conservando **ambos** conjuntos de cambios.
3. Actualizar la sección «Contradicciones abiertas» del contexto compartido.
4. Comprobar que los enlaces simbólicos resuelven tras la fusión.
5. Ejecutar la suite y el verificador de consistencia antes de publicar.

**No se fusiona en esta revisión.** Es trabajo de otro agente sobre un archivo
compartido, y la decisión corresponde al autor del proyecto.
