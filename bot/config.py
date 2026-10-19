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


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [p.strip() for p in raw.split(",") if p.strip()]


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    discord_token: str = ""
    channel_id: int = 0
    feed_url: str = DEFAULT_FEED_URL
    # Which terms count (a posting matches if ANY of its terms is listed).
    terms: list[str] = field(default_factory=lambda: ["Summer 2027"])
    # Normalized categories to post. Empty list = post every category.
    categories: list[str] = field(default_factory=list)
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
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            channel_id=int(os.getenv("CHANNEL_ID", "0") or 0),
            feed_url=os.getenv("FEED_URL", DEFAULT_FEED_URL),
            terms=_csv("TERMS", "Summer 2027"),
            categories=_csv("CATEGORIES", ""),
            poll_minutes=int(os.getenv("POLL_MINUTES", "15")),
            db_path=os.getenv("DB_PATH", "/data/seen.db"),
            max_posts_per_cycle=int(os.getenv("MAX_POSTS_PER_CYCLE", "25")),
            max_age_days=int(os.getenv("MAX_AGE_DAYS", "14")),
            seed_post_latest=int(os.getenv("SEED_POST_LATEST", "0")),
            dry_run=_bool("DRY_RUN", False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate_for_discord(self) -> None:
        if not self.discord_token:
            raise SystemExit("DISCORD_TOKEN is not set")
        if not self.channel_id:
            raise SystemExit("CHANNEL_ID is not set")
