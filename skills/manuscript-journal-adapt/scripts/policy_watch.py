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
    uv run --script policy_watch.py check --venue aging-cell --update   # re-read one venue and store the result
    uv run --script policy_watch.py check --stale-days 30 --update      # only URLs not read for 30 days
    uv run --script policy_watch.py record URL saved.html        # a page saved from your browser (challenge pages)

A page that could not be read is `not_assessed`, never `unchanged`. Exit code 1 when a page changed or is gone.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import subprocess
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


class Result(str, Enum):
    unchanged = "unchanged"
    changed = "changed"
    new = "new"
    gone = "gone"
    not_assessed = "not_assessed"


@dataclass
class Fetched:
    route: Optional[str]  # httpx | chrome | wayback:<timestamp> | the route named to `record`
    html: Optional[str] = None
    status: Optional[int] = None
    reason: Optional[str] = None


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


# ------------------------------------------------------------------------------------------------ fetch

def _challenged(html: str) -> bool:
    head = html[:20000].lower()
    return any(m in head for m in CHALLENGE_MARKERS)


def fetch_httpx(url: str) -> Fetched:
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"}, follow_redirects=True,
                      timeout=30)
    except httpx.HTTPError as e:
        return Fetched("httpx", reason=f"{type(e).__name__}: {e}")
    if r.status_code in (404, 410):
        return Fetched("httpx", status=r.status_code, reason=f"HTTP {r.status_code}")
    if r.status_code >= 400 or _challenged(r.text):
        return Fetched("httpx", status=r.status_code, reason=f"blocked (HTTP {r.status_code})")
    return Fetched("httpx", html=r.text, status=r.status_code)


def _chrome() -> Optional[str]:
    return next((b for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
                 if shutil.which(b)), None)


def fetch_chrome(url: str) -> Fetched:
    binary = _chrome()
    if binary is None:
        return Fetched("chrome", reason="no Chrome or Chromium on PATH")
    with tempfile.TemporaryDirectory(prefix="policy-watch-") as profile:
        run = subprocess.run([binary, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
                              "--virtual-time-budget=15000", "--dump-dom", url],
                             capture_output=True, text=True, timeout=120)
    if run.returncode != 0 or not run.stdout.strip():
        return Fetched("chrome", reason=f"chrome exit {run.returncode}")
    if _challenged(run.stdout):
        return Fetched("chrome", reason="blocked (challenge page)")
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
        return None, f"wayback unreachable ({type(e).__name__})"
    return (closest["timestamp"], "") if closest.get("available") else (None, "no archived copy")


def fetch_wayback(url: str, newer_than: Optional[date]) -> Fetched:
    stamp, why = _wayback_latest(url)
    if stamp is None:
        return Fetched("wayback", reason=why)
    taken = datetime.strptime(stamp[:8], "%Y%m%d").date()
    if newer_than is not None and taken <= newer_than:
        return Fetched("wayback", reason=f"newest archived copy ({taken}) is not newer than the snapshot")
    got = fetch_httpx(f"https://web.archive.org/web/{stamp}id_/{url}")
    return Fetched(f"wayback:{stamp}", html=got.html, status=got.status, reason=got.reason)


def fetch(url: str, routes: list[str], last: Optional[date]) -> Fetched:
    """Each route in turn until one returns a readable page."""
    reasons: list[str] = []
    for route in routes:
        got = (fetch_httpx(url) if route == "httpx" else fetch_chrome(url) if route == "chrome"
               else fetch_wayback(url, last))
        if got.html is not None:
            return got
        if got.status in (404, 410) and route == "httpx":
            return got
        reasons.append(f"{route}: {got.reason}")
    return Fetched(None, reason="; ".join(reasons))


# ------------------------------------------------------------------------------------------------ data

def watched_urls(only: Optional[list[str]] = None) -> dict[str, list[str]]:
    """URL -> the venue keys that cite it, from the raw (uninherited) entries, so each URL is counted once."""
    raw = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
    out: dict[str, list[str]] = {}
    for key, v in raw.items():
        if only and key not in only:
            continue
        for u in [v.get("url"), v.get("ai_policy_url"), *(v.get("sources") or [])]:
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


def compare(url: str, got: Fetched, index: dict[str, dict[str, Any]], venues: list[str],
            plain_text: bool = False) -> Outcome:
    if got.html is None:
        result = Result.gone if got.status in (404, 410) else Result.not_assessed
        return Outcome(url, result, got.route, got.reason or "", venues=venues)
    blocks = text_blocks(got.html) if plain_text else page_blocks(got.html)
    if sum(len(t) for _, t in blocks) < MIN_PAGE_CHARS:
        return Outcome(url, Result.not_assessed, got.route, "page too short: a stub, login wall or script shell",
                       venues=venues)
    body = ai_extract(blocks)
    n = body.count("\n\n") + 1 if body else 0
    entry = index.get(url)
    old = read_snapshot(entry) if entry else None
    if old is None:
        return Outcome(url, Result.new, got.route, "no AI text on this page" if not body else "", n, venues, body=body)
    if digest(old) == digest(body):
        return Outcome(url, Result.unchanged, got.route, "", n, venues, body=body)
    note = ""
    if _route_kind(entry.get("route")) != _route_kind(got.route):
        note = f"read by {got.route}, the snapshot by {entry.get('route')}: some differences may be the route"
    diff = list(difflib.unified_diff(old.split("\n\n"), body.split("\n\n"), "snapshot", "live", lineterm="", n=0))
    return Outcome(url, Result.changed, got.route, note, n, venues, diff, body)


def apply(outcomes: list[Outcome], index: dict[str, dict[str, Any]], today: date) -> None:
    for o in outcomes:
        if o.result in (Result.new, Result.changed, Result.unchanged) and o.body is not None and o.route:
            index[o.url] = {"file": write_snapshot(o.url, o.body), "read": today.isoformat(),
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
    typer.echo("| URL | venues | last read | route | passages | last failed attempt |")
    typer.echo("|---|---|---|---|---:|---|")
    for url, keys in sorted(watched_urls(venue).items()):
        e = index.get(url, {})
        att = e.get("last_attempt")
        failed = f"{att['date']}: {att['reason']}" if att else ""
        typer.echo(f"| {url} | {', '.join(keys)} | {e.get('read', 'never')} | {e.get('route', '')} "
                   f"| {e.get('passages', '')} | {failed} |")


@app.command()
def check(
    venue: Annotated[Optional[list[str]], typer.Option(help="Only these venue keys (repeatable)")] = None,
    stale_days: Annotated[Optional[int], typer.Option(help="Only URLs not read for this many days")] = None,
    update: Annotated[bool, typer.Option(help="Write new and changed snapshots and the read dates")] = False,
    routes: Annotated[str, typer.Option(help="Fetch routes in order: httpx, chrome, wayback")] = "httpx,chrome,wayback",
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
    typer.echo(f"Policy pages checked {today} ({len(outcomes)} URLs)\n")
    for res in order:
        group = [o for o in outcomes if o.result == res]
        if not group:
            continue
        typer.echo(f"## {res.value} ({len(group)})\n")
        for o in group:
            extra = f" {o.reason}" if o.reason else ""
            typer.echo(f"- {o.url} [{', '.join(o.venues)}] via {o.route or 'none'}, {o.blocks} AI passages.{extra}")
            for line in o.diff[:60]:
                typer.echo(f"    {line}")
            if len(o.diff) > 60:
                typer.echo(f"    ... {len(o.diff) - 60} more diff lines")
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


@app.command()
def record(
    url: Annotated[str, typer.Argument(help="A watched URL")],
    page_file: Annotated[Path, typer.Argument(help="The page saved from a browser (.html) or its text")],
    route: Annotated[str, typer.Option(help="How it was read, e.g. browser, webfetch")] = "browser",
    update: Annotated[bool, typer.Option(help="Store it as the snapshot")] = True,
) -> None:
    """Compare (and store) a page read by a route this script cannot use: saved from the user's own browser, or
    read with WebFetch, when a challenge page blocks the scripted routes."""
    index = load_index()
    venues = watched_urls().get(url)
    if venues is None:
        raise typer.BadParameter(f"{url} is not cited by any venue in venues.yaml")
    content = page_file.read_text(encoding="utf-8", errors="replace")
    is_html = bool(re.search(r"<(html|body|p|div)\b", content[:5000], re.IGNORECASE))
    outcome = compare(url, Fetched(route, html=content), index, venues, plain_text=not is_html)
    typer.echo(f"{outcome.result.value}: {url} via {route}, {outcome.blocks} AI passages. {outcome.reason}")
    for line in outcome.diff:
        typer.echo(f"    {line}")
    if update:
        apply([outcome], index, date.today())


if __name__ == "__main__":
    app()
