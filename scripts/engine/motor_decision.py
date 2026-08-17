#!/usr/bin/env python3
"""Motor de decision en tiempo real (fase de solo lectura, sin enforcement).

Reusa directamente las funciones del extractor congelado
``scripts/features/extract_multilayer_v2.py`` (``load_packet_observations``,
``load_app_observations``, ``build_rows``) en vez de reimplementar las 28
formulas de features. Esta es la leccion explicita que se tomo del MVP
anterior, donde el motor y el entrenamiento duplicaron manualmente la logica
de extraccion y podian desincronizarse; ver
docs/06-features-modelado/06-protocolo-modelado-multilayer-v2-y-hoja-de-ruta.md.

Arquitectura de entrada, distinta a una campana offline:

- PCAP: ``ppi-motor-capture.service`` mantiene un buffer en anillo de
  archivos rotados por tiempo (``-G 15 -W 8`` => ~120s de historia) en
  ``--capture-dir``. Cada ciclo se listan los archivos YA CERRADOS (se
  excluye siempre el mas reciente, que tcpdump todavia esta escribiendo) y
  se pasan tal cual a ``load_packet_observations`` -- sin reimplementar el
  parseo PCAP.
- EVE: Suricata escribe un unico ``eve.json`` continuo. Como
  ``load_app_observations`` espera un archivo completo (no soporta tail
  incremental), este script mantiene en memoria las lineas EVE de los
  ultimos ``--history-seconds`` segundos (por timestamp del propio evento,
  reusando ``parse_eve_timestamp`` del extractor) y las vuelca cada ciclo a
  un archivo temporal que SI se pasa a ``load_app_observations`` sin tocar
  su logica interna.

Limitacion conocida y declarada, no oculta: a diferencia de una campana
offline (PCAP completo desde el primer paquete del episodio),
``attribute_packets`` solo ve el buffer en anillo de ~120s. Un flujo que ya
llevaba mas de ~120s abierto cuando el motor lo observa por primera vez
puede tener su IP iniciadora mal atribuida si el paquete que abrio el flujo
ya rotó fuera del buffer. Para flujos cortos (la inmensa mayoria del trafico
de ataque real medido en la evaluacion bloqueada) esto no aplica.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "features"))

import extract_multilayer_v2 as extractor  # noqa: E402

try:
    import joblib
except ImportError as exc:  # pragma: no cover - fallo de despliegue, no de logica
    raise SystemExit(
        "falta joblib/scikit-learn en este interprete; usar el venv congelado "
        "creado por configs/sensor/install-ppi-motor.sh (requirements-model.txt)"
    ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eve-path", type=Path, default=Path("/var/log/suricata/eve.json"))
    parser.add_argument("--capture-dir", type=Path, default=Path("/var/lib/ppi-motor-capture"))
    parser.add_argument("--capture-glob", default="live-*.pcap")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument(
        "--manifest-path",
        type=Path,
        help="manifest.json de la calibracion congelada; si se omite, se busca "
        "manifest.json junto a --model-path",
    )
    parser.add_argument("--detector-name", default="ocsvm_scaled")
    parser.add_argument(
        "--schema",
        type=Path,
        default=REPO_ROOT / "configs/features/multilayer-v2.json",
    )
    parser.add_argument("--entity-network", default="10.20.0.0/24")
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--step-seconds", type=int, default=10)
    parser.add_argument("--history-seconds", type=int, default=110)
    return parser.parse_args()


def load_threshold(manifest_path: Path, detector_name: str) -> float:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    detector = manifest["detectors"][detector_name]
    comparison = detector["calibration"]["comparison"]
    if comparison != "score < threshold":
        raise ValueError(
            f"regla de comparacion inesperada en el manifiesto: {comparison!r}"
        )
    return float(detector["calibration"]["threshold"])


class EveTail:
    """Tail incremental de eve.json con deteccion de rotacion/truncamiento."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._offset = 0
        self._inode: tuple[int, int] | None = None
        self._partial = b""

    def poll(self) -> list[str]:
        try:
            stat_result = self.path.stat()
        except FileNotFoundError:
            return []
        current_inode = (stat_result.st_dev, stat_result.st_ino)
        if self._inode is not None and current_inode != self._inode:
            self._offset = 0
            self._partial = b""
        self._inode = current_inode
        if stat_result.st_size < self._offset:
            self._offset = 0
            self._partial = b""

        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
            self._offset = handle.tell()

        data = self._partial + chunk
        parts = data.split(b"\n")
        self._partial = parts[-1]
        return [raw.decode("utf-8", errors="replace") for raw in parts[:-1] if raw.strip()]


def list_closed_pcap_files(capture_dir: Path, pattern: str) -> list[Path]:
    files = sorted(capture_dir.glob(pattern))
    return files[:-1] if len(files) > 1 else []


def main() -> int:
    args = parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    feature_names = tuple(
        item["name"] for item in sorted(schema["features"], key=lambda item: item["order"])
    )
    if feature_names != extractor.FEATURE_NAMES:
        raise SystemExit("el esquema de features no coincide con el extractor importado")

    manifest_path = args.manifest_path or (args.model_path.parent.parent / "manifest.json")
    threshold = load_threshold(manifest_path, args.detector_name)
    pipeline = joblib.load(args.model_path)

    import ipaddress

    entity_network = ipaddress.ip_network(args.entity_network)

    state_dir = args.state_dir or (args.log_path.parent / "_state")
    state_dir.mkdir(parents=True, exist_ok=True)
    eve_slice_path = state_dir / "eve_window.jsonl"

    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    tail = EveTail(args.eve_path)
    eve_buffer: collections.deque[tuple[float, str]] = collections.deque()
    scored_windows: dict[tuple[str, str], float] = {}

    startup_record = {
        "event": "motor_startup",
        "timestamp": time.time(),
        "model_path": str(args.model_path),
        "manifest_path": str(manifest_path),
        "detector_name": args.detector_name,
        "threshold": threshold,
        "entity_network": str(entity_network),
        "capture_dir": str(args.capture_dir),
        "eve_path": str(args.eve_path),
        "step_seconds": args.step_seconds,
        "history_seconds": args.history_seconds,
    }
    with args.log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(startup_record, sort_keys=True) + "\n")
    print(json.dumps(startup_record, sort_keys=True), flush=True)

    while True:
        cycle_start = time.time()

        for raw_line in tail.poll():
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            timestamp_raw = event.get("timestamp")
            if not timestamp_raw:
                continue
            try:
                event_time = extractor.parse_eve_timestamp(timestamp_raw)
            except ValueError:
                continue
            eve_buffer.append((event_time, raw_line))

        cutoff = cycle_start - args.history_seconds
        while eve_buffer and eve_buffer[0][0] < cutoff:
            eve_buffer.popleft()
        for stale_key in [key for key, anchor in scored_windows.items() if anchor < cutoff]:
            del scored_windows[stale_key]

        with eve_slice_path.open("w", encoding="utf-8") as handle:
            for _, raw_line in eve_buffer:
                handle.write(raw_line + "\n")

        pcap_files = list_closed_pcap_files(args.capture_dir, args.capture_glob)

        if pcap_files or eve_buffer:
            packets = extractor.load_packet_observations(pcap_files, entity_network) if pcap_files else []
            apps = (
                extractor.load_app_observations(eve_slice_path, entity_network)
                if eve_buffer
                else []
            )
            rows = extractor.build_rows(
                "motor-live", packets, apps, step_seconds=args.step_seconds
            )

            for row in rows:
                window_key = (str(row["entity_ip"]), str(row["window_end_utc"]))
                if window_key in scored_windows:
                    continue
                if not row["eligible_training"]:
                    continue
                scored_windows[window_key] = extractor.parse_eve_timestamp(row["window_end_utc"])

                feature_vector = [[float(row[name]) for name in feature_names]]
                score = float(pipeline.score_samples(feature_vector)[0])
                decision = "ALERT" if score < threshold else "PERMIT"

                record = {
                    "event": "decision",
                    "logged_at": time.time(),
                    "entity_ip": row["entity_ip"],
                    "window_end_utc": row["window_end_utc"],
                    "history_coverage_s": row["history_coverage_s"],
                    "packet_count_10s": row["packet_count_10s"],
                    "detector_name": args.detector_name,
                    "score": score,
                    "threshold": threshold,
                    "decision": decision,
                }
                with args.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
                if decision == "ALERT":
                    print(json.dumps(record, sort_keys=True), flush=True)

        elapsed = time.time() - cycle_start
        time.sleep(max(0.5, args.step_seconds - elapsed))


if __name__ == "__main__":
    raise SystemExit(main())
