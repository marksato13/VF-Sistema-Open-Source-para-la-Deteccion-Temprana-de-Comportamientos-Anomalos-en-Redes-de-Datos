# Preparación de captura multicapa v2

Fecha: 2026-08-12. Estado: servicios desplegados y pilotos de conectividad correctos; captura oficial pendiente.

## Ya preparado

- Contrato `configs/features/multilayer-v2.json` con 28 variables.
- Extractor v2 y cuatro pruebas sintéticas correctas.
- Matriz normal `configs/campaigns/multilayer-v2-normal.json` con seis perfiles
  iniciales y cinco repeticiones por perfil (`train`, `validation`, `test`).
- Matriz separada `configs/campaigns/multilayer-v2-anomalies.json`; sus perfiles
  no pueden entrar al entrenamiento.
- Escenarios de cliente `api-normal` y `api-auth-fail`, además de `dns-multi`.
- Validación de sintaxis Bash, Python y Ansible ejecutada localmente.
- VM03: `ppi-api` activo; `/api/health` HTTPS devuelve 200, login válido 200,
  login inválido 401, PUT 204 y DELETE 403. Los logs JSONL de autenticación se
  escriben correctamente.
- VM05: `api-normal`, `api-auth-fail` y `dns-multi 10` ejecutados como pilotos;
  DNS devolvió las cinco identidades internas esperadas.
- VM02: Suricata activo con `kernel_drops=0`, `kernel_ifdrops=0` y
  `decoder_invalid=0` en la verificación previa.

## Orden de ejecución pendiente

1. Desde la consola de VM03 otorgar temporalmente `sudo` a `useransible`.
2. Ejecutar el playbook del servidor para instalar `ppi-api`, Nginx y dnsmasq;
   probar `/api/health`, login correcto, login 401, PUT 204, DELETE 403 y
   registrar una respuesta 5xx controlada sólo en un piloto.
3. Ejecutar el playbook de sensor/cliente para publicar el generador v2.
4. Ejecutar un piloto normal por perfil y revisar PCAP, EVE, logs y JSONL.
5. Cerrar cualquier discrepancia y sólo después iniciar las cinco repeticiones.
6. Construir episodios independientes hasta 2.000–3.000 ventanas elegibles.
7. Congelar normales, calibrar y ejecutar las anomalías en evaluación ciega.

## Bloqueos honestos

La API ya está desplegada. El permiso `sudo` total temporal fue retirado de
VM03 después del despliegue; el sensor conserva únicamente los controladores
restringidos previstos. Las matrices son planes ejecutables, no evidencia. No se afirma todavía que
existan 2.000–3.000 filas ni que las features nuevas estén validadas en tráfico
real. No se requiere Internet para estas campañas.
