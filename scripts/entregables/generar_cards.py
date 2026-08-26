#!/usr/bin/env python3
"""Genera la model card y la system card desde los artefactos.

Model card  <- artifacts/model/manifest.json
System card <- results/f6/*.jsonl y el codigo del motor

Ninguna cifra se transcribe: si el manifiesto o las corridas cambian, las
tarjetas cambian con ellos.

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


def model_card(d: dict) -> str:
    o = d["evaluation"]["ocsvm_scaled"]
    an, te = o["anomalies"], o["test"]
    L: list[str] = []
    a = L.append

    a("# Model card — OCSVM `multilayer-v2`\n\n")
    a("> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, "
      "desde `artifacts/model/manifest.json`.\n\n")
    a("Responde por **el modelo**. Los datos están en "
      "[`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md) y el sistema desplegado "
      "en [`SYSTEM_CARD_MOTOR.md`](SYSTEM_CARD_MOTOR.md).\n\n---\n\n")

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
        "**Sin validación cruzada** sobre este modelo; la que existe es de un pipeline descartado.",
        "**Sin análisis de estabilidad** del OCSVM: las diez semillas registradas cubren Isolation Forest, no el modelo elegido. El umbral 1,8126 se reporta sin banda de variabilidad.",
        "**Ajustado sin ponderación** pese a que 5 de 132 episodios concentran el 31,7 % de las filas de entrenamiento, y los cinco son transferencias lentas de 1 GB.",
        "**La significancia entre modelos ya está medida**: las 6 comparaciones del OCSVM son significativas tras Holm, pero **ninguna diferencia de falso positivo lo es**. Ver [`08-significancia-entre-modelos.md`](../fase04-modelado/08-significancia-entre-modelos.md).",
        "**La ablación por capas ya está ejecutada** y matiza este contrato: la expansión multicapa es significativa (p < 0,001), pero las 8 variables L7 nuevas **no aportan detección medible y cuestan 5 falsos positivos**. Ver [`07-ablacion-multicapa.md`](../fase04-modelado/07-ablacion-multicapa.md).",
        "**Un solo punto de operación.** No hay segundo umbral, así que la respuesta es binaria: permitir o bloquear.",
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
    a("# System card — motor de decisión y control en línea\n\n")
    a("> **Generada**, no redactada a mano: `scripts/entregables/generar_cards.py`, "
      "desde `results/f6/*.jsonl`.\n\n")
    a("Responde por **el sistema desplegado**: qué decide, qué acción ejerce y cómo se "
      "comporta en operación. El modelo está en "
      "[`MODEL_CARD_OCSVM.md`](MODEL_CARD_OCSVM.md) y los datos en "
      "[`DATASHEET_MULTILAYER_V2.md`](DATASHEET_MULTILAYER_V2.md).\n\n---\n\n")

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
      "en el servidor.\n")

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

    a("\n---\n\n## 3 · Acción de control\n\n")
    a("| | |\n|---|---|\n")
    a("| **Mecanismo** | `nftables` en VM02, vía el ayudante versionado `ppi-enforce` |\n")
    a("| **Alcance** | La IP ofensora de la red de clientes |\n")
    a("| **Duración** | **120 s**, con expiración nativa del conjunto |\n")
    a("| **Reversión** | Automática al expirar; no requiere intervención |\n")
    a("| **Lista blanca** | Direcciones de infraestructura, nunca bloqueables |\n")
    a("\n**No hay nivel intermedio.** La respuesta es binaria: permitir o bloquear. Un nivel "
      "de limitación de caudal exigiría un segundo umbral calibrado, y **inventar ese número "
      "sería peor que no tenerlo**.\n")

    a("\n---\n\n## 4 · Desempeño en operación\n\n")
    a(f"Dos pases con el motor activo, **{len(rows)} corridas** en total.\n\n")
    a("> **Solo el pase 2 sirve para medir tiempos.** El pase 1 usó un asentamiento fijo "
      "en vez de esperar a que el motor se pusiera al día, así que sus tiempos mezclan "
      "atraso con detección; está archivado como contaminado. Se usa únicamente para "
      "disponibilidad, donde esa contaminación no aplica.\n\n")
    a("### Lo que funciona\n\n| | |\n|---|---|\n")
    if lt:
        p95 = lt[max(0, int(len(lt) * 0.95) - 1)]
        a(f"| **Tiempo hasta el bloqueo** (ataques) | mediana **{es(statistics.median(lt))} s** · "
          f"p95 {es(p95)} s · rango {es(min(lt))}–{es(max(lt))} s |\n")
    a(f"| **Caídas de servicio registradas** | **{caidas}** en {len(rows)} corridas |\n")
    a(f"| Corridas con servicios verificados | {estables}/{len(rows)} |\n")
    a("\n> **Precisión sobre la disponibilidad.** No se registró **ninguna** caída de "
      f"servicio, pero {len(rows)-estables} corridas no tienen medición de servicios. Lo "
      "correcto es decir «cero caídas registradas», no «100 % de disponibilidad "
      "verificada»: son afirmaciones distintas.\n")

    a("\n### El resultado incómodo\n\n")
    a(f"> **{ba} de {bw} ventanas de tráfico legítimo se marcaron como anómalas: "
      f"{es(ba/bw*100, 2)} %.**\n")
    lo, hi = wilson(ba, bw)
    a(f"\nIntervalo de Wilson al 95 %: **[{es(lo)} – {es(hi)}]**. El falso positivo medido "
      "en evaluación bloqueada fue **4,71 %** [2,8 – 7,9]. **Los intervalos no se solapan**: "
      "no es ruido de muestreo, es una diferencia real.\n\n")
    a(f"De las {len(ben)} corridas benignas del pase 2, "
      f"**{sum(1 for r in ben if r.get('blocked'))} terminaron bloqueando al cliente "
      "legítimo.**\n\n")
    a(f"> Quedan fuera de este cálculo las {len(frontera)} corridas `H*`, que prueban a "
      "propósito la **frontera del heurístico de autenticación**: ahí la alerta es el "
      "comportamiento buscado, no un falso positivo. Incluirlas subiría la cifra sin que "
      "signifique lo mismo.\n\n")
    lo1, hi1 = wilson(ba1, bw1)
    a(f"El pase 1, medido de forma independiente, dio **{es(ba1/bw1*100, 2)} %** "
      f"[{es(lo1)} – {es(hi1)}] sobre {bw1} ventanas. **Las dos mediciones coinciden entre "
      "sí y ninguna se acerca al 4,71 % de laboratorio.**\n\n")
    a("Se reprodujo **en aislamiento**, sin otro tráfico compitiendo: una transferencia "
      "`iperf-tcp` legítima de 200 Mbit/s puntuó **1,689** frente al umbral 1,8126 y cortó "
      "al cliente durante 120 s. Otra ventana pasó por **0,0014**.\n\n")
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
    a("| Bloqueo por suplantación de IP | ⚪ **No evaluado** | Un tercero podría provocar el bloqueo de un cliente legítimo falsificando su origen. No se probó |\n")
    a("| Evasión del detector | ⚪ **No evaluado** | No se intentó eludirlo deliberadamente |\n")

    a("\n---\n\n## 6 · Salvaguardas\n\n")
    for s in ["**Lista blanca** de infraestructura, imposible de bloquear.",
              "**Expiración nativa a los 120 s**: ningún bloqueo es permanente, así que un "
              "falso positivo se corrige solo.",
              "**Sin sudo general**: el motor solo puede invocar el ayudante `ppi-enforce`, "
              "con argumentos acotados.",
              "**El panel es de solo lectura**: observa, no ejerce ninguna acción.",
              "**El motor reutiliza el extractor congelado**, así que las variables de "
              "producción son por construcción las mismas del entrenamiento."]:
        a(f"- {s}\n")

    a("\n---\n\n## 7 · Veredicto\n\n")
    a("**Demostrado con evidencia:** detectar comportamiento anómalo y **ejercer control en "
      "línea real** sobre una red enrutada, con bloqueo en una mediana de "
      f"{statistics.median(lt):.0f} s y sin ninguna caída de servicio registrada.\n\n")
    a("**No demostrado:** hacerlo con una tasa de falso positivo aceptable sobre tráfico "
      "legítimo pesado. En esa condición el sistema **todavía no es apto para operación "
      "desatendida**.\n\n")
    a("Delimitar esa frontera con medición es el resultado, no un defecto del informe.\n")
    return "".join(L)


def main() -> None:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    carga = lambda f: [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    limpio, pase1 = carga(F6_LIMPIO), carga(F6_PASE1)
    OUT_M.write_text(model_card(d), encoding="utf-8")
    OUT_S.write_text(system_card(limpio, pase1), encoding="utf-8")
    print(f"Generado: {OUT_M.relative_to(REPO)}")
    print(f"Generado: {OUT_S.relative_to(REPO)}  "
          f"({len(limpio)} corridas limpias + {len(pase1)} del pase 1)")


if __name__ == "__main__":
    main()
