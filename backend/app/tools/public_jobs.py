import ipaddress
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field


class PublicJobSearchError(RuntimeError):
    pass


class PublicJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    snippet: str = Field(default="", max_length=1_000)
    url: str = Field(min_length=1, max_length=1_000)
    source_host: str = Field(min_length=1, max_length=253)
    source_trust_level: str = Field(min_length=1, max_length=40)
    source_trust_score: float = Field(ge=0.0, le=1.0)
    source_policy: str = "public_web_search_only"
    retrieval_method: str = "bing_public_search"
    automation_policy: str = "analysis_only_no_auto_apply"
    verification_required: bool = True
    fetched_at: datetime


def validate_public_http_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("URL must be a public HTTP(S) address")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("local hosts are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("private network addresses are not allowed")
    return value.strip()


def canonicalize_public_url(value: str) -> str:
    value = validate_public_http_url(value)
    parsed = urlsplit(value)
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"from", "ref", "source"}
        ]
    )
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            query,
            "",
        )
    ).rstrip("/")


def source_trust(hostname: str) -> tuple[str, float]:
    host = hostname.lower().rstrip(".")
    if host.endswith(".gov.cn") or host.endswith(".edu.cn") or host.endswith(".edu"):
        return "official_or_education", 0.9
    if any(token in host for token in ("campus", "career", "job", "zhaopin", "liepin", "51job")):
        return "recruitment_or_career_site", 0.72
    if host.endswith(".org") or host.endswith(".org.cn"):
        return "organization_site", 0.68
    return "public_web_unverified", 0.55


class BingResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[tuple[str, str, str]] = []
        self._inside_result = False
        self._inside_heading = False
        self._inside_snippet = False
        self._href: str | None = None
        self._title: list[str] = []
        self._snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "li" and "b_algo" in classes:
            self._inside_result = True
            self._href = None
            self._title = []
            self._snippet = []
        elif self._inside_result and tag == "h2":
            self._inside_heading = True
        elif self._inside_result and self._inside_heading and tag == "a":
            self._href = attributes.get("href")
        elif self._inside_result and tag == "p":
            self._inside_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._inside_heading = False
        elif tag == "p":
            self._inside_snippet = False
        elif tag == "li" and self._inside_result:
            title = " ".join("".join(self._title).split())
            snippet = " ".join("".join(self._snippet).split())
            if self._href and title:
                self.results.append((title, snippet, self._href))
            self._inside_result = False

    def handle_data(self, data: str) -> None:
        if self._inside_result and self._inside_heading:
            self._title.append(data)
        elif self._inside_result and self._inside_snippet:
            self._snippet.append(data)


class BingPublicJobSearch:
    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.Client,
        max_results: int,
        retry_attempts: int = 1,
    ) -> None:
        self.base_url = base_url
        self.client = client
        self.max_results = max(1, min(max_results, 10))
        self.retry_attempts = max(0, min(retry_attempts, 3))

    def _get(self, *, terms: str, count: int) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.retry_attempts + 1):
            try:
                response = self.client.get(
                    self.base_url,
                    params={"q": terms, "count": count},
                    headers={
                        "User-Agent": "CareerAgent/1.0 (+public-job-search)",
                        "Accept": "text/html,application/xhtml+xml",
                    },
                )
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_error = error
            except httpx.HTTPStatusError as error:
                last_error = error
                status_code = error.response.status_code
                if status_code != 429 and status_code < 500:
                    break
            if attempt >= self.retry_attempts:
                break
        raise PublicJobSearchError("public_job_search_unavailable") from last_error

    def search(self, *, query: str, city: str | None, limit: int) -> list[PublicJobResult]:
        terms = " ".join(
            part for part in [query.strip(), city.strip() if city else "", "招聘 岗位"] if part
        )
        bounded_limit = max(1, min(limit, self.max_results))
        response = self._get(terms=terms, count=bounded_limit)

        parser = BingResultParser()
        parser.feed(response.text)
        fetched_at = datetime.now(timezone.utc)
        results: list[PublicJobResult] = []
        seen: set[str] = set()
        for title, snippet, raw_url in parser.results:
            try:
                url = canonicalize_public_url(raw_url)
            except ValueError:
                continue
            if url in seen:
                continue
            seen.add(url)
            source_host = urlsplit(url).hostname or "unknown"
            trust_level, trust_score = source_trust(source_host)
            results.append(
                PublicJobResult(
                    title=title[:200],
                    snippet=snippet[:1_000],
                    url=url,
                    source_host=source_host,
                    source_trust_level=trust_level,
                    source_trust_score=trust_score,
                    fetched_at=fetched_at,
                )
            )
            if len(results) >= bounded_limit:
                break
        return results
