from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RiskFacts:
    days_without_target: int = 0
    days_without_application: int = 0
    overdue_tasks: int = 0
    applications_without_interview: int = 0
    consecutive_failed_interviews: int = 0


@dataclass(frozen=True)
class RiskFinding:
    code: str
    level: str
    fact_name: str
    fact_value: int
    message: str
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def evaluate_risk_facts(facts: RiskFacts) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    rules = (
        (
            facts.days_without_target >= 7,
            "target_not_set",
            "attention",
            "days_without_target",
            facts.days_without_target,
            f"已建档 {facts.days_without_target} 天但尚未确认目标岗位",
        ),
        (
            facts.days_without_application >= 14,
            "no_recent_application",
            "intervention",
            "days_without_application",
            facts.days_without_application,
            f"连续 {facts.days_without_application} 天无投递记录",
        ),
        (
            facts.overdue_tasks >= 3,
            "tasks_overdue",
            "attention",
            "overdue_tasks",
            facts.overdue_tasks,
            f"已有 {facts.overdue_tasks} 项计划任务逾期",
        ),
        (
            facts.applications_without_interview >= 20,
            "applications_without_interview",
            "intervention",
            "applications_without_interview",
            facts.applications_without_interview,
            f"已投递 {facts.applications_without_interview} 次但尚未进入面试",
        ),
        (
            facts.consecutive_failed_interviews >= 3,
            "repeated_interview_failure",
            "intervention",
            "consecutive_failed_interviews",
            facts.consecutive_failed_interviews,
            f"连续 {facts.consecutive_failed_interviews} 次面试未通过",
        ),
    )
    for triggered, code, level, fact_name, fact_value, message in rules:
        if triggered:
            findings.append(
                RiskFinding(
                    code=code,
                    level=level,
                    fact_name=fact_name,
                    fact_value=fact_value,
                    message=message,
                )
            )
    return findings
