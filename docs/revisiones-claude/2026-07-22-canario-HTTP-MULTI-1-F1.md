# Revisión Claude — canario HTTP multidestino F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen técnico, sin herramientas, edición ni operación.

## Dictamen

Claude emitió **ACEPTAR CONDICIONADO**. Confirmó el cumplimiento del objetivo acotado: tres conexiones completas, tres destinos lógicos, tres HTTP 200, PCAP/EVE íntegros, cero pérdidas y `unique_dst_ip_ratio_30s=1`.

## Límites confirmados

- las tres VIP pertenecen a una sola VM y solo aportan diversidad lógica L3;
- existe un único Cliente, puerto 80 y ruta `/health`;
- las tres solicitudes ocurren en aproximadamente 0.25 segundos;
- una sola fila no permite medir varianza intra-campaña;
- las respuestas pequeñas producen 0 % de paquetes entre 500–1500 bytes;
- la IP externa de Kali sigue configurada en una interfaz desconectada y debe comprobarse en cada preflight.

La campaña es un punto de la matriz completa, no una distribución autosuficiente. `HTTP-MULTI-5` y las repeticiones R02–R05 ampliarán la evidencia sin cambiar el contrato.

## Correcciones al dictamen

Claude describió tres destinos como «tres muestras» y sugirió que la fila correspondía a calibración. Manifiesto y ledger demuestran `purpose=experiment`, `partition=train` y una sola fila oficial. Los tres destinos son observaciones que forman el vector, no réplicas experimentales.

Claude propuso comprobar si el ratio 1.0 era exclusivo de esta campaña. La auditoría de los CSV aceptados mostró que no lo es: aparece repetidamente en HTTP/HTTPS de una sola conexión y en una fila de HTTP 404. En esos casos significa 1/1; aquí significa 3/3. Las features de tasa e intentos permiten distinguir los contextos.

La condición de no entrenar un modelo final con esta fila aislada ya está impuesta por el ensamblador: mientras falte una de las 145 celdas, `ready_to_build=false` y no se escriben splits.

## Interpretación defendible

`unique_dst_ip_ratio_30s=1` demuestra que todos los intentos de la ventana apuntaron a direcciones distintas. No demuestra hosts físicos distintos ni normalidad universal. Una exploración ofensiva también puede producir un ratio alto; F3 deberá separarla mediante tasa, número de intentos y señales multicapa.

`unique_dst_port_ratio_30s=1/3` es correcto: los tres intentos usan un único puerto, 80. Esta combinación —diversidad IP máxima y diversidad de puerto baja— representa el escenario diseñado.

## Próximo paso

Se autoriza `HTTP-MULTI-5/R01` con su contrato congelado: el mismo Cliente realizará cinco solicitudes secuenciales por cada VIP. Su ratio esperado es 3 destinos / 15 intentos = 0.2. La concurrencia continúa separada en `HTTP-C2/C4/C8`.
