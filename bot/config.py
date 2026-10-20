"""Configuration loaded from environment variables.

Everything the bot needs is read from the environment so the same image runs
in dev and on kronos — only the .env / Dokploy env settings change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_FEED_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/"
    "dev/.github/scripts/listings.json"
)

DEFAULT_NEWGRAD_FEED_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
    "dev/.github/scripts/listings.json"
)


# Title keywords that pull finance/business roles out of any category.
# Whole-word, case-insensitive ("tax" won't match "Taxonomy").
# Tuned against the live feed 2026-10-19. Override with TITLE_KEYWORDS ("" disables).
DEFAULT_TITLE_KEYWORDS = (
    "finance,financial,banking,investment,investments,accounting,accountant,audit,tax,"
    "treasury,trading,trader,consulting,consultant,strategy,business,operations,marketing,"
    "sales,risk,economics,economic,capital markets,wealth,asset management,private equity,"
    "venture,actuarial,underwriting,credit,portfolio,fp&a"
)


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [p.strip() for p in raw.split(",") if p.strip()]


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Source:
    name: str = ""
    feed_url: str = ""
    channel_id: int = 0
    # Which terms count (a posting matches if ANY of its terms is listed).
    terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    discord_token: str = ""
    sources: list[Source] = field(default_factory=list)
    # Normalized categories to post. Empty list = post every category.
    categories: list[str] = field(default_factory=list)
    # Title keywords that pull in postings from ANY category (labeled Finance/Business).
    title_keywords: list[str] = field(default_factory=list)
    # Only keep postings with at least one US location.
    us_only: bool = False
    poll_minutes: int = 15
    db_path: str = "/data/seen.db"
    # Safety valve: never post more than this many in one cycle.
    max_posts_per_cycle: int = 25
    # Ignore postings whose date_posted is older than this (catches old
    # postings that get re-activated or re-ID'd upstream).
    max_age_days: int = 14
    # On the very first run, post the N newest matches so the channel
    # isn't empty (everything else is silently marked as seen).
    seed_post_latest: int = 0
    dry_run: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        sources: list[Source] = [
            Source(
                name="internship",
                feed_url=os.getenv("FEED_URL", DEFAULT_FEED_URL),
                channel_id=int(os.getenv("CHANNEL_ID", "0") or 0),
                terms=_csv("TERMS", "Summer 2027"),
            )
        ]

        if ng_channel_id := os.getenv("NEWGRAD_CHANNEL_ID"):
            sources.append(
                Source(
                    name="newgrad",
                    feed_url=os.getenv("NEWGRAD_FEED_URL", DEFAULT_NEWGRAD_FEED_URL),
                    channel_id=int(ng_channel_id),
                    terms=[],
                )
            )

        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            sources=sources,
            categories=_csv("CATEGORIES", ""),
            title_keywords=_csv("TITLE_KEYWORDS", DEFAULT_TITLE_KEYWORDS),
            us_only=_bool("US_ONLY", True),
            poll_minutes=int(os.getenv("POLL_MINUTES", "15")),
            db_path=os.getenv("DB_PATH", "/data/seen.db"),
            max_posts_per_cycle=int(os.getenv("MAX_POSTS_PER_CYCLE", "25")),
            max_age_days=int(os.getenv("MAX_AGE_DAYS", "14")),
            seed_post_latest=int(os.getenv("SEED_POST_LATEST", "0")),
            dry_run=_bool("DRY_RUN", False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def filter_fingerprint(self, source: Source) -> str:
        """Stable hash of everything that decides WHICH postings match.

        Stored in the DB; when it changes we silently seed the newly matching
        postings instead of flooding the channel with them.
        """
        import hashlib
        import json

        key = {
            "source": source.name,
            "terms": sorted(t.lower() for t in source.terms),
            "categories": sorted(c.lower() for c in self.categories),
            "keywords": sorted(k.lower() for k in self.title_keywords),
            "us_only": self.us_only,
        }
        return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]

    def validate_for_discord(self) -> None:
        if not self.discord_token:
            raise SystemExit("DISCORD_TOKEN is not set")
        for s in self.sources:
            if not s.channel_id:
                env = "CHANNEL_ID" if s.name == "internship" else "NEWGRAD_CHANNEL_ID"
                raise SystemExit(f"{env} is not set")
