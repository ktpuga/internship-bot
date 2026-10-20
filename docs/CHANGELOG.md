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

## v0.3.0 — 2026-10-19
Multi-source polling in one Discord process:

- **Sources**: `Config.sources` — always `internship` (`CHANNEL_ID` / `FEED_URL` / `TERMS`); optional `newgrad`
  when `NEWGRAD_CHANNEL_ID` is set (default feed SimplifyJobs/New-Grad-Positions, empty terms).
- **Isolation**: seen IDs stored as `{source}:{id}`; filter fingerprint meta key `filter_fingerprint:{source}`.
  Shared CATEGORIES / TITLE_KEYWORDS / US_ONLY / caps across sources.
- **Loop**: each poll cycle fetches every source (separate ETag clients), plans, posts to that source's channel;
  one source failing does not skip the others.
- **Upgrade**: renaming the fingerprint meta key causes a one-time silent reseed of internship matches (no flood).
- Verified: 15/15 unit tests (`PYTHONPATH=. pytest`). Deploy: set `NEWGRAD_CHANNEL_ID`, grant View/Send/Embed
  on the new channel, redeploy.

### Review fixes (PR #1) — 2026-10-20
- New Grad footer no longer ends in a dangling "•" (that feed has no terms).
- First-run detection is now per source (`is_empty(prefix)`), so `SEED_POST_LATEST` works when New Grad is
  enabled on an existing DB.
- One-time, idempotent migration moves pre-multi-source seen IDs under `internship:` and drops the old
  `filter_fingerprint` key — prevents the upgrade from looking like a first run and removes dead rows.
- Verified on live feeds: main DB → this branch with SEED_POST_LATEST=3 posts 0 (1,222 IDs migrated);
  enabling New Grad seeds 1,762 and posts 3; next cycle posts 0 on both. 19/19 tests.
