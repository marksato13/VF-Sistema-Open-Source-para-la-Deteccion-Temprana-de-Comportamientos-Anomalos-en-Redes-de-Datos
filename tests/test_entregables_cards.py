"""Regression checks for claims generated in the canonical cards."""
import json
from pathlib import Path

from scripts.entregables.generar_cards import model_card, system_card


REPO = Path(__file__).resolve().parents[1]


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_model_card_reports_internal_validation_and_no_stale_p95():
    manifest = json.loads((REPO / "artifacts/model/manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((REPO / "results/ablacion/validacion-cruzada-estabilidad.json").read_text(encoding="utf-8"))
    text = model_card(manifest, validation)
    assert "Se ejecutaron 5 pliegues" in text
    assert "mismas anomalías" in text
    assert "p95" not in text


def test_system_card_uses_median_range_and_qualifies_wilson():
    clean = _rows(REPO / "results/f6/f6_resultados.jsonl")
    pass1 = _rows(REPO / "results/f6/f6_resultados.pass1-contaminado.jsonl")
    text = system_card(clean, pass1)
    assert "mediana **8,0 s** · rango 6,1–13,7 s · `n = 8`" in text
    assert "no demuestra por sí solo" in text
    assert "p95" not in text
