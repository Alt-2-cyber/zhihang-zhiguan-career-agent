from datetime import datetime, timezone

import pytest

from app.risks.rules import RiskFacts, evaluate_risk_facts


@pytest.mark.parametrize(
    ("facts", "expected_code", "expected_level"),
    [
        (RiskFacts(days_without_target=7), "target_not_set", "attention"),
        (RiskFacts(days_without_application=14), "no_recent_application", "intervention"),
        (RiskFacts(overdue_tasks=3), "tasks_overdue", "attention"),
        (
            RiskFacts(applications_without_interview=20),
            "applications_without_interview",
            "intervention",
        ),
        (
            RiskFacts(consecutive_failed_interviews=3),
            "repeated_interview_failure",
            "intervention",
        ),
    ],
)
def test_risk_rule_returns_explainable_fact(
    facts: RiskFacts, expected_code: str, expected_level: str
) -> None:
    finding = next(item for item in evaluate_risk_facts(facts) if item.code == expected_code)

    assert finding.level == expected_level
    assert finding.fact_value > 0
    assert finding.triggered_at.tzinfo == timezone.utc
    assert datetime.now(timezone.utc) >= finding.triggered_at

