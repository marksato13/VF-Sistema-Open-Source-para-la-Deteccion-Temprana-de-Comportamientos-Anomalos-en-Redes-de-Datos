---
name: ppi-operational-validation
description: "Valida el sistema PPI desplegado y contrasta métricas offline con tráfico real: falsos positivos, lead-time, bloqueo, expiración, disponibilidad, atraso y contaminación entre corridas."
---

# Validación operacional

Lee `docs/agent-context/ppi-data-science-context.md` desde la raíz y el diseño del motor.
No generes tráfico ofensivo ni cambies VMs sin autorización explícita.

## Controles

1. Fija unidad, perfiles, tasas, tiempos de asentamiento y criterios de éxito
   antes de ejecutar.
2. Separa pase contaminado, pase limpio y pruebas de aislamiento.
3. Mide falsos positivos benignos con numerador, denominador e intervalo;
   contrástalos con 13/276 offline.
4. Para ataques mide detección, bloqueo efectivo, lead-time y expiración nativa.
5. Registra backlog del motor y excluye tiempos cuando no estaba al día.
6. Distingue “cero caídas registradas” de “100 % verificado”; documenta campos
   ausentes.
7. Conserva hashes, timestamps, configuración y evidencia agregada saneada.

## Salida

Entrega matriz por corrida, resumen por perfil, intervalos y modos de fallo. No
promuevas umbrales nuevos con los mismos datos operativos usados para juzgarlos.
