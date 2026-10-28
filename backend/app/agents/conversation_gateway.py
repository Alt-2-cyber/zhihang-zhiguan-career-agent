import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.agents.conversation_contracts import (
    Citation,
    ComposeAnswerRequest,
    ConversationAnswer,
    ConversationMessage,
    ConversationPlan,
    MemorySummary,
    MemorySummaryRequest,
    PlanTurnRequest,
    SpecialistDecision,
    SpecialistOutput,
    SpecialistRequest,
    SpecialistSummaryRequest,
    SuggestedAction,
    ToolRequest,
)
from app.agents.conversation_prompts import build_conversation_system_prompt
from app.agents.failover import ProviderError, _online_provider_unavailable
from app.agents.fastgpt import AgentOutputError
from app.agents.redaction import redact_data
from app.agents.skills import PromptResolver
from app.agents.usage import ModelCallUsage, calculate_cost_micros, parse_usage

ContractT = TypeVar("ContractT", bound=BaseModel)
INCOMPLETE_LEAD_IN = re.compile(
    r"(?:以下(?:是|为).{0,60}(?:信息|内容|资源|建议|方案|步骤|结果|路线)|"
    r"(?:具体|详细)(?:内容)?如下)[：:。.!！]?$"
)
ROLE_QUERY = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9+#.]{1,16}"
    r"(?:工程师|设计师|分析师|产品经理|运营|会计|教师|律师|医生)"
)
ROLE_INTENT_PREFIX = re.compile(
    r"^(?:请帮我|帮我|请|我想要|我想|我要|我希望|想要|想做|介绍一下|介绍|"
    r"了解一下|了解|应聘|申请|成为|转行|准备面试|准备|面试)+"
)


def _latest_user_content(messages: list[ConversationMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content if messages else ""


def _requires_grounded_weekly_actions(messages: list[ConversationMessage]) -> bool:
    content = _latest_user_content(messages)
    evidence_terms = ("就业画像", "求职计划", "投递记录", "最近投递", "本周最优先", "三项行动")
    return sum(1 for term in evidence_terms if term in content) >= 2


def _covers_weekly_actions(plan: ConversationPlan) -> bool:
    agents = {step.agent for step in plan.steps}
    return {"career", "application"}.issubset(agents)


def _intent_agent_allowlist(messages: list[ConversationMessage]) -> set[str] | None:
    """Return a narrow specialist set for single-domain user requests."""
    content = _latest_user_content(messages)
    if any(term in content for term in ("面试", "模拟面试", "面试问题")):
        allowed = {"interview"}
        if _requested_role(messages):
            allowed.add("job")
        return allowed
    if any(term in content for term in ("课程", "学习", "考试", "技能差距")):
        return {"learning"}
    if any(term in content for term in ("职场模拟", "沟通训练", "汇报训练", "冲突处理")):
        return {"workplace"}
    if any(term in content for term in ("入职", "试用期", "企业评价", "回访")):
        return {"employment"}
    if any(term in content for term in ("岗位情报", "招聘趋势", "招聘来源")):
        return {"intelligence"}
    return None


def _constrain_plan_to_intent(
    messages: list[ConversationMessage], plan: ConversationPlan
) -> ConversationPlan:
    allowed = _intent_agent_allowlist(messages)
    if not allowed:
        return plan
    kept: list = []
    seen_agents: set[str] = set()
    for step in plan.steps:
        if step.agent not in allowed or step.agent in seen_agents:
            continue
        seen_agents.add(step.agent)
        kept.append(step)
    if not kept:
        agent = "job" if "job" in allowed and _requested_role(messages) else next(iter(allowed))
        kept = [
            {
                "id": agent,
                "agent": agent,
                "instruction": "仅处理用户当前请求，并引用真实业务数据。",
                "depends_on": [],
            }
        ]
        return ConversationPlan(intent=plan.intent, steps=kept)
    known_ids: set[str] = set()
    normalized = []
    for step in kept:
        normalized.append(step.model_copy(update={"depends_on": [item for item in step.depends_on if item in known_ids]}))
        known_ids.add(step.id)
    return plan.model_copy(update={"steps": normalized})


def _requires_grounded_tools(request: SpecialistRequest) -> bool:
    if _requires_grounded_weekly_actions(request.messages):
        return request.step.agent in {"career", "application"}
    return request.step.agent in {
        "career",
        "job",
        "resume",
        "application",
        "interview",
        "counselor",
        "learning",
        "workplace",
        "intelligence",
        "employment",
    }


def _dedupe_tool_requests(items: list[ToolRequest]) -> list[ToolRequest]:
    result: list[ToolRequest] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.name, json.dumps(item.arguments, ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


AGENT_LABELS = {
    "career": "职业规划",
    "job": "岗位分析",
    "resume": "简历建议",
    "application": "投递管理",
    "interview": "面试准备",
    "counselor": "就业帮扶",
    "learning": "学习成长",
    "workplace": "职场训练",
    "intelligence": "岗位情报",
    "employment": "就业质量",
}
TOOL_LABELS = {
    "profile.get": "就业画像",
    "plan.get": "求职计划",
    "tasks.list": "计划任务",
    "jobs.get": "岗位详情",
    "jobs.search_internal": "校内岗位",
    "jobs.search_public": "公开岗位",
    "resumes.list": "简历材料",
    "applications.list": "投递记录",
    "dashboard.class_summary": "班级概览",
    "risks.list": "风险提醒",
    "growth.overview": "学习成长",
    "workplace.sessions": "职场训练",
    "workplace.deliverables": "工作交付物",
    "intelligence.overview": "岗位情报",
    "employment.records": "就业记录",
}
STATUS_LABELS = {
    "active": "进行中",
    "confirmed": "已确认",
    "completed": "已完成",
    "done": "已完成",
    "pending": "待处理",
    "todo": "待完成",
    "queued": "排队中",
    "in_progress": "进行中",
    "applied": "已投递",
    "interview": "面试中",
    "offered": "已录用",
    "closed": "已关闭",
}


def _iter_sse_data(response: httpx.Response):
    data_lines: list[str] = []
    for raw_line in response.iter_lines():
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _decode_json_string_prefix(raw: str) -> tuple[str, bool]:
    """Decode the safe prefix of a JSON string value while it is still arriving."""
    safe_end = 0
    index = 0
    while index < len(raw):
        character = raw[index]
        if character == '"':
            try:
                return json.loads(f'"{raw[:index]}"'), True
            except ValueError:
                return "", False
        if character == "\\":
            if index + 1 >= len(raw):
                break
            escaped = raw[index + 1]
            if escaped == "u":
                if index + 6 > len(raw) or any(
                    item not in "0123456789abcdefABCDEF" for item in raw[index + 2 : index + 6]
                ):
                    break
                index += 6
            elif escaped in '"\\/bfnrt':
                index += 2
            else:
                break
        else:
            if ord(character) < 0x20:
                break
            index += 1
        safe_end = index
    if safe_end == 0:
        return "", False
    try:
        return json.loads(f'"{raw[:safe_end]}"'), False
    except ValueError:
        return "", False


class _JsonContentStream:
    def __init__(self, on_delta: Callable[[str], None]) -> None:
        self.on_delta = on_delta
        self.buffer = ""
        self.emitted = ""

    def feed(self, fragment: str) -> None:
        self.buffer += fragment
        match = re.search(r'"content"\s*:\s*"', self.buffer)
        if match is None:
            return
        decoded, _complete = _decode_json_string_prefix(self.buffer[match.end() :])
        if not decoded.startswith(self.emitted):
            return
        delta = decoded[len(self.emitted) :]
        if delta:
            self.on_delta(delta)
            self.emitted = decoded


def _chunk_text(value: str, *, size: int = 80):
    for offset in range(0, len(value), size):
        yield value[offset : offset + size]


def _requested_role(messages: list[ConversationMessage]) -> str | None:
    user_content = next(
        (message.content for message in reversed(messages) if message.role == "user"), ""
    )
    normalized = ROLE_INTENT_PREFIX.sub("", user_content.strip())
    matches = list(ROLE_QUERY.finditer(normalized))
    if not matches:
        # Keep the check useful for sentences that put the request before the
        # role, while selecting the final role phrase instead of the whole
        # sentence (for example, "我要面试前端开发工程师").
        matches = list(ROLE_QUERY.finditer(user_content))
    return matches[-1].group(0) if matches else None


def _answer_is_incomplete(request: ComposeAnswerRequest, content: str) -> bool:
    normalized = content.strip()
    role = _requested_role(request.messages)
    if role and role not in normalized:
        return True
    if INCOMPLETE_LEAD_IN.search(normalized):
        return True
    minimum_length = min(180, 40 + len(request.specialist_outputs) * 20)
    return len(request.specialist_outputs) > 1 and len(normalized) < minimum_length


def _readable_answer(content: str) -> str:
    normalized = re.sub(r"\r\n?", "\n", content.strip())
    normalized = re.sub(r"\*\*(.*?)\*\*", r"\1", normalized)
    normalized = _hide_internal_tool_jargon(normalized)
    normalized = re.sub(r"(?<!\n)([。！？])(?=\S)", r"\1\n\n", normalized)
    normalized = re.sub(r"[；;]\s*(?=\d{1,2}\s*[）)])", "\n", normalized)
    normalized = re.sub(r"(?<!\n)(?=\d{1,2}\s*[）)])", "\n", normalized)
    normalized = re.sub(r"^(\d{1,2})\s*[）)]\s*", r"\1. ", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"(?<!\n)(建议|行动建议|求职建议)：\s*", r"\n\n\1：\n", normalized)
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


def _hide_internal_tool_jargon(content: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append(raw_line)
            continue
        if re.search(
            r"(已使用|使用|调用|通过)\s*[a-z][a-z0-9_.]{2,}\s*(工具|tool)",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        if re.search(r"\b[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\b", line) and re.search(
            r"(工具|调用|tool|schema|JSON|Agent\s*编排)",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        cleaned_lines.append(raw_line)
    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\b[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\b\s*工具", "业务数据", cleaned)
    return cleaned


def _merge_citations(request: ComposeAnswerRequest, answer: ConversationAnswer) -> list[Citation]:
    return _dedupe_citations(
        answer.citations + [
            item for output in request.specialist_outputs for item in output.citations
        ]
    )


def _dedupe_citations(source: list[Citation]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    for citation in source:
        key = (citation.source_id, citation.url, citation.label)
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation)
    return citations[:30]


def _merge_actions(
    request: ComposeAnswerRequest, answer: ConversationAnswer
) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    seen: set[tuple[str, str, str]] = set()
    for action in answer.suggested_actions + request.pending_actions:
        key = (
            action.tool_name,
            action.title,
            json.dumps(action.arguments, ensure_ascii=False, sort_keys=True, default=str),
        )
        if key in seen:
            continue
        seen.add(key)
        actions.append(action)
    return actions[:10]


def _clean_text(value: object, *, limit: int = 220) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit].rstrip()


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _status_label(value: object) -> str:
    text = _clean_text(value, limit=40)
    return STATUS_LABELS.get(text, text)


def _first_text(record: dict[str, object], *keys: str, limit: int = 160) -> str:
    for key in keys:
        text = _clean_text(record.get(key), limit=limit)
        if text:
            return text
    return ""


def _task_line(item: object) -> str:
    record = _as_dict(item)
    title = _first_text(record, "title", "name", limit=80) or "未命名任务"
    due_date = _clean_text(record.get("due_date"), limit=20)
    status = _status_label(record.get("status"))
    criteria = _clean_text(record.get("acceptance_criteria"), limit=120)
    details = [part for part in [f"{due_date} 截止" if due_date else "", status] if part]
    suffix = f"（{'，'.join(details)}）" if details else ""
    return f"{title}{suffix}" + (f"，验收标准：{criteria}" if criteria else "")


def _summarize_profile(record: dict[str, object]) -> list[str]:
    if not record:
        return ["暂未读取到已确认的就业画像，建议先完善简历和目标偏好。"]
    lines: list[str] = []
    summary = _first_text(record, "summary", limit=220)
    if summary:
        lines.append(f"就业画像：{summary}")
    strengths = []
    for item in _as_list(record.get("strengths"))[:4]:
        strength = _as_dict(item)
        name = _first_text(strength, "name", limit=80)
        level = _first_text(strength, "level", limit=80)
        if name:
            strengths.append(f"{name}（{level}）" if level else name)
    if strengths:
        lines.append(f"优势能力：{'、'.join(strengths)}。")
    gaps = [_clean_text(item, limit=90) for item in _as_list(record.get("gaps"))[:4]]
    gaps = [item for item in gaps if item]
    if gaps:
        lines.append(f"待补短板：{'、'.join(gaps)}。")
    constraints = [
        _clean_text(item, limit=90) for item in _as_list(record.get("constraints"))[:4]
    ]
    constraints = [item for item in constraints if item]
    if constraints:
        lines.append(f"约束条件：{'、'.join(constraints)}。")
    return lines or ["已读取就业画像，但当前可用于判断的信息较少。"]


def _summarize_plan(record: dict[str, object]) -> list[str]:
    if not record:
        return ["暂未找到求职计划，建议先生成一份按周推进的目标计划。"]
    lines: list[str] = []
    primary = _first_text(record, "primary_role", limit=80)
    backups = [_clean_text(item, limit=60) for item in _as_list(record.get("backup_roles"))[:3]]
    backups = [item for item in backups if item]
    if primary:
        backup_text = f"，备选方向：{'、'.join(backups)}" if backups else ""
        lines.append(f"求职目标：主攻 {primary}{backup_text}。")
    rationale = _first_text(record, "rationale", limit=220)
    if rationale:
        lines.append(f"规划依据：{rationale}")
    tasks = _as_list(record.get("tasks"))
    open_tasks = [
        task for task in tasks if _as_dict(task).get("status") not in {"completed", "done"}
    ][:3]
    if open_tasks:
        lines.append(f"近期任务：{'；'.join(_task_line(task) for task in open_tasks)}。")
    return lines or ["已读取求职计划，但计划内容还需要补充目标和任务。"]


def _summarize_items(tool_name: str, items: list[object]) -> list[str]:
    label = TOOL_LABELS.get(tool_name, tool_name)
    if not items:
        return [f"{label}：暂未读取到相关记录。"]
    if tool_name == "tasks.list":
        completed = sum(
            1 for item in items if _as_dict(item).get("status") in {"completed", "done"}
        )
        pending = len(items) - completed
        open_items = [
            item for item in items if _as_dict(item).get("status") not in {"completed", "done"}
        ][:3]
        lines = [f"任务进度：共 {len(items)} 项，待推进 {pending} 项，已完成 {completed} 项。"]
        if open_items:
            lines.append(f"优先行动：{'；'.join(_task_line(item) for item in open_items)}。")
        return lines
    highlights = []
    for item in items[:4]:
        record = _as_dict(item)
        title = _first_text(record, "title", "name", "company", "primary_role", limit=80)
        status = _status_label(record.get("status") or record.get("stage"))
        if title:
            highlights.append(f"{title}（{status}）" if status else title)
    if highlights:
        return [f"{label}：共 {len(items)} 条，重点包括 {'、'.join(highlights)}。"]
    return [f"{label}：共读取到 {len(items)} 条记录，建议在详情页继续查看。"]


def _summarize_generic_record(tool_name: str, record: dict[str, object]) -> list[str]:
    label = TOOL_LABELS.get(tool_name, tool_name)
    if not record:
        return [f"{label}：暂未读取到可用记录。"]
    summary = _first_text(record, "summary", "rationale", "description", "title", "name")
    status = _status_label(record.get("status") or record.get("stage"))
    if summary and status:
        return [f"{label}：{summary}（{status}）。"]
    if summary:
        return [f"{label}：{summary}。"]
    if status:
        return [f"{label}：当前状态为 {status}。"]
    return [f"{label}：已读取到记录，建议结合右侧工具详情进一步核对。"]


def _summarize_tool_result(item: dict[str, object]) -> list[str]:
    tool_name = _clean_text(item.get("tool_name"), limit=80)
    data = _as_dict(item.get("data"))
    record = _as_dict(data.get("record"))
    items = _as_list(data.get("items"))
    if tool_name == "profile.get":
        return _summarize_profile(record)
    if tool_name == "plan.get":
        return _summarize_plan(record)
    if items:
        return _summarize_items(tool_name, items)
    if record or "record" in data:
        return _summarize_generic_record(tool_name, record)
    return [f"{TOOL_LABELS.get(tool_name, tool_name or '工具结果')}：已完成读取。"]


def _tool_citations(item: dict[str, object]) -> list[Citation]:
    citations: list[Citation] = []
    for citation in _as_list(item.get("citations")):
        try:
            citations.append(Citation.model_validate(citation))
        except ValidationError:
            continue
    return citations


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = _clean_text(item, limit=500)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _enrich_answer(
    request: ComposeAnswerRequest,
    answer: ConversationAnswer,
    provider: str,
) -> ConversationAnswer:
    citations = _merge_citations(request, answer)
    actions = _merge_actions(request, answer)
    advice = _readable_answer(answer.content)[:6_500].rstrip()
    if not advice:
        advice = _readable_answer(
            "\n".join(output.summary for output in request.specialist_outputs)
        )[:6_500].rstrip()
    sections = [f"综合建议\n\n{advice}"]
    if citations:
        resources = ["参考资源"]
        resources.extend(
            f"{index}. {citation.label[:100]}：{citation.excerpt[:140]}"
            for index, citation in enumerate(citations[:8], start=1)
        )
        sections.append("\n".join(resources))
    if actions:
        next_steps = ["下一步行动"]
        next_steps.extend(
            f"{index}. {action.title[:120]}：{action.rationale[:220]}"
            for index, action in enumerate(actions[:5], start=1)
        )
        sections.append("\n".join(next_steps))
    return answer.model_copy(
        update={
            "provider": provider,
            "content": "\n\n".join(sections)[:12_000].rstrip(),
            "citations": citations,
            "suggested_actions": actions,
        }
    )


class ConversationGateway(Protocol):
    provider: str

    def plan_turn(self, request: PlanTurnRequest) -> ConversationPlan: ...

    def decide_specialist(self, request: SpecialistRequest) -> SpecialistDecision: ...

    def summarize_specialist(self, request: SpecialistSummaryRequest) -> SpecialistOutput: ...

    def compose_answer(self, request: ComposeAnswerRequest) -> ConversationAnswer: ...

    def summarize_memory(self, request: MemorySummaryRequest) -> MemorySummary: ...


class OpenAIConversationGateway:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        client: httpx.Client | None = None,
        usage_recorder: Callable[[ModelCallUsage], None] | None = None,
        prompt_version: str | None = None,
        input_cost_per_million_usd: float | None = None,
        output_cost_per_million_usd: float | None = None,
        prompt_resolver: PromptResolver | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.usage_recorder = usage_recorder
        self.prompt_version = prompt_version
        self.input_cost_per_million_usd = input_cost_per_million_usd
        self.output_cost_per_million_usd = output_cost_per_million_usd
        self.prompt_resolver = prompt_resolver

    def plan_turn(self, request: PlanTurnRequest) -> ConversationPlan:
        result = self._invoke("plan_turn", request, ConversationPlan)
        result = _constrain_plan_to_intent(request.messages, result)
        if _requested_role(request.messages) and not any(
            step.agent == "job" for step in result.steps
        ):
            raise AgentOutputError("模型规划未覆盖岗位意图")
        if _requires_grounded_weekly_actions(request.messages) and not _covers_weekly_actions(result):
            raise AgentOutputError("模型规划未覆盖职业规划和投递记录")
        return result

    def decide_specialist(self, request: SpecialistRequest) -> SpecialistDecision:
        result = self._invoke("decide_specialist", request, SpecialistDecision)
        allowed = {item.name for item in request.tool_catalog}
        candidates = [item for item in result.tool_requests if item.name in allowed]
        candidates = _dedupe_tool_requests(candidates)
        if not candidates:
            # A follow-up is allowed to be empty: after the first tool round
            # the model may have no additional evidence to read. Treating an
            # unauthorized or malformed follow-up as a hard Agent failure
            # makes an otherwise successful specialist appear failed.
            if request.tool_results:
                return result.model_copy(update={"tool_requests": []})
            raise AgentOutputError("模型未返回可授权工具")
        return result.model_copy(update={"tool_requests": candidates})

    def summarize_specialist(self, request: SpecialistSummaryRequest) -> SpecialistOutput:
        return self._invoke("summarize_specialist", request, SpecialistOutput)

    def compose_answer(self, request: ComposeAnswerRequest) -> ConversationAnswer:
        result = self._invoke("compose_answer", request, ConversationAnswer)
        if _answer_is_incomplete(request, result.content):
            raise AgentOutputError("回答内容不完整")
        return _enrich_answer(request, result, self.provider)

    def compose_answer_stream(
        self,
        request: ComposeAnswerRequest,
        *,
        on_delta: Callable[[str], None],
        on_reset: Callable[[], None] | None = None,
    ) -> ConversationAnswer:
        try:
            result = self._invoke_stream("compose_answer", request, ConversationAnswer, on_delta)
        except (ProviderError, AgentOutputError):
            # Some OpenAI-compatible gateways expose chat completions but do
            # not implement SSE. Preserve the online provider path in that
            # case instead of silently switching to local rules.
            if on_reset is not None:
                on_reset()
            result = self._invoke("compose_answer", request, ConversationAnswer)
            # Keep the UI progressive even when this provider only supports
            # the regular completion endpoint.
            for chunk in _chunk_text(result.content):
                on_delta(chunk)
        if _answer_is_incomplete(request, result.content):
            raise AgentOutputError("回答内容不完整")
        return _enrich_answer(request, result, self.provider)

    def summarize_memory(self, request: MemorySummaryRequest) -> MemorySummary:
        return self._invoke("summarize_memory", request, MemorySummary)

    def _invoke(
        self,
        operation: str,
        request: BaseModel,
        contract: type[ContractT],
    ) -> ContractT:
        started_at = datetime.now(timezone.utc)
        request_id: str | None = None
        resolved_prompt = (
            self.prompt_resolver.resolve("conversation", operation)
            if self.prompt_resolver is not None
            else None
        )
        prompt_version = resolved_prompt.version if resolved_prompt else self.prompt_version
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": build_conversation_system_prompt(
                        operation,
                        contract,
                        instruction=resolved_prompt.prompt_text if resolved_prompt else None,
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        redact_data(request.model_dump(mode="json")),
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "temperature": 0.2,
        }
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        except (httpx.TimeoutException, httpx.TransportError) as error:
            provider_error = ProviderError(type(error).__name__, retryable=True)
            self._record_failure(
                operation, started_at, provider_error, request_id=request_id, prompt_version=prompt_version
            )
            raise provider_error from error
        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            provider_error = ProviderError(
                f"provider_http_{response.status_code}",
                retryable=retryable,
                status_code=response.status_code,
            )
            self._record_failure(
                operation, started_at, provider_error, request_id=request_id, prompt_version=prompt_version
            )
            raise provider_error
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            result = contract.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            output_error = AgentOutputError("模型未返回符合约定的对话结构")
            self._record_failure(
                operation, started_at, output_error, request_id=request_id, prompt_version=prompt_version
            )
            raise output_error from error
        self._record_success(
            operation,
            started_at,
            parse_usage(payload),
            request_id=request_id,
            prompt_version=prompt_version,
        )
        return result

    def _invoke_stream(
        self,
        operation: str,
        request: BaseModel,
        contract: type[ContractT],
        on_delta: Callable[[str], None],
    ) -> ContractT:
        started_at = datetime.now(timezone.utc)
        request_id: str | None = None
        resolved_prompt = (
            self.prompt_resolver.resolve("conversation", operation)
            if self.prompt_resolver is not None
            else None
        )
        prompt_version = resolved_prompt.version if resolved_prompt else self.prompt_version
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": build_conversation_system_prompt(
                        operation,
                        contract,
                        instruction=resolved_prompt.prompt_text if resolved_prompt else None,
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        redact_data(request.model_dump(mode="json")),
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": True,
            "temperature": 0.2,
        }
        raw_content = ""
        usage: dict[str, int | None] = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
        extractor = _JsonContentStream(on_delta)
        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "text/event-stream",
                },
                json=body,
            ) as response:
                request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                if response.status_code >= 400:
                    retryable = response.status_code == 429 or response.status_code >= 500
                    provider_error = ProviderError(
                        f"provider_http_{response.status_code}",
                        retryable=retryable,
                        status_code=response.status_code,
                    )
                    self._record_failure(
                        operation,
                        started_at,
                        provider_error,
                        request_id=request_id,
                        prompt_version=prompt_version,
                    )
                    raise provider_error
                for raw_event in _iter_sse_data(response):
                    if raw_event.strip() == "[DONE]":
                        break
                    try:
                        payload = json.loads(raw_event)
                    except ValueError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if isinstance(payload.get("usage"), dict):
                        usage = parse_usage(payload)
                    choices = payload.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0]
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta")
                    if not isinstance(delta, dict):
                        delta = choice.get("message")
                    if not isinstance(delta, dict):
                        continue
                    fragment = delta.get("content")
                    if isinstance(fragment, str):
                        raw_content += fragment
                        # _JsonContentStream owns the cumulative buffer. Feed
                        # only this transport fragment; passing raw_content
                        # duplicates every previous chunk and prevents the
                        # JSON string prefix from being decoded progressively.
                        extractor.feed(fragment)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            provider_error = ProviderError(type(error).__name__, retryable=True)
            self._record_failure(
                operation,
                started_at,
                provider_error,
                request_id=request_id,
                prompt_version=prompt_version,
            )
            raise provider_error from error

        try:
            if not raw_content:
                raise ValueError("empty streaming response")
            result = contract.model_validate_json(raw_content)
        except (TypeError, ValueError, ValidationError) as error:
            output_error = AgentOutputError("模型未返回符合约定的对话结构")
            self._record_failure(
                operation,
                started_at,
                output_error,
                request_id=request_id,
                prompt_version=prompt_version,
            )
            raise output_error from error
        self._record_success(
            operation,
            started_at,
            usage,
            request_id=request_id,
            prompt_version=prompt_version,
        )
        return result

    def _record_success(
        self,
        operation: str,
        started_at: datetime,
        usage: dict[str, int | None],
        *,
        request_id: str | None,
        prompt_version: str | None,
    ) -> None:
        self._record(
            ModelCallUsage(
                operation=operation,
                provider=self.provider,
                model=self.model,
                status="succeeded",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                prompt_version=prompt_version,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["total_tokens"],
                cost_micros=calculate_cost_micros(
                    usage,
                    input_cost_per_million_usd=self.input_cost_per_million_usd,
                    output_cost_per_million_usd=self.output_cost_per_million_usd,
                ),
                request_id=request_id,
            )
        )

    def _record_failure(
        self,
        operation: str,
        started_at: datetime,
        error: Exception,
        *,
        request_id: str | None,
        prompt_version: str | None,
    ) -> None:
        self._record(
            ModelCallUsage(
                operation=operation,
                provider=self.provider,
                model=self.model,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                prompt_version=prompt_version,
                request_id=request_id,
                error_code=(
                    f"provider_http_{error.status_code}"
                    if isinstance(error, ProviderError) and error.status_code
                    else type(error).__name__
                ),
                error_message=str(error)[:300],
            )
        )

    def _record(self, usage: ModelCallUsage) -> None:
        if self.usage_recorder is None:
            return
        try:
            self.usage_recorder(usage)
        except Exception:
            return


class LocalRuleConversationGateway:
    provider = "local-rules"

    def plan_turn(self, request: PlanTurnRequest) -> ConversationPlan:
        content = request.messages[-1].content
        if _requires_grounded_weekly_actions(request.messages):
            return ConversationPlan(
                intent="local_weekly_action_review",
                steps=[
                    {
                        "id": "career",
                        "agent": "career",
                        "instruction": "读取就业画像、求职计划和任务进度，形成本周行动依据",
                        "depends_on": [],
                    },
                    {
                        "id": "application",
                        "agent": "application",
                        "instruction": "读取最近投递记录，补充本周行动优先级判断",
                        "depends_on": ["career"],
                    },
                ],
            )
        if any(word in content for word in ("入职", "试用期", "企业评价", "就业质量", "回访")):
            agent = "employment"
        elif any(word in content for word in ("职场模拟", "沟通训练", "汇报训练", "冲突处理")):
            agent = "workplace"
        elif any(word in content for word in ("课程", "学习", "能力提升", "技能差距")):
            agent = "learning"
        elif any(word in content for word in ("岗位趋势", "招聘趋势", "岗位情报", "招聘来源")):
            agent = "intelligence"
        elif any(word in content for word in ("班级", "风险", "帮扶", "辅导员")):
            agent = "counselor"
        elif "简历" in content:
            agent = "resume"
        elif _requested_role(request.messages) or any(
            word in content for word in ("岗位", "职位", "招聘")
        ):
            agent = "job"
        elif any(word in content for word in ("投递", "申请", "进度")):
            agent = "application"
        elif any(word in content for word in ("面试", "回答", "追问")):
            agent = "interview"
        else:
            agent = "career"
        return ConversationPlan(
            intent=f"local_{agent}",
            steps=[
                {
                    "id": agent,
                    "agent": agent,
                    "instruction": "基于已授权业务数据给出可解释建议",
                    "depends_on": [],
                }
            ],
        )

    def decide_specialist(self, request: SpecialistRequest) -> SpecialistDecision:
        available = {item.name for item in request.tool_catalog}
        context = request.context
        query = _requested_role(request.messages) or request.messages[-1].content[:120]
        candidates: dict[str, list[tuple[str, dict[str, object]]]] = {
            "career": [
                ("profile.get", {}),
                ("plan.get", {}),
                ("tasks.list", {}),
                ("applications.list", {}),
                ("knowledge.search", {"query": query, "source_types": ["course", "attachment"]}),
            ],
            "job": [
                ("jobs.search_internal", {"query": query}),
                ("jobs.search_public", {"query": query}),
                ("profile.get", {}),
                ("knowledge.search", {"query": query, "source_types": ["job", "resume"]}),
            ],
            "resume": [
                ("resumes.list", {}),
                ("knowledge.search", {"query": query, "source_types": ["resume", "attachment"]}),
            ],
            "application": [("applications.list", {})],
            "interview": [
                ("resumes.list", {}),
                ("knowledge.search", {"query": query, "source_types": ["resume", "job"]}),
            ],
            "counselor": [("dashboard.class_summary", {}), ("risks.list", {})],
            "learning": [
                ("growth.overview", {}),
                ("knowledge.search", {"query": query, "source_types": ["course", "question_bank"]}),
            ],
            "workplace": [
                ("workplace.sessions", {}),
                ("workplace.deliverables", {}),
                ("knowledge.search", {"query": query, "source_types": ["attachment", "public"]}),
            ],
            "intelligence": [
                ("intelligence.overview", {}),
                ("knowledge.search", {"query": query, "source_types": ["job", "public"]}),
            ],
            "employment": [
                ("employment.records", {}),
                ("knowledge.search", {"query": query, "source_types": ["employment", "public"]}),
            ],
        }
        if request.step.agent == "job" and context.get("job_id"):
            candidates["job"].insert(0, ("jobs.get", {"resource_id": context["job_id"]}))
        if not context.get("knowledge_ready", False):
            candidates[request.step.agent] = [
                item for item in candidates[request.step.agent] if item[0] != "knowledge.search"
            ]
        tool_requests: list[ToolRequest] = []
        for name, arguments in candidates[request.step.agent]:
            if name not in available:
                continue
            tool_requests.append(ToolRequest(name=name, arguments=arguments))
            if len(tool_requests) >= 3:
                break
        return SpecialistDecision(
            analysis="在线模型不可用，使用受限本地规则读取必要业务数据。",
            tool_requests=tool_requests,
        )

    def summarize_specialist(self, request: SpecialistSummaryRequest) -> SpecialistOutput:
        lines: list[str] = []
        citations: list[Citation] = []
        for item in request.tool_results:
            lines.extend(_summarize_tool_result(item))
            citations.extend(_tool_citations(item))
        summary = "\n".join(_dedupe_text(lines)) or "当前没有可用的结构化业务结果。"
        return SpecialistOutput(
            agent=request.step.agent,
            summary=summary[:4_000],
            citations=_dedupe_citations(citations),
        )

    def compose_answer(self, request: ComposeAnswerRequest) -> ConversationAnswer:
        summary_lines: list[str] = []
        for output in request.specialist_outputs:
            summary_lines.extend(
                line
                for line in _dedupe_text(output.summary.splitlines())
                if line and not line.lstrip().startswith(("{", "["))
            )
        summary_lines = _dedupe_text(summary_lines)
        situation = [
            line
            for line in summary_lines
            if line.startswith(("就业画像", "优势能力", "求职目标", "规划依据", "任务进度"))
        ][:4]
        blockers = [
            line
            for line in summary_lines
            if line.startswith(("待补短板", "约束条件", "风险提醒"))
        ][:3]
        actions = [line for line in summary_lines if line.startswith("近期任务")][:2]
        if not actions:
            actions = [line for line in summary_lines if line.startswith("优先行动")][:2]
        if not actions:
            actions = [
                "先把简历里最能证明岗位能力的项目补成“背景-行动-结果”结构。",
                "按主攻岗位筛选高匹配岗位，避免一口气海投低匹配岗位。",
                "每周复盘投递、面试和反馈，保留下一轮可改进证据。",
            ]

        lines = [
            "先别急，我把系统里的就业画像、计划和任务记录整理成一句话：你不是没有方向，当前更像是“能力证据还不够清楚、求职动作需要更聚焦”。",
            "当前情况：",
        ]
        lines.extend(
            f"{index}. {line}" for index, line in enumerate(situation or summary_lines[:4], start=1)
        )
        if blockers:
            lines.append("主要卡点：")
            lines.extend(f"{index}. {line}" for index, line in enumerate(blockers, start=1))
        lines.append("本周先做：")
        lines.extend(f"{index}. {line}" for index, line in enumerate(actions, start=1))
        answer = ConversationAnswer(
            provider=self.provider,
            content="\n".join(lines),
            citations=[],
            suggested_actions=[],
        )
        return _enrich_answer(request, answer, self.provider)

    def compose_answer_stream(
        self,
        request: ComposeAnswerRequest,
        *,
        on_delta: Callable[[str], None],
        on_reset: Callable[[], None] | None = None,
    ) -> ConversationAnswer:
        answer = self.compose_answer(request)
        for chunk in _chunk_text(answer.content):
            on_delta(chunk)
        return answer

    def summarize_memory(self, _request: MemorySummaryRequest) -> MemorySummary:
        return MemorySummary(
            confirmed_facts=[],
            preferences=[],
            unresolved_actions=[],
            source_message_ids=[],
        )


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


def _provider_failure_reason(provider: ConversationGateway, error: Exception) -> str:
    provider_name = getattr(provider, "provider", "unknown-provider")
    if isinstance(error, ProviderError):
        code = str(error) or "provider_error"
        if error.status_code is not None and f"{error.status_code}" not in code:
            code = f"{code}_{error.status_code}"
        return f"{provider_name}={code}"
    if isinstance(error, AgentOutputError):
        return f"{provider_name}=invalid_model_output"
    return f"{provider_name}={type(error).__name__}"


def _fallback_answer_with_reason(
    answer: ConversationAnswer,
    failures: list[str],
) -> ConversationAnswer:
    reason = "；".join(failures[:6]) or "未配置在线模型或在线模型全部不可用"
    note = (
        "【模型状态】在线模型未完成本次回答，系统已降级为本地规则。"
        f"原因：{reason}。\n\n"
    )
    return answer.model_copy(
        update={
            "provider": "local-rules:fallback",
            "content": f"{note}{answer.content}"[:12_000].rstrip(),
        }
    )


class FailoverConversationGateway:
    provider = "failover"

    def __init__(
        self,
        *,
        providers: list[ConversationGateway],
        fallback: ConversationGateway | None = None,
        retry_attempts: int = 1,
        circuit_failure_threshold: int = 3,
        circuit_reset_seconds: int = 60,
        now: Callable[[], float] = monotonic,
    ) -> None:
        self.providers = providers
        self.fallback = fallback
        self.retry_attempts = retry_attempts
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_reset_seconds = circuit_reset_seconds
        self.now = now
        self._circuits = {id(provider): CircuitState() for provider in providers}

    def _allows(self, provider: ConversationGateway) -> bool:
        state = self._circuits[id(provider)]
        if state.opened_at is None:
            return True
        if self.now() - state.opened_at < self.circuit_reset_seconds:
            return False
        state.failures = 0
        state.opened_at = None
        return True

    def _invoke(self, method: str, request: BaseModel) -> BaseModel:
        failures: list[str] = []
        if not self.providers:
            failures.append("online_providers=not_configured")
        for provider in self.providers:
            if not self._allows(provider):
                failures.append(f"{getattr(provider, 'provider', 'unknown-provider')}=circuit_open")
                continue
            attempt = 0
            while True:
                try:
                    result = getattr(provider, method)(request)
                    state = self._circuits[id(provider)]
                    state.failures = 0
                    state.opened_at = None
                    return result
                except Exception as error:
                    # A provider can return syntactically valid JSON that
                    # violates the contract or semantic guardrails (for
                    # example, omitting the required job specialist). A
                    # bounded retry gives the same provider a chance to
                    # self-correct before failover, just like a retryable
                    # transport error.
                    retryable = (
                        isinstance(error, ProviderError) and error.retryable
                    ) or isinstance(error, AgentOutputError)
                    if retryable and attempt < self.retry_attempts:
                        attempt += 1
                        continue
                    state = self._circuits[id(provider)]
                    state.failures += 1
                    if state.failures >= self.circuit_failure_threshold:
                        state.opened_at = self.now()
                    failures.append(_provider_failure_reason(provider, error))
                    break
        if self.fallback is None:
            raise _online_provider_unavailable(failures)
        result = getattr(self.fallback, method)(request)
        if method == "compose_answer" and isinstance(result, ConversationAnswer):
            return _fallback_answer_with_reason(result, failures)
        return result

    def plan_turn(self, request: PlanTurnRequest) -> ConversationPlan:
        result = self._invoke("plan_turn", request)
        assert isinstance(result, ConversationPlan)
        return result

    def decide_specialist(self, request: SpecialistRequest) -> SpecialistDecision:
        result = self._invoke("decide_specialist", request)
        assert isinstance(result, SpecialistDecision)
        return result

    def summarize_specialist(self, request: SpecialistSummaryRequest) -> SpecialistOutput:
        result = self._invoke("summarize_specialist", request)
        assert isinstance(result, SpecialistOutput)
        return result

    def compose_answer(self, request: ComposeAnswerRequest) -> ConversationAnswer:
        result = self._invoke("compose_answer", request)
        assert isinstance(result, ConversationAnswer)
        return result

    def compose_answer_stream(
        self,
        request: ComposeAnswerRequest,
        *,
        on_delta: Callable[[str], None],
        on_reset: Callable[[], None] | None = None,
    ) -> ConversationAnswer:
        failures: list[str] = []
        if not self.providers:
            failures.append("online_providers=not_configured")
        for provider in self.providers:
            if not self._allows(provider):
                failures.append(f"{getattr(provider, 'provider', 'unknown-provider')}=circuit_open")
                continue
            attempt = 0
            while True:
                try:
                    stream_method = getattr(provider, "compose_answer_stream", None)
                    if callable(stream_method):
                        result = stream_method(request, on_delta=on_delta)
                    else:
                        result = provider.compose_answer(request)
                        for chunk in _chunk_text(result.content):
                            on_delta(chunk)
                    state = self._circuits[id(provider)]
                    state.failures = 0
                    state.opened_at = None
                    return result
                except Exception as error:
                    if on_reset is not None:
                        on_reset()
                    retryable = (
                        isinstance(error, ProviderError) and error.retryable
                    ) or isinstance(error, AgentOutputError)
                    if retryable and attempt < self.retry_attempts:
                        attempt += 1
                        continue
                    state = self._circuits[id(provider)]
                    state.failures += 1
                    if state.failures >= self.circuit_failure_threshold:
                        state.opened_at = self.now()
                    failures.append(_provider_failure_reason(provider, error))
                    break
        if self.fallback is None:
            raise _online_provider_unavailable(failures)
        result = self.fallback.compose_answer(request)
        if isinstance(result, ConversationAnswer):
            result = _fallback_answer_with_reason(result, failures)
        for chunk in _chunk_text(result.content):
            on_delta(chunk)
        return result

    def summarize_memory(self, request: MemorySummaryRequest) -> MemorySummary:
        result = self._invoke("summarize_memory", request)
        assert isinstance(result, MemorySummary)
        return result
