# Contexto compartido de ciencia de datos

Estado de referencia: **26 de agosto de 2026**. Este documento alinea a Claude
y Codex; no sustituye a los artefactos primarios. Antes de citar una cifra,
volver a leer su fuente.

## Orden de autoridad

1. Artefactos congelados y sus SHA-256:
   `artifacts/model/manifest.json`, `artifacts/model/*.joblib`,
   `artifacts/model/candidates/*.joblib`,
   `artifacts/dataset/multilayer-v2-*.csv` y
   `docs/dataset/SHA256SUMS`.
2. Contratos versionados:
   `configs/features/multilayer-v2.json` y
   `configs/campaigns/multilayer-v2-anomalies.json`.
3. Resultados generados:
   `artifacts/dataset/multilayer-v2-audit-report.json`,
   `results/ablacion/ablacion-multicapa.json`,
   `results/ablacion/significancia-modelos.json` y `results/f6/*.jsonl`.
4. Documentos generados: datasheet, diccionario, model card y system card.
5. Documentos narrativos. Si contradicen una fuente anterior, registrar la
   contradicción; no elegir la cifra más conveniente.

## Estado comprobado

- Dataset normal: 1 373 ventanas, 220 episodios; particiones 824/273/276 y
  132/44/44 episodios. Los 44 perfiles aparecen en las tres particiones.
- Dataset anómalo: 179 ventanas, 132 episodios; 161 ventanas de Kali y 18
  heredadas/re-etiquetadas. Hay 9 familias declaradas.
- Variables: 28 definidas (L3=9, L4=8, L7=11) y 27 efectivas. La variable
  `tls_handshake_failure_ratio_60s` es constante y no observable.
- Calidad: 22 duplicados excedentes en 14 grupos; ninguno cruza etiqueta o
  partición; `gates.pass=true`.
- Modelo congelado: `ocsvm_scaled`, OCSVM con `nu=0.05` sobre variables
  estandarizadas. Alerta si `score < 1.8126087939765134`; el umbral se fijó
  solo en `validation` con `alpha=0.05`.
- Evaluación bloqueada: ROC-AUC 0,974; detección global 158/179; detección Kali
  143/161; falsos positivos benignos 13/276. Usar los intervalos de Wilson ya
  publicados, no recalcularlos de memoria.
- Selección: el manifiesto designaba `if_primary_weighted` como conclusión y a
  OCSVM como comparador. Promover OCSVM después de observar la evaluación hace
  optimistas sus cifras absolutas. Hay siete filas candidatas, pero solo seis
  objetos ajustados únicos: `if_uniform` y `if_exact_collapsed` comparten hash.
- Ablación: 14→28 variables mejora la detección en este corpus, pero 20
  variables (`base+L3+L4`) igualan la detección observada del contrato completo
  y producen menos falsos positivos. No promover esa variante sin protocolo y
  evaluación nuevos.
- Operación: el FPR benigno pesado es 22,97 % en el pase limpio y 25,81 % en el
  pase anterior, no 4,71 %. Una transferencia legítima `iperf-tcp 200M`
  produjo bloqueo durante 120 s. Lead-time limpio: mediana 8,0 s, p95 8,7 s.
- Disponibilidad: cero caídas registradas en 58 corridas; solo 55 tienen
  verificación explícita de servicios. No afirmar “100 % verificado”.
- Publicación: los CSV derivados, el manifiesto y los siete archivos candidatos
  sí están versionados en Git. PCAP, EVE completo, campañas y dependencias
  empaquetadas permanecen fuera.

## Límites que deben acompañar las conclusiones

- Los 44 perfiles se repiten entre train, validation y test por índice R01–R05;
  se mide repetibilidad de escenarios, no generalización externa.
- No existe jornada temporal externa, red externa ni cliente multi-sistema.
- Faltan SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones legítimas.
- Las ventanas del mismo episodio son correlacionadas. Una prueba inferencial
  por ventana debe justificarse o repetirse por episodio/cluster; McNemar
  exacto no vuelve independientes a las ventanas.
- El desempeño operacional refuta una lectura productiva del FPR offline. El
  sistema no es apto para operación desatendida sin recalibración.
- No convertir resultados descriptivos o post hoc en confirmación prospectiva.

## Contradicciones abiertas detectadas

- El datasheet y su generador todavía dicen que la ablación no se ejecutó,
  aunque `docs/fase04-modelado/07-ablacion-multicapa.md` ya existe.
- Tres entregables aún conservan “100 % en 57 corridas”; la fuente vigente dice
  58 corridas, 55 verificadas y cero caídas registradas.
- El contraste entre modelos usa ventanas como unidad inferencial pese a que el
  propio corpus documenta correlación dentro del episodio.

El detalle, severidad y verificación están en
`docs/auditorias/2026-08-26-auditoria-cambios-y-contexto-agentes.md`.

## Protocolo común

1. Ejecutar `git status --short --branch` y preservar cambios ajenos.
2. Verificar `sha256sum -c docs/dataset/SHA256SUMS` antes de cargar `.joblib`.
3. Leer el artefacto primario y registrar numerador, denominador y unidad.
4. Separar ventana, episodio, familia, corrida y usuario; no intercambiarlos.
5. Reportar selección posterior, dependencia por episodio y validez externa.
6. No modificar los artefactos congelados. Una mejora que cambie datos, modelo
   o umbral exige versión nueva y evaluación reservada.
7. Dejar salidas generadas y comandos reproducibles; no transcribir cifras.
