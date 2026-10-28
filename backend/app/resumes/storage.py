from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from app.core.errors import AppError

ALLOWED_UPLOADS = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}


@dataclass
class StorageService:
    """Shared boundary for local uploads and S3-compatible object storage."""

    backend: str
    root: Path
    endpoint_url: str = ""
    bucket: str = "career"
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    prefix: str = "career"

    def __post_init__(self) -> None:
        self.backend = self.backend.lower().strip()
        if self.backend not in {"local", "s3"}:
            raise ValueError(f"unsupported storage backend: {self.backend}")
        self._client = None
        if self.backend == "s3":
            if not self.bucket or not self.access_key or not self.secret_key:
                raise ValueError("s3 storage requires bucket and credentials")
            try:
                import boto3
            except ImportError as error:  # pragma: no cover - optional in local tests
                raise RuntimeError("boto3 is required for s3 storage") from error
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url or None,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )

    def _key(self, key: str) -> str:
        clean = key.strip("/")
        prefix = self.prefix.strip("/")
        return f"{prefix}/{clean}" if prefix else clean

    def put_bytes(self, key: str, content: bytes, *, media_type: str | None = None) -> str:
        if self.backend == "local":
            target = (self.root / key).resolve()
            root = self.root.resolve()
            if target != root and root not in target.parents:
                raise AppError(400, "invalid_storage_path", "文件保存路径无效")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return str(target)
        assert self._client is not None
        arguments: dict[str, object] = {
            "Bucket": self.bucket,
            "Key": self._key(key),
            "Body": content,
        }
        if media_type:
            arguments["ContentType"] = media_type
        self._client.put_object(**arguments)
        return f"s3://{self.bucket}/{arguments['Key']}"

    def read_bytes(self, reference: str, *, allow_external_local: bool = False) -> bytes:
        if not reference.startswith("s3://"):
            path = Path(reference).resolve()
            root = self.root.resolve()
            if not allow_external_local and path != root and root not in path.parents:
                raise AppError(400, "invalid_storage_path", "文件读取路径无效")
            return path.read_bytes()
        bucket, _, key = reference[5:].partition("/")
        if bucket != self.bucket or not key:
            raise AppError(400, "invalid_storage_reference", "对象存储引用无效")
        assert self._client is not None
        return self._client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def delete(self, reference: str) -> None:
        if reference.startswith("s3://"):
            bucket, _, key = reference[5:].partition("/")
            if bucket != self.bucket or not key:
                raise AppError(400, "invalid_storage_reference", "对象存储引用无效")
            assert self._client is not None
            self._client.delete_object(Bucket=bucket, Key=key)
            return
        path = Path(reference).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise AppError(400, "invalid_storage_path", "文件删除路径无效")
        path.unlink(missing_ok=True)

    @contextmanager
    def materialize(self, reference: str, *, suffix: str = "") -> Iterator[Path]:
        """Yield a local path for OCR/ASR libraries that cannot read object URIs."""
        if not reference.startswith("s3://"):
            path = Path(reference).resolve()
            root = self.root.resolve()
            if path != root and root not in path.parents:
                raise AppError(400, "invalid_storage_path", "文件读取路径无效")
            yield path
            return
        content = self.read_bytes(reference)
        temporary = NamedTemporaryFile(prefix="career-storage-", suffix=suffix, delete=False)
        try:
            temporary.write(content)
            temporary.close()
            yield Path(temporary.name)
        finally:
            Path(temporary.name).unlink(missing_ok=True)


def build_storage(settings) -> StorageService:
    return StorageService(
        backend=settings.storage_backend,
        root=Path(settings.upload_dir),
        endpoint_url=settings.storage_endpoint_url,
        bucket=settings.storage_bucket,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        region=settings.storage_region,
        prefix=settings.storage_prefix,
    )


def validate_upload(filename: str, media_type: str, content: bytes, *, max_bytes: int) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_UPLOADS or media_type not in ALLOWED_UPLOADS[extension]:
        raise AppError(415, "unsupported_resume", "仅支持 PDF 或 DOCX 简历")
    if len(content) > max_bytes:
        raise AppError(413, "resume_too_large", "简历文件大小超过限制")
    return extension


def save_upload(
    content: bytes,
    extension: str,
    upload_dir: Path,
    *,
    storage: StorageService | None = None,
    key_prefix: str = "uploads",
) -> tuple[str, str]:
    stored_name = f"{uuid4().hex}{extension}"
    service = storage or StorageService(backend="local", root=upload_dir)
    prefix = key_prefix.strip("/") if service.backend == "s3" else ""
    reference = service.put_bytes(
        f"{prefix}/{stored_name}" if prefix else stored_name,
        content,
    )
    return stored_name, reference
