# B4 — Fuerza bruta: endpoint 401 + medición

Cierra la 4ª familia de ataque (`brute_force`) de la tabla comparativa. La idea:
un endpoint que exige login y responde **401** a cada intento fallido; una ráfaga
de logins equivocados genera muchos 401 que Suricata lee del espejo y el heurístico
`brute_force` convierte en **BLOCK**.

## Por qué HTTP en claro
El sensor observa por espejo SPAN (pasivo). Suricata solo puede extraer el
`status` (401) si el tráfico **no** va cifrado. Por eso el endpoint es HTTP, no
HTTPS. La señal que mide CyberFlow (`extract_multilayer_v2.py`):
`http_auth_failure_ratio_60s = nº de HTTP con status 401/403 ÷ total HTTP en 60 s`.
Umbral del heurístico (`heuristicos.py`, versión 2026-10-06.1):
**≥5 req HTTP/60s y ≥80 % de fallo de auth → BLOCK**.

## Pasos

1. **En el host DMZ** (10.10.30.10), arrancar el endpoint (no necesita sudo):
   ```
   python3 endpoint_401.py --port 8081
   ```
   Si el cortafuegos del host no deja entrar al 8081, ábrelo o usa un puerto ya
   permitido con `--port`. Sin credenciales reales: todo intento es 401. (Opcional
   para un "login correcto" en la demo: `DEMO_OK_USER`/`DEMO_OK_PASS` de laboratorio.)

2. **Medir** (desde el bastión, con el endpoint arriba):
   ```
   bash medir_brute.sh 10.10.30.10 8081
   ```
   Lanza 80 logins fallidos desde la Kali y mide los tres tiempos
   (detección/decisión/respuesta) anclados al reloj del sensor, igual que el
   escaneo. Hace un pre-check de que el endpoint responde 401.

3. **Comprobar el corte real** en el host:
   ```
   sudo nft list set inet cyberflow cyberflow_bloqueados   # aparece 10.10.20.30
   ```

## Nota de narrativa (demo)
El **modelo** detecta flojo la fuerza bruta (50–55 %, declarado en el panel); quien
la caza es el **heurístico** `brute_force`. Correrla en vivo demuestra que el
heurístico tapa el hueco del modelo — justo el valor del enfoque híbrido.

> `medir_brute.sh` vive en el scratchpad de la sesión (no se versiona porque lleva
> rutas/llaves del laburo); este README documenta cómo reproducirlo.
