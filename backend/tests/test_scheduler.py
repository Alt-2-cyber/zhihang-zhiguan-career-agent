from app.core.config import Settings
from app.core.scheduler import build_scheduler


def test_scheduler_is_not_created_when_disabled() -> None:
    settings = Settings(enable_scheduler=False)

    assert build_scheduler(settings) is None
