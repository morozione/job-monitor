"""
Android job monitor for Ukraine.

Checks:
  1. DOU.ua RSS feed(s) for new Android vacancies (reliable, structured).
  2. Raw career pages of priority companies (Kyivstar, PrivatBank, Oschadbank,
     MODUS X) for any link/text mentioning "android" that wasn't there last run.

Sends a Telegram message summarizing anything new. State (what we've already
seen) is stored in state.json so re-running doesn't re-notify you.

Run manually:   python job_monitor.py
Run in CI:      see .github/workflows/job_monitor.yml
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
import feedparser
from bs4 import BeautifulSoup

# Windows terminals often default stdout to a non-UTF-8 codepage (e.g. cp1251),
# which crashes on the emoji/Ukrainian text in our messages. Force UTF-8 so
# local runs don't blow up; GitHub Actions' runners are already UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATE_FILE = Path(__file__).parent / "state.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Sources -----------------------------------------------------------

# DOU provides RSS for filtered vacancy searches. Verify this URL still
# works by visiting jobs.dou.ua/vacancies/?category=Android in a browser
# and looking for an RSS/feed link/icon — DOU has changed feed URLs before.
DOU_RSS_FEEDS = {
    "DOU – Android category": "https://jobs.dou.ua/vacancies/feeds/?category=Android",
}

# Career pages that don't have RSS — we do a lightweight "did anything
# mentioning android change" check instead of parsing exact job listings,
# since every company's HTML is different and JS-rendered pages won't work
# with a simple requests.get() at all (see NOTE below per-company).
CAREER_PAGES = {
    "Kyivstar": "https://www.kyivstar.ua/uk/about/career",
    "PrivatBank": "https://work.privatbank.ua/",
    "Oschadbank": "https://www.oschadbank.ua/career",
    "MODUS X (DOU listings)": "https://jobs.dou.ua/companies/modus-x/vacancies/",
}

KEYWORD_RE = re.compile(r"android", re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobMonitorBot/1.0; personal use)"
}


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen_dou_ids": [], "seen_career_snippets": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def check_dou_feeds(state):
    new_items = []
    seen = set(state.get("seen_dou_ids", []))

    for label, url in DOU_RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                print(f"[warn] Could not parse feed for {label}: {feed.bozo_exception}")
                continue
            for entry in feed.entries:
                entry_id = entry.get("id") or entry.get("link")
                if not entry_id:
                    continue
                if entry_id not in seen:
                    new_items.append(
                        {
                            "source": label,
                            "title": entry.get("title", "Untitled"),
                            "link": entry.get("link", url),
                        }
                    )
                    seen.add(entry_id)
        except Exception as exc:  # noqa: BLE001 - keep going on other sources
            print(f"[warn] Error checking {label}: {exc}")

    state["seen_dou_ids"] = list(seen)
    return new_items


def check_career_pages(state):
    """
    Very lightweight change-detector: pull all <a> tags whose visible text
    or href mentions 'android', and diff against what we saw last time.

    NOTE: if a company's career page is a JS single-page-app (React/Vue),
    requests.get() will only see the empty shell HTML and this will find
    nothing. If that happens for a given company, this check will silently
    report zero android links every time — not a bug, just a limit of
    simple HTML fetching. In that case check the page manually or swap in
    a headless-browser tool (e.g., playwright) for that one source.
    """
    new_items = []
    snippets_state = state.get("seen_career_snippets", {})

    for label, url in CAREER_PAGES.items():
        seen_for_company = set(snippets_state.get(label, []))
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            candidates = set()
            for a in soup.find_all("a"):
                text = (a.get_text() or "").strip()
                href = a.get("href", "")
                if KEYWORD_RE.search(text) or KEYWORD_RE.search(href):
                    snippet = f"{text} | {href}".strip()
                    if snippet:
                        candidates.add(snippet)

            new_for_company = candidates - seen_for_company
            for snippet in new_for_company:
                new_items.append({"source": label, "title": snippet, "link": url})

            snippets_state[label] = list(candidates)

        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Error checking {label}: {exc}")

    state["seen_career_snippets"] = snippets_state
    return new_items


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[warn] Telegram credentials not set, skipping send. Message was:")
        print(message)
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        api_url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    if resp.status_code != 200:
        print(f"[error] Telegram send failed: {resp.status_code} {resp.text}")


def format_message(dou_items, career_items):
    lines = []
    if dou_items:
        lines.append("🆕 New DOU Android vacancies:")
        for item in dou_items:
            lines.append(f"• {item['title']}\n  {item['link']}")
        lines.append("")

    if career_items:
        lines.append("🏢 New Android mentions on career pages:")
        for item in career_items:
            lines.append(f"• [{item['source']}] {item['title']}\n  {item['link']}")

    return "\n".join(lines).strip()


def main():
    state = load_state()

    dou_items = check_dou_feeds(state)
    career_items = check_career_pages(state)

    save_state(state)

    if not dou_items and not career_items:
        print("No new items found.")
        return

    message = format_message(dou_items, career_items)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    sys.exit(main())
