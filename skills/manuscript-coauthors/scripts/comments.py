# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "openpyxl>=3.1"]
# ///
"""Co-authors' comments on a round of the manuscript: the ledger that keeps them, and how the next round
answers each one (manuscript-coauthors).

    uv run --script comments.py import EXPORT.docx --ledger v0.5/comments.yaml [--master v0.5/PAPER.md] [--doc URL]
    uv run --script comments.py import-gdoc READ_DOC.json --ledger v0.5/comments.yaml [--master ...] [--doc URL] [--tab t.0]
    uv run --script comments.py add ITEMS.yaml --ledger v0.5/comments.yaml [--master ...] [--doc URL]
    uv run --script comments.py status v0.5/comments.yaml [--old v0.5/PAPER.md] [--new v0.6/PAPER.md] [--json] [--strict]
    uv run --script comments.py findings v0.5/comments.yaml --new v0.6/PAPER.md --out RUN/manuscript-coauthors/findings.json
    uv run --script comments.py signoffs v0.5/comments.yaml --new v0.6/PAPER.md [--go]
    uv run --script comments.py changelog --base OLD.md --new v0.6/PAPER.md [--seen SEEN.md] --ledger v0.5/comments.yaml [--out FILE]
    uv run --script comments.py gaps v0.5/comments.yaml --inventory RUN/manuscript-dashboard/findings.json [--out SHEET.md]
    uv run --script comments.py gaps v0.5/comments.yaml --inventory v0.5/PAPER.dashboard.html --merge GAPS.yaml | --check

`import` reads a Google Doc exported as .docx (rclone `--drive-export-formats docx`, a Drive connector's
download with exportMimeType docx, or File > Download > Microsoft Word). Google writes each comment and each
reply as a Word comment on the same range, with no thread record, a comment over several ranges as one copy
per range, and suggested edits as tracked insertions and deletions; it does not say whether a thread was
resolved. So: copies are merged, a comment on exactly the range of an earlier one is its reply, and the
suggested edits of one person in one paragraph are one item. `add` takes items written from a connector's
text view (a YAML list of author, date, anchor, comment, and optionally context_before, context_after,
replies, kind, edits, resolved) and merges them the same way.

`import-gdoc` reads the same from the Google Docs connector: read_doc with commentsIncluded, saved as JSON (a
large answer is saved to a file by the client; write a small one out). It gives each thread's exact range,
whether it was resolved and who resolved it, and each open suggestion's inserted and deleted text, and keeps
the Doc's ids (gdoc_id), so a later pull, by either route, knows each item again.

`import` and `import-gdoc` also record who commented: each commenter's name is mapped to a handle (manuscript-mark-people's
rules: an alias, an author of the paper by full name or by initials and surname start, else a new handle), added
to rev-marks.toml's humans with the name among its aliases, and written as `by:` on the item or reply
(--no-people: none of it). A comment or reply that starts with [ai] or [ai:NAME] is an agent's: `ai:` instead of
`by:`, and such a comment is kept as not-on-point. `add` records nobody.

Ids: C<n> for comments and S<n> for suggested edits, numbered in paper order, continuing past every id
already used in the round folders beside this one (their comments.yaml) and in the master's revision marks,
so a revision mark `@rev C41` names one comment for good. A pull again keeps every id (an item is known by
its author, date and first words) and adds only what is new; nothing is renumbered or dropped.

Each item's anchor is found in the round's master (`--master`, or the ledger's `master:`): its heading
(`where`) and line. `status` maps it to the next round with the revision-marks alignment
(manuscript-revision-marks' rev_marks.py) and says whether the paragraph changed, and checks what the
ledger says of it: `addressed`/`partly` need `now`, a passage of the new round verbatim; `declined` and
`not-on-point` need `why`; `open`/`partly` need `next`, what could still be done. `findings` writes the
stage's findings.json (a CA finding for each comment not fully addressed, and the `coauthors` object the
dashboard shows) and comments.md beside it, the digest the findings cite. `changelog` is revision marks'
`changes` table from the round's base (with `--seen`, which rows the co-authors have not seen yet), its Why
filled for every row whose segment answers a comment of the ledgers: who asked, what, and the ledger's `why`.

`signoffs` takes a co-author's resolved thread, or their suggested edit that was taken, as their sign-off: the
person who resolved the thread (or made the suggestion) is added to the `by=` of the segments of the next round's
master that answer it (a segment named for the comment, or the one holding its `now`), once; an agent's
resolution or a name that is not a person signs nothing. The changelog's first line says how many marked passages
have no person's sign-off yet.

`gaps` asks of each comment whether the run that produced the round had caught it, from that run's inventory
(its findings.json, or the dashboard it rendered): caught or partly (a finding of the run names it), missed, or
introduced (the passage was written by one of the run's applied edits). Without --merge or --check it writes a
worksheet: each comment with the run's records nearest to it, found by shared words, for the agent to judge.
--merge takes the agent's YAML of gap records into the ledger, nothing written while one has a problem;
--check checks them and lists the comments not judged yet (--strict: exit 1 while any is). An item that is not a
co-author's (an open point a run carried into the ledger) may stay unjudged. `findings` carries them to the dashboard.

EXIT STATUS 0 done · 1 a problem the ledger must fix (status --strict, findings) · 2 usage or a malformed
ledger · 3 could not run (an unreadable file)
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

REV_MARKS = Path(__file__).resolve().parents[2] / "manuscript-revision-marks" / "scripts" / "rev_marks.py"
PEOPLE = Path(__file__).resolve().parents[2] / "manuscript-mark-people" / "scripts" / "people.py"
# A comment or reply an agent wrote starts with [ai] or [ai:NAME] (`[ai:claude]`), whoever's Google account posted it.
AI_MARK = re.compile(r"^\s*\[ai(?:\s*:\s*([A-Za-z0-9][A-Za-z0-9_.-]*))?\s*\]", re.IGNORECASE)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
STATUSES = ("open", "addressed", "partly", "declined", "not-on-point")
KINDS = ("comment", "suggestion")
CONTEXT = 200  # characters of the Doc kept on each side of an anchor, to find it in the master
CONTEXT_WORDS = 12
TRIAGE = ("category", "severity", "stage", "decision")
SEVERITIES = ("blocker", "major", "minor", "info", "unknown")
STAGES = ("now", "writing", "journal", "final")
LEDGER_HEADER = ("# Co-authors' comments on this round, kept by manuscript-coauthors (comments.py).\n"
                 "# status: open | addressed | partly | declined | not-on-point. now: the next round's passage that\n"
                 "# answers it, verbatim. why: what was done and why, or why not. next: what could still be done.\n"
                 "# gap: whether the run that produced this round had caught it (caught | partly | missed | introduced),\n"
                 "# with that run's findings or applied edits, miss_reason, owner (the skill whose remit covers it) and\n"
                 "# note; gap_run names the run (comments.py gaps).\n")
# Did the run that produced the round catch what a co-author raised: a finding of it names the same problem (caught),
# part of it (partly), none does (missed), or the passage was written by one of its own applied edits (introduced).
GAP_VERDICTS = ("caught", "partly", "missed", "introduced")
# Why it was not caught in full: the dashboard's reasons for a reference review, so both read the same way.
MISS_REASONS = ("no-skill-covers", "skill-did-not-look", "judged-differently", "input-missing",
                "wording-preference", "later-decision")
NEEDS_OWNER = ("skill-did-not-look", "judged-differently")  # the miss was in a skill's remit: name the skill
INVENTORY = re.compile(r'<script type="application/json" id="inventory">(.*?)</script>', re.S)


class Failure(Exception):
    """A usage or ledger problem (exit 2), or one that stops the command from running (exit 3)."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def rev_marks() -> Any:
    """manuscript-revision-marks' reader of the master: its clean text, paragraphs and alignment."""
    if "coauthors_rev_marks" not in sys.modules:
        spec = importlib.util.spec_from_file_location("coauthors_rev_marks", REV_MARKS)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["coauthors_rev_marks"] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules["coauthors_rev_marks"]


def people_module() -> Any:
    """manuscript-mark-people's people.py: who a commenter is, and the rev-marks.toml it writes."""
    if "coauthors_people" not in sys.modules:
        spec = importlib.util.spec_from_file_location("coauthors_people", PEOPLE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["coauthors_people"] = module
        spec.loader.exec_module(module)
    return sys.modules["coauthors_people"]


def ai_of(text: Any) -> str | None:
    """The agent a comment says wrote it (`[ai:claude]` -> claude, `[ai]` -> ai), or None for a person's."""
    m = AI_MARK.match(str(text or ""))
    return (m.group(1) or "ai").lower() if m else None


def commenters(found: list[Found], start: Path) -> dict[str, Any]:
    """Every person who commented, replied or suggested in the Doc, mapped to a handle (manuscript-mark-people's
    rules: an alias, an author of the paper by full name or by initials and surname start, else a new handle) and
    recorded in rev-marks.toml as a person, their Doc name among the handle's aliases. A comment marked [ai:NAME]
    is an agent's and names nobody. A Doc's commenters are people by default: they read the paper as one."""
    pm = people_module()
    names: list[str] = []
    for f in found:
        if not (f.kind == "comment" and ai_of(f.comment)):
            names.append(f.author)
        names += [r.get("author", "") for r in f.replies if not ai_of(r.get("text"))]
    names = [n for n in dict.fromkeys(n.strip() for n in names) if n]
    if not names:
        return {"handles": {}, "people": [], "config": None}
    try:
        survey = pm.survey(start)
        people = pm.rm.load_people(start, survey.config)
        matches = [pm.resolve(n, people, survey.identities) for n in names]
        pm.record_people(survey.target, matches)
    except (pm.rm.ConfigError, ValueError) as exc:
        raise Failure(f"rev-marks.toml: {exc}") from None
    except (RuntimeError, OSError) as exc:
        raise Failure(f"the commenters could not be recorded as people: {exc}", 3) from None
    return {"handles": {m.name: m.handle for m in matches}, "config": survey.target.as_posix(),
            "people": [{"name": m.name, "handle": m.handle, "rule": m.rule, **({"via": m.via} if m.via else {})}
                       for m in matches]}


# --- the Google Doc export ------------------------------------------------------------------------


@dataclass
class Found:
    """A comment or a suggestion read from a Doc, before it has an id."""

    kind: str
    author: str
    date: str
    comment: str
    anchor: str
    before: str = ""
    after: str = ""
    at: int = 0  # where it starts in the Doc's text, for paper order
    replies: list[dict[str, str]] = field(default_factory=list)
    edits: list[dict[str, str]] = field(default_factory=list)
    resolved: bool | None = None
    span: tuple[int, int] = (0, 0)  # its range in the Doc's text: a reply has exactly its comment's
    gdoc_id: str = ""  # the Doc's own id (doco.…, suggest.…), read through the Google Docs connector
    resolved_by: str = ""  # who posted the reply that resolved the thread
    resolved_on: str = ""  # when they did

    @property
    def key(self) -> str:
        first = self.comment if self.kind == "comment" else " ".join(
            e.get("deleted") or e.get("inserted") or "" for e in self.edits)
        return f"{self.author}|{self.date}|{' '.join(first.split())[:40]}"


def paragraph_text(element: ET.Element) -> str:
    return "\n".join("".join(t.text or "" for t in p.iter(W + "t")) for p in element.iter(W + "p")).strip()


def read_docx(path: Path) -> list[Found]:
    try:
        archive = zipfile.ZipFile(path)
        document = ET.fromstring(archive.read("word/document.xml"))
        comments = ET.fromstring(archive.read("word/comments.xml")) if "word/comments.xml" in archive.namelist() else None
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise Failure(f"{path}: not a readable .docx ({exc}).", 3) from exc
    body = document.find(W + "body")
    if body is None:
        raise Failure(f"{path}: no document body.", 3)
    pieces: list[str] = []
    starts: dict[str, int] = {}
    ends: dict[str, int] = {}
    parts: list[tuple[str, str, str, int, int, str]] = []  # (ins|del, author, date, paragraph, position, text)
    state = {"pos": 0, "para": 0, "para_start": 0}
    paragraphs: list[tuple[int, int]] = []

    def add(text: str) -> None:
        pieces.append(text)
        state["pos"] += len(text)

    def walk(element: ET.Element, inserted: bool) -> None:
        tag = element.tag
        if tag == W + "commentRangeStart":
            starts.setdefault(element.get(W + "id", ""), state["pos"])
        elif tag == W + "commentRangeEnd":
            ends[element.get(W + "id", "")] = state["pos"]
        elif tag in (W + "ins", W + "del"):
            at = state["pos"]
            text = "".join(t.text or "" for t in element.iter(W + "t" if tag == W + "ins" else W + "delText"))
            for child in element:
                walk(child, inserted or tag == W + "ins")
            parts.append((tag[len(W):], element.get(W + "author", ""), element.get(W + "date", ""),
                          state["para"], at, text))
            return
        elif tag == W + "t" and not inserted or tag == W + "delText":
            add(element.text or "")
        elif tag == W + "tab" and not inserted:
            add(" ")
        elif tag == W + "br" and not inserted:
            add("\n")
        elif tag == W + "p":
            state["para_start"] = state["pos"]
        for child in element:
            walk(child, inserted)
        if tag == W + "p":
            paragraphs.append((state["para_start"], state["pos"]))
            state["para"] += 1
            add("\n")

    walk(body, False)
    text = "".join(pieces)

    def around(start: int, end: int) -> tuple[str, str]:
        return text[max(0, start - CONTEXT):start], text[end:end + CONTEXT]

    found: list[Found] = []
    copies: dict[tuple[str, str, str], Found] = {}
    raw = [] if comments is None else comments.findall(W + "comment")
    for element in raw:
        wid = element.get(W + "id", "")
        start = starts.get(wid, 0)
        end = max(start, ends.get(wid, start))
        author, date, said = element.get(W + "author", ""), element.get(W + "date", ""), paragraph_text(element)
        if (author, date, said) in copies:  # one comment over several ranges: one copy per range
            continue
        before, after = around(start, end)
        item = Found("comment", author, date, said, " ".join(text[start:end].split()), before, after, start,
                     span=(start, end))
        copies[author, date, said] = item
        found.append(item)
    found.sort(key=lambda f: (f.at, f.date))
    threads: list[Found] = []
    for item in found:
        root = threads[-1] if threads else None
        if root is not None and root.span == item.span and item.date >= root.date:
            root.replies.append({"author": item.author, "date": item.date, "text": item.comment})
        else:
            threads.append(item)

    suggestions: dict[tuple[int, str], Found] = {}
    for kind, author, date, para, at, said in parts:
        if not said:
            continue
        lo, hi = paragraphs[para] if para < len(paragraphs) else (at, at)
        item = suggestions.get((para, author))
        if item is None:
            before, after = around(lo, hi)
            item = Found("suggestion", author, date, "", " ".join(text[lo:hi].split()), before, after, lo)
            suggestions[para, author] = item
        last = item.edits[-1] if item.edits else None
        if kind == "ins" and last is not None and "inserted" not in last and last.get("_end") == at:
            last["inserted"] = said  # a deletion and the insertion at its place: one replacement
        else:
            item.edits.append({"deleted": said, "_end": at + len(said)} if kind == "del" else {"inserted": said})
        item.date = min(item.date, date) if item.date and date else item.date or date
    for item in suggestions.values():
        for edit in item.edits:
            edit.pop("_end", None)
        item.comment = describe(item.edits)
    return sorted([*threads, *suggestions.values()], key=lambda f: (f.at, f.kind, f.date))


def describe(edits: list[dict[str, str]]) -> str:
    """A suggestion's edits as one line a person reads."""
    said = []
    for e in edits:
        if e.get("deleted") and e.get("inserted"):
            said.append(f"replace “{e['deleted'].strip()}” with “{e['inserted'].strip()}”")
        elif e.get("inserted"):
            said.append(f"insert “{e['inserted'].strip()}”")
        else:
            said.append(f"delete “{e.get('deleted', '').strip()}”")
    return "Suggested edits: " + "; ".join(said) + "."


# --- the Google Docs connector's view of the Doc (read_doc with commentsIncluded) ---------------------------


def gdoc_document(path: Path) -> dict[str, Any]:
    """The document object of a saved read_doc result: the tool's answer ({"content": {...}}) or the document."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise Failure(f"{path}: cannot read: {exc}", 3) from None
    except json.JSONDecodeError as exc:
        raise Failure(f"{path}: not JSON ({exc}); save read_doc's whole answer", 2) from None
    doc = data.get("content", data) if isinstance(data, dict) else None
    if not isinstance(doc, dict) or not isinstance(doc.get("tabs"), list):
        raise Failure(f"{path}: not a Google Docs read_doc answer (no tabs).")
    if doc.get("commentsViewMode") not in (None, "COMMENTS_VIEW_MODE_INCLUDED") or "comments" not in doc:
        raise Failure(f"{path}: read without its comments; read_doc again with commentsIncluded: true.")
    return doc


def gdoc_body(doc: dict[str, Any], tab: str | None) -> list[Any]:
    """The content of the tab's body (the first tab by default)."""
    tabs = doc["tabs"]
    chosen = next((x for x in tabs if (x.get("tabProperties") or {}).get("tabId") == tab), None) if tab else tabs[0]
    if chosen is None:
        raise Failure(f"no tab {tab!r}; the Doc's tabs: "
                      + ", ".join(str((x.get("tabProperties") or {}).get("tabId")) for x in tabs))
    return ((chosen.get("documentTab") or {}).get("body") or {}).get("content", [])


def gdoc_runs(doc: dict[str, Any], tab: str | None) -> list[dict[str, Any]]:
    """Every text run of the tab's body in document order, with its index range and suggestion ids."""
    runs: list[dict[str, Any]] = []

    def walk(elements: list[Any]) -> None:
        for el in elements or []:
            if not isinstance(el, dict):
                continue
            for part in (el.get("paragraph") or {}).get("elements", []):
                run = part.get("textRun")
                if run and "startIndex" in part:
                    runs.append({"start": part["startIndex"], "end": part.get("endIndex", part["startIndex"]),
                                 "text": run.get("content", ""), "ins": run.get("suggestedInsertionIds") or [],
                                 "del": run.get("suggestedDeletionIds") or [],
                                 "style": list((run.get("suggestedTextStyleChanges") or {}))})
            for row in (el.get("table") or {}).get("tableRows", []):
                for cell in row.get("tableCells", []):
                    walk(cell.get("content", []))
            walk((el.get("tableOfContents") or {}).get("content", []))

    walk(gdoc_body(doc, tab))
    return sorted(runs, key=lambda r: r["start"])


def gdoc_paragraphs(path: Path, tab: str | None = None) -> list[str]:
    """A Doc's text from the Google Docs connector's read_doc, as doc_paragraphs reads an export: one string per
    paragraph (a table cell's each its own), pending insertions left out, the words a pending deletion would remove
    kept."""
    out: list[str] = []

    def walk(elements: list[Any]) -> None:
        for el in elements or []:
            if not isinstance(el, dict):
                continue
            if "paragraph" in el:
                text = " ".join("".join(run.get("content", "") for part in el["paragraph"].get("elements", [])
                                        if (run := part.get("textRun")) and not run.get("suggestedInsertionIds")).split())
                if text:
                    out.append(text)
            for row in (el.get("table") or {}).get("tableRows", []):
                for cell in row.get("tableCells", []):
                    walk(cell.get("content", []))
            walk((el.get("tableOfContents") or {}).get("content", []))

    walk(gdoc_body(gdoc_document(path), tab))
    return out


def read_gdoc(path: Path, tab: str | None = None) -> list[Found]:
    """A Doc's comments, replies and suggestions from the Google Docs connector's read_doc (commentsIncluded):
    each thread with the exact range it is anchored on and whether it was resolved (and by whom), each
    suggestion with its inserted and deleted text. The context around each is the Doc's text as the master
    has it: suggested insertions left out, suggested deletions kept."""
    doc = gdoc_document(path)
    runs = gdoc_runs(doc, tab)
    pieces, offsets = [], []  # the master-like text, and (doc index, text offset) where each kept run starts
    for run in runs:
        if run["ins"]:
            continue
        offsets.append((run["start"], sum(len(p) for p in pieces)))
        pieces.append(run["text"])
    text = "".join(pieces)

    def at(index: int) -> int:
        """The text offset of a document index (an index inside a left-out insertion goes to its start)."""
        pos = 0
        for start, offset in offsets:
            if start > index:
                break
            pos = offset + (index - start)
        return min(pos, len(text))

    def around(start: int, end: int) -> tuple[str, str]:
        return text[max(0, start - CONTEXT):start], text[end:end + CONTEXT]

    anchors = doc.get("commentAnchors") or {}
    found: list[Found] = []
    for thread in doc.get("comments") or []:
        head = thread.get("headPost") or {}
        quote = " ".join(str(thread.get("plainTextQuote") or "").split())
        ranges = (anchors.get(thread.get("anchorId") or "") or {}).get("ranges") or []
        if ranges:
            start, end = at(ranges[0]["startIndex"]), at(ranges[-1]["endIndex"])
        else:  # a comment with no anchor in the Doc: find its quoted words
            start = text.find(quote) if quote else -1
            start, end = (start, start + len(quote)) if start >= 0 else (0, 0)
        replies, resolved_by, resolved_on = [], "", ""
        for post in thread.get("replies") or []:
            said = str(post.get("content") or "")
            author = str((post.get("author") or {}).get("displayName") or "")
            if post.get("commentAction") == "RESOLVE":
                resolved_by = author if not ai_of(said) else f"[ai:{ai_of(said)}]"
                resolved_on = str(post.get("createTime") or "")[:10]
            elif post.get("commentAction") == "REOPEN":
                resolved_by = resolved_on = ""
            if said.strip():
                replies.append({"author": author, "date": str(post.get("createTime") or ""), "text": said})
        before, after = around(start, end)
        found.append(Found("comment", str((head.get("author") or {}).get("displayName") or ""),
                           str(head.get("createTime") or ""), str(head.get("content") or ""),
                           quote or " ".join(text[start:end].split()), before, after, start, replies,
                           resolved=(thread.get("status") == "RESOLVED") if thread.get("status") else None,
                           span=(start, end), gdoc_id=str(thread.get("commentId") or ""),
                           resolved_by=resolved_by if thread.get("status") == "RESOLVED" else "",
                           resolved_on=resolved_on if thread.get("status") == "RESOLVED" else ""))
    for s in doc.get("suggestions") or []:
        sid = str(s.get("suggestionId") or "")
        mine = [r for r in runs if sid in r["ins"] or sid in r["del"] or sid in r["style"]]
        if not mine or (s.get("status") or "OPEN") != "OPEN":
            continue
        inserted = "".join(r["text"] for r in mine if sid in r["ins"])
        deleted = "".join(r["text"] for r in mine if sid in r["del"])
        styled = "".join(r["text"] for r in mine if sid in r["style"] and sid not in r["ins"])
        start, end = at(mine[0]["start"]), at(mine[-1]["end"])
        edits = [{"deleted": deleted, "inserted": inserted}] if inserted or deleted else []
        head = s.get("headPost") or {}
        summary = str(s.get("summaryText") or "")
        before, after = around(start, start if inserted and not deleted else end)
        found.append(Found("suggestion", str((head.get("author") or {}).get("displayName") or ""),
                           str(head.get("createTime") or ""),
                           describe(edits) if edits else f"Suggested edits: {summary or 'formatting'} on “{styled.strip()}”.",
                           " ".join((deleted or styled or inserted).split()), before, after, start, [], edits,
                           span=(start, end), gdoc_id=sid))
    return sorted(found, key=lambda f: (f.at, f.kind, f.date))


def from_items(path: Path) -> list[Found]:
    """Items written from a connector's text view of the Doc."""
    data = load_yaml(path)
    if not isinstance(data, list):
        raise Failure(f"{path}: expected a list of items.")
    out = []
    for n, item in enumerate(data):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ("author", "comment")):
            raise Failure(f"{path}: item {n + 1} needs author and comment.")
        kind = item.get("kind", "comment")
        if kind not in KINDS:
            raise Failure(f"{path}: item {n + 1}: kind must be comment or suggestion.")
        out.append(Found(kind, item["author"], str(item.get("date", "")), item["comment"],
                         " ".join(str(item.get("anchor", "")).split()), str(item.get("context_before", "")),
                         str(item.get("context_after", "")), n, list(item.get("replies", [])),
                         list(item.get("edits", [])), item.get("resolved")))
    return out


# --- finding a passage in the master ----------------------------------------------------------------


def tokens(text: str) -> list[str]:
    return [t for t in (re.sub(r"\W+", "", w.lower()) for w in text.split()) if t]


class Master:
    """A round's master, word by word, as revision marks reads it (marks removed, paragraphs kept)."""

    def __init__(self, path: Path):
        rm = rev_marks()
        try:
            raw = rm.read_source(path)
        except (OSError, UnicodeDecodeError) as exc:
            raise Failure(f"{path}: cannot read ({exc}).", 3) from exc
        self.path = path
        self.syntax = rm.syntax_for(path)
        self.marks = rm.parse(raw, self.syntax)
        self.blocks = rm.blocks(self.marks)
        self.words = rm.flat(self.blocks)
        self.clean = self.marks.clean_text()
        self.norm: list[str] = []
        self.index: list[int] = []  # the word each normalized token is
        for k, word in enumerate(self.words):
            token = re.sub(r"\W+", "", word[0].lower())
            if token:
                self.norm.append(token)
                self.index.append(k)
        self.first = [0]
        for block in self.blocks:
            self.first.append(self.first[-1] + len(block.words))

    def locate(self, anchor: str, before: str = "", after: str = "") -> tuple[int, int] | None:
        """The words of the master the anchor stands for (an empty range for a comment on a point), found
        with the words around it in the Doc; None when the master does not have it."""
        b, a, f = tokens(before)[-CONTEXT_WORDS:], tokens(anchor), tokens(after)[:CONTEXT_WORDS]
        context = b + a + f
        if not context or not self.norm:
            return None
        i, j, k = SequenceMatcher(None, self.norm, context, autojunk=False).find_longest_match(
            0, len(self.norm), 0, len(context))
        if k == 0:
            return None
        lo, hi = max(0, i - j - 8), min(len(self.norm), i + len(context) - j + 8)
        at: dict[int, int] = {}
        for x, y, n in SequenceMatcher(None, self.norm[lo:hi], context, autojunk=False).get_matching_blocks():
            for d in range(n):
                at[y + d] = lo + x + d
        if len(at) < max(2, (len(context) + 1) // 2) and len(at) < len(context):
            return None
        first, last = len(b), len(b) + len(a)
        inside = [at[y] for y in range(first, last) if y in at]
        if inside:
            s, e = min(inside), max(inside) + 1
        else:
            earlier = [at[y] for y in range(first) if y in at]
            later = [at[y] for y in range(last, len(context)) if y in at]
            s = e = max(earlier) + 1 if earlier else min(later) if later else -1
            if s < 0:
                return None
        start = self.index[s] if s < len(self.index) else len(self.words)
        return (start, self.index[e - 1] + 1) if e > s else (start, start)

    def where(self, span: tuple[int, int]) -> tuple[str, int]:
        k = min(span[0], len(self.words) - 1)
        return self.words[k][3], self.words[k][1]

    def paragraphs(self, span: tuple[int, int]) -> tuple[int, int]:
        """The block range (first, last + 1) holding the span."""
        k0 = min(span[0], len(self.words) - 1)
        k1 = min(max(span[0], span[1] - 1), len(self.words) - 1)
        return self.words[k0][4], self.words[k1][4] + 1

    def text_of(self, blocks: tuple[int, int]) -> str:
        return "\n\n".join(self.blocks[k].text for k in range(*blocks))

    def verbatim(self, lo: int, hi: int) -> str:
        """Words lo..hi as the clean text writes them."""
        rm = rev_marks()
        start, end = self.words[lo][5], self.words[hi - 1][5] + len(self.words[hi - 1][0])
        return " ".join(rm.clean_slice(self.marks.text, start, end, self.marks.removals).split())

    def clean_runs(self, first: int, last: int) -> list[tuple[int, int]]:
        """Words first..last split wherever a revision mark or a table-cell border sits between two of them."""
        runs, start = [], first
        for k in range(first, last):
            if "|" in self.words[k][0]:  # a table row's border is a word of its own: no quote holds it
                runs.append((start, k))
                start = k + 1
                continue
            if k + 1 < last:
                a, b = self.words[k][5] + len(self.words[k][0]), self.words[k + 1][5]
                if "|" in self.marks.text[a:b] or any(r0 < b and r1 > a for r0, r1 in self.marks.removals):
                    runs.append((start, k + 1))
                    start = k + 1
        runs.append((start, last))
        return [r for r in runs if r[1] > r[0]]

    def holds(self, passage: str) -> bool:
        return " ".join(passage.split()) in " ".join(self.clean.split())


# --- the ledger ---------------------------------------------------------------------------------------


class Literal(str):
    pass


yaml.SafeDumper.add_representer(Literal, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))


def plain(value: Any) -> Any:
    """Ledger values as YAML keeps them readable: a multi-line string as a block."""
    if isinstance(value, str) and "\n" in value:
        return Literal(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise Failure(f"{path}: cannot read ({exc}).", 3) from exc
    except yaml.YAMLError as exc:
        raise Failure(f"{path}: not valid YAML ({exc}).") from exc


def read_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": []}
    data = load_yaml(path) or {}
    if not isinstance(data, dict) or not isinstance(data.get("items", []), list):
        raise Failure(f"{path}: a ledger is a mapping with an items list.")
    data.setdefault("items", [])
    seen: set[str] = set()
    for item in data["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise Failure(f"{path}: every item needs an id.")
        if item["id"] in seen:
            raise Failure(f"{path}: id {item['id']} appears twice.")
        seen.add(item["id"])
        if item.get("status", "open") not in STATUSES:
            raise Failure(f"{path}: {item['id']}: status must be one of {', '.join(STATUSES)}.")
        if item.get("kind", "comment") not in KINDS:
            raise Failure(f"{path}: {item['id']}: kind must be comment or suggestion.")
        if item.get("severity") not in (None, *SEVERITIES) or item.get("stage") not in (None, *STAGES):
            raise Failure(f"{path}: {item['id']}: severity or stage outside the dashboard's scale.")
        gap = item.get("gap")
        if gap is not None:
            if not isinstance(gap, dict) or gap.get("verdict") not in GAP_VERDICTS:
                raise Failure(f"{path}: {item['id']}: gap.verdict must be one of {', '.join(GAP_VERDICTS)}.")
            if gap.get("miss_reason") not in (None, *MISS_REASONS):
                raise Failure(f"{path}: {item['id']}: gap.miss_reason must be one of {', '.join(MISS_REASONS)}.")
            if any(not isinstance(gap.get(key) or [], list) for key in ("findings", "changes")):
                raise Failure(f"{path}: {item['id']}: gap.findings and gap.changes are lists of IDs.")
    return data


def write_ledger(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(plain(data), sort_keys=False, allow_unicode=True, width=110)
    path.write_text(LEDGER_HEADER + body, encoding="utf-8")


def used_ids(ledger: Path, master: Master | None) -> set[str]:
    """Every C or S id the project has given out: in the ledgers of the round folders beside this one and in
    the master's revision marks."""
    ids: set[str] = set()
    for other in ledger.resolve().parent.parent.glob("*/comments.yaml"):
        try:
            data = load_yaml(other) or {}
        except Failure:
            continue
        ids |= {i.get("id", "") for i in data.get("items", []) if isinstance(i, dict)} if isinstance(data, dict) else set()
    if master is not None:
        rm = rev_marks()
        ids |= {rm.comment_of(s.id) for s in master.marks.segments}
    return ids


def next_number(ids: set[str], letter: str) -> int:
    numbers = [int(m.group(1)) for i in ids if (m := re.fullmatch(rf"{letter}(\d+)", i))]
    return max(numbers, default=0) + 1


def merge(ledger_path: Path, found: list[Found], master: Master | None, round_name: str | None,
          doc: str | None, source_file: str | None, handles: dict[str, str] | None = None) -> dict[str, Any]:
    data = read_ledger(ledger_path)
    if round_name:
        data["round"] = str(round_name)
    elif "round" not in data:
        name = ledger_path.resolve().parent.name
        data["round"] = name[1:] if re.fullmatch(r"v\d[\w.-]*", name) else name
    own_master = None
    if master is not None:
        where = Path(master.path).resolve()
        here = ledger_path.resolve().parent
        own_master = where.relative_to(here).as_posix() if where.is_relative_to(here) else str(master.path)
        data.setdefault("master", own_master)  # the round's main master; a comment on another Doc names its own
        own_master = None if own_master == data["master"] else own_master
    by_key = {item.get("key"): item for item in data["items"]}
    by_gdoc = {item["gdoc_id"]: item for item in data["items"] if item.get("gdoc_id")}

    def soft(by: Any, date: Any, comment: Any) -> tuple[str, str, str]:
        """The same comment pulled once as .docx and once through the connector: the Doc shows the author's name
        differently, so it is known by the person's handle, the minute it was written and its first words."""
        return (str(by or ""), str(date or "")[:16], " ".join(str(comment or "").split())[:40])
    by_soft = {soft(item.get("by"), item.get("date"), item.get("comment")): item for item in data["items"]
               if item.get("by") and item.get("master") == own_master}  # within this Doc only

    def key_of(f: Found) -> str:  # an item of another Doc of the round is known within that Doc
        return f"{own_master}|{f.key}" if own_master else f.key
    ids = used_ids(ledger_path, master) | {item["id"] for item in data["items"]}
    numbers = {"comment": next_number(ids, "C"), "suggestion": next_number(ids, "S")}
    added = 0
    for f in found:
        item = by_gdoc.get(f.gdoc_id) if f.gdoc_id else None
        item = item or by_key.get(key_of(f)) or (by_soft.get(soft(handles.get(f.author), f.date, f.comment))
                                                  if handles and handles.get(f.author) else None)
        if item is None:
            letter = "C" if f.kind == "comment" else "S"
            item = {"id": f"{letter}{numbers[f.kind]}", "kind": f.kind, "author": f.author, "date": f.date,
                    "key": key_of(f)}
            numbers[f.kind] += 1
            data["items"].append(item)
            added += 1
        if own_master:
            item["master"] = own_master
        if item.get("key") != key_of(f) and key_of(f) not in by_key:
            item.setdefault("also_keys", [])
            if key_of(f) not in item["also_keys"]:
                item["also_keys"].append(key_of(f))
        item.update({"anchor": f.anchor, "context_before": " ".join(f.before.split()[-CONTEXT_WORDS:]),
                     "context_after": " ".join(f.after.split()[:CONTEXT_WORDS]), "comment": f.comment})
        if f.edits:
            item["edits"] = f.edits
        for reply in f.replies:
            if ai_of(reply.get("text")):
                reply["ai"] = ai_of(reply.get("text"))
            elif handles and handles.get(reply.get("author", "")):
                reply["by"] = handles[reply["author"]]
        if f.replies or "replies" in item:
            item["replies"] = f.replies
        ai = ai_of(f.comment) if f.kind == "comment" else None
        if ai:  # an agent's comment stays on record but asks nothing of the next round
            item["ai"] = ai
            item.pop("by", None)
            if "status" not in item:
                item.update(status="not-on-point", why=f"Posted by an agent ([ai:{ai}]), not by a co-author.")
        elif handles and handles.get(f.author):
            item["by"] = handles[f.author]
        if f.resolved is not None:
            item["resolved"] = f.resolved
        if f.gdoc_id:
            item["gdoc_id"] = f.gdoc_id
        if f.resolved_by:  # who closed the thread, and when: a co-author accepting the answer, or an agent
            item["resolved_by"] = (handles or {}).get(f.resolved_by) or f.resolved_by
            if f.resolved_on:
                item["resolved_on"] = f.resolved_on
        elif f.resolved is False:
            item.pop("resolved_by", None)
            item.pop("resolved_on", None)
        if master is not None:
            span = master.locate(f.anchor, f.before, f.after)
            item["where"], item["line"] = master.where(span) if span else ("", None)
        for key, default in (("status", "open"), ("now", ""), ("why", ""), ("next", "")):
            item.setdefault(key, default)
    known = {key_of(f) for f in found}
    for item in data["items"]:  # an item matched under another key (the other pull method) is still in this pull
        if any(k in known for k in item.get("also_keys", [])) or (item.get("gdoc_id") and item["gdoc_id"] in
                                                                   {f.gdoc_id for f in found}):
            known.add(item.get("key"))
    # This pull speaks only for its own Doc: the comments of the round's other Docs are neither gone nor reordered.
    gone = [item["id"] for item in data["items"] if item.get("master") == own_master and item.get("key") not in known]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data.setdefault("sources", []).append({k: v for k, v in {"doc": doc, "file": source_file, "pulled": stamp,
                                                             "items": len(found), "new": added}.items() if v is not None})
    order = {key_of(f): n for n, f in enumerate(found)}
    for item in data["items"]:
        for k in item.get("also_keys", []):
            if k in order:
                order.setdefault(item.get("key"), order[k])
    place = {id(i): n for n, i in enumerate(data["items"])}
    data["items"].sort(key=lambda i: (i.get("master") or "", order.get(i.get("key"), len(order) + place[id(i)])))
    ordered = {k: data[k] for k in ("round", "master", "sources", "items") if k in data}
    write_ledger(ledger_path, ordered | {k: v for k, v in data.items() if k not in ordered})
    return {"ledger": ledger_path.as_posix(), "round": data["round"], "items": len(data["items"]), "new": added,
            "not_in_this_pull": gone,
            "not_located": [i["id"] for i in data["items"] if master is not None and i.get("line") is None
                            and i.get("key") in known]}


# --- the next round's answer ----------------------------------------------------------------------------


def assess(data: dict[str, Any], pairs: Masters) -> list[dict[str, Any]]:
    """Each item with where its passage went in the new round, and the ledger's problems with it."""
    rm = rev_marks()
    out = []
    for item in data["items"]:
        old, new = pairs.of(item)
        ops = pairs.ops(old, new)
        status = item.get("status", "open")
        row = {"id": item["id"], "status": status, "change": None, "before": None, "after": None, "segments": [],
               "rev_ids": [], "quote": None, "problems": [], "hints": []}
        span = old.locate(item.get("anchor", ""), item.get("context_before", ""), item.get("context_after", "")) \
            if old else None
        if old and span is None:
            row["change"] = "not-located"
        if old and span:
            blocks = old.paragraphs(span)
            row["before"] = old.text_of(blocks)
            row["quote"] = quote(old, span)
            if new and ops is not None:
                kept = counterpart_blocks(ops, new, old.first[blocks[0]], old.first[blocks[1]])
                if kept is None:
                    row["change"], row["quote"] = "removed", None  # nothing of the new round to quote
                else:
                    lo, hi = new.first[kept[0]], new.first[kept[1]]
                    row["after"] = new.text_of(kept)
                    row["change"] = "unchanged" if row["after"] == row["before"] else "changed"
                    row["segments"] = sorted({new.marks.segments[w[2]].id for w in new.words[lo:hi] if w[2] >= 0})
                    a_lo, a_hi = rm.counterpart(ops, span[0], max(span[1], span[0] + 1), False)
                    row["quote"] = quote(new, (a_lo, a_hi)) if a_hi > a_lo else quote(new, (lo, hi))
        if new:
            named = [s for s in new.marks.segments if rm.comment_of(s.id) == item["id"]]
            row["rev_ids"] = [s.id for s in named]
            if row["change"] == "removed" and named:  # its paragraph went, and a passage written for it is elsewhere
                row["change"] = "moved"
                row["after"] = "\n\n".join(rm.own_text(new.marks, s) for s in named)
                lo, hi = rm.words_in([w[5] for w in new.words], named[0])
                row["quote"] = quote(new, (lo, min(hi, lo + 30))) if hi > lo else None
        problems, hints = row["problems"], row["hints"]
        if status in ("addressed", "partly"):
            if not str(item.get("now", "")).strip():
                problems.append(f"{status} needs now: the new round's passage that answers it, verbatim")
            elif new and not new.holds(item["now"]):
                problems.append("now is not in the new round, verbatim")
        if status in ("declined", "not-on-point") and not str(item.get("why", "")).strip():
            problems.append(f"{status} needs why: the reason, for the co-author")
        if status in ("open", "partly") and not str(item.get("next", "")).strip():
            problems.append(f"{status} needs next: what could still be done")
        if new and row["change"] == "changed" and status == "open":
            hints.append("its paragraph changed in the new round: check whether the change answers it")
        if new and row["change"] == "unchanged" and status == "addressed" and not row["rev_ids"]:
            hints.append("addressed, but its paragraph reads the same in the new round: say where it was answered")
        out.append(row)
    return out


def counterpart_blocks(ops: list, new: Master, lo: int, hi: int) -> tuple[int, int] | None:
    """The new round's paragraphs that old words lo..hi became: those holding their equal or replaced words; for a
    paragraph rewritten past recognition, what stands in its place; None when nothing does."""
    found: list[int] = []
    for tag, i1, i2, j1, j2 in ops:
        if i1 < hi and i2 > lo and j2 > j1 and tag in ("equal", "replace"):
            found += [j1 + max(lo, i1) - i1, j1 + min(hi, i2) - i1 - 1] if tag == "equal" else [j1, j2 - 1]
    if not found:
        c1, c2 = rev_marks().counterpart(ops, lo, hi, False)
        if c1 == c2:
            return None
        found = [c1, c2 - 1]
    return new.words[min(found)][4], new.words[max(found)][4] + 1


def quote(master: Master, span: tuple[int, int]) -> str | None:
    """At least three words of the master around a span, verbatim, to find the passage once."""
    if not master.words:
        return None
    lo, hi = span
    block = master.words[min(lo, len(master.words) - 1)][4]
    first, last = master.first[block], master.first[block + 1]
    lo, hi = max(first, min(lo, last - 1)), max(min(hi, last), min(lo, last - 1) + 1)
    # The quote must read the same in the marked master the run checks against: no revision mark and no table-cell
    # border inside it. Take the clean stretch around the span, the longest one the span touches first.
    runs = master.clean_runs(first, last)
    touching = [r for r in runs if r[0] < hi and r[1] > lo and r[1] - r[0] >= 3]
    near = sorted((r for r in runs if r[1] - r[0] >= 3), key=lambda r: min(abs(r[0] - lo), abs(r[1] - hi)))
    chosen = max(touching, key=lambda r: min(r[1], hi) - max(r[0], lo)) if touching else (near[0] if near else None)
    if chosen is None:
        return None
    a, b = chosen
    lo, hi = max(a, min(lo, b - 1)), max(min(hi, b), min(lo, b - 1) + 1)
    while hi - lo < 6 and (lo > a or hi < b):
        lo, hi = max(a, lo - 1), min(b, hi + 1)
    hi = min(hi, lo + 30)
    return master.verbatim(lo, hi) if hi - lo >= 3 else None


class Masters:
    """The old and new master of each item: the round's main master (--old, or the ledger's `master`) and --new,
    or for a comment on another Doc of the round (its own `master`, say the supplement) that file in the
    ledger's round and the same path in --new's round. Each is read once."""

    def __init__(self, data: dict[str, Any], ledger: Path, old: Path | None, new: Path | None):
        main = data.get("master")
        self.old = old or ((ledger.parent / main if not Path(main).is_absolute() else Path(main)) if main else None)
        self.new, self.ledger = new, ledger
        self.read: dict[Path, Master] = {}
        self.aligned: dict[tuple[int, int], list] = {}

    def get(self, path: Path | None) -> Master | None:
        if path is None or not path.is_file():
            return None
        key = path.resolve()
        if key not in self.read:
            self.read[key] = Master(path)
        return self.read[key]

    def of(self, item: dict[str, Any]) -> tuple[Master | None, Master | None]:
        own = item.get("master")
        if not own:
            if self.old is not None and not self.old.is_file():
                raise Failure(f"{self.old}: cannot read the master.", 3)
            return self.get(self.old), self.get(self.new)
        return self.get(self.ledger.parent / own), self.get(self.new.parent / own) if self.new else None

    def ops(self, old: Master | None, new: Master | None) -> list | None:
        if old is None or new is None:
            return None
        key = (id(old), id(new))
        if key not in self.aligned:
            self.aligned[key] = rev_marks().align(old.blocks, new.blocks)[2]
        return self.aligned[key]


def first_line(text: str) -> str:
    line = next((l.strip() for l in str(text).splitlines() if l.strip()), "")
    return line if len(line) <= 160 else line[:157].rstrip() + "…"


def person_names(items: list[dict[str, Any]]) -> dict[str, str]:
    """One name for each person, by item id: the items of one handle (`by:`) go by the name most of them carry (the
    longer on a tie: "Tom Example" over "T Exa"), so a co-author the Docs show under two names is counted once."""
    names: dict[str, Counter] = {}
    for item in items:
        if item.get("by"):
            names.setdefault(str(item["by"]), Counter())[str(item.get("author", ""))] += 1
    chosen = {by: max(counts, key=lambda name: (counts[name], len(name))) for by, counts in names.items()}
    return {str(item.get("id")): chosen.get(str(item.get("by") or ""), str(item.get("author", "?"))) for item in items}


def findings(data: dict[str, Any], rows: list[dict[str, Any]], next_round: str | None, ledger: Path) -> tuple[dict, str]:
    """The stage's findings.json and the digest (comments.md) its evidence quotes."""
    names = person_names(data["items"])
    lines = [f"# Co-authors' comments on v{data.get('round', '?')}", ""]
    out, items, not_checked = [], [], []
    for item, row in zip(data["items"], rows):
        head = f"{item['id']} ({item.get('author', '?')}, {str(item.get('date', ''))[:10]}): {first_line(item.get('comment', ''))}"
        lines += [f"## {head}", "", f"- Status: {item.get('status', 'open')}"]
        lines += [f"- {label}: {' '.join(str(item[key]).split())}" for key, label in
                  (("where", "Where"), ("now", "Now"), ("why", "Why"), ("next", "What could be done"))
                  if str(item.get(key) or "").strip()]
        lines.append("")
        finding_ids = []
        status = item.get("status", "open")
        if status in ("open", "partly"):
            fid = f"CA-{len(out) + 1}"
            finding_ids.append(fid)
            suggestion = item.get("kind") == "suggestion"
            words = " ".join(str(item.get("comment", "")).split()).split()
            summary = f"{item['id']} ({item.get('author', 'a co-author')}): " + " ".join(words[:10]) + ("…" if len(words) > 10 else "")
            out.append({
                "id": fid, "category": item.get("category") or "Writing and clarity",
                "section": item.get("where") or "Whole manuscript",
                "quote": row["quote"], **({} if row["quote"] else {"looked_in": [f"v{next_round or data.get('round')}"]}),
                "summary": summary,
                "detail": (f"{'Suggested edits' if suggestion else 'Comment'} on v{data.get('round')} by "
                           f"{item.get('author', 'a co-author')}, {'partly answered' if status == 'partly' else 'not answered yet'}"
                           f"{' in v' + next_round if next_round else ''}: “{' '.join(str(item.get('comment', '')).split())[:400]}”"),
                "action": " ".join(str(item.get("next", "")).split())
                          or "Not triaged yet: decide what the next round does with it (manuscript-coauthors, step 2).",
                "severity": item.get("severity") or "minor", "stage": item.get("stage") or "writing",
                "confidence": "confirmed", "decision": bool(item.get("decision", False)),
                "evidence": [{"path": "comments.md", "quote": head}]})
        if row["change"] == "not-located":
            not_checked.append({"check": f"where {item['id']} sits in the manuscript",
                                "why": "the text it was attached to in the Doc was not found in the master",
                                "leaves_open": "whether the commented passage changed"})
        items.append({
            "id": item["id"], "kind": item.get("kind", "comment"), "author": names[str(item["id"])],
            "date": str(item.get("date", "")), "where": item.get("where") or "", "anchor": item.get("anchor", ""),
            "comment": item.get("comment", ""),
            "replies": [{k: r.get(k, "") for k in ("author", "date", "text")} for r in item.get("replies") or []
                        if isinstance(r, dict)],  # the dashboard's reply; by: and ai: stay in the ledger
            "edits": [{"deleted": e.get("deleted", ""), "inserted": e.get("inserted", "")} for e in item.get("edits", [])],
            # With no later version yet, the paragraph was compared with itself: nothing changed, nothing answered it.
            "resolved": item.get("resolved"), "status": status, "change": row["change"] if next_round else None,
            "before": row["before"], "after": row["after"] if next_round else None, "now": item.get("now", "") or "",
            "why": item.get("why", "") or "",
            "next": item.get("next", "") or ("Not triaged yet: decide what the next round does with it."
                                            if status in ("open", "partly") else ""),
            "rev_ids": row["rev_ids"] or list(item.get("rev_ids", [])), "finding_ids": finding_ids,
            "gap": gap_record(item)})
    document = {"skill": "manuscript-coauthors", "findings": out, "changes": [], "dismissed": [],
                "not_checked": not_checked,
                "coauthors": {"round": str(data.get("round", "")), "next_round": next_round,
                              "source": ledger.name, "gap_run": str(data.get("gap_run") or ""),
                              "gap_matched_by": str(data.get("gap_matched_by") or ""), "items": items}}
    return document, "\n".join(lines).rstrip() + "\n"


# --- did the run that produced the round catch it -------------------------------------------------------
# Co-authors read the version a run handed over. What they raise is a second reading of that version, so each
# comment is matched against the run's own records, as a reference review is: which of its problems names the same
# thing, or which of its applied edits wrote the passage. The run's inventory is its findings.json, or the dashboard
# it rendered, which carries the same records (a run folder often stays on the computer that ran it).

QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                        " ": " "})
STOP = set("about after also because been before being between both could does doing done each from have into more "
           "most only other over such than that their them then there these they this those through under upon very "
           "were what when where which while whose with within without would your".split())


def gap_record(item: dict[str, Any]) -> dict[str, Any] | None:
    """The ledger's gap, as the dashboard's co-author comment carries it."""
    gap = item.get("gap")
    if not gap:
        return None
    return {"verdict": gap["verdict"], "finding_ids": [str(x) for x in gap.get("findings") or []],
            "change_ids": [str(x) for x in gap.get("changes") or []], "miss_reason": gap.get("miss_reason"),
            "owner": str(gap.get("owner") or ""), "note": " ".join(str(gap.get("note") or "").split())}


def load_inventory(path: Path) -> dict[str, Any]:
    """The run's adjudicated inventory, from its findings.json or from the dashboard it rendered."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Failure(f"{path}: cannot read ({exc}).", 3) from exc
    if path.suffix.lower() in (".html", ".htm"):
        found = INVENTORY.search(text)
        if not found:
            raise Failure(f"{path}: not a manuscript dashboard (it carries no inventory).")
        text = found.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Failure(f"{path}: not valid JSON ({exc}).") from exc
    data = data.get("inventory", data) if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise Failure(f"{path}: no findings in it; give the run's findings.json or the dashboard it rendered.")
    return data


def norm(text: Any) -> str:
    return " ".join(str(text or "").translate(QUOTES).split())


def words_of(text: Any) -> set[str]:
    """Content words, cut to six letters so that plural and verb forms meet."""
    return {w[:6] for w in re.findall(r"[a-z][a-z0-9-]{3,}", norm(text).lower()) if w not in STOP}


def section_number(text: Any) -> str:
    found = re.match(r"\s*(?:Section\s+)?(S?\d+(?:\.\d+)*)\b", str(text or ""))
    return found.group(1) if found else ""


def own_findings(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """The run's problems: not dismissed, and not made from these comments by the co-authors stage itself."""
    return [f for f in inventory.get("findings", []) if f.get("assessment") != "dismissed"
            and set(f.get("skills") or []) - {"manuscript-coauthors"}]


def asked_words(item: dict[str, Any]) -> set[str]:
    edits = " ".join(f"{e.get('deleted', '')} {e.get('inserted', '')}" for e in item.get("edits") or [])
    replies = " ".join(str(r.get("text", "")) for r in item.get("replies") or [] if isinstance(r, dict))
    return words_of(" ".join((str(item.get("comment", "")), replies, str(item.get("anchor", "")), edits)))


def candidates(item: dict[str, Any], row: dict[str, Any], inventory: dict[str, Any]) -> dict[str, list]:
    """What of the run might answer a comment: the applied edits that wrote its passage, and the problems, dismissed
    flags, unchecked items, referees' concerns and story tests nearest to it. A list to judge from, never a match."""
    paragraph = norm(row.get("before"))
    anchor = norm(item.get("anchor"))
    probe = anchor if len(anchor) >= 12 else norm(row.get("quote")) or anchor
    asked = asked_words(item)
    near = asked | words_of(paragraph)
    number = section_number(item.get("where"))

    def score(text: str, quote: str = "", section: str = "") -> tuple[float, int]:
        overlap = len(asked & words_of(text))
        s = overlap + 0.25 * len(near & words_of(text))
        if quote and norm(quote) and norm(quote) in paragraph:
            s += 6
        if number and section_number(section) == number:
            s += 2
        return s, overlap

    def top(rows: list[tuple[tuple[float, int], Any]], n: int, least: float) -> list:
        return [r for (s, _), r in sorted(rows, key=lambda x: x[0], reverse=True) if s >= least][:n]

    written = [c for c in inventory.get("changes", []) if c.get("status") == "applied" and probe
               and probe in norm(c.get("after")) and probe not in norm(c.get("before"))]
    problems = top([(score(" ".join(str(f.get(k) or "") for k in ("summary", "detail", "action", "quote")),
                           f.get("quote") or "", f.get("section") or ""), f) for f in own_findings(inventory)], 5, 3)
    dismissed = top([(score(f"{d.get('summary', '')} {d.get('why', '')}"), d) for d in inventory.get("dismissed", [])], 2, 3)
    unchecked = top([(score(f"{n.get('check', '')} {n.get('leaves_open', '')}"), n)
                     for n in inventory.get("not_checked", [])], 2, 3)
    concerns = top([(score(str(c.get("concern", "")), section=str(c.get("location", ""))), c)
                    for r in (inventory.get("panel") or {}).get("reviewers", []) for c in r.get("concerns", [])], 3, 4)
    tests = top([(score(f"{t.get('test', '')} {t.get('note', '')}"), t)
                 for t in (inventory.get("story") or {}).get("tests", [])], 2, 3)
    return {"written": written, "problems": problems, "dismissed": dismissed, "unchecked": unchecked,
            "concerns": concerns, "tests": tests}


def clip(text: Any, n: int = 220) -> str:
    text = norm(text)
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def worksheet(data: dict[str, Any], rows: list[dict[str, Any]], inventory: dict[str, Any], every: bool) -> str:
    """For the agent who matches the comments: each comment with the run's records nearest to it."""
    run_id = inventory.get("run_id", "?")
    lines = [f"# Did run {run_id} catch the co-authors' comments on v{data.get('round', '?')}?", "",
             "For each comment, read it with its passage and the run's records below, then write a gap record in a",
             "YAML file and merge it (`comments.py gaps LEDGER --inventory … --merge GAPS.yaml`):", "",
             "```yaml",
             f"run: {run_id}",
             "matched_by: the coordinating agent, after the comments arrived",
             "items:",
             "  C12: {verdict: missed, miss_reason: skill-did-not-look, owner: manuscript-prose-edit,",
             "        note: The sentence it questions was never read for sense; the prose stage reads only what it edits.}",
             "  C13: {verdict: caught, findings: [PE-3], note: Raised and proposed, left for the authors.}",
             "  C14: {verdict: introduced, changes: [improve.C40], miss_reason: judged-differently,",
             "        owner: manuscript-improve, note: The run wrote this sentence; the re-check passed it as accurate.}",
             "```", "",
             f"Verdicts: {', '.join(GAP_VERDICTS)}. `caught` and `partly` name the run's problems (`findings`);",
             "`introduced` names the applied edits that wrote the passage (`changes`). A dismissed flag is never a",
             "match: a comment the run dismissed is `missed` with `judged-differently`. Anything not caught in full",
             f"says why ({', '.join(MISS_REASONS)}) and, when the miss was in a skill's remit, its `owner`.",
             "The candidates are found by shared words, so read each before using it; the run may also have raised",
             "a comment where nothing below shows it.", ""]
    authors: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}  # each co-author's, in paper order
    names = person_names(data["items"])
    for item, row in zip(data["items"], rows):
        if every or not item.get("gap"):
            authors.setdefault(names[str(item.get("id"))], []).append((item, row))
    for author, pairs in authors.items():
        lines += [f"# {author}: {len(pairs)} to judge", ""]
        for item, row in pairs:
            lines += comment_block(item, row, candidates(item, row, inventory))
    return "\n".join(lines).rstrip() + "\n"


def comment_block(item: dict[str, Any], row: dict[str, Any], found: dict[str, list]) -> list[str]:
    """One comment of the worksheet: what it asks, its passage, and the run's records nearest to it."""
    lines = [f"## {item['id']} ({item.get('kind', 'comment')}, {item.get('status', 'open')})"
             f"{' · ' + item['where'] if item.get('where') else ''}", ""]
    if item.get("comment"):
        lines += [f"> {norm(item['comment'])}", ""]
    for e in item.get("edits") or []:
        lines.append(f"- Suggested: delete “{e.get('deleted', '')}” insert “{e.get('inserted', '')}”")
    for r in item.get("replies") or []:
        if isinstance(r, dict):
            lines.append(f"- Reply ({r.get('author', '?')}): {clip(r.get('text'), 300)}")
    if item.get("anchor"):
        lines.append(f"- On: “{clip(item['anchor'], 160)}”")
    if row.get("before"):
        lines.append(f"- Passage: {clip(row['before'], 700)}")
    if item.get("gap"):
        lines.append(f"- Recorded: {json.dumps(item['gap'], ensure_ascii=False)}")
    for c in found["written"]:
        lines.append(f"- **Written by the run's edit {c['id']}** ({c.get('section', '')}): {clip(c.get('summary'), 160)}")
    for f in found["problems"]:
        lines.append(f"- Problem {f['id']} [{f.get('severity')}, {f.get('resolution')}, {clip(f.get('section'), 40)}]: "
                     f"{clip(f.get('summary'), 160)} · Action: {clip(f.get('action'), 200)}")
    for d in found["dismissed"]:
        lines.append(f"- Dismissed by {d.get('skill')}: {clip(d.get('summary'), 140)} · Why: {clip(d.get('why'), 160)}")
    for n in found["unchecked"]:
        lines.append(f"- Not checked by {n.get('skill')}: {clip(n.get('check'), 120)} · Leaves open: {clip(n.get('leaves_open'), 140)}")
    for c in found["concerns"]:
        lines.append(f"- Referee concern {c.get('id')} [{c.get('severity')}] ({clip(c.get('location'), 60)}): "
                     f"{clip(c.get('concern'), 200)}{' → ' + ', '.join(c['finding_ids']) if c.get('finding_ids') else ''}")
    for t in found["tests"]:
        lines.append(f"- Story test “{t.get('test')}” ({t.get('result')}): {clip(t.get('note'), 200)}")
    lines.append("")
    return lines


def gap_problems(gap: dict[str, Any], inventory: dict[str, Any]) -> list[str]:
    findings = {f.get("id"): f for f in inventory.get("findings", [])}
    changes = {c.get("id"): c for c in inventory.get("changes", [])}
    verdict, out = gap["verdict"], []
    fids, cids = [str(x) for x in gap.get("findings") or []], [str(x) for x in gap.get("changes") or []]
    if verdict in ("caught", "partly") and not fids:
        out.append(f"{verdict}: name the run's problems that raise it (findings)")
    if verdict == "introduced" and not cids:
        out.append("introduced: name the run's applied edits that wrote the passage (changes)")
    for fid in fids:
        f = findings.get(fid)
        if f is None:
            out.append(f"problem {fid} is not in the run's inventory")
        elif f.get("assessment") == "dismissed":
            out.append(f"problem {fid} is a dismissed flag, which is never a match (say missed, judged-differently)")
        elif not set(f.get("skills") or []) - {"manuscript-coauthors"}:
            out.append(f"problem {fid} was made from the co-authors' comments, not found by the run")
    for cid in cids:
        c = changes.get(cid)
        if c is None:
            out.append(f"edit {cid} is not in the run's inventory")
        elif c.get("status") != "applied":
            out.append(f"edit {cid} was only proposed; the co-authors read what the run applied")
    reason, owner = gap.get("miss_reason"), str(gap.get("owner") or "")
    if verdict == "caught" and reason:
        out.append("caught in full has no miss_reason")
    if verdict != "caught" and not reason:
        out.append(f"{verdict}: say why the run did not catch it in full (miss_reason)")
    if verdict != "caught" and not norm(gap.get("note")):
        out.append(f"{verdict}: say in a sentence what the run missed or wrote (note)")
    if reason in NEEDS_OWNER and not owner:
        out.append(f"{reason}: name the skill whose remit covers it (owner)")
    if owner and not re.fullmatch(r"manuscript-[a-z-]+", owner):
        out.append(f"owner {owner!r} is not a skill's name (manuscript-…)")
    return out


def check_gaps(data: dict[str, Any], inventory: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The ledger's gap records against the run's inventory: their problems, and the comments not judged yet (a
    comment that is not on point needs none)."""
    problems, unjudged = [], []
    judged = [item for item in data["items"] if item.get("gap")]
    run_id = str(inventory.get("run_id") or "")
    if judged and not data.get("gap_run"):
        problems.append("gap_run: name the run whose records the comments were matched against")
    elif judged and run_id and str(data["gap_run"]) != run_id:
        problems.append(f"gap_run is {data['gap_run']}, but this inventory is run {run_id}")
    for item in data["items"]:
        if item.get("gap"):
            problems += [f"{item['id']}: {p}" for p in gap_problems(item["gap"], inventory)]
        elif item.get("status", "open") != "not-on-point":
            unjudged.append(item["id"])
    return problems, unjudged


def gap_counts(data: dict[str, Any]) -> dict[str, Any]:
    """The gap records counted overall and for each co-author."""
    def counts(items: list[dict[str, Any]]) -> dict[str, Any]:
        gaps = [item["gap"] for item in items if item.get("gap")]
        count = lambda key: dict(sorted(((k, sum(1 for g in gaps if (g.get(key) or "") == k)) for k in
                                         {str(g.get(key) or "") for g in gaps} if k), key=lambda kv: -kv[1]))
        return {"judged": len(gaps), "by_verdict": {v: sum(g["verdict"] == v for g in gaps) for v in GAP_VERDICTS},
                "miss_reasons": count("miss_reason"), "by_owner": count("owner")}
    authors: dict[str, list[dict[str, Any]]] = {}
    names = person_names(data["items"])
    for item in data["items"]:
        authors.setdefault(names[str(item.get("id"))], []).append(item)
    return {**counts(data["items"]), "by_author": {author: {k: v for k, v in counts(items).items() if k != "miss_reasons"}
                                                   for author, items in authors.items() if any(i.get("gap") for i in items)}}


def merge_gaps(data: dict[str, Any], source: Path, inventory: dict[str, Any]) -> list[str]:
    """A YAML file of gap records (run, matched_by, items: {ID: {verdict, findings, changes, miss_reason, owner,
    note}}) into the ledger; nothing is written while one of them has a problem."""
    raw = load_yaml(source) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), dict):
        raise Failure(f"{source}: a mapping with run, matched_by and items (ID: gap record).")
    known = {item["id"]: item for item in data["items"]}
    problems = [f"{cid}: not a comment of this ledger" for cid in raw["items"] if cid not in known]
    staged = {}
    for cid, gap in raw["items"].items():
        if cid not in known:
            continue
        if not isinstance(gap, dict) or gap.get("verdict") not in GAP_VERDICTS:
            problems.append(f"{cid}: verdict must be one of {', '.join(GAP_VERDICTS)}")
            continue
        if gap.get("miss_reason") not in (None, *MISS_REASONS):
            problems.append(f"{cid}: miss_reason must be one of {', '.join(MISS_REASONS)}")
            continue
        record = {key: gap[key] for key in ("verdict", "findings", "changes", "miss_reason", "owner", "note")
                  if gap.get(key) not in (None, "", [])}
        if "note" in record:
            record["note"] = norm(record["note"])
        problems += [f"{cid}: {p}" for p in gap_problems(record, inventory)]
        staged[cid] = record
    run = str(raw.get("run") or inventory.get("run_id") or "")
    if inventory.get("run_id") and run != str(inventory["run_id"]):
        problems.append(f"run is {run}, but this inventory is run {inventory['run_id']}")
    if data.get("gap_run") and str(data["gap_run"]) != run:
        problems.append(f"the ledger was matched against run {data['gap_run']}; matching it against {run} too would mix two runs")
    if problems:
        return problems
    data["gap_run"] = run
    if raw.get("matched_by"):
        data["gap_matched_by"] = norm(raw["matched_by"])
    for cid, record in staged.items():
        known[cid]["gap"] = record
    return []


# --- what the authors changed in a released Doc -------------------------------------------------------------
# A round reaches the co-authors as Google Docs built from the master, and the authors then accept suggestions and
# edit the Doc's text. Those edits exist in the Doc only: an export shows no mark of an accepted suggestion, and the
# next release, built from the master, would undo them. So the Doc's text as it stands (pending suggestions left out,
# the words they would delete kept) is compared word by word with the master as it was released, Markdown's markup
# and what a Doc never shows (comments, images) set aside, and each paragraph that differs becomes an edit for
# runs.py apply on the master the next release is built from.

DASHES = (("---", "—"), ("--", "–"), ("...", "…"))  # how pandoc's smart typography renders them
# Comments and what pandoc reads as raw HTML (<CN0>) never reach a Doc; inside a code span the same text shows.
UNSHOWN = re.compile(r"(`[^`\n]*`)|<!--.*?-->|<[^<>\s]+>", re.S)
LINK = re.compile(r"(!?\[)[^\[\]]*(\]\([^)]*\)(?:\{[^}]*\})?)")  # a link or an image shows its text only (an image's
# text becomes its caption); a bracket of its own stays
ESCAPED = {f"\\{c}": chr(0xE000 + n) for n, c in enumerate("*_[]#|>`\\$^~")}
MARKUP_ONLY = re.compile(r"[-:|>#*_`]+")  # a table rule, a list bullet, a heading's hashes: no word, on either side
LIST_NUMBER = re.compile(r"(?:\d+|[a-z])[.)]|[-–•·*]")  # a Doc numbers its lists itself


def master_token(word: str) -> str:
    """A word of the master as the Doc built from it shows it: emphasis, superscript and subscript marks and escapes
    set aside, intraword underscores (W_display) kept. Links are masked before (LINK)."""
    word = html.unescape(word)
    if "`" in word:  # code shows as written: no emphasis or typography inside it
        return word.replace("`", "")
    for plain, typographic in DASHES:
        word = word.replace(plain, typographic)
    for escaped, held in ESCAPED.items():
        word = word.replace(escaped, held)
    word = re.sub(r"[*^~]", "", word)  # emphasis, superscript and subscript marks
    word = re.sub(r"(?<![^\W_])_+|_+(?![^\W_])", "", word)  # underscore emphasis; W_display keeps its own
    for escaped, held in ESCAPED.items():
        word = word.replace(held, escaped[1:])
    word = word.translate(QUOTES)
    return "" if MARKUP_ONLY.fullmatch(word) else word


def retoken(raw: str, word: str) -> str:
    """The Doc's word written the way the master writes that token: the characters that changed are replaced and the
    token's markup (superscripts, emphasis, escapes) stays around them, so Livia^1^ becomes Livia^4^, not Livia4. A
    token whose markup is more than marks over its characters (an entity, a dash ligature) takes the Doc's word."""
    chars: list[str] = []
    spans: list[tuple[int, int]] = []
    k = 0
    while k < len(raw):
        if raw[k] == "\\" and k + 1 < len(raw) and raw[k + 1] in "*_[]#|>`\\$^~":
            chars.append(raw[k + 1])
            spans.append((k, k + 2))
            k += 2
            continue
        edge = raw[k] == "_" and not (0 < k < len(raw) - 1 and raw[k - 1].isalnum() and raw[k + 1].isalnum())
        if raw[k] not in "*^~`" and not edge:
            chars.append(raw[k])
            spans.append((k, k + 1))
        k += 1
    shown = "".join(chars).translate(QUOTES)
    if not spans or shown != master_token(raw):
        return word
    out = raw
    for tag, a1, a2, b1, b2 in reversed(SequenceMatcher(None, shown, word, autojunk=False).get_opcodes()):
        if tag == "equal":
            continue
        if a2 == a1:  # an insertion goes before the character it precedes, or after the last one
            at = spans[a1][0] if a1 < len(spans) else spans[-1][1]
            out = out[:at] + word[b1:b2] + out[at:]
            continue
        # the changed characters' own spans go, the markup between them stays; the new text takes the first one's place
        for n, (start, end) in reversed(list(enumerate(spans[a1:a2]))):
            out = out[:start] + (word[b1:b2] if n == 0 else "") + out[end:]
    if re.search(r"\^[,;:.]$", raw):  # punctuation after a superscript stays after it: Georg^1^, not Georg^1,^
        out = re.sub(r"([,;:.])\^$", r"^\1", out)
    return out


def doc_paragraphs(path: Path) -> list[str]:
    """A Doc export's text as it stands, one string per paragraph: pending insertions left out, the words a pending
    deletion would remove kept (a suggestion nobody accepted is not an edit yet)."""
    try:
        root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise Failure(f"{path}: not a .docx export ({exc}).", 3) from exc
    out: list[str] = []
    for paragraph in root.iter(W + "p"):
        words: list[str] = []

        def walk(element: ET.Element, inserted: bool) -> None:
            for child in element:
                if child.tag == W + "ins":
                    walk(child, True)
                elif child.tag == W + "t" and not inserted or child.tag == W + "delText":
                    words.append(child.text or "")
                elif child.tag in (W + "tab", W + "br") and not inserted:
                    words.append(" ")
                elif child.tag != W + "p":  # a nested paragraph (a text box) is read on its own
                    walk(child, inserted)
        walk(paragraph, False)
        text = " ".join("".join(words).split())
        if text:
            out.append(text)
    return out


def clean_of(raw: str, path: Path) -> str:
    """A master's text with its revision marks removed: the text runs.py apply finds an edit's before-text in."""
    rm = rev_marks()
    return rm.parse(raw, rm.syntax_for(path)).clean_text()


@dataclass
class DocEdit:
    """One paragraph of the released master that the Doc now reads differently."""

    lo: int  # the paragraph's span in the released clean text
    hi: int
    section: str
    hunks: list[tuple[int, int, str]] = field(default_factory=list)  # (start, end, the Doc's words there)
    doc: list[str] = field(default_factory=list)  # the changed words as the Doc has them, for the report
    released: list[str] = field(default_factory=list)  # the words they replace, as released
    before: str = ""  # the paragraph as released, verbatim in the master's clean text
    after: str = ""  # the same paragraph with the Doc's words in place of the released ones


def doc_edits(released: str, paragraphs: list[str]) -> list[DocEdit]:
    """The paragraphs of the released master (clean text) that the Doc's paragraphs now read differently, each as
    the released paragraph and the same paragraph with the Doc's words in place. List numbers a Doc adds by itself
    are not differences. New words at the start of a Doc paragraph go before the paragraph's first word, and a new
    paragraph goes after the one it follows."""
    masked = UNSHOWN.sub(lambda m: m.group(0) if m.group(1) else re.sub(r"\S", " ", m.group(0)), released)
    masked = LINK.sub(lambda m: " " * len(m.group(1)) + m.group(0)[len(m.group(1)):-len(m.group(2))] + " " * len(m.group(2)),
                      masked)
    # a list's marker at the start of a line never reaches a Doc's text: the Doc numbers the list itself
    base = [(tok, m.start(), m.end()) for m in re.finditer(r"\S+", masked) if (tok := master_token(m.group(0)))
            and not (LIST_NUMBER.fullmatch(tok) and not masked[masked.rfind("\n", 0, m.start()) + 1:m.start()].strip())]
    doc = [(word.translate(QUOTES), n) for n, text in enumerate(paragraphs) for word in text.split()
           if not MARKUP_ONLY.fullmatch(word)]
    a, b = [t[0] for t in base], [t[0] for t in doc]
    edits: list[DocEdit] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        gone, came = a[i1:i2], b[j1:j2]
        if tag == "equal" or (not came and all(LIST_NUMBER.fullmatch(w) for w in gone)) \
                or (not gone and all(LIST_NUMBER.fullmatch(w) for w in came)) or "".join(gone) == "".join(came):
            continue  # a list number the Doc adds itself, or only the spacing differs ("summary ." against "summary.")
        opens = j1 == 0 or doc[j1][1] != doc[j1 - 1][1]  # the new words open a Doc paragraph
        forward = i1 == i2 and i1 < len(base) and j2 < len(doc) and opens and doc[j2 - 1][1] == doc[j2][1]
        words = ""
        one_for_one = i2 - i1 == j2 - j1 and len({doc[j][1] for j in range(j1, j2)}) == 1
        for j in range(j1, j2):
            breaks = j > j1 and doc[j][1] != doc[j - 1][1]
            word = retoken(released[base[i1 + j - j1][1]:base[i1 + j - j1][2]], doc[j][0]) if one_for_one else doc[j][0]
            words += ("\n\n" if breaks else " " if words else "") + word
        if i2 > i1:
            start, end = base[i1][1], base[i2 - 1][2]
            if not came:  # a deletion takes one space with it, so no double space is left
                if released[end:end + 1] == " ":
                    end += 1
                elif start and released[start - 1] == " ":
                    start -= 1
        elif forward:  # new words at the start of a paragraph
            start = end = base[i1][1]
            words += " "
        else:  # after the word before them: in its paragraph, or as a new paragraph of their own
            start = end = base[i1 - 1][2] if i1 else 0
            words = ("\n\n" if opens and i1 else " " if i1 else "") + words
        lo = released.rfind("\n", 0, start) + 1
        hi = released.find("\n", end)
        hi = len(released) if hi < 0 else hi
        if edits and lo <= edits[-1].hi:  # the same released paragraph as the change before
            edit = edits[-1]
            edit.hi = max(edit.hi, hi)
        else:
            heading = next((line.strip("#* ") for line in reversed(released[:lo].splitlines()) if line.startswith("#")), "")
            edit = DocEdit(lo, hi, heading)
            edits.append(edit)
        edit.hunks.append((start, end, words))
        edit.doc.append(" ".join(came))
        edit.released.append(" ".join(gone))
    for edit in edits:
        edit.before = after = released[edit.lo:edit.hi]
        for start, end, words in sorted(edit.hunks, key=lambda h: h[0], reverse=True):
            after = after[:start - edit.lo] + words + after[end - edit.lo:]
        edit.after = after
    return [e for e in edits if " ".join(e.before.split()) != " ".join(e.after.split())]


def shown_as(text: str) -> str:
    """A passage of the master as its Doc reads, for comparing words: markup set aside, one space between words."""
    return " ".join(t for w in text.split() if (t := master_token(w)))


def suggestions_in(edit: DocEdit, items: list[dict[str, Any]], pending: set[str]) -> list[str]:
    """The ledger's suggested edits this edit carries: no longer pending in the Doc (`pending` holds the keys of
    those still there, and their Doc ids when read through the connector), attached to this paragraph, and with
    every insertion now in it and every deletion gone."""
    before, after = shown_as(edit.before), shown_as(edit.after)
    found = []
    for item in items:
        if (item.get("kind") != "suggestion" or not item.get("edits") or item.get("key") in pending
                or item.get("gdoc_id") and item["gdoc_id"] in pending):
            continue
        anchor = " ".join(norm(item.get("anchor")).split()[:6])
        if anchor and anchor not in before and anchor not in after:
            continue
        parts = [(norm(e.get("inserted")), norm(e.get("deleted"))) for e in item["edits"]]
        if all((not ins or after.count(ins) > before.count(ins)) and (not gone or before.count(gone) > after.count(gone))
               for ins, gone in parts if ins or gone):
            found.append(item["id"])
    return found


def gaps(args: argparse.Namespace, ledger: Path, data: dict[str, Any], rows: list[dict[str, Any]]) -> int:
    inventory = load_inventory(Path(args.inventory))
    if args.merge:
        problems = merge_gaps(data, Path(args.merge), inventory)
        if problems:
            print("Nothing merged; fix these in the gap file first:", file=sys.stderr)
            for line in problems:
                print(f"  {line}", file=sys.stderr)
            return 1
        write_ledger(ledger, data)
    if args.merge or args.check:
        problems, unjudged = check_gaps(data, inventory)
        print(json.dumps({"ledger": ledger.as_posix(), "run": data.get("gap_run") or inventory.get("run_id"),
                          **gap_counts(data), "not_judged": unjudged, "problems": problems}, indent=2, ensure_ascii=False))
        return 1 if problems or (args.strict and unjudged) else 0
    sheet = worksheet(data, rows, inventory, args.all)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(sheet, encoding="utf-8")
        print(json.dumps({"worksheet": args.out, "to_judge": sum(1 for i in data["items"] if args.all or not i.get("gap"))},
                         ensure_ascii=False))
    else:
        sys.stdout.write(sheet)
    return 0


# --- commands -----------------------------------------------------------------------------------------


def why_of(item: dict[str, Any]) -> str:
    """A changelog row's Why, from the comment it answers: who asked, what, and what the ledger says was done."""
    words = " ".join(str(item.get("comment", "")).split()).split()
    asked = f"{item['id']} ({item.get('author', 'a co-author')}): “{' '.join(words[:16])}{'…' if len(words) > 16 else ''}”"
    done = " ".join(str(item.get("why", "")).split())
    return f"{asked}. {done}" if done else asked


def changelog(args: argparse.Namespace) -> int:
    """The round's changelog from its base, with Why filled from the ledgers where a row answers a comment."""
    rm = rev_marks()
    texts = {}
    for name in ("base", "new", "seen"):
        path = getattr(args, name)
        if path is None:
            continue
        found = Master(Path(path)).marks
        if found.errors:
            raise Failure(f"{path}: its revision marks do not lint (rev_marks.py lint).")
        texts[name] = found
    items = {}
    for ledger in args.ledger:
        items |= {item["id"]: item for item in read_ledger(Path(ledger))["items"]}
    rows = rm.changes(texts["base"], texts["new"])
    why = [why_of(items[rm.comment_of(r.id)]) if r.id and rm.comment_of(r.id) in items else "" for r in rows]
    since = rm.since_seen(rows, texts["seen"]) if "seen" in texts else None
    table = rm.format_changes(texts["base"], texts["new"], args.base_name or args.base, args.new_name or args.new, rows,
                              args.full, since, args.seen_name or str(args.seen), why)
    note = unsigned_line(Path(args.new), texts["new"])
    if note:
        table = f"> {note}\n\n{table}"
    if args.out and Path(args.out).suffix.lower() == ".xlsx":  # a Sheet on Drive, never Markdown under that name
        workbook(table, Path(args.out))
    elif args.out:
        Path(args.out).write_text(table, encoding="utf-8")
        print(json.dumps({"changelog": args.out, "rows": len(rows), "why_from_comments": sum(1 for w in why if w),
                          **({"since_seen": {k: since.count(k) for k in ("new", "changed", "same")}} if since else {})},
                         ensure_ascii=False))
    else:
        sys.stdout.write(table)
    return 0


def workbook(table: str, path: Path) -> int:
    """The changelog as a real workbook, for a release that uploads it as a Google Sheet: the lines above the table
    as notes on top of the Changes sheet, the table's rows under its header, and the record behind each row on a
    sheet of its own. The number of rows written."""
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    def clean(text: str) -> str:
        return ILLEGAL_CHARACTERS_RE.sub("", text.replace("\\|", "|").strip())
    book = Workbook()
    sheet = book.active
    sheet.title = "Changes"
    record = book.create_sheet("Record")
    lines, rows, part = table.splitlines(), 0, "notes"
    for line in lines:
        if line.startswith("## The record behind each row"):
            part = "record"
            continue
        if part == "record":
            if line.strip():
                record.append([clean(line.lstrip("- "))])
            continue
        if line.startswith("|") and not re.fullmatch(r"\|(?:-+\|)+", line.strip()):
            sheet.append([clean(c) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))])
            rows += 1
        elif line.strip() and not line.startswith("|"):
            sheet.append([clean(line.lstrip("#> "))])
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)
    return max(rows - 1, 0)


def unsigned_line(path: Path, found: Any) -> str:
    """How many of the master's marked passages no person has signed off, for the co-authors."""
    rm = rev_marks()
    try:
        people = rm.load_people(path)
    except rm.ConfigError as exc:
        raise Failure(str(exc)) from None
    open_ = rm.unreviewed(found, people)
    total = len(found.segments)
    return (f"{len(open_)} of {total} marked passages were last written by an AI or agent, with no person's sign-off "
            f"recorded since: nobody has put their name to that wording yet. A co-author's resolved comment or "
            f"accepted suggestion records theirs (comments.py signoffs).") if total else ""


def signoffs(args: argparse.Namespace) -> int:
    """A co-author who resolved a thread, or whose suggested edit was taken, has seen that passage: their handle
    goes into the `by=` of the segments that answer it, so the count of passages with no person's sign-off falls as
    people actually read them."""
    rm = rev_marks()
    ledger = Path(args.ledger)
    data = read_ledger(ledger)
    path = Path(args.new)
    if not path.is_file():
        raise Failure(f"{path}: cannot read the next round's master.", 3)
    found = Master(path).marks
    if found.errors:
        raise Failure(f"{path}: its revision marks do not lint (rev_marks.py lint).")
    try:
        people = rm.load_people(path)
    except rm.ConfigError as exc:
        raise Failure(str(exc)) from None
    plan, skipped = [], []
    for item in data["items"]:
        if item.get("resolved") is True and item.get("resolved_by"):
            signer, because = str(item["resolved_by"]), f"resolved {item['id']}"
            on = str(item.get("resolved_on") or "")[:10]  # the day they resolved it, not the day this ran
        elif item.get("kind") == "suggestion" and item.get("status") == "addressed" and item.get("by"):
            signer, because, on = str(item["by"]), f"suggested edit {item['id']} taken", ""
        else:
            continue
        if signer.startswith("[ai") or people.known(signer) != rm.Kind.HUMAN:
            skipped.append({"item": item["id"], "by": signer, "why": "not a person in rev-marks.toml"})
            continue
        handle = people.canonical(signer)
        now = " ".join(str(item.get("now") or "").split())
        segments = [s for s in found.segments if rm.comment_of(s.id) == item["id"]
                    or (now and now in rm.own_text(found, s))]
        if not segments:
            skipped.append({"item": item["id"], "by": handle, "why": "no marked passage answers it"})
        done = {(x.get("segment"), x.get("by")) for x in item.get("signed") or [] if isinstance(x, dict)}
        for s in segments:
            # Once per person and segment, whoever wrote after them since: the ledger keeps what was signed.
            if (s.id, handle) in done or people.canonical(s.last) == handle \
                    or any(p["segment"] == s.id and p["by"] == handle for p in plan):
                continue
            plan.append({"segment": s.id, "by": handle, "because": because, "item": item["id"],
                         "on": on or date.today().isoformat()})
    before = len(rm.unreviewed(found, people))
    text = found.text
    if args.go:
        for step in plan:
            text = rm.bump_segment(text, step["segment"], rm.Entry(step["by"], date.fromisoformat(step["on"])),
                                   found.syntax)
        path.write_bytes(text.encode("utf-8"))
        by_item = {item["id"]: item for item in data["items"]}
        for step in plan:
            by_item[step["item"]].setdefault("signed", []).append(
                {"segment": step["segment"], "by": step["by"], "on": step["on"]})
        if plan:
            write_ledger(ledger, data)
    after = len(rm.unreviewed(rm.parse(text, found.syntax), people))
    print(json.dumps({"master": path.as_posix(), "dry_run": not args.go, "signoffs": plan, "skipped": skipped,
                      "unsigned_before": before, "unsigned_after": after if args.go else None,
                      "of": len(found.segments)}, indent=2, ensure_ascii=False))
    return 0


def run(args: argparse.Namespace) -> int:
    if args.command == "changelog":
        return changelog(args)
    if args.command == "signoffs":
        return signoffs(args)
    ledger = Path(args.ledger)
    if args.command in ("import", "import-gdoc", "add"):
        source = Path(args.source)
        found = (read_docx(source) if args.command == "import" else
                 read_gdoc(source, args.tab) if args.command == "import-gdoc" else from_items(source))
        data = read_ledger(ledger)
        master_path = Path(args.master) if args.master else (ledger.parent / data["master"] if data.get("master") else None)
        master = Master(master_path) if master_path else None
        # A Doc's commenters are people; items written by hand (add) may carry any author, a workbook among them.
        people = commenters(found, master_path or ledger.parent) if args.command != "add" and args.people \
            else {"handles": {}, "people": [], "config": None}
        result = merge(ledger, found, master, args.round, args.doc, Path(args.source).name, people["handles"])
        if people["people"]:
            result["people"], result["rev_marks"] = people["people"], people["config"]
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    data = read_ledger(ledger)
    if not data["items"] and not ledger.exists():
        raise Failure(f"{ledger}: no ledger; pull the comments first (comments.py import).", 3)
    if args.new and not Path(args.new).is_file():
        raise Failure(f"{args.new}: cannot read the new round's master.", 3)
    rows = assess(data, Masters(data, ledger, Path(args.old) if args.old else None, Path(args.new) if args.new else None))
    if args.command == "gaps":
        return gaps(args, ledger, data, rows)
    if args.command == "status":
        problems = sum(len(r["problems"]) for r in rows)
        if args.json:
            print(json.dumps({"round": data.get("round"), "items": rows}, indent=2, ensure_ascii=False))
        else:
            counts: dict[str, int] = {}
            for item in data["items"]:
                counts[item.get("status", "open")] = counts.get(item.get("status", "open"), 0) + 1
            print(f"v{data.get('round')}: {len(rows)} comments and suggestions; "
                  + ", ".join(f"{n} {s}" for s, n in counts.items()))
            for item, row in zip(data["items"], rows):
                place = f" [{row['change']}]" if row["change"] else ""
                print(f"{item['id']}{place} {item.get('author', '')}: {first_line(item.get('comment', ''))}")
                for p in row["problems"]:
                    print(f"  problem: {p}")
                for h in row["hints"]:
                    print(f"  check: {h}")
        return 1 if args.strict and problems else 0
    untriaged = bool(getattr(args, "untriaged", False))
    if untriaged:  # a pull shown before triage: an open comment has no answer yet, and says so
        for item, row in zip(data["items"], rows):
            if item.get("status", "open") == "open":
                row["problems"] = [p for p in row["problems"] if not p.startswith("open needs next")]
    missing = [f"{r['id']}: {p}" for r in rows for p in r["problems"]]
    if missing:
        print("The ledger must say how each comment was handled before the dashboard can show it:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1
    next_round = args.next_round or (new_round(args.new) if args.new else None)
    if next_round == str(data.get("round")):  # --new is this round's own master: there is no next round yet
        next_round = None
    document, digest = findings(data, rows, next_round, ledger)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out.parent / "comments.md").write_text(digest, encoding="utf-8")
    print(json.dumps({"findings": out.as_posix(), "open": len(document["findings"]),
                      "items": len(document["coauthors"]["items"])}, ensure_ascii=False))
    return 0


def new_round(path: str) -> str | None:
    name = Path(path).resolve().parent.name
    return name[1:] if re.fullmatch(r"v\d[\w.-]*", name) else None


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    for name, source in (("import", "the Doc exported as .docx"),
                         ("import-gdoc", "the Google Docs connector's read_doc answer (commentsIncluded), saved as JSON"),
                         ("add", "a YAML list of items from a connector's text view")):
        s = sub.add_parser(name, help=f"merge {source} into the round's ledger")
        s.add_argument("source", help=source)
        s.add_argument("--ledger", required=True, help="the round's comments.yaml (created when missing)")
        s.add_argument("--master", help="the round's master, to find each anchor (default: the ledger's master)")
        s.add_argument("--round", help="the round's name, e.g. 0.5 (default: from the folder, v0.5)")
        s.add_argument("--doc", help="the Doc's link, recorded with the pull")
        if name == "import-gdoc":
            s.add_argument("--tab", help="the Doc tab's id (default: the first tab)")
        if name != "add":
            s.add_argument("--no-people", dest="people", action="store_false",
                           help="do not record the Doc's commenters as people in rev-marks.toml")
    for name, about in (("status", "how the next round answers each comment"),
                        ("findings", "the stage's findings.json and comments.md for the dashboard"),
                        ("gaps", "whether the run that produced the round had caught each comment")):
        s = sub.add_parser(name, help=about)
        s.add_argument("ledger")
        s.add_argument("--old", help="the round the comments were left on (default: the ledger's master)")
        s.add_argument("--new", help="the next round's master")
        if name == "status":
            s.add_argument("--json", action="store_true")
            s.add_argument("--strict", action="store_true", help="exit 1 on any problem in the ledger")
        elif name == "gaps":
            s.add_argument("--inventory", required=True,
                           help="the run's findings.json, or the dashboard it rendered (its .html carries the same records)")
            s.add_argument("--merge", help="a YAML file of gap records to merge into the ledger, checked first")
            s.add_argument("--check", action="store_true", help="check the ledger's gap records; exit 1 on a problem")
            s.add_argument("--strict", action="store_true",
                           help="with --check, exit 1 while a comment is not judged (one not on point needs no verdict)")
            s.add_argument("--all", action="store_true", help="the worksheet lists judged comments too")
            s.add_argument("--out", help="write the worksheet here instead of printing it")
        else:
            s.add_argument("--out", required=True, help="RUN/manuscript-coauthors/findings.json")
            s.add_argument("--next-round", help="the next round's name (default: from --new's folder)")
            s.add_argument("--untriaged", action="store_true",
                           help="accept open comments with no `next` yet (a pull shown before triage)")
    s = sub.add_parser("signoffs", help="record co-authors' resolved threads and taken suggestions as their sign-off")
    s.add_argument("ledger")
    s.add_argument("--new", required=True, help="the next round's marked master, whose segments get the names")
    s.add_argument("--go", action="store_true", help="write the names into the master; without it, only print")
    s = sub.add_parser("changelog", help="the round's changelog skeleton, Why filled from the comments it answers")
    s.add_argument("--base", required=True, help="the previous round's master as it was when this round opened")
    s.add_argument("--new", required=True, help="this round's master")
    s.add_argument("--seen", help="this round as the co-authors last saw it (a circulated commit)")
    s.add_argument("--ledger", action="append", default=[], help="a comments.yaml whose ids the marks name; repeat")
    s.add_argument("--full", action="store_true", help="whole passages in the cells")
    s.add_argument("--out", help="write the table here instead of printing it")
    for name in ("base", "new", "seen"):
        s.add_argument(f"--{name}-name", help=f"how the table names --{name} (e.g. v0.5)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return run(args)
    except Failure as exc:
        print(str(exc), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 whatever the console's code page (Windows)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
