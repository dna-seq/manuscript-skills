# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27", "beautifulsoup4>=4.12"]
# ///
"""Watch the pages where venues state their AI policy, and say which ones changed since they were read.

Every URL in venues.yaml (`url`, `ai_policy_url`, `sources`) is fetched, reduced to the passages that talk about
AI, and compared with the snapshot kept in references/policy-snapshots/. Snapshots are plain text under git,
so `git log -p` on a snapshot is the history of that policy.

    uv run --script policy_watch.py list                         # every watched URL, its venues, last read
    uv run --script policy_watch.py check                        # fetch all, report changed / unchanged / blocked
    uv run --script policy_watch.py check --venue KEY --routes httpx,chrome   # an author's task: read, store nothing
    uv run --script policy_watch.py check --venue aging-cell --update   # maintenance: re-read one venue and store it
    uv run --script policy_watch.py check --stale-days 30 --update      # maintenance: URLs not read for 30 days
    uv run --script policy_watch.py record URL saved.html        # compare a page saved from a browser
    uv run --script policy_watch.py record URL saved.html --update   # maintenance: also store it as the snapshot

Only `--update` writes, and it writes into the plugin's own references: that is catalogue maintenance, never part
of an author's task. An archived copy (the Internet Archive route) is dated by its capture and is not the current
rule; the report says so, and the live page is still to be read.

A page that could not be read is `not_assessed` in the JSON ("Could not be read" in the printed report), never
`unchanged`. The printed report quotes each changed passage before and after, with the heading it sits under.
Exit code 1 when a page changed or is gone, 3 when nothing changed but at least one page could not be read (not a
clean result).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional

import httpx
import typer
import yaml
from bs4 import BeautifulSoup

app = typer.Typer(add_completion=False, no_args_is_help=True)

REFERENCES = Path(__file__).resolve().parents[2] / "manuscript-integrity-check" / "references"
VENUES_YAML = REFERENCES / "venues.yaml"
SNAPSHOTS = REFERENCES / "policy-snapshots"
INDEX = SNAPSHOTS / "index.yaml"

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/140.0 Safari/537.36")
CHALLENGE_MARKERS = ("just a moment...", "cf-browser-verification", "challenge-platform", "attention required! | cloudflare",
                     "enable javascript and cookies to continue", "verifying you are human", "px-captcha",
                     "request unsuccessful. incapsula", "are you a robot", "checking your browser")
MIN_PAGE_CHARS = 500  # less than this after extraction is a stub, a login wall or a JS shell, not a policy page

# Passages that talk about AI. "AI" alone is matched case-sensitively; the rest in any case.
AI_WORDS = re.compile(r"\b(generative|artificial intelligence|large language models?|LLMs?|chat ?gpt|chatbots?|"
                      r"gen ?ai|machine[- ]generated|ai[- ](?:assisted|generated|based|tools?|technolog\w*|use|"
                      r"writing|detection|detectors?))\b", re.IGNORECASE)
AI_CAPS = re.compile(r"\bAI\b")
BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "td", "th", "blockquote", "pre", "summary"]
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6", "summary", "dt"}
DROP_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "form", "svg", "iframe", "button"]

# What the printed report calls each fetch route (the JSON and index.yaml keep the route codes).
ROUTE_LABEL = {"httpx": "plain download", "chrome": "headless browser", "wayback": "Internet Archive lookup"}
ROUTE_WORDS = {"httpx": "a plain download", "chrome": "a headless browser", "browser": "a copy saved from a browser",
               "webfetch": "a web-fetch tool"}
LEGACY_ROUTE_PREFIX = re.compile(r"\b(httpx|chrome|wayback): ")
EXCERPT_CHARS = 160  # a quoted passage is cut to about this many characters around what changed
CHANGES_SHOWN = 10
GROUPS = {
    "changed": ("Changed since the last read", "The passages about AI on these pages differ from the stored copy. "
                "Read each change and decide whether the rule itself moved."),
    "gone": ("No longer at this address", "These addresses answered that the page does not exist. Find where the "
             "journal moved its policy."),
    "not_assessed": ("Could not be read", "These pages were not checked at all, which is not the same as unchanged."),
    "new": ("Read for the first time", "No earlier copy of these pages was stored, so there is nothing to compare."),
    "unchanged": ("Unchanged", "The passages about AI are the same as in the stored copy."),
}


class Result(str, Enum):
    unchanged = "unchanged"
    changed = "changed"
    new = "new"
    gone = "gone"
    not_assessed = "not_assessed"


@dataclass
class Fetched:
    route: Optional[str]  # httpx | chrome | wayback:<timestamp> | the route named to `record`
    html: Optional[str] = None  # the page, or its plain text when `plain` (a PDF, a text file given to `record`)
    status: Optional[int] = None
    reason: Optional[str] = None
    plain: bool = False


@dataclass
class Outcome:
    url: str
    result: Result
    route: Optional[str]
    reason: str = ""
    blocks: int = 0
    venues: list[str] = field(default_factory=list)
    diff: list[str] = field(default_factory=list)
    body: Optional[str] = None
    changes: list[str] = field(default_factory=list)  # each change as a sentence quoting the passage before and after


# ------------------------------------------------------------------------------------------------ text

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2013: "-", 0x2014: "-", 0xA0: " "})
    return re.sub(r"\s+", " ", text).strip()


def is_ai_passage(text: str) -> bool:
    return bool(AI_WORDS.search(text) or AI_CAPS.search(text))


def page_blocks(html: str) -> list[tuple[str, str]]:
    """(tag, text) for each innermost block element, in document order."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(DROP_TAGS):
        tag.decompose()
    out: list[tuple[str, str]] = []
    for el in soup.find_all(BLOCK_TAGS):
        if el.find(BLOCK_TAGS):  # an outer block; its inner blocks carry the text
            continue
        text = normalize(el.get_text(" "))
        if text:
            out.append((el.name, text))
    return out


def text_blocks(text: str) -> list[tuple[str, str]]:
    """Plain text (from `record`): paragraphs separated by blank lines; a short line without a full stop is a heading."""
    out: list[tuple[str, str]] = []
    for para in re.split(r"\n\s*\n", text):
        para = normalize(para)
        if para:
            out.append(("h" if len(para) < 90 and not para.endswith(".") else "p", para))
    return out


def ai_extract(blocks: list[tuple[str, str]]) -> str:
    """The AI passages, each preceded once by the heading it sits under. Stable under layout and whitespace changes."""
    kept: list[str] = []
    seen: set[str] = set()
    heading: Optional[str] = None
    heading_written: Optional[str] = None
    for tag, text in blocks:
        if tag in HEADINGS or tag == "h":
            heading = text
            if is_ai_passage(text) and text not in seen:
                kept.append(f"## {text}")
                seen.add(text)
                heading_written = text
            continue
        if not is_ai_passage(text) or text in seen:
            continue
        if heading and heading != heading_written:
            if heading not in seen:
                kept.append(f"## {heading}")
                seen.add(heading)
            heading_written = heading
        kept.append(text)
        seen.add(text)
    return "\n\n".join(kept)


def digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ report

def route_words(route: Optional[str]) -> str:
    """How a page was read, in words: an archived copy is named with its capture date."""
    if not route:
        return "an unrecorded method"
    m = re.match(r"wayback:(\d{4})(\d{2})(\d{2})", route)
    if m:
        return f"the Internet Archive's copy of {m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ROUTE_WORDS.get(route, route)


def plain_reason(reason: str) -> str:
    """A stored failure reason; older index entries name the fetch routes by their codes."""
    return LEGACY_ROUTE_PREFIX.sub(lambda m: f"{ROUTE_LABEL[m.group(1)]}: ", reason)


def _cut_left(text: str, room: int) -> str:
    if len(text) <= room:
        return text
    tail = text[len(text) - room:]
    return "[...] " + (tail.split(" ", 1)[1] if " " in tail else "")


def _cut_right(text: str, room: int) -> str:
    if len(text) <= room:
        return text
    head = text[:room]
    return (head.rsplit(" ", 1)[0] if " " in head else "") + " [...]"


def excerpt(text: str, start: int, end: int, width: int = EXCERPT_CHARS) -> str:
    """`text` with text[start:end] in bold, cut to about `width` characters around it. An empty span (text was only
    added on the other side) shows the context where the addition sits."""
    middle = _cut_right(text[start:end].strip(), width)
    room = max(0, width - len(middle)) // 2
    left = _cut_left(text[:start].rstrip(), room)
    right = _cut_right(text[end:].lstrip(), room)
    glue_left = " " if text[:start].endswith(" ") else ""
    glue_right = " " if text[end:].startswith(" ") else ""
    if not middle:
        return f"{left}{glue_left or glue_right}{right}".strip()
    return f"{left}{glue_left}**{middle}**{glue_right}{right}".strip()


TOKEN = re.compile(r"[\w'-]+|[^\w\s]")


def _changed_span(before: str, after: str) -> Optional[tuple[int, int, int, int]]:
    """Character spans, in `before` and in `after`, from the first to the last word or mark that differs."""
    ta, tb = list(TOKEN.finditer(before)), list(TOKEN.finditer(after))
    ops = [op for op in difflib.SequenceMatcher(a=[m.group() for m in ta], b=[m.group() for m in tb],
                                                autojunk=False).get_opcodes() if op[0] != "equal"]
    if not ops:
        return None

    def span(tokens: list[re.Match[str]], i: int, j: int, text: str) -> tuple[int, int]:
        if i == j:  # nothing on this side: an empty span where the other side's words go
            pos = tokens[i].start() if i < len(tokens) else len(text)
            return pos, pos
        return tokens[i].start(), tokens[j - 1].end()

    return (*span(ta, ops[0][1], ops[-1][2], before), *span(tb, ops[0][3], ops[-1][4], after))


def _heading_before(paras: list[str], idx: int) -> Optional[str]:
    return next((p[3:] for p in reversed(paras[:idx]) if p.startswith("## ")), None)


def _kind(para: str) -> tuple[str, str]:
    return ("heading", para[3:]) if para.startswith("## ") else ("passage", para)


def _under(heading: Optional[str]) -> str:
    return f'Under the heading "{heading}", the' if heading else "The"


def describe_changes(old: str, new: str) -> list[str]:
    """Each changed, removed or added passage as a sentence that quotes it, with the heading it sits under and the
    changed words in bold. Passages are paired in order within a changed stretch."""
    a, b = (old.split("\n\n") if old else []), (new.split("\n\n") if new else [])
    out: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        pairs = list(zip(a[i1:i2], b[j1:j2]))
        for k, (x, y) in enumerate(pairs):
            kind, before = _kind(x)
            _, after = _kind(y)
            spans = _changed_span(before, after)
            if spans is None:
                continue
            head = _heading_before(b, j1 + k) if kind == "passage" else None
            out.append(f'{_under(head)} {kind} that read "{excerpt(before, spans[0], spans[1])}" now reads '
                       f'"{excerpt(after, spans[2], spans[3])}".')
        for k, x in enumerate(a[i1 + len(pairs):i2]):
            kind, text = _kind(x)
            head = _heading_before(a, i1 + len(pairs) + k) if kind == "passage" else None
            out.append(f'{_under(head)} {kind} "{_cut_right(text, EXCERPT_CHARS)}" was removed.')
        for k, y in enumerate(b[j1 + len(pairs):j2]):
            kind, text = _kind(y)
            head = _heading_before(b, j1 + len(pairs) + k) if kind == "passage" else None
            out.append(f'{_under(head)} new {kind} "{_cut_right(text, EXCERPT_CHARS)}" was added.')
    return out


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def venue_names() -> dict[str, str]:
    raw = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
    return {k: v.get("name", k) for k, v in raw.items()}


def render(o: "Outcome", names: dict[str, str]) -> list[str]:
    """One page in the printed report: its URL, the venues that cite it, how it was read and what changed."""
    cited = _and([f"{names.get(k, k)} (`{k}`)" for k in o.venues]) if o.venues else "no venue"
    lines = [f"- {o.url}", f"  Cited for {cited}."]
    if o.result == Result.gone:
        lines.append(f"  The address answered that the page does not exist ({o.reason}).")
    elif o.result == Result.not_assessed:
        lines.append(f"  It could not be read: {plain_reason(o.reason) or 'no reason was recorded'}.")
    else:
        lines.append(f"  Read with {route_words(o.route)}; {o.blocks} of its passages mention AI."
                     + (f" {o.reason}" if o.reason else ""))
        if _route_kind(o.route) == "wayback":
            lines.append("  This is an archived copy, not the current rule: read the live page before relying on it.")
    lines += [f"  - {change}" for change in o.changes[:CHANGES_SHOWN]]
    if len(o.changes) > CHANGES_SHOWN:
        lines.append(f"  - {len(o.changes) - CHANGES_SHOWN} more changes are not shown; `--json FILE` writes "
                     "the full comparison.")
    return lines


# ------------------------------------------------------------------------------------------------ fetch

def _challenged(html: str) -> bool:
    head = html[:20000].lower()
    return any(m in head for m in CHALLENGE_MARKERS)


def _pdf_text(data: bytes) -> Optional[str]:
    """A PDF's text through poppler's pdftotext, or None when it is not installed."""
    binary = shutil.which("pdftotext")
    if binary is None:
        return None
    run = subprocess.run([binary, "-layout", "-", "-"], input=data, capture_output=True, timeout=120)
    return run.stdout.decode("utf-8", errors="replace") if run.returncode == 0 else None


def fetch_httpx(url: str) -> Fetched:
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"}, follow_redirects=True,
                      timeout=30)
    except httpx.HTTPError as e:
        return Fetched("httpx", reason=f"failed ({type(e).__name__}: {e})")
    if r.status_code in (404, 410):
        return Fetched("httpx", status=r.status_code, reason=f"HTTP {r.status_code}")
    if r.content[:5] == b"%PDF-" or "pdf" in r.headers.get("content-type", ""):
        text = _pdf_text(r.content)
        if text is None:
            return Fetched("httpx", status=r.status_code,
                           reason="got a PDF, and pdftotext (poppler) is not installed to read it; read the PDF "
                                  "with another tool")
        return Fetched("httpx", html=text, status=r.status_code, plain=True)
    if r.status_code >= 400 or _challenged(r.text):
        return Fetched("httpx", status=r.status_code, reason=f"was blocked (HTTP {r.status_code})")
    return Fetched("httpx", html=r.text, status=r.status_code)


CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "chrome.exe",
                "msedge", "msedge.exe")


def _chrome_paths() -> list[Path]:
    """Where Chrome, Chromium or Edge (which runs the same headless mode) installs itself outside the PATH."""
    if sys.platform == "darwin":
        apps = [Path("/Applications"), Path.home() / "Applications"]
        return [a / app / "Contents" / "MacOS" / exe for a in apps for app, exe in (
            ("Google Chrome.app", "Google Chrome"), ("Chromium.app", "Chromium"),
            ("Microsoft Edge.app", "Microsoft Edge"))]
    if os.name == "nt":
        roots = [os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        return [Path(r) / sub for r in roots if r for sub in (
            Path("Google") / "Chrome" / "Application" / "chrome.exe", Path("Chromium") / "Application" / "chrome.exe",
            Path("Microsoft") / "Edge" / "Application" / "msedge.exe")]
    return []


def _chrome() -> Optional[str]:
    found = next((shutil.which(b) for b in CHROME_NAMES if shutil.which(b)), None)
    return found or next((str(p) for p in _chrome_paths() if p.is_file()), None)


def fetch_chrome(url: str) -> Fetched:
    binary = _chrome()
    if binary is None:
        return Fetched("chrome", reason="could not run, because no Chrome or Chromium is installed")
    # On Windows the browser can hold its profile files for a moment after it exits; a leftover temporary
    # folder is not a failed read.
    with tempfile.TemporaryDirectory(prefix="policy-watch-", ignore_cleanup_errors=True) as profile:
        run = subprocess.run([binary, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
                              "--virtual-time-budget=15000", "--dump-dom", url],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if run.returncode != 0 or not (run.stdout or "").strip():
        return Fetched("chrome", reason=f"failed (exit code {run.returncode})")
    if _challenged(run.stdout):
        return Fetched("chrome", reason="was stopped by a challenge page")
    return Fetched("chrome", html=run.stdout)


def _wayback_latest(url: str) -> tuple[Optional[str], str]:
    """Timestamp of the newest archived 200 response: the CDX index first, the availability API as fallback."""
    try:
        r = httpx.get("https://web.archive.org/cdx/search/cdx", timeout=30,
                      params={"url": url, "output": "json", "limit": "-1", "filter": "statuscode:200", "fl": "timestamp"})
        rows = r.json()
        if len(rows) > 1:
            return rows[-1][0], ""
    except (httpx.HTTPError, ValueError):
        pass
    try:
        r = httpx.get("https://archive.org/wayback/available", params={"url": url}, timeout=30)
        closest = r.json().get("archived_snapshots", {}).get("closest") or {}
    except (httpx.HTTPError, ValueError) as e:
        return None, f"failed ({type(e).__name__})"
    return (closest["timestamp"], "") if closest.get("available") else (None, "found no archived copy")


def fetch_wayback(url: str, newer_than: Optional[date]) -> Fetched:
    stamp, why = _wayback_latest(url)
    if stamp is None:
        return Fetched("wayback", reason=why)
    taken = datetime.strptime(stamp[:8], "%Y%m%d").date()
    if newer_than is not None and taken <= newer_than:
        return Fetched("wayback", reason=f"found only a copy from {taken}, which is not newer than the stored one")
    got = fetch_httpx(f"https://web.archive.org/web/{stamp}id_/{url}")
    return Fetched(f"wayback:{stamp}", html=got.html, status=got.status, reason=got.reason)


def blocks_of(got: Fetched) -> list[tuple[str, str]]:
    return text_blocks(got.html or "") if got.plain else page_blocks(got.html or "")


def readable(blocks: list[tuple[str, str]]) -> bool:
    return sum(len(t) for _, t in blocks) >= MIN_PAGE_CHARS


def fetch(url: str, routes: list[str], last: Optional[date]) -> Fetched:
    """Each route in turn until one returns a readable page; a stub ("JavaScript is disabled") tries the next."""
    reasons: list[str] = []
    for route in routes:
        got = (fetch_httpx(url) if route == "httpx" else fetch_chrome(url) if route == "chrome"
               else fetch_wayback(url, last))
        if got.html is not None:
            if readable(blocks_of(got)):
                return got
            reasons.append(f"the {ROUTE_LABEL.get(route, route)} got a page too short to be the policy (a stub, "
                           "login wall or script shell)")
            continue
        if got.status in (404, 410) and route == "httpx":
            return got
        reasons.append(f"the {ROUTE_LABEL.get(route, route)} {got.reason}")
    return Fetched(None, reason="; ".join(reasons))


# ------------------------------------------------------------------------------------------------ data

def watched_urls(only: Optional[list[str]] = None) -> dict[str, list[str]]:
    """URL -> selected venues governed by it, including inherited publisher/parent policies."""
    raw = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
    out: dict[str, list[str]] = {}
    selected = list(only) if only else list(raw)

    def urls(key: str, seen: set[str], inherited: bool = False) -> list[str]:
        if key in seen or key not in raw:
            raise typer.BadParameter(f"Invalid venue inheritance at {key}.")
        entry = raw[key]
        candidates = [entry.get('ai_policy_url'), entry.get('publisher_policy_url')]
        if not inherited or entry.get('kind') == 'publisher':
            candidates += [entry.get('url'), *(entry.get('sources') or [])]
        own = [u for u in candidates if u]
        return own + (urls(entry['inherits'], seen | {key}, True) if entry.get('inherits') else [])

    for key in selected:
        for u in urls(key, set()):
            if u and key not in out.get(u, []):
                out.setdefault(u, []).append(key)
    if only and not out:
        raise typer.BadParameter(f"no URLs for {only}; is the key in venues.yaml?")
    return out


def load_index() -> dict[str, dict[str, Any]]:
    if not INDEX.exists():
        return {}
    return yaml.safe_load(INDEX.read_text(encoding="utf-8")) or {}


def save_index(index: dict[str, dict[str, Any]]) -> None:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    header = ("# Written by manuscript-journal-adapt/scripts/policy_watch.py. One entry per watched URL: the snapshot\n"
              "# file, when it was last read and how, and the last attempt when that attempt could not read the page.\n")
    INDEX.write_text(header + yaml.safe_dump(dict(sorted(index.items())), sort_keys=False, allow_unicode=True,
                                             width=120), encoding="utf-8")


def snapshot_name(url: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://(www\.)?", "", url.lower())).strip("-")[:80]
    return f"{stem}-{hashlib.sha1(url.encode()).hexdigest()[:8]}.txt"


def read_snapshot(entry: dict[str, Any]) -> Optional[str]:
    path = SNAPSHOTS / entry["file"]
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").split("\n---\n", 1)[-1].strip()


def write_snapshot(url: str, body: str) -> str:
    """The file holds only the URL and the passages, so an unchanged page leaves it byte-identical."""
    name = snapshot_name(url)
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    (SNAPSHOTS / name).write_text(f"url: {url}\n---\n{body}\n", encoding="utf-8")
    return name


def _route_kind(route: Optional[str]) -> str:
    return (route or "").split(":")[0]


def compare(url: str, got: Fetched, index: dict[str, dict[str, Any]], venues: list[str]) -> Outcome:
    if got.html is None:
        result = Result.gone if got.status in (404, 410) else Result.not_assessed
        return Outcome(url, result, got.route, got.reason or "", venues=venues)
    blocks = blocks_of(got)
    if not readable(blocks):
        return Outcome(url, Result.not_assessed, got.route, "the page was too short to be the policy (a stub, "
                       "login wall or script shell)", venues=venues)
    body = ai_extract(blocks)
    n = body.count("\n\n") + 1 if body else 0
    entry = index.get(url)
    old = read_snapshot(entry) if entry and "file" in entry else None  # an entry may hold only failed attempts
    if old is None:
        return Outcome(url, Result.new, got.route, "The page has no passages about AI." if not body else "", n, venues,
                       body=body)
    if digest(old) == digest(body):
        return Outcome(url, Result.unchanged, got.route, "", n, venues, body=body)
    note = ""
    if _route_kind(entry.get("route")) != _route_kind(got.route):
        note = (f"This read used {route_words(got.route)} and the stored copy {route_words(entry.get('route'))}, so "
                "some differences may come from how the page was read.")
    diff = list(difflib.unified_diff(old.split("\n\n"), body.split("\n\n"), "snapshot", "live", lineterm="", n=0))
    return Outcome(url, Result.changed, got.route, note, n, venues, diff, body, changes=describe_changes(old, body))


def route_date(route: Optional[str]) -> Optional[date]:
    """The capture date of an archived copy (`wayback:YYYYMMDDhhmmss`), which is when its text was current."""
    m = re.match(r"wayback:(\d{8})", route or "")
    return datetime.strptime(m.group(1), "%Y%m%d").date() if m else None


def apply(outcomes: list[Outcome], index: dict[str, dict[str, Any]], today: date) -> None:
    """Store what was read. An archived copy is dated by its capture, not by today, so `venues.py` shows its age."""
    for o in outcomes:
        if o.result in (Result.new, Result.changed, Result.unchanged) and o.body is not None and o.route:
            index[o.url] = {"file": write_snapshot(o.url, o.body), "read": (route_date(o.route) or today).isoformat(),
                            "route": o.route, "passages": o.blocks, "sha256": digest(o.body)}
        else:
            entry = index.setdefault(o.url, {})
            entry["last_attempt"] = {"date": today.isoformat(), "result": o.result.value, "reason": o.reason}
    save_index(index)


# ------------------------------------------------------------------------------------------------ commands

@app.command("list")
def list_cmd(venue: Annotated[Optional[list[str]], typer.Option(help="Only these venue keys")] = None) -> None:
    """Every watched URL with the venues that cite it and when it was last read."""
    index = load_index()
    typer.echo("| Policy page | Cited for (catalogue keys) | Last read | Read with | Passages about AI "
               "| Last failed attempt |")
    typer.echo("|---|---|---|---|---:|---|")
    for url, keys in sorted(watched_urls(venue).items()):
        e = index.get(url, {})
        att = e.get("last_attempt")
        failed = f"On {att['date']}, {plain_reason(att['reason'])}." if att else ""
        typer.echo(f"| {url} | {', '.join(keys)} | {e.get('read', 'never')} "
                   f"| {route_words(e['route']) if e.get('route') else ''} | {e.get('passages', '')} | {failed} |")


@app.command()
def check(
    venue: Annotated[Optional[list[str]], typer.Option(help="Only these venue keys (repeatable)")] = None,
    stale_days: Annotated[Optional[int], typer.Option(help="Only URLs not read for this many days")] = None,
    update: Annotated[bool, typer.Option(
        help="Write new and changed snapshots and the read dates into the plugin's references (catalogue "
             "maintenance only, never during an author's task)")] = False,
    routes: Annotated[str, typer.Option(
        help="Fetch routes in order: httpx, chrome, wayback. In an author's task use httpx,chrome, then the "
             "agent's own browser tool, before any archived copy")] = "httpx,chrome,wayback",
    workers: Annotated[int, typer.Option(help="Parallel fetches")] = 6,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Also write the outcomes as JSON")] = None,
) -> None:
    """Fetch the watched pages and compare their AI passages with the snapshots."""
    today = date.today()
    index = load_index()
    urls = watched_urls(venue)
    if stale_days is not None:
        urls = {u: k for u, k in urls.items()
                if "read" not in index.get(u, {}) or (today - date.fromisoformat(index[u]["read"])).days >= stale_days}
    route_list = [r.strip() for r in routes.split(",") if r.strip()]

    def one(item: tuple[str, list[str]]) -> Outcome:
        url, keys = item
        last = index.get(url, {}).get("read")
        return compare(url, fetch(url, route_list, date.fromisoformat(last) if last else None), index, keys)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = sorted(pool.map(one, urls.items()), key=lambda o: (o.result.value, o.url))
    order = [Result.changed, Result.gone, Result.not_assessed, Result.new, Result.unchanged]
    names = venue_names()
    typer.echo(f"Policy pages checked on {today}: {len(outcomes)} pages, compared with the passages about AI "
               "stored when each was last read.\n")
    for res in order:
        group = [o for o in outcomes if o.result == res]
        if not group:
            continue
        title, meaning = GROUPS[res.value]
        typer.echo(f"## {title} ({len(group)})\n\n{meaning}\n")
        for o in group:
            typer.echo("\n".join(render(o, names)))
        typer.echo("")
    if update:
        apply(outcomes, index, today)
        typer.echo(f"Snapshots and {INDEX.name} updated. Review `git diff` of policy-snapshots/, then update "
                   "venues.yaml and the reference notes for every venue whose rule moved.")
    if json_out:
        json_out.write_text(json.dumps([{**asdict(o), "result": o.result.value, "body": None} for o in outcomes],
                                       indent=2), encoding="utf-8")
    if any(o.result in (Result.changed, Result.gone) for o in outcomes):
        raise typer.Exit(1)
    if any(o.result == Result.not_assessed for o in outcomes):
        raise typer.Exit(3)


@app.command()
def record(
    url: Annotated[str, typer.Argument(help="A watched URL")],
    page_file: Annotated[Path, typer.Argument(help="The page saved from a browser (.html) or its text")],
    route: Annotated[str, typer.Option(help="How it was read, e.g. browser, webfetch")] = "browser",
    update: Annotated[bool, typer.Option(
        help="Also store it as the snapshot in the plugin's references (catalogue maintenance only, never during "
             "an author's task)")] = False,
) -> None:
    """Compare a page read by a route this script cannot use (saved from the user's own browser, or read with
    WebFetch, when a challenge page blocks the scripted routes) with the stored passages; --update stores it."""
    index = load_index()
    venues = watched_urls().get(url)
    if venues is None:
        raise typer.BadParameter(f"{url} is not cited by any venue in venues.yaml")
    content = page_file.read_text(encoding="utf-8", errors="replace")
    is_html = bool(re.search(r"<(html|body|p|div)\b", content[:5000], re.IGNORECASE))
    outcome = compare(url, Fetched(route, html=content, plain=not is_html), index, venues)
    typer.echo(f"## {GROUPS[outcome.result.value][0]}\n")
    typer.echo("\n".join(render(outcome, venue_names())))
    if update:
        apply([outcome], index, date.today())


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # tables, quotes and names print in UTF-8 on every platform
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
