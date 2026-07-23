# Revisión Claude — reintento HTTP concurrente C8 F1

Fecha: 23 de julio de 2026. Herramienta: Claude Code 2.1.217. Modelo final: Haiku. Alcance: revisión adversarial de archivos pequeños y resumen técnico; Claude no operó el laboratorio ni abrió los PCAP.

## Acceso y método

Los primeros intentos de revisión no produjeron dictamen porque el sandbox de Claude no podía leer directamente `/srv/ppi-evidence` o agotó el tiempo. Se creó una copia temporal, ignorada por Git, de nueve archivos de texto: manifest, deltas, resultado de captura, resumen de longitudes, salida del escenario, reporte y CSV de features, ledger y `archive.json` del intento fallido. No se copiaron PCAP ni payload. La carpeta temporal se eliminó al terminar; los originales permanecen en el volumen oficial.

Claude recibió además los resultados reproducibles de flags TCP, hashes y ensamblador. Su revisión no sustituye la verificación de SHA-256 ejecutada por Codex.

## Errores encontrados en la primera revisión

La primera respuesta de Claude mezcló el `archive.json` del intento fallido con el manifest del reintento actual y declaró una contradicción inexistente. También:

- calculó 176 Mbit/s en vez de 135.555656 Mbit/s;
- interpretó `unique_dst_ip_ratio_30s=0.125` como ocho destinos, cuando significa un destino entre ocho intentos;
- afirmó independencia entre ventanas del mismo episodio.

Se rechazaron esas conclusiones y se solicitó una segunda revisión con los commits, rutas y fórmulas explícitos.

## Separación corregida

Claude reconoció que:

- `attempt-01`, commit `99919343017...`, es solo el intento fallido archivado;
- el reintento actual, commit `391624019497...`, permanece activo como `completed/experiment/train`;
- no existe colisión de IDs ni contradicción de estados;
- el throughput correcto es aproximadamente 135.56 Mbit/s;
- `0.125=1/8` representa concentración legítima en un destino;
- las seis filas son autocorrelacionadas y deben agruparse por `campaign_id`;
- el ensamblador confirmó 16 aceptadas, 0 inválidas y 129 faltantes.

## Segunda corrección de cifras

La respuesta corregida todavía arrastró tres valores históricos. Se aclaró por tercera vez:

| Ejecución | Paquetes tcpdump | Rango 500–1500 | Duración de flujos |
|---|---:|---:|---:|
| intento fallido C8 | 596,704 capturados; 476 drops | 97.1282 % | ~49.51 s |
| calibración C8 | 605,266; cero drops | 95.8258 % | ~49.52 s |
| reintento oficial C8 | **600,128; cero drops** | **96.6514 %** | **49.505–49.511 s** |
| C4 histórico | 301,517; cero drops | 96.1803 % | ~19.5 s |

Claude confirmó que estas correcciones no crean un bloqueo y condicionó la aceptación a hashes y preflight G7.

## Cierre de condiciones

Ambas condiciones estaban verificadas antes de la revisión:

1. `SHA256SUMS` de campaña y features pasó; los hashes raíz están documentados en `../07-dataset-campanas/23-canario-HTTP-C8-F1.md`.
2. El preflight G7 comprobó Git, volumen, ID libre, NTP, aislamiento, bypass negativo, rutas, servicios, Suricata, archivo y generador.

Por tanto, el dictamen operativo queda **ACEPTAR CON LIMITACIONES**.

## Límites

- Las seis filas pertenecen a un episodio y no representan seis repeticiones.
- Los ocho flujos usan un Cliente, un destino, un archivo y HTTP.
- La celda prueba carga y concurrencia legítimas, no diversidad de usuarios ni destinos.
- El resultado valida el búfer en las condiciones observadas, no garantiza cero drops futuros.
- `fileinfo=TRUNCATED` limita inspección de Suricata; no invalida las descargas verificadas.

Esta revisión conserva deliberadamente las correcciones a Claude: la revisión cruzada solo aporta valor si sus afirmaciones también se contrastan con evidencia.
