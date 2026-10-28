from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from app.intelligence.models import JobSource


class JobSourceAdapter(Protocol):
    key: str
    display_name: str

    def supports(self, source: JobSource) -> bool: ...

    def fetch(self, source: JobSource, client: httpx.Client) -> "AdapterResult": ...


@dataclass(frozen=True)
class AdapterResult:
    items: list[dict[str, str]]
    retrieval_method: str


@dataclass(frozen=True)
class ManualPublicAdapter:
    key: str = "manual-public"
    display_name: str = "公开入口人工核验"

    def supports(self, source: JobSource) -> bool:
        return source.access_policy in {"manual", "public_entry"}

    def fetch(self, source: JobSource, client: httpx.Client) -> AdapterResult:
        response = client.get(source.base_url, follow_redirects=True)
        response.raise_for_status()
        return AdapterResult(items=[], retrieval_method="public_entry_probe")


@dataclass(frozen=True)
class ApiAdapter:
    key: str = "official-api"
    display_name: str = "官方 API"

    def supports(self, source: JobSource) -> bool:
        return source.access_policy in {"official_api", "api"} or source.source_type == "official_api"

    def fetch(self, source: JobSource, client: httpx.Client) -> AdapterResult:
        response = client.get(source.base_url, follow_redirects=True)
        response.raise_for_status()
        payload: Any = response.json()
        raw_items = payload if isinstance(payload, list) else payload.get("jobs", payload.get("data", []))
        if not isinstance(raw_items, list):
            raise ValueError("official API response must contain a jobs/data list")
        items: list[dict[str, str]] = []
        for raw in raw_items[:500]:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or raw.get("job_title") or "").strip()
            company = str(raw.get("company") or raw.get("employer") or "").strip()
            description = str(raw.get("description") or raw.get("summary") or "").strip()
            if not title or not company or not description:
                continue
            items.append(
                {
                    "title": title[:120],
                    "company": company[:160],
                    "location": str(raw.get("location") or raw.get("city") or "全国")[:120],
                    "description": description[:10_000],
                    "source_url": str(raw.get("url") or raw.get("source_url") or source.base_url)[:1_000],
                }
            )
        return AdapterResult(items=items, retrieval_method="official_json_api")


class _VisibleTextParser(HTMLParser):
    """Collect visible text from a public detail page without adding an HTML dependency."""

    _IGNORED_TAGS = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._IGNORED_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)

    def text(self) -> str:
        return " ".join(self.parts)


def _ncss_detail_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    text = parser.text()
    start = text.find("职位详情")
    if start >= 0:
        text = text[start + len("职位详情") :]
    end_markers = ("面试评价", "查看该公司全部评价", "扫码快速投递")
    end_positions = [text.find(marker) for marker in end_markers if text.find(marker) >= 0]
    if end_positions:
        text = text[: min(end_positions)]
    return " ".join(text.split())[:10_000]


def _ncss_description(raw: dict[str, Any], detail: str = "") -> str:
    if detail:
        return detail
    salary = ""
    low_pay = raw.get("lowMonthPay")
    high_pay = raw.get("highMonthPay")
    if low_pay is not None or high_pay is not None:
        salary = f"薪资：{low_pay or '-'}k-{high_pay or '-'}k"
    fields = [
        f"{salary}" if salary else "",
        f"学历：{raw.get('degreeName')}" if raw.get("degreeName") else "",
        f"专业：{raw.get('major')}" if raw.get("major") else "",
        f"招聘人数：{raw.get('headCount')}人" if raw.get("headCount") else "",
        f"企业性质：{raw.get('recProperty')}" if raw.get("recProperty") else "",
        f"福利：{raw.get('recTags')}" if raw.get("recTags") else "",
    ]
    return "；".join(item for item in fields if item)[:10_000] or "岗位详情请打开来源链接核验。"


@dataclass(frozen=True)
class NcssPublicAdapter:
    """Read the public job list/detail endpoints exposed by the NCSS portal."""

    key: str = "ncss-public-jobs"
    display_name: str = "国家大学生就业服务平台公开职位接口"

    def supports(self, source: JobSource) -> bool:
        host = (urlsplit(source.base_url).hostname or "").lower()
        return host.endswith("ncss.cn") or host.endswith("chsi.com.cn")

    def fetch(self, source: JobSource, client: httpx.Client) -> AdapterResult:
        list_url = urljoin(source.base_url, "/student/jobs/jobslist/ajax/")
        response = client.get(
            list_url,
            params={
                "jobType": "",
                "areaCode": "",
                "jobName": "",
                "monthPay": "",
                "industrySectors": "",
                "property": "",
                "categoryCode": "",
                "memberLevel": "",
                "recruitType": "",
                "offset": "1",
                "limit": "20",
                "keyUnits": "",
                "degreeCode": "",
                "sourcesName": "",
                "sourcesType": "",
            },
            headers={
                "User-Agent": "CareerAgent/1.0 (+public-job-sync)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": source.base_url,
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        payload: Any = response.json()
        raw_items = ((payload.get("data") or {}).get("list") if isinstance(payload, dict) else None)
        if not isinstance(raw_items, list):
            raise ValueError("ncss response must contain data.list")

        items: list[dict[str, str]] = []
        for index, raw in enumerate(raw_items[:20]):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("jobName") or "").strip()
            company = str(raw.get("recName") or "").strip()
            if not title or not company:
                continue
            job_id = str(raw.get("jobId") or "").strip()
            detail_url = (
                urljoin(source.base_url, f"/student/jobs/{job_id}/detail.html")
                if job_id
                else source.base_url
            )
            detail = ""
            if job_id and index < 8:
                try:
                    detail_response = client.get(
                        detail_url,
                        headers={"User-Agent": "CareerAgent/1.0 (+public-job-sync)"},
                        follow_redirects=True,
                    )
                    if detail_response.is_success and "text/html" in detail_response.headers.get(
                        "content-type", ""
                    ):
                        detail = _ncss_detail_text(detail_response.text)
                except httpx.HTTPError:
                    # A list item is still usable when its detail page is temporarily unavailable.
                    pass
            items.append(
                {
                    "title": title[:120],
                    "company": company[:160],
                    "location": str(raw.get("areaCodeName") or "全国")[:120],
                    "description": _ncss_description(raw, detail),
                    "source_url": detail_url[:1_000],
                }
            )
        return AdapterResult(items=items, retrieval_method="ncss_public_json_and_detail")


@dataclass(frozen=True)
class GuopinPublicAdapter:
    """Read the public, unauthenticated job feed published by 国聘雷达."""

    key: str = "guopin-public-api"
    display_name: str = "国聘雷达公开 API"

    def supports(self, source: JobSource) -> bool:
        host = (urlsplit(source.base_url).hostname or "").lower()
        return host == "guopinleida.com" or host.endswith(".guopinleida.com")

    def fetch(self, source: JobSource, client: httpx.Client) -> AdapterResult:
        api_url = urljoin(source.base_url, "/api/jobs")
        response = client.get(
            api_url,
            params={"skip": 0, "take": 20, "orderBy": "recordedAt", "order": "desc", "hideExpired": "true"},
            headers={
                "User-Agent": "CareerAgent/1.0 (+public-job-sync)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        payload: Any = response.json()
        raw_items = ((payload.get("data") or {}).get("data") if isinstance(payload, dict) else None)
        if not isinstance(raw_items, list):
            raise ValueError("guopin response must contain data.data")

        items: list[dict[str, str]] = []
        for raw in raw_items[:20]:
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip()
            company_data = raw.get("company")
            company = (
                str(company_data.get("name") or "").strip()
                if isinstance(company_data, dict)
                else str(company_data or "").strip()
            )
            if not title or not company:
                continue
            locations = raw.get("locations")
            location = (
                ", ".join(str(item).strip() for item in locations if str(item).strip())
                if isinstance(locations, list)
                else str(locations or "全国")
            )
            description_parts = [
                str(raw.get("description") or "").replace("\\\\", "\\").strip(),
                f"企业标签：{', '.join(str(item) for item in raw.get('companyTags') or [])}"
                if raw.get("companyTags")
                else "",
                f"招聘届次：{', '.join(str(item) for item in raw.get('recruitmentYear') or [])}"
                if raw.get("recruitmentYear")
                else "",
                f"截止时间：{raw.get('deadline')}" if raw.get("deadline") else "",
            ]
            source_url = str(raw.get("detailUrl") or "").strip() or urljoin(
                source.base_url, f"/jobs/{raw.get('id', '')}"
            )
            items.append(
                {
                    "title": title[:120],
                    "company": company[:160],
                    "location": location[:120] or "全国",
                    "description": "；".join(item for item in description_parts if item)[:10_000]
                    or "岗位详情请打开来源链接核验。",
                    "source_url": source_url[:1_000],
                }
            )
        return AdapterResult(items=items, retrieval_method="guopin_public_json_api")


ADAPTERS: tuple[JobSourceAdapter, ...] = (
    NcssPublicAdapter(),
    GuopinPublicAdapter(),
    ApiAdapter(),
    ManualPublicAdapter(),
)


def resolve_adapter(source: JobSource) -> JobSourceAdapter | None:
    for adapter in ADAPTERS:
        if adapter.key == source.adapter_key or adapter.supports(source):
            return adapter
    return None
