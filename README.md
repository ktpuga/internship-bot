# KTP Internship Bot

Posts new internship and (optionally) new-grad listings to Discord. Each poll cycle
reads the public SimplifyJobs JSON feeds — 
[Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) and, when
`NEWGRAD_CHANNEL_ID` is set,
[New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) —
posts anything new as an embed with an **Apply** button, and remembers what it has posted
in SQLite. Runs as one Docker container on kronos via Dokploy.

## How it works

```
every POLL_MINUTES
  for each source (internship; + newgrad if NEWGRAD_CHANNEL_ID is set)
    └─ GET that source's listings.json  (If-None-Match: <etag>  → usually 304)
    └─ filter: active + visible + source TERMS + posted within MAX_AGE_DAYS
             + (CATEGORIES or title matches a finance/business keyword)
             + at least one US location (US_ONLY)
    └─ diff against seen.db using namespaced IDs ({source}:{id})
    └─ post up to MAX_POSTS_PER_CYCLE to that source's channel (oldest first);
       mark each ID only after it sends
  └─ write /data/heartbeat (used by Docker HEALTHCHECK)
```

- **Sources**: Internships always run (`CHANNEL_ID`, `TERMS`, `FEED_URL`). New Grad is
  opt-in via `NEWGRAD_CHANNEL_ID` (empty terms — that feed has no `terms` field).
  Shared filters: `CATEGORIES`, `TITLE_KEYWORDS`, `US_ONLY`, caps, age.
- **First boot** marks every current posting as seen without posting (no 1,000-message flood).
  Set `SEED_POST_LATEST=5` to post the 5 newest so the channel isn't empty.
  This only applies on a fresh DB: a source enabled later (e.g. New Grad) seeds fully silently.
- **Failed sends** (Discord outage, 5xx) aren't marked, so they retry next cycle.
  Messages Discord rejects as invalid (4xx) are skipped permanently.
- **Restart-safe**: state lives in the `/data` volume.
- **Filter changes don't flood**: a per-source fingerprint is stored in the DB; when it changes,
  newly matching postings are marked seen silently and only postings that appear afterwards get posted.
- **Finance/Business**: Simplify has no finance category, so titles matching keywords
  (finance, banking, accounting, consulting, strategy, sales, risk, …) are pulled in from any
  category and labeled Finance/Business. Classic IB/accounting/consulting programs mostly aren't in this feed.
- **Engineering**: same mechanism for mechanical/manufacturing/systems roles (mechanical, manufacturing,
  robotics, aerospace, quality engineer, …), labeled Engineering and checked before Finance/Business.
  Low volume: Simplify's feeds are tech-focused, so classic ME/civil/chemical roles are rare.
- **US only**: allowlist match on state codes/names, NYC/SF/LA, "USA"/"United States". Foreign locations are
  dropped from the card; postings with no US location are skipped.

| File | Role |
|---|---|
| `bot/config.py` | All settings from env vars; `Source` list (internship / newgrad) |
| `bot/feed.py` | Download (ETag-cached), normalize categories, filter, keyword match |
| `bot/location.py` | US location detection |
| `bot/store.py` | SQLite: seen IDs + meta (per-source filter fingerprint) |
| `bot/poller.py` | Decides what to post this cycle (pure logic, unit-tested) |
| `bot/embeds.py` | Embed + Apply button |
| `bot/main.py` | Discord client + 15-min loop over sources |
| `bot/dryrun.py` | One cycle per source, prints instead of posting |
