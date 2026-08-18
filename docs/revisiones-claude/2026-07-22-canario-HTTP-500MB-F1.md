# Revisión Claude — canario HTTP 500 MB F1

Fecha: 22 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión adversarial del resumen del bundle, sin editar archivos ni operar el laboratorio.

## Dictamen

Claude emitió **ACEPTAR con observaciones críticas** y autorizó avanzar al siguiente canario. Reconoció:

- descarga HTTP 200 completa de 524,288,000 bytes;
- dos PCAP rotados íntegros, 368,467 paquetes parseados y capturados;
- cero drops, ifdrops, errores de decodificación y overflow;
- 98.3499 % de paquetes IPv4 entre 500 y 1500 bytes;
- recursos del Sensor holgados;
- EVE 19/19 y límite `fileinfo=102400` ya conocido;
- cuatro filas extraídas y aceptación del ensamblador.

## Observaciones verificadas

### Elegibilidad y propósito

Claude preguntó si las cuatro filas realmente tenían `eligible_training=true` y si `purpose=experiment` podría excluirlas. El CSV contiene cuatro filas con `eligible_training=True`; manifiesto y ledger coinciden en `experiment/R01/train`; el ensamblador rechaza calibraciones y acepta la campaña sin advertencias. No existe ambigüedad pendiente.

### Paquetes menores de 500 bytes

Claude pidió descartar fragmentación o anomalía TCP en los 6,080 paquetes pequeños. La lectura independiente de ambos PCAP confirmó:

- 6,080/6,080 son TCP;
- cero fragmentados;
- 6,075 no tienen payload TCP;
- 5,775 miden 52 bytes y 6,071 llevan flag ACK;
- los cinco con payload corresponden a segmentos PSH/ACK pequeños.

Son control y cierre normales de la sesión, no una señal anómala.

### Diversidad

Claude señaló correctamente que este canario aislado no demuestra diversidad estadística de todo el dataset. La matriz completa aborda esa limitación mediante 29 perfiles, cinco repeticiones, múltiples destinos, concurrencia, DNS, HTTP/HTTPS, ICMP, TCP, UDP y tráfico mixto. No se atribuye a una sola transferencia lo que corresponde demostrar al conjunto.

## Límite acordado

Se valida captura, transferencia, rotación, integridad, volumen legítimo pesado y extracción de cuatro ventanas. No se valida inspección completa de payload L7 ni suficiencia estadística del dataset final.
