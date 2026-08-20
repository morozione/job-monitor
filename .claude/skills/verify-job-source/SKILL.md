---
name: verify-job-source
description: Vet a candidate new job source (career page, ATS board, or job-board API) before adding it to job_monitor.py, or diagnose why an existing source finds nothing. Use whenever proposing a new CAREER_PAGES/LEVER_BOARDS/BREEZY_BOARDS/*_BOARDS entry, or investigating a source that never seems to alert.
---

# Verifying a job source before adding (or debugging) it

CLAUDE.md's Constraints say: don't add a source without verifying it
actually works. This is the checklist for doing that properly — guessing
from a site's marketing page or API docs alone is not enough; every source
added so far (Lever, Breezy, monobank, MacPaw, RemoteOK, Jobicy, Arbeitnow,
WWR) was live-tested with real HTTP requests first.

## 1. Confirm it's reachable and not JS-rendered

```
curl -s -A "Mozilla/5.0 (compatible; JobMonitorBot/1.0; personal use)" "<url>" -o /tmp/out -w "HTTP %{http_code}\n"
```

- HTTP must be 200 (not blocked by bot protection like Incapsula/Cloudflare
  — SoftServe was rejected for exactly this).
- For HTML career pages: grep the raw response for real `<a>` tags whose
  text/href mentions the target keyword. If your keyword string is nowhere
  in the raw HTML, the listings are client-side rendered and this scraper
  (`requests.get()` + BeautifulSoup, no JS execution) will never see them —
  don't add it as a `CAREER_PAGES` entry. Note it as a known-dead source
  instead (see the Kyivstar/PrivatBank/Oschadbank/MODUS X precedent).
- For JSON APIs (Lever/Breezy-style): confirm the response is real JSON
  with the fields the code expects (id, title/position/name field, url).

## 2. Check whether the source needs per-keyword filtering, not just a fixed fetch

This is the mistake that caused the RemoteOK/Jobicy "found nothing"
incident (2026-08): some general job-board APIs only return their most
*recent* N postings across ALL categories, not the full current listing.
For a niche keyword, that recent-N slice can legitimately contain zero
matches even though matching jobs exist right now. Check:

- Fetch the plain/unfiltered endpoint and grep for the keyword in the
  title field across the *whole* response. Zero hits doesn't necessarily
  mean the source is broken — it might mean the returned set is too narrow.
- If it's suspiciously narrow (tens of postings, recency-sorted), look for
  a real server-side filter param (`?tags=`, `?tag=`, `?category=`,
  `?search=`). Test it directly — don't trust that a documented param
  actually filters; Arbeitnow's `?tags=` was found to be silently ignored
  (same response either way), while RemoteOK's `?tags=` and Jobicy's
  `?tag=` were confirmed to genuinely filter server-side.
- If a real filter param exists, query it once per `SEARCH_KEYWORDS` entry
  (see `check_remoteok`/`check_jobicy` for the pattern) rather than fetching
  the unfiltered feed once — and still re-check the keyword against the
  title client-side afterward, since tag filters can be loose/noisy.
- If no working filter param exists, it's fine to just scan the full
  current listing client-side (as `check_wwr_feeds`/`check_arbeitnow` do)
  — but document in a comment that it's expected to go quiet for runs at a
  time on a niche keyword, so a future debugging session doesn't mistake
  quiet-because-no-matches for broken.

## 3. Check the dedup identifier is actually stable

Whatever field is used to key `state["seen_*_ids"]` must not change for the
same posting across fetches, or it'll cause repeat alerts (this bit DOU:
its RSS `id`/`guid` embeds a timestamp DOU bumps periodically for the same
vacancy — fixed by keying on `link` instead, which only carries a static
`utm_source` param). Fetch the source twice a few seconds apart and diff
the candidate id field for the same postings before trusting it.

## 4. Wire it in

- Add the fetch function following the existing `check_*` pattern (own
  `seen_*_ids` state bucket via `load_state()`'s `setdefault`, try/except
  per source with a `[warn]` print on failure so CI logs show it clearly
  rather than crashing the whole run).
- Update `README.md`'s source list and Limitations section, and
  `CLAUDE.md`'s Files/Constraints sections, to match.
- Report exactly what you verified (HTTP status, real keyword matches
  found, filter-param behavior) back to the user rather than just saying
  "added it" — this repo has been burned before by sources that were added
  on faith and silently never fired.
