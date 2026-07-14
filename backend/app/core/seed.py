import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.applications.models import Application, ApplicationEvent
from app.auth.models import User, UserRole
from app.auth.service import create_user
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.model_registry import load_all_models
from app.interventions.models import Intervention
from app.jobs.models import Job
from app.plans.models import CareerPlanRecord, PlanTaskRecord
from app.risks.models import RiskEvent
from app.students.models import StudentProfile

DEMO_JOBS = (
    ("数据分析师", "星云科技", "上海", "要求 Python、SQL、数据可视化和业务分析能力。"),
    ("商业分析师", "远见咨询", "北京", "负责行业研究、经营分析和管理层报告。"),
    ("运营分析师", "云帆网络", "杭州", "负责用户增长、活动复盘和指标体系建设。"),
    ("产品数据分析师", "知行互联", "深圳", "结合产品行为数据发现问题并推动实验。"),
    ("BI 分析师", "数智制造", "苏州", "负责数据仓库取数、看板开发和经营监控。"),
    ("数据运营专员", "青禾服务", "南京", "维护业务数据质量并支持日常运营决策。"),
)

load_all_models()


def seed_demo_data(db: Session, *, student_password: str, counselor_password: str) -> None:
    counselor = db.scalar(select(User).where(User.username == "counselor_demo"))
    if counselor is None:
        counselor = create_user(
            db,
            username="counselor_demo",
            password=counselor_password,
            display_name="李老师",
            role=UserRole.counselor,
            class_id="class-2026-a",
        )
    student = db.scalar(select(User).where(User.username == "student_demo"))
    if student is None:
        student = create_user(
            db,
            username="student_demo",
            password=student_password,
            display_name="张同学",
            role=UserRole.student,
            class_id="class-2026-a",
        )

    jobs: list[Job] = []
    for title, company, location, description in DEMO_JOBS:
        job = db.scalar(select(Job).where(Job.title == title, Job.company == company))
        if job is None:
            job = Job(
                title=title,
                company=company,
                location=location,
                description=description,
            )
            db.add(job)
            db.flush()
        jobs.append(job)

    profile = db.scalar(select(StudentProfile).where(StudentProfile.student_id == student.id))
    if profile is None:
        profile = StudentProfile(
            student_id=student.id,
            summary="掌握 Python 和 SQL，完成销售数据分析与可视化项目。",
            strengths_json=json.dumps(
                [
                    {
                        "name": "Python / SQL",
                        "level": "具备实践基础",
                        "evidence": [
                            {"source": "resume", "quote": "使用 Python 和 SQL 分析销售数据"}
                        ],
                    }
                ],
                ensure_ascii=False,
            ),
            gaps_json=json.dumps(["项目成果需要补充量化结果"], ensure_ascii=False),
            constraints_json=json.dumps(["目标城市：上海"], ensure_ascii=False),
            status="confirmed",
            version=1,
        )
        db.add(profile)

    plan = db.scalar(select(CareerPlanRecord).where(CareerPlanRecord.student_id == student.id))
    if plan is None:
        plan = CareerPlanRecord(
            student_id=student.id,
            provider="local-demo",
            primary_role="数据分析师",
            backup_roles_json=json.dumps(["商业分析师", "运营分析师"], ensure_ascii=False),
            rationale="技能基础与数据分析岗位要求较匹配。",
            status="active",
        )
        db.add(plan)
        db.flush()
        for week, title in enumerate(
            ["完善目标岗位简历", "筛选并投递匹配岗位", "完成模拟面试训练", "复盘求职漏斗"],
            start=1,
        ):
            db.add(
                PlanTaskRecord(
                    plan_id=plan.id,
                    student_id=student.id,
                    title=title,
                    week=week,
                    due_date=date.today() + timedelta(days=week * 7),
                    acceptance_criteria="完成任务并提交可核实结果",
                    status="pending",
                )
            )

    application = db.scalar(
        select(Application).where(
            Application.student_id == student.id, Application.job_id == jobs[0].id
        )
    )
    if application is None:
        application = Application(student_id=student.id, job_id=jobs[0].id, stage="applied")
        db.add(application)
        db.flush()
        db.add_all(
            [
                ApplicationEvent(
                    application_id=application.id,
                    student_id=student.id,
                    from_stage=None,
                    to_stage="saved",
                ),
                ApplicationEvent(
                    application_id=application.id,
                    student_id=student.id,
                    from_stage="saved",
                    to_stage="applied",
                ),
            ]
        )

    risk = db.scalar(
        select(RiskEvent).where(
            RiskEvent.student_id == student.id,
            RiskEvent.rule_code == "no_recent_application",
            RiskEvent.status == "open",
        )
    )
    if risk is None:
        db.add(
            RiskEvent(
                student_id=student.id,
                rule_code="no_recent_application",
                level="intervention",
                facts_json=json.dumps(
                    {
                        "name": "days_without_application",
                        "value": 14,
                        "message": "连续 14 天无投递记录",
                    },
                    ensure_ascii=False,
                ),
                status="open",
            )
        )

    intervention = db.scalar(
        select(Intervention).where(
            Intervention.student_id == student.id,
            Intervention.title == "完成岗位筛选",
        )
    )
    if intervention is None:
        db.add(
            Intervention(
                counselor_id=counselor.id,
                student_id=student.id,
                title="完成岗位筛选",
                description="结合就业画像筛选 5 个匹配岗位。",
                status="assigned",
            )
        )
    db.commit()


def main() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        seed_demo_data(
            db,
            student_password=settings.demo_student_password,
            counselor_password=settings.demo_counselor_password,
        )


if __name__ == "__main__":
    main()
