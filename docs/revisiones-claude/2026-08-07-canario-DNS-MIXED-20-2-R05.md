# Revisión Claude — DNS-MIXED-20-2/R05

Fecha: 7 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

Claude autorizó una única captura después de leer el preflight, la matriz, el
generador y el extractor. Confirmó que los nombres `error-legitimo-N.ppi.lab`
son inexistentes por diseño, que la fórmula es NXDOMAIN/consultas en 60 s y que
un eventual duplicado debe conservarse sin recalibración.

En la revisión postcaptura leyó manifest, EVE completo, deltas, controles PCAP,
extracción, CSV R01–R05 y bundles como texto. Verificó directamente veinte
pares `NOERROR` seguidos de dos pares `NXDOMAIN`, PCAP 44/44/44, cero drops,
EVE 56 y ratio `2/22=0.09090909`.

También reprodujo la causalidad de los dos flows tardíos. El ICMP y el DNS
comenzaron durante los probes `00:33:49–51` y fueron emitidos por timeout a
`00:38:54/58`; el PCAP oficial sólo contiene tráfico de `00:38:52.557–53.086`.
Por tanto, los flows se preservan en EVE pero no contaminan PCAP ni features.

Claude confirmó que las catorce features son idénticas a R01–R04. Lo clasificó
como limitación del generador determinista y nuevo cruce hacia `test`, no fuga
operacional. Verificó además que las tres filas existentes dentro de R05 son
distintas entre sí.

La sesión de Claude no recomputó SHA-256 ni ejecutó el auditor global. Codex
confirmó ambos bundles y las cifras 119/145, R05 3/29, 26 faltantes, 29
duplicados, 12 cruces y cero inválidas/advertencias.

Claude autorizó únicamente documentar y publicar. No autorizó scoring ni otra
captura; el siguiente preflight corresponde a una decisión separada.
