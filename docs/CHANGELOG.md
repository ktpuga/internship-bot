# Changelog / build log

## v0.1.0 — 2026-10-18
Built in stages, each verified before the next.

**S1 — feed + diff (no Discord)**
- `config.py`, `feed.py` (ETag fetch, category normalization, filters), `store.py` (SQLite), `poller.py`, `dryrun.py`.
- Verified: 6 unit tests; live feed run 1 seeded 1,102 Software/Hardware Summer 2027 postings and posted 0;
  run 2 found 0 new; deleting 3 IDs from the DB made exactly those 3 show as new.

**S2 — Discord layer**
- `embeds.py` (card: company, role, location, posted <t:…:R>, category, sponsorship; Apply link button),
  `main.py` (client, 15-min `tasks.loop`, per-message error handling, heartbeat).
- Verified: 4 more tests (10 total) with a fake channel — embed layout, location truncation,
  unsafe URL → no button, transient send failure retried next cycle.
- Not verified here: real Discord login (discord.com unreachable from build sandbox) → test on first local run.

**S4 — Docker / Dokploy**
- `Dockerfile` (python:3.13-slim, non-root uid 10001, /data volume, heartbeat HEALTHCHECK),
  `docker-compose.yml` (named volume, restart policy, log rotation), `.env.example`, ignore files.
- Verified: `docker compose config` valid; image steps reproduced in a clean venv with only shipped files
  (dry run OK, DB + heartbeat written); healthcheck returns healthy/unhealthy correctly.
- Not verified here: `docker build` (registry pulls blocked in sandbox) → first build happens on Yash's machine/kronos.

**S3 — slash commands**: skipped for v1 (scope decision).

## Known issues
- ~~Feed includes non-US postings~~ fixed in v0.2 (US_ONLY).

## README trim — 2026-10-19
- Removed Configuration, Discord setup, Run locally, Deploy and Operating sections from README (team already knows repo workflow). Setup steps remain in .env.example.

## v0.2.0 — 2026-10-19
Deployed v0.1 to kronos via Dokploy (Application service, build type switched from Nixpacks → Dockerfile,
volume `internship-bot-data` → `/data`). Then:

- **Finance/Business**: Simplify feed has no finance category. Added `TITLE_KEYWORDS` (built-in default list in
  `config.py`) — titles matching any keyword are posted from any category, labeled Finance/Business (teal).
  Added `Quant` to default CATEGORIES. Same channel as tech postings (decision).
- **US only**: new `bot/location.py`, `US_ONLY` (default true). Allowlist matching; card shows only US locations.
- **Filter fingerprint**: `meta` table in SQLite; changing TERMS/CATEGORIES/keywords/US_ONLY silently seeds newly
  matching postings instead of flooding the channel.
- Verified against live feed: keywords add ~115 Finance/Business postings (Summer 2027, all-time); US filter drops
  166 postings, all UK/Canada. Upgrade path: v0.1 DB → v0.2 seeds 236 silently, next cycle posts 0. 15/15 tests.
- Known noise: TikTok "Business Integrity" ML research roles match "business". Tune keywords if it's annoying.
