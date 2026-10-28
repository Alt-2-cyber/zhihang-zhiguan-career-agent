import hashlib
import math
import os
from contextlib import asynccontextmanager
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)


class EmbedResponse(BaseModel):
    model: str
    dimensions: int
    vectors: list[list[float]]


class EmbeddingRuntime:
    def __init__(self, *, fake_mode: bool) -> None:
        self.fake_mode = fake_mode
        self.model_id = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self.device = os.getenv("EMBEDDING_DEVICE", "cpu")
        self.cache_dir = os.getenv("MODELSCOPE_CACHE", "/models/modelscope")
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
            from FlagEmbedding import BGEM3FlagModel
            from modelscope import snapshot_download

            model_path = snapshot_download(self.model_id, cache_dir=self.cache_dir)
            self.model = BGEM3FlagModel(
                model_path,
                use_fp16=self.device.startswith("cuda"),
                devices=[self.device],
            )
            self.ready = True
        except Exception as error:
            self.error = type(error).__name__
            raise

    @staticmethod
    def _fake_vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((digest[index % len(digest)] / 255.0) * 2.0) - 1.0 for index in range(1024)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [float(value / norm) for value in values]

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not self.ready:
            raise RuntimeError("embedding model is not ready")
        if self.fake_mode:
            return [self._fake_vector(text) for text in texts]
        with self.lock:
            output = self.model.encode(
                texts,
                batch_size=4,
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )["dense_vecs"]
        vectors = [[float(value) for value in row] for row in output]
        if any(len(row) != 1024 or not all(math.isfinite(value) for value in row) for row in vectors):
            raise RuntimeError("embedding model returned invalid vectors")
        return vectors


def create_app(*, fake_mode: bool | None = None) -> FastAPI:
    runtime = EmbeddingRuntime(
        fake_mode=(os.getenv("AI_FAKE_MODE") == "1") if fake_mode is None else fake_mode
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if runtime.fake_mode:
            runtime.load()
        else:
            Thread(target=runtime.load, name="embedding-model-loader", daemon=True).start()
        yield

    app = FastAPI(title="Career Agent Embedding Service", lifespan=lifespan)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        if not runtime.ready:
            raise HTTPException(503, detail={"ready": False, "error": runtime.error})
        return {"ready": True, "model": runtime.model_id, "device": runtime.device}

    @app.post("/embed", response_model=EmbedResponse)
    def embed(payload: EmbedRequest) -> EmbedResponse:
        if any(not text.strip() or len(text) > 20_000 for text in payload.texts):
            raise HTTPException(422, "texts must contain 1 to 20000 characters")
        vectors = runtime.encode(payload.texts)
        return EmbedResponse(model=runtime.model_id, dimensions=1024, vectors=vectors)

    return app


app = create_app()
