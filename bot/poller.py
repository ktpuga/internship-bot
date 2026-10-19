"""Decide what to post this cycle. No Discord code here, so it's easy to test.

Rules:
- First run (empty DB): mark everything matching as seen WITHOUT posting,
  except the `seed_post_latest` newest ones. Avoids flooding the channel.
- Filter changed (fingerprint in DB differs): same idea — newly matching
  postings are marked seen silently, nothing is posted that cycle.
- Otherwise: anything matching and not in the DB is new. Post up to
  `max_posts_per_cycle` (oldest-first so the channel reads chronologically);
  the rest stay unmarked and go out next cycle.
- An ID is only marked "seen" after its message is sent, so a failed send
  is retried next cycle instead of being lost.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Config
from .feed import Listing, filter_listings
from .store import SeenStore

log = logging.getLogger(__name__)

FINGERPRINT_KEY = "filter_fingerprint"


@dataclass
class Plan:
    to_post: list[Listing]
    mark_silently: list[str]
    backlog: int  # new items deferred to a later cycle
    fingerprint: str = ""  # caller saves this after applying the plan


def _filter(raw: list[dict], cfg: Config, max_age_days: int, now: float | None) -> list[Listing]:
    return filter_listings(
        raw, cfg.terms, cfg.categories, max_age_days, now,
        keywords=cfg.title_keywords, us_only=cfg.us_only,
    )


def plan_cycle(raw: list[dict], store: SeenStore, cfg: Config, now: float | None = None) -> Plan:
    fp = cfg.filter_fingerprint()

    if store.is_empty():
        # Seeding ignores max_age so the whole current feed counts as "seen".
        everything = _filter(raw, cfg, 0, now)
        latest = everything[: cfg.seed_post_latest]
        latest_ids = {x.id for x in latest}
        silent = [x.id for x in everything if x.id not in latest_ids]
        log.info("first run: seeding %d existing postings, posting %d", len(silent), len(latest))
        return Plan(to_post=list(reversed(latest)), mark_silently=silent, backlog=0, fingerprint=fp)

    if store.get_meta(FINGERPRINT_KEY) != fp:
        everything = _filter(raw, cfg, 0, now)
        silent = sorted(store.unseen(x.id for x in everything))
        log.info("filters changed: silently seeding %d newly matching postings", len(silent))
        return Plan(to_post=[], mark_silently=silent, backlog=0, fingerprint=fp)

    matches = _filter(raw, cfg, cfg.max_age_days, now)
    new_ids = store.unseen(x.id for x in matches)
    new = [x for x in matches if x.id in new_ids]  # newest first
    # Take the newest N, then post them oldest-first.
    batch = new[: cfg.max_posts_per_cycle]
    backlog = len(new) - len(batch)
    if backlog:
        log.warning("%d new postings deferred to next cycle (cap %d)", backlog, cfg.max_posts_per_cycle)
    return Plan(to_post=list(reversed(batch)), mark_silently=[], backlog=backlog, fingerprint=fp)
