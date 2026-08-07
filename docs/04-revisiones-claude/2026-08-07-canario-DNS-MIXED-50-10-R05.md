# Revisión Claude — DNS-MIXED-50-10/R05

Fecha: 7 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

Claude autorizó una única captura después del preflight continuo y del dry-run
con volumen oficial explícito. La revisión previa limitó el permiso a esta
campaña, sin retry, entrenamiento, scoring ni inicio del perfil siguiente.

En la revisión postcaptura leyó manifest, PCAP, EVE completo, deltas, resumen
de longitudes, extracción, CSV R01–R05, recursos y bundles. Confirmó
`experiment/test`, commit limpio `4174c049…da21`, PCAP 120/120/120, 13,866
bytes, cero drops, 120 paquetes IPv4 pequeños y EVE 130 = 120 DNS + diez
`stats`, sin eventos `flow`.

Claude comprobó línea por línea sesenta requests y sesenta responses: los
primeros cincuenta pares son `NOERROR` y los últimos diez `NXDOMAIN`, sin
huérfanos. Verificó además 120 observaciones de paquete, 70 de aplicación, una
fila, `dns_nxdomain_ratio_60s=10/60=0.16666667` y las catorce features idénticas
a R01–R04.

El dictamen distingue igualdad del vector y fuga operacional. El generador
actual `scripts/f1/run-benign.sh` fija contenido, orden y conteos; por ello el
cruce train↔test limita la diversidad y la interpretación de generalización.
Sin embargo, cada repetición conserva PCAP, EVE, flow IDs, tiempos y hashes
propios: no hay evidencia de reutilización de archivos. La fila debe mantenerse
como repetición estructural, sin deduplicación post hoc.

La revisión también confirmó las 53 muestras de recursos y ambos bundles. Los
cuatro paquetes del delta Suricata permanecen sin atribución; su ausencia de
efecto observado no equivale a riesgo cero. La ausencia de paquetes pesados es
coherente con una celda DNS; la observación del jurado se cubre mediante los
perfiles benignos HTTP/HTTPS/TCP/UDP.

Claude señaló que dos rutas citadas inicialmente eran antiguas: los componentes
reales son `scripts/f1/run-benign.sh` y
`scripts/features/extract_multilayer.py`. Su sesión sólo lectura no recomputó el
auditor global. Codex verificó por separado 120/145 aceptadas, R05 4/29, 25
faltantes, 30 duplicados, 13 cruces y cero inválidas/advertencias.

Claude autorizó **únicamente documentar y publicar** este cierre. No autorizó
scoring, entrenamiento, reintento ni captura de `PING-10/R05`; ésta exige un
preflight nuevo sobre el próximo commit limpio.
