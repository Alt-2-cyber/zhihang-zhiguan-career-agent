import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.intelligence.adapters import AdapterResult, resolve_adapter
from app.intelligence.models import JobCrawlRecord, JobSource
from app.jobs.models import Job

PUBLIC_SOURCE_KINDS = (
    "official_api",
    "official_portal",
    "government_portal",
    "local_government_portal",
    "public_web",
)


def _top_rows(db: Session, column, *, limit: int = 8) -> list[dict[str, object]]:
    rows = db.execute(
        select(column, func.count(Job.id))
        .where(Job.status == "active")
        .group_by(column)
        .order_by(func.count(Job.id).desc(), column)
        .limit(limit)
    ).all()
    return [{"name": str(name or "未标注"), "count": int(count)} for name, count in rows]


def job_intelligence_overview(db: Session) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(days=30)
    active_jobs = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.status == "active")) or 0
    )
    public_jobs = int(
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.status == "active",
                Job.source_kind.in_(PUBLIC_SOURCE_KINDS),
            )
        )
        or 0
    )
    stale_jobs = int(
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.status == "active",
                Job.source_fetched_at.is_not(None),
                Job.source_fetched_at < stale_before,
            )
        )
        or 0
    )
    sources = db.scalars(
        select(JobSource).order_by(JobSource.status, JobSource.name).limit(100)
    ).all()
    crawls = db.execute(
        select(JobCrawlRecord, JobSource)
        .join(JobSource, JobSource.id == JobCrawlRecord.source_id)
        .order_by(JobCrawlRecord.created_at.desc())
        .limit(20)
    ).all()
    latest_crawl_by_source: dict[str, JobCrawlRecord] = {}
    for crawl, _source in crawls:
        latest_crawl_by_source.setdefault(crawl.source_id, crawl)
    recent_public_jobs = db.scalars(
        select(Job)
        .where(
            Job.status == "active",
            Job.source_kind.in_(PUBLIC_SOURCE_KINDS),
        )
        .order_by(Job.source_fetched_at.desc(), Job.created_at.desc())
        .limit(20)
    ).all()
    return {
        "metrics": {
            "active_jobs": active_jobs,
            "public_jobs": public_jobs,
            "stale_jobs": stale_jobs,
            "active_sources": sum(item.status == "active" for item in sources),
        },
        "locations": _top_rows(db, Job.location),
        "roles": _top_rows(db, Job.title),
        "companies": _top_rows(db, Job.company),
        "sources": [
            {
                "id": item.id,
                "name": item.name,
                "base_url": item.base_url,
                "source_type": item.source_type,
                "adapter_key": item.adapter_key,
                "adapter_name": resolve_adapter(item).display_name
                if resolve_adapter(item)
                else "未注册适配器",
                "access_policy": item.access_policy,
                "terms_url": item.terms_url,
                "status": item.status,
                "refresh_interval_hours": item.refresh_interval_hours,
                "last_success_at": item.last_success_at.isoformat()
                if item.last_success_at
                else None,
                "last_checked_at": item.last_checked_at.isoformat()
                if item.last_checked_at
                else None,
                "freshness": _freshness_status(
                    item,
                    latest_crawl_by_source.get(item.id),
                    now=now,
                ),
            }
            for item in sources
        ],
        "recent_crawls": [
            {
                "id": crawl.id,
                "source_name": source.name,
                "status": crawl.status,
                "items_seen": crawl.items_seen,
                "items_imported": crawl.items_imported,
                "error_code": crawl.error_code,
                "started_at": crawl.started_at.isoformat() if crawl.started_at else None,
                "completed_at": crawl.completed_at.isoformat() if crawl.completed_at else None,
            }
            for crawl, source in crawls
        ],
        "recent_public_jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source_url": job.source_url,
                "source_host": job.source_host,
                "source_trust_level": job.source_trust_level,
                "source_trust_score": job.source_trust_score,
                "fetched_at": job.source_fetched_at.isoformat()
                if job.source_fetched_at
                else None,
            }
            for job in recent_public_jobs
        ],
        "generated_at": now.isoformat(),
        "freshness_alerts": [
            {
                "source_id": item["id"],
                "source_name": item["name"],
                "status": item["freshness"]["status"],
                "message": item["freshness"]["message"],
            }
            for item in _source_payloads(
                sources,
                latest_crawl_by_source,
                now=now,
            )
            if item["freshness"]["status"] in {"stale", "error", "never_checked"}
        ],
    }


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _import_jobs(
    db: Session,
    *,
    source: JobSource,
    result: AdapterResult,
    now: datetime,
) -> int:
    imported = 0
    for item in result.items:
        source_url = item["source_url"]
        job = db.scalar(select(Job).where(Job.source_url == source_url))
        if job is None:
            job = Job(
                title=item["title"],
                company=item["company"],
                location=item["location"],
                description=item["description"],
                source_url=source_url,
            )
            db.add(job)
        else:
            job.title = item["title"]
            job.company = item["company"]
            job.location = item["location"]
            job.description = item["description"]
            job.status = "active"
        job.source_kind = source.source_type
        job.source_host = urlsplit(source_url).hostname
        job.source_trust_level = "official_api" if source.access_policy in {"api", "official_api"} else "public_entry"
        job.source_trust_score = 0.95 if source.access_policy in {"api", "official_api"} else 0.8
        job.source_fetched_at = now
        imported += 1
    return imported


def refresh_job_sources(
    db: Session,
    *,
    client: httpx.Client,
    now: datetime | None = None,
    force: bool = False,
    retry_attempts: int = 1,
    limit: int = 100,
) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    sources = db.scalars(select(JobSource).where(JobSource.status == "active").limit(limit)).all()
    summary = {"checked": 0, "succeeded": 0, "failed": 0, "items_imported": 0}
    for source in sources:
        last_checked = _aware(source.last_checked_at)
        if not force and last_checked is not None:
            next_refresh = last_checked + timedelta(hours=max(1, source.refresh_interval_hours))
            if next_refresh > current:
                continue
        adapter = resolve_adapter(source)
        crawl = JobCrawlRecord(
            source_id=source.id,
            status="running",
            started_at=current,
        )
        db.add(crawl)
        db.flush()
        summary["checked"] += 1
        source.last_checked_at = current
        if adapter is None:
            crawl.status = "failed"
            crawl.error_code = "source_adapter_not_found"
            crawl.error_message = "no registered adapter for source"
            crawl.completed_at = current
            summary["failed"] += 1
            continue
        result: AdapterResult | None = None
        last_error: Exception | None = None
        for attempt in range(max(0, min(retry_attempts, 3)) + 1):
            try:
                result = adapter.fetch(source, client)
                break
            except (httpx.HTTPError, ValueError) as error:
                last_error = error
                if attempt >= retry_attempts:
                    break
        if result is None:
            crawl.status = "failed"
            crawl.error_code = (
                f"http_{last_error.response.status_code}"
                if isinstance(last_error, httpx.HTTPStatusError)
                else type(last_error).__name__ if last_error else "source_fetch_failed"
            )[:80]
            crawl.error_message = str(last_error or "source fetch failed")[:300]
            crawl.completed_at = current
            summary["failed"] += 1
            continue
        imported = _import_jobs(db, source=source, result=result, now=current)
        crawl.status = "succeeded"
        crawl.items_seen = len(result.items)
        crawl.items_imported = imported
        crawl.details_json = json.dumps(
            {"adapter": adapter.key, "retrieval_method": result.retrieval_method},
            ensure_ascii=False,
        )
        crawl.completed_at = current
        source.last_success_at = current
        summary["succeeded"] += 1
        summary["items_imported"] += imported
    db.flush()
    return summary


def _freshness_status(
    source: JobSource,
    latest_crawl: JobCrawlRecord | None,
    *,
    now: datetime,
) -> dict[str, object]:
    reference = source.last_success_at or source.last_checked_at
    age_hours = round((now - reference).total_seconds() / 3600, 1) if reference else None
    if latest_crawl is not None and latest_crawl.status in {"failed", "error"}:
        return {"status": "error", "age_hours": age_hours, "message": "最近一次采集失败，请人工检查来源。"}
    if reference is None:
        return {"status": "never_checked", "age_hours": None, "message": "来源尚未完成首次核验。"}
    if age_hours is not None and age_hours > source.refresh_interval_hours:
        return {"status": "stale", "age_hours": age_hours, "message": "来源超过刷新周期，岗位可能已过期。"}
    return {"status": "fresh", "age_hours": age_hours, "message": "来源在刷新周期内。"}


def _source_payloads(
    sources: list[JobSource],
    latest_crawl_by_source: dict[str, JobCrawlRecord],
    *,
    now: datetime,
) -> list[dict[str, object]]:
    return [
        {
            "id": source.id,
            "name": source.name,
            "freshness": _freshness_status(source, latest_crawl_by_source.get(source.id), now=now),
        }
        for source in sources
    ]
