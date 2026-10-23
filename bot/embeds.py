"""Turn a Listing into a Discord embed + Apply button (matches the old bot's cards)."""
from __future__ import annotations

import discord

from .feed import Listing

CATEGORY_COLORS = {
    "Software": 0x4F8EF7,
    "Hardware": 0xF5A623,
    "AI/ML/Data": 0x9B59B6,
    "Product": 0x2ECC71,
    "Quant": 0xE74C3C,
    "Finance/Business": 0x1ABC9C,
    "Engineering": 0xA0522D,
}


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _valid_url(u: str) -> bool:
    return u.startswith(("http://", "https://")) and len(u) <= 512


def format_locations(locs: list[str], limit: int = 4) -> str:
    if not locs:
        return "Not listed"
    shown = ", ".join(locs[:limit])
    if len(locs) > limit:
        shown += f" +{len(locs) - limit} more"
    return _trunc(shown, 1024)


def build_embed(x: Listing) -> discord.Embed:
    e = discord.Embed(
        title=_trunc(x.company, 256),
        url=x.company_url if _valid_url(x.company_url) else None,
        color=CATEGORY_COLORS.get(x.category, 0x95A5A6),
    )
    e.add_field(name="Role", value=_trunc(x.title, 1024), inline=False)
    e.add_field(name="Location", value=format_locations(x.locations), inline=False)
    if x.date_posted:
        # <t:UNIX:R> renders client-side as "2 hours ago" in each viewer's timezone.
        e.add_field(name="Posted", value=f"<t:{x.date_posted}:R>", inline=True)
    e.add_field(name="Category", value=x.category, inline=True)
    if x.sponsorship and x.sponsorship != "Other":
        e.add_field(name="Sponsorship", value=x.sponsorship, inline=True)
    footer = "Source: Simplify.jobs"
    if x.terms:  # New Grad listings have no terms
        footer += " • " + ", ".join(x.terms)
    e.set_footer(text=footer)
    return e


def build_view(x: Listing) -> discord.ui.View | None:
    """Link buttons just open a URL — no callback or persistent view needed."""
    if not _valid_url(x.url):
        return None
    v = discord.ui.View(timeout=None)
    v.add_item(discord.ui.Button(label="Apply", style=discord.ButtonStyle.link, url=x.url, emoji="↗️"))
    return v
