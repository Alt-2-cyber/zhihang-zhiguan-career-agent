from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from threading import Lock, Thread
from typing import Any

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field

EMOTION_LABELS = {
    "angry": "愤怒",
    "disgust": "厌恶",
    "fear": "紧张",
    "happy": "积极",
    "neutral": "平稳",
    "sad": "低落",
    "surprise": "惊讶",
}


class FaceBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class EmotionObservation(BaseModel):
    face_detected: bool
    face_count: int = Field(ge=0)
    # Normalized coordinates keep the response independent of the uploaded frame size.
    face_boxes: list[FaceBox] = Field(default_factory=list, max_length=8)
    dominant_emotion: str = "unknown"
    dominant_emotion_label: str = "未识别"
    confidence: float = Field(ge=0, le=1)
    presentation_score: int | None = Field(default=None, ge=0, le=100)
    model: str
    device: str
    warning: str | None = None


class EmotionRuntime:
    def __init__(self, *, fake_mode: bool) -> None:
        self.fake_mode = fake_mode
        self.face_model_path = os.getenv("EMOTION_FACE_MODEL_PATH", "/models/yolov8n-face.pt")
        self.face_model_url = os.getenv(
            "EMOTION_FACE_MODEL_URL",
            "https://github.com/akanametov/yolo-face/releases/download/1.0.0/yolov8n-face.pt",
        )
        self.classifier_id = os.getenv(
            "EMOTION_CLASSIFIER_ID", "trpakov/vit-face-expression"
        )
        self.classifier_path = Path(
            os.getenv("EMOTION_CLASSIFIER_PATH", "/models/huggingface/vit-face-expression")
        )
        self.hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com").rstrip("/")
        self.hf_verify_ssl = os.getenv("EMOTION_HF_VERIFY_SSL", "0") == "1"
        requested_device = os.getenv("EMOTION_DEVICE", "cuda")
        self.device = requested_device if requested_device != "cuda" or self._cuda_available() else "cpu"
        self.face_detector: Any = None
        self.processor: Any = None
        self.classifier: Any = None
        self.ready = False
        self.error: str | None = None
        self.lock = Lock()

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _ensure_face_weights(self) -> None:
        target = Path(self.face_model_path)
        if target.is_file() and target.stat().st_size > 0:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        import requests

        temporary = target.with_suffix(target.suffix + ".part")
        with requests.get(self.face_model_url, stream=True, timeout=(20, 300)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        temporary.replace(target)

    def _ensure_classifier_files(self) -> Path:
        """Download the model files directly when Hub HEAD metadata is unavailable."""
        required = ("config.json", "preprocessor_config.json", "model.safetensors")
        self.classifier_path.mkdir(parents=True, exist_ok=True)
        import requests

        for filename in required:
            target = self.classifier_path / filename
            if target.is_file() and target.stat().st_size > 0:
                continue
            url = f"{self.hf_endpoint}/{self.classifier_id}/resolve/main/{filename}"
            temporary = target.with_suffix(target.suffix + ".part")
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    verify = self.hf_verify_ssl
                    offset = temporary.stat().st_size if temporary.exists() else 0
                    total: int | None = None
                    while True:
                        end = offset + 50 * 1024 * 1024 - 1
                        with requests.get(
                            url,
                            headers={"Range": f"bytes={offset}-{end}"},
                            stream=True,
                            timeout=(20, 900),
                            allow_redirects=True,
                            verify=verify,
                        ) as response:
                            response.raise_for_status()
                            content_range = response.headers.get("content-range", "")
                            match = re.match(r"bytes (\\d+)-(\\d+)/(\\d+)", content_range)
                            if match:
                                response_start, _, total_text = match.groups()
                                if int(response_start) != offset:
                                    raise RuntimeError(
                                        f"unexpected range start {response_start}, expected {offset}"
                                    )
                                total = int(total_text)
                            elif response.status_code == 200:
                                if offset:
                                    offset = 0
                                total = int(response.headers.get("content-length", "0")) or None
                            mode = "ab" if offset else "wb"
                            written = 0
                            with temporary.open(mode) as output:
                                for chunk in response.iter_content(chunk_size=1024 * 1024):
                                    if chunk:
                                        output.write(chunk)
                                        written += len(chunk)
                        if written == 0:
                            raise RuntimeError("empty model download response")
                        offset += written
                        if total is None or offset >= total:
                            break
                    temporary.replace(target)
                    break
                except Exception as error:
                    last_error = error
                    if temporary.exists():
                        temporary.unlink()
                    # The domestic mirror occasionally fails certificate negotiation.
                    if not self.hf_verify_ssl:
                        try:
                            import urllib3

                            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        except Exception:
                            pass
                    if attempt < 3:
                        import time

                        time.sleep(attempt * 2)
            else:
                raise RuntimeError(f"download failed for {filename}: {last_error}") from last_error
        return self.classifier_path

    def load(self) -> None:
        if self.ready:
            return
        if self.fake_mode:
            self.ready = True
            return
        try:
            from transformers import AutoImageProcessor, AutoModelForImageClassification
            from ultralytics import YOLO

            self._ensure_face_weights()
            self.face_detector = YOLO(self.face_model_path)
            classifier_path = self._ensure_classifier_files()
            self.processor = AutoImageProcessor.from_pretrained(
                classifier_path, local_files_only=True
            )
            self.classifier = AutoModelForImageClassification.from_pretrained(
                classifier_path, local_files_only=True
            )
            self.classifier.to(self.device)
            self.classifier.eval()
            self.ready = True
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"[:300]
            raise

    @staticmethod
    def _largest_face(image: Image.Image, boxes: np.ndarray) -> Image.Image | None:
        if boxes.size == 0:
            return None
        image_width, image_height = image.size
        candidates = []
        for raw in boxes:
            x1, y1, x2, y2 = [int(value) for value in raw[:4]]
            x1 = max(0, min(x1, image_width - 1))
            y1 = max(0, min(y1, image_height - 1))
            x2 = max(x1 + 1, min(x2, image_width))
            y2 = max(y1 + 1, min(y2, image_height))
            candidates.append(((x2 - x1) * (y2 - y1), (x1, y1, x2, y2)))
        _, box = max(candidates, key=lambda item: item[0])
        return image.crop(box)

    @staticmethod
    def _normalized_boxes(image: Image.Image, boxes: np.ndarray, confidences: np.ndarray) -> list[FaceBox]:
        image_width, image_height = image.size
        if image_width <= 0 or image_height <= 0 or boxes.size == 0:
            return []
        normalized: list[FaceBox] = []
        for index, raw in enumerate(boxes[:8]):
            x1, y1, x2, y2 = [float(value) for value in raw[:4]]
            x1 = max(0.0, min(x1, float(image_width)))
            y1 = max(0.0, min(y1, float(image_height)))
            x2 = max(x1, min(x2, float(image_width)))
            y2 = max(y1, min(y2, float(image_height)))
            width = x2 - x1
            height = y2 - y1
            if width <= 0 or height <= 0:
                continue
            confidence = float(confidences[index]) if index < len(confidences) else 0.0
            normalized.append(
                FaceBox(
                    x=round(x1 / image_width, 4),
                    y=round(y1 / image_height, 4),
                    width=round(width / image_width, 4),
                    height=round(height / image_height, 4),
                    confidence=round(max(0.0, min(1.0, confidence)), 4),
                )
            )
        return normalized

    def analyze(self, content: bytes) -> EmotionObservation:
        if not self.ready:
            raise RuntimeError("emotion model is not ready")
        if self.fake_mode:
            return EmotionObservation(
                face_detected=True,
                face_count=1,
                face_boxes=[FaceBox(x=0.25, y=0.12, width=0.5, height=0.76, confidence=0.8)],
                dominant_emotion="neutral",
                dominant_emotion_label="平稳",
                confidence=0.8,
                presentation_score=80,
                model="fake-disabled-in-production",
                device="cpu",
            )
        try:
            image = Image.open(BytesIO(content)).convert("RGB")
        except Exception as error:
            raise ValueError("invalid image") from error
        with self.lock:
            detection = self.face_detector.predict(image, conf=0.45, verbose=False, device=self.device)
            result = detection[0]
            boxes = result.boxes.xyxy.detach().cpu().numpy() if result.boxes is not None else np.empty((0, 4))
            confidences = result.boxes.conf.detach().cpu().numpy() if result.boxes is not None and result.boxes.conf is not None else np.empty((0,))
            face_boxes = self._normalized_boxes(image, boxes, confidences)
            face = self._largest_face(image, boxes)
            if face is None:
                return EmotionObservation(
                    face_detected=False,
                    face_count=0,
                    face_boxes=[],
                    confidence=0.0,
                    presentation_score=None,
                    model=f"YOLO-face + {self.classifier_id}",
                    device=self.device,
                    warning="未检测到清晰人脸，请保持正面并确保光线充足",
                )
            import torch

            inputs = self.processor(images=face, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.inference_mode():
                probabilities = torch.softmax(self.classifier(**inputs).logits, dim=-1)[0]
            index = int(torch.argmax(probabilities).item())
            confidence = float(probabilities[index].item())
            raw_label = str(self.classifier.config.id2label.get(index, "unknown")).lower()
            normalized = next(
                (key for key in EMOTION_LABELS if key in raw_label.replace("_", " ")),
                "unknown",
            )
            # This is a presentation signal, not a psychological or hiring judgment.
            presentation_score = round(max(0, min(100, 60 + confidence * 40)))
            return EmotionObservation(
                face_detected=True,
                face_count=int(len(boxes)),
                face_boxes=face_boxes,
                dominant_emotion=normalized,
                dominant_emotion_label=EMOTION_LABELS.get(normalized, raw_label),
                confidence=round(confidence, 4),
                presentation_score=presentation_score,
                model=f"YOLO-face + {self.classifier_id}",
                device=self.device,
            )


def create_app(*, fake_mode: bool | None = None) -> FastAPI:
    runtime = EmotionRuntime(
        fake_mode=(os.getenv("AI_FAKE_MODE") == "1") if fake_mode is None else fake_mode
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if runtime.fake_mode:
            runtime.load()
        else:
            Thread(target=runtime.load, name="emotion-model-loader", daemon=True).start()
        yield

    app = FastAPI(title="Career Agent Emotion Service", lifespan=lifespan)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        if not runtime.ready:
            raise HTTPException(503, detail={"ready": False, "error": runtime.error})
        return {
            "ready": True,
            "model": f"YOLO-face + {runtime.classifier_id}",
            "device": runtime.device,
        }

    @app.post("/emotion/analyze", response_model=EmotionObservation)
    async def analyze(file: UploadFile = File(...)) -> EmotionObservation:
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed:
            raise HTTPException(415, "only JPEG, PNG and WebP images are accepted")
        content = await file.read(4 * 1024 * 1024 + 1)
        if not content or len(content) > 4 * 1024 * 1024:
            raise HTTPException(413, "image is empty or exceeds 4 MB")
        try:
            return runtime.analyze(content)
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    return app


app = create_app()
