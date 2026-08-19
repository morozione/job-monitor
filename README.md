# Job Vacancy Monitor → Telegram

Watches job sources for postings matching a keyword you choose, and pings you
on Telegram the moment something new shows up. Runs entirely on GitHub
Actions' free tier — no server, no database, no paid services.

Ships configured out of the box to watch for **Android developer** roles in
Ukraine (DOU.ua + a handful of company career pages), but the keyword and
company list are just config — retarget it at iOS, backend, whatever you're
looking for, in a couple of minutes.

## How it works

Every run does the same four things:

1. **Fetch** from three kinds of sources:
   - **RSS** (DOU.ua) — structured, reliable, parsed with `feedparser`.
   - **Career-page HTML scraping** — plain `requests.get()` + BeautifulSoup,
     looking for any link whose text or URL contains your keyword(s). Only
     works if the site renders job listings in the raw HTML response — see
     [Limitations](#limitations).
   - **Job-board JSON APIs** (Lever, Breezy HR) — companies using these
     recruiting platforms expose a public JSON feed of postings, which is
     far more reliable than scraping.
2. **Diff** what was found against `state.json` (a JSON file checked into
   the repo, tracking which item IDs / link snippets we've already alerted
   on) to figure out what's actually new.
3. **Alert** — anything new gets formatted into one message and posted to
   Telegram via the Bot API. If Telegram credentials aren't set (e.g. running
   locally), it just prints the message instead of sending.
4. **Persist** — `state.json` gets rewritten with the updated seen-state,
   and the GitHub Actions workflow commits that file back to the repo. That
   commit *is* the database — the next scheduled run starts by checking out
   the repo and picking up where the last one left off.

GitHub Actions' `schedule:` trigger (cron) wakes a throwaway Ubuntu VM up on
a timer, runs the script, and the VM disappears — nothing runs continuously.

## Quickstart

### 1. Use this template

Click **Use this template** (or fork it) to get your own copy. Keep it
private or public, your call — nothing in the repo itself is sensitive
(secrets live in GitHub's secret store, never in code or `state.json`).

### 2. Create a Telegram bot (2 minutes)

1. Open Telegram, message **@BotFather**, send `/newbot` and follow the
   prompts. You'll get a **bot token** like `123456789:AAExampleTokenHere`.
2. Send your new bot any message (e.g. "hi") — it can't message you first.
3. Get your **chat ID**: visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
   in a browser (swap in your real token) and find `"chat":{"id": 123456789, ...}`.

### 3. Set your secrets

In your repo: **Settings → Secrets and variables → Actions → Secrets tab**

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat ID |

### 4. (Optional) Set what keyword(s) to search for

Same place, but the **Variables tab** (not Secrets — this isn't sensitive,
and variables are easier to see/edit at a glance):

| Name | Value | Default if unset |
|---|---|---|
| `SEARCH_KEYWORDS` | comma-separated, case-insensitive, plain substring match, e.g. `ios,swift` | `android` |

This retargets the career-page and job-board checks. **DOU's RSS feed is
separately filtered by a `category=` URL param** (defaults to Android) —
if you change `SEARCH_KEYWORDS` to something else, update `DOU_RSS_FEEDS` in
`job_monitor.py` to match (check `jobs.dou.ua/vacancies/` for valid category
values). The script also locally filters DOU entries against
`SEARCH_KEYWORDS` as a safety net, so a mismatch just means fewer/no results
rather than mislabeled ones.

### 5. Customize the company list (optional)

Edit these dicts in `job_monitor.py`:

- `CAREER_PAGES` — company name → career page URL, scraped for matching links.
- `LEVER_BOARDS` — company name → Lever board slug (from `jobs.lever.co/<slug>`).
- `BREEZY_BOARDS` — company name → Breezy HR slug (from `<slug>.breezy.hr`).

### 6. Enable and test

- Go to the **Actions** tab and enable workflows if prompted.
- **Job Monitor → Run workflow** to trigger it manually.
- Check the run logs. First run will likely alert on everything currently
  matching (since `state.json` starts empty/fresh) — that's expected, it's
  establishing the baseline. After that, only genuinely new items trigger
  an alert, running automatically twice a day per the cron schedule.

## Limitations

**JS-rendered career pages won't work.** `requests.get()` is a plain HTTP
client — it doesn't execute JavaScript. If a company's careers page loads
job listings client-side (React/Vue/Next.js widgets, iframes), the scraper
only ever sees an empty shell and will silently find nothing, forever. This
project intentionally does **not** add a headless browser (Playwright/
Selenium) to work around this — it's a meaningful complexity/cost tradeoff
for a free-tier tool. If a career page never seems to find anything:

1. Open it in your browser, **View Page Source** (not "Inspect" — you want
   the raw HTML the server actually sent, not the rendered DOM).
2. Search for your keyword in that raw source. If it's not there, the
   listings are JS-rendered and this scraper can't see them.
3. Options: check that source manually, look for a JSON API behind the
   widget (see how `LEVER_BOARDS`/`BREEZY_BOARDS` do this for ATS-backed
   career pages) and add it as a new source type, or accept the gap.

## Project layout

```
job_monitor.py                  # main script
requirements.txt                # Python deps
state.json                      # seen-item tracking (auto-updated by CI)
.github/workflows/job_monitor.yml  # schedule + run + commit-state workflow
```

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, change it, no attribution
required (though a star is always appreciated).
