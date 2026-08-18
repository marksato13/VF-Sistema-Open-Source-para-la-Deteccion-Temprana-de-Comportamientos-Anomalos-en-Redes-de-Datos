# Diseño del dashboard operativo del motor — arquitectura, instalación y manual de usuario

- **Fecha:** 2026-08-18
- **Estado:** desplegado y validado end-to-end contra datos reales en VM02.
- **Alcance confirmado:** sistema en vivo completo (decisiones del motor,
  estado de enforcement, salud de servicios, contexto del modelo), estrictamente
  de solo lectura, complementario a otras herramientas de monitoreo — no las
  reemplaza ni intenta ser un panel de control completo.

## Por qué existe

El motor y el enforcement ya corren de forma autónoma en VM02
(`docs/06-features-modelado/09-diseno-motor-tiempo-real.md`), pero su única
salida visible hasta ahora es un archivo JSONL (`motor_decision.log`) y
comandos SSH puntuales (`ppi-enforce status <ip>`, `journalctl`). Este
dashboard da una vista humana de ese estado sin sustituir esas herramientas:
sigue siendo posible (y necesario para depuración profunda) usar SSH,
`journalctl` y el helper directamente.

Ya existe `dashboard/app.py`, pero es un panel distinto: muestra estadísticas
del **dataset** consolidado (filas, particiones, rangos de features), lee un
CSV estático y corre en VM01. Este dashboard nuevo es sobre el **sistema en
vivo** (motor + enforcement + servicios) y corre en VM02, porque ahí es donde
vive esa información real. Son dos paneles con propósitos distintos; no se
fusionan para no complicar ninguno de los dos.

## Decisiones de arquitectura y por qué

| Decisión | Elegido | Por qué |
|---|---|---|
| Dónde corre | VM02 (Sensor) | Ahí están el log, el estado de nftables y los servicios reales. Consultarlos desde VM01 exigiría SSH en cada carga de página — más lento, más fragil, y expondría uso de la llave SSH a un proceso web. |
| Cómo se accede | Túnel SSH desde VM01, sin exponer el puerto | Mismo criterio de seguridad ya documentado en `dashboard/README.md`: nunca exponer estos puertos a la red externa. |
| Tecnología | Python estándar (`http.server`), sin dependencias nuevas | VM02 está aislada de internet (ya costó una tarde instalar `python3.14-venv` y las wheels de scikit-learn offline). Agregar Flask+SSE repetiría ese esfuerzo para una ganancia marginal (actualización push en vez de polling). El dashboard de dataset ya usa este mismo patrón; se mantiene consistencia. |
| Actualización | Polling cada 5 s desde el navegador (`fetch`) | Suficiente para un panel de monitoreo (no es un terminal de trading). Más robusto que SSE sobre un túnel SSH, que necesita lógica de reconexión si el túnel parpadea. |
| Intérprete | `/usr/bin/python3` del sistema, NO el venv del motor | El dashboard no necesita `joblib`/`scikit-learn`/`numpy` — solo librería estándar. Usar el venv del motor sería una dependencia innecesaria; el dashboard puede fallar o reiniciarse sin afectar al proceso de scoring, y viceversa. |
| Interactividad | Estrictamente de solo lectura | Decisión explícita del usuario: es complementario, no reemplaza otras herramientas. Cualquier acción (desbloquear una IP, reiniciar un servicio) se sigue haciendo por SSH, como ahora. Evita además la superficie de riesgo de exponer un endpoint que ejecuta acciones sin autenticación. |
| Privilegios nuevos | Ninguno | Todas las fuentes de datos ya son legibles por `useransible` sin sudo (`motor_decision.log`, `systemctl is-active`) o ya están cubiertas por el sudoers existente (`useransible-ppi-enforce.sudoers` autoriza `ppi-enforce *`, un comodín que ya cubre el nuevo subcomando `list` que se agrega). No hace falta ninguna línea sudoers nueva ni acceso root para operar, solo para instalar la unidad systemd una vez. |

## Fuentes de datos y cómo se leen

1. **Decisiones del motor** — cola del archivo `motor_decision.log` (JSONL).
   No se relee el archivo completo en cada request (puede crecer varios MB
   en una corrida larga, como ya pasó una vez): se busca desde el final del
   archivo (`seek` hacia atrás) y se toman solo las últimas ~200 líneas.
2. **Estado de enforcement** — nuevo subcomando `ppi-enforce list`, que lista
   todos los elementos actuales del set nftables `blocked_ips` (IP + tiempo
   restante) en JSON, vía `nft -j list set`. No agrega privilegios: es una
   acción de solo lectura dentro del mismo helper ya autorizado.
3. **Salud de servicios** — `systemctl is-active ppi-motor.service
   ppi-motor-capture.service suricata.service`, sin sudo (polkit permite
   consultas de estado a cualquier usuario local).
4. **Contexto del modelo** — se lee una sola vez al arrancar el archivo
   `manifest.json` ya desplegado (`/home/useransible/ppi-motor-model/manifest.json`,
   el mismo que usa el motor para el umbral): nombre del detector, umbral,
   y las métricas de la evaluación bloqueada ya calculadas (`test.fpr`,
   `anomalies.detection_rate`, `anomalies.kali_real_detection_rate`,
   desglose por familia de ataque). Nada se recalcula ni se vuelve a
   evaluar; es el mismo número congelado que ya está documentado en
   `08-modelo-final-congelado-ocsvm.md`.

## Endpoints

- `GET /` — página HTML única (sin build step, sin frontend framework).
- `GET /api/status` — JSON: salud de servicios, contexto del modelo,
  IPs bloqueadas actuales, contadores agregados (decisiones en la última
  hora: total, ALERT, PERMIT-modelo, PERMIT-heurístico).
- `GET /api/decisions?limit=200` — últimas N decisiones crudas, para la
  tabla de actividad reciente.

## Qué NO hace (límites declarados, no ocultos)

- No dispara ninguna acción (bloquear, desbloquear, reiniciar servicios).
- No reemplaza `journalctl` para depuración de errores del proceso —
  solo expone decisiones y estado, no trazas de error completas.
- No persiste histórico más allá de lo que ya vive en `motor_decision.log`;
  no es un sistema de series temporales (no hay Prometheus/Grafana aquí).
- No se expone fuera de VM02; el acceso remoto es responsabilidad del
  túnel SSH que arma quien lo use, igual que el dashboard de dataset.

## Instalación (manual de despliegue)

Requiere haber desplegado ya el motor (`09-diseno-motor-tiempo-real.md`).
No requiere acceso root nuevo salvo para el paso 1 (instalar la unidad
systemd una única vez):

```bash
# 1. (root, una sola vez) instalar la unidad systemd
sudo install -m 0644 configs/sensor/ppi-dashboard.service /etc/systemd/system/ppi-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now ppi-dashboard.service

# 2. Verificar que responde localmente en VM02
curl -s http://127.0.0.1:8788/api/status | head -c 300
```

Acceso remoto desde VM01 (o tu máquina), vía túnel SSH — nunca exponer el
puerto directamente:

```bash
ssh -N -L 8788:127.0.0.1:8788 useransible@10.10.10.20
# luego abrir http://127.0.0.1:8788/ en el navegador local
```

## Manual de usuario

La página tiene cuatro secciones, de arriba hacia abajo:

1. **Salud del sistema** — tres tarjetas (motor, captura, Suricata) en
   verde/rojo según `systemctl is-active`. Si alguna está en rojo, el
   motor no está observando tráfico real; revisar con
   `journalctl -u ppi-motor.service -f` por SSH.
2. **Modelo congelado** — nombre del detector, umbral operativo, y las
   métricas de la evaluación bloqueada (FPR benigno, detección global,
   detección Kali-real). Estos números son fijos: no cambian mientras el
   modelo siga congelado, se muestran aquí solo como contexto de lectura.
3. **IPs bloqueadas ahora** — tabla vacía la mayor parte del tiempo (es lo
   esperado en un laboratorio sin tráfico ofensivo activo). Cada fila
   muestra la IP y el tiempo restante antes de que el bloqueo expire solo.
4. **Actividad reciente** — las últimas decisiones del motor, más nueva
   arriba, con la IP, el score (si aplica), el umbral y si fue `ALERT` o
   `PERMIT` (y si fue por el modelo o por el heurístico de ventana vacía).

La página se actualiza sola cada 5 segundos; no hace falta recargar.

## Validación real (2026-08-18)

Desplegado con acceso root temporal (mismo patrón ya usado para el motor y
el enforcement, revocado y verificado al cerrar). El único punto que no se
pudo probar sin la infraestructura real —el filtro `jq` sobre la salida
`nft -j list set`— funcionó correctamente a la primera contra el set real,
tanto vacío como con contenido.

Prueba end-to-end completa: generé una ráfaga de ping real desde el cliente,
el motor la marcó `ALERT` y bloqueó la IP automáticamente, y **el dashboard
mostró esa IP bloqueada con su tiempo de expiración exacto** vía
`GET /api/status`, sin intervención manual. `/api/decisions` devolvió el
registro correcto en orden cronológico inverso. Los tres servicios
(`ppi-motor`, `ppi-motor-capture`, `suricata`) y las métricas del modelo
(umbral `1.8126`, FPR `4.71%`, detección `88.3%`/`88.9%` Kali-real)
coincidieron exactamente con los valores ya documentados en
`08-modelo-final-congelado-ocsvm.md`, confirmando que se leen del
`manifest.json` real y no están hardcodeados.

Bug encontrado y corregido **antes** de desplegar (durante el smoke test
local, no en producción): `load_model_summary` asumía
`manifest["evaluation"]["threshold_used"]` plano, pero el manifiesto real
indexa `evaluation` por nombre de detector
(`manifest["evaluation"]["ocsvm_scaled"]["threshold_used"]`). Verificado
también contra el `manifest.json` real de `/srv/ppi-evidence` antes de
tocar VM02.
