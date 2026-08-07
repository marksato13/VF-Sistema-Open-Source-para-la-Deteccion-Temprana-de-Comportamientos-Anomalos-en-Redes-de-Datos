# Revisión Claude — calibración PM-F1-v1

Fecha: 6 de agosto de 2026. Dictamen útil: **CALIBRACIÓN ACEPTADA PARA CONGELAMIENTO**.

## Revisión previa

Claude/Haiku recibió el JSON del preflight: 87/224 train, 29/72 validation,
entorno exacto, Git limpio, destino ausente y cero lectura de R05. Autorizó el
comando `--execute-once` contra el commit completo `b94035e…ae0f0`. Escribió por
error que R05 era una “validación posterior”; Codex corrigió que R04 es
`validation` y R05 es `test`. El gate no dependió de esa frase.

## Revisión posterior

Claude leyó `manifest.json` y el protocolo en modo de sólo lectura. Confirmó:

- 87 campañas/224 ventanas R01–R03 y 29/72 R04;
- `k=3`, `threshold=s(4)` y alerta estricta;
- parámetros IF, ramas, comparadores y diez semillas congelados;
- IF por ventana como único principal;
- R05 ausente de fuentes y scores;
- hashes calculados antes de diagnósticos y Git limpio;
- concentración de la cola principal en dos campañas.

Emitió `CALIBRACIÓN ACEPTADA PARA CONGELAMIENTO` y pidió documentar la
concentración y el mapeo `seen`.

## Correcciones al dictamen

La revisión también produjo inferencias que no se aceptan como evidencia:

1. `threshold_tie_count=1` no representa un empate roto: es sólo la fila que
   define el umbral; no hubo empate múltiple.
2. El span absoluto `0.0122` entre umbrales de semillas no es “1.22 %”. No se
   asigna porcentaje a scores sin una escala justificable.
3. Claude enumeró erróneamente varios cruces `seen` y sugirió que la alerta vista
   podía ser `HTTP-404-5`. La reconstrucción sellada confirma los diez cruces
   publicados y que la única alerta `seen` es `DNS-MIXED-50-10/R04`.
4. Igualdad de conteos entre semillas no significa igualdad de campañas: TLS
   permanece, pero la segunda campaña cambia entre DNS, HTTP-C8 y TCP-REFUSED.
5. La sugerencia de añadir diversidad a F2 no modifica matrices congeladas ni
   autoriza F2–F4. Cualquier rediseño posterior necesita versión y evaluación
   retenida nueva.

Codex verificó independientemente `SHA256SUMS`, reconstruyó umbrales/alertas
desde los CSV y recargó los seis modelos con igualdad exacta de scores. Esas
pruebas cierran las dos condiciones útiles de Claude: concentración y mapeo.

El dictamen autoriza publicar el congelamiento, no abrir R05 automáticamente.
R05 requiere su propio procedimiento de ejecución única, revisión previa y
prohibición de `fit` o cambio de umbral.
