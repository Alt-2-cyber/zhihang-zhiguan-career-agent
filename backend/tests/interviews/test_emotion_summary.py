from app.interviews.router import _summarize_emotion


def _observation(
    *,
    face_detected: bool = True,
    emotion: str = "neutral",
    confidence: float = 0.9,
    presentation_score: int | None = 96,
) -> dict[str, object]:
    return {
        "face_detected": face_detected,
        "dominant_emotion": emotion,
        "confidence": confidence,
        "presentation_score": presentation_score,
        "model": "YOLO-face + vit-face-expression",
    }


def test_emotion_summary_does_not_score_when_face_is_missing() -> None:
    summary = _summarize_emotion([_observation(face_detected=False, presentation_score=None)])

    assert summary is not None
    assert summary["face_presence_rate"] == 0.0
    assert summary["stability_score"] is None
    assert summary["warning"] == "未检测到清晰人脸，未生成情绪评分"


def test_emotion_summary_aggregates_presence_consistency_and_variation() -> None:
    summary = _summarize_emotion(
        [
            _observation(emotion="neutral", confidence=0.9, presentation_score=90),
            _observation(emotion="neutral", confidence=0.8, presentation_score=80),
            _observation(face_detected=False, presentation_score=None),
        ]
    )

    assert summary is not None
    assert summary["sample_count"] == 3
    assert summary["face_presence_rate"] == 0.6667
    assert summary["dominant_emotion"] == "neutral"
    assert 0 < int(summary["stability_score"]) < 100
