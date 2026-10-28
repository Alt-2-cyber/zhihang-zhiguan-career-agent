from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from services.emotion.app import create_app


def _jpeg() -> bytes:
    image = Image.new("RGB", (64, 64), color=(120, 120, 120))
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def test_fake_emotion_service_contract() -> None:
    with TestClient(create_app(fake_mode=True)) as client:
        assert client.get("/health/ready").json()["ready"] is True
        response = client.post(
            "/emotion/analyze",
            files={"file": ("frame.jpg", _jpeg(), "image/jpeg")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["face_detected"] is True
        assert payload["face_boxes"] == [{"x": 0.25, "y": 0.12, "width": 0.5, "height": 0.76, "confidence": 0.8}]
        assert payload["confidence"] == 0.8
        assert payload["presentation_score"] == 80


def test_emotion_service_rejects_non_image() -> None:
    with TestClient(create_app(fake_mode=True)) as client:
        response = client.post(
            "/emotion/analyze",
            files={"file": ("frame.txt", b"not-an-image", "text/plain")},
        )
        assert response.status_code == 415
