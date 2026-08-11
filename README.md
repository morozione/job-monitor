# Android Job Monitor (Ukraine) → Telegram

Checks DOU's Android vacancy feed plus a few career pages (Kyivstar, PrivatBank,
Oschadbank, MODUS X) on a schedule and pings you on Telegram when something new
shows up.

## 1. Create a Telegram bot (2 minutes)

1. Open Telegram, search for **@BotFather**, send `/newbot`.
2. Follow the prompts (name, username). BotFather gives you a **bot token**
   like `123456789:AAExampleTokenHere`. Save it.
3. Send your new bot any message (e.g. "hi") so it can message you back.
4. Get your **chat ID**: open this URL in a browser (replace `<TOKEN>`):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Find `"chat":{"id": 123456789, ...}` in the response — that number is your
   chat ID.

## 2. Put this code in a GitHub repo

1. Create a new **private** GitHub repo (private is fine and recommended,
   this is just for you).
2. Push all these files (`job_monitor.py`, `requirements.txt`, `state.json`,
   `.github/workflows/job_monitor.yml`, this README) to the repo root.

## 3. Add your secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

- `TELEGRAM_BOT_TOKEN` = the token from BotFather
- `TELEGRAM_CHAT_ID` = your chat ID

## 4. Enable and test

- Go to the **Actions** tab, enable workflows if prompted.
- Click **Job Monitor → Run workflow** to trigger it manually the first time.
- Check the run logs. If Telegram creds are correct, you'll get a message on
  the first run listing everything currently "new" (since state.json starts
  empty) — that's expected, it's establishing the baseline.
- After that, it only messages you about genuinely new items, running
  automatically twice a day per the cron schedule in the workflow file.

## 5. If a career page shows zero results every time

Some career pages (especially Kyivstar's, which may be a modern JS-driven
site) might not expose job links in the raw HTML that `requests.get()` sees —
the content gets built by JavaScript in the browser, which this simple
scraper doesn't execute. If you notice a company never triggers alerts even
when you know a new role posted:

- Open the page in your browser, right-click → **View Page Source** (not
  "Inspect" — you want the *raw* HTML, not the rendered DOM).
- Search for "android" in that raw source. If it's not there, the page is
  JS-rendered and this script can't see it.
- Fix: either check that company manually/via LinkedIn alerts instead, or
  ask me to swap that source to use Playwright (a headless browser) — more
  setup, but handles JS-rendered pages.

## 6. Adjust the schedule or sources

- Change the `cron` line in `.github/workflows/job_monitor.yml` to run more
  or less often.
- Add/remove companies in the `CAREER_PAGES` dict in `job_monitor.py`.
- Verify the DOU RSS URL still works by checking `jobs.dou.ua` for a feed
  link — DOU has changed feed URL formats before.
