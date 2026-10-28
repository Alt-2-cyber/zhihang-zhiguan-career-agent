from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.core.errors import AppError
from app.students.service import assert_counselor_can_access_student
from app.tools.contracts import ToolExecutionContext


def authorize_tool_context(db: Session, context: ToolExecutionContext) -> User:
    actor = db.get(User, context.actor_id)
    if actor is None or not actor.is_active or actor.role != context.actor_role:
        raise AppError(403, "forbidden", "Agent 工具执行身份无效")

    if actor.role == UserRole.student:
        if context.subject_student_id != actor.id:
            raise AppError(403, "forbidden", "学生只能操作自己的就业数据")
    elif context.subject_student_id is not None:
        assert_counselor_can_access_student(db, actor, context.subject_student_id)
    return actor
