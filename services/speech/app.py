import io
import os
import subprocess
import tempfile
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text: str
    duration_seconds: float
    model: str


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    language: str = "ZH"


class SpeechRuntime:
    def __init__(self, *, fake_mode: bool) -> None:
        self.fake_mode = fake_mode
        self.asr_model_id = os.getenv("ASR_MODEL", "paraformer-zh")
        self.asr_device = os.getenv("ASR_DEVICE", "cuda")
        self.tts_device = os.getenv("TTS_DEVICE", "cpu")
        self.modelscope_cache = os.getenv("MODELSCOPE_CACHE", "/models/modelscope")
        self.melotts_cache = Path(os.getenv("MELOTTS_CACHE", "/models/melotts"))
        self.asr_model = None
        self.tts_model = None
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
            from funasr import AutoModel
            from modelscope import snapshot_download
            from transformers import AutoModelForMaskedLM, AutoTokenizer

            bert_files = [
                "config.json",
                "model.safetensors",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
            ]
            bert_paths = {
                "bert-base-multilingual-uncased": snapshot_download(
                    "google-bert/bert-base-multilingual-uncased",
                    cache_dir=self.modelscope_cache,
                    allow_file_pattern=bert_files,
                ),
                "bert-base-uncased": snapshot_download(
                    "google-bert/bert-base-uncased",
                    cache_dir=self.modelscope_cache,
                    allow_file_pattern=bert_files,
                ),
            }
            self._redirect_transformers(AutoTokenizer, AutoModelForMaskedLM, bert_paths)

            from melo.api import TTS

            self.asr_model = AutoModel(
                model=self.asr_model_id,
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                device=self.asr_device,
            )
            config_path = self._download_melotts_file("config.json")
            checkpoint_path = self._download_melotts_file("checkpoint.pth")
            self.tts_model = TTS(
                language="ZH",
                device=self.tts_device,
                config_path=str(config_path),
                ckpt_path=str(checkpoint_path),
            )
            self.ready = True
        except Exception as error:
            self.error = type(error).__name__
            raise

    @staticmethod
    def _redirect_transformers(
        tokenizer_class: Any,
        model_class: Any,
        model_paths: dict[str, str],
    ) -> None:
        original_tokenizer = tokenizer_class.from_pretrained
        original_model = model_class.from_pretrained

        def tokenizer_from_pretrained(model_id: str, *args: object, **kwargs: object):
            return original_tokenizer(model_paths.get(str(model_id), model_id), *args, **kwargs)

        def model_from_pretrained(model_id: str, *args: object, **kwargs: object):
            return original_model(model_paths.get(str(model_id), model_id), *args, **kwargs)

        tokenizer_class.from_pretrained = staticmethod(tokenizer_from_pretrained)
        model_class.from_pretrained = staticmethod(model_from_pretrained)

    def _download_melotts_file(self, filename: str) -> Path:
        import requests

        self.melotts_cache.mkdir(parents=True, exist_ok=True)
        target = self.melotts_cache / filename
        if target.is_file() and target.stat().st_size > 0:
            return target
        temporary = target.with_suffix(f"{target.suffix}.part")
        url = f"https://huggingface.co/myshell-ai/MeloTTS-Chinese/resolve/main/{filename}"
        with requests.get(url, stream=True, timeout=(20, 300)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        temporary.replace(target)
        return target

    @staticmethod
    def _fake_wav() -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            output.writeframes(b"\x00\x00" * 1_600)
        return buffer.getvalue()

    def transcribe(self, source: Path) -> TranscriptionResponse:
        if not self.ready:
            raise RuntimeError("speech model is not ready")
        if self.fake_mode:
            return TranscriptionResponse(
                text="我完成了销售数据分析项目",
                duration_seconds=3.2,
                model=self.asr_model_id,
            )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as converted:
            wav_path = Path(converted.name)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(wav_path),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            with wave.open(str(wav_path), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
            with self.lock:
                result = self.asr_model.generate(input=str(wav_path), batch_size_s=60)
            text = str(result[0].get("text", "")).strip() if result else ""
            return TranscriptionResponse(
                text=text,
                duration_seconds=round(duration, 3),
                model=self.asr_model_id,
            )
        finally:
            wav_path.unlink(missing_ok=True)

    def synthesize(self, text: str) -> bytes:
        if not self.ready:
            raise RuntimeError("speech model is not ready")
        if self.fake_mode:
            return self._fake_wav()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output:
            output_path = Path(output.name)
        try:
            speaker_id = self.tts_model.hps.data.spk2id["ZH"]
            with self.lock:
                self.tts_model.tts_to_file(text, speaker_id, str(output_path), speed=1.0)
            return output_path.read_bytes()
        finally:
            output_path.unlink(missing_ok=True)


def create_app(*, fake_mode: bool | None = None) -> FastAPI:
    runtime = SpeechRuntime(
        fake_mode=(os.getenv("AI_FAKE_MODE") == "1") if fake_mode is None else fake_mode
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if runtime.fake_mode:
            runtime.load()
        else:
            Thread(target=runtime.load, name="speech-model-loader", daemon=True).start()
        yield

    app = FastAPI(title="Career Agent Speech Service", lifespan=lifespan)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        if not runtime.ready:
            raise HTTPException(503, detail={"ready": False, "error": runtime.error})
        return {
            "ready": True,
            "asr_model": runtime.asr_model_id,
            "asr_device": runtime.asr_device,
            "tts_device": runtime.tts_device,
        }

    @app.post("/transcribe", response_model=TranscriptionResponse)
    async def transcribe(file: UploadFile = File(...)) -> TranscriptionResponse:
        allowed = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav"}
        if file.content_type not in allowed:
            raise HTTPException(415, "unsupported audio type")
        content = await file.read(20 * 1024 * 1024 + 1)
        if not content or len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "audio is empty or exceeds 20 MB")
        suffix = Path(file.filename or "recording.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(content)
            source = Path(temporary.name)
        try:
            return runtime.transcribe(source)
        finally:
            source.unlink(missing_ok=True)

    @app.post("/synthesize")
    def synthesize(payload: SynthesisRequest) -> Response:
        if payload.language != "ZH":
            raise HTTPException(422, "only ZH synthesis is configured")
        return Response(runtime.synthesize(payload.text), media_type="audio/wav")

    return app


app = create_app()
