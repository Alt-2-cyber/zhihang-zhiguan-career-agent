import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.risks.models import RiskEvent
from app.risks.rules import RiskFinding


def upsert_risk_findings(
    db: Session, student_id: str, findings: list[RiskFinding]
) -> list[RiskEvent]:
    records: list[RiskEvent] = []
    for finding in findings:
        record = db.scalar(
            select(RiskEvent).where(
                RiskEvent.student_id == student_id,
                RiskEvent.rule_code == finding.code,
                RiskEvent.status == "open",
            )
        )
        facts = {
            "name": finding.fact_name,
            "value": finding.fact_value,
            "message": finding.message,
        }
        if record is None:
            record = RiskEvent(
                student_id=student_id,
                rule_code=finding.code,
                level=finding.level,
                facts_json=json.dumps(facts, ensure_ascii=False),
                status="open",
            )
            db.add(record)
        else:
            record.level = finding.level
            record.facts_json = json.dumps(facts, ensure_ascii=False)
        records.append(record)
    db.commit()
    return records

