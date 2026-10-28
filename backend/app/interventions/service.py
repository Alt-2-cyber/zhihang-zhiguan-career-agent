from sqlalchemy.orm import Session

from app.auth.models import User
from app.interventions.models import Intervention
from app.students.service import assert_counselor_can_access_student


def assign_intervention(
    db: Session,
    *,
    counselor: User,
    student_id: str,
    title: str,
    description: str,
) -> Intervention:
    assert_counselor_can_access_student(db, counselor, student_id)
    item = Intervention(
        counselor_id=counselor.id,
        student_id=student_id,
        title=title,
        description=description,
        status="assigned",
    )
    db.add(item)
    return item
