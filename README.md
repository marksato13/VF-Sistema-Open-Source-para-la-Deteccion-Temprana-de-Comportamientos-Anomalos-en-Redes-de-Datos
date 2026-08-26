# Sistema open source para la detección temprana de comportamientos anómalos en redes de datos

Detección de anomalías de red con aprendizaje no supervisado y **control en
línea**: el sistema no solo puntúa el tráfico, también bloquea la IP ofensora
mediante `nftables` en el propio router del laboratorio.

Proyecto de investigación · Universidad Peruana Unión · Facultad de Ingeniería
y Arquitectura · E.P. de Ingeniería de Sistemas.

## Qué hay aquí

| | |
|---|---|
| **Dataset** | `multilayer-v2` — 1 552 ventanas causales, 28 variables L3/L4/L7 |
| **Modelo congelado** | OCSVM (`nu=0.05`), umbral 1,8126 calibrado con `alpha=0.05` |
| **Sistema** | Motor en tiempo real + bloqueo `nftables` + panel de operación |
| **Sensor** | Suricata 8.0.3 sobre AF_PACKET, captura PCAP por campaña |

## Empieza por aquí

| Documento | Qué responde |
|---|---|
| [`docs/dataset/DATASHEET_MULTILAYER_V2.md`](docs/dataset/DATASHEET_MULTILAYER_V2.md) | Procedencia, estructura, particiones, calidad, sesgos y privacidad del corpus |
| [`docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md`](docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md) | Las 28 variables: fórmula, denominador, rangos y observabilidad |
| [`docs/entregables/01-evaluacion-critica/`](docs/entregables/01-evaluacion-critica/informe-evaluacion-critica.md) | Resultados y su crítica, con figuras |
| [`docs/entregables/06-plan-de-mejora/`](docs/entregables/06-plan-de-mejora/README.md) | Debilidades abiertas, priorizadas por impacto y esfuerzo |

## Verificar los artefactos publicados

```bash
sha256sum -c docs/dataset/SHA256SUMS
```

Se publican el dataset, el manifiesto del modelo y **los siete modelos
candidatos** evaluados, byte a byte como los produjo la calibración.

> Los `.joblib` son *pickles*: cargarlos **ejecuta código**. Verifica su
> SHA-256 antes de abrirlos.

## Resultados, en corto

| | |
|---|---|
| ROC-AUC | **0,974** |
| Detección sobre ataques genuinos | **88,8 %** [83,0 – 92,8] |
| Falso positivo en evaluación bloqueada | **4,71 %** |
| **Falso positivo en operación real** | **23–26 %** |
| Bloqueo tras el inicio del ataque | mediana **8 s** |
| Disponibilidad | 100 % en 57 corridas |

La última fila que importa es la cuarta. **El error de laboratorio no se
sostiene sobre tráfico legítimo pesado**, y está medido, no estimado: una
transferencia legítima de 200 Mbit/s llegó a bloquear a un cliente real
durante 120 s. Es la limitación principal del sistema y se declara antes que
cualquier resultado favorable.

## Licencias

| | |
|---|---|
| Código (`scripts/`, `ansible/`, `tests/`, `configs/`) | MIT — [`LICENSE`](LICENSE) |
| Datos y documentación | CC BY 4.0 — [`LICENSE-DATA`](LICENSE-DATA) |

## Uso responsable

El tráfico ofensivo documentado se generó exclusivamente dentro de un
laboratorio aislado, contra máquinas propias y autorizadas. Los perfiles de
ataque **no deben usarse contra sistemas de terceros**.

Un modelo ajustado sobre este corpus **no debe desplegarse en producción sin
recalibrar**; la sección 10 del datasheet detalla los usos previstos y los
que no lo son.

## Contacto

Rubén Mark Salazar Tocas — `ruben.salazar@upeu.edu.pe`
