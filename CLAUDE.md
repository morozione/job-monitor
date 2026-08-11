# CLAUDE.md — Instructions for Claude Code

## What this project is

A Python bot that monitors Ukrainian job sites (DOU.ua RSS + a few company
career pages: Kyivstar, PrivatBank, Oschadbank, MODUS X) for new Android
developer vacancies, and sends alerts to Telegram. It runs on a schedule via
GitHub Actions (free tier), no server needed.

Files:
- `job_monitor.py` — main script
- `requirements.txt` — Python deps
- `state.json` — tracks what's already been seen, so we don't get repeat alerts
- `.github/workflows/job_monitor.yml` — GitHub Actions schedule (runs 2x/day)
- `README.md` — full human-readable setup guide

## Your task

Get this running end-to-end as a scheduled GitHub Actions bot. Concretely:

1. **Sanity-check the code first.** Read `job_monitor.py`. Confirm the
   dependencies in `requirements.txt` install cleanly and the script has no
   syntax errors (`python -m py_compile job_monitor.py`). Run it locally once
   without Telegram secrets set — it should print a "Telegram credentials not
   set, skipping send" warning and still print the message content to stdout,
   rather than crashing. Fix anything broken.

2. **Initialize git and create a GitHub repo** (use the `gh` CLI if
   available; ask me to run `gh auth login` first if it's not authenticated).
   Make the repo **private**. Suggested name: `android-job-monitor`.

3. **Push all files**, preserving the `.github/workflows/` folder structure —
   GitHub Actions only picks up workflows from that exact path.

4. **Set up repo secrets.** You cannot generate these yourself — stop and ask
   me for two values:
   - `TELEGRAM_BOT_TOKEN` (from @BotFather on Telegram)
   - `TELEGRAM_CHAT_ID` (from the getUpdates API call, see README.md)

   Once I give them to you, set them with:
   ```
   gh secret set TELEGRAM_BOT_TOKEN --body "<value I gave you>"
   gh secret set TELEGRAM_CHAT_ID --body "<value I gave you>"
   ```
   Never print these values back to me or commit them to any file — secrets
   only, never in code or logs.

5. **Trigger a manual run** to verify it works end-to-end:
   ```
   gh workflow run job_monitor.yml
   ```
   Then check the run status/logs with `gh run list` and `gh run view
   --log`. Confirm it completed successfully and (if secrets are correct)
   that I received a Telegram message.

6. **Report back** with: the repo URL, confirmation the first scheduled run
   succeeded, and a plain-language summary of what happens next (it'll now
   run automatically twice a day per the cron schedule in the workflow
   file).

## Known limitation to watch for

The career-page scraping (Kyivstar especially) uses a simple HTTP GET and
parses static HTML — it will **not** see content that's rendered client-side
by JavaScript. If a run completes successfully but a career-page source
never seems to find anything even when you know new roles are posted there,
check `README.md` section 5 for how to diagnose this, and flag it to me
rather than silently leaving it broken. Don't attempt to add a headless
browser (Playwright/Selenium) to fix this unless I explicitly ask — it adds
real complexity and I'd rather decide that trade-off knowingly.

## Constraints

- Keep this free-tier friendly — no paid services, no always-on server.
- Don't change the alert channel from Telegram without asking me.
- Don't add new source websites without asking — I have a specific list of
  companies I care about (see `CAREER_PAGES` in `job_monitor.py`).
