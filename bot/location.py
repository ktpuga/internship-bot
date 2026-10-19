"""Decide whether a Simplify location string is in the United States.

Allowlist approach: a location counts as US only if it positively matches a
US pattern. Anything unrecognized is treated as non-US, so a new foreign
format can't leak through. (Note "London, UK" looks like "City, ST" — that's
why state codes are checked against the real list.)
"""
from __future__ import annotations

import re

STATE_CODES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
    "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split()
)
STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia", "washington dc", "washington, dc", "puerto rico",
}
# Shorthands Simplify uses for big metros / remote.
ALIASES = {"nyc", "sf", "south sf", "la", "remote", "us", "usa", "united states"}

_STATE_SUFFIX = re.compile(r",\s*([A-Z]{2})$")
_US_WORDS = re.compile(r"\b(usa|united states|u\.s\.)\b", re.I)


def is_us(loc: str) -> bool:
    s = loc.strip()
    low = s.lower()
    if low in ALIASES or low in STATE_NAMES:
        return True
    m = _STATE_SUFFIX.search(s)
    if m:
        return m.group(1) in STATE_CODES
    return bool(_US_WORDS.search(s))  # "Remote in USA", "Austin, Texas, United States"


def us_locations(locs: list[str]) -> list[str]:
    return [l for l in locs if is_us(l)]
