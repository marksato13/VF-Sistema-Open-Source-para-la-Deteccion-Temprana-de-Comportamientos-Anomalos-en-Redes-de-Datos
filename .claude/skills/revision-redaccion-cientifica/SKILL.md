---
name: revision-redaccion-cientifica
description: "Revisa la redacción científica de un texto del PPI: cifras sin fuente, resultados planificados presentados como obtenidos, causalidad excesiva, limitaciones ocultas y coherencia entre documentos. Usar sobre cualquier párrafo que vaya a leer un jurado o un revisor."
---

# Revisión de redacción científica

No es corrección de estilo. Es comprobar que **cada frase se sostenga en algo
verificable**.

## Los cinco fallos que se buscan

### 1 · Cifra sin fuente

Toda cifra se comprueba con `ppi_cifra`. Si no aparece registrada, o falta
registrarla o el documento la inventa. **Las dos cosas importan.**

Cifras vigentes, con su estado:

| Cifra | Qué es | Estado |
|---|---|---|
| 0,9741 | ROC-AUC en prueba | OBTENIDO |
| 88,8 % (143/161) | Detección Kali-real | OBTENIDO |
| 4,71 % (13/276) | FPR en laboratorio | OBTENIDO |
| 25,81 % y 22,97 % | FPR en operación | OBTENIDO |
| 8,0 s (6,1–13,7, n=8) | Lead time mediano | OBTENIDO |
| 58 corridas, 0 caídas | Disponibilidad | VALIDADO |
| CV 4,10 %, banda [1,6496–1,8132] | Estabilidad del umbral | OBTENIDO |

### 2 · Planificado escrito como obtenido

«El sistema se validó con usuarios» es falso mientras `respuestas-sus.csv`
tenga cero filas. Comprueba el estado con `ppi_afirmacion`: `PLANIFICADO` no
se redacta en pasado.

`CLAIM-012` está **REFUTADO** por la propia medición: el sistema no es apto
para operación desatendida, porque el FPR operativo lo desmiente. No debe
aparecer como logro en ningún sitio.

### 3 · Causalidad excesiva

«Las variables multicapa **mejoran** la detección» exige la ablación, que
existe: 66,5 % → 88,8 %, p < 0,001. Pero «el sistema **garantiza** la
seguridad de la red» no se sostiene con nada.

Marca todo verbo que afirme más de lo medido: garantiza, elimina, asegura,
resuelve, demuestra que siempre.

### 4 · Limitación escondida

Estas tres deben aparecer en cualquier documento que presente resultados:

- El FPR de laboratorio **no se sostiene** en operación.
- El motor **se atrasa hasta 161 s** bajo carga sostenida.
- `tls_handshake_failure_ratio_60s` es **constante y no observable**; de 28
  variables, 27 tienen variación.

Ocultarlas no es un descuido de redacción: es lo que el jurado va a buscar.

### 5 · Incoherencia entre documentos

La misma cifra escrita de varias formas —`25,8 %` y `25,81 %`, `23,0 %` y
`22,97 %`— ya ocurrió en este proyecto. Compara el informe consolidado con el
detallado antes de dar ninguno por bueno.

## Lo que sí conviene decir

Declarar una limitación medida **refuerza** el trabajo. Que el pase
contaminado de F6 se conservara en vez de borrarse, o que una fuga se
detectara y se marcara «no debe citarse», son argumentos a favor. Señala
cuando falten.
