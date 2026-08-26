# Revisión de la verificación de revistas ejecutada por Codex

**Fecha:** 26 de agosto de 2026
**Objeto:** encargo de verificación en fuente primaria de IJIES, IJIT e ISI
**Entorno de Codex:** `C:\Users\markp\AppData\Local\Temp\opencode\ppi-repo\` (Windows)
**Entorno de esta revisión:** `/home/m4rk/Documentos/pronteacomopepa/vf-sistema-final` (Linux)

## Resumen

Codex **respetó la regla central del encargo**: ante tres bloqueos de acceso no
inventó ningún dato. Eso era lo que más importaba, porque los cinco errores
previos de la matriz venían de agregadores.

Sin embargo trabajó sobre **otro repositorio**, de modo que ningún archivo llegó
al repositorio oficial, y dos de sus afirmaciones sobre el proceso son falsas.
Sus hallazgos sustantivos sobre ISI sí son correctos y **corrigen un error mío**.

| | |
|---|---|
| Afirmaciones verificadas como correctas | 3 |
| Afirmaciones refutadas | 2 |
| Errores propios que su trabajo destapó | 1 |
| Archivos entregados al repositorio oficial | **0** |

---

## R-01 · El trabajo no llegó al repositorio

**Severidad:** alta

**Hecho.** Codex informa haber dejado el informe en
`C:\Users\markp\AppData\Local\Temp\opencode\ppi-repo\docs\articulo\verificacion-revistas-2026-08.md`.
En el repositorio oficial, `ls docs/articulo/` devuelve solo `README.md` y
`mapeo-secciones-BEEI-IJSSE.xlsx`, y `git status --short --branch` sale limpio
sobre `main`.

**Inferencia.** Codex se ejecutó mediante opencode sobre un clon temporal en
Windows, no sobre la ruta indicada en el encargo. Él mismo lo detectó: «el
repositorio del prompt no está disponible aquí» y «el repositorio encontrado no
contiene `matriz-decision-revistas.md` ni `generar_matriz_revistas.py`».

**Riesgo.** El informe con las citas literales y las URL de consulta no es
recuperable desde aquí. La evidencia que respalda sus hallazgos hay que
reconstruirla, que es lo que hizo esta revisión.

**Prueba.** `ls -la docs/articulo/` y `git status --short --branch`.

**Corrección propuesta.** Reejecutar el encargo desde el repositorio Linux, o
recuperar el archivo del temporal de Windows antes de que se borre.

**Estado:** confirmada.

---

## R-02 · La afirmación sobre el verificador de consistencia es falsa

**Severidad:** media

**Hecho.** Codex informa: «El verificador existente terminó con código de error
porque detectó 21 rastros obsoletos preexistentes». La ejecución real de
`scripts/entregables/verificar_consistencia.py` devuelve:

```
RASTROS OBSOLETOS: 0
EXCEPCIONES DECLARADAS: 21 coincidencias legítimas
exit code = 0
```

**Inferencia.** Codex tomó el número 21 de la línea de **excepciones
declaradas** —coincidencias con justificación escrita, no defectos— y lo
reportó como rastros obsoletos. El código de salida no fue de error.

**Riesgo.** Si se acepta sin comprobar, se busca un problema inexistente en un
verificador que funciona. En sentido contrario, acostumbrarse a que este
verificador «siempre falla» anularía su utilidad como puerta de calidad.

**Prueba.** `python3 scripts/entregables/verificar_consistencia.py; echo $?`

**Estado:** refutada.

---

## R-03 · La advertencia sobre el ISSN de IJIES es legítima, y los datos resisten

**Severidad:** informativa

**Hecho.** Codex advierte que `ijies.org` corresponde a otra revista con ISSN
2319-9598 y declara no haber mezclado sus datos.

**Verificación.** La advertencia es correcta y la colisión de siglas es real:

| ISSN | Revista | Editor |
|---|---|---|
| **2185-3118** | International Journal of Intelligent Engineering and Systems | **Intelligent Networks and Systems Society** |
| 2319-9598 | International Journal of Inventive Engineering and Sciences | — |

Toda la evidencia de la matriz se tomó de `inass.org`, no de `ijies.org`, y el
ISSN registrado es el correcto.

**Estado:** confirmada como advertencia válida; sin efecto sobre los datos.

---

## R-04 · Hallazgo correcto de Codex que corrige un error mío

**Severidad:** media

**Hecho.** Codex reporta para ISI un «límite recomendado de 6-12 páginas y
mínimo de 20 referencias». La página oficial lo confirma literalmente:

> «The preferred length of each paper falls between 6 and 12 pages of the IIETA
> journals. Each paper should contain at least 20 references.»

Fuente: <https://www.iieta.org/journals/isi/Instructions%20for%20Authors>,
consultada el 26/08/2026.

**Error propio detectado.** La matriz registraba para ISI «plantilla disponible
y **sin límite estrecho de páginas declarado**», con puntaje de formato 8. Era
falso.

**Segundo error propio, detectado al comprobar lo anterior.** La matriz
registraba la revisión de ISI como «double-blind · **~2 meses**» marcada `✔`.
Ese plazo **no aparece en ninguna página de ISI**: su declaración de revisión
describe el proceso y las cuatro decisiones posibles, sin ningún tiempo. El dato
era un arrastre de la ficha de IJSSE, revista del mismo editor.

**Corrección aplicada.**

| Campo | Antes | Después |
|---|---|---|
| Plantilla | «DOCX oficial disponible» | «DOCX oficial · extensión preferida 6–12 páginas · mínimo 20 referencias» `✔` |
| Revisión | «double-blind · ~2 meses» `✔` | «double-blind · **no declara plazo**» `?` |
| Formato | 8 | **7** |
| Viabilidad | 9 | **8** |
| **Puntaje total** | 72,0 | **69,0** |

**Efecto.** ISI pasa a ser la candidata con menor puntaje del conjunto. Sigue
siendo el Plan C **por eliminación**, no por mérito: es la única candidata
restante que supera el listón de volumen anual.

**Estado:** corregida.

---

## R-05 · Bloqueos reportados, no sustituidos

**Severidad:** informativa

Codex reporta tres bloqueos: SCImago con HTTP 403, Springer con «Client
Challenge», y tasas de aceptación no encontradas en fuentes oficiales. Los tres
coinciden con lo hallado de forma independiente en esta máquina.

**Esto es el resultado correcto, no un fallo del encargo.** La regla era «un
bloqueo reportado es un resultado válido; un dato inventado no», y se cumplió.
Quedan pendientes exactamente los mismos datos que antes:

| Dato | Revista | Estado |
|---|---|---|
| Cobertura vigente en Scopus | IJIES | **Pendiente — bloqueo** |
| Cuartil SJR | IJIES, IJIT, ISI | Pendiente — bloqueo |
| Tiempo de revisión | IJIT, ISI, ISJ, ICS | Pendiente |
| Tasa de aceptación | IJIT, ISI | **No publicada por las revistas** |

Las dos primeras filas requieren un navegador. La última no se resuelve con
ninguna herramienta automática: hay que escribir al editor.

**Estado:** pendiente, con causa concreta.

---

## Conclusión

Codex cumplió la regla que definía el encargo y aportó un hallazgo real que
corrigió dos errores de la matriz. Falló en dónde ejecutó el trabajo y en la
lectura de la salida del verificador.

**El saldo neto es positivo:** la matriz es hoy más exacta que antes del encargo,
aunque ninguno de sus archivos haya llegado al repositorio.
