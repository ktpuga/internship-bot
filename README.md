# KTP Internship Bot

Posts new internship listings to a Discord channel. Reads the public
[SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships)
JSON feed every 15 minutes, posts anything new as an embed with an **Apply** button,
and remembers what it has posted in SQLite. Runs as one Docker container on kronos via Dokploy.

## How it works

```
every POLL_MINUTES
  └─ GET listings.json  (If-None-Match: <etag>  → usually 304, no download)
  └─ filter: active + visible + TERMS + CATEGORIES + posted within MAX_AGE_DAYS
  └─ diff against seen.db  → new IDs
  └─ post up to MAX_POSTS_PER_CYCLE (oldest first), mark each ID only after it sends
  └─ write /data/heartbeat (used by Docker HEALTHCHECK)
```

- **First boot** marks every current posting as seen without posting (no 1,000-message flood).
  Set `SEED_POST_LATEST=5` to post the 5 newest so the channel isn't empty.
- **Failed sends** (Discord outage, 5xx) aren't marked, so they retry next cycle.
  Messages Discord rejects as invalid (4xx) are skipped permanently.
- **Restart-safe**: state lives in the `/data` volume.

| File | Role |
|---|---|
| `bot/config.py` | All settings from env vars |
| `bot/feed.py` | Download (ETag-cached), normalize categories, filter |
| `bot/store.py` | SQLite set of seen IDs |
| `bot/poller.py` | Decides what to post this cycle (pure logic, unit-tested) |
| `bot/embeds.py` | Embed + Apply button |
| `bot/main.py` | Discord client + 15-min loop |
| `bot/dryrun.py` | One cycle, prints instead of posting |
