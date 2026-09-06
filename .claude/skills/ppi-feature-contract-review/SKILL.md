---
name: ppi-feature-contract-review
description: "Revisa el contrato de variables multicapa L3/L4/L7 contra el extractor y los datos: fórmulas, ventanas, fuentes, denominadores, causalidad, observabilidad, coste, orden y deriva."
---

# Revisión del contrato de variables

Lee `docs/agent-context/ppi-data-science-context.md` desde la raíz,
`configs/features/multilayer-v2.json`, el extractor y el diccionario generado.

## Controles

1. Compara nombre y orden entre contrato, `manifest.feature_names`, cabeceras
   CSV y entrada del modelo.
2. Para cada variable registra capa, ventana, fuente exacta, fórmula,
   denominador, tratamiento de cero/faltantes, rango y coste en línea.
3. Verifica causalidad: una fila en `T` solo usa `(T-W, T]`.
4. Busca constantes, casi constantes, redundancias, correlación y variables no
   observables. No confundas una definición con una señal efectiva.
5. Revisa consistencia offline/online: ambos caminos deben reutilizar el mismo
   extractor y el mismo orden.
6. Ejecuta pruebas específicas y la suite completa. Una coincidencia de nombres
   no prueba equivalencia semántica.

## Salida

Produce una matriz `variable / contrato / extractor / dato observado / modelo /
estado`, con hallazgos críticos primero. No cambies el contrato congelado sin
crear una versión formal nueva.
