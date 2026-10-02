"""PTT Stock board (批踢踢 Stock 版) posts about a Taiwan stock.

PTT's Stock board is Taiwan's busiest retail stock forum. Its web front end
serves a board search (``/bbs/Stock/search?q=``, 20 posts a page, newest first)
and each post's page, which carries the body and the replies, each tagged
推 (agree), 噓 (disagree) or → (neutral). A post's id embeds the epoch second
it was posted (``M.1790943882.A.49A``), so posts are dated exactly and trimmed
to the analysis window; the search reaches back only so far, so an older window
is reported unavailable rather than empty.

No key. Returns a formatted plaintext block and never raises, like the other
social fetchers; a failed fetch is reported as unavailable, never as silence.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import UTC, datetime

import requests

from tradingagents.dataflows.date_window import coverage_gap, in_window

logger = logging.getLogger(__name__)

BOARD_URL = "https://www.ptt.cc/bbs/Stock"
TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; TradingAgents)"

# Pages read per search term, newest first; reading stops once a page reaches
# back past the window's start.
SEARCH_PAGES = 3
# Posts listed in the block, and how many of them (the most discussed) are
# opened for their body and replies.
MAX_POSTS = 15
MAX_BODIES = 8
EXCERPT_CHARS = 280
_SCREEN_CHARS = 600

_POST_ID = re.compile(r"/bbs/Stock/M\.(\d+)\.A\.[0-9A-F]+\.html")
_ENTRY_SPLIT = '<div class="r-ent">'
_STANCE = re.compile(r"^\s*\[標的\].*?([多空])\s*$")
_TEMPLATE = re.compile(r"請勿|板規|處分|此行請刪除|網址超過一行")


def _get(url: str, params: dict | None = None) -> str | None:
    try:
        response = requests.get(
            url, params=params, timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT}, cookies={"over18": "1"},
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.warning("PTT fetch failed for %s: %s", url, exc)
        return None


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _score(nrec: str) -> int:
    """The list's reply score: a number, 爆 (100+), or X1..XX (net disagreement)."""
    nrec = nrec.strip()
    if nrec == "爆":
        return 100
    if nrec.startswith("X"):
        return -100 if nrec == "XX" else -10 * int(nrec[1:] or 1)
    return int(nrec) if nrec.isdigit() else 0


def parse_search_page(page: str) -> list[dict]:
    """Posts on one search page: ``{url, title, author, score, posted}``."""
    posts = []
    for chunk in page.split(_ENTRY_SPLIT)[1:]:
        link = re.search(r'<a href="([^"]+)">(.*?)</a>', chunk, re.S)
        if not link:
            continue  # a deleted post keeps its row but loses its link
        match = _POST_ID.search(link.group(1))
        if not match:
            continue
        nrec = re.search(r'<div class="nrec">(.*?)</div>', chunk, re.S)
        author = re.search(r'<div class="author">(.*?)</div>', chunk, re.S)
        posts.append({
            "url": "https://www.ptt.cc" + link.group(1),
            "title": _text(link.group(2)),
            "author": _text(author.group(1)) if author else "",
            "score": _score(_text(nrec.group(1))) if nrec else 0,
            "posted": datetime.fromtimestamp(int(match.group(1)), tz=UTC),
        })
    return posts


def parse_post_page(page: str) -> dict:
    """A post's body excerpt and its reply tags: ``{body, push, boo, neutral}``."""
    main = re.search(r'<div id="main-content"[^>]*>(.*)', page, re.S)
    content = re.sub(r"<(script|style)\b.*?</\1>", "", main.group(1) if main else "", flags=re.S)
    tags = re.findall(r'<span class="[^"]*push-tag">\s*(\S)', content)
    # Each header line (author, board, title, time) is one div of spans.
    body = re.sub(r'<div class="article-metaline(?:-right)?">.*?</div>', "", content, flags=re.S)
    body = re.split(r'<div class="push">|※ 發信站', body, maxsplit=1)[0]
    # News reposts keep the board's form, whose instruction lines are not content.
    lines = [line for line in _text(body).splitlines() if not _TEMPLATE.search(line)]
    body = " ".join(" ".join(lines).split())
    return {
        "body": body,
        "push": tags.count("推"),
        "boo": tags.count("噓"),
        "neutral": tags.count("→"),
    }


def _search(term: str, start: datetime) -> tuple[list[dict], bool] | None:
    """Posts matching ``term``, newest first, and whether the search reached back
    to ``start`` (or ran out of results); None if the first page failed."""
    found: list[dict] = []
    for page_no in range(1, SEARCH_PAGES + 1):
        page = _get(f"{BOARD_URL}/search", {"q": term, "page": page_no})
        if page is None:
            return (found, False) if found else None
        posts = parse_search_page(page)
        found.extend(posts)
        if len(posts) < 20:
            return found, True
        if min(p["posted"] for p in posts) < start:
            return found, True
    return found, False


def stance(title: str) -> str | None:
    """The direction a [標的] (pick) post declares in its title: 多 or 空."""
    match = _STANCE.match(title)
    return match.group(1) if match else None


def fetch_ptt_posts(
    stock_id: str,
    name: str | None,
    *,
    start_date: str,
    end_date: str,
    screen=None,
) -> str:
    """PTT Stock posts about one stock within ``[start_date, end_date]`` as a text block.

    Searches by code and by name; ``screen`` (see ``post_screen``) can drop
    off-topic posts before the cut.
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    label = f"{name} ({stock_id})" if name else stock_id

    fetched: dict[str, dict] = {}
    searched = 0
    covered = True  # every search reached back to the window's start
    for term in [stock_id] + ([name] if name else []):
        result = _search(term, start_dt.replace(tzinfo=UTC))
        if result is None:
            covered = False
            continue
        posts, reached = result
        searched += 1
        covered = covered and reached
        for post in posts:
            fetched.setdefault(post["url"], post)
    if not searched:
        return "<PTT unavailable: the board search failed; this is not an absence of discussion>"

    posts = sorted(
        (p for p in fetched.values() if in_window(p["posted"], start_dt, end_dt)),
        key=lambda p: p["posted"], reverse=True,
    )
    if not posts:
        if not covered:
            return (f"<PTT unavailable for {start_date}..{end_date}: the board search only reached "
                    f"recent posts, so this is not an absence of discussion of {label}>")
        gap = coverage_gap([], start_date, end_date, "PTT Stock board search", f"discussion of {label}") \
            if end_date > datetime.now(UTC).strftime("%Y-%m-%d") else None
        return gap or f"<no PTT Stock posts about {label} within {start_date}..{end_date}>"

    note = ""
    if screen:
        keep, note = screen([p["title"][:_SCREEN_CHARS] for p in posts])
        posts = [p for p, kept in zip(posts, keep, strict=True) if kept]
        if not posts:
            return f"{note}\n<no PTT Stock posts about {label} after screening>"

    posts = posts[:MAX_POSTS]
    for post in sorted(posts, key=lambda p: p["score"], reverse=True)[:MAX_BODIES]:
        page = _get(post["url"])
        if page is not None:
            post.update(parse_post_page(page))

    picks = [stance(p["title"]) for p in posts]
    lines = [
        f"PTT Stock board — {len(posts)} posts about {label} within {start_date}..{end_date} "
        f"(searched by code{' and name' if name else ''}); [標的] picks declaring 多 (long): "
        f"{picks.count('多')}, 空 (short): {picks.count('空')}."
    ]
    for p in posts:
        replies = (f"; replies 推 {p['push']} / 噓 {p['boo']} / → {p['neutral']}"
                   if "push" in p else "")
        lines.append(f"  [{p['posted']:%Y-%m-%d}] {p['title']} (list score {p['score']:+d}{replies})")
        body = p.get("body", "")
        if body:
            excerpt = body[:EXCERPT_CHARS] + ("…" if len(body) > EXCERPT_CHARS else "")
            lines.append(f"    body excerpt: {excerpt}")
    return "\n".join(([note] if note else []) + lines)
