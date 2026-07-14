from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.model_registry import load_all_models
from app.core.models import Base
from app.core.seed import seed_demo_data
from app.jobs.models import Job


def test_demo_seed_is_idempotent(db_session: Session) -> None:
    seed_demo_data(db_session, student_password="Student123!", counselor_password="Counselor123!")
    first_users = db_session.scalar(select(func.count()).select_from(User))
    first_jobs = db_session.scalar(select(func.count()).select_from(Job))

    seed_demo_data(db_session, student_password="Student123!", counselor_password="Counselor123!")

    assert db_session.scalar(select(func.count()).select_from(User)) == first_users == 2
    assert db_session.scalar(select(func.count()).select_from(Job)) == first_jobs == 6


def test_model_registry_loads_every_foreign_key_target() -> None:
    load_all_models()

    assert "resume_versions" in Base.metadata.tables
    assert Base.metadata.tables["applications"].c.resume_version_id.foreign_keys
