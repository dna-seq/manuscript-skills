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

`import` reads a Google Doc exported as .docx (rclone `--drive-export-formats docx`, a Drive connector's
download with exportMimeType docx, or File > Download > Microsoft Word). Google writes each comment and each
reply as a Word comment on the same range, with no thread record, a comment over several ranges as one copy
per range, and suggested edits as tracked insertions and deletions; it does not say whether a thread was
resolved. So: copies are merged, a comment on exactly the range of an earlier one is its reply, and the
suggested edits of one person in one paragraph are one item. `add` takes items written from a connector's
text view (a YAML list of author, date, anchor, comment, and optionally context_before, context_after,
replies, kind, edits, resolved) and merges them the same way.

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
                 "# answers it, verbatim. why: what was done and why, or why not. next: what could still be done.\n")


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
          doc: str | None, source_file: str | None) -> dict[str, Any]:
    data = read_ledger(ledger_path)
    if round_name:
        data["round"] = str(round_name)
    elif "round" not in data:
        name = ledger_path.resolve().parent.name
        data["round"] = name[1:] if re.fullmatch(r"v\d[\w.-]*", name) else name
    if master is not None and "master" not in data:
        data["master"] = Path(master.path).resolve().relative_to(ledger_path.resolve().parent).as_posix() \
            if Path(master.path).resolve().is_relative_to(ledger_path.resolve().parent) else str(master.path)
    by_key = {item.get("key"): item for item in data["items"]}
    ids = used_ids(ledger_path, master) | {item["id"] for item in data["items"]}
    numbers = {"comment": next_number(ids, "C"), "suggestion": next_number(ids, "S")}
    added = 0
    for f in found:
        item = by_key.get(f.key)
        if item is None:
            letter = "C" if f.kind == "comment" else "S"
            item = {"id": f"{letter}{numbers[f.kind]}", "kind": f.kind, "author": f.author, "date": f.date,
                    "key": f.key}
            numbers[f.kind] += 1
            data["items"].append(item)
            added += 1
        item.update({"anchor": f.anchor, "context_before": " ".join(f.before.split()[-CONTEXT_WORDS:]),
                     "context_after": " ".join(f.after.split()[:CONTEXT_WORDS]), "comment": f.comment})
        if f.edits:
            item["edits"] = f.edits
        if f.replies or "replies" in item:
            item["replies"] = f.replies
        if f.resolved is not None:
            item["resolved"] = f.resolved
        if master is not None:
            span = master.locate(f.anchor, f.before, f.after)
            item["where"], item["line"] = master.where(span) if span else ("", None)
        for key, default in (("status", "open"), ("now", ""), ("why", ""), ("next", "")):
            item.setdefault(key, default)
    known = {f.key for f in found}
    gone = [item["id"] for item in data["items"] if item.get("key") not in known]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data.setdefault("sources", []).append({k: v for k, v in {"doc": doc, "file": source_file, "pulled": stamp,
                                                             "items": len(found), "new": added}.items() if v is not None})
    order = {f.key: n for n, f in enumerate(found)}
    data["items"].sort(key=lambda i: (order.get(i.get("key"), len(order)), i["id"]))
    ordered = {k: data[k] for k in ("round", "master", "sources", "items") if k in data}
    write_ledger(ledger_path, ordered | {k: v for k, v in data.items() if k not in ordered})
    return {"ledger": ledger_path.as_posix(), "round": data["round"], "items": len(data["items"]), "new": added,
            "not_in_this_pull": gone,
            "not_located": [i["id"] for i in data["items"] if master is not None and i.get("line") is None
                            and i.get("key") in known]}


# --- the next round's answer ----------------------------------------------------------------------------


def assess(data: dict[str, Any], old: Master | None, new: Master | None) -> list[dict[str, Any]]:
    """Each item with where its passage went in the new round, and the ledger's problems with it."""
    rm = rev_marks()
    ops = rm.align(old.blocks, new.blocks)[2] if old and new else None
    out = []
    for item in data["items"]:
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


def masters(data: dict[str, Any], ledger: Path, old: Path | None, new: Path | None) -> tuple[Master | None, Master | None]:
    if old is None and data.get("master"):
        old = (ledger.parent / data["master"]) if not Path(data["master"]).is_absolute() else Path(data["master"])
    return (Master(old) if old else None), (Master(new) if new else None)


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
            "rev_ids": row["rev_ids"] or list(item.get("rev_ids", [])), "finding_ids": finding_ids})
    document = {"skill": "manuscript-coauthors", "findings": out, "changes": [], "dismissed": [],
                "not_checked": not_checked,
                "coauthors": {"round": str(data.get("round", "")), "next_round": next_round,
                              "source": ledger.name, "items": items}}
    return document, "\n".join(lines).rstrip() + "\n"


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
        result = merge(ledger, found, master, args.round, args.doc, Path(args.source).name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    data = read_ledger(ledger)
    if not data["items"] and not ledger.exists():
        raise Failure(f"{ledger}: no ledger; pull the comments first (comments.py import).", 3)
    old, new = masters(data, ledger, Path(args.old) if args.old else None, Path(args.new) if args.new else None)
    rows = assess(data, old, new)
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
    for name, about in (("status", "how the next round answers each comment"),
                        ("findings", "the stage's findings.json and comments.md for the dashboard")):
        s = sub.add_parser(name, help=about)
        s.add_argument("ledger")
        s.add_argument("--old", help="the round the comments were left on (default: the ledger's master)")
        s.add_argument("--new", help="the next round's master")
        if name == "status":
            s.add_argument("--json", action="store_true")
            s.add_argument("--strict", action="store_true", help="exit 1 on any problem in the ledger")
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
