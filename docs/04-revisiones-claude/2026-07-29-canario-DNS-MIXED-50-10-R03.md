# Revisión Claude — DNS-MIXED-50-10 R03

Fecha: 29 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión crítica sin operación ni edición.

## Aportes conservados

Claude emitió **ACEPTADA CON LIMITACIONES** y autorizó el preflight de `PING-10/R03`.

Se conservaron:

- integridad PCAP 120/120/120, EVE 130/130 y cero drops;
- una tercera ejecución con artefactos independientes y vector idéntico;
- peso empírico repetido sin diversidad estadística adicional;
- orden fijo de cincuenta consultas válidas seguido por diez NXDOMAIN;
- separabilidad y comportamiento futuro del modelo todavía no demostrados;
- prohibición de atribuir una causa a los cuatro paquetes adicionales.

## Correcciones

El delta 124 de Suricata es un contador de paquetes de captura, no “124 eventos”. EVE contiene 130 eventos: 120 DNS y diez `stats`.

Los cuatro paquetes adicionales no hacen depender la integridad de su identificación. El PCAP contiene los 120 paquetes causales esperados, capturados, recibidos y parseados con cero drops; la causa del delta permanece desconocida.

El manifiesto y el ledger registran escenario y argumentos, pero no demuestran el orden de cada consulta. El orden se verifica en EVE y se deriva del generador versionado.

No se acepta que Isolation Forest “aprenderá tres veces” un efecto concreto ni que el sobreajuste tenga severidad conocida. Solo está probado el mayor peso empírico de una firma; su efecto requiere análisis de sensibilidad.

Un eventual vector exacto de `PING-10/R03` no demostraría que todas las repeticiones `train` coinciden. `DNS-VALID-200/R03` ya produjo ventanas distintas, y los perfiles restantes deben medirse individualmente.

Claude también condicionó R04/R05 a ataques DNS específicos no definidos por el gate. Se conserva el orden del diseño congelado: completar y auditar R03 antes de abrir R04; no se introduce una condición nueva.

## Dictamen consolidado

**ACEPTADA CON LIMITACIONES.** La campaña reproduce íntegramente el perfil benigno 50+10 con evidencia independiente, pero añade un tercer vector exacto y no prueba separabilidad.

Estado: 62/145 aceptadas, R03 4/29, 83 faltantes, cero inválidas/advertencias, diez coincidencias `train` y cero cruces observados.

Siguiente: solo el preflight independiente de `F1N-PING-10-R03`.
