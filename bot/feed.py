"""Fetch and filter the SimplifyJobs listings feed.

The feed is one ~13 MB JSON array. We use HTTP conditional requests (ETag /
If-None-Match): if nothing changed upstream, GitHub answers 304 Not Modified
with no body, so most polls cost almost nothing.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

# Upstream uses a few spellings for the same category; collapse them.
CATEGORY_ALIASES = {
    "software": "Software",
    "software engineering": "Software",
    "hardware": "Hardware",
    "hardware engineering": "Hardware",
    "ai/ml/data": "AI/ML/Data",
    "data science, ai & machine learning": "AI/ML/Data",
    "product": "Product",
    "product management": "Product",
    "quant": "Quant",
    "quantitative finance": "Quant",
}


def normalize_category(raw: str | None) -> str:
    if not raw:
        return "Other"
    return CATEGORY_ALIASES.get(raw.strip().lower(), raw.strip())


@dataclass(frozen=True)
class Listing:
    id: str
    company: str
    title: str
    locations: list[str]
    category: str
    terms: list[str]
    url: str
    company_url: str
    date_posted: int
    sponsorship: str

    @classmethod
    def from_raw(cls, d: dict) -> "Listing":
        return cls(
            id=str(d["id"]),
            company=d.get("company_name", "Unknown"),
            title=d.get("title", "Unknown role"),
            locations=list(d.get("locations") or []),
            category=normalize_category(d.get("category")),
            terms=list(d.get("terms") or []),
            url=d.get("url", ""),
            company_url=d.get("company_url", ""),
            date_posted=int(d.get("date_posted") or 0),
            sponsorship=d.get("sponsorship") or "Other",
        )


def filter_listings(
    raw: list[dict],
    terms: list[str],
    categories: list[str],
    max_age_days: int,
    now: float | None = None,
) -> list[Listing]:
    """Keep active, visible postings for our terms/categories, newest first."""
    now = now if now is not None else time.time()
    cutoff = now - max_age_days * 86400 if max_age_days > 0 else 0
    wanted_terms = {t.lower() for t in terms}
    wanted_cats = {normalize_category(c) for c in categories}

    out: list[Listing] = []
    for d in raw:
        if not d.get("active") or not d.get("is_visible", True):
            continue
        if not d.get("id") or not d.get("url"):
            continue
        if wanted_terms and not wanted_terms & {t.lower() for t in d.get("terms") or []}:
            continue
        item = Listing.from_raw(d)
        if wanted_cats and item.category not in wanted_cats:
            continue
        if item.date_posted < cutoff:
            continue
        out.append(item)
    out.sort(key=lambda x: x.date_posted, reverse=True)
    return out


class FeedClient:
    """Remembers the last ETag so unchanged feeds return quickly."""

    def __init__(self, url: str, session: aiohttp.ClientSession):
        self.url = url
        self.session = session
        self.etag: str | None = None
        self.last: list[dict] | None = None

    async def fetch(self) -> list[dict]:
        """Return the parsed feed (cached copy if upstream says 304)."""
        headers = {"User-Agent": "ktp-internship-bot"}
        if self.etag and self.last is not None:
            headers["If-None-Match"] = self.etag
        timeout = aiohttp.ClientTimeout(total=60)
        async with self.session.get(self.url, headers=headers, timeout=timeout) as r:
            if r.status == 304 and self.last is not None:
                log.debug("feed unchanged (304)")
                return self.last
            r.raise_for_status()
            # raw.githubusercontent serves text/plain, so skip the content-type check.
            data = await r.json(content_type=None)
            if not isinstance(data, list):
                raise ValueError("feed is not a JSON array")
            self.etag = r.headers.get("ETag")
            self.last = data
            log.info("feed fetched: %d entries", len(data))
            return data
