from datetime import date

import pytest
from pydantic import ValidationError

from app.agents.contracts import CareerPlan, JobMatch, ProfileAnalysis


def test_profile_capability_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        ProfileAnalysis.model_validate(
            {
                "provider": "test",
                "summary": "具备数据分析基础",
                "strengths": [{"name": "Python", "level": "熟练", "evidence": []}],
                "gaps": ["缺少业务项目"],
                "constraints": ["目标城市为上海"],
            }
        )


def test_job_match_requires_all_five_dimensions() -> None:
    with pytest.raises(ValidationError, match="五个匹配维度"):
        JobMatch.model_validate(
            {
                "provider": "test",
                "recommendation": "apply",
                "overall_score": 80,
                "dimensions": [
                    {
                        "dimension": "skills",
                        "score": 80,
                        "evidence": [{"source": "resume", "quote": "掌握 Python"}],
                    }
                ],
                "gaps": [],
                "actions": [],
            }
        )


def test_career_plan_rejects_more_than_two_backup_roles() -> None:
    with pytest.raises(ValidationError):
        CareerPlan(
            provider="test",
            primary_role="数据分析师",
            backup_roles=["商业分析师", "运营分析师", "产品经理"],
            rationale="技能和经历匹配",
            tasks=[
                {
                    "title": "完善项目经历",
                    "week": 1,
                    "due_date": date(2026, 7, 20),
                    "acceptance_criteria": "补充一个量化结果",
                }
            ],
        )
