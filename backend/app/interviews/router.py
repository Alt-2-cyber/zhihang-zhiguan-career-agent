import asyncio
import json
from collections import Counter
from datetime import timedelta
from statistics import fmean, pstdev
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.contracts import InterviewQuestion
from app.agents.conversation_contracts import (
    ComposeAnswerRequest,
    ConversationMessage,
    SpecialistOutput,
)
from app.agents.service import build_agent_gateway, build_conversation_gateway
from app.ai.clients import AIServiceError, EmotionObservation, LocalAIClients
from app.ai.models import AITaskType, MediaArtifact
from app.ai.service import enqueue_task, ensure_task_available, is_task_available, utc_now
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.interviews.models import InterviewSession, InterviewTurn
from app.interviews.service import (
    build_configured_question_plan,
    build_final_report,
    load_question_plan,
    normalize_interview_question,
    serialize_progress,
)
from app.jobs.models import Job
from app.resumes.models import ResumeFile
from app.resumes.storage import build_storage
from app.workplace.models import SimulationScenario

router = APIRouter(prefix="/interviews", tags=["interviews"])


class InterviewStartRequest(BaseModel):
    resume_id: str
    job_id: str


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)


class InterviewSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


def _summarize_emotion(samples: list[dict[str, object]]) -> dict[str, object] | None:
    """Turn frame-level model output into an auditable, non-psychological signal."""
    if not samples:
        return None
    detected = [item for item in samples if bool(item.get("face_detected"))]
    if not detected:
        return {
            "sample_count": len(samples),
            "face_presence_rate": 0.0,
            "dominant_emotion": "unknown",
            "mean_confidence": 0.0,
            "stability_score": None,
            "model": str(samples[-1].get("model") or "unknown"),
            "warning": "未检测到清晰人脸，未生成情绪评分",
        }
    labels = [str(item.get("dominant_emotion") or "unknown") for item in detected]
    scores = [
        max(0, min(100, int(item["presentation_score"])))
        for item in detected
        if item.get("presentation_score") is not None
    ]
    confidences = [
        max(0.0, min(1.0, float(item.get("confidence") or 0))) for item in detected
    ]
    label_consistency = max(Counter(labels).values()) / len(labels)
    score_volatility = min(1.0, (pstdev(scores) / 50.0)) if len(scores) > 1 else 0.0
    presence_rate = len(detected) / len(samples)
    stability = round(
        max(0.0, min(100.0, 100 * (0.5 * presence_rate + 0.3 * label_consistency + 0.2 * (1 - score_volatility))))
    )
    return {
        "sample_count": len(samples),
        "face_presence_rate": round(presence_rate, 4),
        "dominant_emotion": Counter(labels).most_common(1)[0][0],
        "mean_confidence": round(fmean(confidences), 4) if confidences else 0.0,
        "stability_score": stability,
        "model": str(detected[-1].get("model") or "unknown"),
        "warning": None,
    }


def _load_emotion_samples(session: InterviewSession) -> list[dict[str, object]]:
    try:
        samples = json.loads(session.emotion_samples_json)
    except (TypeError, ValueError):
        return []
    return samples if isinstance(samples, list) else []


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _repair_legacy_state(
    db: Session, session: InterviewSession, job: Job | None = None
) -> list[InterviewTurn]:
    """Reconcile sessions written by the retired fixed-two-question endpoint."""
    turns = list(
        db.scalars(
            select(InterviewTurn)
            .where(InterviewTurn.session_id == session.id)
            .order_by(InterviewTurn.sequence)
        ).all()
    )
    changed = False
    if session.total_turns != len(turns):
        session.total_turns = len(turns)
        changed = True
    try:
        current = json.loads(session.current_question_json)
    except (TypeError, ValueError):
        current = None
    if isinstance(current, dict):
        try:
            normalized_current = normalize_interview_question(
                InterviewQuestion.model_validate(current),
                role=job.title if job is not None else None,
            )
            normalized_payload = normalized_current.model_dump(mode="json")
            if normalized_payload != current:
                session.current_question_json = normalized_current.model_dump_json()
                current = normalized_payload
                changed = True
        except (TypeError, ValueError):
            pass
        question_id = str(current.get("question_id") or "")
        if question_id.startswith("follow-up") or question_id.endswith("-FU"):
            if session.current_question_kind != "follow_up":
                session.current_question_kind = "follow_up"
                changed = True
            if session.follow_up_count < 1:
                session.follow_up_count = 1
                changed = True
        elif question_id.startswith("core-"):
            try:
                core_index = max(0, int(question_id.rsplit("-", 1)[-1]) - 1)
            except ValueError:
                core_index = session.current_core_index
            if session.current_core_index != core_index:
                session.current_core_index = core_index
                changed = True
    if not session.question_plan_json or session.question_plan_json == "[]":
        if isinstance(current, dict) and job is not None:
            try:
                adaptive = InterviewQuestion.model_validate(current)
                from app.interviews.service import build_question_plan

                plan = build_question_plan(role=job.title, adaptive_question=adaptive)
                session.question_plan_json = json.dumps(
                    [item.model_dump(mode="json") for item in plan], ensure_ascii=False
                )
                session.core_question_count = len(plan)
                changed = True
            except Exception:
                pass
    if changed:
        db.flush()
    return turns


def _serialize_interview(db: Session, session: InterviewSession) -> dict[str, object]:
    job = db.get(Job, session.job_id)
    turns = _repair_legacy_state(db, session, job)
    serialized_turns: list[dict[str, object]] = []
    for turn in turns:
        try:
            evaluation = json.loads(turn.evaluation_json)
        except (TypeError, ValueError):
            evaluation = {}
        display_question = turn.question
        try:
            display_question = normalize_interview_question(
                InterviewQuestion(
                    provider=session.provider,
                    question_id=f"core-{turn.sequence}",
                    question=turn.question,
                    competency="综合表达与岗位匹配",
                ),
                role=job.title if job is not None else None,
            ).question
        except (TypeError, ValueError):
            pass
        serialized_turns.append(
            {
                "id": turn.id,
                "sequence": turn.sequence,
                "question": display_question,
                "answer": turn.answer,
                "evaluation": evaluation,
                "emotion": json.loads(turn.emotion_json) if turn.emotion_json else None,
                "assistant_content": turn.assistant_content,
                "created_at": turn.created_at,
            }
        )
    try:
        final_report = json.loads(session.final_report_json) if session.final_report_json else None
    except (TypeError, ValueError):
        final_report = None
    if session.status == "completed" and final_report is None:
        final_report = build_final_report(turns)
    try:
        current_question = json.loads(session.current_question_json)
    except (TypeError, ValueError):
        current_question = None
    if isinstance(current_question, dict):
        try:
            current_question = normalize_interview_question(
                InterviewQuestion.model_validate(current_question),
                role=job.title if job is not None else None,
            ).model_dump(mode="json")
        except (TypeError, ValueError):
            current_question = None
    if session.status == "completed":
        current_question = None
    progress = serialize_progress(session)
    return {
        "id": session.id,
        "status": session.status,
        "provider": session.provider,
        "rubric_version": session.rubric_version,
        "question": current_question,
        "question_index": min(progress["turns_answered"] + (1 if session.status == "active" else 0), progress["max_turns"]),
        "question_total": progress["max_turns"],
        "progress": progress,
        "turns": serialized_turns,
        "final_report": final_report,
        "job": {
            "id": job.id,
            "title": job.title,
            "company": job.company,
        }
        if job is not None
        else None,
    }


@router.post("/{session_id}/emotion/analyze", response_model=EmotionObservation)
async def analyze_interview_emotion(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> EmotionObservation:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    if session.status != "active":
        raise AppError(409, "interview_not_active", "Interview request failed")
    if get_settings().deployment_mode == "server-demo":
        raise AppError(
            503,
            "capability_unavailable",
            "当前服务器演示版未部署 YOLO 情绪分析服务。",
        )
    allowed = {"image/jpeg", "image/png", "image/webp"}
    media_type = file.content_type or "application/octet-stream"
    if media_type not in allowed:
        raise AppError(415, "unsupported_emotion_frame", "Only JPEG, PNG and WebP images are accepted")
    settings = get_settings()
    content = await file.read(settings.max_emotion_frame_size_mb * 1024 * 1024 + 1)
    if not content or len(content) > settings.max_emotion_frame_size_mb * 1024 * 1024:
        raise AppError(413, "emotion_frame_too_large", "Emotion frame is empty or too large")
    try:
        with LocalAIClients(settings) as clients:
            observation = clients.analyze_emotion(
                content,
                filename=file.filename or "emotion-frame.jpg",
                media_type=media_type,
            )
        samples = _load_emotion_samples(session)
        samples.append(observation.model_dump(mode="json"))
        session.emotion_samples_json = json.dumps(samples[-20:], ensure_ascii=False)
        db.commit()
        return observation
    except AIServiceError as error:
        raise AppError(503, error.code, "Emotion analysis service is unavailable") from error

@router.post("", status_code=status.HTTP_201_CREATED)
def start_interview(
    payload: InterviewStartRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    resume = db.get(ResumeFile, payload.resume_id)
    job = db.get(Job, payload.job_id)
    if resume is None or resume.student_id != current_user.id:
        raise AppError(404, "resume_not_found", "Interview request failed")
    if job is None:
        raise AppError(404, "job_not_found", "Interview request failed")
    if not resume.parsed_text:
        raise AppError(409, "resume_not_parsed", "Interview request failed")
    gateway = build_agent_gateway(get_settings(), db=db, owner_id=current_user.id)
    adaptive_question = gateway.start_interview(resume.parsed_text, job.description)
    scenario = db.scalar(
        select(SimulationScenario)
        .where(
            SimulationScenario.status == "active",
            SimulationScenario.category == "interview",
        )
        .order_by(SimulationScenario.updated_at.desc())
    )
    scenario_steps = json.loads(scenario.steps_json) if scenario else None
    question_plan = build_configured_question_plan(
        role=job.title,
        adaptive_question=adaptive_question,
        scenario_steps=scenario_steps,
        core_question_count=len(scenario_steps) if scenario_steps else 6,
    )
    question = question_plan[0]
    session = InterviewSession(
        student_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        provider=adaptive_question.provider,
        question_plan_json=json.dumps(
            [item.model_dump(mode="json") for item in question_plan], ensure_ascii=False
        ),
        current_question_json=question.model_dump_json(),
        current_core_index=0,
        current_question_kind="core",
        follow_up_count=0,
        total_turns=0,
        max_follow_ups=2,
        core_question_count=len(question_plan),
        rubric_version=f"scenario:{scenario.id}" if scenario else "interview-v1",
        rubric_json=scenario.rubric_json
        if scenario
        else json.dumps(
            ["content_completeness", "job_relevance", "answer_structure", "evidence_quality"]
        ),
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "status": session.status,
        "provider": session.provider,
        "rubric_version": session.rubric_version,
        "core_question_count": session.core_question_count,
        "question_index": 1,
        "question_total": session.core_question_count + session.max_follow_ups,
        "question": question.model_dump(mode="json"),
        "progress": serialize_progress(session),
    }


@router.get("")
def list_interviews(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    sessions = db.scalars(
        select(InterviewSession)
        .where(InterviewSession.student_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
        .limit(12)
    ).all()
    return [_serialize_interview(db, item) for item in sessions]


@router.get("/{session_id}")
def read_interview(
    session_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    return _serialize_interview(db, session)


@router.post("/{session_id}/recordings", status_code=status.HTTP_202_ACCEPTED)
def upload_interview_recording(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    if session.status != "active":
        raise AppError(409, "interview_not_active", "Interview request failed")
    ensure_task_available(AITaskType.speech_transcription)
    media_type = file.content_type or "application/octet-stream"
    suffixes = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }
    if media_type not in suffixes:
        raise AppError(415, "unsupported_audio", "Interview request failed")
    settings = get_settings()
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise AppError(413, "audio_too_large", "Interview request failed")
    storage_ref = build_storage(settings).put_bytes(
        f"media/recordings/{uuid4().hex}{suffixes[media_type]}",
        content,
        media_type=media_type,
    )
    artifact = MediaArtifact(
        owner_id=current_user.id,
        session_id=session.id,
        kind="recording",
        media_type=media_type,
        storage_path=storage_ref,
        size_bytes=len(content),
        expires_at=utc_now() + timedelta(days=settings.audio_retention_days),
    )
    db.add(artifact)
    db.flush()
    task = enqueue_task(
        db,
        task_type=AITaskType.speech_transcription,
        owner_id=current_user.id,
        input_data={
            "storage_ref": storage_ref,
            "media_type": media_type,
            "session_id": session.id,
            "artifact_id": artifact.id,
        },
    )
    db.commit()
    return {"task_id": task.id, "artifact_id": artifact.id, "status": task.status}


@router.post("/{session_id}/speech", status_code=status.HTTP_202_ACCEPTED)
def synthesize_interview_question(
    session_id: str,
    payload: InterviewSpeechRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    if session.status != "active":
        raise AppError(409, "interview_not_active", "Interview request failed")
    task = enqueue_task(
        db,
        task_type=AITaskType.speech_synthesis,
        owner_id=current_user.id,
        input_data={"text": payload.text.strip(), "session_id": session.id},
    )
    db.commit()
    return {"task_id": task.id, "status": task.status}


@router.post("/{session_id}/answers")
def answer_interview_question(
    session_id: str,
    payload: InterviewAnswerRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    if session.status != "active":
        raise AppError(409, "interview_not_active", "婵☆垪鍓濈€氭瑩妫冮姀锝囨Ц鐎规瓕灏欑划锛勭磼閹惧瓨灏嗛柨娑樼焷椤曨剙顕ｉ埀顒佹叏鐎ｂ晝顏遍柛锔惧劋閺屽﹪妫冮姀锝囨Ц")
    job = db.get(Job, session.job_id)
    if job is None:
        raise AppError(404, "job_not_found", "Interview request failed")
    turns = _repair_legacy_state(db, session, job)
    question_payload = json.loads(session.current_question_json)
    if not isinstance(question_payload, dict) or not question_payload.get("question"):
        raise AppError(409, "interview_question_missing", "瑜版挸澧犻棃銏ｇ槸妫版娲版稉宥呯摠閸︻煉绱濈拠宄板煕閺傛澘鎮楅柌宥堢槸")
    question = normalize_interview_question(
        InterviewQuestion.model_validate(question_payload),
        role=job.title,
    ).model_dump(mode="json")
    evaluation = build_agent_gateway(
        get_settings(), db=db, owner_id=current_user.id
    ).evaluate_answer(question["question"], payload.answer, job.description)
    emotion_summary = _summarize_emotion(_load_emotion_samples(session))
    if emotion_summary and emotion_summary.get("stability_score") is not None:
        evaluation = evaluation.model_copy(
            update={
                "emotion_stability": int(emotion_summary["stability_score"]),
                "feedback": [
                    *evaluation.feedback,
                    "摄像头分析仅用于表达训练参考，不代表心理状态或录用判断。",
                ],
            }
        )
    turn_number = len(turns) + 1
    db.add(
        InterviewTurn(
            session_id=session.id,
            student_id=current_user.id,
            sequence=turn_number,
            question=question["question"],
            answer=payload.answer,
            evaluation_json=evaluation.model_dump_json(),
            emotion_json=json.dumps(emotion_summary, ensure_ascii=False)
            if emotion_summary
            else None,
        )
    )
    session.total_turns = turn_number
    session.emotion_samples_json = "[]"
    if emotion_summary:
        session.emotion_summary_json = json.dumps(emotion_summary, ensure_ascii=False)
    question_plan = load_question_plan(session, role=job.title)
    if not question_plan:
        raise AppError(409, "interview_plan_missing", "Interview request failed")
    next_question = None
    next_kind = None
    can_follow_up = (
        session.current_question_kind == "core"
        and evaluation.follow_up is not None
        and session.follow_up_count < session.max_follow_ups
        and turn_number < len(question_plan) + session.max_follow_ups
    )
    if can_follow_up:
        session.follow_up_count += 1
        next_question = normalize_interview_question(
            evaluation.follow_up.model_copy(
                update={"question_id": f"follow-up-{session.follow_up_count}"}
            ),
            role=job.title,
            fallback_competency="证据充分度",
        )
        next_kind = "follow_up"
    else:
        session.current_core_index += 1
        if (
            session.current_core_index < len(question_plan)
            and turn_number < len(question_plan) + session.max_follow_ups
        ):
            next_question = question_plan[session.current_core_index]
            next_kind = "core"

    speech_task = None
    final_report = None
    if next_question is not None:
        session.current_question_json = next_question.model_dump_json()
        session.current_question_kind = str(next_kind)
        if is_task_available(AITaskType.speech_synthesis):
            speech_task = enqueue_task(
                db,
                task_type=AITaskType.speech_synthesis,
                owner_id=current_user.id,
                input_data={
                    "text": next_question.question,
                    "session_id": session.id,
                },
            )
    else:
        session.status = "completed"
        session.completed_at = utc_now()
        session.current_question_json = "null"
        session.current_question_kind = "completed"
        db.flush()
        turns = db.scalars(
            select(InterviewTurn)
            .where(InterviewTurn.session_id == session.id)
            .order_by(InterviewTurn.sequence)
        ).all()
        final_report = build_final_report(turns)
        session.final_report_json = json.dumps(final_report, ensure_ascii=False)
    db.commit()
    payload_data = evaluation.model_dump(mode="json")
    payload_data.pop("follow_up")
    if payload_data.get("emotion_stability") is None:
        payload_data.pop("emotion_stability", None)
    provider = payload_data.pop("provider", None)
    return {
        "evaluation": payload_data,
        "next_question": next_question.model_dump(mode="json") if next_question else None,
        "follow_up": next_question.model_dump(mode="json") if next_question and next_kind == "follow_up" else None,
        "status": session.status,
        "provider": provider,
        "speech_task_id": speech_task.id if speech_task else None,
        "question_index": min(
            serialize_progress(session)["turns_answered"] + (1 if session.status == "active" else 0),
            serialize_progress(session)["max_turns"],
        ),
        "question_total": serialize_progress(session)["max_turns"],
        "progress": serialize_progress(session),
        "final_report": final_report,
    }


def _build_interview_dialogue_request(
    *,
    turn: InterviewTurn,
    result: dict[str, object],
    job: Job,
) -> ComposeAnswerRequest:
    evaluation = result.get("evaluation")
    evaluation_data = evaluation if isinstance(evaluation, dict) else {}
    scores = " / ".join(
        f"{label}{evaluation_data.get(key, 0)}分"
        for key, label in (
            ("content_completeness", "内容完整度"),
            ("job_relevance", "岗位相关性"),
            ("answer_structure", "表达结构"),
            ("evidence_quality", "证据质量"),
        )
    )
    feedback = evaluation_data.get("feedback")
    feedback_text = "；".join(str(item) for item in feedback) if isinstance(feedback, list) else ""
    next_question = result.get("next_question")
    next_text = (
        str(next_question.get("question"))
        if isinstance(next_question, dict) and next_question.get("question")
        else "本场面试已完成，请用简洁中文总结表现并给出下一步行动。"
    )
    summary = (
        f"本轮面试回答评分：{scores}。反馈：{feedback_text or '暂无额外反馈'}。"
        f"下一题：{next_text}。"
    )
    return ComposeAnswerRequest(
        messages=[
            ConversationMessage(role="assistant", content=turn.question),
            ConversationMessage(role="user", content=turn.answer),
        ],
        specialist_outputs=[SpecialistOutput(agent="interview", summary=summary)],
    )


@router.post("/{session_id}/answers/stream", response_class=StreamingResponse)
def stream_interview_answer(
    request: Request,
    session_id: str,
    payload: InterviewAnswerRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Score a turn in the background and stream the interviewer response over SSE."""
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    if session.status != "active":
        raise AppError(409, "interview_not_active", "婵☆垪鍓濈€氭瑩妫冮姀锝囨Ц鐎规瓕灏欑划锛勭磼閹惧瓨灏嗛柨娑樼焷椤曨剙顕ｉ埀顒佹叏鐎ｂ晝顏遍柛锔惧劋閺屽﹪妫冮姀锝囨Ц")
    if db.get(Job, session.job_id) is None:
        raise AppError(404, "job_not_found", "Interview request failed")
    try:
        initial_question = json.loads(session.current_question_json)
    except (TypeError, ValueError) as error:
        raise AppError(
            500, "interview_stream_state_invalid", "闂傚牄鍨奸惁顖炴偐閼哥鍋撴担瑙勶骏婵炲娲樻禒顔藉緞瀹ュ繒绀夐悹鍥у槻閸╂盯寮弶鎸庡€甸梺鎻掔Х閻?"
        ) from error
    try:
        job = db.get(Job, session.job_id)
        if job is not None and isinstance(initial_question, dict):
            initial_question = normalize_interview_question(
                InterviewQuestion.model_validate(initial_question),
                role=job.title,
            ).model_dump(mode="json")
    except (TypeError, ValueError):
        pass
    database_bind = db.get_bind()
    owner_id = current_user.id

    async def event_stream():
        yield _sse(
            "turn.started",
            {
                "session_id": session_id,
                "question": initial_question.get("question", ""),
                "status": "evaluating",
            },
        )
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

        def enqueue(kind: str, value: object) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (kind, value))

        def run_model() -> None:
            usage_session_factory = sessionmaker(
                bind=database_bind,
                autoflush=False,
                expire_on_commit=False,
            )
            with usage_session_factory() as usage_db:
                try:
                    work_factory = sessionmaker(
                        bind=database_bind,
                        autoflush=False,
                        expire_on_commit=False,
                    )
                    with work_factory() as work_db:
                        result = answer_interview_question(
                            session_id,
                            payload,
                            current_user,
                            work_db,
                        )
                        work_session = work_db.get(InterviewSession, session_id)
                        work_job = (
                            work_db.get(Job, work_session.job_id)
                            if work_session is not None
                            else None
                        )
                        work_turn = work_db.scalar(
                            select(InterviewTurn)
                            .where(InterviewTurn.session_id == session_id)
                            .order_by(InterviewTurn.sequence.desc())
                        )
                        if work_session is None or work_job is None or work_turn is None:
                            raise AppError(
                                500,
                                "interview_stream_state_invalid",
                                "闂傚牄鍨奸惁顖炴偐閼哥鍋撴担瑙勶骏婵炲娲樻禒顔藉緞瀹ュ繒绀夐悹鍥у槻閸╂盯寮弶鎸庡€甸梺鎻掔Х閻?,"
                            )
                        turn_id = work_turn.id
                        compose_request = _build_interview_dialogue_request(
                            turn=work_turn,
                            result=result,
                            job=work_job,
                        )
                        evaluated_payload = {
                            "session_id": session_id,
                            "evaluation": result.get("evaluation", {}),
                            "next_question": result.get("next_question"),
                            "status": result.get("status"),
                            "provider": result.get("provider"),
                            "speech_task_id": result.get("speech_task_id"),
                            "progress": result.get("progress"),
                            "final_report": result.get("final_report"),
                        }
                        enqueue("evaluated", evaluated_payload)
                    gateway = build_conversation_gateway(
                        get_settings(),
                        db=usage_db,
                        owner_id=owner_id,
                    )
                    answer = gateway.compose_answer_stream(
                        compose_request,
                        on_delta=lambda delta: enqueue("delta", delta),
                        on_reset=lambda: enqueue("reset", None),
                    )
                    persisted_turn = usage_db.get(InterviewTurn, turn_id)
                    if persisted_turn is not None:
                        persisted_turn.assistant_content = answer.content
                        usage_db.flush()
                    enqueue("done", {"content": answer.content, "provider": answer.provider})
                except Exception as error:  # provider failures are returned as typed stream events
                    code = getattr(error, "code", "interview_stream_failed")
                    message = getattr(error, "message", str(error)) or "Interview stream failed"
                    enqueue("error", {"code": str(code), "message": str(message)[:300]})
                finally:
                    try:
                        usage_db.commit()
                    except Exception:
                        usage_db.rollback()

        task = asyncio.create_task(asyncio.to_thread(run_model))
        while True:
            if await request.is_disconnected():
                return
            kind, value = await queue.get()
            if kind == "evaluated":
                evaluated = value if isinstance(value, dict) else {"session_id": session_id}
                yield _sse("turn.evaluated", evaluated)
                continue
            if kind == "delta":
                yield _sse("assistant.delta", {"text": str(value)})
                continue
            if kind == "reset":
                yield _sse("assistant.reset", {"reason": "provider_retry"})
                continue
            if kind == "done":
                done = value if isinstance(value, dict) else {}
                yield _sse("assistant.done", done)
                break
            error = value if isinstance(value, dict) else {"message": "Interview stream failed"}
            yield _sse("stream.error", error)
            break
        await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{session_id}/complete")
def complete_interview(
    session_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "Interview request failed")
    turns = db.scalars(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == session.id)
        .order_by(InterviewTurn.sequence)
    ).all()
    report = (
        json.loads(session.final_report_json)
        if session.final_report_json
        else build_final_report(turns)
    )
    session.status = "completed"
    session.completed_at = session.completed_at or utc_now()
    session.final_report_json = json.dumps(report, ensure_ascii=False)
    session.current_question_json = "null"
    session.current_question_kind = "completed"
    db.commit()
    return {
        "status": session.status,
        "progress": serialize_progress(session),
        "final_report": report,
    }
