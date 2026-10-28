import math
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.core.config import Settings


class AIServiceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EmbedResponse(BaseModel):
    model: str
    dimensions: int
    vectors: list[list[float]]

    @model_validator(mode="after")
    def validate_vectors(self) -> "EmbedResponse":
        if self.dimensions != 1024:
            raise ValueError("embedding dimensions must be 1024")
        if any(
            len(vector) != self.dimensions or not all(math.isfinite(value) for value in vector)
            for vector in self.vectors
        ):
            raise ValueError("embedding vectors are invalid")
        return self


class OCRPage(BaseModel):
    page: int = Field(ge=1)
    text: str
    confidence: float = Field(ge=0, le=1)


class OCRResponse(BaseModel):
    pages: list[OCRPage]
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    duration_seconds: float = Field(ge=0)
    model: str


class FaceBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class EmotionObservation(BaseModel):
    face_detected: bool
    face_count: int = Field(ge=0)
    face_boxes: list[FaceBox] = Field(default_factory=list, max_length=8)
    dominant_emotion: str = "unknown"
    dominant_emotion_label: str = "未识别"
    confidence: float = Field(ge=0, le=1)
    presentation_score: int | None = Field(default=None, ge=0, le=100)
    model: str
    device: str
    warning: str | None = None


class LocalAIClients:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._client = httpx.Client(
            timeout=httpx.Timeout(settings.agent_timeout_seconds), transport=transport
        )

    def __enter__(self) -> "LocalAIClients":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _post_json(
        self,
        *,
        service: str,
        url: str,
        payload: dict[str, object],
        contract: type[BaseModel],
    ) -> BaseModel:
        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            return contract.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            raise AIServiceError(
                f"{service}_service_error",
                f"{service} service request failed ({type(error).__name__})",
            ) from error

    def embed(self, texts: list[str]) -> EmbedResponse:
        result = self._post_json(
            service="embedding",
            url=f"{self.settings.embedding_service_url.rstrip('/')}/embed",
            payload={"texts": texts},
            contract=EmbedResponse,
        )
        assert isinstance(result, EmbedResponse)
        if len(result.vectors) != len(texts):
            raise AIServiceError(
                "embedding_service_error", "embedding service returned wrong count"
            )
        return result

    def ocr(self, path: Path) -> OCRResponse:
        try:
            with path.open("rb") as source:
                response = self._client.post(
                    f"{self.settings.ocr_service_url.rstrip('/')}/ocr",
                    files={"file": (path.name, source, "application/pdf")},
                )
            response.raise_for_status()
            return OCRResponse.model_validate(response.json())
        except (OSError, httpx.HTTPError, ValueError, ValidationError) as error:
            raise AIServiceError(
                "ocr_service_error",
                f"ocr service request failed ({type(error).__name__})",
            ) from error

    def transcribe(self, path: Path, *, media_type: str) -> TranscriptionResponse:
        try:
            with path.open("rb") as source:
                response = self._client.post(
                    f"{self.settings.speech_service_url.rstrip('/')}/transcribe",
                    files={"file": (path.name, source, media_type)},
                )
            response.raise_for_status()
            return TranscriptionResponse.model_validate(response.json())
        except (OSError, httpx.HTTPError, ValueError, ValidationError) as error:
            raise AIServiceError(
                "speech_service_error",
                f"speech service request failed ({type(error).__name__})",
            ) from error

    def synthesize(self, text: str) -> bytes:
        try:
            response = self._client.post(
                f"{self.settings.speech_service_url.rstrip('/')}/synthesize",
                json={"text": text, "language": "ZH"},
            )
            response.raise_for_status()
            if response.headers.get("content-type", "").split(";", 1)[0] != "audio/wav":
                raise ValueError("unexpected synthesis media type")
            if not response.content:
                raise ValueError("empty synthesis response")
            return response.content
        except (httpx.HTTPError, ValueError) as error:
            raise AIServiceError(
                "speech_service_error",
                f"speech service request failed ({type(error).__name__})",
            ) from error

    def analyze_emotion(self, content: bytes, *, filename: str, media_type: str) -> EmotionObservation:
        try:
            response = self._client.post(
                f"{self.settings.emotion_service_url.rstrip('/')}/emotion/analyze",
                files={"file": (filename, content, media_type)},
                timeout=self.settings.emotion_analysis_timeout_seconds,
            )
            response.raise_for_status()
            return EmotionObservation.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            raise AIServiceError(
                "emotion_service_error",
                f"emotion service request failed ({type(error).__name__})",
            ) from error
