# CLAUDE.md — Instructions for Claude Code

## What this project is

A public, template-able Python bot that monitors job sources for postings
matching a configurable keyword and sends alerts to Telegram. Shipped
configured for Android developer vacancies in Ukraine (DOU.ua RSS + a few
company career pages / job-board APIs), but `SEARCH_KEYWORDS` and the source
lists are meant to be retargeted by anyone who forks it. Runs on a schedule
via GitHub Actions (free tier), no server needed. See `README.md` for the
full setup/customization guide — that's the source of truth for end users;
keep it in sync with any behavior change.

Files:
- `job_monitor.py` — main script. Four source types: DOU RSS
  (`check_dou_feeds`), career-page HTML link-scraping (`check_career_pages`),
  Lever/Breezy job-board JSON APIs (`check_lever_boards`/`check_breezy_boards`),
  and international remote-only job boards (`check_wwr_feeds`,
  `check_remoteok`, `check_remotive`, `check_jobicy`, `check_arbeitnow`) for
  English-speaking remote roles outside Ukraine.
- `requirements.txt` — Python deps.
- `state.json` — tracks what's already been seen (per source type, separate
  buckets), committed back to the repo by CI after every run — this file
  *is* the persistence layer, there's no database.
- `.github/workflows/job_monitor.yml` — schedule (2x/day), runs the script
  with secrets/vars injected, commits the updated `state.json`.
- `LICENSE` — MIT.
- `README.md` — full human-readable setup guide.

## Working on this repo

- This is Ivan's personal repo, now public as a community template. Treat
  README.md as documentation other forkers will actually read — keep it
  accurate when you change behavior (new source types, new env vars, new
  limitations discovered).
- Running the script locally without Telegram secrets set should print a
  "Telegram credentials not set, skipping send" warning and still print the
  message content to stdout, rather than crashing. Don't break that.
- Local test runs mutate `state.json`. Before committing, check whether your
  local run's changes to `state.json` should be kept (advances real seen-state,
  fine to commit) or reverted (if it consumed items that haven't actually
  been alerted on and you want the next real run to still alert on them). If
  the remote has moved since you last synced (scheduled runs commit
  `state.json` on their own cadence), rebase and take the remote's
  `state.json` over any local test-run pollution — it reflects real
  accumulated state.
- Never print Telegram secret values back to the user or commit them to any
  file — secrets only, injected via GitHub Actions env vars.

## Known limitation to watch for

Career-page scraping uses a simple HTTP GET and parses static HTML — it will
**not** see content that's rendered client-side by JavaScript (confirmed
dead for Kyivstar, PrivatBank, Oschadbank, and the MODUS X DOU listing as of
2026-08 — their listings load via JS/widgets requests.get() can't see). If a
run completes successfully but a source never seems to find anything even
when new roles are known to exist there, check README.md's Limitations
section for how to diagnose this, and flag it explicitly rather than
silently leaving it broken. Don't add a headless browser (Playwright/
Selenium) to fix this unless explicitly asked — real complexity for a
free-tier tool, worth deciding knowingly. Prefer finding a JSON API behind
the widget (as done for Lever/Breezy) over adding a browser dependency.

## Constraints

- Keep this free-tier friendly — no paid services, no always-on server.
- Don't change the alert channel from Telegram without asking.
- Don't add new source websites without asking — verify candidate URLs
  actually work (HTTP 200, and real matching content in the raw response —
  not JS-rendered) before proposing them, the way the Lever/Breezy/monobank/
  MacPaw additions were verified in August 2026. Exception on record: the
  We Work Remotely/RemoteOK/Remotive/Jobicy/Arbeitnow international boards
  (added 2026-08) were approved by the user but NOT live-verified, because
  the dev session that added them had no outbound network access to those
  sites — built from each API's public docs instead. Confirm they still
  work by checking Actions run logs for `[warn] Error checking <source>`
  after a real run; fix or remove any that error out consistently.
- `SEARCH_KEYWORDS` is a GitHub Actions *variable*, not a secret — it isn't
  sensitive, and variables are easier for forkers to see/edit. Don't move it
  to secrets.
