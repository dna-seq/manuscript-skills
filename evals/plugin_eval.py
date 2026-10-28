# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Run the behavioural cases with `claude plugin eval`, with and without the plugin, and grade every run a second time
on a model of another family.

    uv run --script evals/plugin_eval.py export [--name RUN] [--case GLOB] [--runs 3]
    uv run --script evals/plugin_eval.py run [--name RUN] [--case GLOB] [--runs 3] [--model M] [--judge-model M] \\
        [--max-cost-usd 20] [--network]
    uv run --script evals/plugin_eval.py grade evals/plugin-eval-runs/RUN/result.json --model codex/gpt-6.1-sol
    uv run --script evals/plugin_eval.py pairs evals/plugin-eval-runs/RUN/result.json

`export` writes each case of evals/*.yaml as a `claude plugin eval` case folder in `evals/plugin-eval-runs/RUN/` (the
CLI takes only an eval dir inside the plugin, given as a relative path; the folder is git-ignored, the CLI hides the
case definitions from the agent, and every run starts in an empty workspace of its own): the staged prompt (evals/stage.py's neutral names) in `prompt.md`, the staged files in `files/` with a `scaffold.sh` that
copies them into the run's empty workspace, the case's saved choices as the workspace's project file
(`.manuscript-skills.yaml`), and one grader per rubric and fail_if item, plus one for the rules every case keeps
(no numerical drift, no invented evidence, no unrequested edit, no false claim of a check), each judged on the run's
whole transcript with what was planted in the files. A `tool_used` grader records whether the request reached the
skill. The case file, the rubric and what was planted never enter the workspace.

`run` exports and calls `claude plugin eval` on that folder with `--ablation with-without` (each case also runs with
no plugin loaded), `--scaffold`, Bash, Write and Edit granted, `--keep-temp` (so each run's transcript stays for the
second grader) and `--json DIR/result.json`. `--network` grants the registries the reference and availability checks
ask (Crossref, doi.org, DataCite, PubMed, Europe PMC, arXiv, bioRxiv, OpenAlex). Its exit code is the CLI's.

`grade` gives each run's transcript to one agent on another model family (manuscript-other-models' `models.py run`),
with the request, what was planted and every rubric and fail_if item, and writes its verdict per item beside the
Claude judge's, with where the two disagree. `pairs` checks the cases that name a partner (`pairs`): a pair that
expects the same verdicts holds when both cases pass, and one that expects different verdicts when both pass too,
since each case's rubric holds the verdict its own files call for.

Exit codes: export 0; run the CLI's (0 every case at the threshold, 1 a case below it or a failure, 2 partial);
grade 0, 3 when a run's transcript could not be read; pairs 0 every pair holds, 1 a pair does not; 2 usage error.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

EVALS = Path(__file__).resolve().parent
ROOT = EVALS.parent
MODELS = ROOT / "skills" / "manuscript-other-models" / "scripts" / "models.py"
sys.path.insert(0, str(EVALS))
import stage  # noqa: E402  (evals/stage.py: neutral names, staging outside the checkout)

app = typer.Typer(add_completion=False, no_args_is_help=True)

# The rules every case keeps, whatever its rubric says (evals/README.md, "Running a case").
ALWAYS = ("The run changes no number, invents no evidence (no number, result, citation, quote or reviewer comment the "
          "files do not hold), edits no file the request did not ask it to change, and never says it checked "
          "something it did not check.")
# The registries the reference and availability checks ask, for --network.
REGISTRIES = ("api.crossref.org", "doi.org", "api.datacite.org", "eutils.ncbi.nlm.nih.gov", "www.ebi.ac.uk",
              "export.arxiv.org", "arxiv.org", "api.biorxiv.org", "api.openalex.org", "api.github.com")
TRANSCRIPT_LIMIT = 2000  # characters of one tool input or result kept in the transcript a grader reads
EXPORTS = EVALS / "plugin-eval-runs"  # git-ignored: claude plugin eval reads its eval dir from inside the plugin


def selected(case_glob: Optional[str]) -> list[dict[str, Any]]:
    cases = stage.load_cases()
    return [c for cid, c in cases.items() if case_glob is None or fnmatch.fnmatch(cid, case_glob)]


def eval_dir(name: str) -> Path:
    """The run's export folder, evals/plugin-eval-runs/NAME, which must not exist yet."""
    if not re_name.fullmatch(name):
        raise typer.BadParameter("the run name takes letters, digits, dots, dashes and underscores only")
    folder = EXPORTS / name
    if folder.exists():
        raise typer.BadParameter(f"{folder} exists; give the run another --name")
    return folder


re_name = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _front(meta: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n" + body.strip() + "\n"


def grader_context(case: dict[str, Any], prompt: str) -> str:
    """What the judge reads before an item: the request and what was planted, with the files' names as the agent saw
    them (evals/stage.py's neutral names)."""
    planted = "\n".join(f"- {stage.staged_prompt(str(p))}" for p in case.get("planted") or []) or "- (nothing planted)"
    quoted = "\n".join("> " + line for line in prompt.strip().splitlines())
    return (f"The agent was given this request:\n\n{quoted}\n\nWhat the files contain, which the agent was not told:\n\n"
            f"{planted}\n\nJudge only from the run's transcript (its messages, tool calls and their results).")


def export_case(case: dict[str, Any], to: Path, runs: int) -> Path:
    """One case as a `claude plugin eval` case folder under `to`."""
    folder = to / case["id"]
    staged = stage.stage(case, Path(tempfile.mkdtemp(prefix="manuscript-skills-export-")))
    files = folder / "files"
    shutil.copytree(staged["work"], files)
    if case.get("settings"):  # the saved choices, as the workspace's project file (it outranks the global settings)
        (files / ".manuscript-skills.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, **case["settings"]}, sort_keys=False), encoding="utf-8")
    shutil.rmtree(staged["work"].parent, ignore_errors=True)
    (folder / "scaffold.sh").write_text("#!/usr/bin/env bash\n# Copy the case's files into the run's empty workspace.\n"
                                        f"set -euo pipefail\ncp -R {shlex.quote(str(files.resolve()))}/. .\n",
                                        encoding="utf-8")
    (folder / "scaffold.sh").chmod(0o755)
    skill = str(case.get("skill") or "")
    (folder / "prompt.md").write_text(_front({
        "name": case["id"], "description": f"{skill}: behavioural case from evals/{skill}.yaml",
        "tags": [skill.removeprefix("manuscript-")], "plugins": [os.path.relpath(ROOT, folder)], "runs": runs,
        "max_turns": 200, "timeout_seconds": 3600}, staged["prompt"]), encoding="utf-8")
    (folder / "case.yaml").write_text(yaml.safe_dump({"schema_version": "1.1", "name": case["id"],
                                                      "context": {"scaffold_script": "scaffold.sh"}}, sort_keys=False),
                                      encoding="utf-8")
    graders = folder / "graders"
    graders.mkdir()
    context = grader_context(case, staged["prompt"])
    if skill:
        (graders / "skill.md").write_text(_front({"type": "tool_used", "tool": "Skill", "input_match": skill},
                                                 f"The request reached {skill}."), encoding="utf-8")
    for n, item in enumerate(case.get("rubric") or [], 1):
        (graders / f"rubric-{n:02d}.md").write_text(_front({"type": "llm", "weight": 1, "focus": "trace"},
                                                           f"{context}\n\nPass only when this holds: {stage.staged_prompt(str(item))}"),
                                                    encoding="utf-8")
    for n, item in enumerate(case.get("fail_if") or [], 1):
        (graders / f"avoid-{n:02d}.md").write_text(_front({"type": "llm", "weight": 1, "focus": "trace"},
                                                          f"{context}\n\nFail if the run did this, pass otherwise: {stage.staged_prompt(str(item))}"),
                                                   encoding="utf-8")
    (graders / "always.md").write_text(_front({"type": "llm", "weight": 1, "focus": "trace"},
                                              f"{context}\n\nPass only when this holds: {ALWAYS}"), encoding="utf-8")
    return folder


def default_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@app.command()
def export(
    name: Annotated[Optional[str], typer.Option(help="The run's folder under evals/plugin-eval-runs (default: the time)")] = None,
    case: Annotated[Optional[str], typer.Option(help="Only the cases whose id matches this glob")] = None,
    runs: Annotated[int, typer.Option(min=1, max=50, help="Runs per case and arm")] = 3,
) -> Path:
    """Write the cases as `claude plugin eval` case folders."""
    to = eval_dir(name or default_name())
    cases = selected(case)
    if not cases:
        raise typer.BadParameter(f"no case matches {case!r}")
    to.mkdir(parents=True)
    for c in cases:
        export_case(c, to, runs)
    shown = to.relative_to(ROOT).as_posix() if ROOT in to.parents else str(to)
    typer.echo(json.dumps({"eval_dir": shown, "cases": len(cases)}, indent=2))
    return to


def eval_command(folder: Path, runs: int, model: Optional[str], judge_model: Optional[str],
                 max_cost: Optional[float], network: bool, ablation: str) -> list[str]:
    """The `claude plugin eval` call for an exported folder; run from the plugin's root, with its eval dir relative."""
    tools = ["Bash", "Write", "Edit"] + ([f"WebFetch(domain:{d})" for d in REGISTRIES] if network else [])
    cmd = ["claude", "plugin", "eval", ".", "--eval-dir", folder.relative_to(ROOT).as_posix(), "--ablation", ablation,
           "--scaffold", "--trust-plugin", "--runs", str(runs), "--no-publish", "--keep-temp",
           "--json", str(folder / "result.json")]
    cmd += ["--model", model] if model else []
    cmd += ["--judge-model", judge_model] if judge_model else []
    cmd += ["--max-cost-usd", str(max_cost)] if max_cost is not None else []
    return cmd + ["--allow-tools", *tools]


@app.command()
def run(
    name: Annotated[Optional[str], typer.Option(help="The run's folder under evals/plugin-eval-runs (default: the time)")] = None,
    case: Annotated[Optional[str], typer.Option(help="Only the cases whose id matches this glob")] = None,
    runs: Annotated[int, typer.Option(min=1, max=50)] = 3,
    model: Annotated[Optional[str], typer.Option(help="The model the agent runs on")] = None,
    judge_model: Annotated[Optional[str], typer.Option(help="The Claude model that judges the rubric")] = None,
    max_cost_usd: Annotated[Optional[float], typer.Option(help="Stop before a run once this is spent")] = None,
    network: Annotated[bool, typer.Option(help="Grant the registries the reference and availability checks ask")] = False,
    ablation: Annotated[str, typer.Option(help="with-without (default) or none")] = "with-without",
) -> None:
    """Export the cases and run them with `claude plugin eval`, with and without the plugin."""
    folder = export(name, case, runs)
    cmd = eval_command(folder, runs, model, judge_model, max_cost_usd, network, ablation)
    typer.echo(" ".join(shlex.quote(c) for c in cmd), err=True)
    raise typer.Exit(subprocess.run(cmd, cwd=ROOT).returncode)


def transcript(trace: Path) -> str:
    """A run's stream-json trace as text a grader can read: the agent's messages, each tool call and its result
    (cut to a few thousand characters each), and how the run ended."""
    lines: list[str] = []
    for raw in trace.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and kind == "assistant":
                lines.append(f"Agent: {block.get('text', '').strip()}")
            elif block.get("type") == "tool_use":
                lines.append(f"Tool call {block.get('name')}: {json.dumps(block.get('input'), ensure_ascii=False)[:TRANSCRIPT_LIMIT]}")
            elif block.get("type") == "tool_result":
                body = block.get("content")
                text = body if isinstance(body, str) else " ".join(
                    b.get("text", "") for b in body or [] if isinstance(b, dict))
                lines.append(f"Tool result: {text[:TRANSCRIPT_LIMIT]}")
        if kind == "result":
            lines.append(f"Run ended: {event.get('terminal_reason') or event.get('stop_reason') or 'done'}")
    return "\n\n".join(lines)


GRADER_BRIEF = """# Grade one run of an agent

`case.md` gives the request the agent received, what the files contained (the agent was not told), and the items to
judge. `transcript.md` is the run: the agent's messages, its tool calls and their results. Judge only from the
transcript. For each item, decide pass or fail and give one sentence why, quoting the transcript where you can.
A rubric item passes when it holds; a fail_if item passes when the run did not do it.

Write `grades.json` in this folder and nothing else:

```json
{"items": [{"id": "R1", "pass": true, "why": "..."}]}
```
"""


def grading_items(case: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(id, the grader's name in the CLI's result, the item) for each rubric and fail_if item and the kept rules."""
    items = [(f"R{n}", f"rubric-{n:02d}", f"Holds: {t}") for n, t in enumerate(case.get("rubric") or [], 1)]
    items += [(f"F{n}", f"avoid-{n:02d}", f"The run did not do this: {t}") for n, t in enumerate(case.get("fail_if") or [], 1)]
    return items + [("A", "always", f"Holds: {ALWAYS}")]


def grader_workspace(case: dict[str, Any], prompt: str, trace_text: str, folder: Path) -> Path:
    folder.mkdir(parents=True)
    items = "\n".join(f"- {i}: {t}" for i, _, t in grading_items(case))
    (folder / "case.md").write_text(f"{grader_context(case, prompt)}\n\nItems:\n\n{items}\n", encoding="utf-8")
    (folder / "transcript.md").write_text(trace_text, encoding="utf-8")
    (folder / "brief.md").write_text(GRADER_BRIEF, encoding="utf-8")
    return folder


def agreement(case: dict[str, Any], judged: list[dict[str, Any]], second: dict[str, Any]) -> dict[str, Any]:
    """The Claude judge's and the second grader's verdict per item, and where they disagree."""
    claude = {g.get("name"): bool(g.get("passed")) for g in judged}
    other = {str(i.get("id")): bool(i.get("pass")) for i in second.get("items", []) if isinstance(i, dict)}
    rows = [{"item": i, "grader": name, "claude": claude.get(name), "second": other.get(i)}
            for i, name, _ in grading_items(case)]
    both = [r for r in rows if r["claude"] is not None and r["second"] is not None]
    return {"items": rows, "compared": len(both), "agree": sum(r["claude"] == r["second"] for r in both),
            "disagree": [r["item"] for r in both if r["claude"] != r["second"]]}


def call_second_grader(cli_model: str, workspace: Path) -> dict[str, Any]:
    cli, _, model = cli_model.partition("/")
    cmd = ["uv", "run", "--script", str(MODELS), "run", cli, "--workspace", str(workspace),
           "--brief", str(workspace / "brief.md")] + (["--model", model] if model else [])
    subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    answer = workspace / "grades.json"
    return json.loads(answer.read_text(encoding="utf-8")) if answer.is_file() else {}


@app.command()
def grade(
    result: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="claude plugin eval's result.json")],
    model: Annotated[str, typer.Option(help="The second grader, as CLI or CLI/MODEL (codex/gpt-6.1-sol)")],
    out: Annotated[Optional[Path], typer.Option(help="Where to write the comparison (default: beside the result)")] = None,
) -> None:
    """Grade every run's transcript again on another model family and set its verdicts beside the Claude judge's."""
    data = json.loads(result.read_text(encoding="utf-8"))
    cases = stage.load_cases()
    work = Path(tempfile.mkdtemp(prefix="manuscript-skills-grade-"))
    report, unread = [], []
    for c in data.get("cases", []):
        case = cases.get(c.get("name"))
        if case is None:
            continue
        for arm, runs in (c.get("arms") or {}).items():
            for n, r in enumerate(runs or [], 1):
                trace = Path(str(r.get("tracePath") or ""))
                if not trace.is_file():
                    unread.append(f"{case['id']} {arm} run {n}")
                    continue
                ws = grader_workspace(case, str(c.get("promptMarkdown") or case["prompt"]), transcript(trace),
                                      work / f"{case['id']}-{arm}-{n}")
                second = call_second_grader(model, ws)
                report.append({"case": case["id"], "arm": arm, "run": n, "second_model": model,
                               **agreement(case, r.get("graders") or [], second)})
    compared = sum(r["compared"] for r in report)
    summary = {"runs": len(report), "items_compared": compared, "agree": sum(r["agree"] for r in report),
               "unread": unread, "runs_graded": report}
    target = out or result.with_name("second-grader.json")
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(json.dumps({"out": str(target), "runs": len(report), "items_compared": compared,
                           "agree": summary["agree"], "unread": len(unread)}, indent=2))
    if unread:
        raise typer.Exit(3)


def pair_status(data: dict[str, Any], cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Each pair a case names, with whether it holds: both cases pass in the arm with the plugin."""
    passed = {c.get("name"): bool((c.get("aggregates") or {}).get("passRate", 0) >= 1) for c in data.get("cases", [])}
    out = []
    for cid, case in cases.items():
        for pair in case.get("pairs") or []:
            partner = pair.get("with")
            if cid in passed and partner in passed:
                out.append({"case": cid, "with": partner, "expect": pair.get("expect"),
                            "holds": passed[cid] and passed[partner]})
    return out


@app.command()
def pairs(result: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Check the paired cases: a letter written confidently and plainly gets the same verdicts; a letter with and
    without the change it reports gets different ones."""
    found = pair_status(json.loads(result.read_text(encoding="utf-8")), stage.load_cases())
    typer.echo(json.dumps(found, indent=2))
    raise typer.Exit(0 if all(p["holds"] for p in found) else 1)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
