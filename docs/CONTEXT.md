# Context & decisions — KTP Internship Bot

Single source of truth so a new chat can pick this up.

## Goal
Replace the frat's broken internship bot (someone else's, used Internly) with Yash's own,
hosted on kronos. Posts new internship (and optionally new-grad) listings to Discord channels.

## Decisions (2026-10-09)
| Decision | Choice | Why |
|---|---|---|
| Data source | SimplifyJobs `listings.json` (dev branch) only | Structured JSON with id/category/terms/sponsorship; Internly's cards were Simplify data anyway. vanshb03 deferred (needs cross-source dedup). |
| Language | Python 3.13 + discord.py 2.7 | Simplest async polling bot; easy JSON/SQLite. |
| Hosting | Docker container via Dokploy on kronos | Already runs Dokploy; Git-push deploys; Docker/CI resume value. |
| v1 scope | Auto-post + category filter via env vars | Ship fast; slash commands later. |
| State | SQLite in `/data` volume | One file, no server; enough for ~20k IDs. |
| Polling | 15 min with ETag conditional GET | Feed is ~13 MB; 304s make polls nearly free. |

## Design rules
- Mark an ID seen only after its message sends → no lost postings on Discord errors.
- First run seeds silently (optionally posts N newest).
- Cap per cycle (25); overflow carries to next cycle.
- Skip postings older than 14 days (guards against old postings re-activated upstream).
- Least privilege: no privileged intents; perms = View/Send/Embed Links; non-root container; no exposed ports.
- Multi-source: seen IDs and filter fingerprints are namespaced per source (`{name}:{id}`, `filter_fingerprint:{name}`).

## Feed facts (checked 2026-10-18)
~17k entries, ~3.7k tagged Summer 2027, ~1.1k active+visible Software/Hardware Summer 2027.
Category spellings vary (`Software` vs `Software Engineering`) — normalized in `feed.py`.
Fields: id, company_name, title, locations[], category, terms[], url, company_url,
date_posted (unix), active, is_visible, sponsorship, degrees.
New Grad feed (SimplifyJobs/New-Grad-Positions) same shape but no `terms` (uses `degrees`); filter with empty TERMS.

## Decisions (2026-10-19)
| Decision | Choice | Why |
|---|---|---|
| Deploy | Dokploy Application, Dockerfile build, volume → /data | Nixpacks couldn't infer the start command and ignores our Dockerfile |
| Finance/business | Quant category + title keyword match, labeled Finance/Business | Simplify has no finance category; no clean structured feed for IB/accounting/consulting; scraping rejected (brittle, ToS) |
| Channel | Same channel for internship categories | Yash's call |
| Locations | US only (allowlist) | Yash's call |
| Filter changes | Fingerprint in DB → silent reseed | Prevent flooding when filters widen |

## Decisions (2026-10-19 — New Grad)
| Decision | Choice | Why |
|---|---|---|
| New Grad | Same app, second Simplify feed each poll | Same JSON schema; no second container |
| New Grad channel | Separate Discord channel (`NEWGRAD_CHANNEL_ID`) | Keep internship vs full-time audiences apart |
| New Grad terms | Empty (no term filter) | Feed has no `terms` field |
| Shared filters | CATEGORIES / TITLE_KEYWORDS / US_ONLY | Keep ops simple; override later if needed |
| Opt-in | Only when `NEWGRAD_CHANNEL_ID` is set | Deploy without New Grad until the channel exists |

## Status
v0.2 live path on kronos. v0.3 (multi-source New Grad) built and tested locally; needs Dokploy
`NEWGRAD_CHANNEL_ID` + bot perms on the new channel, then push + redeploy (see CHANGELOG.md).
Upgrade note: fingerprint meta key is now per-source → one-time silent reseed of internships.

## Ideas / backlog (not started)
- Slash commands: `/setchannel`, `/filters`, `/search company`
- Per-category channel routing (#swe, #hardware, #security)
- Keyword routing for security roles (title contains security/cyber/SOC)
- Add vanshb03 source with company+title dedup
- Ping a role for specific companies
