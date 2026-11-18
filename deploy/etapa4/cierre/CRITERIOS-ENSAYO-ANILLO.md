# Ensayo `ring-size: 16384` en Suricata: criterios declarados ANTES de medir (cierre 4A, 4-nov-2026)

These criteria are fixed before the change is applied. They are not adjusted afterwards. The trial interval is not repeated in search of a favourable result.

## Hypothesis and limits

- **Hypothesis.** Part of the drops in `capture.kernel_drops` comes from bursts that overflow the AF_PACKET ring of each worker. Today the ring is the default size, because `ring-size` is not set.
- **What the base data show.** In the 4A, the drops (7 in 1 interval) coincided with large flows. That is a **correlation**. It does not prove the cause.
- **What has not been ruled out.** CPU, disk I/O, softirq/NIC and memory pressure. They have not been measured at enough resolution. `ps %CPU` is a lifetime average, and disk usage is not I/O latency. This trial measures them at 1 s resolution (`muestreo_fino.py`).
- **What one hour cannot do.** It cannot prove or refute the hypothesis. Background today is about 1.2 drop episodes per hour (7 episodes between 00:00 and 05:55 on 04-nov). Seeing 0 in 1 h is compatible both with "the change fixes it" and with "chance". The verdict is therefore stated only as **compatible / not compatible / insuficiente**.

## Single change

- `af-packet[ens37].ring-size: 16384`.
- Nothing else changes: no threads, no `use-mmap`, no `tpacket-v3`, no `block-size`, no NIC offloads, no NIC rings, no `rmem`.
- Prerequisite: Suricata must already use an mmap ring (`socket:` mappings in `/proc/<pid>/maps`). Otherwise the change is not made.
- Expected memory: about 16384 frames × frame size per worker. The real figure is read from `maps` before and after.

## Windows

- **Start (T0).** The moment Suricata is active after the restart (`t-restart-suricata.txt` plus "Engine started").
- **Warm-up.** 10 min (T0 → T0+600 s). This is more than the 230 s horizon of the motor's history plus margin, and allows Suricata's flow table to rebuild. It is reported separately. It does not count as observation.
- **Observation.** Fixed window of 60 min, from T0+600 s to T0+4200 s. It is not cut or moved to avoid incidents. If anything falls inside it, it is recorded in that window.
- **EVE gap.** From the last EVE event before the restart to the first one after it. It is measured and reported. It is not filled in.
- **Counters.** Segmented by process: when uptime drops, it is a restart, and the increment that crosses it is not used (`comparar_suricata.py`, `clasificar_periodo.py`).

## Comparison with the base (same method, `comparar_suricata.py`)

The main base is the 4A window, 02:19:45–03:19:51:

| Measure | Base value |
|---|---|
| Packets | 936,761 |
| Drops | 7 (7.473 per million) |
| Intervals with drops | 1 |
| Packets per 8 s interval | p50 1856, p95 4306, max 7168 |
| Bursts ≥ 5000 per 8 s | 11 |
| Large flows (≥ 1000 packets) | 63 |

Context bases: 03-nov (987 per million, 155 episodes) and 04-nov 00:00–05:55 (159 per million, 7 episodes).

**Comparable load.** The trial window counts as comparable only if both hold:

- bursts ≥ 5000 per 8 s ≥ **9** (80 % of 11);
- large flows ≥ **50** (80 % of 63).

If either fails, the result is **insuficiente**, even with 0 drops. Zero drops under clearly lower load does not confirm the fix.

**Same profiles.** The same legitimate background generators as in the 4A, with no attacks. Intensity, volumes and bursts are recorded, not chosen.

## Rollback (restore the YAML backup and restart; both measurements are kept)

Restore if any of these happens:

1. `suricata -T` fails, either for the candidate or for the installed YAML. In that case nothing is installed, or the backup is restored immediately.
2. Suricata restarts on its own, stops being active, or its PID changes outside the controlled restart.
3. EVE stays frozen for more than 60 s after warm-up, or capture stops.
4. Errors appear in `suricata.log` about af-packet, ring or memory (allocation, mmap, "Unable to").
5. The host's `MemAvailable` drops below 1 GiB.
6. With comparable load, drops per million reach **≥ 2×** the 4A base (≥ 14.95 per million).

## Result classes (stated exactly as written)

- **compatible con la hipótesis.** Comparable load, drops per million clearly below the base, no rollback criterion met, and resources (CPU per thread, softirq, disk, memory) with no new saturation. This does **not** prove the cause.
- **no compatible.** Comparable load and drops per million ≥ the base, or drops that coincide with saturation of another resource (that is diagnosed before anything else is proposed).
- **insuficiente.** Load not comparable, incomplete coverage, or a failed or missing reading.

Whatever the result: **I5** still requires 0 drops in the 30 min before 4C; the main population is still **C0**; and nothing in this trial relaxes those criteria.
