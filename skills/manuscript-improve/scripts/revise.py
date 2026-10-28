# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "markdown-it-py>=3"]
# ///
"""Build the corrected version of a manuscript from a run: the edits applied, then every proposal.

    uv run --script revise.py ORIGINAL WORKING RUN/manuscript-dashboard/findings.json \
        --choices RUN/manuscript-improve/revision-choices.json --output-dir RUN/manuscript-improve/revision \
        [--supplement-original SUP_ORIGINAL --supplement-working SUP_WORKING [--supplement-document NAME]]

ORIGINAL is the run's snapshot of the manuscript as it was before the workflow (RUN/inputs/01-paper.md, the copy
`runs.py start` made). WORKING is the working copy: the manuscript as it is now, with every applied edit. Where
the manuscript carries revision marks, give both as clean copies (`rev_marks.py strip ... --out`). INVENTORY is
the adjudicated findings.json from manuscript-dashboard. Each applied edit is located in the working copy, newest
first; undoing them must give the original exactly, so an edit nobody recorded stops the build. An applied edit
that a later recorded change restored (a reverse `runs.py change`, as for a widened claim) cancels out and is
listed as restored. The proposals are then applied in manuscript order to give the proposed version.

Proposals that rewrite the same passage are alternatives (the dashboard's competing groups, formed after
the held proposals are set aside). The choices file (revision-choices.json) names the ones to use from each
group ("prefer"; two from one group only when they change different words), the proposals held back with the
reason shown to the authors ("hold": a statement that waits for the journal choice, a decision only the authors
can make, a proposal whose claim widened) and an anchor for an addition that lacks one. Every key is optional:

    {"prefer": ["ST-C3"],
     "hold": [{"id": "JA-C18", "why": "Waits for the choice of journal."},
              {"id": "ST-C7", "why": "widened claim, wording restored"}],
     "anchor": [{"id": "JA-C1", "after": "verbatim passage the addition follows"}]}

A proposal is applied only where its before-text, or an addition's anchor, occurs exactly once in the
working copy and does not overlap another proposal; one that still has a gap for a fact only the authors
have waits for their answer. Every proposal not applied is listed with its reason.

Outputs, named after the manuscript's own extension (`.tex` for a LaTeX manuscript): revised.tex or revised.md
(the working copy), proposed.tex or proposed.md (every chosen proposal applied: the corrected version),
changes.md (the same as CriticMarkup against the original, each change named by its section and summary with
its ID in parentheses, and the questions for the authors as comments) and revision.json: what was applied,
restored, held, left as an alternative or not placed, the questions for the authors, the notes still in the
text, and the track-changes view that manuscript-dashboard shows in the dashboard's Corrected version tab. An
existing output folder is refused; the message names the next attempt (revision.2).

A change to another file than the manuscript names it (`document`, from `runs.py change --document`), and the
manuscript's corrected version leaves it alone. Given the supplement's reviewed text and working copy (clean, like
the manuscript's), the supplement gets its own corrected version from its own changes, by the same rules and the
same choices file: supplement-revised, supplement-proposed and supplement-changes.md beside the manuscript's, and
`supplement` in revision.json with the same lists. Without them, the supplement's changes are only listed
(`other_files`).

No note to the authors goes into the text. A question comes as a proposal's `comment`; a `[AUTHORS: ...]` note
a stage left in a proposal's text is lifted out of it and becomes a comment too, so the corrected version
never carries one; so does a note that came with an applied edit. Two lists remain: `notes_in_working_copy`,
the notes the run's applied edits left in the working copy (remove each there with a recorded runs.py change),
and `notes_in_text`, the notes the authors' own draft has, listed for them and never removed by the run.
"""
from __future__ import annotations

import difflib
import hashlib
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "manuscript-dashboard" / "scripts"))
import dashboard as viz  # noqa: E402

TOKEN = re.compile(r"\s+|\w+|[^\w\s]")
BLOCK = re.compile(r"\n|^(?:#{1,6}\s|\||[-*+]\s|\d+[.)]\s|\*\*)")
MARKERS = re.compile(r"[ \t]*(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+[.)][ \t]+|>[ \t]?)*")
OPEN = {"del": ("\ue000", "\ue001"), "ins": ("\ue002", "\ue003")}
CLOSE = {"del": "\ue004", "ins": "\ue005"}
app = typer.Typer(add_completion=False)


@dataclass
class Piece:
    """Unchanged text, or an edit: `old` from the original, `base` in the working copy (the applied edits
    only), `new` in the version being built."""
    text: str = ""
    old: str = ""
    new: str = ""
    base: str = ""
    ids: list[str] = field(default_factory=list)
    status: str = "text"

    @property
    def current(self) -> str:
        return self.text if self.status == "text" else self.new

    @property
    def previous(self) -> str:
        return self.text if self.status == "text" else self.old

    @property
    def working(self) -> str:
        return self.text if self.status == "text" else self.base


def trim(before: str, after: str) -> tuple[int, int]:
    """Characters of whole words the two texts share at the start and at the end: an edit covers only the rest,
    so a later proposal for a neighbouring phrase of the same sentence is not mistaken for an overlap."""
    a, b = TOKEN.findall(before), TOKEN.findall(after)
    prefix = 0
    while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
        prefix += 1
    suffix = 0
    while suffix < min(len(a), len(b)) - prefix and a[-1 - suffix] == b[-1 - suffix]:
        suffix += 1
    return len("".join(a[:prefix])), len("".join(a[len(a) - suffix:]))


class Unplaced(Exception):
    """A change the text cannot take; the message is the reason shown to the authors."""


class Document:
    """The manuscript as pieces, readable in three versions: the original (`previous`), the working copy with
    the applied edits (`working`) and the version being built (`current`). Proposals are located in the
    working copy, as their stages wrote them, so two proposals that change different words of one sentence
    both apply."""

    def __init__(self, text: str) -> None:
        self.pieces = [Piece(text=text)]

    def current(self) -> str:
        return "".join(p.current for p in self.pieces)

    def previous(self) -> str:
        return "".join(p.previous for p in self.pieces)

    def working(self) -> str:
        return "".join(p.working for p in self.pieces)

    def find(self, needle: str) -> int:
        text = self.working()
        if (count := text.count(needle)) != 1:
            raise Unplaced("its passage is not in the working copy" if not count else f"its passage occurs {count} times")
        return text.index(needle)

    def propose(self, start: int, end: int, new: str, cid: str) -> None:
        """Replace [start, end) of the working copy with `new`. Inside unchanged text it becomes its own edit; a
        range that takes in an applied edit (a proposal written on the working copy, around a routine fix) joins
        it; a range that touches another proposal is not placed."""
        bounds, offset = [], 0
        for piece in self.pieces:
            bounds.append((offset, offset + len(piece.working)))
            offset += len(piece.working)
        if start == end:
            # At a boundary an insertion goes after any earlier insertion there, so additions keep their order.
            spots = [i for i, (a, b) in enumerate(bounds) if a <= start <= b and self.pieces[i].status == "text"]
            touched = spots[-1:] or [i for i, (a, b) in enumerate(bounds) if a < start < b]
            if not touched:
                if start != offset:
                    raise Unplaced("its passage is not in the working copy")
                self.pieces.append(Piece(text=""))
                touched = [len(self.pieces) - 1]
                bounds.append((offset, offset))
        else:
            touched = [i for i, (a, b) in enumerate(bounds) if a < end and start < b]
        if not touched:
            raise Unplaced("its passage is not in the working copy")
        if rivals := [x for i in touched if self.pieces[i].status == "proposed" for x in self.pieces[i].ids]:
            raise Unplaced(f"it overlaps {', '.join(dict.fromkeys(rivals))}")
        first, last = touched[0], touched[-1]
        if first == last and self.pieces[first].status == "text":
            text, at = self.pieces[first].text, start - bounds[first][0]
            segment = text[at:at + end - start]
            self.pieces[first:first + 1] = [p for p in (
                Piece(text=text[:at]), Piece(old=segment, base=segment, new=new, ids=[cid], status="proposed"),
                Piece(text=text[at + end - start:])) if p.status != "text" or p.text]
            return
        lo = start if self.pieces[first].status == "text" else bounds[first][0]
        hi = end if self.pieces[last].status == "text" else bounds[last][1]
        old, base = [], []
        for i in range(first, last + 1):
            piece, (a, b) = self.pieces[i], bounds[i]
            if piece.status == "text":
                part = piece.text[max(lo, a) - a:min(hi, b) - a]
                old.append(part)
                base.append(part)
            else:
                old.append(piece.old)
                base.append(piece.base)
        working = "".join(base)
        merged = Piece(old="".join(old), base=working, new=working[:start - lo] + new + working[end - lo:],
                       ids=[*(x for i in range(first, last + 1) for x in self.pieces[i].ids), cid], status="proposed")
        lead = Piece(text=self.pieces[first].text[:lo - bounds[first][0]]) if self.pieces[first].status == "text" else None
        rest = Piece(text=self.pieces[last].text[hi - bounds[last][0]:]) if self.pieces[last].status == "text" else None
        self.pieces[first:last + 1] = [p for p in (lead, merged, rest) if p is not None and (p.status != "text" or p.text)]

    def undo(self, before: str, after: str, cid: str) -> None:
        """Mark an applied edit, newest first: its after-text is found in the text as it stood before the later
        edits, and the words it changed become an edit. An edit a later stage changed again joins that edit."""
        text = self.previous()
        if (count := text.count(after)) != 1:
            raise Unplaced("its text is not in the working copy" if not count else f"its text occurs {count} times")
        head, tail = trim(before, after)
        start = text.index(after) + head
        self.mark(start, start + len(after) - head - tail, before[head:len(before) - tail], cid)

    def undo_deletion(self, before: str, original: str, cid: str) -> None:
        """Mark an applied deletion: the deleted text is found in the original, and its place in the text as it
        stood before the later edits by the words around it (a space the deletion took with it allowed for)."""
        if (count := original.count(before)) != 1:
            raise Unplaced("its deleted text is not in the original" if not count else f"its deleted text occurs {count} times in the original")
        text, at = self.previous(), original.index(before)
        for width in (80, 40, 20, 10):
            left, right = original[max(0, at - width):at], original[at + len(before):at + len(before) + width]
            for lead, rest in ((left, right), (left.rstrip(), right), (left, right.lstrip()), (left.rstrip(), right.lstrip())):
                if lead + rest and text.count(lead + rest) == 1:
                    spot = text.index(lead + rest) + len(lead)
                    self.mark(spot, spot, left[len(lead):] + before + right[:len(right) - len(rest)], cid)
                    return
        raise Unplaced("the place it was deleted from could not be found in the working copy")

    def mark(self, start: int, end: int, old: str, cid: str) -> None:
        """Turn [start, end) of the text as it stood before the later edits into an applied edit whose original
        text was `old`; an edit a later stage changed again joins that edit."""
        text = self.previous()
        bounds, offset = [], 0
        for piece in self.pieces:
            bounds.append((offset, offset + len(piece.previous)))
            offset += len(piece.previous)
        if start == end:
            touched = [i for i, (a, b) in enumerate(bounds) if a <= start <= b and self.pieces[i].status == "text"][:1] \
                or [i for i, (a, b) in enumerate(bounds) if a < start < b]
        else:
            touched = [i for i, (a, b) in enumerate(bounds) if a < end and start < b]
        first, last = touched[0], touched[-1]
        lo = start if self.pieces[first].status == "text" else bounds[first][0]
        hi = end if self.pieces[last].status == "text" else bounds[last][1]
        current = []
        for i in range(first, last + 1):
            piece, (a, b) = self.pieces[i], bounds[i]
            current.append(piece.text[max(lo, a) - a:min(hi, b) - a] if piece.status == "text" else piece.new)
        merged = Piece(old=text[lo:start] + old + text[end:hi], new="".join(current),
                       base="".join(current), ids=[cid, *(x for i in range(first, last + 1) for x in self.pieces[i].ids)],
                       status="applied")
        lead = Piece(text=self.pieces[first].text[:lo - bounds[first][0]]) if self.pieces[first].status == "text" else None
        rest = Piece(text=self.pieces[last].text[hi - bounds[last][0]:]) if self.pieces[last].status == "text" else None
        self.pieces[first:last + 1] = [p for p in (lead, merged, rest) if p is not None and (p.status != "text" or p.text)]


def first_difference(a: str, b: str) -> str:
    for number, (x, y) in enumerate(zip(a.splitlines(), b.splitlines()), 1):
        if x != y:
            return f"line {number}: {x[:120]!r} against {y[:120]!r}"
    return "a different number of lines"


# A reference entry: an author-year citation's year in parentheses near its start, or a DOI.
REFERENCE_ENTRY = re.compile(r"^.{0,300}?\((?:19|20)\d{2}[a-z]?\)|\bdoi(?:\.org/|:)\s*10\.", re.IGNORECASE | re.DOTALL)
REFERENCES_HEADING = re.compile(r"^#{1,6}\s.*\b(?:references|bibliography|literature cited|works cited)\b", re.IGNORECASE)


def in_references(text: str, at: int) -> bool:
    """Whether `at` sits under a references heading (the nearest heading above it names one)."""
    for line in reversed(text[:at].splitlines()):
        if line.lstrip().startswith("#"):
            return bool(REFERENCES_HEADING.match(line.strip()))
    return False


def insertion_point(text: str, anchor_end: int, addition: str) -> tuple[int, str]:
    """Where an addition goes and how it is joined. In a block of lines (a reference list, a table, a list) a
    line or lines go on new lines after the anchor's line; a reference entry added after another, in a list that
    keeps one entry per paragraph, is a paragraph of its own; a sentence follows its anchor in the paragraph; a
    heading, table, list or new paragraph goes after the anchor's paragraph."""
    addition = addition.strip()
    start = text.rfind("\n\n", 0, anchor_end)
    start = 0 if start < 0 else start + 2
    end = text.find("\n\n", anchor_end)
    end = len(text.rstrip("\n")) if end < 0 else end
    in_lines = "\n" in text[start:end].strip() and (anchor_end == end or text.startswith("\n", anchor_end))
    if in_lines and "\n\n" not in addition and not addition.startswith("#"):
        return anchor_end, "\n" + addition
    entry = REFERENCE_ENTRY.match(addition) and (in_references(text, start) or REFERENCE_ENTRY.match(text[start:end]))
    if entry and anchor_end == end:
        return end, "\n\n" + addition
    if not BLOCK.search(addition):
        return anchor_end, " " + addition
    return end, "\n\n" + addition


# A gap a proposal still holds once its notes are lifted: a placeholder in another form, or the empty brackets a
# lifted note leaves ("just-dna-seq ()."). Only what the passage did not already contain counts.
GAP = re.compile(r"\bAUTHORS\b|\b(?:TODO|TBD|FIXME)\b|\bX{2,}\b|\(\s*[,;]?\s*\)|\[\s*\]|"
                 r"(?i:\[(?:todo|tbd|tbc|insert|add|citation needed)\b[^\]]*\])")
# A note that filled a slot inside a sentence: after one of these words, or after a colon at the end of its line, the
# sentence cannot stand without the fact ("The authors used [AUTHORS: tool] to ...", "Correspondence: [AUTHORS: email]").
SLOT = re.compile(r"(?i:\b(?:of|for|by|with|using|used|use|the|a|an|to|in|on|at|from|as|and|or|is|are|was|were|be|been|"
                  r"via|than|named|called|version|model|tool|tools))\s*$")


def gaps(after: str, before: str) -> list[str]:
    found = []
    for match in GAP.finditer(after):
        if match.group(0) not in before:
            start, end = max(0, match.start() - 40), min(len(after), match.end() + 40)
            found.append(after[start:end].strip())
    return found


def slots(after: str) -> list[str]:
    """The notes in a proposal that stand where the sentence needs their fact, each with the words around it."""
    found = []
    for start, end in viz.author_notes(after):
        lead, rest = after[:start].rstrip(), after[end:]
        line_end = not rest.split("\n", 1)[0].strip(" .")
        if SLOT.search(lead) or (lead.endswith(":") and line_end):
            found.append((after[max(0, start - 40):start] + "…" + after[end:end + 40]).strip())
    return found


def lift(change: viz.Change) -> tuple[str, list[str]]:
    """A proposal's text without the notes to the authors a stage left in it, and its questions: those notes,
    then its comment. A note in the text could reach a submission; a comment cannot."""
    after = change.after or ""
    spans = viz.author_notes(after)
    asked = [re.sub(r"^\[AUTHORS:\s*|\]$", "", after[a:b]).strip() for a, b in spans]
    if spans:
        after = viz.strip_notes(after)
    return after, [*asked, *([change.comment.strip()] if change.comment.strip() else [])]


CHOICES_EXAMPLE = ('{"prefer": ["ST-C3"], "hold": [{"id": "ST-C7", "why": "widened claim, wording restored"}], '
                   '"anchor": [{"id": "JA-C1", "after": "verbatim passage the addition follows"}]}')
CHOICE_FIELDS = {"hold": ("id", "why"), "anchor": ("id", "after")}


def check_choices(choices: object, name: str = "The choices file") -> dict:
    """The choices file, checked: `prefer` a list of proposal IDs, `hold` a list of {id, why}, `anchor` a list of
    {id, after}. A wrong key or shape is a ValueError that says what the file should hold."""
    shape = f" It holds, for example: {CHOICES_EXAMPLE}"
    if not isinstance(choices, dict):
        raise ValueError(f"{name} must be a JSON object with the keys prefer, hold and anchor.{shape}")
    if unknown := sorted(set(choices) - {"prefer", *CHOICE_FIELDS}):
        raise ValueError(f"{name} has keys revise.py does not read: {', '.join(unknown)}; the keys are prefer, hold and anchor.{shape}")
    prefer = choices.get("prefer", [])
    if not isinstance(prefer, list) or not all(isinstance(x, str) and x.strip() for x in prefer):
        raise ValueError(f"{name}: prefer is a list of proposal IDs, such as [\"ST-C3\"].{shape}")
    for key, (first, second) in CHOICE_FIELDS.items():
        entries = choices.get(key, [])
        if not isinstance(entries, list):
            raise ValueError(f"{name}: {key} is a list of objects, each with {first} and {second}.{shape}")
        for number, entry in enumerate(entries, 1):
            if (not isinstance(entry, dict) or set(entry) != {first, second}
                    or not all(isinstance(entry[k], str) and entry[k].strip() for k in (first, second))):
                what = "the reason shown to the authors" if key == "hold" else "the verbatim passage the addition follows"
                raise ValueError(f"{name}: {key} entry {number} needs exactly {first} (the proposal's ID) and {second} "
                                 f"({what}), both non-empty; it has {json.dumps(entry, ensure_ascii=False)}.{shape}")
    return {"prefer": prefer, **{key: choices.get(key, []) for key in CHOICE_FIELDS}}


def build(original: str, working: str, data: viz.Inventory, choices: dict, document: str = "") -> tuple[Document, dict]:
    """The corrected version of one file: the manuscript (`document` "") or another input, a supplement, named as the
    inventory's changes name it."""
    choices = check_choices(choices)
    # A change to another file is not part of this file's corrected version: it is neither undone nor proposed here,
    # so a sentence the supplement repeats from the manuscript is never changed in the wrong copy.
    elsewhere = [c for c in data.changes if c.document != document]
    data = data.model_copy(update={"changes": [c for c in data.changes if c.document == document]})
    changes = {c.id: c for c in data.changes}
    proposals = {c.id: c for c in data.changes if c.status == "proposed"}
    # A choice about another file's change has nothing to choose here (a choices file written before changes named
    # their file held each supplement edit by hand).
    outside = {c.id for c in elsewhere}
    prefer = [cid for cid in choices["prefer"] if cid not in outside]
    held = {h["id"]: h["why"] for h in choices["hold"] if h["id"] not in outside}
    anchors = {a["id"]: a["after"] for a in choices["anchor"] if a["id"] not in outside}
    if unknown := sorted((set(prefer) | set(held) | set(anchors)) - set(proposals)):
        applied_ids = sorted(cid for cid in unknown if cid in changes)
        raise ValueError(f"The choices name changes that are not proposals in the inventory: {', '.join(unknown)}"
                         + (f". {', '.join(applied_ids)} are applied edits, which a choice cannot hold back; to take one "
                            "back, record the reverse change with runs.py change" if applied_ids else ""))
    if both := sorted(set(prefer) & set(held)):
        raise ValueError(f"Preferred and held at once: {', '.join(both)}")
    alternatives: dict[str, str] = {}
    unresolved = []
    # A held proposal is out of play, so it joins no group: a whole-Abstract rewrite for one journal, held
    # until the journal is chosen, does not make every edit inside the Abstract an alternative to the others.
    for group in viz.competing([c for c in data.changes if c.id not in held]):
        chosen = [cid for cid in group if cid in prefer]
        if chosen:
            alternatives |= {cid: ", ".join(chosen) for cid in group if cid not in chosen}
        else:
            unresolved.append(group)
    if unresolved:
        raise ValueError("Choose one proposal per passage (\"prefer\") or hold the group: "
                         + "; ".join(", ".join(group) for group in unresolved))

    document = Document(working)
    unplaced: dict[str, str] = {}
    applied = [c for c in data.changes if c.status == "applied"]
    for change in reversed(applied):  # newest first, so an edit a later stage changed again is still found
        try:
            if change.after is None:
                document.undo_deletion(change.before or "", original, change.id)
            else:
                document.undo(change.before or "", change.after, change.id)
        except Unplaced as reason:
            unplaced[change.id] = f"Applied edit not found in the working copy: {reason}."
    if document.previous() != original:
        raise ValueError("The working copy differs from the original outside the recorded applied edits, at "
                         f"{first_difference(document.previous(), original)}. Record every applied edit first.")
    # An applied edit and the recorded change that restored its wording (a widened claim put back) cancel out.
    restored = []
    for index, piece in enumerate(document.pieces):
        if piece.status == "applied" and piece.old == piece.new:
            restored.append({"ids": piece.ids, "why": "Applied, then its original wording was restored by a later recorded change."})
            document.pieces[index] = Piece(text=piece.new)
    document.pieces = [p for p in document.pieces if p.status != "text" or p.text]
    revised = document.current()

    def position(change: viz.Change) -> int:
        target = change.before or anchors.get(change.id) or change.anchor or ""
        return revised.find(target) if target else -1

    todo = [c for c in proposals.values() if c.id not in held and c.id not in alternatives]
    questions: dict[str, list[str]] = {}
    for change in sorted(todo, key=lambda c: (position(c) < 0, position(c))):
        after, asked = lift(change)
        if asked:
            questions[change.id] = asked
        if left := [*slots(change.after or ""), *gaps(after, change.before or "")]:
            questions[change.id] = [*asked, *(f'complete the passage it proposes: "{text}"' for text in left)]
        try:
            if left:
                raise Unplaced("its text still has a gap for a fact only the authors have; it waits for their answer, "
                               "and its questions are listed")
            if asked and after.strip() == (change.before or "").strip():
                raise Unplaced("without its notes to the authors it changes nothing: it only asks them, and its questions are listed")
            if change.before:
                if after == change.before:
                    raise Unplaced("its text is the same before and after: a move to another place is left to the authors")
                head, tail = trim(change.before, after)
                start = document.find(change.before) + head
                document.propose(start, start + len(change.before) - head - tail, after[head:len(after) - tail], change.id)
                continue
            anchor = anchors.get(change.id) or change.anchor
            if not anchor:
                raise Unplaced("an addition that names no anchor passage")
            start = document.find(anchor)
            at, addition = insertion_point(document.working(), start + len(anchor), after)
            document.propose(at, at, addition, change.id)
        except Unplaced as reason:
            unplaced[change.id] = str(reason)
    # A note to the authors that came with an applied edit leaves the corrected version as a comment; a note the
    # authors' own draft already had is theirs, and is listed below.
    for piece in document.pieces:
        if piece.status != "text" and (spans := viz.author_notes(piece.new)):
            asked = [re.sub(r"^\[AUTHORS:\s*|\]$", "", piece.new[a:b]).strip() for a, b in spans]
            questions[piece.ids[0]] = [*questions.get(piece.ids[0], []), *asked]
            piece.new = viz.strip_notes(piece.new)
    in_text = {cid for piece in document.pieces for cid in piece.ids}
    # The notes the applied edits brought into the working copy: those the original did not already have.
    own = [original[a:b] for a, b in viz.author_notes(original)]
    from_edits = []
    for a, b in viz.author_notes(revised):
        if revised[a:b] in own:
            own.remove(revised[a:b])
        else:
            from_edits.append({"note": revised[a:b], "line": revised.count("\n", 0, a) + 1})
    record = {
        "applied": [c.id for c in applied if c.id in in_text],
        "restored": restored,
        "proposed_in_this_version": [cid for cid in proposals if cid in in_text],
        "held": [{"id": cid, "why": why} for cid, why in held.items()],
        "alternatives": [{"id": cid, "chosen": chosen} for cid, chosen in alternatives.items()],
        "not_placed": [{"id": cid, "why": why} for cid, why in unplaced.items()],
        "comments": [{"ids": [cid], "question": question, "section": changes[cid].section, "placed": cid in in_text,
                      "passage": (changes[cid].before or anchors.get(cid) or changes[cid].anchor or "")[:400]}
                     for cid, asked in questions.items() for question in asked],
        # The authors' own draft notes: unchanged text keeps them, in the corrected version and in their manuscript.
        # They are the authors' to answer or remove; the run never deletes them. Lines are the corrected version's.
        "notes_in_text": [{"note": document.current()[a:b], "line": document.current().count("\n", 0, a) + 1}
                          for a, b in viz.author_notes(document.current())],
        # Notes the run's applied edits left in the working copy (lines of the working copy). The corrected version
        # has them as comments; each is removed from the working copy with a recorded runs.py change.
        "notes_in_working_copy": from_edits,
        "changes": {cid: {"section": c.section, "summary": c.summary, "kind": c.kind, "status": c.status,
                          "finding_ids": c.finding_ids} for cid, c in changes.items()},
        # Changes to the run's other files, each as the file holds it now: an applied one is in that file already.
        "other_files": [{"id": c.id, "document": c.document, "status": c.status, "section": c.section,
                         "summary": c.summary} for c in elsewhere],
    }
    return document, record


def word_diff(old: str, new: str) -> list[tuple[str, str]]:
    a, b = re.findall(r"\s+|\w+|[^\w\s]", old), re.findall(r"\s+|\w+|[^\w\s]", new)
    out: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(("equal", "".join(a[i1:i2])))
            continue
        if i2 > i1:
            out.append(("del", "".join(a[i1:i2])))
        if j2 > j1:
            out.append(("ins", "".join(b[j1:j2])))
    return out


def critic(document: Document, asked: dict[str, list[str]] | None = None,
           info: dict[str, tuple[str, str]] | None = None) -> str:
    """CriticMarkup against the original; each edit's comment names it by its section and summary, with its ID in
    parentheses, and carries its questions for the authors."""
    parts = []
    for piece in document.pieces:
        if piece.status == "text":
            parts.append(piece.text)
            continue
        questions = [q for cid in piece.ids for q in (asked or {}).get(cid, [])]
        names = "; ".join(f"{info[cid][0]}: {info[cid][1].rstrip('.')} ({cid})" if info and cid in info else cid for cid in piece.ids)
        note = "{>>" + names + "".join(f" · Question for the authors: {q}" for q in questions) + "<<}"
        if piece.old and piece.new:
            parts.append("{~~" + piece.old + "~>" + piece.new + "~~}" + note)
        elif piece.new:
            parts.append("{++" + piece.new + "++}" + note)
        else:
            parts.append("{--" + piece.old + "--}" + note)
    return "".join(parts)


def marked(document: Document) -> tuple[str, list[dict]]:
    """Markdown with each deleted and inserted run between private-use sentinels, kept inside one line and one
    table cell, after any heading or list marker, so the markup still parses and the tags stay balanced. A
    change inside a link's address shows the new address only."""
    out: list[str] = []
    edits = []

    def emit(kind: str, text: str, number: int) -> None:
        if re.search(r"\]\([^)\s]*$", "".join(out)[-500:]):
            out.append(text if kind == "ins" else "")  # inside a link's address: the new address only
            return
        for chunk in re.split(r"(\n|\|)", text):
            if chunk in ("\n", "|") or not chunk:
                out.append(chunk)
                continue
            lead = MARKERS.match(chunk).group(0) if (not out or "".join(out[-1:]).endswith("\n")) else ""
            rest = chunk[len(lead):]
            out.append(lead + (OPEN[kind][0] + str(number) + OPEN[kind][1] + rest + CLOSE[kind] if rest.strip() else rest))

    for piece in document.pieces:
        if piece.status == "text":
            out.append(piece.text)
            continue
        number = len(edits)
        edits.append({"n": number, "ids": piece.ids, "status": piece.status})
        for kind, text in word_diff(piece.old, piece.new):
            if kind == "equal":
                out.append(text)
            else:
                emit(kind, text, number)
    return "".join(out), edits


def tagged(rendered: str, edits: list[dict]) -> str:
    """Turn the sentinels into <del>/<ins>. Inside a tag (a link's address, which the renderer percent-encodes)
    the deleted text is dropped and the new text kept."""
    status = {e["n"]: e for e in edits}

    def opening(kind: str):
        def replace(match: re.Match) -> str:
            edit = status[int(match.group(1))]
            return (f'<{kind} class="{edit["status"]}" data-c="{edit["n"]}" '
                    f'title="{html.escape(", ".join(edit["ids"]))}">')
        return replace

    parts = re.split(r"(<[^>]*>)", rendered)
    for i, part in enumerate(parts):
        if part.startswith("<"):
            for k in range(6):
                part = part.replace(f"%EE%80%8{k}", chr(0xE000 + k))
            part = re.sub("\ue000\\d+\ue001.*?\ue004", "", part)
            parts[i] = re.sub("\ue002\\d+\ue003|\ue005", "", part)
            continue
        for kind, (start, end) in OPEN.items():
            part = re.sub(f"{start}(\\d+){end}", opening(kind), part)
            part = part.replace(CLOSE[kind], f"</{kind}>")
        parts[i] = part
    return "".join(parts)


def track_changes(document: Document, suffix: str, folders: list[Path] | None = None) -> tuple[str, list[dict]]:
    text, edits = marked(document)
    return tagged(viz.manuscript_html(text, suffix, folders), edits), edits


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@app.command()
def main(original: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help=(
             "ORIGINAL: the run's snapshot of the manuscript before the workflow (RUN/inputs/01-paper.md); its clean "
             "copy when the manuscript carries revision marks"))],
         working: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help=(
             "WORKING: the working copy, the manuscript now, with every applied edit; its clean copy when it carries "
             "revision marks"))],
         inventory: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help=(
             "The adjudicated inventory, RUN/manuscript-dashboard/findings.json (or its newest attempt)"))],
         output_dir: Annotated[Path, typer.Option("--output-dir", help=(
             "RUN/manuscript-improve/revision; a second attempt goes to revision.2"))],
         choices: Annotated[Path | None, typer.Option(help=(
             "revision-choices.json: prefer, hold (with the reason) and anchor, e.g. " + CHOICES_EXAMPLE))] = None,
         supplement_original: Annotated[Path | None, typer.Option(exists=True, dir_okay=False, help=(
             "The supplement as the run took it (RUN/inputs/02-...), clean; with --supplement-working, the supplement's "
             "corrected version is built too"))] = None,
         supplement_working: Annotated[Path | None, typer.Option(exists=True, dir_okay=False, help=(
             "The supplement now, with its applied edits, clean"))] = None,
         supplement_document: Annotated[str | None, typer.Option(help=(
             "The supplement's file name as the inventory's changes name it (`document`); default: the only other file "
             "they name"))] = None) -> None:
    suffix = original.suffix or ".md"
    names = (f"revised{suffix}", f"proposed{suffix}", "changes.md", "revision.json")
    if (supplement_original is None) != (supplement_working is None):
        raise typer.BadParameter("Give the supplement's reviewed text and its working copy together "
                                 "(--supplement-original and --supplement-working).")
    sup_suffix = (supplement_original.suffix or ".md") if supplement_original else ""
    sup_names = (f"supplement-revised{sup_suffix}", f"supplement-proposed{sup_suffix}", "supplement-changes.md")
    if any((output_dir / name).exists() for name in names + (sup_names if supplement_original else ())):
        raise typer.BadParameter(f"Output files already exist in {output_dir.name}; write this attempt to "
                                 f"{viz.next_attempt(output_dir, folder=True).name} to keep the previous one.")
    try:
        data = viz.Inventory.model_validate_json(inventory.read_text(encoding="utf-8"))
        try:
            decided = json.loads(choices.read_text(encoding="utf-8")) if choices else {}
        except json.JSONDecodeError as exc:
            raise ValueError(f"{choices.name} is not valid JSON ({exc.msg}, line {exc.lineno}, column {exc.colno}). "
                             f"It holds, for example: {CHOICES_EXAMPLE}") from exc
        if choices:
            decided = check_choices(decided, choices.name)
        source, revised = original.read_text(encoding="utf-8"), working.read_text(encoding="utf-8")
        document, record = build(source, revised, data, decided)
        supplement = None
        if supplement_original is not None and supplement_working is not None:
            named = sorted({c.document for c in data.changes if c.document})
            if supplement_document is None and len(named) > 1:
                raise ValueError(f"The inventory's changes name several other files ({', '.join(named)}); say which is "
                                 "the supplement with --supplement-document.")
            sup_name = supplement_document or (named[0] if named else supplement_original.name)
            sup_source = supplement_original.read_text(encoding="utf-8")
            sup_revised = supplement_working.read_text(encoding="utf-8")
            supplement = (sup_name, sup_source, sup_revised, *build(sup_source, sup_revised, data, decided, sup_name))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    proposed = document.current()
    body, edits = track_changes(document, original.suffix.lower(), [working.resolve().parent, original.resolve().parent])
    asked: dict[str, list[str]] = {}
    for comment in record["comments"]:
        for cid in comment["ids"]:
            asked.setdefault(cid, []).append(comment["question"])
    for edit in edits:
        edit["comments"] = [q for cid in edit["ids"] for q in asked.get(cid, [])]
    record |= {"files": {"revised": names[0], "proposed": names[1], "changes": names[2]}, "suffix": suffix,
               "original_sha256": digest(source), "revised_sha256": digest(revised), "proposed_sha256": digest(proposed),
               "inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(), "edits": edits, "body_html": body,
               # The text as unchanged runs and edits, in order, for exports such as the annotated Word document.
               "pieces": [{"text": p.text} if p.status == "text" else {"old": p.old, "new": p.new, "ids": p.ids, "status": p.status}
                          for p in document.pieces]}
    info = {c.id: (c.section, c.summary) for c in data.changes}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / names[0]).write_text(revised, encoding="utf-8")
    (output_dir / names[1]).write_text(proposed, encoding="utf-8")
    (output_dir / "changes.md").write_text(critic(document, asked, info), encoding="utf-8")
    if supplement is not None:
        sup_name, sup_source, sup_revised, sup_document, sup_record = supplement
        sup_asked: dict[str, list[str]] = {}
        for comment in sup_record["comments"]:
            for cid in comment["ids"]:
                sup_asked.setdefault(cid, []).append(comment["question"])
        sup_proposed = sup_document.current()
        (output_dir / sup_names[0]).write_text(sup_revised, encoding="utf-8")
        (output_dir / sup_names[1]).write_text(sup_proposed, encoding="utf-8")
        (output_dir / sup_names[2]).write_text(critic(sup_document, sup_asked, info), encoding="utf-8")
        # The supplement's corrected version, as the manuscript's is recorded above; its changes are the same
        # inventory's, so the record leaves out the per-change table and the track-changes view.
        record["supplement"] = {key: value for key, value in sup_record.items() if key not in ("changes", "other_files")} | {
            "document": sup_name, "files": {"revised": sup_names[0], "proposed": sup_names[1], "changes": sup_names[2]},
            "original_sha256": digest(sup_source), "revised_sha256": digest(sup_revised),
            "proposed_sha256": digest(sup_proposed)}
    (output_dir / "revision.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # notes_in_working_copy: notes the applied edits left in the working copy (remove each with a recorded change);
    # notes_in_text: the authors' own draft notes, listed for them.
    counted = ("applied", "restored", "proposed_in_this_version", "held", "alternatives", "not_placed", "comments",
               "notes_in_working_copy", "notes_in_text")
    typer.echo(json.dumps({"files": record["files"], **{key: len(record[key]) for key in counted},
                           **({"supplement": {"files": record["supplement"]["files"],
                                              **{key: len(record["supplement"][key]) for key in counted}}}
                              if "supplement" in record else {})}, indent=2))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
