# Guion de demo — validación interna técnica (CyberFlow)

Guion **reproducible** para la sesión del jueves. Objetivo: que el producto se
vea FUNCIONANDO y que cada afirmación tenga su evidencia a la vista. Orden
pensado para responder, en vivo, los diez puntos técnicos del profesor.

> Regla de oro de la demo: **nada de "es rápido" / "detecta anomalías"** a secas.
> Cada cosa con su número y su sitio en el panel.

## 0. Antes de empezar (checklist, 5 min)

- [ ] **Reiniciar el panel** para cargar los cambios nuevos (heurístico visible +
      umbrales): en el sensor `sudo systemctl restart ppi-dashboard`. **(sudo de Mark)**
- [ ] Abrir el panel a pantalla completa: `cf-panel.cmd` → `https://10.10.60.11:8788`
      (certificado autofirmado; aceptar la huella). Login como **admin**, modo
      **desarrollador** (para que se vean Topología, Variables, Alcance, Modelo).
- [ ] Verificar que el motor y Suricata están **verdes** en *Salud del sistema*.
- [ ] Dejar `nft list table inet cyberflow` limpio en el host DMZ (sin bloqueos
      heredados): `sudo nft flush set inet cyberflow cyberflow_bloqueados`.
- [ ] Tener a mano la terminal de la Kali (10.10.20.30) y una del host DMZ.
- [ ] **Empezar a grabar** la sesión (requisito del profe, audio 10).

## 1. Arquitectura y alcance (2–3 min) — *responde req. 2, 7, 9*

1. Sección **Topología y flujo**: recorrer el camino SPAN → sensor → motor →
   feed firmado → agente en el host. Recalcar: **el sensor observa por espejo
   (pasivo) y NUNCA sale a Internet**; la acción la aplica el agente EN el host.
2. Sección **Variables por capa**: son **28 variables** que puntúa el modelo,
   repartidas en **L3/L4/L7**. Aquí se responde lo de **capa 2** (ing. Fernando):
   el modelo desplegado (v2) **no** usa L2; la L2 entra por la **deduplicación
   del espejo** (el SPAN duplica cada trama) y por el extractor v3 (no desplegado).
   Incorporar L2 al scoring = reentrenar v3 (siguiente versión).
3. Sección **Alcance del análisis**: lo que se captura pero **no** se puntúa, con
   su cifra. "Sin número, «se excluyó» no es una medición."

## 2. Qué detecta y cómo decide (3 min) — *responde req. 3, 5, 6*

1. Sección **Modelo congelado**: IsolationForest **recalibrado en esta red**,
   umbral fijo `score_samples < -0,568892`. Explicar los **tres regímenes de
   aprendizaje**: congelado en operación (reproducible) + reentrenamiento
   periódico; **no** aprende en caliente (un ataque sostenido no se "normaliza").
   Mostrar el **punto débil declarado**: fuerza bruta 50–55 %.
2. Sección **heurísticos** (en la topología): las **cuatro reglas** con sus
   **umbrales exactos y versión `2026-10-06.1`**. Es la respuesta a "¿de dónde
   salen esos umbrales?": versionados y trazables, no mágicos.
3. **Anomalía desconocida (sin firma)**: lo coge el modelo one-class + los
   heurísticos. Es el aporte frente a Suricata (firmas). → se demuestra en §3.

## 3. Escenario en vivo: escaneo → BLOCK (5 min) — *responde req. 1, 3, 4, 5*

**Hero del demo** (el más limpio y rápido: `port_scan`→BLOCK).

1. En la Kali, lanzar el escaneo contra el host DMZ (acotado a 1-1000 para que sea
   rápido; el catálogo del panel usa la variante completa `-p-`):
   ```
   nmap -sT -T4 --max-retries 1 -p 1-1000 --open 10.10.30.10
   # variante del catálogo: nmap -sT -sV -T4 -p- --open 10.10.30.10
   ```
2. En el panel, sección **Actividad** y **Decisiones recientes**: aparece la
   entidad 10.10.20.30 con **Acción = BLOCK** y, en *Motivo*, el badge del
   heurístico **`port_scan`** + "N intentos/30s…" (detección **sin firma**).
3. **Los tres tiempos** (medidos, doc `evidencias/tiempos-2026-10-06.md`):
   - **detección** ≈ **1–9 s** (el motor marca en el tick de 10 s),
   - **decisión** ≈ **17–18 s** (el feed firmado emite la acción),
   - **respuesta** ≈ **51–57 s** (el agente aplica `nft` en el host).
   Diferenciarlos explícitamente: el cómputo es de segundos; el resto es la
   **cadencia del feed firmado** (seguridad > latencia), y es **configurable**.
4. **Corte real en el host** (no es teatro del panel):
   ```
   # en el host DMZ:
   sudo nft list set inet cyberflow cyberflow_bloqueados   # aparece 10.10.20.30
   # desde la Kali, comprobar que ya no pasa:
   curl -m 3 -o /dev/null -w "%{http_code}\n" http://10.10.30.10/   # -> 000 (cortado)
   ```

## 4. Breadth: DNS alta entropía → LIMIT (3 min) — *responde req. 5, 6*

Demostrar la **acción diferenciada** (no todo es BLOCK) y la anomalía **sin
firma** que Suricata (ET Open) **no** cazó (comparación, nota 26: CyberFlow 3/3,
Suricata 0/9).

1. En la Kali, ráfaga de consultas DNS tipo DGA contra el **resolver 10.10.10.20**
   (no al DMZ): nombres aleatorios de un TLD inexistente → todas únicas y NXDOMAIN.
   ```
   for i in $(seq 1 40); do dig +time=1 +tries=1 @10.10.10.20 x$RANDOM$RANDOM.invalid A >/dev/null 2>&1; done
   ```
   (dispara `dns_entropy`: ≥20 consultas/60s con ≥45 % únicas o ≥50 % NXDOMAIN.)
2. En **Decisiones**: entidad con **Acción = LIMIT**, motivo `dns_entropy`.
   Explicar por qué **LIMIT y no BLOCK**: ambiguo (podría ser uso legítimo) →
   degradar, no cortar. Con FPR 4,45 % en red real, degradar es más barato que
   cortar en falso.

## 5. Datos auténticos y traslado sim→real (2 min) — *responde req. 7, 8*

1. **Variables por capa** muestra valores **reales** tomados del dataset de la
   línea base que se está acumulando (no cifras inventadas).
2. El dato fuerte del traslado **sim→real**: la **recalibración en esta red
   bajó el FPR del 92,4 % al 4,45 %**. Es la respuesta concreta al
   *distribution shift*: el umbral de otra red daba 92 % de falsos; recalibrado
   aquí, 4,45 %.
3. El experimento es **reproducible**: método de **replay de PCAP** (mismo PCAP a
   CyberFlow y a Suricata, reloj anclado al sensor) — el PCAP es el artefacto
   verificable (orquestación, notas 19–26).

## 6. Código y modelo (2 min) — *responde req. 2*

- Repo **`producto-as-deployed`**: snapshot *as-deployed* del sensor (lo que
  corre de verdad, no una maqueta).
- **Dónde está el modelo**: `artifacts/preliminar/if_recalibrado_desplegable.joblib`;
  umbral en `artifacts/preliminar/manifest-if-recalibrado.json`.
- **Motor**: `scripts/engine/motor_decision.py`; **heurísticos**:
  `scripts/engine/heuristicos.py` (umbrales versionados); **feed firmado**:
  `publicar_feed.py` + `feed.py` (ed25519); **agente**: `agente_enforce.py`.

## 7. Cierre: observaciones → mejoras (req. 10)

- La sesión queda **grabada**. Las observaciones de los expertos se convierten en
  issues/mejoras (p. ej. L2 en el scoring = v3; acción de cuarentena; endpoint
  401 para cerrar la familia de fuerza bruta).

---

## Pendientes que condicionan la demo

| Pendiente | De quién | Bloquea |
|---|---|---|
| `sudo systemctl restart ppi-dashboard` (cargar panel nuevo) | Mark | §0, que se vean heurístico+umbrales |
| Instalar timers systemd del enforcement (si no están) | Mark (sudo) | §3 respuesta automática |
| Endpoint **401** en el host DMZ | Mark | §4-bis fuerza bruta (B4) — opcional en la demo |
| Decisión **cuarentena** A/B | Mark | discurso de "aislar" (req. 5) |
| Ensayo e2e cronometrado completo | conjunto | cerrar B6 |

## Presupuesto de tiempo

~22–25 min de demo + preguntas. Núcleo imprescindible: §1, §2, §3, §6. §4 y §5
si hay tiempo; refuerzan mucho pero el escaneo (§3) ya demuestra el ciclo
completo detección→decisión→respuesta→corte real.
