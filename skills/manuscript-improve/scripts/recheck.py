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
        --revision RUN/manuscript-improve/revision --original ORIGINAL --into RUN/manuscript-improve/recheck
    uv run --script recheck.py numbers --original ORIGINAL --proposed RUN/manuscript-improve/revision/proposed.md \\
        --json RUN/manuscript-improve/recheck/numbers.json [--online]
    uv run --script recheck.py check RUN/manuscript-improve/recheck/answer.json \\
        --numbers RUN/manuscript-improve/recheck/numbers.json --out RUN/manuscript-improve/recheck.json \\
        [--isolation fresh-agent] [--model codex/gpt-5.6-sol]

`prepare` writes the agent's folder: the reviewed text (`original<ext>`), the corrected version (`corrected<ext>`),
the content changes between them as the claim guard lists them (`changes.json`), each confirmed problem with its
quote, what is wrong, what would settle it and who raised it (`concerns.json`), and `brief.md`, the agent's whole
prompt. The agent writes `answer.json`: per problem a verdict (fully, partly, not, worse or unchecked), a verbatim
quote from the corrected version and one sentence why, and new problems, each labelled introduced (the text is new
in the corrected version) or missed (the same text was in the reviewed one).

`numbers` runs the number checks (number_check.py) and the offline reference checks (scan.py --references-only) on
both versions and keeps the candidates the edits introduced and those they resolved.

`check` holds the answer to the contract: every problem answered once with a known verdict, every quote verbatim in
the corrected version, an introduced problem's text absent from the reviewed version and a missed one's present in
it. It writes the re-check the dashboard shows beside the corrected version (`recheck.json`, with the corrected
version's sha256).

Exit codes: prepare and numbers 0; check 0 when the answer meets the contract and no edit made anything worse, 1 when
the answer breaks the contract (nothing is written; correct the quote from the text, or mark the problem unchecked,
never ask the agent to judge again), 3 when it meets the contract but an edit made a problem worse, introduced one,
or introduced a number or reference candidate (hold or reverse those edits and rebuild; there is no second
re-check); 2 usage error.
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

- `{original}`: the version that was reviewed;
- `{corrected}`: the version after the edits;
- `changes.json`: each content change between the two, as a script found it (claims, numbers, citations);
- `concerns.json`: the {n} problems the review confirmed, each with the passage it quoted, what was wrong, what
  would settle it, and who raised it.

For each problem in `concerns.json`, read the place it names in `{corrected}` and give one verdict:

- `fully`: the corrected version no longer has the problem;
- `partly`: the problem is smaller, but part of it remains (say which part);
- `not`: the problem is still there as it was;
- `worse`: the edit made it worse, or made the passage wrong in a new way;
- `unchecked`: these files cannot settle it (it needs data, a source or a fact that is not here).

Give a quote copied word for word from `{corrected}` that shows your verdict (the passage as it now reads; none
for `unchecked`), and one sentence saying why. Judge what the text says, never what an edit meant to do.

Then read the passages the edits changed, and their neighbours, as a referee would, and list any new problem: a
quote copied word for word from `{corrected}`, its section, one sentence on what is wrong, and its origin:
`introduced` when the quoted text is new in `{corrected}`, `missed` when the same text is in `{original}`.

Write `answer.json` in this folder and nothing else:

```json
{{"concerns": [{{"id": "IC-1", "verdict": "partly", "quote": "...", "why": "..."}}],
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
) -> None:
    """Write the re-check agent's folder: both texts, the content changes, the confirmed problems and its brief."""
    if into.exists():
        raise typer.BadParameter(f"{into} exists; prepare the next attempt under a new name.")
    data = json.loads(inventory.read_text(encoding="utf-8"))
    concerns = concerns_of(data)
    proposed = corrected_file(revision)
    suffix = proposed.suffix or ".md"
    into.mkdir(parents=True)
    names = {"original": f"original{suffix}", "corrected": f"corrected{suffix}"}
    shutil.copyfile(original, into / names["original"])
    shutil.copyfile(proposed, into / names["corrected"])
    guard = _load("recheck_guard", SKILLS / "manuscript-prose-edit" / "scripts" / "guard.py")
    report = guard.compare(original.read_text(encoding="utf-8"), proposed.read_text(encoding="utf-8"), revision=True)
    keep = ("kind", "change", "section", "before_line", "after_line", "before", "after", "removed", "added", "token")
    changes = [{k: c.get(k) for k in keep} for c in report["sentence_changes"]]
    (into / "changes.json").write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")
    (into / "concerns.json").write_text(json.dumps(concerns, indent=2, ensure_ascii=False), encoding="utf-8")
    (into / "brief.md").write_text(BRIEF.format(n=len(concerns), **names), encoding="utf-8")
    typer.echo(json.dumps({"folder": str(into.resolve()), "concerns": len(concerns), "changes": len(changes),
                           "brief": str((into / "brief.md").resolve())}, indent=2))


LINE_WORDS = re.compile(r"\(?\b(?:on )?lines? \d+(?:\s*(?:and|to|[-–])\s*\d+)?\)?", re.IGNORECASE)


def _key(f: dict) -> tuple[str, str]:
    """A candidate as compared across the two versions: its check and its message without line numbers."""
    return str(f["check"]), " ".join(LINE_WORDS.sub("", str(f["message"])).split())


def _candidates(path: Path, online: bool) -> dict[str, list[dict]]:
    numbers = _load("recheck_number_check", SKILLS / "manuscript-integrity-check" / "scripts" / "number_check.py")
    scan = _load("recheck_scan", SKILLS / "manuscript-integrity-check" / "scripts" / "scan.py")
    found = numbers.run(path)
    refs = scan.check_references(path, online, search_unidentified=False)
    pick = lambda fs, levels: [{"check": f.check, "severity": f.severity.value, "message": f.message,  # noqa: E731
                                "section": f.section or ""} for f in fs if f.severity.value in levels]
    return {"numbers": pick(found.findings, ("major", "minor")),
            "references": pick(refs.findings, ("blocker", "major", "minor"))}


def compare_candidates(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> dict[str, dict]:
    out = {}
    for kind in ("numbers", "references"):
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
    """Run the number and reference checks on both versions: what the edits introduced and what they resolved."""
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
    original = next(folder.glob("original.*")).read_text(encoding="utf-8")
    corrected = next(folder.glob("corrected.*")).read_text(encoding="utf-8")
    problems = contract(answer, concerns, original, corrected)
    if problems:
        typer.echo("The answer breaks the re-check's contract; nothing was written. Correct each quote from the "
                   "corrected version, or mark the problem unchecked:\n" + "\n".join(f"- {p}" for p in problems), err=True)
        raise typer.Exit(1)
    by_id = {c["id"]: c for c in concerns}
    compared = json.loads(numbers_json.read_text(encoding="utf-8")) if numbers_json else {}
    if compared and compared.get("proposed_sha256") != digest(corrected):
        typer.echo("The number and reference comparison was made on another corrected version; run `numbers` on this "
                   "one.", err=True)
        raise typer.Exit(1)
    result = {"schema_version": 1, "proposed_sha256": digest(corrected), "isolation": isolation, "model": model,
              "concerns": [{**a.model_dump(), "section": by_id[a.id].get("section", ""),
                            "summary": by_id[a.id].get("problem", "")[:300], "raised_by": by_id[a.id].get("raised_by", [])}
                           for a in answer.concerns],
              "new_problems": [p.model_dump() for p in answer.new_problems],
              "numbers": {k: compared[k] for k in ("numbers", "references") if k in compared}}
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise typer.BadParameter(f"{out} exists; write the next attempt under a new name.")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {v: sum(a.verdict == v for a in answer.concerns) for v in VERDICTS}
    introduced = [p for p in answer.new_problems if p.origin == "introduced"]
    flagged = [c for k in ("numbers", "references") for c in result["numbers"].get(k, {}).get("introduced", [])]
    typer.echo(json.dumps({"out": str(out.resolve()), "verdicts": counts, "new_problems": {
        "introduced": len(introduced), "missed": len(answer.new_problems) - len(introduced)},
        "checks_introduced": len(flagged)}, indent=2))
    if counts["worse"] or introduced or flagged:
        typer.echo("An edit made a problem worse, introduced one, or introduced a number or reference candidate: hold "
                   "or reverse those edits and rebuild the corrected version. There is no second re-check.", err=True)
        raise typer.Exit(3)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
