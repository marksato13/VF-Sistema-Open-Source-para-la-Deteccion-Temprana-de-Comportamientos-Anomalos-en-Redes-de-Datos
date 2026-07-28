# Revisión Claude — HTTP-C4 R02

Fecha: 28 de julio de 2026. Claude Code 2.1.217, modelo Haiku.

Claude emitió **ACEPTAR CON LIMITACIONES** y condicionó el preflight de C8. Se conserva la aceptación; las condiciones se sustituyen por los gates versionados del proyecto.

Se conservaron:

- cuatro flujos realmente solapados de un solo Cliente;
- 93.6295 % de paquetes en el rango pesado;
- variación de tamaños R01/R02 sin causa medida;
- `fileinfo` truncado y ausencia de inspección completa;
- tres ventanas correlacionadas del mismo episodio;
- CPU máxima de 72.24 % sin umbral formal y con cero drops.

Se corrigieron o descartaron:

- −2.5508 puntos no se califican “significativos” sin un criterio definido;
- no se extrapola CPU linealmente a 144 % ni packet rate a C8;
- no existe en este gate un requisito P95 de 500 ms;
- no se exige calibración C8 previa, buffer `-B 65536`, CPU preflight menor de 30 %, gates G7/G8 ni canario iperf;
- la igualdad `310555=310559−4` no demuestra cero drops; lo hacen los contadores específicos;
- `56008−56000` compara puertos, no velocidades; el rango real fue 2,110 B/s;
- la tercera fila contiene carga pesada además del cierre y terminó a `20:16:33.919678 UTC`;
- la ausencia de mDNS no prueba un cambio de alcance;
- no se proyectan payloads de ataque en una campaña normal F1;
- R02 continúa 20/29 y el siguiente perfil es C8/R02, no R03.

**Dictamen consolidado: ACEPTADA CON LIMITACIONES.** Estado global 49/145; R02 20/29.
