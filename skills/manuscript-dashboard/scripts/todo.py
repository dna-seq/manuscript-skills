# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "markdown-it-py>=3", "pyyaml>=6"]
# ///
"""The authors' to-do marks, read by the next run.

    uv run --script todo.py show paper.todo.json
    uv run --script todo.py edits paper.todo.json --text paper.md --output RUN/manuscript-improve/todo-edits.json

The dashboard's To-do tab lists what a run leaves for the authors (each decision only they can make, each applied edit
that asks them something, each proposal, each open blocker or major problem nothing else answers), and they mark each
one approved (do it, or keep it) or redundant (drop it, and do not raise it again), with an optional reason. The tab
saves the marks beside the manuscript as STEM.todo.json, one file for every run of the paper.

`show` lists the marks by run, approved first.

`edits` turns the marked edits into the list `runs.py apply RUN --skill S --edits EDITS.json --by NAME` takes, checked
against the manuscript as it is now (its clean text, without revision marks):

- an approved proposal whose text before is in the manuscript once becomes that edit (an addition goes after its
  anchor, joined as revise.py joins it); one whose text after is there already is done;
- an edit marked redundant whose text after is in the manuscript once (an applied edit the authors want undone, or a
  proposal they took over with the corrected version) is undone; one whose text after is not there was not made;
- an approved applied edit is kept, which needs nothing.

Nothing is guessed: an edit whose text is not in the manuscript exactly once is listed as not placed, with why. The
approved decisions and problems are listed for the stages (`for_the_stages`), since each needs judgement rather
than a replacement, and so is every approved item that carries the authors' note (an answer to an edit's question,
say); what was marked redundant is for the adjudication to dismiss, with the authors' reason, when
the new run raises it again (collect.py lists the word-for-word restatements). An existing output is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(1, str(HERE.parents[2] / "manuscript-improve" / "scripts"))
import dashboard as viz  # noqa: E402
import revise  # noqa: E402

app = typer.Typer(add_completion=False)
SAID = {"approved": "approved it", "redundant": "marked it redundant"}


def read_marks(path: Path, runs: list[str] | None = None) -> list[viz.Mark]:
    found = viz.MarksFile.model_validate_json(path.read_text(encoding="utf-8"))
    if runs and (unknown := sorted(set(runs) - {m.run_id for m in found.marks})):
        raise ValueError(f"{path.name} has no marks from run {', '.join(unknown)}.")
    return [m for m in found.marks if not runs or m.run_id in runs]


def reason(mark: viz.Mark) -> str:
    said = f"The authors {SAID[mark.mark]} in the To-do list of run {mark.run_id}"
    return f"{said}: {mark.reason.strip()}" if mark.reason.strip() else f"{said}."


def is_made(before: str, after: str, text: str) -> bool:
    """Whether TEXT holds an edit as made: its text after, and its text before only inside that (an edit that adds
    to a sentence keeps the sentence)."""
    return bool(after) and after in text and (not before or before not in text or before in after)


def with_space(text: str, at: int, end: int) -> tuple[int, int]:
    """A passage to take out, widened to the space or line break that joined it to what precedes it."""
    return len(text[:at].rstrip(" \n")), end


def edit_for(mark: viz.Mark, text: str) -> tuple[dict | None, str]:
    """The edit a marked change asks for in TEXT, or None with what is so instead."""
    def once(passage: str) -> int | None:
        return text.index(passage) if passage and text.count(passage) == 1 else None

    before, after, anchor = mark.before or "", mark.after or "", mark.anchor or ""
    if mark.mark == "approved":
        if mark.kind == "question":
            return None, "kept: an applied edit, already in the text"
        if is_made(before, after, text) or (not after and before and before not in text):
            return None, "done: the text is already as the edit leaves it"
        if not before:  # an addition: after its anchor, joined as the corrected version joins it
            if (at := once(anchor)) is None:
                return None, "not placed: its anchor passage is not in the text exactly once"
            end, addition = revise.insertion_point(text, at + len(anchor), after)
            return {"before": text[at:end], "after": text[at:end] + addition}, "approved: added"
        if (at := once(before)) is None:
            return None, f"not placed: its text before is {'in the text more than once' if before in text else 'not in the text'}"
        if not after:  # a deletion, with the space that joined it
            start, end = with_space(text, at, at + len(before))
            return {"before": text[start:end], "after": ""}, "approved: deleted"
        return {"before": before, "after": after}, "approved: made"
    # Redundant: undo it where the text holds it; an edit never made needs nothing.
    if not after:
        return None, ("not made: its text before is still in the text" if before in text
                      else "not placed: a deletion cannot be undone without the passage it followed")
    if not is_made(before, after, text):
        return None, "not made: the text does not hold it"
    if (at := once(after)) is None:
        return None, "not placed: its text after is in the text more than once"
    if not before:  # an addition: take it out with the space or break that joined it
        start, end = with_space(text, at, at + len(after))
        return {"before": text[start:end], "after": ""}, "redundant: undone"
    return {"before": after, "after": before}, "redundant: undone"


@app.command()
def show(marks: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """The marks by run, approved first, each with its reason."""
    try:
        found = read_marks(marks)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for run in dict.fromkeys(m.run_id for m in found):
        mine = [m for m in found if m.run_id == run]
        typer.echo(f"Run {run}: {sum(m.mark == 'approved' for m in mine)} approved, {sum(m.mark == 'redundant' for m in mine)} redundant")
        for m in sorted(mine, key=lambda m: m.mark):
            typer.echo(f"  {m.mark:<9} {m.kind:<8} {m.id}: {m.summary}" + (f" ({m.reason.strip()})" if m.reason.strip() else ""))


@app.command()
def edits(marks: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
          text: Annotated[Path, typer.Option("--text", exists=True, dir_okay=False, help="The manuscript as it is now")],
          output: Annotated[Path, typer.Option("--output", help="The EDITS.json for runs.py apply")],
          run: Annotated[list[str] | None, typer.Option("--run", help="Only this run's marks; repeatable")] = None) -> None:
    """The marked edits as the list runs.py apply takes, and the approved decisions and problems for the stages."""
    if output.exists():
        raise typer.BadParameter(f"{output.name} exists; write the next attempt as {viz.next_attempt(output, folder=False).name}.")
    try:
        found = read_marks(marks, run)
        clean = viz.revision_marks(text.read_text(encoding="utf-8"), text.suffix.lower(), text)[0]
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    made, outcomes, stages = [], [], []
    for mark in found:
        key = viz.mark_key(mark.run_id, mark.kind, mark.id)
        # An approved decision or problem needs a stage's judgement; so does a note on an approved edit (an answer to its
        # question, say).
        if mark.mark == "approved" and (mark.kind not in viz.CHANGE_KINDS or mark.reason.strip()):
            stages.append({"mark": key, "kind": mark.kind, "summary": mark.summary, "section": mark.section,
                           "action": mark.action, "note": mark.reason, "finding_ids": mark.finding_ids})
        if mark.kind not in viz.CHANGE_KINDS:
            continue
        edit, outcome = edit_for(mark, clean)
        outcomes.append({"mark": key, "outcome": outcome})
        if edit is not None:  # runs.py apply makes them in order, so the next is checked against this one's result
            made.append({**edit, "reason": reason(mark), "section": mark.section})
            clean = clean.replace(edit["before"], edit["after"], 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(made, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(json.dumps({"output": str(output.resolve()), "edits": len(made), "changes": outcomes,
                           "for_the_stages": stages}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
