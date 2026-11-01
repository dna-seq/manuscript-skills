# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Co-authors' comments on a round of the manuscript: the ledger that keeps them, and how the next round
answers each one (manuscript-coauthors).

    uv run --script comments.py import EXPORT.docx --ledger v0.5/comments.yaml [--master v0.5/PAPER.md] [--doc URL]
    uv run --script comments.py add ITEMS.yaml --ledger v0.5/comments.yaml [--master ...] [--doc URL]
    uv run --script comments.py status v0.5/comments.yaml [--old v0.5/PAPER.md] [--new v0.6/PAPER.md] [--json] [--strict]
    uv run --script comments.py findings v0.5/comments.yaml --new v0.6/PAPER.md --out RUN/manuscript-coauthors/findings.json
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

`import` also records who commented: each commenter's name is mapped to a handle (manuscript-mark-people's
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
import importlib.util
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

    def key_of(f: Found) -> str:  # an item of another Doc of the round is known within that Doc
        return f"{own_master}|{f.key}" if own_master else f.key
    ids = used_ids(ledger_path, master) | {item["id"] for item in data["items"]}
    numbers = {"comment": next_number(ids, "C"), "suggestion": next_number(ids, "S")}
    added = 0
    for f in found:
        item = by_key.get(key_of(f))
        if item is None:
            letter = "C" if f.kind == "comment" else "S"
            item = {"id": f"{letter}{numbers[f.kind]}", "kind": f.kind, "author": f.author, "date": f.date,
                    "key": key_of(f)}
            numbers[f.kind] += 1
            data["items"].append(item)
            added += 1
        if own_master:
            item["master"] = own_master
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
        if master is not None:
            span = master.locate(f.anchor, f.before, f.after)
            item["where"], item["line"] = master.where(span) if span else ("", None)
        for key, default in (("status", "open"), ("now", ""), ("why", ""), ("next", "")):
            item.setdefault(key, default)
    known = {key_of(f) for f in found}
    # This pull speaks only for its own Doc: the comments of the round's other Docs are neither gone nor reordered.
    gone = [item["id"] for item in data["items"] if item.get("master") == own_master and item.get("key") not in known]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data.setdefault("sources", []).append({k: v for k, v in {"doc": doc, "file": source_file, "pulled": stamp,
                                                             "items": len(found), "new": added}.items() if v is not None})
    order = {key_of(f): n for n, f in enumerate(found)}
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
    while hi - lo < 6 and (lo > first or hi < last):
        lo, hi = max(first, lo - 1), min(last, hi + 1)
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


def findings(data: dict[str, Any], rows: list[dict[str, Any]], next_round: str | None, ledger: Path) -> tuple[dict, str]:
    """The stage's findings.json and the digest (comments.md) its evidence quotes."""
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
                "action": " ".join(str(item.get("next", "")).split()),
                "severity": item.get("severity") or "minor", "stage": item.get("stage") or "writing",
                "confidence": "confirmed", "decision": bool(item.get("decision", False)),
                "evidence": [{"path": "comments.md", "quote": head}]})
        if row["change"] == "not-located":
            not_checked.append({"check": f"where {item['id']} sits in the manuscript",
                                "why": "the text it was attached to in the Doc was not found in the master",
                                "leaves_open": "whether the commented passage changed"})
        items.append({
            "id": item["id"], "kind": item.get("kind", "comment"), "author": item.get("author", ""),
            "date": str(item.get("date", "")), "where": item.get("where") or "", "anchor": item.get("anchor", ""),
            "comment": item.get("comment", ""), "replies": item.get("replies", []),
            "edits": [{"deleted": e.get("deleted", ""), "inserted": e.get("inserted", "")} for e in item.get("edits", [])],
            "resolved": item.get("resolved"), "status": status, "change": row["change"],
            "before": row["before"], "after": row["after"], "now": item.get("now", "") or "",
            "why": item.get("why", "") or "", "next": item.get("next", "") or "",
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
    for item, row in zip(data["items"], rows):
        if item.get("gap") and not every:
            continue
        found = candidates(item, row, inventory)
        lines += [f"## {item['id']} ({item.get('author', '?')}, {item.get('kind', 'comment')}, {item.get('status', 'open')})"
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
    return "\n".join(lines).rstrip() + "\n"


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
    gaps = [item["gap"] for item in data["items"] if item.get("gap")]
    count = lambda key: dict(sorted(((k, sum(1 for g in gaps if (g.get(key) or "") == k)) for k in
                                     {str(g.get(key) or "") for g in gaps} if k), key=lambda kv: -kv[1]))
    return {"judged": len(gaps), "by_verdict": {v: sum(g["verdict"] == v for g in gaps) for v in GAP_VERDICTS},
            "miss_reasons": count("miss_reason"), "by_owner": count("owner")}


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
    if args.out:
        Path(args.out).write_text(table, encoding="utf-8")
        print(json.dumps({"changelog": args.out, "rows": len(rows), "why_from_comments": sum(1 for w in why if w),
                          **({"since_seen": {k: since.count(k) for k in ("new", "changed", "same")}} if since else {})},
                         ensure_ascii=False))
    else:
        sys.stdout.write(table)
    return 0


def run(args: argparse.Namespace) -> int:
    if args.command == "changelog":
        return changelog(args)
    ledger = Path(args.ledger)
    if args.command in ("import", "add"):
        found = read_docx(Path(args.source)) if args.command == "import" else from_items(Path(args.source))
        data = read_ledger(ledger)
        master_path = Path(args.master) if args.master else (ledger.parent / data["master"] if data.get("master") else None)
        master = Master(master_path) if master_path else None
        # A Doc's commenters are people; items written by hand (add) may carry any author, a workbook among them.
        people = commenters(found, master_path or ledger.parent) if args.command == "import" and args.people \
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
    missing = [f"{r['id']}: {p}" for r in rows for p in r["problems"]]
    if missing:
        print("The ledger must say how each comment was handled before the dashboard can show it:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1
    document, digest = findings(data, rows, args.next_round or (new_round(args.new) if args.new else None), ledger)
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
    for name, source in (("import", "the Doc exported as .docx"), ("add", "a YAML list of items from a connector's text view")):
        s = sub.add_parser(name, help=f"merge {source} into the round's ledger")
        s.add_argument("source", help=source)
        s.add_argument("--ledger", required=True, help="the round's comments.yaml (created when missing)")
        s.add_argument("--master", help="the round's master, to find each anchor (default: the ledger's master)")
        s.add_argument("--round", help="the round's name, e.g. 0.5 (default: from the folder, v0.5)")
        s.add_argument("--doc", help="the Doc's link, recorded with the pull")
        if name == "import":
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
