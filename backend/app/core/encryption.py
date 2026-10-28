import base64
import hashlib
from typing import Any

from sqlalchemy.types import Text, TypeDecorator


def _fernet_key() -> bytes | None:
    from app.core.config import get_settings

    settings = get_settings()
    raw = settings.data_encryption_key.strip()
    if not raw:
        if settings.data_encryption_required:
            raise RuntimeError("DATA_ENCRYPTION_KEY is required")
        return None
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        if len(decoded) == 32:
            return base64.urlsafe_b64encode(decoded)
    except (ValueError, UnicodeError):
        pass
    return base64.urlsafe_b64encode(hashlib.sha256(raw.encode("utf-8")).digest())


class EncryptedText(TypeDecorator[str]):
    """Encrypt new values while allowing existing plaintext rows to migrate lazily."""

    impl = Text
    cache_ok = False
    prefix = "enc:v1:"

    def process_bind_param(self, value: Any, dialect) -> str | None:
        del dialect
        if value is None:
            return None
        text = str(value)
        key = _fernet_key()
        if key is None:
            return text
        from cryptography.fernet import Fernet

        return self.prefix + Fernet(key).encrypt(text.encode("utf-8")).decode("ascii")

    def process_result_value(self, value: Any, dialect) -> str | None:
        del dialect
        if value is None or not isinstance(value, str) or not value.startswith(self.prefix):
            return value
        key = _fernet_key()
        if key is None:
            raise RuntimeError("encrypted data cannot be read without DATA_ENCRYPTION_KEY")
        from cryptography.fernet import Fernet, InvalidToken

        try:
            return Fernet(key).decrypt(value[len(self.prefix) :].encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as error:
            raise RuntimeError("encrypted data failed integrity validation") from error
