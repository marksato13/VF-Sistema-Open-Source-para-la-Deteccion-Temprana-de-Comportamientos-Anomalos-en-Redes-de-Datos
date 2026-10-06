# Mejora propuesta: robustez del heurístico `port_scan`

**Estado:** analizado y validado en FPR (offline). **Implementación + despliegue
PENDIENTES de tu OK** (cambia el enforcement en vivo).

## Problema
`port_scan` disparó solo **1/3** en la batería (nota 26 de orquestación): un
escaneo corto (~17 s) no siempre cumple las 3 condiciones en una ventana de 30 s.

## Causa raíz (medida 2026-10-06, escaneo real de 17,8 s)
Extraídas las features del escaneo por ventana (`nmap -sT -p 1-1000`):

| Ventana | flow_attempt_30s | unique_dst_port_ratio_30s | syn_completion_10s | ¿port_scan? |
|---|---|---|---|---|
| borde | 6 (<20 ❌) | 0,75 | 0,00 | no |
| pico | 2007 (✓) | **0,50** | 0,00 | **sí** |

- La ventana **pico** (donde cae el grueso del escaneo) **sí dispara**.
- Fragilidad: `unique_dst_port_ratio_30s` queda **bordeando 0,45–0,50**. El espejo
  SPAN **duplica cada trama**, así que la unicidad topa en ~0,5; si en una
  repetición la ventana pico baja de 0,45, **falla** aunque sea obviamente un
  escaneo (miles de intentos, 0 % completados). Eso explica el 1/3.

## Fix propuesto (principiado, no "aflojar umbrales")
Añadir a `_port_scan` una **condición OR para ráfagas masivas de baja completitud**,
que no dependa del ratio distorsionado por el espejo:

```
dispara si:
   (flow_attempt_count_30s >= 20  y  unique_dst_port_ratio_30s >= 0.45  y  syn_completion_ratio_10s <= 0.3)   # actual
   O
   (flow_attempt_count_30s >= 200  y  syn_completion_ratio_10s <= 0.1)                                         # NUEVO: ráfaga inequívoca
```
Una ventana con 200+ intentos de flujo y ~0 % de completitud es un escaneo sin
ambigüedad, pase lo que pase con la unicidad. Subir `VERSION_UMBRALES` a `2026-10-06.2`.

## Validación de FPR (offline, línea base completa = 712 450 ventanas)
| Regla | Ventanas que disparan | FPR |
|---|---|---|
| port_scan ACTUAL | 78 | 0,011 % |
| OR candidata sola (flow≥200 & syn≤0,1) | 80 | 0,011 % |
| **COMBINADO (actual OR nueva)** | **83** | **0,012 %** |

→ La condición OR añade **+5 disparos en 712 450** ventanas: **neutra en FPR**. Y
sobre el escaneo medido, la ventana pico (2007, syn 0) la cumple → disparo robusto.

## Plan de despliegue (GATED — necesita tu OK)
1. Editar `scripts/engine/heuristicos.py` (`_port_scan` + `VERSION_UMBRALES=2026-10-06.2`).
2. `py_compile` + `unittest` local (añadir caso: ráfaga masiva dispara aunque uratio<0,45).
3. `scp` al sensor + `sudo -n systemctl restart ppi-motor` (es NOPASSWD).
4. Re-correr la batería de escaneo para confirmar **3/3** y FPR estable.

Nada de esto se ha tocado aún en el producto desplegado. Di "adelante con el fix de
port_scan" y lo implemento, pruebo y despliego con esos gates.
