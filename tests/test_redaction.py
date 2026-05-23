from app.infra.redaction import redact_payload, redact_text


def test_redact_text_hides_secret_patterns():
    sample = (
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def "
        "token=sk-1234567890abcdef "
        "github=ghp_1234567890abcdef1234 "
        "password=supersecret"
    )

    redacted = redact_text(sample)

    assert "sk-1234567890abcdef" not in redacted
    assert "ghp_1234567890abcdef1234" not in redacted
    assert "supersecret" not in redacted
    assert redacted.count("[REDACTED]") >= 3


def test_redact_payload_handles_nested_fields():
    payload = {
        "authorization": "Bearer abcdef",
        "nested": {"password": "hello", "notes": "token=abc"},
        "storage": {"minio_access_key": "minioadmin", "minio_secret_key": "supersecret"},
        "items": ["sk-1234567890abcdef", {"secret": "keep out"}],
    }

    redacted = redact_payload(payload)

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["notes"] == "token=[REDACTED]"
    assert redacted["storage"]["minio_access_key"] == "[REDACTED]"
    assert redacted["storage"]["minio_secret_key"] == "[REDACTED]"
    assert redacted["items"][0] == "[REDACTED]"
    assert redacted["items"][1]["secret"] == "[REDACTED]"

