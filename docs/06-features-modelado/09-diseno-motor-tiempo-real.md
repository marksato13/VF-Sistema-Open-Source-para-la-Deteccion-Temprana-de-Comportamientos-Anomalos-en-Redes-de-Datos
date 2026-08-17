# Diseño del motor de decisión en tiempo real — bloqueo de infraestructura encontrado

- **Fecha:** 2026-08-17
- **Estado:** diseño definido, **ejecución bloqueada por permisos** — necesita tu decisión antes de continuar.

## Lo que ya está resuelto (sin bloqueos)

- **EVE continuo:** Suricata en VM02 ya corre `service_state=active` de forma permanente (58.5M paquetes procesados, cero drops), generando `/var/log/suricata/eve.json` sin interrupción. El motor puede hacer `tail -f` de este archivo tal cual, ahora mismo, sin cambios de infraestructura.
- **Reutilización del extractor:** revisé `scripts/features/extract_multilayer_v2.py` a fondo. Está bien factorizado — `attribute_packets()`, `load_app_observations()` y `build_rows()` son funciones puras e importables, no código enterrado dentro de un script de línea de comandos. El motor puede **importar y llamar exactamente estas funciones**, alimentándolas con un buffer continuo (últimos ~60-120s) en vez de un PCAP/EVE de campaña completa, sin reescribir ni una fórmula. Esto evita el error del MVP anterior (duplicación manual de la lógica de features entre entrenamiento y motor, con riesgo real de que se desincronicen).
- **Modelo congelado:** `ocsvm_scaled.joblib` ya está listo para cargar y puntuar (`08-modelo-final-congelado-ocsvm.md`).

## El bloqueo real: no existe captura de paquetes continua

Para calcular features a nivel de paquete (SYN, RST, TTL, fragmentación, retransmisión) el motor necesita PCAP en vivo, no solo EVE. Revisé el mecanismo de captura existente (`configs/sensor/ppi-pcap-control`, desplegado como helper raíz que `useransible` puede invocar vía sudo) y **es deliberadamente de una sola captura activa a la vez, por campaña** (`start|stop ID`, falla si ya hay una activa). Si el motor usara este mismo mecanismo de forma permanente, **bloquearía cualquier futura campaña del dataset** (y viceversa: iniciar una campaña pararía al motor).

Necesito un mecanismo de captura **separado**, exclusivo para el motor, corriendo en paralelo al de campañas. Eso implica:

1. Un nuevo servicio systemd en VM02 (`ppi-motor-capture.service` o similar) con `tcpdump` en rotación continua (buffer, tamaño de archivo y filtro similares a los ya calibrados: interfaz `ens35`, filtro LAN↔DMZ, snaplen completo, rotación acotada — mismos parámetros ya validados en `docs/05-plan-pruebas/11-diseno-captura-PCAP-G4.md`, solo que perpetuo en vez de por campaña).
2. Una nueva regla en el sudoers de `useransible` en VM02 para poder iniciar/detener/consultar ese servicio (el archivo actual, `configs/sensor/useransible-ppi-metrics.sudoers`, solo autoriza exactamente `ppi-suricata-metrics` y `ppi-pcap-control` — nada más, sin comodines).

**`useransible` no tiene sudo general en VM02** (confirmado, mismo patrón que bloqueó el fix de `/api/error` y el ajuste del servicio iperf3 anteriormente en este proyecto). Desplegar un servicio nuevo + una regla sudoers nueva requiere acceso root real en VM02, que no tengo.

## Lo que puedo hacer ahora mismo (sin permisos nuevos)

Puedo escribir y dejar listo, versionado en el repo, para que se despliegue en cuanto haya acceso:

1. `configs/sensor/ppi-motor-capture` — helper de captura continua (mismo estilo que `ppi-pcap-control`, rotación fija, sin parámetros abiertos).
2. Unidad systemd correspondiente.
3. La línea sudoers nueva a agregar al archivo ya versionado.
4. El motor de decisión mismo (`scripts/engine/motor_decision.py` o ubicación similar): tail de EVE + lectura de la rotación de PCAP del nuevo helper + `attribute_packets`/`build_rows` reusados + scoring con el `.joblib` congelado + logging de decisiones — todo esto **no necesita permisos nuevos para escribirse**, solo para desplegarse y ejecutarse de verdad contra tráfico en vivo.

## Lo que necesito de ti

Una de estas dos rutas:

1. **Conseguir acceso root temporal en VM02** (como se hizo para el fix de `/api/error` en VM03) para desplegar el helper + systemd + sudoers nuevos, dejándolo persistente — la vía "correcta" y ya usada varias veces en este proyecto.
2. **Alternativa sin cambios de infraestructura:** degradar el motor para que use *solo* EVE (sin PCAP en vivo) para el primer despliegue — Suricata's EVE `flow` events ya traen `pkts_toserver/toclient`, `bytes_toserver/toclient`, banderas TCP resumidas. Esto permitiría un motor funcional YA, pero **con una limitación real y declarada**: no sería exactamente el mismo camino de cálculo que se usó para entrenar el modelo (violaría el principio de "mismo código en train y en producción" que me propuse evitar) — features como TTL exacto, fragmentación real y detección de retransmisión por número de secuencia no están disponibles solo con EVE. Sería una aproximación, no una réplica fiel del modelo entrenado.

**Mi recomendación:** la opción 1. Es más trabajo de coordinación ahora, pero evita construir el motor sobre una aproximación que ya sé que es distinta al modelo que acabamos de congelar con tanto cuidado.

¿Cuál prefieres, o hay una tercera opción (por ejemplo, tú mismo aplicando los cambios de infraestructura por consola) que no estoy viendo?
