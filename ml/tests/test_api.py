from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_categorize_batch():
    res = client.post(
        "/categorize",
        json={"descriptions": ["SHELL OIL 5521", "UBER EATS ORDER 8841", "ZZZ UNKNOWN"]},
    )
    assert res.status_code == 200
    preds = res.json()["predictions"]
    assert [p["category"] for p in preds] == ["Gas", "Dining", "Other"]
    assert preds[0]["source"] == "rules"
    assert preds[2]["matched"] is None


def test_empty_batch_rejected():
    assert client.post("/categorize", json={"descriptions": []}).status_code == 422
