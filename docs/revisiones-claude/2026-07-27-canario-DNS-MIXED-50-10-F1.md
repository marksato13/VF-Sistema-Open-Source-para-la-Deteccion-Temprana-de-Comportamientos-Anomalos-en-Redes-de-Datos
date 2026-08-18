# Revisión Claude — canario DNS-MIXED-50-10 F1

Fecha: 27 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo: Haiku. Alcance: revisión técnica sin operación, herramientas ni edición.

## Aporte válido

Claude emitió **ACEPTAR CON LIMITACIONES** para `F1N-DNS-MIXED-50-10-R01`. Su observación central se conserva:

- los diez NXDOMAIN tienen etiqueta benigna porque fueron errores sintéticos intencionales dentro de un laboratorio controlado, no porque NXDOMAIN sea universalmente benigno;
- `dns_nxdomain_ratio_60s=10/60=0.16666667` está medido correctamente;
- el bloque fijo de cincuenta consultas válidas seguido de diez inválidas introduce sesgo temporal;
- una sola fila representa una ventana de un episodio, no una repetición independiente;
- las futuras anomalías DNS F3 aún no se capturaron, por lo que no se ha demostrado separabilidad;
- aceptar esta celda no demuestra desempeño de Isolation Forest, falsos positivos ni generalización.

## Errores y correcciones

La primera respuesta cambió el estado real del ensamblador a 28 aceptadas y 117 faltantes, propuso como siguiente `HTTP-404-5/R01` —ya ejecutado— e inventó una asignación R02–R05 de particiones. Los valores vinculantes son 27/145 aceptadas, 0 inválidas, 0 advertencias, 118 faltantes; la matriz y el ensamblador gobiernan la partición y el siguiente perfil es `PING-10/R01`.

La segunda respuesta corrigió esos puntos, pero afirmó que había dos filas. Existe una sola fila elegible. La tercera inventó un span de 1.248 s; el PCAP mide 1.260866 s. La última corrección incorporó nombres `B-DNS` y `C-DNS` que no pertenecen a la matriz congelada y atribuyó imprecisamente el ratio al “flujo EVE”. El ratio procede del extractor al relacionar consultas y respuestas EVE dentro de la ventana.

Estas salidas no se utilizaron como fuente de cifras. Manifest, PCAP, EVE, reporte de extracción, ledger y auditoría del ensamblador son la fuente de verdad.

## Dictamen consolidado

**ACEPTAR CON LIMITACIONES.** La evidencia técnica es íntegra: 60 consultas, 50 respuestas válidas, 10 NXDOMAIN, 120/120 paquetes, cero drops, una fila elegible y hashes válidos. El orden determinista y la separabilidad aún no demostrada quedan como límites explícitos, no como motivos para alterar retroactivamente la campaña congelada.

Siguiente: `PING-10/R01`, después de un preflight completo.
