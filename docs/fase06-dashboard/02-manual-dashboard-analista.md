# Manual del dashboard — para quien lo usa (analista)

- **Fecha:** 2026-08-18
- **Para quién es:** alguien que necesita *observar* el sistema en vivo, sin instalarlo ni operarlo. Si necesitas desplegarlo o entender cómo se construyó, ver `docs/07-mejoras-futuras/02-manual-sistema-completo.md`.

## Qué es

Un panel web de solo lectura que muestra, en tiempo casi real, qué está haciendo el motor de detección: qué decisiones tomó, si bloqueó alguna IP, y si los servicios están sanos. Se actualiza solo cada 5 segundos. **No permite hacer nada** — ni bloquear, ni desbloquear, ni reiniciar servicios. Es un complemento a otras herramientas (SSH, `journalctl`), no un reemplazo.

## Cómo entrar

El dashboard corre en el Sensor (VM02) y solo escucha en su propia máquina, nunca expuesto directamente. Para verlo, abre un túnel:

```bash
ssh -N -L 8788:127.0.0.1:8788 useransible@10.10.10.20
```

Deja esa terminal abierta y entra a `http://127.0.0.1:8788/` en tu navegador.

## Qué significa cada sección

### Franja de estado (arriba de todo)

Lo primero que debes mirar. Tres estados posibles:
- 🟢 **Verde** — todo normal: servicios activos, sin alertas reales en la última hora, sin pérdida de paquetes.
- 🟡 **Ámbar** — hubo alertas reales recientes, o Suricata está perdiendo paquetes (revisa la tarjeta de "Drops de captura" más abajo — si hay drops, las features que calcula el motor pueden estar incompletas mientras eso ocurra).
- 🔴 **Rojo** — un servicio no está activo. El motor puede no estar observando tráfico ahora mismo; esto sí requiere atención por SSH.

### Salud del sistema

Tres servicios (Motor, Captura, Suricata) más dos tarjetas de Suricata: paquetes capturados y drops de captura. Un dato importante: "activo" solo significa que el proceso vive, no que esté procesando todo el tráfico sin pérdida — por eso los drops se muestran aparte.

### Modelo congelado

Contexto fijo sobre el modelo que está tomando las decisiones: qué umbral usa y sus métricas ya medidas (FPR, detección). Estos números no cambian mientras el modelo siga congelado — no se recalculan aquí. Debajo hay una nota fija con el punto débil conocido del modelo (fuerza bruta de contraseñas) — tenla presente antes de confiar ciegamente en un `PERMIT` en ese tipo de tráfico.

### Actividad

Contadores de la última hora, separados por qué los produjo: el modelo (`ALERT (modelo)`), el heurístico de fuerza bruta (`ALERT (fuerza bruta)`), y los dos tipos de `PERMIT`. El gráfico de barras debajo (última hora / últimas 24h, con el botón) muestra de un vistazo si hay más actividad de lo normal: rojo = ese intervalo tuvo al menos un `ALERT`, verde = solo tráfico normal, gris = sin tráfico.

### IPs bloqueadas ahora

Vacía casi todo el tiempo en un laboratorio sin ataques activos — eso es lo esperado. Cada bloqueo expira solo (columna "Expira en"), no hace falta desbloquear nada manualmente.

### Distribución de scores recientes

Responde una pregunta distinta a "¿alertó o no?": *qué tan cerca del umbral* está pasando el tráfico. La línea marcada es el umbral operativo. Barras rojas = por debajo del umbral (zona de alerta), ámbar = cruzan el umbral, verde = claramente por encima (zona normal). Útil para notar tráfico "al límite" que hoy pasa como `PERMIT` pero podría no hacerlo si el umbral cambiara.

### Decisiones recientes

La tabla con el detalle. Dos herramientas encima:
- **Filtrar por IP** — escribe parte de una IP y la tabla se reduce a esa IP en el momento, sin recargar nada.
- **Exportar CSV** — descarga lo que ves actualmente (respeta el filtro si hay uno activo) como un archivo `.csv`, útil para adjuntar a un reporte de incidente.

La columna "Motivo" te dice cuál de los dos detectores decidió: el modelo (OCSVM) o el heurístico de fuerza bruta o de ventana vacía.

### Si la pestaña no está abierta

Si cambias a otra pestaña y llega un `ALERT` real, el título de esta pestaña cambia a `(N) Sistema PPI` y el ícono se marca con un punto rojo, hasta que vuelvas a mirarla.

## Preguntas frecuentes

**¿Por qué la tarjeta de servicios dice "activo" pero no veo decisiones nuevas?**
Puede que simplemente no haya tráfico real en ese momento — el motor no inventa actividad. Revisa el histograma y el sparkline: si están vacíos, es silencio de red genuino.

**¿Puedo desbloquear una IP desde aquí?**
No — es intencional. Usa `sudo /usr/local/sbin/ppi-enforce unblock <ip>` por SSH.

**¿Los números del histograma o el sparkline "24h" están completos si el sistema lleva menos de un día corriendo?**
No fingen datos: si el log no llega tan atrás, esos intervalos simplemente aparecen vacíos, no se rellenan con nada inventado.
