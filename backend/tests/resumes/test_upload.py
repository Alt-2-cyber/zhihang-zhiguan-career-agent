from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.resumes.storage import validate_upload
from tests.conftest import login_headers


def test_upload_uses_random_safe_name_for_path_traversal_filename(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    headers = login_headers(client, "student1", "Student123!")

    response = client.post(
        "/api/resumes",
        headers=headers,
        files={"file": ("../../evil.pdf", b"not-a-valid-pdf", "application/pdf")},
    )

    assert response.status_code == 201
    stored_name = response.json()["stored_name"]
    assert stored_name.endswith(".pdf")
    assert "evil" not in stored_name
    assert (tmp_path / stored_name).exists()
    assert not (tmp_path.parent / "evil.pdf").exists()
    assert response.json()["parse_status"] == "failed"


def test_validate_upload_rejects_disallowed_extension_and_large_file() -> None:
    with pytest.raises(AppError, match="仅支持"):
        validate_upload("resume.exe", "application/octet-stream", b"123", max_bytes=4)

    with pytest.raises(AppError, match="大小"):
        validate_upload("resume.pdf", "application/pdf", b"12345", max_bytes=4)
