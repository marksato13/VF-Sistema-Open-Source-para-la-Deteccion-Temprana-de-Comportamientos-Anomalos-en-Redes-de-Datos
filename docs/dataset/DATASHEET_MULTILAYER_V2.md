# Datasheet — `multilayer-v2`

> **Generado**, no redactado a mano: `scripts/entregables/generar_datasheet.py`.
> Toda cifra se deriva de los artefactos congelados; ninguna se transcribe.

Sigue **las once secciones de la rúbrica de datasheet**, en ese orden, para que cada una pueda auditarse por separado.

---

## 1 · Identidad, versión, responsables, licencia y contacto

| | |
|---|---|
| **Nombre del corpus** | `multilayer-v2` |
| **Estado** | **Congelado.** Los CSV no se modifican; toda corrección es documental |
| **Contrato de variables** | `multilayer-v2` · `configs/features/multilayer-v2.json` |
| **Versión de este datasheet** | 1.0 — 25 de agosto de 2026 |
| **Ventanas** | 1 373 normales + 179 anómalas = **1 552** |
| **Episodios** | 220 normales + 132 anómalos |
| **Variables** | 28 definidas · **27 con variación observable** |
| **SHA-256 normal** | `3846d44c0fe32ac4b4c98f022adac7c459c6add2c6b95062e6bb3237fe9b28ab` |
| **SHA-256 anómalo** | `d115ef987cbd845118038314b7c55a7ad4e359ff4ebfd486c0e664ed3d8078c3` |

> **Por qué no se llama `v2.1`.** Declarar una variable como no observable es una **anotación documental**, no un corpus nuevo. El dataset sigue siendo `multilayer-v2` con los mismos hashes; lo que se versiona por separado es este documento.

### Responsables, licencia y contacto

| | |
|---|---|
| **Autor** | Rubén Mark Salazar Tocas |
| **Coautor** | Uziel Elias Sauñe Fernandez |
| **Afiliación** | Universidad Peruana Unión · Facultad de Ingeniería y Arquitectura · E.P. de Ingeniería de Sistemas |
| **Contacto** | `ruben.salazar@upeu.edu.pe` |
| **Licencia de los datos** | **CC BY 4.0** — [`LICENSE-DATA`](../../LICENSE-DATA) |
| **Licencia del código** | MIT — [`LICENSE`](../../LICENSE) |
| **Repositorio** | https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos |

### Cómo citar

> Salazar Tocas, R. M. y Sauñe Fernandez, U. E. (2026). *Dataset `multilayer-v2`:
> ventanas causales multicapa para detección de anomalías de red* [Conjunto de
> datos]. Universidad Peruana Unión.

### Registro de cambios

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 25 de agosto de 2026 | Primer datasheet canónico. El corpus no cambia; se documenta |

El historial del corpus, campaña por campaña, está en [`docs/fase03-dataset/README.md`](../fase03-dataset/README.md).

---

## 2 · Topología y entorno de captura

Laboratorio virtualizado sobre VMware ESXi, con tres redes separadas. El Sensor **es** el router entre la red de clientes y la red de servicio, así que todo el tráfico observado lo atraviesa por diseño, no por replicación.

```text
Cliente 10.20.0.20 ─┐
                     ├─► Sensor 10.20.0.1 / 10.30.0.1 ─► Servidor 10.30.0.10
Kali 10.20.0.100 ───┘
```

| Rol | VM | Red de clientes | Red de servicio |
|---|---|---|---|
| Sensor, router e IDS | VM02 | `10.20.0.1` | `10.30.0.1` |
| Servidor protegido | VM03 | `—` | `10.30.0.10` |
| Kali · tráfico ofensivo | VM04 | `10.20.0.100` | `—` |
| Cliente legítimo | VM05 | `10.20.0.20` | `—` |

### Instrumentación

| | |
|---|---|
| **IDS** | Suricata 8.0.3, AF_PACKET sobre `ens35`, `HOME_NET=[10.30.0.0/24, 10.20.0.20/32]`, reglas Emerging Threats Open |
| **Salida de eventos** | EVE JSON — se consumen `http`, `dns` y `tls` |
| **Captura de paquetes** | `tcpdump` por campaña mediante un helper con parámetros fijos |
| **Interfaz y filtro** | `ens35`; tráfico bidireccional `10.20.0.0/24` ↔ `10.30.0.0/24` |
| **Snaplen** | Paquete completo (`-s 0`) |
| **Calentamiento antes de medir** | 60 s |
| **Asentamiento y enfriamiento** | 9 s y 30 s entre repeticiones |

**Techos de tasa calibrados.** 200 Mbit/s TCP, 50 Mbit/s UDP y 20 MB/s por transferencia HTTP/HTTPS. Se fijaron tras medir pérdida real: una prueba sin limitación a 2,58 Gbit/s produjo 389 932 descartes y **está excluida del corpus**. El generador rechaza valores por encima de esos techos.

**Aislamiento.** Las interfaces externas de VM02–VM05 permanecen desconectadas durante las campañas. El riesgo de una ruta que evitara al Sensor no es hipotético: se comprobó y se cerró.

---

## 3 · Unidad de observación y causalidad

Una fila = **una IP iniciadora** observada hasta un instante `T`, emitida cada **10 s**.

Las ventanas son deslizantes y **estrictamente causales**:

```text
(T − W, T]   con W ∈ {10, 30, 60} segundos
```

Ningún paquete o evento posterior a `T` participa en la fila cerrada en `T`. Eso permite decidir **sin esperar el cierre del flujo** y elimina la fuga temporal por construcción, no por convención.

### Atribución a la entidad iniciadora

| Protocolo | Iniciador |
|---|---|
| TCP | Quien envía el primer `SYN` sin `ACK` |
| UDP | Quien envía el primer datagrama observado |
| ICMP eco | Quien envía el `echo request` |
| Captura empezada a mitad | El primer emisor observado — **limitación registrada** |

Las respuestas se atribuyen a la misma entidad iniciadora. Solo se emiten filas para `10.20.0.0/24`: el servidor no genera una fila propia por responder.

**Verificado con prueba unitaria:** un evento posterior a `T` no altera una ventana ya cerrada. Es la respuesta directa al requisito de no usar información futura.

---

## 4 · Catálogo de escenarios

### Tráfico legítimo — 44 perfiles

Generados desde VM05 con 5 repeticiones cada uno. Agrupados por estrato declarado:

| Estrato | Perfiles |
|---|---:|
| `api-5xx` | 2 |
| `api-auth-failure` | 3 |
| `api-methods` | 2 |
| `dns-baseline` | 1 |
| `dns-diversity` | 3 |
| `dns-nxdomain` | 3 |
| `http-concurrency` | 3 |
| `http-duration-diversity` | 6 |
| `http-error` | 1 |
| `http-multi-destino` | 2 |
| `icmp-l3` | 3 |
| `ip-fragmentation` | 2 |
| `multilayer-mixed` | 1 |
| `tcp-duration-diversity` | 1 |
| `tcp-heavy` | 1 |
| `tcp-rate-diversity` | 3 |
| `tcp-rst` | 1 |
| `tls-session` | 3 |
| `udp-rate-diversity` | 3 |
| **Total** | **44** |

Sobre **17 generadores distintos**: `api-auth-fail`×3, `api-normal`×4, `dns-mixed`×3, `dns-multi`×3, `dns-valid`×1, `frag-udp`×2, `http`×3, `http-concurrent`×3, `http-missing`×1, `http-multi`×2, `https`×3, `https-sessions`×3, `iperf-tcp`×5, `iperf-udp`×3, `mixed-light`×1, `ping`×3, `tcp-refused`×1.

> **Tráfico pesado incluido a propósito.** El corpus contiene transferencias de 10 MB a 1 GB y de 2 a 8 flujos concurrentes, con una muestra medida en **90,84 % de cargas TCP entre 500 y 1500 bytes**. Un paquete grande no puede convertirse por sí solo en señal de ataque, y por eso el tráfico pesado entra como normalidad.

### Tráfico anómalo — 9 familias

| Familia | Origen | Escenario | Ventanas | Episodios |
|---|---|---|---:|---:|
| `ANOM-KALI-SYN-RATE-50` | **Kali (VM04)** | `tcp-syn-rate` | 31 | 20 |
| `ANOM-KALI-PORT-SCAN` | **Kali (VM04)** | `tcp-port-scan` | 20 | 20 |
| `ANOM-KALI-PORT-SCAN-WIDE` | **Kali (VM04)** | `port-scan-wide` | 20 | 20 |
| `ANOM-KALI-UDP-PROBE-50` | **Kali (VM04)** | `udp-probe` | 40 | 20 |
| `ANOM-KALI-PASSWORD-SPRAY-50` | **Kali (VM04)** | `password-spray` | 29 | 20 |
| `ANOM-KALI-DNS-ENTROPY-50` | **Kali (VM04)** | `dns-entropy` | 21 | 20 |
| `ANOM-SYN-RATE-10` | VM05 reetiquetado | `tcp-refused` | 6 | 4 |
| `ANOM-DNS-NX-200` | VM05 reetiquetado | `dns-nxdomain` | 6 | 4 |
| `ANOM-AUTH-FAIL-50` | VM05 reetiquetado | `api-auth-fail` | 6 | 4 |
| **Total** | | | **179** | **132** |

---

## 5 · Etiquetado y procedencia

El etiquetado es **por diseño experimental, no por juicio posterior**: la etiqueta proviene de qué campaña generó el tráfico, se une **después** de extraer las variables y nunca entra al vector del modelo.

| Etiqueta | Ventanas | Procedencia |
|---|---:|---|
| `normal` | 1373 | Cliente legítimo VM05, campañas `F2N-*` |
| `anomaly` (Kali real) | 161 | Kali VM04, campañas `F2A-ANOM-KALI-*` |
| `anomaly` (heredada) | 18 | VM05 reetiquetado, generación anterior |

> **Las 18 heredadas se reportan por separado, siempre.** No son tráfico ofensivo genuino: son escenarios del cliente legítimo reetiquetados en una generación anterior del corpus. Mezclarlas con las 161 de Kali inflaría cualquier métrica de detección. Por eso el desempeño se publica en las dos formas.

### Lo que falta en el protocolo de etiquetado

No existe un procedimiento canónico escrito para **casos ambiguos** ni una segunda revisión independiente de etiquetas. En este corpus el riesgo es bajo, porque la etiqueta la determina la máquina de origen y no una interpretación; pero el procedimiento debería existir antes de incorporar tráfico capturado en producción.

---

## 6 · Particiones y prevención de fuga

| Partición | Repeticiones | Ventanas | Episodios |
|---|---|---:|---:|
| `train` | R01, R02, R03 | 824 | 132 |
| `validation` | R04 | 273 | 44 |
| `test` | R05 | 276 | 44 |
| `evaluation_only` | — | 179 | 132 |

### Lo que sí está garantizado

- **Ningún episodio se reparte entre particiones** — gate `no_episode_split`, 0 violaciones.
- **Ventanas solapadas del mismo episodio no se reparten** al azar entre conjuntos.
- **El escalador y los hiperparámetros se ajustaron solo con `train`**; el umbral se calibró una sola vez con `validation`.
- **Las campañas de calibración quedan fuera** de las tres particiones (`excluded_calibration`).
- **Ningún grupo de vectores duplicados cruza etiqueta ni partición** — dos gates de tolerancia cero.

### La limitación que hay que declarar primero

> **La partición se hizo por índice de repetición, y los 44 perfiles aparecen en las tres.** Verificado: **44 de 44**.

R01–R03 entrenan, R04 valida, R05 prueba. Eso evita la fuga directa de episodios, pero significa que lo que se mide es **repetibilidad de escenarios conocidos**, no generalización. El corpus **no demuestra** desempeño sobre:

- perfiles de tráfico nuevos
- una fecha posterior (no hay jornada de holdout externa)
- otros sistemas operativos
- una red distinta
- servicios ausentes: SSH, SCP/SFTP, SMB, respaldo, streaming, actualizaciones

Es la debilidad más importante del diseño muestral y se declara antes que cualquier resultado.

---

## 7 · Diccionario de variables

El diccionario científico completo —fórmula, tipo, fuente exacta, denominador, comportamiento con denominador cero, rango teórico y observado, observabilidad, coste en línea y estado— está en
[`docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md`](../fase02-features-multicapa/03-diccionario-multicapa-v2.md), **generado desde el extractor congelado**.

| Capa | Variables | Qué observa |
|---|---:|---|
| `L3` | 9 | Volumen, tamaño, diversidad de destinos, TTL, fragmentación |
| `L4` | 8 | Intentos de flujo, tasa y compleción de `SYN`, `RST`, puertos, retransmisión, duración, dirección de bytes |
| `L7` | 11 | Errores y autenticación HTTP, entropía de métodos, DNS y NXDOMAIN, sesiones y versión TLS |
| **Total** | **28** | **27 con variación observable** |

**Convenio de denominador cero:** `safe_ratio(a, b) = a/b si b ≠ 0, en otro caso 0.0`. Un `0.0` **no distingue** «sin actividad» de «proporción real igual a cero»; por eso el corpus conserva contadores de soporte como metadatos.

### Redundancias y ambigüedades declaradas

- `http_status_5xx_ratio_60s` es **subconjunto** de `http_error_ratio_60s`, que ya cuenta ≥ 400.
- `protocol_diversity_30s` se normaliza **por paquetes, no por protocolos**: tiende a 0 al crecer el volumen.
- `http_method_entropy_60s` vale `0.0` tanto sin peticiones como con un único método.
- `tcp_retransmission_ratio_10s` es una **heurística** por número de secuencia repetido.
- Existen **seis pares con correlación absoluta superior a 0,8**. La ablación por capas **ya midió** el aporte de cada grupo: la expansión multicapa es significativa (p < 0,001), pero **las 8 variables L7 nuevas no aportan detección medible** (p = 1,000) y cuestan 5 falsos positivos.

---

## 8 · Calidad y estadísticas

Reproducible con `scripts/dataset/audit_multilayer_v2.py`; el reporte vive en `artifacts/dataset/multilayer-v2-audit-report.json`.

| Gate | Resultado |
|---|---|
| `anomaly_labels_clean` | ✅ |
| `constants_declared` | ✅ |
| `duplicates_within_tolerance` | ✅ |
| `no_duplicate_crossing_label` | ✅ |
| `no_duplicate_crossing_partition` | ✅ |
| `no_episode_split` | ✅ |
| `no_missing_values` | ✅ |
| `normal_labels_clean` | ✅ |
| `partition_values_valid` | ✅ |
| `schema_complete` | ✅ |
| **`pass`** | **✅** |

| Indicador | Valor |
|---|---|
| Valores faltantes | **0** en las 1552 ventanas |
| Variables constantes | 1 — `tls_handshake_failure_ratio_60s` |
| Grupos de vectores duplicados | 14 (36 filas, 22 excedentes = 1.42 %) |
| Duplicados que cruzan etiqueta | 0 |
| Duplicados que cruzan partición | 0 |
| Episodios repartidos | 0 |

Los ratios verificados permanecen dentro de `[0, 1]` y todas las ventanas tienen los 60 s de historia mínima exigidos.

> **Sobre la tolerancia de duplicados.** El presupuesto del 2 % es un valor **declarado, no derivado** de los datos. Los gates con dientes reales son los de tolerancia cero: un duplicado que cruce etiqueta o partición indica fuga y falla siempre.

---

## 9 · Sesgos y limitaciones

Ordenadas por gravedad. Ninguna se descubre leyendo el corpus: todas están medidas.

| # | Limitación | Evidencia |
|---|---|---|
| 1 | **La partición mide repetición, no generalización** | Los 44 perfiles aparecen en las tres particiones; no hay jornada de holdout externa |
| 2 | **Un único laboratorio, una única red, un único sistema operativo cliente** | No hay captura multi-sistema ni multi-red |
| 3 | **Seis escenarios legítimos exigidos no existen** | Faltan SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones |
| 4 | **`tls_handshake_failure_ratio_60s` no es observable** | Constante 0,0; Suricata 8.0.3 no emite el evento intermedio |
| 5 | **Tamaño por debajo de la meta declarada** | 1373 ventanas frente a la meta de 2 000–3 000; ~6 ventanas por episodio, luego **no son independientes entre sí** |
| 6 | **Desbalance de episodios en entrenamiento** | 5 de los 132 episodios de entrenamiento concentran el 31,7 % de sus filas, y los cinco son transferencias lentas de 1 GB — el mismo tráfico pesado donde luego aparece el falso positivo operativo |
| 7 | **Las 18 ventanas heredadas no son ataques genuinos** | Provienen del cliente legítimo reetiquetado; se reportan por separado |
| 8 | **No todas las variables se ganan su lugar** | La ablación lo midió: las 8 variables L7 nuevas no aportan detección medible (p = 1,000). El contrato se conserva congelado; cambiarlo exigiría un protocolo nuevo con evaluación reservada |
| 9 | **Solo IPv4 y protocolos TCP/UDP/ICMP** | IPv6, PCAP-NG y fragmentación avanzada quedan fuera; se rechazan, no se interpretan en silencio |

### Sesgo heredado por quien use este corpus

El corpus se capturó en una red controlada, sin ruido de fondo real, con generadores sintéticos y un solo servidor objetivo. **Un modelo ajustado aquí no debe desplegarse en una red de producción sin recalibrar.** No es una advertencia formal: se midió — el error sobre tráfico legítimo pesado pasó de 4,71 % en evaluación bloqueada a 23–26 % en operación real.

---

## 10 · Privacidad y uso responsable

### Datos personales

**El corpus no contiene datos personales.** Todo el tráfico es sintético, generado por herramientas contra un servidor de laboratorio. No hay usuarios reales, ni navegación real, ni contenido de terceros.

Las direcciones IP son de rangos privados internos del laboratorio (`10.20.0.0/24`, `10.30.0.0/24`) y no identifican a ninguna persona.

### Qué se publica y qué no

| Artefacto | Publicación |
|---|---|
| Ventanas derivadas (CSV) | **Publicable** — solo agregados numéricos por ventana |
| Modelo y manifiesto | **Publicable** |
| PCAP crudo | **No se publica.** El snaplen completo conserva carga útil, nombres, URI y posibles credenciales en claro |
| `eve.json` completo | **No se publica** sin sanear |

La cadena de hashes prueba **integridad**, no anonimización. Son garantías distintas y no deben confundirse.

### Usos previstos y usos prohibidos

**Previsto:** investigación y docencia en detección de anomalías de red, comparación de algoritmos, y reproducción de los resultados de la tesis.

**No previsto:** entrenar un detector para producción sin recalibración; presentar sus métricas como desempeño esperado en una red real; ni extraer conclusiones sobre generalización, que el diseño muestral no sostiene.

**Prohibido:** usar los perfiles ofensivos documentados como guía de ataque contra sistemas de terceros. El tráfico ofensivo se generó exclusivamente dentro del laboratorio, contra máquinas propias y autorizadas.

### Retención

| Artefacto | Retención | Dónde |
|---|---|---|
| Ventanas derivadas, modelo y manifiesto | **Permanente**, versionados en el repositorio | Git |
| PCAP y `eve.json` por campaña | Mientras exista el laboratorio; **fuera de Git** | Disco de evidencias de VM01 |
| Reportes de auditoría superados | **Se archivan, no se borran** | `artifacts/dataset/archive/` |

**Borrado.** La eliminación de un PCAP exige identificador exacto de campaña, verificación previa de `SHA256SUMS` y una copia de respaldo. Nunca un borrado amplio. Es un procedimiento administrativo deliberado: la evidencia bruta es lo único que no se puede reconstruir.

---

## 11 · Reproducción, publicación y mantenimiento

### Lo que ya es reproducible

| | |
|---|---|
| **Contrato de variables** | Versionado; el extractor **aborta** si el orden no coincide |
| **Extractor** | Con pruebas unitarias, incluida la de no usar información futura |
| **Auditoría** | Un comando regenera el reporte completo con sus gates |
| **Integridad** | SHA-256 de los CSV, del calibrador y de los modelos |
| **Entorno** | Versiones de `scikit-learn` y `numpy` registradas en el manifiesto |
| **Trazabilidad** | Cada campaña tiene manifiesto, inventario, contadores y hashes |
| **Diccionario** | Generado desde el extractor; falla si una variable no existe en él |

### Descarga y verificación

**El dataset y el modelo se publican con el repositorio.** Clonar basta:

```bash
git clone https://github.com/marksato13/VF-Sistema-Open-Source-para-la-Deteccion-Temprana-de-Comportamientos-Anomalos-en-Redes-de-Datos.git
cd VF-Sistema-Open-Source-*
sha256sum -c docs/dataset/SHA256SUMS
```

| Artefacto | Tamaño |
|---|---:|
| `artifacts/dataset/multilayer-v2-normal.csv` | 618 KB |
| `artifacts/dataset/multilayer-v2-anomalies.csv` | 84 KB |
| `artifacts/dataset/multilayer-v2-audit-report.json` | 2 KB |
| `artifacts/dataset/partition-map-normal-v2.json` | 1 KB |
| `artifacts/model/manifest.json` | 29 KB |
| `artifacts/model/ocsvm_scaled.joblib` | 7 KB |
| `artifacts/model/candidates/` — **los 7 modelos evaluados** | 4931 KB |
| **Total** | **5674 KB** |

**Los siete candidatos se publican, no solo el ganador.** `candidates/` contiene los objetos ajustados de los siete modelos comparados —los cuatro Isolation Forest, LOF, Elliptic Envelope y el OCSVM— **byte a byte como los produjo la calibración**: sus SHA-256 coinciden con los `model_hashes` del manifiesto. Sin ellos, la comparación de modelos no sería reproducible, solo citable.

> Dos de esos hashes son idénticos: `if_uniform` e `if_exact_collapsed` son **el mismo objeto ajustado**. No es un error de copia; es un hecho del modelado que el manifiesto ya registraba y que conviene saber antes de compararlos.

> **Verifica antes de cargar el modelo.** `ocsvm_scaled.joblib` es un *pickle*: cargarlo **ejecuta código**. Comprueba su SHA-256 contra `docs/dataset/SHA256SUMS` antes de abrirlo, vengas de donde vengas. No es una formalidad.

### Lo que sigue sin publicarse, y por qué

| Artefacto | Motivo |
|---|---|
| PCAP crudo y `eve.json` (24 MB) | Snaplen completo: conserva carga útil, URI y posibles credenciales en claro |
| Dependencias empaquetadas (60 MB) | Reconstruibles desde `pip`; no son evidencia |
| Diagnóstico intermedio del pipeline | Artefacto de trabajo, superado por el reporte de auditoría |

### Mantenimiento

| Regla | |
|---|---|
| **El corpus está congelado** | Ninguna corrección modifica los CSV. Si una mitigación exigiera cambiar los datos, nace una versión formal nueva |
| **Los reportes se regeneran, no se editan** | El reporte de auditoría se regenera con el script; las versiones antiguas se archivan, no se borran |
| **Un punto solo se declara corregido con prueba** | Positiva y negativa, no solo descripción |

El registro de debilidades abiertas, con prioridad e impacto, está en [`docs/entregables/06-plan-de-mejora/`](../entregables/06-plan-de-mejora/README.md).

---

## Trazabilidad

| Tema | Documento |
|---|---|
| Diccionario de las 28 variables | `docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md` |
| Historial campaña por campaña | `docs/fase03-dataset/README.md` |
| Límite de `tls_handshake_failure_ratio_60s` | `docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md` |
| Corrección del catálogo y los gates | `docs/fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md` |
| Modelo congelado y su calibración | `docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md` |
| Validación en operación | `docs/fase07-validacion-final/02-resultados-f6.md` |
| Requisitos del jurado | `docs/requisitos-jurado/README.md` |
| Revisión adversarial de cada campaña | `docs/revisiones-claude/README.md` |
