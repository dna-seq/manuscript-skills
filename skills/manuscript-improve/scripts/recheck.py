# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "pyyaml>=6", "httpx>=0.27"]
# ///
"""An independent re-check of the corrected version, once, after revise.py.

The agent that made an edit is the one most inclined to see the problem as fixed. So one fresh agent, which did not
take part in the review or the edits, reads each confirmed problem against the corrected version, and the
deterministic number and reference checks run again on it. Nothing of the run's own reasoning reaches the agent: no
change reasons, no summary, no adjudication.

    uv run --script recheck.py prepare --inventory RUN/manuscript-dashboard/findings.json \\
        --revision RUN/manuscript-improve/revision --original ORIGINAL --into RUN/manuscript-improve/recheck \\
        [--supplement-original SUPPLEMENT_ORIGINAL]
    uv run --script recheck.py numbers --original ORIGINAL --proposed RUN/manuscript-improve/revision/proposed.md \\
        --json RUN/manuscript-improve/recheck/numbers.json [--online]
    uv run --script recheck.py check RUN/manuscript-improve/recheck/answer.json \\
        --numbers RUN/manuscript-improve/recheck/numbers.json --out RUN/manuscript-improve/recheck.json \\
        [--isolation fresh-agent] [--model codex/gpt-6.1-sol]

`prepare` writes the agent's folder: the reviewed text (`original<ext>`), the corrected version (`corrected<ext>`),
the content changes between them as the claim guard lists them (`changes.json`), each confirmed problem with its
quote, what is wrong, what would settle it and who raised it (`concerns.json`), and `brief.md`, the agent's whole
prompt. The agent writes `answer.json`: per problem a verdict (fully, partly, not, worse or unchecked), a verbatim
quote from the corrected version and one sentence why, and new problems, each labelled introduced (the text is new
in the corrected version) or missed (the same text was in the reviewed one).

`numbers` runs the number checks (number_check.py), the offline reference checks (scan.py --references-only) and the
section-roles check (section_roles.py: procedure or a measurement in the Abstract or Introduction, a result in
Methods) on both versions and keeps the candidates the edits introduced and those they resolved.

`check` holds the answer to the contract: every problem answered once with a known verdict, every quote verbatim in
the corrected version, an introduced problem's text absent from the reviewed version and a missed one's present in
it. It writes the re-check the dashboard shows beside the corrected version (`recheck.json`, with the corrected
version's sha256).

When revise.py built the supplement's corrected version too, `--supplement-original` gives the agent the
supplement's two versions as well, and its quotes may come from either file.

After an exit 3 the edits are held or reversed and the version rebuilt; the rebuilt version gets one second
re-check, narrow: `prepare --since RUN/manuscript-improve/recheck.json --previous RUN/manuscript-improve/revision`
(the folder the first re-check read) with the rebuilt `--revision`. The agent reads the version the first re-check
read and the rebuilt one, what the fixes changed, and only the problems to judge again: each the first found made
worse, each new problem it found introduced (as `new-N`), and each whose quoted passage the fixes changed. `check`
then keeps the first re-check's verdicts for the rest (`carried_over`, `round: 2`). There is no third.

Exit codes: prepare and numbers 0; check 0 when the answer meets the contract and no edit made anything worse, 1 when
the answer breaks the contract (nothing is written; correct the quote from the text, or mark the problem unchecked,
never ask the agent to judge again), 3 when it meets the contract but an edit made a problem worse, introduced one,
or introduced a number, reference or section-roles candidate (hold or reverse those edits and rebuild, then the
second re-check; after the second, record what stays unchecked); 2 usage error.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

import typer
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

app = typer.Typer(add_completion=False, no_args_is_help=True)

SKILLS = Path(__file__).resolve().parents[2]
VERDICTS = ("fully", "partly", "not", "worse", "unchecked")
ORIGINS = ("introduced", "missed")

BRIEF = """# Re-check of a corrected manuscript

You are checking the corrected version of a scientific manuscript against the problems an earlier review
confirmed. You took no part in that review or in the edits. Work only from the files in this folder; open
nothing outside it:

{files}
- `changes.json`: each content change between the two, as a script found it (claims, numbers, citations);
- `concerns.json`: the {n} problems the review confirmed, each with the passage it quoted, what was wrong, what
  would settle it, and who raised it.

For each problem in `concerns.json`, read the place it names in the corrected version and give one verdict:

- `fully`: the corrected version no longer has the problem;
- `partly`: the problem is smaller, but part of it remains (say which part);
- `not`: the problem is still there as it was;
- `worse`: the edit made it worse, or made the passage wrong in a new way;
- `unchecked`: these files cannot settle it (it needs data, a source or a fact that is not here).

Give a quote copied word for word from the corrected version{either} that shows your verdict (the passage as it now reads; none
for `unchecked`), and one sentence saying why. Judge what the text says, never what an edit meant to do.

Then read the passages the edits changed, and their neighbours, as a referee would, and list any new problem,
including detail an edit put in the wrong section (a procedure, a threshold or a measured count brought into the
Abstract or the Introduction; a result left in Methods): a quote copied word for word from the corrected
version{either}, its section, one sentence on what is wrong, and its origin: `introduced` when the quoted text is
new in the corrected version, `missed` when the same text is in the reviewed one.

Write `answer.json` in this folder and nothing else:

```json
{{"concerns": [{{"id": "IC-1", "verdict": "partly", "quote": "...", "why": "..."}}],
 "new_problems": [{{"origin": "introduced", "section": "Results", "quote": "...", "problem": "..."}}]}}
```

No scores and no overall verdict. Do not edit any other file.
"""


AGAIN = """# Second re-check of a corrected manuscript

An earlier re-check read a corrected version of this manuscript and found problems the edits had left or made.
Those were fixed, and the version rebuilt. You check the fixes. You took no part in the review, the edits or the
earlier re-check. Work only from the files in this folder; open nothing outside it:

{files}
- `changes.json`: each content change the fixes made, as a script found it (claims, numbers, citations);
- `concerns.json`: the {n} problems to judge again: those the earlier re-check found made worse or new, and those
  whose passage the fixes changed.

For each problem in `concerns.json`, read the place it names in the new version and give one verdict:

- `fully`: the new version no longer has the problem;
- `partly`: the problem is smaller, but part of it remains (say which part);
- `not`: the problem is still there as it was;
- `worse`: the fix made it worse, or made the passage wrong in a new way;
- `unchecked`: these files cannot settle it.

Give a quote copied word for word from the new version{either} that shows your verdict (none for `unchecked`), and
one sentence saying why. Judge what the text says, never what a fix meant to do.

Then read the passages the fixes changed (`changes.json`), and their neighbours, and list any new problem there:
a quote copied word for word from the new version{either}, its section, one sentence on what is wrong, and its
origin: `introduced` when the quoted text is new in the new version, `missed` when the same text is in the earlier
one.

Write `answer.json` in this folder and nothing else:

```json
{{"concerns": [{{"id": "IC-1", "verdict": "fully", "quote": "...", "why": "..."}}],
 "new_problems": [{{"origin": "introduced", "section": "Results", "quote": "...", "problem": "..."}}]}}
```

No scores and no overall verdict. Do not edit any other file.
"""


class Answered(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    verdict: Literal["fully", "partly", "not", "worse", "unchecked"]
    quote: str = ""
    why: str

    @field_validator("quote", mode="before")
    @classmethod
    def no_quote(cls, value: Any) -> Any:
        """The brief asks for no quote with `unchecked`; an agent writes that as null as often as it leaves it out."""
        return "" if value is None else value


class NewProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: Literal["introduced", "missed"]
    section: str = ""
    quote: str
    problem: str


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concerns: list[Answered]
    new_problems: list[NewProblem] = Field(default_factory=list)


def _load(name: str, path: Path) -> Any:
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # pydantic and dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules[name]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def folded(text: str) -> str:
    """Text as a quote is matched against it: Unicode forms, typographic quotes and dashes, emphasis marks and
    whitespace set aside; the words and their order stay."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                                         "—": "-", "−": "-", " ": " "}))
    text = re.sub(r"[*_`]+", "", text)
    return " ".join(text.split())


def corrected_file(revision: Path) -> Path:
    record = json.loads((revision / "revision.json").read_text(encoding="utf-8"))
    files = record.get("files") or {"proposed": "proposed.md"}
    return revision / files["proposed"]


def supplement_file(revision: Path) -> Path | None:
    """The supplement's corrected version when revise.py built one (`supplement` in revision.json)."""
    record = json.loads((revision / "revision.json").read_text(encoding="utf-8"))
    files = (record.get("supplement") or {}).get("files")
    return revision / files["proposed"] if files else None


def texts(folder: Path, stem: str) -> str:
    """A folder's version of the manuscript and, when it has one, of its supplement, read as one text for quotes."""
    main = next(p for p in folder.glob(f"{stem}.*"))
    extra = next(iter(folder.glob(f"{stem}-supplementary.*")), None)
    return main.read_text(encoding="utf-8") + ("\n\n" + extra.read_text(encoding="utf-8") if extra else "")


def file_list(names: dict[str, str], supplement: bool, earlier: str, now: str) -> tuple[str, str]:
    """The brief's list of the texts in the folder, and the words that send a quote to either file."""
    lines = [f"- `{names['original']}`: {earlier};", f"- `{names['corrected']}`: {now};"]
    if supplement:
        lines += [f"- `{names['original_supplement']}` and `{names['corrected_supplement']}`: the supplement, the same two "
                  "versions;"]
    return "\n".join(lines), (" (the manuscript or the supplement)" if supplement else "")


def concerns_of(inventory: dict) -> list[dict]:
    """Each confirmed problem of the adjudicated inventory, with what would settle it (the stage's action, and each
    simulated referee's own suggestion for the concerns it became) and who raised it."""
    asks: dict[str, list[tuple[str, str]]] = {}
    for reviewer in (inventory.get("panel") or {}).get("reviewers", []):
        for concern in reviewer.get("concerns", []):
            for fid in concern.get("finding_ids", []):
                asks.setdefault(fid, []).append((str(reviewer.get("seat") or ""), str(concern.get("suggestion") or "")))
    out = []
    for f in inventory.get("findings", []):
        if f.get("assessment") != "confirmed":
            continue
        settle = [f.get("action") or ""] + [s for _, s in asks.get(f["id"], [])]
        raised = [str(s).removeprefix("manuscript-") for s in f.get("skills", [])] + [seat for seat, _ in asks.get(f["id"], [])]
        out.append({"id": f["id"], "section": f.get("section", ""), "quote": f.get("quote"),
                    "problem": " ".join(x for x in (f.get("summary", ""), f.get("detail", "")) if x).strip(),
                    "settled_by": "; ".join(dict.fromkeys(s for s in settle if s)),
                    "raised_by": list(dict.fromkeys(r for r in raised if r))})
    return out


@app.command()
def prepare(
    inventory: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="The adjudicated findings.json")],
    revision: Annotated[Path, typer.Option(exists=True, file_okay=False, help="revise.py's output folder")],
    original: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="The reviewed text revise.py started from")],
    into: Annotated[Path, typer.Option(help="The agent's folder; must not exist yet")],
    supplement_original: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False, help=(
        "The reviewed supplement revise.py started from, when it built the supplement's corrected version too"))] = None,
    since: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False, help=(
        "The first re-check's result (recheck.json): prepare the second, narrow re-check of the fixes made after it"))] = None,
    previous: Annotated[Optional[Path], typer.Option(exists=True, file_okay=False, help=(
        "With --since: the revise.py folder the first re-check read"))] = None,
) -> None:
    """Write the re-check agent's folder: both texts, the content changes, the confirmed problems and its brief. With
    --since, the second re-check's folder: the version the first re-check read and the rebuilt one, what the fixes
    changed, and only the problems to judge again."""
    if into.exists():
        raise typer.BadParameter(f"{into} exists; prepare the next attempt under a new name.")
    if (since is None) != (previous is None):
        raise typer.BadParameter("--since and --previous go together: the first re-check's result and the revise.py "
                                 "folder it read.")
    data = json.loads(inventory.read_text(encoding="utf-8"))
    proposed, proposed_sup = corrected_file(revision), supplement_file(revision)
    first = None
    if since is not None and previous is not None:
        first = json.loads(since.read_text(encoding="utf-8"))
        if first.get("round", 1) >= 2:
            raise typer.BadParameter(f"{since.name} is already a second re-check; there is no third.")
        before, before_sup = corrected_file(previous), supplement_file(previous)
        if digest(before.read_text(encoding="utf-8")) != first["proposed_sha256"]:
            raise typer.BadParameter(f"{since.name} read another version than {before}; give the revise.py folder the "
                                     "first re-check read.")
        new_text = proposed.read_text(encoding="utf-8") + (
            "\n\n" + proposed_sup.read_text(encoding="utf-8") if proposed_sup else "")
        concerns = again(concerns_of(data), first, new_text)
    else:
        before, before_sup = original, supplement_original
        concerns = concerns_of(data)
    supplement = before_sup is not None and proposed_sup is not None
    suffix = proposed.suffix or ".md"
    into.mkdir(parents=True)
    names = {"original": f"original{suffix}", "corrected": f"corrected{suffix}"}
    shutil.copyfile(before, into / names["original"])
    shutil.copyfile(proposed, into / names["corrected"])
    pairs = [(before, proposed, "")]
    if supplement:
        sup_suffix = proposed_sup.suffix or ".md"
        names |= {"original_supplement": f"original-supplementary{sup_suffix}",
                  "corrected_supplement": f"corrected-supplementary{sup_suffix}"}
        shutil.copyfile(before_sup, into / names["original_supplement"])
        shutil.copyfile(proposed_sup, into / names["corrected_supplement"])
        pairs.append((before_sup, proposed_sup, "supplement"))
    guard = _load("recheck_guard", SKILLS / "manuscript-prose-edit" / "scripts" / "guard.py")
    keep = ("kind", "change", "section", "before_line", "after_line", "before", "after", "removed", "added", "token")
    changes = []
    for old, new, which in pairs:
        report = guard.compare(old.read_text(encoding="utf-8"), new.read_text(encoding="utf-8"), revision=True)
        changes += [{k: c.get(k) for k in keep} | ({"file": which} if which else {}) for c in report["sentence_changes"]]
    (into / "changes.json").write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")
    (into / "concerns.json").write_text(json.dumps(concerns, indent=2, ensure_ascii=False), encoding="utf-8")
    if first is not None:
        (into / "since.json").write_text(json.dumps(first, indent=2, ensure_ascii=False), encoding="utf-8")
        files, either = file_list(names, supplement, "the version the earlier re-check read", "the version after the fixes")
        brief = AGAIN.format(n=len(concerns), files=files, either=either)
    else:
        files, either = file_list(names, supplement, "the version that was reviewed", "the version after the edits")
        brief = BRIEF.format(n=len(concerns), files=files, either=either)
    (into / "brief.md").write_text(brief, encoding="utf-8")
    typer.echo(json.dumps({"folder": str(into.resolve()), "round": 2 if first else 1, "concerns": len(concerns),
                           "changes": len(changes), "supplement": supplement,
                           "brief": str((into / "brief.md").resolve())}, indent=2))


def again(concerns: list[dict], first: dict, new_text: str) -> list[dict]:
    """The problems a second re-check judges: each the first found made worse, each it judged (not unchecked) whose
    quoted passage the fixes changed, each it did not judge, and each new problem it found introduced (as `new-N`).
    The rest keep the first re-check's verdict, whose quote still stands in the rebuilt version."""
    verdicts = {c["id"]: c for c in first.get("concerns", [])}
    text = folded(new_text)
    out = []
    for concern in concerns:
        seen = verdicts.get(concern["id"])
        if seen is None:
            out.append(concern)
        elif seen["verdict"] == "worse" or (seen["verdict"] != "unchecked" and seen.get("quote")
                                            and folded(seen["quote"]) not in text):
            out.append(concern | {"earlier_verdict": seen["verdict"], "earlier_quote": seen.get("quote", "")})
    for n, problem in enumerate(first.get("new_problems", []), 1):
        if problem.get("origin") == "introduced":
            out.append({"id": f"new-{n}", "section": problem.get("section", ""), "quote": problem.get("quote"),
                        "problem": problem.get("problem", ""), "settled_by": "", "raised_by": ["re-check"]})
    return out


LINE_WORDS = re.compile(r"\(?\b(?:on )?lines? \d+(?:\s*(?:and|to|[-–])\s*\d+)?\)?", re.IGNORECASE)


def _key(f: dict) -> tuple[str, str]:
    """A candidate as compared across the two versions: its check and its message without line numbers."""
    return str(f["check"]), " ".join(LINE_WORDS.sub("", str(f["message"])).split())


CHECKS = ("numbers", "references", "placement")


def _candidates(path: Path, online: bool) -> dict[str, list[dict]]:
    numbers = _load("recheck_number_check", SKILLS / "manuscript-integrity-check" / "scripts" / "number_check.py")
    scan = _load("recheck_scan", SKILLS / "manuscript-integrity-check" / "scripts" / "scan.py")
    roles = _load("recheck_section_roles", SKILLS / "manuscript-integrity-check" / "scripts" / "section_roles.py")
    found = numbers.run(path)
    refs = scan.check_references(path, online, search_unidentified=False)
    pick = lambda fs, levels: [{"check": f.check, "severity": f.severity.value, "message": f.message,  # noqa: E731
                                "section": f.section or ""} for f in fs if f.severity.value in levels]
    placed = roles.check(path.read_text(encoding="utf-8"), str(path)).candidates
    return {"numbers": pick(found.findings, ("major", "minor")),
            "references": pick(refs.findings, ("blocker", "major", "minor")),
            "placement": [{"check": c.direction, "severity": "minor", "section": c.section,
                           "message": f"{c.label}, {c.section}: \"{c.quote}\" (belongs in {c.belongs})"}
                          for c in placed]}


def compare_candidates(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> dict[str, dict]:
    out = {}
    for kind in CHECKS:
        b, a = {_key(f): f for f in before[kind]}, {_key(f): f for f in after[kind]}
        out[kind] = {"introduced": [a[k] for k in a if k not in b], "resolved": [b[k] for k in b if k not in a],
                     "unchanged": sum(1 for k in a if k in b)}
    return out


@app.command()
def numbers(
    original: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    proposed: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    json_out: Annotated[Path, typer.Option("--json", help="Where to write the comparison")],
    online: Annotated[bool, typer.Option(help="Also resolve the references online")] = False,
) -> None:
    """Run the number, reference and section-roles checks on both versions: what the edits introduced and what they
    resolved."""
    result = compare_candidates(_candidates(original, online), _candidates(proposed, online))
    result["original_sha256"] = digest(original.read_text(encoding="utf-8"))
    result["proposed_sha256"] = digest(proposed.read_text(encoding="utf-8"))
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(json.dumps({k: {"introduced": len(v["introduced"]), "resolved": len(v["resolved"])}
                           for k, v in result.items() if isinstance(v, dict)}, indent=2))


def contract(answer: Answer, concerns: list[dict], original: str, corrected: str) -> list[str]:
    """What breaks the re-check's contract, in plain words; empty when the answer holds."""
    problems = []
    fo, fc = folded(original), folded(corrected)
    wanted = [c["id"] for c in concerns]
    given = [a.id for a in answer.concerns]
    for cid in wanted:
        if given.count(cid) != 1:
            problems.append(f"Problem {cid} is answered {given.count(cid)} times; answer it once.")
    for cid in sorted(set(given) - set(wanted)):
        problems.append(f"{cid} is not one of the problems in concerns.json.")
    for a in answer.concerns:
        if not a.why.strip():
            problems.append(f"Problem {a.id} has no sentence saying why.")
        if a.verdict != "unchecked":
            if not a.quote.strip():
                problems.append(f"Problem {a.id} ({a.verdict}) has no quote from the corrected version.")
            elif folded(a.quote) not in fc:
                problems.append(f"The quote for {a.id} does not occur word for word in the corrected version: "
                                f"\"{a.quote[:120]}\".")
    for n, p in enumerate(answer.new_problems, 1):
        if not p.problem.strip():
            problems.append(f"New problem {n} does not say what is wrong.")
        if folded(p.quote) not in fc:
            problems.append(f"The quote of new problem {n} does not occur word for word in the corrected version: "
                            f"\"{p.quote[:120]}\".")
        elif p.origin == "introduced" and folded(p.quote) in fo:
            problems.append(f"New problem {n} is labelled introduced, but its text is in the reviewed version: label "
                            "it missed.")
        elif p.origin == "missed" and folded(p.quote) not in fo:
            problems.append(f"New problem {n} is labelled missed, but its text is new in the corrected version: label "
                            "it introduced.")
    return problems


@app.command()
def check(
    answer_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The agent's answer.json")],
    out: Annotated[Path, typer.Option(help="Where to write the re-check (recheck.json beside the revision folder)")],
    workspace: Annotated[Optional[Path], typer.Option(file_okay=False, help="The agent's folder; default: the "
                                                      "answer's")] = None,
    numbers_json: Annotated[Optional[Path], typer.Option("--numbers", exists=True, dir_okay=False,
                                                         help="The output of `numbers`")] = None,
    isolation: Annotated[str, typer.Option(help="fresh-agent, or one-agent where the host could start no agent")] = "fresh-agent",
    model: Annotated[str, typer.Option(help="The model that read it, as CLI/MODEL, when it ran on another")] = "",
) -> None:
    """Hold the agent's answer to the contract and write the re-check the dashboard shows."""
    folder = workspace or answer_path.parent
    if isolation not in ("fresh-agent", "one-agent"):
        raise typer.BadParameter("--isolation takes fresh-agent or one-agent")
    try:
        answer = Answer.model_validate_json(answer_path.read_text(encoding="utf-8"))
    except (ValidationError, ValueError) as exc:
        typer.echo(f"{answer_path.name} does not have the shape the brief asks for:\n{exc}", err=True)
        raise typer.Exit(1) from exc
    concerns = json.loads((folder / "concerns.json").read_text(encoding="utf-8"))
    original, corrected = texts(folder, "original"), texts(folder, "corrected")
    problems = contract(answer, concerns, original, corrected)
    if problems:
        typer.echo("The answer breaks the re-check's contract; nothing was written. Correct each quote from the "
                   "corrected version, or mark the problem unchecked:\n" + "\n".join(f"- {p}" for p in problems), err=True)
        raise typer.Exit(1)
    by_id = {c["id"]: c for c in concerns}
    main_text = next(folder.glob("corrected.*")).read_text(encoding="utf-8")
    compared = json.loads(numbers_json.read_text(encoding="utf-8")) if numbers_json else {}
    if compared and compared.get("proposed_sha256") != digest(main_text):
        typer.echo("The number and reference comparison was made on another corrected version; run `numbers` on this "
                   "one.", err=True)
        raise typer.Exit(1)
    judged = [{**a.model_dump(), "section": by_id[a.id].get("section", ""),
               "summary": by_id[a.id].get("problem", "")[:300], "raised_by": by_id[a.id].get("raised_by", [])}
              for a in answer.concerns if not a.id.startswith("new-")]
    result = {"schema_version": 1, "proposed_sha256": digest(main_text), "isolation": isolation, "model": model,
              "concerns": judged, "new_problems": [p.model_dump() for p in answer.new_problems],
              "numbers": {k: compared[k] for k in CHECKS if k in compared}}
    if (folder / "since.json").is_file():
        result = merged(result, json.loads((folder / "since.json").read_text(encoding="utf-8")),
                        {a.id: a.verdict for a in answer.concerns})
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise typer.BadParameter(f"{out} exists; write the next attempt under a new name.")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {v: sum(a.verdict == v for a in answer.concerns) for v in VERDICTS}
    introduced = [p for p in answer.new_problems if p.origin == "introduced"]
    flagged = [c for k in CHECKS for c in result["numbers"].get(k, {}).get("introduced", [])]
    typer.echo(json.dumps({"out": str(out.resolve()), "verdicts": counts, "new_problems": {
        "introduced": len(introduced), "missed": len(answer.new_problems) - len(introduced)},
        "checks_introduced": len(flagged)}, indent=2))
    if counts["worse"] or introduced or flagged:
        if result.get("round") == 2:
            typer.echo("A fix made a problem worse, introduced one, or introduced a number, reference or section-roles "
                       "candidate. This was the second re-check, and there is no third: hold or reverse those fixes, "
                       "rebuild, and finish the re-check stage as partial with what stays unchecked "
                       "(runs.py stage --name recheck --status partial --reason ...).", err=True)
        else:
            typer.echo("An edit made a problem worse, introduced one, or introduced a number, reference or "
                       "section-roles candidate: hold or reverse those edits and rebuild the corrected version, then "
                       "run the second re-check on the rebuilt version (prepare --since this result --previous this "
                       "revision folder); it reads only what the fixes changed.", err=True)
        raise typer.Exit(3)


def merged(result: dict, first: dict, verdicts: dict[str, str]) -> dict:
    """The second re-check as the dashboard shows it: its verdicts where it judged again, the first re-check's
    elsewhere (`carried_over`), the first's new problems that the fixes did not solve, and its own."""
    judged = {c["id"] for c in result["concerns"]}
    carried = [c for c in first.get("concerns", []) if c["id"] not in judged]
    kept = [p for n, p in enumerate(first.get("new_problems", []), 1)
            if p.get("origin") != "introduced" or verdicts.get(f"new-{n}") != "fully"]
    return result | {"round": 2, "since_sha256": first["proposed_sha256"], "carried_over": [c["id"] for c in carried],
                     "concerns": result["concerns"] + carried, "new_problems": kept + result["new_problems"]}


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
