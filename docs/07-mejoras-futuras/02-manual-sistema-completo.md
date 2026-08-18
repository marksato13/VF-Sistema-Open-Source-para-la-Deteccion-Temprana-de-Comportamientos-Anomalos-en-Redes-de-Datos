# Manual del sistema completo — instalación, operación y verificación

- **Fecha:** 2026-08-18
- **Para quién es:** quien instala, opera o necesita explicar/defender el sistema. Si solo necesitas *usar* el dashboard, ver `docs/fase06-dashboard/02-manual-dashboard-analista.md`.

## Qué es el sistema, en una frase

Un sensor inline (VM02) que captura tráfico real entre la LAN y la DMZ, calcula 28 características por ventana de 10 segundos, las evalúa con un modelo de detección de anomalías ya entrenado y congelado, y bloquea automáticamente (vía nftables, con expiración propia) la IP que dispare una alerta real — con un panel web de solo lectura para observarlo todo.

Para el mapa visual completo (topología, fases de construcción, ciclo de decisión), ver los Artifacts publicados: "Arquitectura PPI", "Fases del proyecto PPI" y "Cómo funciona el motor PPI".

## Las piezas, y dónde está cada una documentada

| Pieza | Qué hace | VM | Documentación de diseño |
|---|---|---|---|
| Extractor de features | Calcula las 28 variables por ventana | (biblioteca, se importa) | `docs/fase02-features-multicapa/` |
| Modelo congelado (OCSVM) | Decide ALERT/PERMIT según el umbral calibrado | — (archivo `.joblib`) | `docs/fase04-modelado/` |
| `ppi-motor-capture.service` | Captura continua en anillo (~240s de historia) | VM02 | `docs/fase05-motor-tiempo-real/01-diseno-motor-tiempo-real.md` |
| `ppi-motor.service` | Extrae features en vivo, puntúa, aplica el heurístico de fuerza bruta, invoca el bloqueo | VM02 | igual que arriba |
| `ppi-enforce` (helper root) | Bloquea/desbloquea IPs vía nftables, con expiración nativa | VM02 | igual que arriba |
| `ppi-dashboard.service` | Panel web de solo lectura | VM02 | `docs/fase06-dashboard/01-diseno-dashboard-motor.md` |

## Instalación (resumen — ver cada documento de diseño para el detalle completo)

1. **Motor + captura**: `configs/sensor/install-ppi-motor.sh` (root, una sola vez). Instala las unidades systemd, crea el venv con las versiones exactas de `requirements-model.txt`, copia el modelo congelado verificando su hash.
2. **Enforcement**: `configs/sensor/ppi-enforce` se instala junto con el motor; no necesita pasos aparte.
3. **Dashboard**: instalar `configs/sensor/ppi-dashboard.service` (root, una sola vez) y `systemctl enable --now ppi-dashboard.service`.

Todos los pasos exactos, con los comandos reales ya probados, están en los documentos de diseño de la tabla de arriba — este manual no los repite para no desincronizarse si cambian.

## Modelo de acceso vigente

Desde el 2026-08-18, `useransible` tiene sudo permanente sin restricción en las cuatro VMs del laboratorio (decisión explícita del usuario, documentada en `docs/fase00-infraestructura/02-cambio-modelo-acceso-root-permanente.md`, incluida la recomendación de volver a un modelo de sudoers estrecho antes de la defensa final). Antes de esa fecha, cada cambio de infraestructura requería una concesión de acceso root temporal, revocada al terminar — ese patrón sigue documentado en cada despliegue anterior como evidencia de cómo se operó durante la mayor parte del desarrollo.

## Cómo verificar que el sistema está funcionando

```bash
# Servicios activos
ssh useransible@10.10.10.20 "systemctl is-active ppi-motor.service ppi-motor-capture.service ppi-dashboard.service suricata.service"

# Decisiones recientes (ver tambien el dashboard, mas legible)
ssh useransible@10.10.10.20 "tail -5 /home/useransible/ppi-motor-logs/motor_decision.log"

# Estado de enforcement (IPs bloqueadas ahora mismo)
ssh useransible@10.10.10.20 "sudo -n /usr/local/sbin/ppi-enforce list"

# Métricas reales de captura de Suricata (paquetes, drops)
ssh useransible@10.10.10.20 "sudo -n /usr/local/sbin/ppi-suricata-metrics"
```

Prueba positiva completa (recomendada tras cualquier cambio): generar una ráfaga de tráfico real desde el cliente (`/home/useransible/bin/ppi-run-benign ping 10 0.5` en VM05) y confirmar que aparece una decisión nueva en el log/dashboard en menos de 20 segundos.

## Métricas del modelo, límites y trabajo futuro

No se repiten aquí — la fuente única de verdad es:
- `docs/fase04-modelado/06-modelo-final-congelado-ocsvm.md` (métricas del modelo)
- `docs/07-mejoras-futuras/01-debilidades-y-mejoras.md` (debilidades conocidas y qué se hizo/falta hacer con cada una)

## Siguiente paso pendiente

La validación final del sistema completo (motor + enforcement activos, múltiples corridas reales midiendo FPR operativo, latencia, disponibilidad y lead-time de detección) — equivalente a la fase F6 del MVP anterior. No hay fecha fijada todavía; queda pendiente de que el usuario confirme la escala (número de corridas, duración).
