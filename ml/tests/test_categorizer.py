"""Model + rules combination. The tiny model here is trained on invented data to test the
wiring (precedence, fallback, bad files), not accuracy."""
import joblib
import pytest
import sklearn
from fastapi.testclient import TestClient

import app as app_module
import train
from categorizer import Categorizer

TRAIN = [("PIZZERIA ROMA", "Dining"), ("SUSHI BAR GINZA", "Dining"), ("NOODLE HOUSE TOKYO", "Dining"),
         ("BOOKSTORE CENTRAL", "Shopping"), ("BOUTIQUE LUNA", "Shopping"), ("SHOE STORE METRO", "Shopping")]


@pytest.fixture
def model_path(tmp_path):
    pipeline = train.build_pipeline().fit([t for t, _ in TRAIN], [c for _, c in TRAIN])
    path = tmp_path / "model.joblib"
    joblib.dump({"pipeline": pipeline, "labels": ["Dining", "Shopping"], "sklearn": sklearn.__version__}, path)
    return str(path)


def test_without_model_file_uses_rules_only(tmp_path):
    cat = Categorizer(str(tmp_path / "missing.joblib"))
    assert not cat.model_loaded
    out = cat.predict(["SHELL OIL 55", "ZZZ UNKNOWN"])
    assert [(r["category"], r["source"]) for r in out] == [("Gas", "rules"), ("Other", "rules")]


def test_rules_match_wins_and_model_fills_gaps(model_path):
    cat = Categorizer(model_path)
    assert cat.model_loaded
    shell, pizza = cat.predict(["SHELL OIL 55", "PIZZERIA NAPOLI"])
    assert (shell["category"], shell["source"], shell["confidence"]) == ("Gas", "rules", None)
    assert pizza["source"] == "model" and pizza["category"] == "Dining"
    assert 0 < pizza["confidence"] <= 1


def test_low_confidence_falls_back_to_other(model_path):
    cat = Categorizer(model_path, threshold=1.01)  # impossible to reach
    (out,) = cat.predict(["PIZZERIA NAPOLI"])
    assert (out["category"], out["source"]) == ("Other", "rules")
    assert out["confidence"] is not None


def test_corrupt_model_file_does_not_crash(tmp_path):
    bad = tmp_path / "bad.joblib"
    bad.write_bytes(b"not a model")
    cat = Categorizer(str(bad))
    assert not cat.model_loaded
    assert cat.predict(["SHELL OIL"])[0]["category"] == "Gas"


def test_endpoint_reports_model(model_path, monkeypatch):
    monkeypatch.setattr(app_module, "categorizer", Categorizer(model_path))
    client = TestClient(app_module.app)
    assert client.get("/healthz").json() == {"status": "ok", "model_loaded": True}
    body = client.post("/categorize", json={"descriptions": ["PIZZERIA NAPOLI"]}).json()
    assert body["predictions"][0]["source"] == "model"
