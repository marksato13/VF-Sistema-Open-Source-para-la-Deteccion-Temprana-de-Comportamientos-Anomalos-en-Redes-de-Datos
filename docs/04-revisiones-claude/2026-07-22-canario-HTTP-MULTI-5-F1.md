# Revisión Claude — canario HTTP multidestino repetido F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial de un resumen técnico, sin herramientas, edición ni operación.

## Dictamen

Claude emitió **ACEPTAR CONDICIONADO**. Confirmó integridad de PCAP/EVE, quince HTTP 200, cero pérdidas, una fila elegible con ratio 0.2, recursos holgados y admisión limpia por el ensamblador.

## Límites confirmados

- las tres VIP son identidades lógicas de una sola VM;
- un Cliente, puerto 80 y ruta `/health`;
- quince solicitudes secuenciales concentradas en aproximadamente 1.67 segundos;
- una sola fila elegible;
- 0 % de paquetes pesados, esperado para respuestas de 36 bytes;
- Kali conserva una IP en su NIC externa desconectada y debe seguir dentro del preflight.

La campaña demuestra el punto L3 3/15 = 0.2 bajo el contrato elegido. No demuestra diversidad física ni una distribución estadística completa. El ensamblador impide entrenar hasta completar las 145 celdas.

## Correcciones al dictamen

La revisión describió treinta flows. El PCAP contiene quince conexiones: 15 SYN, 15 SYN/ACK y 30 FIN. Los treinta FIN son dos cierres por conexión, no treinta flujos.

Manifiesto y ledger registran `purpose=experiment`, `partition=train`; no es calibración.

Claude propuso comparar RTT y jitter entre VIP lógicas y servidores físicos. Las catorce features actuales no incluyen RTT ni jitter. Diferencias temporales podrían afectar tasas de forma indirecta, pero no existe una variable de latencia que el modelo consuma.

Claude citó una dirección SSH externa ajena a la topología. El gate real usa PPI-MGMT `10.10.10.40` y verifica localmente `eth0`, rutas y bloqueo de `172.17.25.113`; no se adopta la dirección inventada.

## Riesgo de falsos negativos

Una enumeración ofensiva de destinos también puede producir `unique_dst_ip_ratio_30s` alto o bajo según su número de intentos. Esta campaña normaliza únicamente tres VIP autorizadas con conexiones completas, HTTP 200 y tasa conocida. F3 deberá combinar procedencia, intensidad, fallos, puertos y demás señales para medir si el modelo distingue enumeración.

## Próximo escenario y corrección de unidades

Se autoriza `HTTP-C2/R01` con el contrato congelado:

- un Cliente y un destino;
- dos descargas concurrentes de 100 MB;
- `10M` de `curl` por flujo, 10 MiB/s o aproximadamente 83.89 Mbit/s decimales;
- agregado máximo aproximado de 20 MiB/s o 167.77 Mbit/s;
- duración ideal cercana a diez segundos por descarga, sujeta al entorno.

No representa múltiples clientes ni múltiples destinos. La concurrencia es de flujos originados por el mismo Cliente.
