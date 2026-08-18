# Revisión técnica — TCP-REFUSED-5/R05

Dictamen provisional: **ACEPTAR CON LIMITACIONES**.

La campaña confirma cinco rechazos TCP esperados, PCAP íntegro 10/10/10 y cero
drops. Las ventanas muestran completitud SYN cero y resets coherentes con un
puerto rechazado; no se exige tráfico pesado porque este caso modela un error
legítimo de capa 4.

Auditoría: 141/145 campañas aceptadas, R05 27/29, 4 faltantes, 37 duplicados,
20 cruces y cero inválidas/advertencias. El cruce con la repetición anterior se
conserva como limitación explícita. Scoring y reentrenamiento siguen bloqueados
hasta completar las cuatro celdas restantes.

Claude Code no pudo autenticarse (`Not logged in`); esta nota representa la
revisión técnica reproducible de Codex y queda pendiente de confirmación.
