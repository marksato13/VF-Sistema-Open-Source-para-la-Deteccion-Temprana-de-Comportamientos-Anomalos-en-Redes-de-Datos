# Revisión Claude — auditoría agregada R03

Fecha: 4 de agosto de 2026. Claude Code 2.1.217, modelo Sonnet.

Claude emitió **APTO CON CONDICIONES** para cerrar R03. Reconoció 29/29 perfiles, gate reproducible, 72 filas de 29 episodios, cobertura no cero de las catorce features y distinción entre 19.54 GB crudos, 87 episodios y 224 ventanas train.

Conservó como límites la autocorrelación, topología fija, mayor peso temporal de web/TLS, cobertura L7 de error escasa, diecisiete coincidencias exactas dentro de `train`, ausencia actual de validation/test y falta de modelo o métricas.

Claude exigió dos condiciones antes de R04: congelar matriz/esquema/generador/topología/software y registrar la política de filas/duplicados. Ambas quedaron formalizadas en `docs/05-plan-pruebas/18-congelamiento-protocolo-R04-R05.md`.

Una revisión adversarial posterior declaró la política **APTA PARA DOCUMENTAR**. Se precisó que peso uno por ventana es siempre el resultado principal; balance por episodio y colapso determinista de duplicados `train` son sensibilidades obligatorias separadas. También se fijaron igualdad decimal exacta en catorce dimensiones como definición de vector visto y la partición atómica mediante la matriz/ensamblador.

Codex encontró una contradicción anterior que la revisión no identificó: G5 limita hiperparámetros/umbral a train, mientras G6 reserva R04 para umbral y falsos positivos normales. Queda expuesta como gate del protocolo de modelado; no se resolverá después de observar R04.

Codex corrigió dos afirmaciones del revisor:

- no está demostrada una causa determinista para las diez coincidencias nuevas;
- web/TLS estricto descendió 57.142857→56→55.5556 % de R01 a R03, por lo que no “aumentó ligeramente”; la serie sigue siendo descriptiva.
- no existe en el contrato F1-v2 evidencia del umbral heredado que Claude creyó recordar; resultados del MVP no se reutilizan en la evaluación final.

La respuesta consolidada al jurado es acotada: 172/224 ventanas train contienen tráfico pesado legítimo y las catorce features se distribuyen en seis L3, cinco L4 y tres L7. Esto demuestra cobertura controlada, no representatividad, suficiencia o detección. No existe una feature de login fallido y no se añadirá silenciosamente a `v2`.

**Dictamen consolidado: R03 CERRADO, APTO CON CONDICIONES.** Únicamente se autoriza el preflight de `F1N-DNS-VALID-10-R04`; no su ejecución hasta predefinir el protocolo de modelado/selección.
