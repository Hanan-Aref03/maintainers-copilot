from fastapi.testclient import TestClient

from model_server.app.main import app


def test_rule_classifier_and_ner_overlap():
    client = TestClient(app)

    classify_response = client.post(
        "/classify",
        json={"title": "BUG: crash on startup", "body": "The app crashes immediately", "model": "rule"},
    )
    assert classify_response.status_code == 200
    payload = classify_response.json()
    assert payload["label"] == "bug"
    assert payload["used_fallback"] is False
    assert payload["classifier_source"] == "rule"

    ner_response = client.post(
        "/ner",
        json={
            "text": "Contact dev@example.com, visit https://example.com, ping @maintainer.",
            "model": "rule",
        },
    )
    assert ner_response.status_code == 200
    entities = ner_response.json()["entities"]
    labels = [entity["label"] for entity in entities]
    texts = [entity["text"] for entity in entities]

    assert "EMAIL" in labels
    assert "URL" in labels
    assert "MENTION" in labels
    assert "dev@example.com" in texts
    assert "@example" not in texts


def test_model_server_health_exposes_fine_tuned_field():
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "fine_tuned_ready" in payload
