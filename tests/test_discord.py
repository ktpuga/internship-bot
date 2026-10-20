"""Exercise the Discord layer with a fake channel (no network, no token)."""

import asyncio

import discord

from bot.config import Config
from bot.embeds import build_embed, build_view, format_locations
from bot.feed import Listing
from bot.main import InternshipBot

from bot.poller import fingerprint_key, store_id
from test_core import item, src


def listing(**kw):
    return Listing.from_raw({**item(1), **kw})


def test_embed_shape():
    x = listing(company_name="Lyft", title="Data Analyst Intern", locations=["NYC"])
    e = build_embed(x)
    names = [f.name for f in e.fields]
    assert e.title == "Lyft" and names[:3] == ["Role", "Location", "Posted"]
    assert e.fields[2].value == f"<t:{x.date_posted}:R>"
    assert "Simplify" in e.footer.text


def test_long_location_list_truncates():
    assert format_locations([f"City{i}" for i in range(10)]).endswith("+6 more")


def test_apply_button_and_bad_url():
    v = build_view(listing())
    assert (
        v.children[0].url == "https://x/1"
        and v.children[0].style is discord.ButtonStyle.link
    )
    assert build_view(listing(url="javascript:alert(1)")) is None


class FakeChannel:
    def __init__(self, fail_ids=()):
        self.sent, self.fail_ids = [], set(fail_ids)

    async def send(self, embed=None, view=None):
        if embed.fields[0].value in self.fail_ids:
            raise discord.HTTPException(
                type("R", (), {"status": 503, "reason": "x"})(), "boom"
            )
        self.sent.append(embed.title)


class FakeFeed:
    def __init__(self, raw):
        self.raw = raw

    async def fetch(self):
        return self.raw


def run(bot, ch, raw, monkeypatch):
    monkeypatch.setattr(bot, "get_channel", lambda _id: ch)
    bot.feeds = {s.name: FakeFeed(raw) for s in bot.cfg.sources}
    monkeypatch.setattr("bot.main.asyncio.sleep", _noop)
    asyncio.run(bot.run_cycle())


async def _noop(*_):
    return None


def test_cycle_posts_and_retries(monkeypatch, tmp_path):
    s = src()
    cfg = Config(
        discord_token="x",
        sources=[s],
        db_path=str(tmp_path / "seen.db"),
        max_age_days=0,
    )
    bot = InternshipBot(cfg)
    bot.store.mark([store_id(s, "preexisting")])  # DB not empty
    bot.store.set_meta(fingerprint_key(s), cfg.filter_fingerprint(s))
    raw = [item(1), {**item(2), "title": "FAILS"}]
    ch = FakeChannel(fail_ids={"FAILS"})
    run(bot, ch, raw, monkeypatch)
    assert ch.sent == ["Co1"]
    # transient failure -> not marked, retried next cycle
    ch2 = FakeChannel()
    run(bot, ch2, raw, monkeypatch)
    assert ch2.sent == ["Co2"]
    # nothing left
    ch3 = FakeChannel()
    run(bot, ch3, raw, monkeypatch)
    assert ch3.sent == []
