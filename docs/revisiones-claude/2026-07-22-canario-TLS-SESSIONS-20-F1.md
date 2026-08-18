# Revisión Claude — canario de recambio TLS F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial de un resumen técnico, sin herramientas, edición ni operación del laboratorio.

## Dictamen

Claude emitió **ACEPTAR CONDICIONADO**. Confirmó que no existen fallos bloqueantes de integridad: veinte resultados HTTP 200, veinte conexiones completas, veinte eventos TLS, cero pérdidas, dos filas elegibles y admisión limpia por el ensamblador.

## Condiciones aceptadas

La campaña debe describirse como un patrón estrecho:

- veinte sesiones secuenciales en aproximadamente 2.46 segundos, cerca de 8.1 por segundo;
- un cliente, un destino y una sola combinación JA3/JA3S/JA4;
- dos ventanas que comparten el mismo horizonte TLS y no equivalen a dos repeticiones independientes;
- certificado autofirmado y validación PKI desactivada con `--insecure`;
- 13.9211 % de paquetes entre 500–1500 bytes, propio de sesiones cortas y no de una descarga pesada.

El HTTP 200 está probado en el extremo Cliente. Suricata no produce HTTP ni `fileinfo` sobre la carga cifrada; sus veinte eventos TLS constituyen la observación L7 pasiva usada por las features.

## Correcciones al dictamen

Claude llamó «calibración» al perfil, pero manifiesto y ledger registran `purpose=experiment`, `partition=train` y `R01`. Es una campaña oficial aceptada.

Calcular Pearson entre dos vectores de 14 features con unidades heterogéneas no demostraría dependencia entre ventanas. La dependencia ya se establece por procedencia y tiempo: ambas filas pertenecen a la misma campaña y sus horizontes de 60 segundos solapan el mismo episodio. La unidad de partición y evaluación debe ser la campaña.

Claude pidió que `HTTP-MULTI-1` tuviera dos clientes, concurrencia y mayor duración. Eso no corresponde a la matriz congelada:

- `HTTP-MULTI-1`: un Cliente, tres destinos lógicos, una solicitud secuencial por VIP;
- `HTTP-MULTI-5`: un Cliente, tres destinos lógicos, cinco solicitudes secuenciales por VIP;
- `HTTP-C2/C4/C8`: concurrencia de 2, 4 u 8 flujos.

Cambiar `HTTP-MULTI-1` después de congelar la matriz rompería la comparabilidad. Su objetivo es L3 multidestino, no concurrencia.

## Riesgo de generalización

Aceptar automatización autorizada a 8.1 sesiones/s puede elevar el rango normal de `tls_session_rate_60s`. No implica que una ráfaga ofensiva idéntica deba considerarse normal: las pruebas F3 deberán aportar tasas, destinos y combinaciones multicapa diferenciables. El resultado final debe medir explícitamente falsos negativos.

## Próximo paso

Se autoriza `HTTP-MULTI-1/R01` con su contrato original y un nuevo preflight. No se atribuyen a TLS-SESSIONS-20 diversidad de clientes, destinos, certificados, huellas o concurrencia.
