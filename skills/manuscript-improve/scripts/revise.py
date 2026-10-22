# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "markdown-it-py>=3"]
# ///
"""Build the corrected version of a manuscript from a run: the edits applied, then every proposal.

    uv run --script revise.py ORIGINAL WORKING INVENTORY --choices choices.json --output-dir RUN/manuscript-improve/revision

ORIGINAL is the manuscript before the workflow, WORKING the working copy with the applied edits, and
INVENTORY the adjudicated findings.json from manuscript-dashboard. Each applied edit is located in the
working copy, newest first; undoing them must give the original exactly, so an edit nobody recorded stops
the build.
The proposals are then applied in manuscript order to give the proposed version.

Proposals that rewrite the same passage are alternatives (the dashboard's competing groups, formed after
the held proposals are set aside). The choices file names the ones to use from each group ("prefer"; two
from one group only when they change different words), the proposals held back with the reason ("hold",
such as a statement that waits for the journal choice) and an anchor for an addition that lacks one:

    {"prefer": ["ST-C3"], "hold": [{"id": "JA-C18", "why": "Genes only"}],
     "anchor": [{"id": "JA-C1", "after": "verbatim passage the addition follows"}]}

A proposal is applied only where its before-text, or an addition's anchor, occurs exactly once in the
text built so far and does not straddle another edit; every other proposal is listed with its reason.

Outputs: revised.md (the working copy), proposed.md (every chosen proposal applied), changes.md (the same
as CriticMarkup against the original) and revision.json: what was applied, held, left as an alternative or
not placed, and the track-changes view that manuscript-dashboard shows as the dashboard's Revised paper.
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
        end = start + len(after) - head - tail
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
        merged = Piece(old=text[lo:start] + before[head:len(before) - tail] + text[end:hi], new="".join(current),
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


def insertion_point(text: str, anchor_end: int, addition: str) -> tuple[int, str]:
    """Where an addition goes and how it is joined. In a block of lines (a reference list, a table, a list) a
    line or lines go on new lines after the anchor's line; a sentence follows its anchor in the paragraph; a
    heading, table, list or new paragraph goes after the anchor's paragraph."""
    addition = addition.strip()
    start = text.rfind("\n\n", 0, anchor_end)
    start = 0 if start < 0 else start + 2
    end = text.find("\n\n", anchor_end)
    end = len(text.rstrip("\n")) if end < 0 else end
    in_lines = "\n" in text[start:end].strip() and (anchor_end == end or text.startswith("\n", anchor_end))
    if in_lines and "\n\n" not in addition and not addition.startswith("#"):
        return anchor_end, "\n" + addition
    if not BLOCK.search(addition):
        return anchor_end, " " + addition
    return end, "\n\n" + addition


def build(original: str, working: str, data: viz.Inventory, choices: dict) -> tuple[Document, dict]:
    changes = {c.id: c for c in data.changes}
    proposals = {c.id: c for c in data.changes if c.status == "proposed"}
    prefer = list(choices.get("prefer", []))
    held = {h["id"]: h["why"] for h in choices.get("hold", [])}
    anchors = {a["id"]: a["after"] for a in choices.get("anchor", [])}
    if unknown := sorted((set(prefer) | set(held) | set(anchors)) - set(proposals)):
        raise ValueError(f"The choices name changes that are not proposals in the inventory: {', '.join(unknown)}")
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
                raise Unplaced("a deletion cannot be located in the working copy")
            document.undo(change.before or "", change.after, change.id)
        except Unplaced as reason:
            unplaced[change.id] = f"Applied edit not found in the working copy: {reason}."
    if document.previous() != original:
        raise ValueError("The working copy differs from the original outside the recorded applied edits, at "
                         f"{first_difference(document.previous(), original)}. Record every applied edit first.")
    revised = document.current()

    def position(change: viz.Change) -> int:
        target = change.before or anchors.get(change.id) or change.anchor or ""
        return revised.find(target) if target else -1

    todo = [c for c in proposals.values() if c.id not in held and c.id not in alternatives]
    for change in sorted(todo, key=lambda c: (position(c) < 0, position(c))):
        try:
            if change.before:
                after = change.after or ""
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
            at, addition = insertion_point(document.working(), start + len(anchor), change.after or "")
            document.propose(at, at, addition, change.id)
        except Unplaced as reason:
            unplaced[change.id] = str(reason)
    in_text = {cid for piece in document.pieces for cid in piece.ids}
    record = {
        "applied": [c.id for c in applied if c.id in in_text],
        "proposed_in_this_version": [cid for cid in proposals if cid in in_text],
        "held": [{"id": cid, "why": why} for cid, why in held.items()],
        "alternatives": [{"id": cid, "chosen": chosen} for cid, chosen in alternatives.items()],
        "not_placed": [{"id": cid, "why": why} for cid, why in unplaced.items()],
        "changes": {cid: {"section": c.section, "summary": c.summary, "kind": c.kind, "status": c.status,
                          "finding_ids": c.finding_ids} for cid, c in changes.items()},
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


def critic(document: Document) -> str:
    parts = []
    for piece in document.pieces:
        if piece.status == "text":
            parts.append(piece.text)
            continue
        note = "{>>" + ", ".join(piece.ids) + "<<}"
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


def track_changes(document: Document, suffix: str) -> tuple[str, list[dict]]:
    text, edits = marked(document)
    return tagged(viz.manuscript_html(text, suffix), edits), edits


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@app.command()
def main(original: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
         working: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
         inventory: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
         output_dir: Annotated[Path, typer.Option("--output-dir")],
         choices: Annotated[Path | None, typer.Option(help="prefer / hold / anchor decisions")] = None) -> None:
    names = ("revised.md", "proposed.md", "changes.md", "revision.json")
    if any((output_dir / name).exists() for name in names):
        raise typer.BadParameter("Output files already exist; choose a new output directory to keep the previous attempt.")
    try:
        data = viz.Inventory.model_validate_json(inventory.read_text(encoding="utf-8"))
        decided = json.loads(choices.read_text(encoding="utf-8")) if choices else {}
        source, revised = original.read_text(encoding="utf-8"), working.read_text(encoding="utf-8")
        document, record = build(source, revised, data, decided)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    proposed = document.current()
    body, edits = track_changes(document, original.suffix.lower())
    record |= {"original_sha256": digest(source), "revised_sha256": digest(revised), "proposed_sha256": digest(proposed),
               "inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(), "edits": edits, "body_html": body}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "revised.md").write_text(revised, encoding="utf-8")
    (output_dir / "proposed.md").write_text(proposed, encoding="utf-8")
    (output_dir / "changes.md").write_text(critic(document), encoding="utf-8")
    (output_dir / "revision.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(json.dumps({key: len(record[key]) for key in ("applied", "proposed_in_this_version", "held",
                                                               "alternatives", "not_placed")}, indent=2))


if __name__ == "__main__":
    app()
