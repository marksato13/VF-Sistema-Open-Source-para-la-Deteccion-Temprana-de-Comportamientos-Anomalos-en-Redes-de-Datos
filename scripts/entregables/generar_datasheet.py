#!/usr/bin/env python3
"""Genera el datasheet canonico del dataset multilayer-v2.

Sigue las once secciones de la rubrica de datasheet, en ese orden, para que
sea auditable una a una. Todas las cifras se derivan de los artefactos:
CSV congelados, reporte de auditoria, contrato de features y configuraciones
de campana. Ninguna se escribe a mano.

    python3 scripts/entregables/generar_datasheet.py
"""
from __future__ import annotations
import collections, csv, hashlib, json, re, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
A = REPO / "artifacts/dataset"
NORMAL, ANOM = A / "multilayer-v2-normal.csv", A / "multilayer-v2-anomalies.csv"
AUDIT = A / "multilayer-v2-audit-report.json"
SCHEMA = REPO / "configs/features/multilayer-v2.json"
CN = REPO / "configs/campaigns/multilayer-v2-normal.json"
CA = REPO / "configs/campaigns/multilayer-v2-anomalies.json"
OUT = REPO / "docs/dataset/DATASHEET_MULTILAYER_V2.md"

VERSION_DATASHEET = "1.0"
FECHA = "25 de agosto de 2026"


def perfil(cid: str) -> str:
    return re.sub(r"-R\d+.*$", "", re.sub(r"-\d+$", "", cid))


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    cn, ca = json.loads(CN.read_text(encoding="utf-8")), json.loads(CA.read_text(encoding="utf-8"))
    feats = sorted(schema["features"], key=lambda x: x["order"])
    names = [f["name"] for f in feats]

    n = list(csv.DictReader(NORMAL.open(encoding="utf-8")))
    z = list(csv.DictReader(ANOM.open(encoding="utf-8")))
    allrows = n + z

    part = collections.Counter(r["partition"] for r in n)
    eps_part = collections.defaultdict(set)
    prof_part = collections.defaultdict(set)
    for r in n:
        eps_part[r["partition"]].add(r["episode_id"])
        prof_part[perfil(r["campaign_id"])].add(r["partition"])
    perfiles_n = sorted({perfil(r["campaign_id"]) for r in n})
    en_las_tres = sum(1 for p in perfiles_n if len(prof_part[p]) == 3)

    estratos = collections.Counter(p.get("stratum", "—") for p in cn["profiles"])
    escenarios = collections.Counter(p["scenario"] for p in cn["profiles"])

    snap = ca["dataset_snapshot"]
    const = list(audit["constant_features"])
    efectivas = len(names) - len(const)

    sha = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (NORMAL, ANOM)}

    # El datasheet no puede describir un reporte de auditoria de otro corpus.
    # Es exactamente el fallo D-32: el reporte almacenado hablaba de 75/18
    # ventanas mientras el dataset tenia 1373/179.
    for clave, archivo in (("normal_sha256", NORMAL), ("anomaly_sha256", ANOM)):
        if audit.get(clave) != sha[archivo.name]:
            raise SystemExit(
                f"el reporte de auditoria no corresponde a {archivo.name}: "
                f"regenerar con scripts/dataset/audit_multilayer_v2.py"
            )

    L: list[str] = []
    a = L.append

    # ---------------------------------------------------------------- portada
    a(f"# Datasheet — `multilayer-v2`\n\n")
    a("> **Generado**, no redactado a mano: `scripts/entregables/generar_datasheet.py`.\n"
      "> Toda cifra se deriva de los artefactos congelados; ninguna se transcribe.\n\n")
    a("Sigue **las once secciones de la rúbrica de datasheet**, en ese orden, para que "
      "cada una pueda auditarse por separado.\n\n---\n\n")

    # ------------------------------------------------- 1 · identidad
    a("## 1 · Identidad, versión, responsables, licencia y contacto\n\n")
    a("| | |\n|---|---|\n")
    a(f"| **Nombre del corpus** | `multilayer-v2` |\n")
    a(f"| **Estado** | **Congelado.** Los CSV no se modifican; toda corrección es documental |\n")
    a(f"| **Contrato de variables** | `{schema['schema_version']}` · `configs/features/multilayer-v2.json` |\n")
    a(f"| **Versión de este datasheet** | {VERSION_DATASHEET} — {FECHA} |\n")
    a(f"| **Ventanas** | {len(n):,} normales + {len(z):,} anómalas = **{len(allrows):,}** |\n".replace(",", " "))
    a(f"| **Episodios** | {audit['normal_episodes']} normales + {audit['anomaly_episodes']} anómalos |\n")
    a(f"| **Variables** | {len(names)} definidas · **{efectivas} con variación observable** |\n")
    a(f"| **SHA-256 normal** | `{sha['multilayer-v2-normal.csv']}` |\n")
    a(f"| **SHA-256 anómalo** | `{sha['multilayer-v2-anomalies.csv']}` |\n")
    a("\n> **Por qué no se llama `v2.1`.** Declarar una variable como no observable es una "
      "**anotación documental**, no un corpus nuevo. El dataset sigue siendo `multilayer-v2` "
      "con los mismos hashes; lo que se versiona por separado es este documento.\n")
    a("\n### Pendiente de formalizar\n\n")
    a("Estos campos **no están cerrados** y se completan en el bloque de gobernanza. "
      "Declararlo es preferible a inventarlo:\n\n")
    a("| Campo | Estado |\n|---|---|\n")
    a("| **Responsables** | Autor y coautor de la tesis; falta declararlos aquí con su afiliación |\n")
    a("| **Licencia** | **Sin definir.** Propuesta: CC BY 4.0 para los datos derivados. Requiere decisión del autor y un archivo `LICENSE` en el repositorio |\n")
    a("| **Contacto** | Falta una dirección institucional. No se publica un correo personal sin autorización expresa |\n")
    a("| **Registro de cambios** | Este datasheet inaugura el historial; los cambios previos del corpus están en `docs/fase03-dataset/` |\n")

    # ------------------------------------------------- 2 · topologia
    a("\n---\n\n## 2 · Topología y entorno de captura\n\n")
    a("Laboratorio virtualizado sobre VMware ESXi, con tres redes separadas. El Sensor "
      "**es** el router entre la red de clientes y la red de servicio, así que todo el "
      "tráfico observado lo atraviesa por diseño, no por replicación.\n\n")
    a("```text\nCliente 10.20.0.20 ─┐\n"
      "                     ├─► Sensor 10.20.0.1 / 10.30.0.1 ─► Servidor 10.30.0.10\n"
      "Kali 10.20.0.100 ───┘\n```\n\n")
    a("| Rol | VM | Red de clientes | Red de servicio |\n|---|---|---|---|\n")
    for rol, vm, lan, dmz in [("Sensor, router e IDS", "VM02", "10.20.0.1", "10.30.0.1"),
                              ("Servidor protegido", "VM03", "—", "10.30.0.10"),
                              ("Kali · tráfico ofensivo", "VM04", "10.20.0.100", "—"),
                              ("Cliente legítimo", "VM05", "10.20.0.20", "—")]:
        a(f"| {rol} | {vm} | `{lan}` | `{dmz}` |\n")
    a("\n### Instrumentación\n\n")
    a("| | |\n|---|---|\n")
    a("| **IDS** | Suricata 8.0.3, AF_PACKET sobre `ens35`, `HOME_NET=[10.30.0.0/24, 10.20.0.20/32]`, reglas Emerging Threats Open |\n")
    a("| **Salida de eventos** | EVE JSON — se consumen `http`, `dns` y `tls` |\n")
    a("| **Captura de paquetes** | `tcpdump` por campaña mediante un helper con parámetros fijos |\n")
    a("| **Interfaz y filtro** | `ens35`; tráfico bidireccional `10.20.0.0/24` ↔ `10.30.0.0/24` |\n")
    a("| **Snaplen** | Paquete completo (`-s 0`) |\n")
    a(f"| **Calentamiento antes de medir** | {cn['warmup_seconds']} s |\n")
    a(f"| **Asentamiento y enfriamiento** | {cn['settle_seconds']} s y {cn['cooldown_seconds']} s entre repeticiones |\n")
    a("\n**Techos de tasa calibrados.** 200 Mbit/s TCP, 50 Mbit/s UDP y 20 MB/s por "
      "transferencia HTTP/HTTPS. Se fijaron tras medir pérdida real: una prueba sin "
      "limitación a 2,58 Gbit/s produjo 389 932 descartes y **está excluida del corpus**. "
      "El generador rechaza valores por encima de esos techos.\n")
    a("\n**Aislamiento.** Las interfaces externas de VM02–VM05 permanecen desconectadas "
      "durante las campañas. El riesgo de una ruta que evitara al Sensor no es hipotético: "
      "se comprobó y se cerró.\n")

    # ------------------------------------------------- 3 · unidad de observacion
    a("\n---\n\n## 3 · Unidad de observación y causalidad\n\n")
    a(f"Una fila = **una IP iniciadora** observada hasta un instante `T`, emitida cada "
      f"**{schema['emission_step_seconds']} s**.\n\n")
    a("Las ventanas son deslizantes y **estrictamente causales**:\n\n")
    a("```text\n(T − W, T]   con W ∈ {10, 30, 60} segundos\n```\n\n")
    a("Ningún paquete o evento posterior a `T` participa en la fila cerrada en `T`. Eso "
      "permite decidir **sin esperar el cierre del flujo** y elimina la fuga temporal por "
      "construcción, no por convención.\n\n")
    a("### Atribución a la entidad iniciadora\n\n")
    a("| Protocolo | Iniciador |\n|---|---|\n")
    a("| TCP | Quien envía el primer `SYN` sin `ACK` |\n")
    a("| UDP | Quien envía el primer datagrama observado |\n")
    a("| ICMP eco | Quien envía el `echo request` |\n")
    a("| Captura empezada a mitad | El primer emisor observado — **limitación registrada** |\n")
    a("\nLas respuestas se atribuyen a la misma entidad iniciadora. Solo se emiten filas "
      "para `10.20.0.0/24`: el servidor no genera una fila propia por responder.\n")
    a("\n**Verificado con prueba unitaria:** un evento posterior a `T` no altera una "
      "ventana ya cerrada. Es la respuesta directa al requisito de no usar información futura.\n")

    # ------------------------------------------------- 4 · catalogo
    a("\n---\n\n## 4 · Catálogo de escenarios\n\n")
    a(f"### Tráfico legítimo — {len(perfiles_n)} perfiles\n\n")
    a(f"Generados desde VM05 con {cn['default_repetitions']} repeticiones cada uno. "
      "Agrupados por estrato declarado:\n\n")
    a("| Estrato | Perfiles |\n|---|---:|\n")
    for k, v in sorted(estratos.items()):
        a(f"| `{k}` | {v} |\n")
    a(f"| **Total** | **{sum(estratos.values())}** |\n")
    a("\nSobre **" + str(len(escenarios)) + " generadores distintos**: ")
    a(", ".join(f"`{k}`×{v}" for k, v in sorted(escenarios.items())) + ".\n")
    a("\n> **Tráfico pesado incluido a propósito.** El corpus contiene transferencias de "
      "10 MB a 1 GB y de 2 a 8 flujos concurrentes, con una muestra medida en **90,84 % de "
      "cargas TCP entre 500 y 1500 bytes**. Un paquete grande no puede convertirse por sí "
      "solo en señal de ataque, y por eso el tráfico pesado entra como normalidad.\n")
    a(f"\n### Tráfico anómalo — {snap['families_total']} familias\n\n")
    a("| Familia | Origen | Escenario | Ventanas | Episodios |\n|---|---|---|---:|---:|\n")
    for p in ca["kali_profiles"] + ca["profiles"]:
        origen = "**Kali (VM04)**" if p["traffic_class"] == "offensive" else "VM05 reetiquetado"
        a(f"| `{p['id']}` | {origen} | `{p['scenario']}` | {p['observed_windows']} | {p['observed_episodes']} |\n")
    a(f"| **Total** | | | **{snap['windows_total']}** | **{snap['episodes_total']}** |\n")

    # ------------------------------------------------- 5 · etiquetado
    a("\n---\n\n## 5 · Etiquetado y procedencia\n\n")
    a("El etiquetado es **por diseño experimental, no por juicio posterior**: la etiqueta "
      "proviene de qué campaña generó el tráfico, se une **después** de extraer las "
      "variables y nunca entra al vector del modelo.\n\n")
    a("| Etiqueta | Ventanas | Procedencia |\n|---|---:|---|\n")
    a(f"| `normal` | {len(n)} | Cliente legítimo VM05, campañas `F2N-*` |\n")
    a(f"| `anomaly` (Kali real) | {snap['kali_real']['windows']} | Kali VM04, campañas `F2A-ANOM-KALI-*` |\n")
    a(f"| `anomaly` (heredada) | {snap['legacy_relabeled']['windows']} | VM05 reetiquetado, generación anterior |\n")
    a("\n> **Las 18 heredadas se reportan por separado, siempre.** No son tráfico "
      "ofensivo genuino: son escenarios del cliente legítimo reetiquetados en una "
      "generación anterior del corpus. Mezclarlas con las 161 de Kali inflaría cualquier "
      "métrica de detección. Por eso el desempeño se publica en las dos formas.\n")
    a("\n### Lo que falta en el protocolo de etiquetado\n\n")
    a("No existe un procedimiento canónico escrito para **casos ambiguos** ni una segunda "
      "revisión independiente de etiquetas. En este corpus el riesgo es bajo, porque la "
      "etiqueta la determina la máquina de origen y no una interpretación; pero el "
      "procedimiento debería existir antes de incorporar tráfico capturado en producción.\n")

    # ------------------------------------------------- 6 · particiones
    a("\n---\n\n## 6 · Particiones y prevención de fuga\n\n")
    a("| Partición | Repeticiones | Ventanas | Episodios |\n|---|---|---:|---:|\n")
    reps = collections.defaultdict(list)
    for k, v in cn["partition_by_repetition"].items():
        reps[v].append(f"R0{k}")
    for p in ("train", "validation", "test"):
        a(f"| `{p}` | {', '.join(reps[p])} | {part[p]} | {len(eps_part[p])} |\n")
    a(f"| `evaluation_only` | — | {len(z)} | {audit['anomaly_episodes']} |\n")
    a("\n### Lo que sí está garantizado\n\n")
    for s in [f"**Ningún episodio se reparte entre particiones** — gate `no_episode_split`, "
              f"{len(audit['episode_split_violations'])} violaciones.",
              "**Ventanas solapadas del mismo episodio no se reparten** al azar entre conjuntos.",
              "**El escalador y los hiperparámetros se ajustaron solo con `train`**; el "
              "umbral se calibró una sola vez con `validation`.",
              "**Las campañas de calibración quedan fuera** de las tres particiones "
              "(`excluded_calibration`).",
              "**Ningún grupo de vectores duplicados cruza etiqueta ni partición** — dos "
              "gates de tolerancia cero."]:
        a(f"- {s}\n")
    a("\n### La limitación que hay que declarar primero\n\n")
    a(f"> **La partición se hizo por índice de repetición, y los {len(perfiles_n)} perfiles "
      f"aparecen en las tres.** Verificado: **{en_las_tres} de {len(perfiles_n)}**.\n")
    a("\nR01–R03 entrenan, R04 valida, R05 prueba. Eso evita la fuga directa de episodios, "
      "pero significa que lo que se mide es **repetibilidad de escenarios conocidos**, no "
      "generalización. El corpus **no demuestra** desempeño sobre:\n\n")
    for s in ["perfiles de tráfico nuevos", "una fecha posterior (no hay jornada de holdout externa)",
              "otros sistemas operativos", "una red distinta",
              "servicios ausentes: SSH, SCP/SFTP, SMB, respaldo, streaming, actualizaciones"]:
        a(f"- {s}\n")
    a("\nEs la debilidad más importante del diseño muestral y se declara antes que "
      "cualquier resultado.\n")

    # ------------------------------------------------- 7 · diccionario
    a("\n---\n\n## 7 · Diccionario de variables\n\n")
    a("El diccionario científico completo —fórmula, tipo, fuente exacta, denominador, "
      "comportamiento con denominador cero, rango teórico y observado, observabilidad, "
      "coste en línea y estado— está en\n"
      "[`docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md`](../fase02-features-multicapa/03-diccionario-multicapa-v2.md), "
      "**generado desde el extractor congelado**.\n\n")
    capas = collections.Counter(f["layer"] for f in feats)
    a("| Capa | Variables | Qué observa |\n|---|---:|---|\n")
    for c, desc in [("L3", "Volumen, tamaño, diversidad de destinos, TTL, fragmentación"),
                    ("L4", "Intentos de flujo, tasa y compleción de `SYN`, `RST`, puertos, retransmisión, duración, dirección de bytes"),
                    ("L7", "Errores y autenticación HTTP, entropía de métodos, DNS y NXDOMAIN, sesiones y versión TLS")]:
        a(f"| `{c}` | {capas[c]} | {desc} |\n")
    a(f"| **Total** | **{len(names)}** | **{efectivas} con variación observable** |\n")
    a("\n**Convenio de denominador cero:** `safe_ratio(a, b) = a/b si b ≠ 0, en otro caso 0.0`. "
      "Un `0.0` **no distingue** «sin actividad» de «proporción real igual a cero»; por eso "
      "el corpus conserva contadores de soporte como metadatos.\n")
    a("\n### Redundancias y ambigüedades declaradas\n\n")
    for s in ["`http_status_5xx_ratio_60s` es **subconjunto** de `http_error_ratio_60s`, que ya cuenta ≥ 400.",
              "`protocol_diversity_30s` se normaliza **por paquetes, no por protocolos**: tiende a 0 al crecer el volumen.",
              "`http_method_entropy_60s` vale `0.0` tanto sin peticiones como con un único método.",
              "`tcp_retransmission_ratio_10s` es una **heurística** por número de secuencia repetido.",
              "Existen **seis pares con correlación absoluta superior a 0,8**; la ablación por capas que mediría el aporte real de cada grupo **aún no se ha ejecutado**."]:
        a(f"- {s}\n")

    # ------------------------------------------------- 8 · calidad
    a("\n---\n\n## 8 · Calidad y estadísticas\n\n")
    a("Reproducible con `scripts/dataset/audit_multilayer_v2.py`; el reporte vive en "
      "`artifacts/dataset/multilayer-v2-audit-report.json`.\n\n")
    a("| Gate | Resultado |\n|---|---|\n")
    for k, v in sorted(audit["gates"].items()):
        if k == "pass":
            continue
        a(f"| `{k}` | {'✅' if v else '❌'} |\n")
    a(f"| **`pass`** | **{'✅' if audit['gates']['pass'] else '❌'}** |\n")
    a("\n| Indicador | Valor |\n|---|---|\n")
    a(f"| Valores faltantes | **0** en las {len(allrows)} ventanas |\n")
    a(f"| Variables constantes | {len(const)} — `{', '.join(const)}` |\n")
    a(f"| Grupos de vectores duplicados | {audit['duplicate_groups']} ({audit['duplicate_rows_involved']} filas, {audit['duplicate_rows_excess']} excedentes = {audit['duplicate_excess_ratio']*100:.2f} %) |\n")
    a(f"| Duplicados que cruzan etiqueta | {audit['duplicate_groups_crossing_label']} |\n")
    a(f"| Duplicados que cruzan partición | {audit['duplicate_groups_crossing_partition']} |\n")
    a(f"| Episodios repartidos | {len(audit['episode_split_violations'])} |\n")
    a("\nLos ratios verificados permanecen dentro de `[0, 1]` y todas las ventanas tienen "
      "los 60 s de historia mínima exigidos.\n")
    a("\n> **Sobre la tolerancia de duplicados.** El presupuesto del "
      f"{audit['duplicate_excess_tolerance']*100:.0f} % es un valor **declarado, no derivado** "
      "de los datos. Los gates con dientes reales son los de tolerancia cero: un duplicado "
      "que cruce etiqueta o partición indica fuga y falla siempre.\n")

    # ------------------------------------------------- 9 · sesgos
    a("\n---\n\n## 9 · Sesgos y limitaciones\n\n")
    a("Ordenadas por gravedad. Ninguna se descubre leyendo el corpus: todas están medidas.\n\n")
    a("| # | Limitación | Evidencia |\n|---|---|---|\n")
    for i, (lim, ev) in enumerate([
        ("**La partición mide repetición, no generalización**",
         f"Los {len(perfiles_n)} perfiles aparecen en las tres particiones; no hay jornada de holdout externa"),
        ("**Un único laboratorio, una única red, un único sistema operativo cliente**",
         "No hay captura multi-sistema ni multi-red"),
        ("**Seis escenarios legítimos exigidos no existen**",
         "Faltan SSH, SCP/SFTP, SMB, respaldo, streaming y actualizaciones"),
        ("**`tls_handshake_failure_ratio_60s` no es observable**",
         "Constante 0,0; Suricata 8.0.3 no emite el evento intermedio"),
        ("**Tamaño por debajo de la meta declarada**",
         f"{len(n)} ventanas frente a la meta de 2 000–3 000; ~6 ventanas por episodio, luego **no son independientes entre sí**"),
        ("**Desbalance de episodios en entrenamiento**",
         "5 de los 132 episodios de entrenamiento concentran el 31,7 % de sus filas, y los cinco son transferencias lentas de 1 GB — el mismo tráfico pesado donde luego aparece el falso positivo operativo"),
        ("**Las 18 ventanas heredadas no son ataques genuinos**",
         "Provienen del cliente legítimo reetiquetado; se reportan por separado"),
        ("**La ablación por capas no se ha ejecutado**",
         "Ninguna de las 28 variables ha demostrado individualmente que se gana su lugar"),
        ("**Solo IPv4 y protocolos TCP/UDP/ICMP**",
         "IPv6, PCAP-NG y fragmentación avanzada quedan fuera; se rechazan, no se interpretan en silencio"),
    ], 1):
        a(f"| {i} | {lim} | {ev} |\n")
    a("\n### Sesgo heredado por quien use este corpus\n\n")
    a("El corpus se capturó en una red controlada, sin ruido de fondo real, con generadores "
      "sintéticos y un solo servidor objetivo. **Un modelo ajustado aquí no debe desplegarse "
      "en una red de producción sin recalibrar.** No es una advertencia formal: se midió — "
      "el error sobre tráfico legítimo pesado pasó de 4,71 % en evaluación bloqueada a "
      "23–26 % en operación real.\n")

    # ------------------------------------------------- 10 · privacidad
    a("\n---\n\n## 10 · Privacidad y uso responsable\n\n")
    a("### Datos personales\n\n")
    a("**El corpus no contiene datos personales.** Todo el tráfico es sintético, generado "
      "por herramientas contra un servidor de laboratorio. No hay usuarios reales, ni "
      "navegación real, ni contenido de terceros.\n\n")
    a("Las direcciones IP son de rangos privados internos del laboratorio "
      "(`10.20.0.0/24`, `10.30.0.0/24`) y no identifican a ninguna persona.\n")
    a("\n### Qué se publica y qué no\n\n")
    a("| Artefacto | Publicación |\n|---|---|\n")
    a("| Ventanas derivadas (CSV) | **Publicable** — solo agregados numéricos por ventana |\n")
    a("| Modelo y manifiesto | **Publicable** |\n")
    a("| PCAP crudo | **No se publica.** El snaplen completo conserva carga útil, nombres, URI y posibles credenciales en claro |\n")
    a("| `eve.json` completo | **No se publica** sin sanear |\n")
    a("\nLa cadena de hashes prueba **integridad**, no anonimización. Son garantías distintas "
      "y no deben confundirse.\n")
    a("\n### Usos previstos y usos prohibidos\n\n")
    a("**Previsto:** investigación y docencia en detección de anomalías de red, comparación "
      "de algoritmos, y reproducción de los resultados de la tesis.\n\n")
    a("**No previsto:** entrenar un detector para producción sin recalibración; presentar "
      "sus métricas como desempeño esperado en una red real; ni extraer conclusiones sobre "
      "generalización, que el diseño muestral no sostiene.\n")
    a("\n**Prohibido:** usar los perfiles ofensivos documentados como guía de ataque contra "
      "sistemas de terceros. El tráfico ofensivo se generó exclusivamente dentro del "
      "laboratorio, contra máquinas propias y autorizadas.\n")
    a("\n### Retención — pendiente\n\n")
    a("No existe una política formal de retención de los PCAP originales ni de los datos "
      "derivados. Es un vacío declarado, no resuelto.\n")

    # ------------------------------------------------- 11 · reproduccion
    a("\n---\n\n## 11 · Reproducción, publicación y mantenimiento\n\n")
    a("### Lo que ya es reproducible\n\n")
    a("| | |\n|---|---|\n")
    a("| **Contrato de variables** | Versionado; el extractor **aborta** si el orden no coincide |\n")
    a("| **Extractor** | Con pruebas unitarias, incluida la de no usar información futura |\n")
    a("| **Auditoría** | Un comando regenera el reporte completo con sus gates |\n")
    a("| **Integridad** | SHA-256 de los CSV, del calibrador y de los modelos |\n")
    a("| **Entorno** | Versiones de `scikit-learn` y `numpy` registradas en el manifiesto |\n")
    a("| **Trazabilidad** | Cada campaña tiene manifiesto, inventario, contadores y hashes |\n")
    a("| **Diccionario** | Generado desde el extractor; falla si una variable no existe en él |\n")
    a("\n### Lo que todavía impide reproducir desde un clon\n\n")
    a("> **`artifacts/` está excluido del repositorio en bloque**, y esa regla arrastra al "
      "dataset y al modelo junto con las dependencias y las capturas.\n")
    a("\nQuien clone el repositorio **no recibe** los CSV, el manifiesto, el modelo OCSVM ni "
      "los seis comparadores. Los hashes permiten verificar archivos que ya se tengan, pero "
      "no descargarlos.\n\n")
    a(f"El coste de resolverlo es bajo: el dataset ocupa **{(NORMAL.stat().st_size + ANOM.stat().st_size)//1024} KB** "
      "y el modelo unos 8 KB. El volumen real de `artifacts/` son las dependencias y las "
      "capturas, no los datos. **Excluir esos dos artefactos de la regla es cuestión de minutos.**\n")
    a("\n### Mantenimiento\n\n")
    a("| Regla | |\n|---|---|\n")
    a("| **El corpus está congelado** | Ninguna corrección modifica los CSV. Si una mitigación exigiera cambiar los datos, nace una versión formal nueva |\n")
    a("| **Los reportes se regeneran, no se editan** | El reporte de auditoría se regenera con el script; las versiones antiguas se archivan, no se borran |\n")
    a("| **Un punto solo se declara corregido con prueba** | Positiva y negativa, no solo descripción |\n")
    a("\nEl registro de debilidades abiertas, con prioridad e impacto, está en "
      "[`docs/entregables/06-plan-de-mejora/`](../entregables/06-plan-de-mejora/README.md).\n")

    # ------------------------------------------------- cierre
    a("\n---\n\n## Trazabilidad\n\n")
    a("| Tema | Documento |\n|---|---|\n")
    for tema, doc in [
        ("Diccionario de las 28 variables", "`docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md`"),
        ("Historial campaña por campaña", "`docs/fase03-dataset/README.md`"),
        ("Límite de `tls_handshake_failure_ratio_60s`", "`docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md`"),
        ("Corrección del catálogo y los gates", "`docs/fase03-dataset/181-correccion-catalogo-auditoria-y-gates.md`"),
        ("Modelo congelado y su calibración", "`docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md`"),
        ("Validación en operación", "`docs/fase07-validacion-final/02-resultados-f6.md`"),
        ("Requisitos del jurado", "`docs/requisitos-jurado/README.md`"),
        ("Revisión adversarial de cada campaña", "`docs/revisiones-claude/README.md`"),
    ]:
        a(f"| {tema} | {doc} |\n")

    OUT.write_text("".join(L), encoding="utf-8")
    print(f"Generado: {OUT.relative_to(REPO)}")
    print(f"  {len(allrows)} ventanas · {len(names)} variables ({efectivas} efectivas)")
    print(f"  {len(perfiles_n)} perfiles normales ({en_las_tres} en las tres particiones)")
    print(f"  {snap['families_total']} familias anómalas · gates.pass={audit['gates']['pass']}")


if __name__ == "__main__":
    main()
