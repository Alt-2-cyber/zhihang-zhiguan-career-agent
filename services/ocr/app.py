import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from statistics import fmean
from threading import Lock, Thread
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel


class OCRPage(BaseModel):
    page: int
    text: str
    confidence: float


class OCRResponse(BaseModel):
    pages: list[OCRPage]
    text: str


class OCRRuntime:
    def __init__(self, *, fake_mode: bool) -> None:
        self.fake_mode = fake_mode
        self.lang = os.getenv("OCR_LANG", "ch")
        self.version = os.getenv("OCR_MODEL_VERSION", "PP-OCRv5")
        self.device = os.getenv("OCR_DEVICE", "cpu")
        self.model = None
        self.ready = False
        self.error: str | None = None
        self.lock = Lock()

    def load(self) -> None:
        if self.ready:
            return
        if self.fake_mode:
            self.ready = True
            return
        try:
            from paddleocr import PaddleOCR

            self.model = PaddleOCR(
                lang=self.lang,
                ocr_version=self.version,
                device=self.device,
                enable_mkldnn=False,
            )
            self.ready = True
        except Exception as error:
            self.error = type(error).__name__
            raise

    @staticmethod
    def _result_data(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item.get("res", item)
        payload = getattr(item, "json", None)
        if callable(payload):
            payload = payload()
        if isinstance(payload, dict):
            return payload.get("res", payload)
        result = getattr(item, "res", None)
        return result if isinstance(result, dict) else {}

    def recognize(self, path: Path) -> OCRResponse:
        if not self.ready:
            raise RuntimeError("OCR model is not ready")
        if self.fake_mode:
            page = OCRPage(page=1, text="掌握 Python 和 SQL", confidence=0.98)
            return OCRResponse(pages=[page], text=page.text)
        with self.lock:
            results = list(self.model.predict(str(path)))
        pages: list[OCRPage] = []
        for index, item in enumerate(results, start=1):
            data = self._result_data(item)
            texts = [str(text).strip() for text in data.get("rec_texts", []) if str(text).strip()]
            scores = [float(score) for score in data.get("rec_scores", [])]
            pages.append(
                OCRPage(
                    page=index,
                    text="\n".join(texts),
                    confidence=fmean(scores) if scores else 0.0,
                )
            )
        return OCRResponse(pages=pages, text="\n\n".join(page.text for page in pages).strip())


def create_app(*, fake_mode: bool | None = None) -> FastAPI:
    runtime = OCRRuntime(
        fake_mode=(os.getenv("AI_FAKE_MODE") == "1") if fake_mode is None else fake_mode
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if runtime.fake_mode:
            runtime.load()
        else:
            Thread(target=runtime.load, name="ocr-model-loader", daemon=True).start()
        yield

    app = FastAPI(title="Career Agent OCR Service", lifespan=lifespan)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        if not runtime.ready:
            raise HTTPException(503, detail={"ready": False, "error": runtime.error})
        return {"ready": True, "model": runtime.version, "device": runtime.device}

    @app.post("/ocr", response_model=OCRResponse)
    async def ocr(file: UploadFile = File(...)) -> OCRResponse:
        if file.content_type != "application/pdf":
            raise HTTPException(415, "only PDF files are accepted")
        content = await file.read(20 * 1024 * 1024 + 1)
        if not content or len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "PDF is empty or exceeds 20 MB")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
            temporary.write(content)
            path = Path(temporary.name)
        try:
            return runtime.recognize(path)
        finally:
            path.unlink(missing_ok=True)

    return app


app = create_app()
