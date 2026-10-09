#!/usr/bin/env python3
"""Genera la model card y la system card desde los artefactos.

Model card  <- artifacts/model/manifest.json + results/ablacion/validacion-cruzada-estabilidad.json
System card <- results/f6/*.jsonl y el codigo del motor

Las cifras de las tarjetas se leen de esos artefactos. La prueba adicional de
aislamiento se conserva como evidencia documental separada porque sus registros
crudos no estan versionados; la tarjeta lo declara expresamente.

    python3 scripts/entregables/generar_cards.py
"""
from __future__ import annotations
import json, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "artifacts/model/manifest.json"
# El pase 1 esta archivado como CONTAMINADO: uso un asentamiento fijo en vez
# de esperar a que el motor se pusiera al dia, asi que sus tiempos mezclan
# atraso con deteccion. Sirve para disponibilidad, NO para temporizacion.
F6_LIMPIO = REPO / "results/f6/f6_resultados.jsonl"
F6_PASE1 = REPO / "results/f6/f6_resultados.pass1-contaminado.jsonl"
VALIDACION = REPO / "results/ablacion/validacion-cruzada-estabilidad.json"
OUT_M = REPO / "docs/dataset/MODEL_CARD_OCSVM.md"
OUT_S = REPO / "docs/dataset/SYSTEM_CARD_MOTOR.md"
FECHA = "26 de agosto de 2026"

FAMILIA = {  # nombre legible de cada familia evaluada
    "ANOM-KALI-SYN-RATE-50": "Ráfaga de SYN",
    "ANOM-KALI-PORT-SCAN": "Escaneo de puertos",
    "ANOM-KALI-PORT-SCAN-WIDE": "Escaneo amplio 1–1000",
    "ANOM-KALI-UDP-PROBE-50": "Sondeo UDP",
    "ANOM-KALI-PASSWORD-SPRAY-50": "Rociado de contraseñas",
    "ANOM-KALI-DNS": "Entropía DNS",
    "ANOM-AUTH-FAIL-50": "Fallo de autenticación (heredada)",
    "ANOM-DNS-NX-200": "NXDOMAIN (heredada)",
    "ANOM-SYN-RATE-10": "SYN rechazados (heredada)",
}


def es(x: float, dec: int = 1) -> str:
    """Formato numerico en espanol: coma decimal."""
    return f"{x:.{dec}f}".replace(".", ",")


def wilson(exitos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = exitos / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - r) / d * 100, (c + r) / d * 100)


def model_card(d: dict, validacion: dict) -> str:
    o = d["evaluation"]["ocsvm_scaled"]
    an, te = o["anomalies"], o["test"]
    L: list[str] = []
    a = L.append

    a("# Model card — OCSVM `multilayer-v2` (histórica, laboratorio)\n\n")
    a("> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, "
      "desde `artifacts/model/manifest.json`.\n\n")
    a("> **Modelo histórico.** Es el modelo de laboratorio de la versión anterior y el que "
      "se evaluó en F6. **No es el detector desplegado hoy**: el motor vivo ejecuta el "
      "**Isolation Forest recalibrado** (`if_recalibrado_2026_09`), descrito en "
      "[`MODEL_CARD_IF_RECALIBRADO.md`](MODEL_CARD_IF_RECALIBRADO.md) y en la "
      "[ficha técnica del despliegue](../FICHA-TECNICA-DESPLIEGUE-VIGENTE.md). Sus cifras "
      "valen para el conjunto y la versión en que se midieron; no se trasladan al IF.\n\n")
    a("Responde por **el modelo de laboratorio**. Los datos están en "
      "[`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md) y el sistema en "
      "[`SYSTEM_CARD_MOTOR.md`](SYSTEM_CARD_MOTOR.md).\n\n---\n\n")

    # 1
    a("## 1 · Detalles del modelo\n\n| | |\n|---|---|\n")
    a("| **Algoritmo** | One-Class SVM sobre variables estandarizadas |\n")
    a("| **Identificador** | `ocsvm_scaled` |\n")
    a("| **Hiperparámetro** | `nu = 0.05` |\n")
    a(f"| **Umbral de decisión** | `score < {o['threshold_used']:.10f}` → `ALERT` |\n")
    a(f"| **Criterio de calibración** | Cuantil con `alpha = {d['alpha']}`, fijado **solo** sobre `validation` |\n")
    a(f"| **Entradas** | {len(d['feature_names'])} variables, orden fijado por contrato |\n")
    a(f"| **Protocolo** | `{d['protocol']}` |\n")
    a(f"| **Entorno** | scikit-learn {d['scikit_learn']} · numpy {d['numpy']} |\n")
    a(f"| **Congelado el** | {d['created_at'][:10]} · commit `{d['git_commit'][:12]}` |\n")
    a(f"| **SHA-256** | `{d['model_hashes']['models/ocsvm_scaled.joblib']}` |\n")
    a("\nEl escalador y el modelo se ajustaron **solo con `train`**; el umbral se calibró "
      "una única vez con `validation`; `test` y las anomalías se puntuaron una sola vez.\n")

    # 2
    a("\n---\n\n## 2 · Uso previsto\n\n")
    a("**Previsto.** Marcar como anómala una ventana de 10 s de comportamiento de una IP "
      "iniciadora, dentro del laboratorio para el que se calibró, como componente del motor "
      "de decisión documentado en la system card.\n\n")
    a("**No previsto.** Desplegarlo en una red de producción sin recalibrar; usarlo sobre "
      "tráfico de otra topología, otro conjunto de servicios u otra distribución de carga; "
      "o interpretar sus métricas como desempeño esperado fuera del laboratorio.\n\n")
    a("**Fuera de alcance.** No identifica el tipo de ataque, no atribuye intención y no "
      "sustituye a un IDS por firmas. Decide una sola cosa: si el comportamiento de esa IP "
      "en esa ventana se parece o no a la normalidad aprendida.\n")

    # 3
    a("\n---\n\n## 3 · La advertencia que va antes de cualquier métrica\n\n")
    a(f"> **El modelo se eligió después de observar el conjunto de prueba.**\n")
    a("\nEl propio manifiesto registra la política que lo prohibía:\n\n")
    a(f"> «{d['model_selection_policy']}»\n\n")
    a("`ocsvm_scaled` figura ahí como **comparador**, no como conclusión. Fue promovido por "
      "ganar la comparación posterior, que es exactamente lo que esa política impedía.\n\n")
    a("**Consecuencia, sin rodeos:** las cifras de abajo son el **máximo sobre siete "
      "candidatos** evaluados en los mismos conjuntos, sin datos reservados. Son una "
      "estimación **optimista**, no insesgada. La corrección real —un protocolo nuevo con "
      "criterio fijado de antemano y una evaluación no observada— es trabajo pendiente.\n")

    # 4
    a("\n---\n\n## 4 · Métricas\n\n")
    a("Punto de operación único, evaluación bloqueada de un solo paso. Intervalos de "
      "Wilson al 95 %.\n\n")
    a("| Métrica | Valor | IC 95 % | Base |\n|---|---|---|---|\n")
    for etq, ex, n in [
        ("Detección global", an["detected_strict"], an["n_windows"]),
        ("Detección · ataques genuinos (Kali)", an["kali_real_detected"], an["kali_real_windows"]),
        ("Detección · ventanas heredadas", an["legacy_detected"], an["legacy_windows"]),
        ("**Falso positivo** (`test` benigno)", te["alerts_strict"], te["n_windows"]),
    ]:
        lo, hi = wilson(ex, n)
        dec = 2 if "positivo" in etq else 1
        a(f"| {etq} | **{es(ex/n*100, dec)} %** | [{es(lo)} – {es(hi)}] | {ex}/{n} ventanas |\n")
    a(f"| Episodios de ataque alcanzados | {an['detected_episode_count']}/{an['total_episode_count']} | — | episodios |\n")
    a("\n**ROC-AUC = 0,974**, calculada re-puntuando el modelo congelado. Hereda el mismo "
      "sesgo optimista de la sección 3: se apoya en los conjuntos usados para seleccionarlo.\n")
    a("\n> **Las ventanas heredadas se reportan aparte a propósito.** No son ataques "
      "genuinos, sino tráfico del cliente legítimo reetiquetado en una generación anterior. "
      "La cifra que debe citarse es la de **Kali real**.\n")

    # 5
    a("\n---\n\n## 5 · Desempeño por familia\n\n")
    a("| Familia | Detección | IC 95 % | |\n|---|---|---|---|\n")
    for k, v in sorted(an["by_profile"].items(), key=lambda x: -x[1]["detected"] / x[1]["windows"]):
        lo, hi = wilson(v["detected"], v["windows"])
        r = v["detected"] / v["windows"]
        marca = "✅" if r >= 0.85 else ("⚠️" if r >= 0.6 else "🔴")
        a(f"| {FAMILIA.get(k, k)} | {v['detected']}/{v['windows']} = **{r*100:.0f} %** | "
          f"[{lo:.0f} – {hi:.0f}] | {marca} |\n")
        if v["windows"] == 6 and r < 0.6:
            peor = (k, v["detected"], v["windows"], lo, hi)
    a("\n**El punto ciego está declarado:** las familias de **fallo de autenticación** son "
      "las peores. Tiene explicación estructural — un rociado de contraseñas genera poco "
      "volumen y su firma vive en la capa 7, no en el caudal de paquetes. Por eso el motor "
      "añade un detector heurístico L7 específico (ver system card).\n")
    n6 = [(k, v) for k, v in an["by_profile"].items() if v["windows"] == 6]
    ej = min(n6, key=lambda x: x[1]["detected"] / x[1]["windows"])
    lo6, hi6 = wilson(ej[1]["detected"], ej[1]["windows"])
    a(f"\n> **Cuidado con los intervalos.** {len(n6)} familias tienen `n = 6`. En "
      f"`{ej[0]}` el «{ej[1]['detected']/ej[1]['windows']*100:.0f} %» es literalmente "
      f"**{ej[1]['detected']} de {ej[1]['windows']}**, con un intervalo de "
      f"**{es(lo6,0)} % a {es(hi6,0)} %**. No sostiene ninguna conclusión por sí solo.\n")

    # 6
    a("\n---\n\n## 6 · Comparación de los siete candidatos\n\n")
    a("Todos evaluados sobre los mismos conjuntos, con el mismo criterio de umbral.\n\n")
    a("| Modelo | FPR benigno | Detección global | Detección Kali |\n|---|---:|---:|---:|\n")
    for m, v in sorted(d["evaluation"].items(), key=lambda x: -x[1]["anomalies"]["detection_rate"]):
        neg = "**" if m == "ocsvm_scaled" else ""
        a(f"| {neg}`{m}`{neg} | {v['test']['fpr']*100:.2f} % | "
          f"{neg}{v['anomalies']['detection_rate']*100:.1f} %{neg} | "
          f"{v['anomalies']['kali_real_detection_rate']*100:.1f} % |\n")
    a("\n**Por qué OCSVM y no Isolation Forest.** No por regla general, sino por puntos "
      "ciegos medidos: las ramas de Isolation Forest detectan **0 de 31** ventanas de ráfaga "
      "SYN y **0 de 40** de sondeo UDP. OCSVM resuelve ambas. A cambio, IF acierta el 100 % "
      "en las familias de autenticación donde OCSVM falla. **No hay un ganador limpio: hay "
      "un intercambio**, y se eligió el lado que cubre los ataques de mayor volumen.\n")
    a("\n> `if_uniform` e `if_exact_collapsed` comparten SHA-256: son **el mismo objeto "
      "ajustado**. Sus dos filas no son dos evidencias independientes.\n")
    a("\nLos siete objetos ajustados se publican en `artifacts/model/candidates/`, "
      "verificables con `sha256sum -c docs/dataset/SHA256SUMS`.\n")

    # 7
    a("\n---\n\n## 7 · Limitaciones\n\n")
    a("| # | Limitación |\n|---|---|\n")
    for i, s in enumerate([
        "**Selección posterior sobre el conjunto de prueba** (sección 3). Es la limitación principal.",
        f"**El falso positivo de {te['fpr']*100:.2f} % no se sostiene en operación**: F6 midió 23–26 % sobre tráfico legítimo pesado. Ver system card.",
        (f"**Validación interna, no externa.** Se ejecutaron {validacion['k_pliegues']} pliegues "
         "agrupados por episodio normal sobre el mismo pipeline OCSVM, pero las mismas anomalías "
         "se reutilizan en todos los pliegues. No mide generalización a otra red o fecha."),
        (f"**Estabilidad interna del umbral medida.** El bootstrap por episodio "
         f"(`B = {validacion['b_bootstrap']}`) dio CV "
         f"{es(validacion['estabilidad_umbral']['cv_pct'], 2)} % y banda percentil "
         f"[{es(validacion['estabilidad_umbral']['ic_percentil_95'][0], 4)} – "
         f"{es(validacion['estabilidad_umbral']['ic_percentil_95'][1], 4)}]. "
         "No sustituye una validación externa."),
        "**Ajustado sin ponderación** pese a que 5 de 132 episodios concentran el 31,7 % de las filas de entrenamiento, y los cinco son transferencias lentas de 1 GB.",
        "**La significancia entre modelos ya está medida**: las 6 comparaciones del OCSVM son significativas tras Holm, pero **ninguna diferencia de falso positivo lo es**. Ver [`08-significancia-entre-modelos.md`](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/f2f0ffdb8f423cf9ac7ec48fb8390011a0d0eece/02-metodologia/historico-laboratorio/fase04-modelado/08-significancia-entre-modelos.md).",
        "**La ablación por capas ya está ejecutada** y matiza este contrato: la expansión multicapa es significativa (p < 0,001), pero las 8 variables L7 nuevas **no aportan detección medible y cuestan 5 falsos positivos**. Ver [`07-ablacion-multicapa.md`](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/blob/f2f0ffdb8f423cf9ac7ec48fb8390011a0d0eece/02-metodologia/historico-laboratorio/fase04-modelado/07-ablacion-multicapa.md).",
        "**Un solo punto de operación.** No hay segundo umbral, así que la respuesta es binaria: permitir o bloquear.",
        "**Una de sus entradas venía corrupta en producción.** Sobre un espejo SPAN, la sesión "
        "enseña la misma trama dos veces y `tcp_retransmission_ratio_10s` las contaba como "
        "retransmisiones: **0,1488 medido, 0,0000 tras deduplicar**. El modelo nunca vio esa "
        "distorsión en entrenamiento, así que toda puntuación anterior a la corrección usó "
        "esa variable fuera de su distribución. Ver system card §8.3.",
        "**Ciego a la capa 2 y al tráfico dentro de una misma VLAN.** Las 28 variables "
        "descartan toda trama que no sea IPv4, así que nunca ven una ARP; y el espejo solo "
        "cruza lo que va entre VLAN. Hay un caso medido de una máquina real invisible para "
        "este modelo. El extractor `multilayer-v3` añade tres variables de enlace, pero "
        "**este modelo no está entrenado con ellas**.",
    ], 1):
        a(f"| {i} | {s} |\n")

    a("\n---\n\n## 8 · Recomendaciones para quien lo reutilice\n\n")
    for s in ["**Recalibra el umbral** con tráfico propio antes de cualquier despliegue. El "
              "valor 1,8126 es específico de esta red y esta carga.",
              "**Cita la detección sobre Kali real**, no la global.",
              "**Acompaña toda proporción de su intervalo**; con `n = 6` los puntos engañan.",
              "**Verifica el SHA-256 antes de cargar el `.joblib`**: es un *pickle* y cargarlo ejecuta código.",
              "**No lo uses como única defensa.** Es un detector de comportamiento, complementario a un IDS por firmas."]:
        a(f"- {s}\n")
    return "".join(L)


def system_card(limpio: list[dict], pase1: list[dict]) -> str:
    g = lambda r, k, d=0: r[k] if r.get(k) is not None else d
    rows = limpio + pase1                     # disponibilidad: los dos pases
    # Las corridas H* prueban a proposito la FRONTERA del heuristico de
    # autenticacion: sus alertas son el comportamiento buscado, no falsos
    # positivos. Se excluyen del FPR, igual que en 02-resultados-f6.md.
    es_fp = lambda r: r["kind"] == "benign" and not r["id"].startswith("H")
    ben = [r for r in limpio if es_fp(r)]
    frontera = [r for r in limpio if r["kind"] == "benign" and r["id"].startswith("H")]
    atk = [r for r in limpio if r["kind"] == "attack"]
    ben1 = [r for r in pase1 if es_fp(r)]
    bw1 = sum(g(r, "windows_total") for r in ben1)
    ba1 = sum(g(r, "windows_alert") for r in ben1)
    bw, ba = sum(g(r, "windows_total") for r in ben), sum(g(r, "windows_alert") for r in ben)
    lt = sorted(r["lead_time_s"] for r in atk if r.get("lead_time_s") is not None)
    lag = [r["lag_before_s"] for r in limpio if r.get("lag_before_s") is not None]
    estables = sum(1 for r in rows if r.get("services_stable"))
    caidas = sum(1 for r in rows
                 if r.get("services_before") and r.get("services_after") and not r.get("services_stable"))
    det: dict[str, int] = {}
    for r in rows:
        for k, v in (r.get("detectors") or {}).items():
            det[k] = det.get(k, 0) + v

    L: list[str] = []
    a = L.append
    a("# System card — motor de decisión y respuesta\n\n")
    a("> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, "
      "desde `results/f6/*.jsonl` (secciones 1–7) y la reconciliación del despliegue "
      "(sección 8).\n\n")
    a("Responde por **el sistema**: qué decide, qué acción ejerce y cómo se comporta. "
      "Tiene **dos partes que no deben mezclarse**:\n\n")
    a("| Parte | Secciones | Qué describe | Modelo |\n|---|---|---|---|\n")
    a("| **A — Laboratorio evaluado (histórico)** | 1–7 | Validación F6: sensor **en línea**, "
      "bloqueo local con `nftables`, 120 s | OCSVM ([model card](MODEL_CARD_OCSVM.md)) |\n")
    a("| **B — Despliegue vigente** | 8 | Sensor por **SPAN** con **enforcement distribuido** "
      "(feed firmado → relay → agente en el host) | Isolation Forest recalibrado "
      "([model card](MODEL_CARD_IF_RECALIBRADO.md)) |\n\n")
    a("Las cifras de la parte A se midieron y valen **para lo que se midió**; no se "
      "trasladan a la parte B. Fuente de verdad del despliegue vigente: "
      "[`FICHA-TECNICA-DESPLIEGUE-VIGENTE.md`](../FICHA-TECNICA-DESPLIEGUE-VIGENTE.md). "
      "Los datos están en [`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md).\n\n---\n\n")

    a("# Parte A — Laboratorio evaluado en F6 (histórico)\n\n")
    a("## 1 · Qué hace\n\n")
    a("Cada 10 s, para cada IP iniciadora activa, el motor extrae las 28 variables con el "
      "**mismo extractor congelado** que produjo el dataset —sin duplicar fórmulas—, "
      "puntúa la ventana y decide.\n\n")
    a("```text\nPCAP en anillo + eve.json\n        │\n        ▼\n"
      "extract_multilayer_v2  ──►  28 variables\n        │\n        ▼\n"
      "OCSVM  ó  heurísticos L7   ──►  PERMIT / ALERT\n        │\n        ▼\n"
      "nftables en el propio Sensor  ──►  bloqueo 120 s\n```\n\n")
    a("El Sensor **es** el router entre la red de clientes y la de servicio, así que el "
      "bloqueo se aplica en el punto de paso: no hace falta SSH a otra máquina ni un agente "
      "en el servidor.\n\n")
    a("> **Esto describe el despliegue que se evaluó en F6**, no el que está corriendo hoy. "
      "Las cifras de las secciones 4 y 7 se midieron con el sensor en el camino del tráfico "
      "y con el OCSVM. El despliegue vigente está en la sección 8.\n")

    a("\n---\n\n## 2 · Detectores\n\n")
    a("| Detector | Qué dispara | Por qué existe |\n|---|---|---|\n")
    a("| `ocsvm_scaled` | `score < 1,8126` | El modelo de la model card |\n")
    a("| `auth_failure_heuristic` | ≥ 5 peticiones HTTP y ≥ 80 % con estado 401/403 en 60 s | El modelo es débil justo en fuerza bruta; esta regla lo cubre por la vía L7 |\n")
    a("| `empty_window_heuristic` | Ventana sin datos | Devuelve `PERMIT`: no se puntúa lo que no se observó |\n")
    a("| `no_live_packets_heuristic` | Ventana sin paquetes en vivo | Igual: `PERMIT` |\n")
    a("\n**Los dos heurísticos de ventana vacía existen por un falso positivo real.** Sin "
      "ellos, una ventana sin tráfico producía un vector de ceros que el modelo puntuaba "
      "como anómalo y bloqueaba a un cliente inocente.\n")
    a(f"\nReparto observado en las {len(rows)} corridas de F6:\n\n")
    a("| Detector | Ventanas |\n|---|---:|\n")
    for k, v in sorted(det.items(), key=lambda x: -x[1]):
        a(f"| `{k}` | {v} |\n")
    a("\n> El heurístico de autenticación **no es decorativo**: disparó en producción y "
      "detectó un rociado de contraseñas **por sí solo**, sin ayuda del modelo, con 6,1 s "
      "de adelanto. Valida en un ataque real el camino L7.\n")

    a("\n---\n\n## 3 · Acción de control (modalidad evaluada)\n\n")
    a("| | |\n|---|---|\n")
    a("| **Mecanismo** | `nftables` en VM02, vía el ayudante versionado `ppi-enforce` |\n")
    a("| **Alcance** | La IP ofensora de la red de clientes |\n")
    a("| **Duración** | **120 s**, con expiración nativa del conjunto |\n")
    a("| **Reversión** | Automática al expirar; no requiere intervención |\n")
    a("| **Lista blanca** | Direcciones de infraestructura, nunca bloqueables |\n")
    a("\nEn esta modalidad la respuesta era **binaria**: permitir o bloquear 120 s. El "
      "despliegue vigente sí tiene un nivel intermedio, **LIMIT**, y una escalera de "
      "caducidad distinta (sección 8.2); los 120 s de aquí no describen el sistema actual.\n")

    a("\n---\n\n## 4 · Desempeño en operación\n\n")
    a(f"Dos pases con el motor activo, **{len(rows)} corridas** en total.\n\n")
    a("> **Solo el pase 2 sirve para medir tiempos.** El pase 1 usó un asentamiento fijo "
      "en vez de esperar a que el motor se pusiera al día, así que sus tiempos mezclan "
      "atraso con detección; está archivado como contaminado. Se usa únicamente para "
      "disponibilidad, donde esa contaminación no aplica.\n\n")
    a("### Lo que funciona\n\n| | |\n|---|---|\n")
    if lt:
        a(f"| **Tiempo hasta el bloqueo** (ataques) | mediana **{es(statistics.median(lt))} s** · "
          f"rango {es(min(lt))}–{es(max(lt))} s · `n = {len(lt)}` bloqueos observables |\n")
    a(f"| **Caídas de servicio registradas** | **{caidas}** en {len(rows)} corridas |\n")
    a(f"| Corridas con servicios verificados | {estables}/{len(rows)} |\n")
    a("\n> **Precisión sobre la disponibilidad.** No se registró **ninguna** caída de "
      f"servicio, pero {len(rows)-estables} corridas no tienen medición de servicios. Lo "
      "correcto es decir «cero caídas registradas», no «100 % de disponibilidad "
      "verificada»: son afirmaciones distintas. Además, es una medición **de F6** (OCSVM, "
      "sensor en línea): **no demuestra la disponibilidad del despliegue vigente**, que no "
      "se ha medido con este protocolo.\n")

    a("\n### El resultado incómodo\n\n")
    a(f"> **{ba} de {bw} ventanas de tráfico legítimo se marcaron como anómalas: "
      f"{es(ba/bw*100, 2)} %.**\n")
    lo, hi = wilson(ba, bw)
    a(f"\nIntervalo de Wilson descriptivo al 95 %: **[{es(lo)} – {es(hi)}]**. El falso positivo "
      "medido en evaluación bloqueada fue **4,71 %** [2,8 – 7,9]. Las ventanas están "
      "agrupadas por corrida y comparten historia de hasta 60 s; por eso el no solapamiento "
      "de estos intervalos por ventana **no demuestra por sí solo** una diferencia inferencial.\n\n")
    a(f"De las {len(ben)} corridas benignas del pase 2, "
      f"**{sum(1 for r in ben if r.get('blocked'))} terminaron bloqueando al cliente "
      "legítimo.**\n\n")
    a(f"> Quedan fuera de este cálculo las {len(frontera)} corridas `H*`, que prueban a "
      "propósito la **frontera del heurístico de autenticación**: ahí la alerta es el "
      "comportamiento buscado, no un falso positivo. Incluirlas subiría la cifra sin que "
      "signifique lo mismo.\n\n")
    lo1, hi1 = wilson(ba1, bw1)
    a(f"El pase 1, medido por separado pero contaminado por atraso, dio "
      f"**{es(ba1/bw1*100, 2)} %** [{es(lo1)} – {es(hi1)}] sobre {bw1} ventanas. "
      "Ambos pases comparten infraestructura y no son réplicas estadísticamente independientes.\n\n")
    a("La documentación de F6 describe una reproducción **en aislamiento**, sin otro tráfico "
      "compitiendo: una transferencia "
      "`iperf-tcp` legítima de 200 Mbit/s puntuó **1,689** frente al umbral 1,8126 y cortó "
      "al cliente durante 120 s. Otra ventana pasó por **0,0014**.\n\n")
    a("> **Límite de trazabilidad.** Los scores, PCAP y registro de bloqueo de esa prueba "
      "aislada no están versionados en `results/f6/*.jsonl`; estas cifras proceden del "
      "[informe de resultados F6](https://github.com/marksato13/VF-PPI-TESIS-ORQUESTACION/"
      "blob/f2f0ffdb8f423cf9ac7ec48fb8390011a0d0eece/02-metodologia/historico-laboratorio/"
      "fase07-validacion-final/02-resultados-f6.md) del registro de investigación, y no "
      "pueden regenerarse desde los artefactos publicados.\n\n")
    a("**Causa.** El tráfico legítimo de alto volumen produce puntuaciones apiñadas justo "
      "en el margen del umbral. No es un fallo de implementación: es el umbral, calibrado "
      "sobre un conjunto donde ese tráfico estaba subrepresentado.\n\n")
    a("**Es la limitación más importante del sistema y se declara antes que cualquier "
      "resultado favorable.**\n")

    a("\n---\n\n## 5 · Modos de fallo conocidos\n\n")
    a("| Modo | Estado | Detalle |\n|---|---|---|\n")
    a("| Falso positivo sobre tráfico pesado | 🔴 **Abierto** | Sección 4. Solo lo resuelve una recalibración con tráfico pesado como normalidad |\n")
    if lag:
        a(f"| Atraso del motor bajo carga | 🟠 **Mitigado** | El parseo incremental redujo el atraso; en F6 la mediana fue {statistics.median(lag):.0f} s con un máximo de {max(lag):.0f} s. **El tiempo de bloqueo de la sección 4 aplica con el motor al día** |\n")
    a("| Falso positivo por ventana sin paquetes | ✅ Corregido | Con prueba positiva y negativa en producción |\n")
    a("| Reproceso del historial al reiniciar | ✅ Corregido | El motor descarta capturas más antiguas que su ventana |\n")
    a("| Bucle de re-bloqueo infinito | ✅ Corregido | La poda de memoria era por reloj y pasó a ser por dato |\n")
    a("| Artefactos del espejo leídos como retransmisiones | ✅ Corregido | La sesión SPAN duplicaba tramas y `tcp_retransmission_ratio_10s` las contaba: **0,1488 antes, 0,0000 después**. Se deduplica la entrada, no la fórmula |\n")
    a("| Parte del anillo descartada en silencio | ✅ Corregido | `tcpdump -W` hacía salir el proceso cada 4 min y el primer fichero de cada arranque quedaba ilegible para el motor: **5,55 %** de los bytes. El motor lo cuenta ahora en `pcaps_ilegibles` |\n")
    a("| Bloqueo por suplantación de IP | ⚪ **No evaluado** | Un tercero podría provocar el bloqueo de un cliente legítimo falsificando su origen. No se probó |\n")
    a("| Evasión del detector | ⚪ **No evaluado** | No se intentó eludirlo deliberadamente |\n")

    a("\n---\n\n## 6 · Salvaguardas (modalidad evaluada)\n\n")
    for s in ["**Lista blanca** de infraestructura, imposible de bloquear.",
              "**Expiración nativa a los 120 s**: ningún bloqueo es permanente, así que un "
              "falso positivo se corrige solo.",
              "**Sin sudo general**: el motor solo puede invocar el ayudante `ppi-enforce`, "
              "con argumentos acotados.",
              "**El panel es de solo lectura**: observa, no ejerce ninguna acción.",
              "**El motor reutiliza el extractor congelado**, así que las variables de "
              "producción son por construcción las mismas del entrenamiento."]:
        a(f"- {s}\n")

    a("\n---\n\n## 7 · Veredicto (F6)\n\n")
    a("**Demostrado con evidencia, en F6:** detectar comportamiento anómalo y **ejercer "
      "control en línea real** sobre una red enrutada, con bloqueo en una mediana de "
      f"{statistics.median(lt):.0f} s y sin ninguna caída de servicio registrada.\n\n")
    a("**No demostrado:** hacerlo con una tasa de falso positivo aceptable sobre tráfico "
      "legítimo pesado. En esa condición el sistema **todavía no es apto para operación "
      "desatendida**.\n\n")
    a("Delimitar esa frontera con medición es el resultado, no un defecto del informe.\n")

    # Seccion 8: el despliegue de produccion no es el que se evaluo. Las cifras
    # de F6 no se reescriben -se midieron y valen para lo que se midio-; lo que
    # se declara es en que difiere lo que hay hoy. Las cifras de aqui salen de
    # mediciones sobre el espejo real, citadas en docs/INVENTARIO.md y
    # docs/CASO-CAPA2-ARP.md.
    a("\n---\n\n# Parte B — Despliegue vigente\n\n")
    a("## 8 · Sensor por SPAN con enforcement distribuido\n\n")
    a("La evaluación de F6 se hizo con el sensor **en el camino del tráfico**. El "
      "despliegue vigente en la red de la entidad usa un **espejo SPAN** y aplica la "
      "respuesta **en el host protegido**. Lo que sigue describe ese despliegue; ninguna "
      "cifra de la parte A se traslada aquí.\n\n")

    a("### 8.1 · Dónde se ejerce el control\n\n")
    a("Con un espejo, el sensor **no está en el camino**: recibe una copia y **no bloquea "
      "el tráfico copiado**. Lo que hace es **decidir y publicar**: un feed firmado "
      "(ed25519) que un relay en el bastión lleva al host, donde un **agente** lo verifica "
      "y sincroniza una tabla `nftables` propia y aislada (`inet cyberflow`, sets "
      "`cyberflow_bloqueados` y `cyberflow_limitados`, con caducidad nativa). Cadena: "
      "**captura SPAN → motor → publicador → feed firmado → relay → agente → nftables**. "
      "Publicador, relay y agente corren con timers systemd (`OnCalendar=minutely`).\n\n")
    a("| Afirmación | Estado |\n|---|---|\n")
    a("| LIMIT automático de punta a punta, originado por el modelo | **Validado en vivo** "
      "(campaña del 1-oct, nota `O` de orquestación) |\n")
    a("| BLOCK aislado con regla explícita en el host | **Validado en banco** (nota `N`) |\n")
    a("| BLOCK automático de punta a punta originado por la detección | **Pendiente** |\n\n")
    a("**La mediana de 8,0 s de la sección 4 no aplica a este despliegue.** Aquí el tiempo "
      "hasta la acción está dominado por la cadencia de los timers (del orden de minutos), "
      "no por el cómputo; debe medirse de punta a punta sobre esta cadena.\n\n")

    a("### 8.2 · Detectores y respuesta\n\n")
    a("| Señal | Acción | Caducidad |\n|---|---|---|\n")
    a("| Modelo: `score_samples < −0,568892` (Isolation Forest recalibrado) | **LIMIT** | 300 s, plano |\n")
    a("| Heurístico `brute_force` o `port_scan` | **BLOCK** | 300 s → 1800 s → 3600 s si reincide |\n")
    a("| Heurístico `http_abuse` o `dns_entropy` | **LIMIT** | 300 s, plano |\n")
    a("| Ninguna señal | **PERMIT** | — |\n\n")
    a("Por IP gana la acción más severa (BLOCK > LIMIT). Desde el tercer BLOCK se marca "
      "**revisión humana**; **nunca hay bloqueo infinito automático** y el contador decae a "
      "las 24 h sin reincidir (`scripts/engine/escalada.py`). La versión de los umbrales "
      "heurísticos se registra en el feed (`VERSION_UMBRALES` de "
      "`scripts/engine/heuristicos.py`). Una lista nunca-bloquear (gateways, DNS, sensor, "
      "bastión) protege la infraestructura.\n\n")

    a("### 8.3 · El umbral se recalibró en esta red\n\n")
    a("`calibrado_en_esta_red = true`. El detector es un Isolation Forest recalibrado con "
      "tráfico normal de esta red; su umbral se fijó con `alpha = 0,05` **sobre "
      "validación** y se evaluó una sola vez sobre **test normal retenido**: FPR **4,45 %** "
      "(65 421 ventanas). Sobre ataques reales de la Kali detectó **54/78 ventanas** "
      "(HTTP 27/27, escaneo 27/43, DNS 0/8). Detalle en "
      "[`MODEL_CARD_IF_RECALIBRADO.md`](MODEL_CARD_IF_RECALIBRADO.md).\n\n")
    a("> **La caída 92,4 % → 4,45 % no aísla el efecto de recalibrar.** El 92,4 % se midió "
      "con el OCSVM en los primeros minutos sobre la red real (92 decisiones en 7 "
      "ventanas, en su mayoría interfaces del cortafuegos emitiendo CARP) y **antes** de "
      "excluir el plano de control y deduplicar el espejo; el 4,45 % se midió con otro "
      "modelo, otros datos (línea base de ~70 h) y ese filtrado ya aplicado. Cambiaron a la "
      "vez modelo, datos y alcance: para atribuir la mejora a la recalibración habría que "
      "puntuar ambos modelos sobre el mismo conjunto retenido.\n\n")

    a("### 8.4 · Qué se excluye del cálculo, y por qué\n\n")
    a("| Exclusión | Motivo | Medido |\n|---|---|---|\n")
    a("| Protocolos 112 (VRRP/CARP) y 240 (pfsync) | No son tráfico de usuarios: cada "
      "interfaz VLAN del cortafuegos emite un anuncio por segundo y pasaba a ser una "
      "entidad puntuada | **14 de 23** entidades eran eso. El **86,3 %** de las tramas de "
      "capa 2 del espejo |\n")
    a("| Copias que el espejo enseña dos veces | La sesión captura en los dos sentidos del "
      "troncal y la difusión inunda los dos puertos origen | `tcp_retransmission_ratio_10s` "
      "pasó de **0,1488 a 0,0000**: las 100 «retransmisiones» eran las 100 copias |\n")
    a("| El bastión y el propio sensor | Su SSH de gestión cruza el troncal espejado | "
      "Declaradas en `[red] excluir` |\n\n")
    a("Las tres actúan sobre la **entrada** del extractor congelado, nunca sobre sus "
      "fórmulas: son alcance, no modelo. El motor publica los contadores en cada decisión "
      "para que la exclusión sea una medición y no una afirmación.\n\n")

    a("### 8.5 · Lo que el punto de observación no puede ver\n\n")
    a("- **Tráfico dentro de una misma VLAN.** El espejo tiene origen en los troncales del "
      "cortafuegos, así que solo cruza por ahí lo que va **entre** VLAN. Una máquina que "
      "solo hable con vecinos de su segmento es invisible para las 28 variables.\n")
    a("- **Respuestas ARP completas.** Las peticiones son difusión y llegan enteras; las "
      "respuestas son unidifusión y solo llegan las dirigidas al cortafuegos.\n")
    a("- **Capas 5 y 6.** Sesión y presentación no son observables sin descifrar TLS, lo que "
      "exigiría interceptación. Es una decisión de alcance declarada, no un olvido.\n\n")
    a("El primer punto tiene un caso medido en producción: una máquina que emite **0,73 "
      "peticiones ARP por segundo** durante horas y **ni un solo paquete IP** que el espejo "
      "pueda atribuirle. Para las 28 variables es silencio absoluto. Ver "
      "[`../CASO-CAPA2-ARP.md`](../CASO-CAPA2-ARP.md).\n\n")

    a("### 8.6 · Lo que todavía no se ha medido en este despliegue\n\n")
    a("- **FPR del sistema completo** (modelo + heurísticos + enforcement) en operación: el "
      "4,45 % es del modelo sobre test normal, no del sistema.\n")
    a("- **Disponibilidad** con el protocolo de F6: las «cero caídas en 58 corridas» son de "
      "la parte A.\n")
    a("- **Tiempo de punta a punta** hasta BLOCK automático originado por la detección.\n")
    a("- **DNS**: el ensayo de septiembre apuntó a un host que no era el resolver; el 0/8 "
      "no basta para concluir que el modelo falla en DNS.\n")
    return "".join(L)


def main() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validacion = json.loads(VALIDACION.read_text(encoding="utf-8"))
    carga = lambda f: [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    limpio, pase1 = carga(F6_LIMPIO), carga(F6_PASE1)
    # newline="\n" explicito: sin el, en Windows write_text traduce cada \n a
    # CRLF y las fichas salen con otro fin de linea segun quien las genere. Ya
    # paso una vez con los CSV publicados y dos hashes dejaron de cuadrar.
    OUT_M.write_text(model_card(d, validacion), encoding="utf-8", newline="\n")
    OUT_S.write_text(system_card(limpio, pase1), encoding="utf-8", newline="\n")
    print(f"Generado: {OUT_M.relative_to(REPO)}")
    print(f"Generado: {OUT_S.relative_to(REPO)}  "
          f"({len(limpio)} corridas limpias + {len(pase1)} del pase 1)")


if __name__ == "__main__":
    main()
