from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from app.applications.models import Application, ApplicationEvent
from app.auth.models import User, UserRole
from app.core.config import Settings
from app.core.database import SessionLocal
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
    return scheduler
