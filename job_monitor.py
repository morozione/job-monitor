"""
Keyword-based job vacancy monitor, defaulting to Android roles in Ukraine.

Checks:
  1. DOU.ua RSS feed(s) for matching vacancies (reliable, structured).
  2. Raw career pages of configured companies for any link/text matching
     SEARCH_KEYWORDS that wasn't there last run.
  3. Lever / Breezy HR job-board JSON APIs for configured companies.

Sends a Telegram message summarizing anything new. State (what we've already
seen) is stored in state.json so re-running doesn't re-notify you. What to
search for is controlled by the SEARCH_KEYWORDS env var / repo variable
(defaults to "android") -- see README.md to retarget this at a different
keyword or role.

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

# What to search for. Comma-separated, case-insensitive, matched as a plain
# substring against job titles / link text (not a regex). Defaults to
# "android" so this behaves exactly as before if unset. Override via the
# SEARCH_KEYWORDS repo *variable* (Settings -> Secrets and variables ->
# Actions -> Variables tab) -- not a secret, since it's not sensitive, and
# variables are easier to see/edit than secrets.
SEARCH_KEYWORDS = [
    kw.strip() for kw in (os.environ.get("SEARCH_KEYWORDS") or "android").split(",") if kw.strip()
]

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
#
# Kyivstar, PrivatBank, Oschadbank and the MODUS X DOU listing are confirmed
# (2026-08) to never actually find anything here: their job listings load
# via client-side JS/widgets, so requests.get() only sees an empty shell.
# Left in place since they're harmless and DOU RSS is the real safety net,
# but don't expect alerts from them.
CAREER_PAGES = {
    "Kyivstar": "https://www.kyivstar.ua/uk/about/career",
    "PrivatBank": "https://work.privatbank.ua/",
    "Oschadbank": "https://www.oschadbank.ua/career",
    "MODUS X (DOU listings)": "https://jobs.dou.ua/companies/modus-x/vacancies/",
    "monobank": "https://monobank.ua/en/careers",
    "MacPaw": "https://macpaw.com/jobs",
}

# Companies whose career sites run on Lever (https://jobs.lever.co/<slug>).
# Lever exposes a public JSON API of postings per board, which is far more
# reliable than scraping the corporate site's HTML.
LEVER_BOARDS = {
    "Ajax Systems": "ajax",
}

# Companies whose career sites run on Breezy HR (https://<slug>.breezy.hr).
# Breezy exposes a public JSON feed of postings per board (<slug>.breezy.hr/json).
BREEZY_BOARDS = {
    "Genesis": "gen-tech",
}

KEYWORD_RE = re.compile("|".join(re.escape(kw) for kw in SEARCH_KEYWORDS), re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobMonitorBot/1.0; personal use)"
}


def load_state():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    else:
        state = {}
    state.setdefault("seen_dou_ids", [])
    state.setdefault("seen_career_snippets", {})
    state.setdefault("seen_lever_ids", [])
    state.setdefault("seen_breezy_ids", [])
    return state


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
                if not KEYWORD_RE.search(entry.get("title", "")):
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


def check_lever_boards(state):
    """Lever's public JSON API: https://api.lever.co/v0/postings/<slug>?mode=json"""
    new_items = []
    seen = set(state.get("seen_lever_ids", []))

    for label, slug in LEVER_BOARDS.items():
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            for posting in resp.json():
                title = posting.get("text", "")
                if not KEYWORD_RE.search(title):
                    continue
                posting_id = posting.get("id")
                if not posting_id or posting_id in seen:
                    continue
                new_items.append(
                    {
                        "source": f"{label} (Lever)",
                        "title": title,
                        "link": posting.get("hostedUrl", url),
                    }
                )
                seen.add(posting_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Error checking {label} (Lever): {exc}")

    state["seen_lever_ids"] = list(seen)
    return new_items


def check_breezy_boards(state):
    """Breezy HR's public JSON feed: https://<slug>.breezy.hr/json"""
    new_items = []
    seen = set(state.get("seen_breezy_ids", []))

    for label, slug in BREEZY_BOARDS.items():
        url = f"https://{slug}.breezy.hr/json"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            for posting in resp.json():
                title = posting.get("name", "")
                if not KEYWORD_RE.search(title):
                    continue
                posting_id = posting.get("id")
                if not posting_id or posting_id in seen:
                    continue
                new_items.append(
                    {
                        "source": f"{label} (Breezy)",
                        "title": title,
                        "link": posting.get("url", url),
                    }
                )
                seen.add(posting_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Error checking {label} (Breezy): {exc}")

    state["seen_breezy_ids"] = list(seen)
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


def format_message(dou_items, career_items, board_items):
    keywords = "/".join(SEARCH_KEYWORDS)
    lines = []
    if dou_items:
        lines.append(f"🆕 New DOU vacancies matching '{keywords}':")
        for item in dou_items:
            lines.append(f"• {item['title']}\n  {item['link']}")
        lines.append("")

    if board_items:
        lines.append(f"📋 New job-board vacancies matching '{keywords}':")
        for item in board_items:
            lines.append(f"• [{item['source']}] {item['title']}\n  {item['link']}")
        lines.append("")

    if career_items:
        lines.append(f"🏢 New career-page mentions matching '{keywords}':")
        for item in career_items:
            lines.append(f"• [{item['source']}] {item['title']}\n  {item['link']}")

    return "\n".join(lines).strip()


def main():
    state = load_state()

    dou_items = check_dou_feeds(state)
    career_items = check_career_pages(state)
    board_items = check_lever_boards(state) + check_breezy_boards(state)

    save_state(state)

    if not dou_items and not career_items and not board_items:
        print("No new items found.")
        return

    message = format_message(dou_items, career_items, board_items)
    print(message)
    send_telegram(message)


if __name__ == "__main__":
    sys.exit(main())
