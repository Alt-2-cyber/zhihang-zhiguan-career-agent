from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from app.ai.router import cleanup_expired_media_job
from app.applications.models import Application, ApplicationEvent
from app.auth.models import User, UserRole
from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.retention import cleanup_retained_data_job
from app.employment.service import generate_all_followups
from app.intelligence.service import refresh_job_sources
from app.plans.models import CareerPlanRecord, PlanTaskRecord
from app.risks.rules import RiskFacts, evaluate_risk_facts
from app.risks.service import upsert_risk_findings
from app.students.models import StudentProfile


def _days_since(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - value).days)


def scan_employment_risks() -> None:
    with SessionLocal() as db:
        students = db.scalars(
            select(User).where(User.role == UserRole.student, User.is_active.is_(True))
        ).all()
        for student in students:
            profile = db.scalar(
                select(StudentProfile).where(StudentProfile.student_id == student.id)
            )
            plan = db.scalar(
                select(CareerPlanRecord)
                .where(CareerPlanRecord.student_id == student.id)
                .order_by(CareerPlanRecord.created_at.desc())
            )
            last_application = db.scalar(
                select(func.max(ApplicationEvent.occurred_at)).where(
                    ApplicationEvent.student_id == student.id,
                    ApplicationEvent.to_stage == "applied",
                )
            )
            overdue_tasks = int(
                db.scalar(
                    select(func.count())
                    .select_from(PlanTaskRecord)
                    .where(
                        PlanTaskRecord.student_id == student.id,
                        PlanTaskRecord.due_date < date.today(),
                        PlanTaskRecord.status != "completed",
                    )
                )
                or 0
            )
            application_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(Application)
                    .where(Application.student_id == student.id)
                )
                or 0
            )
            interview_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(Application)
                    .where(
                        Application.student_id == student.id,
                        Application.stage.in_(["interview", "offered"]),
                    )
                )
                or 0
            )
            facts = RiskFacts(
                days_without_target=_days_since(profile.created_at) if profile and not plan else 0,
                days_without_application=_days_since(last_application) if profile else 0,
                overdue_tasks=overdue_tasks,
                applications_without_interview=application_count if interview_count == 0 else 0,
                consecutive_failed_interviews=0,
            )
            upsert_risk_findings(db, student.id, evaluate_risk_facts(facts))


def build_scheduler(settings: Settings) -> BackgroundScheduler | None:
    if not settings.enable_scheduler:
        return None
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        scan_employment_risks,
        "cron",
        hour=2,
        minute=0,
        id="daily-employment-risk-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        cleanup_expired_media_job,
        "cron",
        hour=3,
        minute=0,
        id="daily-expired-media-cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _generate_employment_followups_job,
        "cron",
        hour=2,
        minute=20,
        id="daily-employment-followups",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        refresh_job_sources_job,
        "cron",
        hour=1,
        minute=30,
        id="daily-job-source-refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        cleanup_retained_data_job,
        "cron",
        hour=3,
        minute=30,
        id="daily-retention-cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def refresh_job_sources_job() -> None:
    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    with SessionLocal() as db, httpx.Client(timeout=settings.public_job_search_timeout_seconds) as client:
        refresh_job_sources(
            db,
            client=client,
            retry_attempts=settings.job_source_refresh_retry_attempts,
        )
        db.commit()


def _generate_employment_followups_job() -> None:
    with SessionLocal() as db:
        generate_all_followups(db)
