"""Run one cycle without Discord and print what would be posted.

    python -m bot.dryrun            # uses env vars, DB_PATH defaults to ./data/seen.db
"""
from __future__ import annotations

import asyncio
import logging
import os

import aiohttp

from .config import Config
from .feed import FeedClient
from .poller import plan_cycle
from .store import SeenStore


async def main() -> None:
    os.environ.setdefault("DB_PATH", "./data/seen.db")
    cfg = Config.from_env()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = SeenStore(cfg.db_path)
    async with aiohttp.ClientSession() as s:
        raw = await FeedClient(cfg.feed_url, s).fetch()
    plan = plan_cycle(raw, store, cfg)
    for x in plan.to_post:
        print(f"[{x.category}] {x.company} — {x.title} | {', '.join(x.locations)} | {x.url}")
    store.mark(plan.mark_silently)
    store.mark((x.id for x in plan.to_post), posted=True)
    print(f"would post {len(plan.to_post)}, seeded {len(plan.mark_silently)}, "
          f"backlog {plan.backlog}, DB now has {store.count()} ids")


if __name__ == "__main__":
    asyncio.run(main())
