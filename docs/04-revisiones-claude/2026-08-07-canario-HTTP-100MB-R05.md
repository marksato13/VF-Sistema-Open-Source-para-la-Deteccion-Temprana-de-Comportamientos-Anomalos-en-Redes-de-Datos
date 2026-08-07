# Revisión técnica — HTTP-100MB/R05

Fecha: 7 de agosto de 2026. Dictamen provisional: **ACEPTAR CON LIMITACIONES**.

La revisión técnica comprobó contra los artefactos primarios HTTP 200 y
104,857,600 bytes, PCAP íntegro `77987/77987/77987`, cero drops, 92.9437 % de
paquetes IPv4 entre 500–1500 bytes, EVE HTTP/fileinfo/stats, dos ventanas de
features y recursos del Sensor sin saturación. El `TRUNCATED` de fileinfo es
el límite de inspección de Suricata (`102400` bytes), no una descarga truncada.

La campaña es `experiment/test`, está fijada a `b601a61` y sus bundles pasan
sus hashes. Las dos ventanas (70,718 y 7,269 paquetes) pertenecen al mismo
episodio HTTP y deben agruparse; no son dos transferencias independientes.
El auditor Codex registra 124/145 aceptadas, R05 8/29, 21 faltantes, 33
duplicados, 16 cruces y cero inválidas/advertencias.

No se detectó una contradicción que justifique rechazo. Sí quedan tres límites:

1. El archivo objetivo se verificó manualmente antes de capturar, pero esa
   salida todavía no forma parte del bundle oficial.
2. Las filas y duplicados estructurales reducen la independencia de una futura
   evaluación; no deben contarse como muestras independientes.
3. Claude Code no emitió dictamen en esta sesión porque el cliente devolvió
   `Not logged in · Please run /login`. Esta nota no atribuye falsamente el
   resultado a Claude; requiere confirmación posterior con una sesión
   autenticada.

Se autoriza únicamente documentar/publicar esta campaña y preparar el próximo
preflight independiente. Quedan bloqueados scoring, reentrenamiento, cambios
de modelo y nuevas capturas en lote.
