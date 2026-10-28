import re
from collections.abc import Iterable

UNIFIED_RUBRIC_VERSION = "unified-v1"
DIMENSION_LABELS = {
    "content_completeness": "内容完整度",
    "job_relevance": "岗位相关性",
    "answer_structure": "表达结构",
    "evidence_quality": "证据质量",
}
EMOTION_DIMENSION_LABEL = "表达稳定度（摄像头分析）"
EVIDENCE_MARKERS = re.compile(
    r"(?:数据|指标|结果|验证|例如|项目|上线|提升|降低|完成|负责|测试|复盘|链接|截图)"
)


def clamp_score(value: object) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def aggregate_scores(scores: dict[str, object]) -> dict[str, int]:
    return {name: clamp_score(scores.get(name)) for name in DIMENSION_LABELS}


def weighted_average(scores: dict[str, object], weights: dict[str, int] | None = None) -> int:
    normalized = aggregate_scores(scores)
    weights = weights or {name: 1 for name in DIMENSION_LABELS}
    total_weight = sum(weights.get(name, 0) for name in normalized)
    if total_weight <= 0:
        return 0
    return round(
        sum(normalized[name] * weights.get(name, 0) for name in normalized) / total_weight
    )


def validate_evidence_quote(quote: str, sources: Iterable[str]) -> str:
    cleaned = " ".join(quote.split()).strip()
    if not cleaned:
        return "missing"
    source_text = " ".join(" ".join(str(item).split()) for item in sources).lower()
    return "grounded" if cleaned.lower() in source_text else "un_grounded"


def assess_answer_evidence(answer: str) -> dict[str, object]:
    cleaned = " ".join(answer.split()).strip()
    markers = EVIDENCE_MARKERS.findall(cleaned)
    numeric_claims = re.findall(r"(?<!\w)(?:\d+(?:\.\d+)?%?|\d+[万千百]?(?:条|人|次|天|个|项))", cleaned)
    if not cleaned:
        status = "missing"
    elif markers or numeric_claims:
        status = "grounded"
    else:
        status = "insufficient"
    return {
        "status": status,
        "marker_count": len(markers),
        "numeric_claim_count": len(numeric_claims),
        "source": "user_answer",
    }
