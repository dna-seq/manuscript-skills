# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27", "pymupdf>=1.24,<2"]
# ///
"""How fast a journal answers, in four measures that are never mixed: the editor's first decision, the first
decision after peer review, submission to acceptance, and acceptance to publication.

- `editor` records the time to the editor's first decision (a desk rejection or sending the paper to review) as the
  journal publishes it, with the population the journal states, or "not published" with the pages read.
- `reviewed` measures the time to the first decision after peer review (the first referee reports) from transparent
  review records that carry dates: the Review Process File of Life Science Alliance and the other EMBO Press
  journals, the peer review history PLOS authors may publish, and eLife's docmaps. It gives the median and the
  interquartile range with n and the period, or, with `--records none`, "not measurable from public records".
- `histories` reads the received, accepted and first-online dates of a journal's recent papers in PubMed:
  submission to acceptance and acceptance to publication, accepted papers only.
- `table` prints the four side by side for the stage report, with what each one counts.

Each measure is one `review_speed` record of the venue facts (`--facts FILE`, the catalogue's form); a new record
replaces the old one of the same measure and sample, and the first write of a venue copies the records the
catalogue already holds, so the file's list is the venue's whole list (a list is laid over the catalogue whole).

    uv run --script speed.py editor nar --days 18 --statistic median --population "not stated" --period 2025 \
        --source https://academic.oup.com/nar/pages/About --facts FACTS.yaml
    uv run --script speed.py editor life-science-alliance --not-published --source URL --source URL --facts FACTS.yaml
    uv run --script speed.py reviewed life-science-alliance --records embo-rpf --journal '"Life Sci Alliance"[ta]' \
        --out SPEED/ --facts FACTS.yaml
    uv run --script speed.py reviewed plos-comp-biol --records plos --journal '"PLoS Comput Biol"[ta]' --out SPEED/
    uv run --script speed.py reviewed elife --records elife --subject genetics-genomics --out SPEED/
    uv run --script speed.py reviewed mbe --records none --reason "MBE publishes no referee reports" --source URL
    uv run --script speed.py histories nar --journal '"Nucleic Acids Res"[ta]' --exclude-issue D1 --exclude-issue W1
    uv run --script speed.py table life-science-alliance mbe nar frontiers-aging --facts FACTS.yaml
"""

from __future__ import annotations

import csv
import html
import importlib.util
import json
import re
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Callable, Optional
from urllib.parse import urlencode

import typer
import yaml

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The venue catalogue and its helpers: which measure a record is (`speed_kind`), the catalogue with facts laid over.
venues = _load("speed_venues", SKILLS / "manuscript-journal-adapt" / "scripts" / "venues.py")

app = typer.Typer(add_completion=False, no_args_is_help=True)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
LSA_RPF = "https://www.life-science-alliance.org/lookup/doi/{doi}.reviewer-comments.pdf"
PLOS_HISTORY = "https://journals.plos.org/{journal}/article/peerReview?id={doi}"
PLOS_JOURNALS = {"pcbi": "ploscompbiol", "pbio": "plosbiology", "pgen": "plosgenetics", "pone": "plosone",
                 "ppat": "plospathogens", "pntd": "plosntds", "pmed": "plosmedicine", "pdig": "digitalhealth",
                 "pclm": "climate", "pgph": "globalpublichealth", "pwat": "water", "pstr": "sustainabilitytransformation",
                 "pcsy": "complexsystems"}
ELIFE_LIST = "https://api.elifesciences.org/reviewed-preprints?per-page=100&page={page}&order=desc"
ELIFE_DOCMAP = ("https://data-hub-api.elifesciences.org/enhanced-preprints/docmaps/v2/by-publisher/elife/"
                "get-by-manuscript-id?manuscript_id={id}")

# The measures and what each counts, in the order the table shows them (venues.speed_kind tells them apart).
METRIC = {"editor": "submission-to-first-decision", "after-review": "first-decision-after-review",
          "acceptance": "submission-to-acceptance", "publication": "acceptance-to-publication"}
COLUMNS = {
    "editor": "Editor's first decision",
    "after-review": "First decision after peer review",
    "acceptance": "Submission to acceptance",
    "publication": "Acceptance to publication",
}
COUNTS = {
    "editor": "days from submission to the editor's first decision, a desk rejection or sending the paper to "
              "review, as the journal publishes it; the population is the journal's own (all submissions, or "
              "desk decisions only), and \"not published\" means the journal's pages give no figure",
    "after-review": "days to the first decision that carries the referee reports, from the dated records the "
                    "journal publishes with its papers (each figure says where it starts); \"not measurable from "
                    "public records\" means the journal publishes no such dates",
    "acceptance": "days from the received to the accepted date in the PubMed histories of recent papers: accepted "
                  "papers only, so a rejection elsewhere first adds its own weeks",
    "publication": "days from the accepted date to the first online date in the same histories",
}
NOT_PUBLISHED = "not published"
NOT_MEASURABLE = "not measurable from public records"
SAMPLE = "inference from a stated sample"


class Records(str, Enum):
    embo_rpf = "embo-rpf"  # the Review Process File of Life Science Alliance and the EMBO Press journals
    plos = "plos"  # the peer review history PLOS authors may publish
    elife = "elife"  # eLife's docmaps: sent for review, then the public reviews
    none = "none"  # the journal publishes no dated review records


# ------------------------------------------------------------------------------------------------ fetching

def _get(url: str) -> bytes:
    """The body at `url`, retried on errors (name lookups fail now and then); b"" when the page does not exist."""
    import httpx

    last: Exception | None = None
    for attempt in range(4):
        try:
            r = httpx.get(url, timeout=60, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (manuscript-skills speed.py)"})
            if r.status_code == 404:
                return b""
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            return r.content
        except Exception as exc:  # noqa: BLE001 - every failure is retried, then reported
            last = exc
            time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"could not read {url}: {last}")


fetch: Callable[[str], bytes] = _get  # tests serve saved pages in its place
PAUSE = 0.5  # seconds between requests to one site


def _pause() -> None:
    if PAUSE:
        time.sleep(PAUSE)


# ------------------------------------------------------------------------------------------------ statistics

def _num(x: float) -> float | int:
    return int(x) if float(x).is_integer() else round(x, 1)


def summary(days: list[int]) -> Optional[dict[str, Any]]:
    """Median, interquartile range (the inclusive method: the quartiles lie between observed values) and n."""
    xs = sorted(d for d in days if d is not None)
    if not xs:
        return None
    q = statistics.quantiles(xs, n=4, method="inclusive") if len(xs) > 1 else [xs[0], xs[0], xs[0]]
    return {"n": len(xs), "median": _num(statistics.median(xs)), "iqr": [round(q[0]), round(q[2])],
            "min": xs[0], "max": xs[-1]}


def statistic_text(s: dict[str, Any]) -> str:
    return f"median (interquartile range {s['iqr'][0]}-{s['iqr'][1]}, n={s['n']})"


def _period(dates: list[Optional[date]], what: str) -> str:
    ds = sorted(d for d in dates if d)
    return f"{what} {ds[0].isoformat()} to {ds[-1].isoformat()}" if ds else "not known"


def _day(text: Any) -> Optional[date]:
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(text or ""))
    return date.fromisoformat(m.group(0)) if m else None


# ------------------------------------------------------------------------------------------------ PubMed

def pubmed_term(journal: str, since: date, until: date, extra: str = "") -> str:
    term = (f'{journal} AND ("{since:%Y/%m/%d}"[dp] : "{until:%Y/%m/%d}"[dp]) AND journal article[pt] '
            "NOT review[pt] NOT editorial[pt] NOT comment[pt] NOT erratum[pt] NOT published erratum[pt]")
    return term + (f" AND ({extra})" if extra else "")


def _pm_date(node: Optional[ET.Element]) -> Optional[date]:
    if node is None:
        return None
    try:
        return date(int(node.findtext("Year")), int(node.findtext("Month")), int(node.findtext("Day")))
    except (TypeError, ValueError):
        return None


def parse_pubmed(xml: bytes) -> list[dict[str, Any]]:
    """One row per article of a PubMed efetch answer: PMID, DOI, issue, pages, received, accepted, first online."""
    rows = []
    for a in ET.fromstring(xml).findall("PubmedArticle"):
        history = {p.get("PubStatus"): _pm_date(p) for p in a.findall(".//History/PubMedPubDate")}
        online = _pm_date(a.find(".//Article/ArticleDate"))
        if online is None:  # no electronic date on the article: its first PubMed date, a proxy for first online
            online = next((history[k] for k in ("aheadofprint", "epublish", "pubmed", "entrez") if history.get(k)), None)
        rows.append({
            "pmid": a.findtext(".//PMID") or "",
            "doi": next((e.text or "" for e in a.findall(".//ArticleIdList/ArticleId") if e.get("IdType") == "doi"), ""),
            "issue": a.findtext(".//JournalIssue/Issue") or "",
            "pages": a.findtext(".//Pagination/MedlinePgn") or "",
            "received": history.get("received"), "accepted": history.get("accepted"), "online": online,
            "title": " ".join((a.findtext(".//ArticleTitle") or "").split())[:140],
        })
    return rows


def excluded(row: dict[str, Any], issues: list[str]) -> bool:
    """Whether a paper is in an issue left out (NAR's Database issue is D1, its Web Server issue W1: their pages
    start with the issue's letter)."""
    for issue in issues:
        letter = issue.rstrip("0123456789")
        if row["issue"].upper() == issue.upper() or (letter and re.match(rf"{letter}\d", row["pages"], re.I)):
            return True
    return False


def pubmed_papers(journal: str, since: date, until: date, limit: int, extra: str = "",
                  exclude_issue: Optional[list[str]] = None,
                  placed_only: bool = False) -> tuple[str, int, list[dict[str, Any]]]:
    """The most recent `limit` research papers of a journal in PubMed (more are read when some are left out)."""
    term = pubmed_term(journal, since, until, extra)
    want = limit * 5 if exclude_issue or placed_only else limit
    found = json.loads(fetch(EUTILS + "esearch.fcgi?" + urlencode(
        {"db": "pubmed", "term": term, "retmax": want, "retmode": "json", "sort": "pub_date"})))
    ids = found["esearchresult"]["idlist"]
    rows: list[dict[str, Any]] = []
    for start in range(0, len(ids), 200):
        _pause()
        rows += parse_pubmed(fetch(EUTILS + "efetch.fcgi?" + urlencode(
            {"db": "pubmed", "id": ",".join(ids[start:start + 200]), "retmode": "xml"})))
    rows = [r for r in rows if not excluded(r, exclude_issue or []) and (r["issue"] or not placed_only)][:limit]
    return term, int(found["esearchresult"]["count"]), rows


# ------------------------------------------------------------------------------------------------ review records

TIMELINE_LABEL = re.compile(r"(Submission Date|Editorial Decision|Revision Received|Accepted)\s*:")
ISO_DAY = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Where the Review Timeline's block ends: the first letter or report. Letters date themselves in words ("February
# 24, 2026"), so every ISO date before this point is the timeline's, whichever side of its labels the PDF put them.
TIMELINE_END = re.compile(r"1st Editorial Decision|Review #1|Reviewer #1|Referee #1|\bDear\b|\bRe:\s")
FIRST_REPORTS = re.compile(r"\b(reviewers?|referees?|experts?)\b", re.I)
TRANSFERRED = re.compile(r"\btransferr?(?:ed|al|ing)?\b|previously reviewed at another journal|"
                         r"reviewed at another journal", re.I)


def pdf_text(data: bytes, pages: int = 3) -> str:
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n".join(doc[i].get_text() for i in range(min(pages, doc.page_count)))


def _iso(text: str) -> Optional[date]:
    try:
        return date.fromisoformat(text)
    except ValueError:  # a typing slip in the file ("2026-28-26")
        return None


def timeline(text: str) -> Optional[list[tuple[str, Optional[date]]]]:
    """The Review Timeline's events in order, each label with its date. The PDF's text puts a date after its label,
    or all labels and then all dates, or the dates first: labels and dates are paired by their order."""
    start = text.find("Review Timeline")
    if start < 0:
        return None
    end = TIMELINE_END.search(text, start)
    block = text[start:end.start() if end else start + 3000]
    labels = TIMELINE_LABEL.findall(block)
    dates = ISO_DAY.findall(block)
    if not labels or len(dates) < len(labels):
        return None
    return [(label, _iso(day)) for label, day in zip(labels, dates)]


def parse_rpf(text: str) -> Optional[dict[str, Any]]:
    """The Review Timeline of an EMBO Press or Life Science Alliance Review Process File, and how the paper reached
    the journal: `direct` (submitted and reviewed at the journal), `review-commons` (reviewed at Review Commons
    before submission), `transfer` (with another journal's reports), `opted-out` (the authors kept the letters
    private, so the route is not known), `no-reports` (a first decision that names no referee) or `bad-timeline`
    (a date that is not one, or dates out of order)."""
    events = timeline(text)
    if not events or events[0][0] != "Submission Date":
        return None
    submitted = events[0][1]
    first = next((d for k, d in events if k == "Editorial Decision"), None)
    accepted = next((d for k, d in events if k == "Accepted"), None)
    days = [d for _, d in events]
    report = text[text.find("Review Timeline"):]
    letter = report[report.find("Transaction Report"):] if "Transaction Report" in report else report
    if None in days or days != sorted(days):
        route = "bad-timeline"
    elif re.search(r"No full (?:Peer )?Review Process File is available", letter[:2500], re.I):
        route = "opted-out"
    elif "Review Commons" in letter[:2500]:
        route = "review-commons"
    elif TRANSFERRED.search(letter[:4000]):
        route = "transfer"
    elif first and not FIRST_REPORTS.search(letter[:6000]):
        route = "no-reports"
    else:
        route = "direct"
    manuscript = re.search(r"manuscript\s*#\s*([A-Z]+-\d{4}-\d+(?:-[A-Z]+)?)", text, re.I)
    return {"submitted": submitted, "first_decision": first, "accepted": accepted, "route": route,
            "manuscript": manuscript.group(1) if manuscript else "",
            "decisions": sum(1 for k, _ in events if k == "Editorial Decision")}


PLOS_DATE = re.compile(r'class="letter__date"[^>]*>\s*([^<]+?)\s*<')
PLOS_TITLE = re.compile(r'class="letter__title"[^>]*>\s*(?:<a[^>]*>)?\s*([^<]*?)\s*<')


def _plos_day(text: str) -> Optional[date]:
    for fmt in ("%B %d, %Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(html.unescape(text).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_plos(page: str) -> Optional[dict[str, Any]]:
    """The Original Submission date and the first Decision Letter's date of a PLOS peer review history page."""
    start = page.find('class="review-history"')
    if start < 0:
        return None
    table = page[start:page.find("</table>", start)]
    marks = sorted([(m.start(), "date", m.group(1)) for m in PLOS_DATE.finditer(table)]
                   + [(m.start(), "title", m.group(1)) for m in PLOS_TITLE.finditer(table)])
    submitted = first = last_date = None
    expect_submission = False
    for _, kind, value in marks:
        if kind == "date":
            last_date = _plos_day(value)
            if expect_submission:  # the Original Submission heading is followed by its date
                submitted, expect_submission = last_date, False
        elif value.startswith("Original Submission"):
            expect_submission = True
        elif value.startswith("Decision Letter") and first is None and submitted is not None:
            first = last_date  # a letter's date comes before its title
    decisions = sum(1 for _, k, v in marks if k == "title" and v.startswith("Decision Letter"))
    return {"submitted": submitted, "first_decision": first, "decisions": decisions} if submitted else None


def parse_docmap(docmap: dict[str, Any]) -> Optional[dict[str, Any]]:
    """From an eLife docmap: when the preprint was sent for review (the `under-review` assertion) and when its
    first public reviews were posted (the earliest review or evaluation output of the first `peer-reviewed` step)."""
    sent = posted = None
    for step in (docmap.get("steps") or {}).values():
        for a in step.get("assertions") or []:
            if a.get("status") == "under-review" and a.get("happened"):
                d = _day(a["happened"])
                sent = min(sent, d) if sent and d else (sent or d)
        if any(a.get("status") == "peer-reviewed" for a in step.get("assertions") or []):
            for action in step.get("actions") or []:
                for o in action.get("outputs") or []:
                    if o.get("type") in ("review-article", "evaluation-summary") and o.get("published"):
                        d = _day(o["published"])
                        posted = min(posted, d) if posted and d else (posted or d)
            if posted:
                break
    return {"sent": sent, "reviews": posted} if sent and posted else None


# ------------------------------------------------------------------------------------------------ facts

def read_facts(path: Optional[Path]) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"venues": {}}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {**raw, "venues": raw.get("venues") or raw.get("venue_facts") or {}}


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return venues.speed_kind(a.get("metric")) == venues.speed_kind(b.get("metric")) and \
        (a.get("sample") or "") == (b.get("sample") or "")


def put_record(path: Path, key: str, record: dict[str, Any]) -> None:
    """Write one measure into the facts file, replacing the venue's record of the same measure and sample; the
    first write of a venue starts from the records the catalogue already holds for it."""
    facts = read_facts(path)
    entry = facts["venues"].setdefault(key, {})
    if "review_speed" not in entry:
        _, known = venues.load_venues()
        entry["review_speed"] = [dict(r) for r in (known.get(key, {}).get("review_speed") or [])]
    entry["review_speed"] = [r for r in entry["review_speed"] if not _same(r, record)] + [record]
    order = list(METRIC)
    entry["review_speed"].sort(key=lambda r: order.index(k) if (k := venues.speed_kind(r.get("metric"))) in order
                               else len(order))
    facts.setdefault("checked", record["checked"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({k: v for k, v in facts.items() if k != "venue_facts"}, sort_keys=False,
                                   allow_unicode=True, width=120), encoding="utf-8")


def _emit(key: str, record: dict[str, Any], facts: Optional[Path]) -> None:
    typer.echo(yaml.safe_dump({"venues": {key: {"review_speed": [record]}}}, sort_keys=False, allow_unicode=True,
                              width=120).rstrip())
    if facts:
        put_record(facts, key, record)
        typer.echo(f"Saved to {facts}.", err=True)


def _write_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, columns, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: "" if r.get(c) is None else r.get(c) for c in columns})


# ------------------------------------------------------------------------------------------------ commands

Today = Annotated[Optional[str], typer.Option(help="The date the sources were read (YYYY-MM-DD); default today")]
FactsOpt = Annotated[Optional[Path], typer.Option(help="Venue facts file to write the record into")]


def _today(on: Optional[str]) -> date:
    return date.fromisoformat(on) if on else date.today()


@app.command()
def editor(
    key: Annotated[str, typer.Argument(help="Catalogue key of the venue")],
    source: Annotated[list[str], typer.Option(help="The page the figure is on; for --not-published, each page read")],
    days: Annotated[Optional[float], typer.Option(help="The journal's figure, in days")] = None,
    statistic: Annotated[str, typer.Option(help="median, mean, ... as the journal says")] = "not stated",
    population: Annotated[str, typer.Option(
        help="Whom the journal counts, in its words: all submissions, desk decisions only, ... or 'not stated'")] = "",
    period: Annotated[str, typer.Option(help="The year or interval the journal gives, or 'not stated'")] = "not stated",
    quote: Annotated[str, typer.Option(help="The journal's sentence, verbatim")] = "",
    not_published: Annotated[bool, typer.Option(help="The journal's pages give no figure")] = False,
    note: Annotated[str, typer.Option(help="Anything a reader needs: a publisher-wide figure, an old report")] = "",
    checked: Today = None,
    facts: FactsOpt = None,
) -> None:
    """Record the time to the editor's first decision as the journal publishes it, or that it publishes none."""
    if not_published == (days is not None):
        raise typer.BadParameter("give either --days (the journal's figure) or --not-published")
    if days is not None and not population:
        raise typer.BadParameter("say whom the journal counts (--population), or 'not stated'")
    record: dict[str, Any] = {"metric": METRIC["editor"], "days": None if days is None else _num(days)}
    if not_published:
        record["status"] = NOT_PUBLISHED
    else:
        record.update(statistic=statistic, population=population, period=period)
        if quote:
            record["quote"] = quote
    record.update(source="; ".join(source), checked=_today(checked),
                  evidence_kind="official statistic" if days is not None else "pages read")
    if note:
        record["note"] = note
    _emit(key, record, facts)


@app.command()
def histories(
    key: Annotated[str, typer.Argument(help="Catalogue key of the journal")],
    journal: Annotated[str, typer.Option(help="PubMed query naming the journal, e.g. '\"Mol Biol Evol\"[ta]'")],
    out: Annotated[Path, typer.Option(help="Folder for KEY.histories.tsv")] = Path("."),
    limit: Annotated[int, typer.Option(help="The most recent papers to read")] = 80,
    months: Annotated[int, typer.Option(help="How far back to look, in months")] = 18,
    extra: Annotated[str, typer.Option(help="A PubMed term the papers must also match")] = "",
    sample: Annotated[str, typer.Option(help="A label for a subset (database papers), kept apart from the rest")] = "",
    exclude_issue: Annotated[Optional[list[str]], typer.Option(
        help="An issue to leave out, e.g. D1 and W1 for NAR's Database and Web Server issues")] = None,
    placed_only: Annotated[bool, typer.Option(
        help="Keep only papers PubMed has placed in an issue: NAR puts its Database and Web Server issue papers "
             "online months before their issue, while its regular articles get one when they appear")] = False,
    checked: Today = None,
    facts: FactsOpt = None,
) -> None:
    """Submission to acceptance and acceptance to publication from the PubMed histories of recent papers."""
    on = _today(checked)
    term, total, rows = pubmed_papers(journal, on - timedelta(days=round(months * 30.44)), on, limit, extra,
                                      exclude_issue, placed_only)
    for r in rows:
        r["to_acceptance"] = (r["accepted"] - r["received"]).days if r["received"] and r["accepted"] else None
        r["to_online"] = (r["online"] - r["accepted"]).days if r["accepted"] and r["online"] else None
        r["received_to_online"] = (r["online"] - r["received"]).days if r["received"] and r["online"] else None
    name = f"{key}{'-' + re.sub(r'[^a-z0-9]+', '-', sample.lower()).strip('-') if sample else ''}"
    _write_tsv(out / f"{name}.histories.tsv", rows, ["pmid", "doi", "issue", "pages", "received", "accepted",
                                                     "online", "to_acceptance", "to_online", "received_to_online",
                                                     "title"])
    typer.echo(f"# {key}: {total} papers match {term!r}; read the {len(rows)} most recent", err=True)
    left_out = (f"; {', '.join(exclude_issue)} issues left out" if exclude_issue else "") + \
        ("; only papers already placed in an issue" if placed_only else "")
    population = ("accepted research papers only (rejected papers and papers still in review are not in the "
                  f"sample): the {len(rows)} most recent journal articles in PubMed{left_out}"
                  + (f", {sample}" if sample else "") + "; reviews, editorials and errata excluded")
    period = _period([r["online"] for r in rows], "published")
    source = f"PubMed article histories ({EUTILS}efetch.fcgi), query {term}"
    whole = summary([r["received_to_online"] for r in rows])
    for kind, field in (("acceptance", "to_acceptance"), ("publication", "to_online")):
        s = summary([r[field] for r in rows])
        if s is None:
            typer.echo(f"No paper of {key} has both dates for {COLUMNS[kind].lower()}.", err=True)
            continue
        record = {"metric": METRIC[kind], "days": s["median"], "statistic": statistic_text(s), "n": s["n"],
                  "iqr": s["iqr"], "population": population, "period": period,
                  "source": source, "checked": on, "evidence_kind": SAMPLE}
        if sample:
            record["sample"] = sample
        if kind == "acceptance" and whole:
            record["note"] = f"received to first online: median {whole['median']} days " \
                             f"(interquartile range {whole['iqr'][0]}-{whole['iqr'][1]}, n={whole['n']})"
        _emit(key, record, facts)


def _harvest_rpf(rows: list[dict[str, Any]], files: list[Path], template: str, cache: Path) -> list[dict[str, Any]]:
    found = []
    for path in files:
        data = path.read_bytes()
        text = pdf_text(data) if data[:4] == b"%PDF" else data.decode("utf-8", "replace")
        parsed = parse_rpf(text)
        found.append({"doi": "", "file": path.name, **(parsed or {"route": "no-timeline"})})
    for r in rows:
        if not r["doi"]:
            continue
        cached = cache / (re.sub(r"[^\w.-]+", "_", r["doi"]) + ".txt")
        if cached.is_file():
            text = cached.read_text(encoding="utf-8")
        else:
            _pause()
            data = fetch(template.format(doi=r["doi"]))
            text = pdf_text(data) if data[:4] == b"%PDF" else ""
            cache.mkdir(parents=True, exist_ok=True)
            cached.write_text(text, encoding="utf-8")
        parsed = parse_rpf(text) if text else None
        found.append({"doi": r["doi"], "pmid": r["pmid"], "online": r["online"],
                      **(parsed or {"route": "no-file" if not text else "no-timeline"})})
    return found


def _harvest_plos(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for r in rows:
        m = re.match(r"10\.1371/journal\.(\w+)\.", r["doi"] or "")
        if not m or m.group(1) not in PLOS_JOURNALS:
            continue
        _pause()
        page = fetch(PLOS_HISTORY.format(journal=PLOS_JOURNALS[m.group(1)], doi=r["doi"])).decode("utf-8", "replace")
        parsed = parse_plos(page) if page else None
        found.append({"doi": r["doi"], "pmid": r["pmid"], "online": r["online"],
                      **({**parsed, "route": "history"} if parsed else {"route": "no-history"})})
    return found


def _harvest_elife(subjects: list[str], limit: int, pages: int) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        listing = json.loads(fetch(ELIFE_LIST.format(page=page)) or b"{}")
        for item in listing.get("items") or []:
            if item.get("version") == 1 and (not subjects or set(subjects) & {s["id"] for s in item.get("subjects") or []}):
                picked.append(item)
        if len(picked) >= limit or not listing.get("items"):
            break
    found = []
    for item in picked[:limit]:
        _pause()
        raw = fetch(ELIFE_DOCMAP.format(id=item["id"]))
        parsed = parse_docmap(json.loads(raw)) if raw else None
        found.append({"doi": f"10.7554/eLife.{item['id']}", "online": _day(item.get("published")),
                      "title": item.get("title", "")[:140],
                      **({"submitted": parsed["sent"], "first_decision": parsed["reviews"], "route": "reviewed"}
                         if parsed else {"route": "no-docmap"})})
    return found


@app.command()
def reviewed(
    key: Annotated[str, typer.Argument(help="Catalogue key of the journal")],
    records: Annotated[Records, typer.Option(help="Where the dated review records are")],
    journal: Annotated[str, typer.Option(help="PubMed query naming the journal (embo-rpf, plos)")] = "",
    out: Annotated[Path, typer.Option(help="Folder for KEY.reviewed.tsv and the texts read")] = Path("."),
    limit: Annotated[int, typer.Option(help="The most recent papers to read")] = 60,
    months: Annotated[int, typer.Option(help="How far back to look, in months")] = 18,
    pdf_url: Annotated[str, typer.Option(help="Where a paper's Review Process File is, with {doi}")] = LSA_RPF,
    file: Annotated[Optional[list[Path]], typer.Option(
        help="A Review Process File already saved (PDF or its text), for EMBO Press journals without a URL pattern")]
        = None,
    subject: Annotated[Optional[list[str]], typer.Option(help="eLife subject ids to keep")] = None,
    reason: Annotated[str, typer.Option(help="--records none: why nothing can be measured")] = "",
    source: Annotated[Optional[list[str]], typer.Option(help="--records none: each page read")] = None,
    checked: Today = None,
    facts: FactsOpt = None,
) -> None:
    """The time to the first decision after peer review, from the dated review records a journal publishes."""
    on = _today(checked)
    record: dict[str, Any] = {"metric": METRIC["after-review"]}
    if records == Records.none:
        if not reason or not source:
            raise typer.BadParameter("--records none needs --reason and the pages read (--source)")
        record.update(days=None, status=NOT_MEASURABLE, note=reason,
                      source="; ".join(source), checked=on, evidence_kind="pages read")
        _emit(key, record, facts)
        return
    term, rows = "", []
    if records in (Records.embo_rpf, Records.plos) and journal:
        term, _, rows = pubmed_papers(journal, on - timedelta(days=round(months * 30.44)), on, limit)
    if records == Records.embo_rpf:
        found = _harvest_rpf(rows, file or [], pdf_url, out / f"{key}.reviewed")
        counted = [f for f in found if f["route"] == "direct" and f.get("first_decision")]
        start, where = "submission (the Submission Date)", "the Review Timeline of each paper's Review Process File"
        population = "accepted papers published with a Review Process File, submitted to the journal directly and " \
                     "reviewed there"
    elif records == Records.plos:
        if not rows:
            raise typer.BadParameter("--records plos needs --journal")
        found = _harvest_plos(rows)
        counted = [f for f in found if f["route"] == "history" and f.get("first_decision")]
        start, where = "submission (the Original Submission date)", "each paper's published peer review history"
        population = (f"accepted papers whose authors chose to publish the peer review history ({len(counted)} of "
                      f"the {len(found)} recent papers read)")
    else:
        found = _harvest_elife(subject or [], limit, pages=10)
        counted = [f for f in found if f["route"] == "reviewed"]
        start, where = "the day eLife sent the preprint for review", "eLife's docmaps"
        population = "Reviewed Preprints (version 1)" + (f" in {', '.join(subject)}" if subject else "")
    for f in found:
        f["days"] = (f["first_decision"] - f["submitted"]).days if f.get("first_decision") and f.get("submitted") \
            else None
    _write_tsv(out / f"{key}.reviewed.tsv", found, ["doi", "pmid", "file", "manuscript", "route", "submitted",
                                                    "first_decision", "accepted", "decisions", "online", "days",
                                                    "title"])
    s = summary([f["days"] for f in counted])
    if s is None:
        raise typer.BadParameter(f"none of the {len(found)} papers read has dated review records; record "
                                 "`--records none` with the pages read if the journal publishes none")
    routes = {}
    for f in found:
        routes.setdefault(f["route"], []).append(f["days"])
    others = [f"{route}: {len(ds)} paper{'' if len(ds) == 1 else 's'}" + (f", median {m['median']} days" if (m := summary(ds)) else "")
              for route, ds in sorted(routes.items()) if route not in ("direct", "history", "reviewed")]
    counts = (f"days from {start} to the first decision that carried the referee reports, in {where}"
              + ("; eLife publishes no submission date, so the days before it decided to review (about a week) "
                 "are not counted, and the reviews are dated when posted, a few days after the authors had them"
                 if records == Records.elife else ""))
    record.update(days=s["median"], statistic=statistic_text(s), n=s["n"], iqr=s["iqr"], counts=counts,
                  population=population + ("" if records == Records.elife else
                                           "; papers that were rejected are not in the sample"),
                  period=_period([f.get("first_decision") for f in counted], "first decisions"),
                  source=({Records.embo_rpf: pdf_url if rows else "Review Process Files given as files",
                           Records.plos: PLOS_HISTORY, Records.elife: ELIFE_DOCMAP}[records]
                          + (f"; papers from PubMed, query {term}" if term else "")),
                  checked=on, evidence_kind=SAMPLE)
    if others:
        record["note"] = "Left out: " + "; ".join(others) + "."
    _emit(key, record, facts)


def cell(kind: str, rec: Optional[dict[str, Any]]) -> str:
    """A measure in a table cell: days, statistic and period, and for the editor's first decision whom the journal
    counts (the samples of the other measures are described under the table); the status when there is no figure."""
    if rec is None:
        return "not looked up"
    if rec.get("days") is None:
        return str(rec.get("status") or "not known")
    parts = [f"{rec['days']} days, {rec.get('statistic') or 'statistic not stated'}"]
    if kind == "editor":
        population = str(rec.get("population") or "not stated")
        parts.append("population not stated" if population == "not stated" else population)
    if rec.get("period"):
        parts.append(str(rec["period"]))
    return "; ".join(parts).replace("|", "/")


def speed_cells(v: dict[str, Any]) -> dict[str, Optional[dict[str, Any]]]:
    """A venue's record for each measure (its whole sample, not a subset); None where nothing was looked up."""
    cells: dict[str, Optional[dict[str, Any]]] = {k: None for k in COLUMNS}
    for r in v.get("review_speed") or []:
        kind = venues.speed_kind(r.get("metric"))
        if kind in cells and not r.get("sample") and cells[kind] is None:
            cells[kind] = r
    return cells


def speed_table(keys: list[str], known: dict[str, dict[str, Any]]) -> str:
    """The four measures side by side, what each counts, and for each journal its samples, notes and reasons."""
    lines = ["| Journal | " + " | ".join(COLUMNS.values()) + " |", "|---|" + "---|" * len(COLUMNS)]
    for key in keys:
        cells = speed_cells(known[key])
        lines.append(f"| {known[key].get('name') or key} | " + " | ".join(cell(k, cells[k]) for k in COLUMNS) + " |")
    lines += ["", "What each column counts:", ""] + [f"- **{w}**: {COUNTS[k]}." for k, w in COLUMNS.items()]
    for key in keys:
        name, said = known[key].get("name") or key, []
        cells = speed_cells(known[key])
        for kind, rec in cells.items():
            if rec is None:
                continue
            what = COLUMNS[kind].lower()
            if rec.get("days") is not None and kind == "after-review":
                said.append(f"{what}: {rec.get('counts')}; {rec.get('population')}")
            elif rec.get("days") is not None and kind in ("acceptance", "publication") and \
                    not any(f"sample: {rec.get('population')}" in s for s in said):
                said.append(f"sample: {rec.get('population')}")
            if rec.get("note"):
                said.append(f"{what}: {rec['note']}")
            if rec.get("quote"):
                said.append(f"{what}, the journal's words: \"{rec['quote']}\"")
        if said:
            lines += ["", f"{name}:", ""] + [f"- {s}" + ("" if s.endswith((".", '."')) else ".") for s in said]
    return "\n".join(lines)


@app.command()
def table(
    keys: Annotated[list[str], typer.Argument(help="Catalogue keys, in the ladder's order")],
    facts: Annotated[Optional[Path], typer.Option(help="Venue facts file laid over the catalogue")] = None,
) -> None:
    """The speed table for the stage report: the four measures side by side, and what each one counts."""
    _, known = venues.load_venues()
    given = read_facts(facts)["venues"]
    if given:
        known = venues.with_facts(known, given)
    missing = [k for k in keys if k not in known]
    if missing:
        raise typer.BadParameter(f"not in the catalogue: {', '.join(missing)}")
    typer.echo(speed_table(keys, known))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    app()
