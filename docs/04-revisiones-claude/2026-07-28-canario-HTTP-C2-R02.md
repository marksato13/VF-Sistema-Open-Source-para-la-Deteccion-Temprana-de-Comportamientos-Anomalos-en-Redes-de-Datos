# Revisión Claude — HTTP-C2 R02

Fecha: 28 de julio de 2026. Claude Code 2.1.217, modelo Haiku.

Claude emitió **ACEPTAR CON LIMITACIONES** y autorizó un preflight nuevo de `HTTP-C4/R02`. Reconoció la concurrencia real, las dos transferencias completas, la captura sin drops, la cobertura pesada, el truncamiento de `fileinfo`, la fila residual y la variación no explicada frente a R01.

Se conservaron:

- dos flujos solapados del mismo Cliente, no dos clientes;
- 93.6718 % de paquetes entre 500–1500 bytes;
- `fileinfo` truncado no demuestra inspección íntegra del cuerpo;
- los seis paquetes finales son teardown normal y los horizontes 30/60 s explican attempts/HTTP;
- la diferencia R01/R02 se conserva sin causalidad;
- el límite de `curl` es nominal, no un shaper exacto.

Se corrigieron o descartaron:

- C4 usa `4 100MB 5M`, no cuatro flujos a `10M`;
- la matriz estima 460,000,000 bytes de PCAP para C4, no 555 GB;
- no existe un requisito de 140 GiB libres: se aplica el gate de almacenamiento versionado;
- no están contratados los umbrales de 90 % pesado, SYN en menos de 50 ms ni vector distinto de C2;
- C4 tiene cuatro flujos, no ocho;
- no se adoptan posibles causas sobre jitter, buffers, Nagle, TSO o virtualización;
- `fileinfo` se trunca por el límite de inspección, no por un supuesto “límite de EVE”;
- no se afirma que EVE esté libre de toda contaminación más allá de los 16 eventos auditados.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Estado global 48/145; R02 19/29.
