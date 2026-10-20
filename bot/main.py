"""Bot entrypoint: log in, then poll the feed every POLL_MINUTES and post new listings.

python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import aiohttp
import discord
from discord.ext import tasks

from .config import Config, Source
from .embeds import build_embed, build_view
from .feed import FeedClient
from .poller import fingerprint_key, plan_cycle, store_id
from .store import SeenStore

log = logging.getLogger("bot")


class InternshipBot(discord.Client):
    def __init__(self, cfg: Config):
        # We only send messages; no privileged intents (message content, members) needed.
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self.cfg = cfg
        self.store = SeenStore(cfg.db_path)
        self.http_session: aiohttp.ClientSession | None = None
        self.feeds: dict[str, FeedClient] = {}
        self.heartbeat = Path(cfg.db_path).with_name("heartbeat")
        self.poll.change_interval(minutes=cfg.poll_minutes)

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        self.feeds = {
            s.name: FeedClient(s.feed_url, self.http_session) for s in self.cfg.sources
        }
        self.poll.start()

    async def close(self) -> None:
        self.poll.cancel()
        if self.http_session:
            await self.http_session.close()
        self.store.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info(
            "logged in as %s (id %s)", self.user, self.user.id if self.user else "?"
        )

    @tasks.loop(minutes=15)
    async def poll(self) -> None:
        try:
            await self.run_cycle()
            self.heartbeat.write_text(str(int(time.time())))
        except Exception:
            # Never let one bad cycle kill the loop; try again next interval.
            log.exception("poll cycle failed")

    @poll.before_loop
    async def _wait_ready(self) -> None:
        await self.wait_until_ready()

    async def run_source(self, source: Source) -> None:
        channel = self.get_channel(source.channel_id) or await self.fetch_channel(
            source.channel_id
        )
        if not hasattr(channel, "send"):
            raise RuntimeError(f"channel {source.channel_id} is not a text channel")

        raw = await self.feeds[source.name].fetch()
        plan = plan_cycle(raw, self.store, self.cfg, source)
        if plan.mark_silently:
            self.store.mark(plan.mark_silently)
        self.store.set_meta(fingerprint_key(source), plan.fingerprint)

        sent = 0
        for x in plan.to_post:
            try:
                view = build_view(x)
                if view is None:
                    await channel.send(embed=build_embed(x))
                else:
                    await channel.send(embed=build_embed(x), view=view)
                self.store.mark([store_id(source, x.id)], posted=True)
                sent += 1
            except discord.Forbidden:
                log.error(
                    "missing permission to post in channel %s; stopping this cycle",
                    source.channel_id,
                )
                break
            except discord.HTTPException as e:
                if 400 <= e.status < 500 and e.status != 429:
                    # Discord rejected this specific message (bad data) — skip it for good
                    # so it doesn't retry forever.
                    log.error(
                        "discord rejected %s (%s): %s; skipping", x.id, e.status, e.text
                    )
                    self.store.mark([store_id(source, x.id)])
                else:
                    log.warning(
                        "send failed for %s (%s); will retry next cycle", x.id, e.status
                    )
            await asyncio.sleep(1)  # be gentle; discord.py also handles 429s itself
        log.info(
            "cycle done: source: %s, posted %d, seeded %d, backlog %d, tracked %d",
            source.name,
            sent,
            len(plan.mark_silently),
            plan.backlog,
            self.store.count(),
        )

    async def run_cycle(self) -> None:
        # One source failing must not skip the others, but the cycle still counts
        # as failed so poll() doesn't write the heartbeat (Docker HEALTHCHECK).
        failed = []
        for source in self.cfg.sources:
            try:
                await self.run_source(source)
            except Exception:
                log.exception("cycle failed for source %s", source.name)
                failed.append(source.name)
        if failed:
            raise RuntimeError(f"sources failed: {', '.join(failed)}")


def main() -> None:
    cfg = Config.from_env()
    logging.basicConfig(
        level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if cfg.dry_run:
        from .dryrun import main as dry

        asyncio.run(dry())
        return
    cfg.validate_for_discord()
    log.info(
        "starting: sources=%s categories=%s keywords=%d us_only=%s every %dmin",
        cfg.sources,
        cfg.categories or "ALL",
        len(cfg.title_keywords),
        cfg.us_only,
        cfg.poll_minutes,
    )
    InternshipBot(cfg).run(cfg.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
