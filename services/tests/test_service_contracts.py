from fastapi.testclient import TestClient

from services.embedding.app import create_app as create_embedding_app
from services.ocr.app import create_app as create_ocr_app
from services.speech.app import create_app as create_speech_app


def test_embedding_service_contract_in_fake_mode() -> None:
    with TestClient(create_embedding_app(fake_mode=True)) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json()["ready"] is True

        response = client.post("/embed", json={"texts": ["数据分析岗位"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "BAAI/bge-m3"
    assert payload["dimensions"] == 1024
    assert len(payload["vectors"]) == 1
    assert len(payload["vectors"][0]) == 1024
    assert all(isinstance(value, float) for value in payload["vectors"][0])


def test_ocr_service_contract_in_fake_mode() -> None:
    with TestClient(create_ocr_app(fake_mode=True)) as client:
        assert client.get("/health/ready").json()["ready"] is True
        response = client.post(
            "/ocr",
            files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "掌握 Python 和 SQL"
    assert payload["pages"] == [
        {"page": 1, "text": "掌握 Python 和 SQL", "confidence": 0.98}
    ]


def test_speech_service_contracts_in_fake_mode() -> None:
    with TestClient(create_speech_app(fake_mode=True)) as client:
        assert client.get("/health/ready").json()["ready"] is True
        transcription = client.post(
            "/transcribe",
            files={"file": ("answer.webm", b"fake-webm", "audio/webm")},
        )
        synthesis = client.post(
            "/synthesize",
            json={"text": "请介绍你的项目经历", "language": "ZH"},
        )

    assert transcription.status_code == 200
    assert transcription.json() == {
        "text": "我完成了销售数据分析项目",
        "duration_seconds": 3.2,
        "model": "paraformer-zh",
    }
    assert synthesis.status_code == 200
    assert synthesis.headers["content-type"].startswith("audio/wav")
    assert synthesis.content.startswith(b"RIFF")
