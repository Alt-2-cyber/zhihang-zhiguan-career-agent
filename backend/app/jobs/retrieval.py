import math
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.ai.models import DocumentChunk
from app.jobs.models import Job


@dataclass(frozen=True)
class SemanticJobMatch:
    job: Job
    score: float


@dataclass(frozen=True)
class SemanticChunkMatch:
    chunk: DocumentChunk
    score: float


def chunk_text(text: str, *, size: int = 800, overlap: int = 100) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size and overlap are invalid")
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = end - overlap
    return chunks


def _validate_query(query_vector: list[float], limit: int) -> None:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    if len(query_vector) != 1024 or not all(math.isfinite(value) for value in query_vector):
        raise ValueError("query vector must contain 1024 finite values")


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def _deduplicate(rows: list[tuple[Job, float]], *, limit: int) -> list[SemanticJobMatch]:
    best: dict[str, SemanticJobMatch] = {}
    for job, score in rows:
        current = best.get(job.id)
        if current is None or score > current.score:
            best[job.id] = SemanticJobMatch(job=job, score=score)
    return sorted(best.values(), key=lambda item: (-item.score, item.job.id))[:limit]


def retrieve_jobs(
    db: Session, query_vector: list[float], *, limit: int = 5
) -> list[SemanticJobMatch]:
    _validate_query(query_vector, limit)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
        result = db.execute(
            select(Job, distance)
            .join(
                DocumentChunk,
                and_(
                    DocumentChunk.source_type == "job",
                    DocumentChunk.source_id == Job.id,
                    DocumentChunk.owner_id.is_(None),
                ),
            )
            .order_by(distance)
            .limit(limit * 4)
        ).all()
        rows = [(job, max(-1.0, min(1.0, 1.0 - float(value)))) for job, value in result]
        return _deduplicate(rows, limit=limit)

    chunks = db.scalars(
        select(DocumentChunk).where(
            DocumentChunk.source_type == "job",
            DocumentChunk.owner_id.is_(None),
        )
    ).all()
    rows: list[tuple[Job, float]] = []
    for chunk in chunks:
        job = db.get(Job, chunk.source_id)
        if job is not None:
            rows.append((job, _cosine_similarity(query_vector, list(chunk.embedding))))
    return _deduplicate(rows, limit=limit)


def retrieve_document_chunks(
    db: Session,
    query_vector: list[float],
    *,
    source_types: list[str],
    owner_id: str | None,
    limit: int = 5,
) -> list[SemanticChunkMatch]:
    _validate_query(query_vector, min(limit, 20))
    if not source_types:
        raise ValueError("source types are required")
    bounded_limit = min(limit, 10)
    ownership = (
        DocumentChunk.owner_id.is_(None)
        if owner_id is None
        else or_(DocumentChunk.owner_id.is_(None), DocumentChunk.owner_id == owner_id)
    )
    conditions = [DocumentChunk.source_type.in_(source_types), ownership]
    if db.get_bind().dialect.name == "postgresql":
        distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
        rows = db.execute(
            select(DocumentChunk, distance)
            .where(*conditions)
            .order_by(distance, DocumentChunk.id)
            .limit(bounded_limit)
        ).all()
        return [
            SemanticChunkMatch(
                chunk=chunk,
                score=max(-1.0, min(1.0, 1.0 - float(distance_value))),
            )
            for chunk, distance_value in rows
        ]

    chunks = db.scalars(select(DocumentChunk).where(*conditions)).all()
    matches = [
        SemanticChunkMatch(
            chunk=chunk,
            score=_cosine_similarity(query_vector, list(chunk.embedding)),
        )
        for chunk in chunks
    ]
    return sorted(matches, key=lambda item: (-item.score, item.chunk.id))[:bounded_limit]
