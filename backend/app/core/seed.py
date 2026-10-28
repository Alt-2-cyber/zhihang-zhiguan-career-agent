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
from app.workplace.models import SimulationScenario

DEMO_JOBS = (
    ("数据分析师", "星云科技", "上海", "要求 Python、SQL、数据可视化和业务分析能力。"),
    ("商业分析师", "远见咨询", "北京", "负责行业研究、经营分析和管理层报告。"),
    ("运营分析师", "云帆网络", "杭州", "负责用户增长、活动复盘和指标体系建设。"),
    ("产品数据分析师", "知行互联", "深圳", "结合产品行为数据发现问题并推动实验。"),
    ("BI 分析师", "数智制造", "苏州", "负责数据仓库取数、看板开发和经营监控。"),
    ("数据运营专员", "青禾服务", "南京", "维护业务数据质量并支持日常运营决策。"),
)

DEMO_WORKPLACE_SCENARIOS = (
    {
        "title": "入职第一周任务澄清",
        "difficulty": "easy",
        "description": "从直属主管接到模糊任务，练习确认目标、范围、协作对象、截止时间和验收标准。",
        "competencies": ["目标理解", "任务澄清", "主动沟通"],
        "context": {
            "role": "数据分析实习生",
            "stage": "入职第一周",
            "objective": "熟悉销售数据口径，并在本周提交一份可复核的销售趋势简报。",
            "stakeholders": ["直属主管", "销售运营同学"],
            "deliverables": ["销售趋势简报", "指标口径说明"],
            "deadline": "本周五 18:00",
            "acceptance_criteria": ["指标口径可追溯", "结论有数据证据", "主管可以复核"],
            "constraints": ["尚未熟悉内部数据表", "需要先确认统计口径"],
            "workflow": ["clarify_questions", "action_plan", "delivery_draft"],
        },
    },
    {
        "title": "跨部门需求变更沟通",
        "difficulty": "medium",
        "description": "业务方临时调整需求，练习记录变更、评估影响、同步取舍并形成可执行的行动项。",
        "competencies": ["需求沟通", "影响评估", "风险升级"],
        "context": {
            "role": "产品数据分析师",
            "stage": "试用期第二周",
            "objective": "评估业务方新增指标需求对当前看板版本的影响，并给出交付取舍建议。",
            "stakeholders": ["产品经理", "业务负责人", "数据开发同学"],
            "deliverables": ["变更影响说明", "行动项清单", "风险升级记录"],
            "deadline": "下个版本评审前",
            "acceptance_criteria": ["影响范围明确", "优先级有依据", "责任人和时间点清晰"],
            "constraints": ["开发资源已排期", "原版本发布时间不变"],
            "workflow": ["clarify_questions", "risk_register", "meeting_minutes"],
        },
    },
    {
        "title": "周报与进度风险汇报",
        "difficulty": "medium",
        "description": "围绕真实交付进度生成周报，练习用事实汇报完成项、风险、依赖和下周计划。",
        "competencies": ["结构化汇报", "进度管理", "风险识别"],
        "context": {
            "role": "数据产品助理",
            "stage": "试用期第三周",
            "objective": "向主管汇报数据看板迭代进度，并提前暴露数据接口延迟风险。",
            "stakeholders": ["直属主管", "前端开发", "数据开发"],
            "deliverables": ["本周周报", "风险升级说明", "下周行动计划"],
            "deadline": "每周五 17:00",
            "acceptance_criteria": ["完成项有证据", "风险有影响和应对", "下周计划可验收"],
            "constraints": ["接口联调依赖数据开发", "不能承诺尚未确认的日期"],
            "workflow": ["weekly_report", "risk_register", "action_plan"],
        },
    },
    {
        "title": "会议纪要与行动项",
        "difficulty": "easy",
        "description": "把跨团队讨论整理为决策、待办、负责人、截止时间和待确认问题，形成可追踪的会议结果。",
        "competencies": ["会议记录", "行动项管理", "协作闭环"],
        "context": {
            "role": "项目助理",
            "stage": "入职后日常协作",
            "objective": "将需求评审会议中的决策和待办整理成团队可执行的记录。",
            "stakeholders": ["产品经理", "研发负责人", "测试同学"],
            "deliverables": ["会议纪要", "行动项列表", "待确认问题"],
            "deadline": "会议结束后 2 小时内",
            "acceptance_criteria": ["决策和待办分开", "每项待办有负责人", "截止时间可追踪"],
            "constraints": ["只记录会议中确认的事实", "未决事项必须标注待确认"],
            "workflow": ["meeting_minutes", "clarify_questions", "action_plan"],
        },
    },
    {
        "title": "客户问题升级与复盘",
        "difficulty": "hard",
        "description": "处理客户问题升级，练习先响应事实、判断影响、协调资源、同步预期并完成事后复盘。",
        "competencies": ["客户沟通", "问题升级", "复盘改进"],
        "context": {
            "role": "客户成功专员",
            "stage": "试用期后期",
            "objective": "对客户反馈的数据异常进行分级响应，推动定位并给出可验证的恢复计划。",
            "stakeholders": ["客户联系人", "客户成功经理", "研发值班同学"],
            "deliverables": ["问题响应稿", "风险与升级记录", "复盘行动项"],
            "deadline": "首次响应 30 分钟内，恢复计划待确认",
            "acceptance_criteria": ["事实与假设分开", "影响范围明确", "客户收到下一次更新时间"],
            "constraints": ["不得承诺未经研发确认的修复时间", "敏感客户数据不能复制到外部文本"],
            "workflow": ["clarify_questions", "risk_register", "delivery_draft"],
        },
    },
)

load_all_models()


def seed_demo_data(db: Session, *, student_password: str, counselor_password: str) -> None:
    counselor = db.scalar(select(User).where(User.username == "counselor_demo"))
    if counselor is None:
        counselor = create_user(
            db,
            username="counselor_demo",
            password=counselor_password,
            display_name="辅导员演示账号",
            role=UserRole.counselor,
            class_id="class-2026-a",
        )
    student = db.scalar(select(User).where(User.username == "student_demo"))
    if student is None:
        student = create_user(
            db,
            username="student_demo",
            password=student_password,
            display_name="学生演示账号",
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
    for definition in DEMO_WORKPLACE_SCENARIOS:
        scenario = db.scalar(
            select(SimulationScenario).where(SimulationScenario.title == definition["title"])
        )
        context = definition["context"]
        stages = [
            {
                "key": "brief",
                "title": "读取工作简报",
                "prompt": f"请先复述任务目标、协作对象和验收标准：{context['objective']}",
            },
            {
                "key": "plan",
                "title": "拆分执行步骤",
                "prompt": "请给出可执行的行动计划，并标明负责人、检查点和风险。",
            },
            {
                "key": "delivery",
                "title": "提交工作交付物",
                "prompt": "请提交一份可以让协作方直接使用的工作交付草案。",
            },
            {
                "key": "review",
                "title": "复盘改进",
                "prompt": "请根据验收标准说明结果证据、偏差和下一步改进。",
            },
        ]
        if scenario is None:
            scenario = SimulationScenario(
                title=str(definition["title"]),
                category="workplace",
                difficulty=str(definition["difficulty"]),
                description=str(definition["description"]),
                competencies_json=json.dumps(definition["competencies"], ensure_ascii=False),
                steps_json="[]",
                rubric_json="[]",
                mode="workplace",
                stage_definition_json=json.dumps(stages, ensure_ascii=False),
                work_context_json=json.dumps(context, ensure_ascii=False),
                safety_policy_json=json.dumps({"no_external_submission": True}, ensure_ascii=False),
                status="active",
            )
            db.add(scenario)
        else:
            scenario.category = "workplace"
            scenario.mode = "workplace"
            scenario.difficulty = str(definition["difficulty"])
            scenario.description = str(definition["description"])
            scenario.competencies_json = json.dumps(definition["competencies"], ensure_ascii=False)
            scenario.stage_definition_json = json.dumps(stages, ensure_ascii=False)
            scenario.work_context_json = json.dumps(context, ensure_ascii=False)
            scenario.safety_policy_json = json.dumps(
                {"no_external_submission": True}, ensure_ascii=False
            )
            scenario.status = "active"
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
