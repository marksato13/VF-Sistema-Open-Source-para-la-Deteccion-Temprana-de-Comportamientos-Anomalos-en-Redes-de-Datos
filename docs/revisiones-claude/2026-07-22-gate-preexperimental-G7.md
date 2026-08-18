# Revisión adversarial Claude — gate preexperimental G7

Fecha: 22 de julio de 2026. Claude Code fue usado como segundo revisor, sin permisos de edición ni generación de tráfico. Una ejecución acotada con Sonnet no emitió un dictamen utilizable; la revisión que sí produjo contenido fue ejecutada con Haiku. No se atribuye una aprobación a Sonnet.

## CLA-G7-01 — SSH externo evita el punto de captura

1. **Severidad:** crítica.
2. **Hecho:** VM01 alcanzó `172.17.25.112` por ICMP y TCP/22. La ruta es directa por la red externa; Suricata captura `ens35` del Sensor.
3. **Inferencia:** una sesión o carga enviada por esa ruta no forma parte del flujo LAN→Sensor→DMZ y puede quedar fuera de la evidencia experimental.
4. **Riesgo:** punto ciego, PCAP incompleto y afirmaciones de cobertura no defendibles.
5. **Prueba reproducible:** desde VM01 probar ICMP y TCP/22 a `.112`; comparar la ruta con la interfaz capturada. Después de la corrección, ambas pruebas deben fallar y el acceso por `10.10.10.30` debe continuar.
6. **Corrección:** desconectar en ESXi la NIC externa `00:0c:29:15:ad:a7` del Servidor y deshabilitar **Conectar al encender**.
7. **Efecto secundario:** se pierde la ruta externa de recuperación del Servidor; la consola ESXi y PPI-MGMT quedan como vías de administración.
8. **Estado:** confirmada, pendiente de corrección física en ESXi.

## CLA-G7-02 — Interfaz externa del Sensor durante captura oficial

1. **Severidad:** alta.
2. **Hecho:** el Sensor conserva `ens34=172.17.25.111/24` activa, aunque VM01 ya lo administra por `10.10.10.20`.
3. **Inferencia:** mantenerla durante campañas aumenta superficie y permite tráfico administrativo no controlado fuera del diseño experimental.
4. **Riesgo:** contaminación temporal de métricas del host, ruta alternativa de administración y objeción metodológica del jurado.
5. **Prueba reproducible:** desconectar la NIC por MAC, verificar enlace sin portadora y ausencia de ruta externa utilizable, y confirmar que PPI-MGMT, forwarding LAN↔DMZ, NTP y Suricata siguen operativos.
6. **Corrección:** desconectarla durante toda campaña oficial; reconectarla únicamente en mantenimiento sin captura activa.
7. **Efecto secundario:** actualizaciones desde Internet requieren una ventana de mantenimiento o un repositorio/proxy interno.
8. **Estado:** confirmada, pendiente de corrección física en ESXi.

## CLA-G7-03 — Prueba negativa de invisibilidad externa

1. **Severidad:** media.
2. **Hecho:** la topología y las rutas demuestran que el flujo externo no cruza la interfaz de captura, pero todavía no existe una prueba correlacionada antes/después en PCAP/EVE dedicada a ese control negativo.
3. **Inferencia:** un jurado puede exigir evidencia empírica además de la explicación de enrutamiento.
4. **Riesgo:** defensa incompleta del supuesto de observabilidad.
5. **Prueba reproducible:** antes de desconectar, tomar checkpoint de EVE/contadores, emitir un único intento TCP externo identificable y comprobar que no aparece en `ens35`; después, emitir un flujo interno equivalente y comprobar que sí aparece. No incorporar ninguno al dataset.
6. **Corrección:** agregar ambos resultados al cierre G7 y conservar solo metadatos/hashes sanitizados en Git.
7. **Efecto secundario:** la ausencia de un evento de aplicación no prueba por sí sola ausencia de paquetes; la verificación debe hacerse también con una captura acotada y filtro exacto.
8. **Estado:** pendiente; no impide declarar el bypass, pero sí cerrar toda la evidencia empírica del gate.

## CLA-G7-04 — Posible contaminación histórica

1. **Severidad propuesta por Claude:** alta.
2. **Hecho revisado por Codex:** el contrato `f1-normal-v2` requiere 145 campañas; el ensamblador reporta `0` aceptadas, `5` pilotos excluidos por propósito `calibration` y `145` faltantes.
3. **Inferencia original:** campañas aceptadas mientras existía la NIC externa podrían contener tráfico administrativo.
4. **Riesgo:** mezclar ruido ajeno o tráfico sin observar en entrenamiento.
5. **Prueba reproducible:** ejecutar el ensamblador, revisar ledger/propósito y comprobar que ninguna calibración es aceptada como `experiment`.
6. **Corrección:** mantener las calibraciones fuera del dataset y no abrir la campaña oficial hasta cerrar G7.
7. **Efecto secundario:** los pilotos continúan útiles para validar herramientas, pero no para entrenar ni informar métricas finales.
8. **Estado:** rechazada para un dataset oficial histórico porque todavía no existe ninguno aceptado; el riesgo prospectivo queda controlado por el bloqueo G7.

## Dictamen cruzado

Claude y Codex coinciden en **NO APTO**. La corrección no consiste en borrar direcciones desde Linux: debe desconectarse cada NIC externa en ESXi y desactivarse su reconexión automática. Después se ejecutará el gate positivo y negativo descrito en `docs/fase01-diseno-experimental/13-auditoria-preexperimental-G7.md`.
