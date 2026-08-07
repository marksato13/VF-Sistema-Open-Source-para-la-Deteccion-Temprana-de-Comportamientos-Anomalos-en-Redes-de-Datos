# Revisión Claude — DNS-VALID-10/R05

Fecha: 6 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

La primera consulta quedó sin dictamen porque el sandbox de Claude no podía
leer `/srv/ppi-evidence`. Codex no aceptó una revisión basada sólo en cifras
transcritas. La segunda sesión recibió acceso adicional exclusivamente de
lectura y sólo las herramientas `Read`, `Grep` y `Glob`; no dispuso de Bash,
edición, campaña, preflight, modelo ni scoring.

Claude leyó manifest, ledger, deltas, preflight, bundles como texto, EVE
completo, CSV R01–R05, reporte de extracción, contadores del Sensor y control
PCAP. Corroboró commit/matriz/argumentos sin drift, `experiment/test`, nueve
gates PASS, PCAP 20/20/20 con cero drops, EVE 29 = 20 DNS + 9 stats, una fila y
el vector exacto R01–R04. No encontró una razón para rechazar la campaña.

Su hallazgo medio `DUP-TEST-01` identifica correctamente el primer vector
idéntico `train↔test`. Se conserva como limitación de diversidad del generador,
no fuga operacional: los artefactos R05 son independientes y no hubo carga de
modelo ni score. No se deduplica. La evaluación primaria futura conserva todas
las filas; un desglose `seen`/`unseen` sólo puede ser complementario.

El hallazgo bajo `LEDGER-NAMING-01` señala que
`eligible_training_rows` es un nombre poco neutral en una partición `test`.
Pertenece al esquema heredado `f1-run-ledger-v1`; `partition=test` controla el
split y no se cambia el contrato durante R05.

Claude aceptó el delta Suricata 24 frente a PCAP 20 como limitación no nueva:
R01, R02 y R04 muestran el mismo patrón y todos los drops son cero. La
explicación por distinto alcance de interfaz/filtro es plausible, pero no se
toma como causa demostrada; los cuatro paquetes siguen sin atribución.

Límites de su reproducción: no dispuso de Bash, no abrió el binario PCAP, no
ejecutó `sha256sum` ni reejecutó el auditor global. Codex verificó PCAP, ambos
bundles, recursos y auditor aparte. También corrigió dos excesos del texto de
Claude: sólo son catorce features —no «24 columnas numéricas»— y el tamaño final
de R05 todavía no permite afirmar que el efecto del duplicado se diluirá.

Claude autorizó únicamente documentar y publicar este cierre. No autorizó como
parte de su revisión el próximo preflight, otra captura ni scoring.
