# Revisión Claude — HTTP-10MB/R05

Fecha: 7 de agosto de 2026. Dictamen final: **ACEPTAR CON LIMITACIONES**.

Claude autorizó una única captura después de leer preflight, matriz,
generador, extractor y antecedentes R01–R04. Señaló que los nueve gates no
validan tamaño/hash del archivo objetivo. Codex comprobó antes de capturar
10,485,760 bytes, SHA estable, HTTP 200 y Content-Length correcto; la salida no
forma parte del bundle, por lo que queda una limitación de trazabilidad y una
mejora de automatización posterior a R05.

En la revisión posterior, Claude verificó manifest, ledger, PCAP, EVE, deltas,
longitudes, extracción, CSV históricos, recursos y bundles. Confirmó HTTP 200,
10,485,760 bytes, PCAP 8,033/8,033/8,033, cero drops y 7,244 paquetes legítimos
de 500–1500 bytes. También confirmó dos filas nuevas 3,852/4,181 con ratios
pesados 0.80815161/0.98804114, una observación HTTP y error ratio cero.

Los flows ICMP/DNS pertenecen al preflight y preceden al PCAP. El `fileinfo`
`TRUNCATED` a 102,400 bytes refleja el límite de inspección Suricata; no
contradice curl ni PCAP. El delta +2 continúa sin atribución. Las dos filas son
autocorrelacionadas del mismo episodio y no deben tratarse como transferencias
independientes.

Claude no reejecutó el auditor global. Codex confirmó 123/145 aceptadas, R05
7/29, 22 faltantes, 33 duplicados, 16 cruces y cero inválidas/advertencias; el
resumen R05 registra siete perfiles, once filas y soporte pesado en dos filas.

El resultado responde al jurado: la etiqueta benigna viene del escenario
controlado `experiment/test`, no del tamaño de paquete. Claude autorizó sólo
documentar/publicar y el siguiente preflight independiente; no scoring,
reintento, modelo ni captura de HTTP-100MB.
