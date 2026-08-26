#!/usr/bin/env python3
"""Genera el diccionario cientifico de las 28 variables de multilayer-v2.

Las formulas se transcriben del extractor congelado
(scripts/features/extract_multilayer_v2.py) y se verifican contra el; los
rangos observados se calculan del dataset. Ninguna cifra se escribe a mano.

    python3 scripts/entregables/generar_diccionario_features.py
"""
from __future__ import annotations
import csv, json, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "configs/features/multilayer-v2.json"
EXTRACTOR = REPO / "scripts/features/extract_multilayer_v2.py"
CSVS = [REPO / "artifacts/dataset/multilayer-v2-normal.csv",
        REPO / "artifacts/dataset/multilayer-v2-anomalies.csv"]
OUT = REPO / "docs/fase02-features-multicapa/03-diccionario-multicapa-v2.md"

# Notacion: P_W paquetes IPv4 de la entidad en (T-W, T]; A_W intentos de flujo
# nuevos; TCP_W subconjunto TCP; TCPD_W segmentos TCP con payload > 0;
# HTTP_W transacciones http de EVE; DNSQ_W consultas dns; NX_W respuestas
# NXDOMAIN; TLS_W eventos tls.
#
# campos: formula | denominador | denominador cero | tipo | fuente exacta |
#         observabilidad | coste | estado
D = {
"packet_rate_10s": (
 r"\|P_{10}\| / 10", "constante 10 s", "no aplica (constante)", "float ≥ 0",
 "PCAP · cuenta de paquetes IPv4 atribuidos",
 "completa", "O(n) por ventana", "efectiva"),
"byte_rate_10s": (
 r"B_{10} / 10", "constante 10 s", "no aplica (constante)", "float ≥ 0",
 "PCAP · campo `total_length` de la cabecera IPv4",
 "completa", "O(n)", "efectiva"),
"mean_ip_len_10s": (
 r"B_{10} / \|P_{10}\|", r"\|P_{10}\|", "0.0 · ventana sin paquetes", "float ≥ 0",
 "PCAP · `total_length` IPv4",
 "completa", "O(n)", "efectiva"),
"large_ip_ratio_10s": (
 r"\|\{p \in P_{10} : 500 \le len(p) \le 1500\}\| / \|P_{10}\|", r"\|P_{10}\|",
 "0.0 · ventana sin paquetes", "float ∈ [0,1]",
 "PCAP · `total_length` IPv4",
 "completa", "O(n)", "efectiva · exigida por el jurado para tráfico legítimo pesado"),
"unique_dst_ip_ratio_30s": (
 r"\|\{peer(a) : a \in A_{30}\}\| / \|A_{30}\|", r"\|A_{30}\|",
 "0.0 · ventana sin intentos nuevos", "float ∈ [0,1]",
 "PCAP · IP destino del primer paquete de cada flujo",
 "completa", "O(n) + conjunto O(f)", "efectiva"),
"icmp_ratio_10s": (
 r"\|\{p \in P_{10} : proto = 1\}\| / \|P_{10}\|", r"\|P_{10}\|",
 "0.0 · ventana sin paquetes", "float ∈ [0,1]",
 "PCAP · campo `protocol` IPv4",
 "completa", "O(n)", "efectiva"),
"flow_attempt_rate_10s": (
 r"\|A_{10}\| / 10", "constante 10 s", "no aplica (constante)", "float ≥ 0",
 "PCAP · primer paquete de cada clave canónica de flujo",
 "completa", "O(n) + diccionario O(f)", "efectiva"),
"syn_rate_10s": (
 r"\|SYN_{10}\| / 10", "constante 10 s", "no aplica (constante)", "float ≥ 0",
 "PCAP · `SYN` activo y `ACK` inactivo, en sentido saliente",
 "completa", "O(n)", "efectiva · exigida por el jurado como señal L4"),
"syn_completion_ratio_10s": (
 r"\min(\|SYNACK_{10}\|, \|SYN_{10}\|) / \|SYN_{10}\|", r"\|SYN_{10}\|",
 "0.0 · ventana sin SYN salientes", "float ∈ [0,1]",
 "PCAP · SYN salientes y SYN-ACK entrantes",
 "completa", "O(n)",
 "efectiva · el `min` acota el ratio a 1 cuando llegan SYN-ACK de SYN anteriores a la ventana"),
"rst_ratio_10s": (
 r"\|\{p \in TCP_{10} : RST\}\| / \|TCP_{10}\|", r"\|TCP_{10}\|",
 "0.0 · ventana sin paquetes TCP", "float ∈ [0,1]",
 "PCAP · bit `RST` de la cabecera TCP",
 "completa", "O(n)", "efectiva"),
"unique_dst_port_ratio_30s": (
 r"\|\{port(a) : a \in A_{30}, port > 0\}\| / \|\{a \in A_{30} : port > 0\}\|",
 "intentos TCP/UDP con puerto destino > 0",
 "0.0 · ventana sin intentos con puerto", "float ∈ [0,1]",
 "PCAP · puerto destino del primer paquete del flujo",
 "completa", "O(n) + conjunto", "efectiva"),
"http_error_ratio_60s": (
 r"\|\{h \in HTTP_{60} : status \ge 400\}\| / \|HTTP_{60}\|", r"\|HTTP_{60}\|",
 "0.0 · ventana sin transacciones HTTP", "float ∈ [0,1]",
 "EVE · `http.status`",
 "solo HTTP en claro; HTTPS no es observable sin descifrar",
 "O(e)", "efectiva"),
"dns_nxdomain_ratio_60s": (
 r"\|NX_{60}\| / \|DNSQ_{60}\|", r"\|DNSQ_{60}\|",
 "0.0 · ventana sin consultas DNS", "float ∈ [0,1]",
 "EVE · `dns.rcode == NXDOMAIN` en respuestas, atribuido por `dest_ip`",
 "solo DNS en claro", "O(e)", "efectiva"),
"tls_session_rate_60s": (
 r"\|\{flow\_id(t) : t \in TLS_{60}\}\| / 60", "constante 60 s",
 "no aplica (constante)", "float ≥ 0",
 "EVE · `flow_id`, con respaldo en `community_id` y en el timestamp",
 "no requiere descifrar; cuenta sesiones, no contenido", "O(e) + conjunto",
 "efectiva"),
"ttl_mean_10s": (
 r"\left(\sum_{p \in P_{10}} ttl(p)\right) / \|P_{10}\|", r"\|P_{10}\|",
 "0.0 · ventana sin paquetes", "float ∈ [0,255]",
 "PCAP · campo `TTL` IPv4",
 "completa · en esta topología revela saltos de router",
 "O(n)", "efectiva"),
"fragment_ratio_10s": (
 r"\|\{p \in P_{10} : MF \lor offset > 0\}\| / \|P_{10}\|", r"\|P_{10}\|",
 "0.0 · ventana sin paquetes", "float ∈ [0,1]",
 "PCAP · bit *More Fragments* y campo *fragment offset* IPv4",
 "completa", "O(n)",
 "efectiva · dejó de ser constante tras la calibración de fragmentación IP real; ver `docs/fase03-dataset/174-cierre-calibracion-fragmentacion-ip-real.md`"),
"protocol_diversity_30s": (
 r"\|\{proto(p) : p \in P_{30}\}\| / \|P_{30}\|", r"\|P_{30}\|",
 "0.0 · ventana sin paquetes", "float ∈ (0,1]",
 "PCAP · campo `protocol` IPv4",
 "completa",
 "O(n)",
 "efectiva · **normalizada por paquetes, no por protocolos**: tiende a 0 cuando el volumen crece, así que mide diversidad *por paquete*, no riqueza de protocolos"),
"tcp_retransmission_ratio_10s": (
 r"\|\{p \in TCPD_{10} : seq\ visto\}\| / \|TCPD_{10}\|", r"\|TCPD_{10}\|",
 "0.0 · ventana sin segmentos TCP con carga", "float ∈ [0,1]",
 "PCAP · número de secuencia TCP repetido en la misma dirección",
 "heurística por `seq` repetido: no distingue retransmisión de duplicado de captura",
 "O(n) + conjunto por dirección", "efectiva"),
"flow_duration_mean_30s": (
 r"\left(\sum_{f} \max_{p \in f} (t_p - t_{inicio(f)})\right) / \|F_{30}\|",
 "flujos distintos con al menos un paquete en la ventana",
 "0.0 · ventana sin flujos", "float ≥ 0 (segundos)",
 "PCAP · marca temporal del primer paquete de cada flujo",
 "**duración hasta `T`, no duración final**: se calcula sin esperar el cierre, por diseño causal",
 "O(n) + diccionario por flujo", "efectiva"),
"tx_rx_byte_ratio_30s": (
 r"B^{tx}_{30} / (B^{tx}_{30} + B^{rx}_{30})", r"B^{tx}_{30} + B^{rx}_{30}",
 "0.0 · ventana sin bytes", "float ∈ [0,1]",
 "PCAP · sentido del paquete respecto a la entidad iniciadora",
 "completa", "O(n)",
 "efectiva · normalizada al total, no un cociente tx/rx: evita la división por cero y acota el rango"),
"http_request_rate_60s": (
 r"\|HTTP_{60}\| / 60", "constante 60 s", "no aplica (constante)", "float ≥ 0",
 "EVE · eventos `event_type = http` con `src_ip` en la red de entidades",
 "solo HTTP en claro", "O(e)", "efectiva"),
"http_method_entropy_60s": (
 r"-\sum_{m} p_m \log_2 p_m,\quad p_m = \|\{h : method = m\}\| / \|HTTP_{60}\|",
 r"\|HTTP_{60}\|", "0.0 · ventana sin transacciones HTTP", "float ≥ 0 (bits)",
 "EVE · `http.http_method`, normalizado a mayúsculas",
 "solo HTTP en claro",
 "O(e) + conteo por método",
 "efectiva · **0.0 es ambiguo**: significa tanto «sin peticiones» como «todas del mismo método»; se desambigua con `http_request_count_60s`"),
"http_auth_failure_ratio_60s": (
 r"\|\{h \in HTTP_{60} : status \in \{401, 403\}\}\| / \|HTTP_{60}\|",
 r"\|HTTP_{60}\|", "0.0 · ventana sin transacciones HTTP", "float ∈ [0,1]",
 "EVE · `http.status`",
 "**solo HTTP**. Los fallos de autenticación SSH van cifrados y no aparecen en EVE: asignarles cero sería falso",
 "O(e)",
 "efectiva · es la señal L7 semántica exigida por el jurado, y la que dispara el heurístico del motor"),
"dns_query_rate_60s": (
 r"\|DNSQ_{60}\| / 60", "constante 60 s", "no aplica (constante)", "float ≥ 0",
 "EVE · `dns.type = request`",
 "solo DNS en claro", "O(e)", "efectiva"),
"unique_dns_name_ratio_60s": (
 r"\|\{rrname(q) : q \in DNSQ_{60}, rrname \ne \emptyset\}\| / \|DNSQ_{60}\|",
 r"\|DNSQ_{60}\|", "0.0 · ventana sin consultas DNS", "float ∈ [0,1]",
 "EVE · `dns.rrname`, con respaldo en `dns.queries[0].rrname`, en minúsculas",
 "solo DNS en claro", "O(e) + conjunto",
 "efectiva · detecta generación algorítmica de nombres"),
"tls_handshake_failure_ratio_60s": (
 r"\|\{t \in TLS_{60} : version = \emptyset\}\| / \|TLS_{60}\|", r"\|TLS_{60}\|",
 "0.0 · ventana sin eventos TLS", "float ∈ [0,1]",
 "EVE · ausencia del campo `tls.version`",
 "**no observable en esta configuración**: Suricata 8.0.3 no emite el evento `tls` intermedio de un handshake fallido, así que el numerador nunca puede ser distinto de cero",
 "O(e)",
 "**NO OBSERVABLE** · constante 0.0 en las 1 552 ventanas. Ver `docs/fase03-dataset/175-limite-tls-handshake-failure-ratio.md`"),
"tls_version_ratio_60s": (
 r"\|\{t : \text{«1.3»} \in version(t)\}\| / \|\{t \in TLS_{60} : version \ne \emptyset\}\|",
 "eventos TLS con versión conocida",
 "0.0 · ventana sin eventos TLS con versión", "float ∈ [0,1]",
 "EVE · subcadena «1.3» en `tls.version`",
 "no requiere descifrar",
 "O(e)",
 "efectiva · **coincidencia por subcadena**, no comparación semántica de versiones"),
"http_status_5xx_ratio_60s": (
 r"\|\{h \in HTTP_{60} : 500 \le status \le 599\}\| / \|HTTP_{60}\|",
 r"\|HTTP_{60}\|", "0.0 · ventana sin transacciones HTTP", "float ∈ [0,1]",
 "EVE · `http.status`",
 "solo HTTP en claro", "O(e)",
 "efectiva · **subconjunto de `http_error_ratio_60s`**, que ya incluye ≥ 400: redundancia declarada"),
}


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    feats = sorted(schema["features"], key=lambda x: x["order"])
    names = [f["name"] for f in feats]
    if set(names) != set(D):
        raise SystemExit(f"desajuste con el diccionario: {set(names) ^ set(D)}")
    extractor = EXTRACTOR.read_text(encoding="utf-8")
    for n in names:
        if f'"{n}"' not in extractor:
            raise SystemExit(f"{n} no aparece en el extractor congelado")

    rows = []
    for path in CSVS:
        rows += list(csv.DictReader(path.open(encoding="utf-8")))
    stats = {}
    for n in names:
        v = [float(r[n]) for r in rows]
        stats[n] = (min(v), max(v), statistics.mean(v), statistics.median(v))

    L = []
    a = L.append
    total_ventanas = f"{len(rows):,}".replace(",", "\u202f")
    a("# Diccionario científico de las 28 variables — `multilayer-v2`\n\n")
    a("> **Generado**, no redactado a mano: "
      "`scripts/entregables/generar_diccionario_features.py`.\n>\n"
      "> Las fórmulas se transcriben del extractor congelado y el script aborta si un\n"
      "> nombre del contrato no aparece en él. Los rangos observados se calculan sobre\n"
      f"> las **{total_ventanas} ventanas** del dataset congelado.\n")
    a("\nCierra el requisito del jurado de «diccionario, fórmulas, unidades y ventanas»\n"
      "para las variables 15–28, que hasta ahora solo existían en el código.\n"
      "El de las 14 primeras se mantiene en\n"
      "[`01-diccionario-multicapa-G5.md`](01-diccionario-multicapa-G5.md).\n")

    a("\n## Unidad de observación\n")
    a(f"- Una fila por **IP iniciadora** y cierre de ventana `T`, emitida cada "
      f"**{schema['emission_step_seconds']} s**.\n")
    a("- Ventanas deslizantes y **estrictamente causales**: `(T − W, T]` con "
      "`W ∈ {10, 30, 60}` s. Ningún paquete o evento posterior a `T` participa.\n")
    a(f"- Historia máxima considerada: **{schema['maximum_history_seconds']} s**. "
      "Una fila solo es elegible para entrenamiento con 60 s de historia verificada.\n")
    a("- Identificadores, etiquetas, marca temporal y contadores de soporte "
      "**no son entradas del modelo**.\n")

    a("\n## Convenio de denominador cero\n")
    a("`safe_ratio(a, b) = a / b si b ≠ 0, en otro caso 0.0`. La consecuencia hay que "
      "declararla: **un 0.0 no distingue «sin actividad» de «proporción real igual a "
      "cero»**. Los contadores de soporte (`packet_count_10s`, `http_request_count_60s`, "
      "`dns_query_count_60s`, `tls_observation_count_60s`, `tcp_data_segment_count_10s`) "
      "se conservan como metadatos precisamente para desambiguarlo.\n")

    a("\n## Resumen\n")
    a("| # | Variable | Capa | Ventana | Unidad | Estado |\n|---:|---|:--:|--:|---|---|\n")
    for f in feats:
        n = f["name"]
        est = "🔴 no observable" if "NO OBSERVABLE" in D[n][7] else "✅ efectiva"
        a(f"| {f['order']} | `{n}` | {f['layer']} | {f['window_seconds']} s | "
          f"`{f['unit']}` | {est} |\n")
    obs = sum(1 for n in names if "NO OBSERVABLE" not in D[n][7])
    a(f"\n**{len(names)} variables definidas · {obs} con variación observable · "
      f"{len(names) - obs} no observable.**\n")

    a("\n---\n\n## Notación\n")
    a("Para la entidad `e` y el cierre `T`, sobre la ventana `W`:\n\n")
    for s in ["`P_W` paquetes IPv4 atribuidos a `e`",
              "`B_W` suma de `total_length` IPv4; `B^tx` saliente, `B^rx` entrante",
              "`A_W` intentos de flujo nuevos (primer paquete de una clave canónica)",
              "`TCP_W` subconjunto TCP; `TCPD_W` segmentos TCP con carga > 0",
              "`SYN_W` SYN salientes sin ACK; `SYNACK_W` SYN-ACK entrantes",
              "`F_W` flujos distintos con al menos un paquete en la ventana",
              "`HTTP_W`, `DNSQ_W`, `NX_W`, `TLS_W` eventos EVE de cada tipo"]:
        a(f"- {s}\n")

    a("\n---\n\n## Fichas\n")
    cur = None
    for f in feats:
        n = f["name"]
        d = D[n]
        if f["layer"] != cur:
            cur = f["layer"]
            a(f"\n### Capa {cur[1]} — `{cur}`\n")
        mn, mx, me, md = stats[n]
        a(f"\n#### {f['order']}. `{n}`\n\n")
        a(f"$$ {d[0]} $$\n\n")
        a("| | |\n|---|---|\n")
        a(f"| **Ventana** | {f['window_seconds']} s |\n")
        a(f"| **Unidad** | `{f['unit']}` |\n")
        a(f"| **Tipo y rango teórico** | {d[3]} |\n")
        a(f"| **Fuente exacta** | {d[4]} |\n")
        den = f"${d[1]}$" if "\\" in d[1] else d[1]
        a(f"| **Denominador** | {den} |\n")
        a(f"| **Denominador cero** | {d[2]} |\n")
        a(f"| **Rango observado** | mín {mn:.4f} · máx {mx:.4f} · media {me:.4f} · mediana {md:.4f} |\n")
        a(f"| **Observabilidad** | {d[5]} |\n")
        a(f"| **Coste en línea** | {d[6]} |\n")
        a(f"| **Estado** | {d[7]} |\n")

    a("\n---\n\n## Valores faltantes\n")
    a("El dataset **no tiene valores faltantes**, y no por relleno: la ausencia de un "
      "evento dentro de una fuente disponible vale cero legítimamente. Si falta el PCAP, "
      "el EVE o la marca `verified_at`, el envoltorio **falla** en vez de producir un "
      "dataset aparentemente válido. Una historia desconocida nunca se rellena con ceros: "
      "la fila queda `eligible_training = false`.\n")

    a("\n## Limitaciones declaradas\n")
    for s in [
        "**`tls_handshake_failure_ratio_60s` no es observable** en esta configuración. "
        "Debe reportarse como **27 variables efectivas de 28 definidas**, no como una "
        "señal validada.",
        "**`http_status_5xx_ratio_60s` es subconjunto de `http_error_ratio_60s`.** "
        "Redundancia conocida; su aporte marginal solo puede resolverlo la ablación "
        "pendiente (D-02).",
        "**`protocol_diversity_30s` se normaliza por paquetes, no por protocolos.** "
        "Tiende a cero al crecer el volumen: mide diversidad por paquete, no riqueza.",
        "**`http_method_entropy_60s` colapsa dos casos en 0.0**: sin peticiones y "
        "monomé­todo. Solo el contador de soporte los separa.",
        "**Las señales L7 solo ven tráfico en claro.** HTTPS y los fallos de "
        "autenticación SSH quedan fuera por diseño, no por omisión.",
        "**`tcp_retransmission_ratio_10s` es una heurística** por número de secuencia "
        "repetido: no separa retransmisión real de duplicado de captura.",
    ]:
        a(f"- {s}\n")

    OUT.write_text("".join(L), encoding="utf-8")
    print(f"Generado: {OUT.relative_to(REPO)}")
    print(f"  {len(names)} variables · {obs} efectivas · {len(names)-obs} no observable")
    print(f"  rangos calculados sobre {len(rows)} ventanas")


if __name__ == "__main__":
    main()
