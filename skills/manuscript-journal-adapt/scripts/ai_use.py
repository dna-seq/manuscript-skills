# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "markdown-it-py>=3", "pyyaml>=6", "httpx>=0.27"]
# ///
"""Draft the AI-use statement from what this run's stages changed, and from nothing else.

    uv run --script ai_use.py RUN [--tool "Claude Code"] [--model claude-opus-5-5] [--developer Anthropic] \\
        [--authors-use "TEXT" | --authors-use none] [--dates]

RUN is the run folder `runs.py start` made. The draft covers this run only, and says so: its run, its dates and what
the plugin's stages changed in it, by stage. Version history, revision markers, commit trailers and earlier runs are
never read, so nothing before this run is reconstructed.

What changed comes from the corrected version when the run built one: the newest manuscript-improve/revision*/
revision.json gives the applied edits and the proposals in that version (a restored edit is left out), each read in
the newest adjudicated inventory (manuscript-dashboard/findings*.json). A run without one counts the edits the stages
recorded with `runs.py change`. A stage that finished with routine edits only (its --routine-only-reason) counts as
language editing, and a stage that finished without changing text counts as a check. A stage reused from an earlier
run is not covered.

Each change has a kind, in the words of the venue rules and of `venues.py rank --ai-use`: a passage added, or a
rewrite whose new words are most of it (at least 20), is drafting; any other rewrite or a removal is revision;
routine edits are polish. The statement names each kind with the sections it touched, the strongest first, so it
never describes less than the run did.

The authors' own use, outside this run, is one question, asked once. Give their answer with --authors-use; "none"
means there was none, and the statement then adds nothing (never a negative assertion). A later draft in the same
run reuses the answer. Without one, the statement keeps a marked gap for it and the report asks the question.

Outputs, in RUN/manuscript-journal-adapt/: ai-use.md (the draft statement, what each stage changed, the question)
and ai-use.json; a draft made again is ai-use.2.md and ai-use.2.json. The tool, model and developer are the
agent's own (the run does not record them); a missing one stays a marked gap. --dates adds the run's dates, for a
venue that asks for them.

Exit codes: 0 written; 2 a bad option or a folder that is not a run.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "manuscript-dashboard" / "scripts"))
import collect  # noqa: E402
import dashboard as viz  # noqa: E402

app = typer.Typer(add_completion=False)
PLUGIN = Path(__file__).resolve().parents[3] / ".claude-plugin" / "plugin.json"
STAGE = "manuscript-journal-adapt"
KINDS = ("drafting", "revision", "polish")  # strongest first
DRAFTED_WORDS = 20  # a rewrite counts as drafting when this many of its words, and most of them, are new
SECTIONS_NAMED = 4  # sections named in the statement; more are counted instead
STAGE_WORDS = {
    "manuscript-prose-edit": "language editing", "manuscript-deslop": "removing formulaic phrasing",
    "manuscript-story": "structure and readability", "manuscript-journal-adapt": "adapting to the journal",
    "manuscript-integrity-check": "integrity check", "manuscript-reference-check": "reference check",
    "manuscript-reporting-check": "reporting check", "manuscript-peer-review": "simulated peer review",
    "manuscript-figures": "figure review", "manuscript-policy-fit": "policy fit",
    "manuscript-journal-select": "journal selection", "manuscript-reviewer-response": "response to referees",
    "manuscript-improve": "the corrected version", "manuscript-revision-marks": "revision marks",
}
# What a stage that changed no text did, as the end of "was also used to ...". Stages that only keep the run's
# records (the dashboard, the people list, the other models' seats, the coordinator) are not checks.
CHECKS = {
    "manuscript-integrity-check": "check the numbers, statistics and submission files",
    "manuscript-reference-check": "check the references and whether they support the claims cited to them",
    "manuscript-reporting-check": "check the reporting against the relevant guidelines",
    "manuscript-peer-review": "simulate peer review",
    "manuscript-figures": "review the figures",
    "manuscript-policy-fit": "check the clinical, ethics and privacy requirements",
    "manuscript-journal-select": "compare candidate journals",
    "manuscript-story": "read the manuscript as its intended readers would",
    "manuscript-reviewer-response": "check the response to the referees",
    "manuscript-deslop": "look for formulaic phrasing",
    "manuscript-prose-edit": "check the language",
    "manuscript-journal-adapt": "check the journal's requirements",
}
KIND_WORDS = {"drafting": "help draft text", "revision": "revise passages", "polish": "edit the language"}
MEANING = {"drafting": "the AI wrote new sentences", "revision": "the AI substantially reworded text the authors wrote",
           "polish": "the AI corrected the spelling, grammar or clarity of text the authors wrote"}
QUESTION = ("Besides this run, did you use AI tools on this manuscript, for example to draft, translate or edit "
            "text, write code or make figures? If so, which tool, and for what?")
GAP = "[The authors' own AI use outside this run, from their answer to the question below.]"
# A section that is the AI-use statement itself ("AI-use statement", "Use of large language models", "Declaration of
# generative AI"): drafting the disclosure is not use of AI on the paper, so its own changes are left out.
DISCLOSURE = (re.compile(r"\b(?:AI|LLMs?|large language models?|generative)\b", re.I),
              re.compile(r"\b(?:use|usage|statement|disclosure|declaration)\b", re.I))
CHANGE_FILE = re.compile(r"# (.*?)\n\nReason: (.*?)\n\n(?:Comment: .*?\n\n)?## Before\n\n(.*)\n\n## After\n\n(.*)\Z", re.S)


def joined(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(?:\s|$)", text.strip())
    return match.group(1) if match else text.strip()


def section_name(section: str) -> str:
    """A change's section as the statement names it: "Methods > Statistics, paragraph 2" is the Methods, and
    "3.2 Polygenic Risk Scores" is Polygenic Risk Scores."""
    head = re.split(r"\s*(?:>|/|:|—|–|,|\(|¶)\s*", section.strip(), maxsplit=1)[0]
    head = re.sub(r"\s+paragraph\s+\d+$", "", head, flags=re.I)
    head = re.sub(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+", "", head).strip()
    return head or section.strip()


def kind_of(before: str | None, after: str | None) -> str:
    if not before:
        return "drafting"
    if not after:
        return "revision"
    old, new = before.split(), after.split()
    kept = sum(block.size for block in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_matching_blocks())
    fresh = len(new) - kept
    return "drafting" if fresh >= DRAFTED_WORDS and fresh * 2 > len(new) else "revision"


def stage_of(change_id: str, owners: dict[str, str]) -> str:
    """The stage a change came from: the stage file that holds its ID, the skill an applied edit's ID names
    (prose-edit.C1), or the stage's letters (PE-C2)."""
    if change_id in owners:
        return owners[change_id]
    head = re.sub(r"[.-]C\d+$", "", change_id)
    if (Path(__file__).resolve().parents[2] / f"manuscript-{head}").is_dir():
        return f"manuscript-{head}"
    return {letters: skill for skill, letters in collect.PREFIX.items()}.get(head, "unknown")


def recorded(run: Path, data: dict) -> list[dict]:
    """The edits the stages recorded with runs.py change, in the order they were recorded."""
    out = []
    for skill, seat in data["skills"].items():
        for number, change in enumerate(seat.get("changes", []), 1):
            path = run / change["path"]
            parts = CHANGE_FILE.match(path.read_text(encoding="utf-8")) if path.is_file() else None
            if not parts:
                continue
            section, reason, before, after = parts.groups()
            before = None if before.strip() == "(No previous block.)" else before.strip()
            after = None if after.strip() == "(Block removed.)" else after.strip()
            out.append({"id": f"{skill.removeprefix('manuscript-')}.C{number}", "stage": skill, "section": section,
                        "summary": first_sentence(reason), "before": before, "after": after})
    return out


def stage_proposals(run: Path) -> tuple[dict[str, str], set[str]]:
    """Each change ID in the stages' own findings files with its stage, and the IDs that are proposals. The
    dashboard's findings.json is the inventory, not a stage's."""
    owners, proposed = {}, set()
    for folder in sorted(run.glob("manuscript-*")):
        if folder.is_dir() and folder.name not in collect.OWN and (path := collect.newest_findings(folder)):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for c in doc.get("changes", []):
                if isinstance(c, dict) and c.get("id"):
                    owners[str(c["id"])] = folder.name
                    if c.get("status") == "proposed":
                        proposed.add(str(c["id"]))
    return owners, proposed


def disclosure(section: str) -> bool:
    return all(pattern.search(section) for pattern in DISCLOSURE)


def run_changes(run: Path, data: dict) -> tuple[list[dict], str, list[str]]:
    """What this run changed in the text, where that was read and what it left out (the AI-use statement's own
    changes among it)."""
    changes, source, notes = text_changes(run, data)
    return [c for c in changes if not disclosure(c["section"])], source, notes


def text_changes(run: Path, data: dict) -> tuple[list[dict], str, list[str]]:
    owners, proposed = stage_proposals(run)
    revision = viz.newest_attempt(run / "manuscript-improve" / "revision", folder=True)
    inventory = viz.newest_attempt(run / "manuscript-dashboard" / "findings.json", folder=False)
    if revision and (revision / "revision.json").is_file() and inventory:
        record = json.loads((revision / "revision.json").read_text(encoding="utf-8"))
        listed = {c["id"]: c for c in json.loads(inventory.read_text(encoding="utf-8")).get("changes", [])}
        restored = {i for r in record.get("restored", []) for i in r.get("ids", [])}
        ids = [i for i in [*record.get("applied", []), *record.get("proposed_in_this_version", [])] if i not in restored]
        out = [{"id": i, "stage": stage_of(i, owners), "section": listed[i].get("section", ""),
                "summary": first_sentence(listed[i].get("summary", "")), "before": listed[i].get("before"),
                "after": listed[i].get("after")} for i in ids if i in listed]
        left = len(record.get("held", [])) + len(record.get("alternatives", [])) + len(record.get("not_placed", []))
        notes = [f"{left} proposal(s) of this run are not in the corrected version (held, an alternative or not placed); "
                 "they are not covered."] if left else []
        return out, f"the corrected version ({revision.relative_to(run).as_posix()})", notes
    out = recorded(run, data)
    waiting = sorted(proposed - {c["id"] for c in out})
    notes = [f"{len(waiting)} proposal(s) of this run are not in the text; draft the statement again after taking "
             "any of them."] if waiting else []
    return out, "the edits the stages recorded", notes


def stages(data: dict, changes: list[dict]) -> tuple[list[dict], list[str]]:
    """Each stage: what it changed and its kind, or the check it was; and the stages this draft does not cover."""
    rows, skipped = [], []
    by_stage: dict[str, list[dict]] = {}
    for change in changes:
        by_stage.setdefault(change["stage"], []).append(change)
    for skill in [*data["skills"], *[s for s in by_stage if s not in data["skills"]]]:
        seat = data["skills"].get(skill, {})
        status = seat.get("status", "")
        if status == "reused":
            skipped.append(f"the {STAGE_WORDS.get(skill, skill)} was reused from an earlier run.")
            continue
        own = by_stage.get(skill, [])
        routine = (seat.get("routine_only_reason") or "").strip()
        row = {"stage": skill, "label": STAGE_WORDS.get(skill, skill.removeprefix("manuscript-")), "status": status}
        if own:
            for change in own:
                change["kind"] = kind_of(change["before"], change["after"])
            row |= {"kind": next(k for k in KINDS if any(c["kind"] == k for c in own)), "changes": own}
        elif routine:
            row |= {"kind": "polish", "routine_only": routine}
        elif status in {"completed", "partial"} and skill in CHECKS:
            row |= {"check": CHECKS[skill]}
        else:
            continue
        rows.append(row)
    return rows, skipped


def sections_phrase(sections: list[str]) -> str:
    if not sections:
        return ""
    if len(sections) <= SECTIONS_NAMED:
        return f" in the {joined(sections)}"
    return f" in {len(sections)} sections"


def statement(rows: list[dict], who: str, when: str, models: list[str], authors: str | None) -> str:
    uses = []
    for kind in KINDS:
        sections = list(dict.fromkeys(section_name(c["section"]) for r in rows for c in r.get("changes", [])
                                      if c["kind"] == kind and c["section"].strip()))
        if any(c["kind"] == kind for r in rows for c in r.get("changes", [])) or (kind == "polish" and any(
                r.get("routine_only") for r in rows)):
            uses.append(KIND_WORDS[kind] + sections_phrase(sections))
    checks = [r["check"] for r in rows if r.get("check")]
    parts = []
    if uses:
        parts.append(f"{who} was used{when} to {joined(uses)}.")
        if checks:
            parts.append(f"It was also used to {joined(checks)}; "
                         + ("these checks" if len(checks) > 1 else "this check") + " changed no text.")
    elif checks:
        parts.append(f"{who} was used{when} to {joined(checks)}; it changed no text.")
    else:
        parts.append(f"{who} was used{when}; it changed no text and ran no checks.")
    if models:
        parts.append(f"Some of these readings also ran on {joined(models)}.")
    if authors is None:
        parts.append(GAP)
    elif authors.strip().lower() != "none":
        parts.append(authors.strip() if authors.strip()[-1:] in ".!?" else authors.strip() + ".")
    parts.append("The authors reviewed and edited all output and take full responsibility for the content.")
    return " ".join(parts)


def plugin_version() -> str:
    try:
        return json.loads(PLUGIN.read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, json.JSONDecodeError):
        return ""


def day(stamp: str) -> date:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()


def dates_phrase(first: date, last: date) -> str:
    def say(d: date) -> str:
        return f"{d.day} {d:%B %Y}"
    return f" on {say(first)}" if first == last else f" between {say(first)} and {say(last)}"


def earlier_answer(folder: Path) -> str | None:
    """The authors' answer an earlier draft in this run recorded: they are asked once."""
    for path in reversed(viz.attempts(folder / "ai-use.json", folder=False)):
        try:
            answer = json.loads(path.read_text(encoding="utf-8")).get("authors_use", {}).get("answer")
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        if answer:
            return answer
    return None


def report(draft: dict) -> str:
    cover = draft["covers"]
    lines = ["# AI-use statement: draft for this run", "",
             f"This draft covers run {cover['run_id']} ({cover['dates']}) only: what the plugin's stages changed in "
             f"this run, read from {draft['source']}. It says nothing about AI use before this run; the authors' own "
             "use comes from their answer below.", "", "## Draft statement", "", f"> {draft['statement']}", "",
             f"Kind of use, as journal rules name it: **{draft['kind']}** ({MEANING[draft['kind']]})." if draft["kind"] else
             "Kind of use: none in the text; this run only checked it.", ""]
    if draft["gaps"]:
        lines += [f"Still to fill in the statement: {joined(draft['gaps'])}.", ""]
    lines += ["## What each stage changed", "", "| Stage | What it did | Kind |", "|---|---|---|"]
    for row in draft["stages"]:
        if row.get("changes"):
            did = f"changed {len(row['changes'])} passage" + ("s" if len(row["changes"]) > 1 else "")
        elif row.get("routine_only"):
            did = f"routine edits only: {row['routine_only']}"
        else:
            did = "changed no text: a check"
        lines.append(f"| {row['label'].capitalize()} | {did} | {row.get('kind', '')} |")
    changed = [(row, c) for row in draft["stages"] for c in row.get("changes", [])]
    if changed:
        lines += ["", "Each change, as it is in the text:", ""]
        lines += [f"- {c['section'] or 'No section named'}: {c['summary']} ({c['kind']}; {c['id']})" for _, c in changed]
    for note in draft["not_covered"]:
        lines += ["", f"Not covered: {note}"]
    lines += ["", "If the authors leave out some of these changes, take their stages out of the statement or draft it "
              "again after their choice.", "", "## The authors' own use", ""]
    answer = draft["authors_use"]["answer"]
    if answer is None:
        lines += ["Asked once, here (the statement keeps its gap until the answer comes):", "", f"> {QUESTION}"]
    elif answer.strip().lower() == "none":
        lines += ["The authors said they used no AI tools outside this run; the statement adds nothing for it."]
    else:
        lines += [f"The authors' answer, in the statement as they gave it: {answer}"]
    return "\n".join(lines) + "\n"


@app.command()
def main(
    run: Annotated[Path, typer.Argument(file_okay=False, help="The run folder runs.py start made")],
    tool: Annotated[Optional[str], typer.Option(help="The agent tool that ran the stages, e.g. Claude Code")] = None,
    model: Annotated[Optional[str], typer.Option(help="Its model id, e.g. claude-opus-5-5")] = None,
    developer: Annotated[Optional[str], typer.Option(help="The model's developer, e.g. Anthropic")] = None,
    authors_use: Annotated[Optional[str], typer.Option(
        help="The authors' answer about their own AI use outside this run; 'none' for none")] = None,
    dates: Annotated[bool, typer.Option(help="Name the run's dates (for a venue that asks for them)")] = False,
) -> None:
    """Draft the AI-use statement from this run's recorded changes."""
    run = run.resolve()
    try:
        data = json.loads((run / "run.json").read_text(encoding="utf-8"))
        first = day(data["started_at"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise typer.BadParameter(f"{run} is not a run folder with a readable run.json ({exc})") from exc
    folder = run / STAGE
    authors = authors_use.strip() if authors_use and authors_use.strip() else earlier_answer(folder)
    changes, source, notes = run_changes(run, data)
    rows, skipped = stages(data, changes)
    last = datetime.now(timezone.utc).date()
    gaps = [] if tool and model else ["the tool and model id"]
    version = plugin_version()
    who = (f"{tool or '[tool]'} ({', '.join(x for x in (model or '[model id]', developer) if x)})"
           + (f", through the manuscript-skills plugin (version {version})," if version else ""))
    models = sorted({item["model"] for seat in data["skills"].values() for item in seat.get("artifacts", [])
                     if item.get("model")})
    text = statement(rows, who, dates_phrase(first, last) if dates else "", models, authors)
    if authors is None:
        gaps.append("the authors' own use outside this run")
    kinds = {r["kind"] for r in rows if r.get("kind")}
    draft = {
        "covers": {"run_id": data["run_id"], "from": first.isoformat(), "to": last.isoformat(),
                   "dates": dates_phrase(first, last).strip(), "scope": "this run only"},
        "source": source, "tool": tool, "model": model, "developer": developer, "plugin_version": version,
        "kind": next((k for k in KINDS if k in kinds), None), "stages": rows, "other_models": models,
        "not_covered": [*notes, *skipped], "gaps": gaps,
        "authors_use": {"question": QUESTION, "answer": authors}, "statement": text,
    }
    folder.mkdir(exist_ok=True)
    out = viz.next_attempt(folder / "ai-use.json", folder=False)
    out.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = out.with_suffix(".md")
    md.write_text(report(draft), encoding="utf-8")
    typer.echo(json.dumps({"statement": text, "kind": draft["kind"], "gaps": gaps,
                           "files": [md.relative_to(run).as_posix(), out.relative_to(run).as_posix()]},
                          indent=2, ensure_ascii=False))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
