# Revisión Claude — auditoría agregada R02

Fecha: 28 de julio de 2026. Claude Code, modelo Haiku.

Claude emitió **APTO CON CONDICIONES PARA CERRAR R02 Y PREPARAR R03**. Conservó correctamente:

- cierre R02 29/29 con `gate_pass=true`;
- necesidad de separar cierre de colección y validez del modelo;
- preservación de filas correlacionadas y coincidencias exactas;
- documentación de sesgos de topología, protocolo y duración;
- prohibición de entrenar o declarar desempeño final con 58/145 campañas;
- necesidad de una política explícita para iperf3 antes de R03.

Se corrigieron o descartaron:

- web/TLS representa 42/75 = 56 %; 60 % solo al incluir MIXED-LIGHT;
- el soporte L7 escaso no permite afirmar que ataques L7 sean “indetectables”;
- 75 filas no se califican como suficientes o insuficientes sin diseño de potencia o criterio previo;
- no existe el plazo de 24 horas propuesto;
- `build_f1_dataset.py` no debe construir con 58/145; la verificación correcta es `--audit-only`;
- no se exige Pearson ni una tabla de correlación ad hoc para reconocer dependencia temporal por diseño;
- no se predicen AUC, falsos positivos o falsos negativos;
- R01–R03 son `train`, pero el dataset final sigue requiriendo R04 `validation` y R05 `test`;
- actualizar iperf3 no autoriza sobrescribir, excluir o repetir silenciosamente `UDP-50M/R02`.

Codex consolida la política de cambio: conservar iperf3 3.20 hasta cerrar F1, auditar coherencia de extremos y secuencias PCAP en cada UDP, y evaluar 3.21 después de R05 en una fase versionada. Un cambio anterior exigiría detener F1 y aprobar una enmienda explícita.

**Dictamen consolidado: APTO CON CONDICIONES.** R02 puede cerrarse; únicamente queda habilitada la preparación y el preflight independiente de R03.
