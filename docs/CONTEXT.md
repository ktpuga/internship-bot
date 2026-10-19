# Context & decisions — KTP Internship Bot

Single source of truth so a new chat can pick this up.

## Goal
Replace the frat's broken internship bot (someone else's, used Internly) with Yash's own,
hosted on kronos. Posts new internship listings to a Discord channel.

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

## Feed facts (checked 2026-10-18)
~17k entries, ~3.7k tagged Summer 2027, ~1.1k active+visible Software/Hardware Summer 2027.
Category spellings vary (`Software` vs `Software Engineering`) — normalized in `feed.py`.
Fields: id, company_name, title, locations[], category, terms[], url, company_url,
date_posted (unix), active, is_visible, sponsorship, degrees.

## Status
See CHANGELOG.md. Next: Yash creates the Discord app (S0), tests locally, deploys.

## Ideas / backlog (not started)
- Location filter (feed includes UK/Canada postings)
- Slash commands: `/setchannel`, `/filters`, `/search company`
- Per-category channel routing (#swe, #hardware, #security)
- Keyword routing for security roles (title contains security/cyber/SOC)
- Add vanshb03 source with company+title dedup
- Ping a role for specific companies
