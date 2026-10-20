"""Run one cycle without Discord and print what would be posted.

python -m bot.dryrun            # uses env vars, DB_PATH defaults to ./data/seen.db
"""

from __future__ import annotations
import asyncio
import logging
import os


import aiohttp

from .config import Config, Source
from .feed import FeedClient
from .poller import fingerprint_key, plan_cycle, store_id
from .store import SeenStore


async def run_source(
    source: Source,
    cfg: Config,
    store: SeenStore,
    session: aiohttp.ClientSession,
) -> None:
    raw = await FeedClient(source.feed_url, session).fetch()
    plan = plan_cycle(raw, store, cfg, source)

    print(f"=== {source.name} (channel {source.channel_id}) ===")
    for x in plan.to_post:
        print(
            f"[{x.category}] {x.company} — {x.title} | "
            f"{', '.join(x.locations)} | {x.url}"
        )

    if plan.mark_silently:
        store.mark(plan.mark_silently)
    store.set_meta(fingerprint_key(source), plan.fingerprint)
    store.mark((store_id(source, x.id) for x in plan.to_post), posted=True)

    print(
        f"would post {len(plan.to_post)}, seeded {len(plan.mark_silently)}, "
        f"backlog {plan.backlog}, DB now has {store.count()} ids"
    )


async def main() -> None:
    os.environ.setdefault("DB_PATH", "./data/seen.db")
    cfg = Config.from_env()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    store = SeenStore(cfg.db_path)
    async with aiohttp.ClientSession() as session:
        for source in cfg.sources:
            await run_source(source, cfg, store, session)
    store.close()


if __name__ == "__main__":
    asyncio.run(main())
