#!/usr/bin/env python3
"""Ejecuta perfiles v2 de anomalía real (Kali) aislados de las particiones normales.

Variante de run_v2_anomaly.py: aquella orquesta escenarios ejecutados desde el
Cliente legítimo (VM05) con nombres relabeled como "anomaly" pero
traffic_class=benign en el manifiesto. Este script ejecuta tráfico realmente
ofensivo desde Kali (VM04) contra la DMZ autorizada, vía run-f1-kali.sh.
"""
from __future__ import annotations
import argparse, json, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = {
    "ANOM-KALI-SYN-RATE-50": ("tcp-syn-rate", ["50"], "syn_rate_10s,rst_ratio_10s,unique_dst_port_ratio_30s"),
    "ANOM-KALI-PORT-SCAN": ("tcp-port-scan", [], "unique_dst_port_ratio_30s,syn_completion_ratio_10s"),
    "ANOM-KALI-PORT-SCAN-WIDE": ("port-scan-wide", ["1-1000"], "unique_dst_port_ratio_30s,syn_rate_10s"),
    "ANOM-KALI-UDP-PROBE-50": ("udp-probe", ["50"], "packet_rate_10s,protocol_diversity_30s"),
    "ANOM-KALI-PASSWORD-SPRAY-50": ("password-spray", ["50"], "http_auth_failure_ratio_60s,http_request_rate_60s"),
    "ANOM-KALI-DNS-ENTROPY-50": ("dns-entropy", ["50"], "dns_nxdomain_ratio_60s,unique_dns_name_ratio_60s"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, choices=PROFILES)
    ap.add_argument("--episode", type=int, default=1)
    ap.add_argument("--attempt-suffix", default="B")
    args = ap.parse_args()
    if not 1 <= args.episode <= 99:
        raise SystemExit("episode debe estar entre 1 y 99")
    scenario, scenario_args, signals = PROFILES[args.profile]
    campaign_id = f"F2A-{args.profile}-E{args.episode:02d}-{args.attempt_suffix}"
    root = Path(os.environ.get("PPI_ARTIFACTS_ROOT", "/srv/ppi-evidence/artifacts")).resolve()
    campaign_dir = root / "campaigns" / campaign_id
    feature_dir = root / "features-v2" / campaign_id
    if campaign_dir.exists() or feature_dir.exists():
        raise SystemExit(f"ya existe evidencia: {campaign_id}")
    env = os.environ.copy()
    env.update(
        PPI_CAMPAIGN_PURPOSE="evaluation",
        PPI_CAMPAIGN_PHASE="F2",
        PPI_CAMPAIGN_WARMUP_SECONDS="60",
        PPI_CAMPAIGN_SETTLE_SECONDS="9",
        PPI_CAMPAIGN_PARTITION="evaluation_only",
        PPI_ARTIFACTS_ROOT=str(root),
    )
    cmd = [str(ROOT / "scripts/campaign/run-f1-kali.sh"), campaign_id, scenario, *scenario_args]
    print(
        json.dumps(
            {
                "campaign_id": campaign_id,
                "label": "anomaly",
                "partition": "evaluation_only",
                "source": "kali",
                "expected_signals": signals,
                "command": cmd,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    extractor = ROOT / "scripts/features/extract_campaign_v2.sh"
    subprocess.run([str(extractor), campaign_id], cwd=ROOT, env=env, check=True)
    manifest = campaign_dir / "manifest.json"
    data = json.loads(manifest.read_text())
    data.update(
        {
            "label": "anomaly",
            "evaluation_only": True,
            "expected_signals": signals,
            "anomaly_matrix": "multilayer-v2-anomalies-kali",
            "anomaly_source": "kali",
        }
    )
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    report = json.loads((feature_dir / "extraction-report.json").read_text())
    print(
        json.dumps(
            {"campaign_id": campaign_id, "status": data.get("status"), "rows": report.get("rows")},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
