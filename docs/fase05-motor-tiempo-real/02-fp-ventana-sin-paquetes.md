# Hallazgo y corrección — falso positivo por ventana sin paquetes (desincronización PCAP/EVE)

- **Fecha:** 2026-08-18
- **Encontrado por:** Claude (revisión adversarial), durante la validación en vivo del `auth_failure_heuristic` con tráfico real.
- **Estado:** **corregida** — verificada en producción (VM02) con prueba positiva y negativa reales.
- **Enlaza:** [`01-diseno-motor-tiempo-real.md`](01-diseno-motor-tiempo-real.md), [`../07-mejoras-futuras/01-debilidades-y-mejoras.md`](../07-mejoras-futuras/01-debilidades-y-mejoras.md)

## 1. Identificador y título

`MOTOR-FP-01` — El motor bloqueaba clientes legítimos por ventanas con `packet_count_10s == 0` pero señal L7 residual.

## 2. Severidad

**Alta.** Producía bloqueo automático (nftables, 120 s) de una IP LAN **legítima** ante un patrón de tráfico completamente normal y frecuente: hacer una petición HTTP y luego quedar en silencio unos segundos. En una red real esto ocurre en casi cada interacción de usuario. Toca directamente la observación del jurado sobre falsos positivos con tráfico legítimo.

## 3. Hecho observado y evidencia concreta

Durante la validación en vivo, una **sola** petición benigna `GET / → 200 OK` desde el Cliente `10.20.0.20` produjo, en la ventana inmediatamente posterior, esta decisión real (extraída de `motor_decision.log` en VM02):

```json
{
  "decision": "ALERT", "detector_name": "ocsvm_scaled",
  "enforcement": {"applied": true,
    "helper_output": "{\"status\": \"blocked\", \"ip\": \"10.20.0.20\", \"timeout_seconds\": 120}"},
  "entity_ip": "10.20.0.20", "packet_count_10s": 0, "score": 0.0,
  "threshold": 1.8126087939765134, "window_end_utc": "2026-08-18T14:45:10+00:00"
}
```

`packet_count_10s: 0`, `score: 0.0`, `applied: true` — el cliente legítimo quedó **bloqueado 120 s**. Se reprodujo de forma determinista: cada `GET` benigno seguido de silencio disparaba el mismo patrón.

## 4. Inferencias (separadas del hecho)

- **Hecho:** el vector con `packet_count_10s == 0` (pero `http_request_count_60s ≥ 1`) recibe del OCSVM un score de ~0.0, por debajo del umbral 1.8126 → ALERT.
- **Inferencia (causa raíz):** el motor toma las features L3/L4 del anillo de PCAP (tcpdump, que **bufferiza** y solo vuelca a disco al rotar cada 15 s) y las features L7 de `eve.json` (Suricata, **continuo**). Existe una ventana temporal en la que el motor ya ve el **evento HTTP** de una petición pero todavía **no sus paquetes** → `http_request_count_60s ≥ 1` con `packet_count_10s = 0`. El vector queda casi todo en cero salvo las features L7 de 60 s.
- **Inferencia:** el modelo se entrenó solo con ventanas que tenían paquetes L3/L4 dentro de su ventana de captura, así que un vector sin paquetes es fuera-de-distribución y se puntúa como anómalo (~0.0). El guard `empty_window` existente no lo atrapaba porque exige que **todos** los contadores (incluidos los de 60 s) sean cero, y aquí el contador L7 de 60 s no lo era.

## 5. Riesgo

- **Funcionamiento:** bloqueo recurrente de clientes legítimos → denegación de servicio autoinfligida sobre el tráfico normal.
- **Validez científica:** un FPR operativo medido con este bug estaría inflado por una causa puramente de ingeniería (desincronización de fuentes), no por el modelo. Habría contaminado la validación final (equivalente F6).

## 6. Prueba reproducible (positiva y negativa)

- **Negativa (antes):** desde VM05, `curl http://10.30.0.10/` una vez, luego silencio; observar en `motor_decision.log` la ventana siguiente de `10.20.0.20` → `ALERT ocsvm_scaled score=0.0 pkts10=0 enforced=true`.
- **Positiva (después del fix):** misma acción → la ventana `14:57:00` se registró como `PERMIT no_live_packets_heuristic pkts10=0`, **sin** enforcement; lista de bloqueos vacía.
- **No-regresión de detección (después del fix):** ráfaga de 10× `POST /api/login → 401` desde Kali `10.20.0.100`; la ventana `15:03:00` se registró como `ALERT auth_failure_heuristic pkts10=0 enforced=true` y el 10.º request obtuvo `000` (Kali bloqueada a mitad del ataque).

## 7. Corrección aplicada y efectos secundarios

Cambio en `scripts/engine/motor_decision.py` (sin tocar el modelo ni el umbral):

1. **Guard ampliado:** cualquier ventana con `packet_count_10s == 0` ya no se puntúa con el modelo; se marca `PERMIT` con detector `no_live_packets_heuristic` (o `empty_window_heuristic` si además todos los contadores L7 son cero). Justificación: sin paquetes L3/L4 el modelo es fuera-de-distribución, y la ausencia de paquetes no es un ataque.
2. **El heurístico de fuerza bruta se evaluó fuera del `else` del modelo**, para que siga disparando sobre ventanas `no_live_packets`. Sus features (`http_request_count_60s`, `http_auth_failure_ratio_60s`) provienen de `eve.json` (L7), que es válido aunque el PCAP no haya volcado los paquetes. Así una ráfaga de 401 se detecta por L7 sin esperar al vuelco del anillo.
3. **Gate de enforcement:** se quitó el guard redundante `not empty_window` → ahora es `decision == "ALERT"` a secas, para que el heurístico que dispara sobre una ventana sin paquetes también bloquee.

**Efecto secundario buscado (mejora):** la detección de fuerza bruta es ahora **más rápida y robusta** que antes — ocurre por L7 en cuanto hay ≥5 peticiones con ≥80 % 401/403, sin depender de que el modelo puntúe (que en fuerza bruta acierta solo 50-55 %) ni del vuelco del anillo de PCAP.

**Efecto secundario a vigilar:** un ataque cuyos **paquetes** son anómalos pero que **no** genera señal L7 (p. ej. SYN flood puro, sin HTTP) y cuyos paquetes aún no volcaron al PCAP, no se puntuaría en esa ventana `pkts10=0`; se detecta en la ventana siguiente cuando el PCAP vuelca (`pkts10>0`). Es el mismo retardo de ≤15 s del anillo ya declarado en `01-diseno-motor-tiempo-real.md`, no un hueco nuevo.

Verificación local antes de desplegar: `python3 -m py_compile` + un test de la lógica de decisión con 7 casos sintéticos (ventana vacía, FP `pkts10=0`+http, anómalo con paquetes, heurístico con paquetes, benigno pesado, **fuerza bruta L7 sin paquetes**, y `pkts10=0` con 3×401 que NO debe disparar). Los 7 pasan.

## 8. Estado

**Corregida y verificada en producción.** Hashes del motor idénticos entre repo y VM02 tras el despliegue; los cuatro servicios activos.

## Nota relacionada — replay de backlog al reiniciar el motor (`MOTOR-OBS-02`, observación, severidad media)

Durante esta sesión se observó que, al **reiniciar** `ppi-motor.service`, el motor reprocesa un backlog grande de ventanas si el directorio del anillo conserva PCAP rancios de sesiones previas (tcpdump `-W` solo gestiona los archivos de su propia corrida, no borra los anteriores). `build_rows()` usa `min(capture_epoch, min(observaciones))` como inicio, de modo que un solo PCAP viejo hace generar una ventana por cada paso de 10 s desde ese timestamp hasta ahora; el dedup por `(entidad, window_end)` evita el re-scoring dentro de una corrida, pero se re-emiten decisiones y se re-aplican bloqueos de ventanas ALERT antiguas. No es un bucle (cada ventana una vez) y los bloqueos expiran en 120 s, pero ensucia el arranque. **Mitigación operativa aplicada:** limpiar el anillo (`systemctl stop ppi-motor-capture` → borrar `live-*.pcap` → `start`) antes de reiniciar el motor deja un arranque limpio. **Mejora futura candidata (no implementada):** que `install-ppi-motor.sh`/el propio servicio de captura limpie PCAP rancios al arrancar, o que el motor acote el lookback por reloj además de por `min(observaciones)`. Queda registrada en `../07-mejoras-futuras/01-debilidades-y-mejoras.md`.
