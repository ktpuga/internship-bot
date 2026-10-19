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

## Configuration

See `.env.example`. Required: `DISCORD_TOKEN`, `CHANNEL_ID`.
Categories: `Software`, `Hardware`, `AI/ML/Data`, `Product`, `Quant` (empty = all).

## Discord setup

1. discord.com/developers/applications → New Application → **Bot** → Reset Token (save it).
   Leave all Privileged Gateway Intents **off**.
2. OAuth2 → URL Generator → scopes `bot` (+ `applications.commands` for later) →
   permissions **View Channels, Send Messages, Embed Links** → open URL, add to server.
3. Discord Settings → Advanced → Developer Mode on → right-click channel → Copy Channel ID.

## Run locally (test server first)

```bash
cp .env.example .env          # fill in token + test channel ID
docker compose up --build     # compose reads .env automatically
# or without Docker:
pip install -r requirements.txt
set -a; source .env; set +a; DB_PATH=./data/seen.db python -m bot.main
```

Dry run (no Discord needed): `DRY_RUN=1 DB_PATH=./data/seen.db python -m bot.main`

Tests: `pip install pytest && PYTHONPATH=tests python -m pytest -q`

## Deploy on kronos (Dokploy)

1. Push this folder to a **private** GitHub repo (`.env` is git-ignored — keep it that way).
2. Dokploy → your project → **Create Service → Compose** → provider GitHub → pick the repo,
   branch `main`, compose path `./docker-compose.yml`.
3. **Environment** tab: set `DISCORD_TOKEN`, `CHANNEL_ID` (and any overrides).
4. **Deploy**. Check **Logs** for `logged in as ...` then `cycle done: posted 0, seeded N ...`.
5. Optional: enable auto-deploy so a `git push` redeploys.

No ports are exposed — the bot only makes outbound connections (GitHub + Discord).

## Operating it

- Health: `docker ps` shows `(healthy)` once a cycle has completed in the last ~50 min.
- Reset state (re-seed): stop the service and delete the `bot-data` volume.
- Change filters: edit env vars in Dokploy and redeploy. Newly-included categories
  only post postings that appear *after* the change (older ones were already marked seen
  only if they matched before — anything never seen within `MAX_AGE_DAYS` will post).
