#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "filelock>=3"]
# ///
"""Inspectable skill runs: source hashes, per-skill evidence, failures and delivery checks.

Use start once, reuse the returned run directory across companion skills, and add new evidence without
overwriting earlier attempts. exec captures a real command's stdout, stderr and exit status. A successful
command does not establish scientific support. validate checks artifacts, not the truth of a report or
whether an agent really showed a passage in chat. validate --final accepts a consequential edit nobody
acknowledged as shown in chat when the newest rendered dashboard shows it (its before/after record, unchanged,
is among the dashboard's evidence), and lists those edits under shown_in_dashboard: in a run the authors were
not present for, the dashboard handed over to them is where they see each edit.

A connected (remote) manuscript is snapshotted through its local reading copy: start --reading-copy FILE
[--connected-version ID], or the reading copy saved with project.py configure. Without one for the main
manuscript, start refuses (exit 3) and creates no run.

validate --final also checks what a finished stage owes the dashboard and the authors: every finding-producing
stage that completed (or partly completed) has RUN/<skill>/findings.json with a `findings` list (an empty list
is valid); manuscript-dashboard, manuscript-other-models, manuscript-mark-people and the coordinator
manuscript-improve write none. A run with manuscript-improve also has the adjudicated inventory
(manuscript-dashboard/findings*.json), the corrected version (manuscript-improve/revision*/proposed*), the
dashboard and its Word version, unless the dashboard or improve stage was finished partial, blocked or not
run with its reason.

A step done again goes to a numbered name (revision.2/, dashboard.2/, findings.2.json), never over the first;
handover and pack take the newest attempt (the highest number, then the newest file).

The run follows the edits and versions settings it started with. Report only (edits: none): change refuses to
record an edit, version refuses to make one, validate fails when a manuscript changed, and an improvement run owes
no corrected version. Immutable versions (versions: immutable): version makes the new file the run's edits go into
(paper_v2.docx -> paper_v3.docx, paper.md -> paper_v2.md, never over an existing file) and names it in the
project's mapping, so the next run reads it; validate fails when an earlier version changed; handover writes a
dated copy beside any different file already there, the dashboard included, and refuses the --replace options.

handover copies the newest dashboard, its Word version, the changes workbook and the corrected version beside the
manuscript as STEM.dashboard.html, STEM.review.docx, STEM.changes.xlsx and STEM.proposed<suffix>; --report SKILL adds a focused run's report
as STEM.<skill without "manuscript-">.md. The dashboard is replaced every run. Any other copy that already
exists and differs (the authors may have worked in it) is kept as it is, and this run's goes beside it under
a dated name (STEM.review.20261024.docx, then -2, -3); --replace-docx, --replace-proposed or --replace
replace it instead. Every copy written is recorded in the manifest.

When the project's `keep` setting is `results`, pack is the run's last step: it moves everything except the
run index, the skills' READMEs and reports, the newest dashboard and Word file and the newest corrected
version into evidence.zip, verifies the archive and only then removes the loose copies; validate checks each
packed file inside the archive, and unpack restores them before a run continues.

Progress records, all optional (a run without them still validates): a stage's entry gets started_at when it
is created (begin RUN --skill NAME creates it before the stage records anything) and finished_at and counts
(findings, proposals, decisions from its newest findings.json) from finish; start --plan writes the stages the
run means to run; stage RUN --name revise|corrected|recheck|handover records the coordinator's own steps under
skills.manuscript-improve.stages; wait RUN --question TEXT says the run stops for the authors, resume that it
goes on.

Exit codes: 0 done; 1 a check failed (validate, finish, pack) or nothing to hand over; 2 a bad option, an
unreadable project file, or an edit, a new version or a replacement the run's settings rule out;
3 the run is busy or packed, or start has no ready project or no reading copy; exec returns its command's.
"""

from __future__ import annotations

import glob
import hashlib
import inspect
import itertools
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from fnmatch import fnmatch
from enum import Enum
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Callable, ParamSpec, TypeVar
from uuid import uuid4

import typer
from filelock import FileLock, Timeout

import project as projects

app = typer.Typer(add_completion=False, no_args_is_help=True)
TERMINAL = {"completed", "partial", "blocked", "not_run", "reused"}
class Role(str, Enum):
    report = 'report'
    reader = 'reader'
    referee = 'referee'
    seat = 'seat'
    defence = 'defence'
    critic = 'critic'  # the deslop reflection loop's critic, a seat like the others
    adjudication = 'adjudication'
    check = 'check'
    comparison = 'comparison'
    failure = 'failure'
    contradiction = 'contradiction'
    input = 'input'
    other = 'other'


ROLES = {role.value for role in Role}
# Outputs of a simulated reader, referee, quick-pass seat or defender: each records how it ran (project-workflow.md,
# "Independent readers and referees").
PANEL = {'reader', 'referee', 'seat', 'defence', 'critic'}


class Isolation(str, Enum):
    fresh_agent = 'fresh-agent'  # a new agent whose whole context was its brief
    one_agent = 'one-agent'  # the fallback: one agent read as each seat in turn; not independent


ISOLATION_LABEL = {'fresh-agent': 'fresh agent', 'one-agent': 'one agent in turn, not independent'}


class Step(str, Enum):
    """The coordinator's own stages, which no other skill records: recorded with `stage` under manuscript-improve."""
    revise = 'revise'  # the review stages' proposals applied to the working copy
    corrected = 'corrected'  # the corrected version built and verified (revise.py into revision/)
    recheck = 'recheck'  # the independent re-check of the corrected version
    handover = 'handover'  # the deliverables copied beside the manuscript


class StepStatus(str, Enum):
    running = 'running'
    completed = 'completed'
    partial = 'partial'
    blocked = 'blocked'
    not_run = 'not_run'


SKILLS = Path(__file__).resolve().parents[2]
ARCHIVE = 'evidence.zip'
# What the authors open after a run (fnmatch patterns; * crosses folders). A step done again writes a numbered
# attempt (revision.2/, dashboard.2/, findings.2.json); the newest attempt of each is the one that counts.
DASHBOARD = 'manuscript-dashboard/*manuscript-dashboard*.html'
WORD = 'manuscript-dashboard/*.docx'
WORKBOOK = 'manuscript-dashboard/*changes*.xlsx'  # the changes workbook export_changes.py writes
CORRECTED = 'manuscript-improve/revision*/proposed*'  # proposed.md, or proposed.tex for a LaTeX manuscript
INVENTORY = 'manuscript-dashboard/findings*.json'  # the adjudicated inventory collect.py writes
# Commands that may run on a packed run; every other writer needs the files back first.
WHEN_PACKED = {'validate', 'pack', 'unpack', 'handover'}
# The deliverables handed over beside the manuscript as STEM + label + the file's own suffix:
# kind -> (pattern in the run, label, whether a different copy already there is simply replaced).
HANDOVER = {'dashboard': (DASHBOARD, '.dashboard', True),  # regenerated each run; nobody writes in it
            'docx': (WORD, '.review', False),  # the authors may have commented in it
            'changes': (WORKBOOK, '.changes', False),  # the authors may have filtered or annotated it
            'corrected': (CORRECTED, '.proposed', False)}  # the authors may have edited it
# Stages that write no findings.json (stage-findings.md): the dashboard reads them (manuscript-visualize is its
# name in older runs), other-models' seats report into the panel that ran them, mark-people writes a people list,
# and the coordinator's findings are the dashboard's adjudicated inventory, which final validation requires.
NO_FINDINGS = {'manuscript-dashboard', 'manuscript-visualize', 'manuscript-other-models', 'manuscript-mark-people',
               'manuscript-improve'}
# A stage finished with one of these, and its reason, is the recorded reason an improvement run lacks a deliverable.
EXCUSED = {'partial', 'blocked', 'not_run'}
# The authors' own version number at the end of a file name: paper_v2, Paper-Rev-04, paper version 3, v7.
VERSION = re.compile(r'(?P<base>(?:.*[\s_.-])?)(?P<tag>v|rev|version)(?P<sep>[\s_.-]?)(?P<number>\d+)', re.IGNORECASE)
P = ParamSpec('P')
T = TypeVar('T')


def serialized(function: Callable[P, T]) -> Callable[P, T]:
    """Fail fast on a concurrent writer; never lose a manifest update or overwrite an attempt."""
    @wraps(function)
    def call(*args: P.args, **kwargs: P.kwargs) -> T:
        arguments = inspect.signature(function).bind(*args, **kwargs).arguments
        run = arguments['run'].resolve()
        try:
            with FileLock(run / '.writer.lock', timeout=0):
                if function.__name__ not in WHEN_PACKED and read(run).get('packed'):
                    typer.echo(f"This run's evidence is packed in {ARCHIVE}; run `runs.py unpack {run}` before "
                               "adding to it. Nothing was changed.", err=True)
                    raise typer.Exit(3)
                return function(*args, **kwargs)
        except Timeout as exc:
            typer.echo(f"Run is busy: {run}. Retry this operation after the active writer finishes; no evidence was overwritten.", err=True)
            raise typer.Exit(3) from exc
    return call


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(run: Path) -> dict[str, Any]:
    return json.loads((run / "run.json").read_text(encoding="utf-8"))


def within(run: Path, relative: str) -> Path:
    path = (run / relative).resolve()
    if not path.is_relative_to(run.resolve()) or path == run.resolve():
        raise ValueError("Evidence paths must stay inside the run directory.")
    return path


# Skills that were renamed: older runs keep the former name, and new records may still be added under it.
FORMER_NAMES = {"manuscript-visualize": "manuscript-dashboard"}


DEFAULT_READERS = {'skimmer', 'potential-user', 'informed-outsider'}


def expected_readers(data: dict[str, Any]) -> set[str]:
    """The story panel's seats: the readers saved for the project when the run started, else the default three."""
    project = data.get('context', {}).get('project')
    saved = project.get('readers') if isinstance(project, dict) else None
    return {re.sub(r"[^a-z0-9]+", "-", str(r).split(":")[0].strip().lower()).strip("-") for r in saved} if saved else DEFAULT_READERS


def skill_name(name: str) -> str:
    if name in FORMER_NAMES:
        return name
    if not re.fullmatch(r"manuscript-[a-z-]+", name) or not (SKILLS / name / "SKILL.md").is_file():
        raise ValueError(f"Unknown manuscript skill: {name}")
    return name


def save(run: Path, data: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=run, delete=False, prefix=".run-") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    Path(handle.name).replace(run / "run.json")
    index = [f"# Manuscript skill run {data['run_id']}", "", f"Started: {data['started_at']}", "",
             "Command exit status and scientific adjudication are separate. Partial and unrun work remains visible.", ""]
    if chosen(data, 'edits') == 'none':
        index.extend(["Report only (edits: none): this run changes no file of the authors.", ""])
    if waiting := data.get('waiting'):
        index.extend([f"**Waiting for the authors** since {waiting['since']}:", "",
                      *(f"- {question}" for question in waiting['questions']), ""])
    if data.get('plan'):
        index.extend([f"Planned stages: {', '.join(data['plan'])}.", ""])
    packed = (data.get('packed') or {}).get('files', {})

    def link(name: str, path: str, text: str | None = None) -> str:
        """A skill README's link to one of its files, or where it is when the run is packed."""
        relative = Path(path).relative_to(name).as_posix()
        return f"{text or relative} (in [{ARCHIVE}](../{ARCHIVE}))" if path in packed else f"[{text or relative}]({relative})"

    for name, seat in data["skills"].items():
        folder = run / name
        folder.mkdir(exist_ok=True)
        lines = [f"# {name}", "", f"Status: **{seat['status']}**. {seat.get('reason', '')}", ""]
        if name == 'manuscript-peer-review':
            lines.append(f"Review mode: {seat.get('review_mode', 'full')}.\n")
        for step, record in seat.get('stages', {}).items():
            lines.append(f"- Stage {step}: **{record['status']}**" + (f". {record['reason']}" if record.get('reason') else ""))
        if seat.get('stages'):
            lines.append("")
        for item in seat["artifacts"]:
            lines.append(f"- {item['role']}: {link(name, item['path'])}" + (f" — seat: {item['seat']}" if item.get('seat') else "")
                         + (f" ({ISOLATION_LABEL[item['isolation']]})" if item.get('isolation') in ISOLATION_LABEL else "")
                         + (f", on {item['model']}" if item.get('model') else ""))
        for issue in seat["issues"]:
            lines.extend(["", f"- **{issue['kind']}**: {issue['message']}"])
        for number, command in enumerate(seat['commands'], 1):
            links = ', '.join(link(name, p, Path(p).name) for p in command['outputs'])
            lines.extend(['', f"- Command {command.get('attempt', number)}: {command.get('state', 'finished')}, exit {command['exit_code']}; {links}"])
        for change in seat["changes"]:
            lines.extend(["", f"- Change: {link(name, change['path'], change['section'])}; "
                          f"shown in chat: {change['shown_in_chat']} (agent attestation)."])
        (folder / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        counted = seat.get('counts')
        index.append(f"- [{name}]({name}/README.md): **{seat['status']}**; {len(seat['issues'])} recorded issue(s)."
                     + (f" {counted['findings']} finding(s), {counted['proposals']} proposal(s), {counted['decisions']} "
                        "decision(s) for the authors." if counted else ""))
    for item in data.get('versions', []):
        index.extend(["", f"New version: {item['new']}, made from {item['previous']}, which is kept as it was."])
    for location in data.get('not_snapshotted', []):
        index.extend(["", f"Not snapshotted: {location}, a connected document with no local reading copy in this run."])
    for item in data.get('handover', []):
        kept = (f"; the different {Path(item['kept']).name} already there was kept as it was" if item.get('kept') else "")
        index.extend(["", f"Handed over beside the manuscript: {item['path']} (from {item['from']}, {item['handed_over_at']}{kept})."])
    if packed:
        index.extend(["", (f"The evidence ({len(packed)} files) is packed in [{ARCHIVE}]({ARCHIVE}), as the project's "
                           "`keep` setting asks; `runs.py unpack` restores it.")])
    index.extend(["", "[Run manifest](run.json) contains effective settings, source hashes and all recorded attempts."])
    (run / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


def chosen(data: dict[str, Any], key: str) -> str | None:
    """The run's effective setting, as start resolved it (None in a run from before the setting existed)."""
    return data.get('context', {}).get('effective', {}).get(key)


def ensure_skill(data: dict[str, Any], name: str, at: str | None = None) -> dict[str, Any]:
    """A stage's entry; one created now starts now (at AT when given), so the progress view can time it."""
    skill_name(name)
    if name not in data["skills"]:
        data["skills"][name] = {"status": "running", "started_at": at or now(), "artifacts": [], "issues": [],
                                "changes": [], "commands": []}
    return data["skills"][name]


def planned(names: list[str]) -> list[str]:
    """The stages a run means to run, in order: skills, and the coordinator's own steps (revise, corrected, ...)."""
    for name in names:
        if name not in {step.value for step in Step}:
            try:
                skill_name(name)
            except ValueError as exc:
                raise typer.BadParameter(f"{exc}; a planned stage is a manuscript skill or one of the coordinator's "
                                         f"steps ({', '.join(step.value for step in Step)}).") from exc
    return list(dict.fromkeys(names))


def artifact(run: Path, data: dict[str, Any], name: str, source: Path, role: str,
             destination: str | None = None, seat: str | None = None, allow_empty: bool = False,
             isolation: str | None = None, model: str | None = None) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"Unknown evidence role: {role}")
    if role in PANEL and isolation not in ISOLATION_LABEL:
        raise ValueError(f"A {role} output records how it ran: --isolation fresh-agent (a new agent whose only context "
                         "was its brief) or --isolation one-agent (the fallback when the host cannot start agents).")
    if not source.is_file() or (not allow_empty and not source.stat().st_size):
        raise ValueError("Evidence must be a non-empty file.")
    entry = ensure_skill(data, name)
    target = within(run, f"{name}/{destination or source.name}")
    if not target.is_relative_to((run / name).resolve()) or target == (run / name / "README.md").resolve():
        raise ValueError("Use an evidence filename inside its skill folder; its root README.md is the generated status index.")
    if any(item['path'] == (relative := target.relative_to(run.resolve()).as_posix()) for item in entry['artifacts']):
        raise ValueError(f"{relative} is already registered; give this file its own path in the skill's folder with "
                         "--name (figures/figure-3/view.png), or save the next attempt under a new filename.")
    if target != source.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
    item = {"path": target.relative_to(run.resolve()).as_posix(), "role": role, "seat": seat,
            "sha256": digest(target), "recorded_at": now()}
    if model:  # the model that produced it, as manuscript-other-models names it: codex/gpt-5.6-sol
        item["model"] = model
    if role in PANEL:
        item["isolation"] = isolation
        if isolation == 'one-agent':
            entry['issues'].append({'kind': 'not_independent', 'recorded_at': now(), 'message':
                f"{seat or role}: read by one agent in turn, not independent; its agreement with other seats is not corroboration."})
    entry['artifacts'].append(item)
    return item


def archived(run: Path, data: dict[str, Any]) -> dict[str, str]:
    """In a packed run, the sha256 of every file in its archive, read back from the archive itself."""
    packed = data.get('packed')
    path = within(run, packed['archive']) if packed else None
    if path is None or not path.is_file():
        return {}
    try:
        with zipfile.ZipFile(path) as archive:
            return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()}
    except (zipfile.BadZipFile, OSError):
        return {}


def stored_body(run: Path, data: dict[str, Any], relative: str) -> bytes | None:
    """A file of the run, from disk or from the evidence archive of a packed run; None when it is in neither."""
    path = run / relative
    if path.is_file():
        return path.read_bytes()
    packed = data.get('packed')
    if packed and relative in packed.get('files', {}):
        try:
            with zipfile.ZipFile(within(run, packed['archive'])) as archive:
                return archive.read(relative)
        except (zipfile.BadZipFile, KeyError, OSError):
            return None
    return None


ATTEMPT = re.compile(r"[.-](\d{1,3})$")  # revision.2, dashboard-3; never a date such as 20261024
EXTENSION = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,4}$")


def attempt(relative: str) -> int:
    """The attempt a run file belongs to: the largest number that ends a folder or file name on its path
    (revision.2/proposed.md, manuscript-dashboard.2.html, findings.2.json); 1 when none does."""
    numbers = [1]
    for part in PurePosixPath(relative).parts:
        while EXTENSION.search(part):
            part = EXTENSION.sub('', part)
        if match := ATTEMPT.search(part):
            numbers.append(int(match.group(1)))
    return max(numbers)


def matching(run: Path, pattern: str, data: dict[str, Any] | None = None) -> list[str]:
    """The run's files matching pattern, oldest attempt first (the attempt number, then the time written); with
    data, the files packed in the evidence archive count too, as older than any file on disk of their attempt."""
    found = {p.relative_to(run).as_posix(): p.stat().st_mtime_ns for p in run.rglob('*') if p.is_file()}
    found = {relative: when for relative, when in found.items() if fnmatch(relative, pattern)}
    for relative in ((data or {}).get('packed') or {}).get('files', {}):
        if fnmatch(relative, pattern):
            found.setdefault(relative, -1)
    return sorted(found, key=lambda relative: (attempt(relative), found[relative], relative))


def latest(run: Path, pattern: str) -> Path | None:
    """The newest attempt on disk matching pattern: a re-render goes to a numbered folder or name."""
    found = matching(run, pattern)
    return run / found[-1] if found else None


def newest_deliverables(run: Path) -> set[str]:
    """The files pack leaves in place for the authors: the newest dashboard, the newest Word file and changes
    workbook, and the corrected version and its track changes from the newest revision attempt."""
    keep = {found[-1] for pattern in (DASHBOARD, WORD, WORKBOOK) if (found := matching(run, pattern))}
    if corrected := matching(run, CORRECTED):
        folder = PurePosixPath(corrected[-1]).parent
        keep |= {corrected[-1], (folder / 'changes.md').as_posix()}
    return keep


FINDINGS_FILE = re.compile(r"findings(?:\.\d{1,3})?\.json$")  # findings.json, findings.2.json; never findings.draft.json


def findings_files(run: Path, data: dict[str, Any], folder: str) -> list[str]:
    """A stage's findings.json attempts directly in its folder, oldest first."""
    return [relative for relative in matching(run, f'{folder}/findings*.json', data)
            if PurePosixPath(relative).parent.as_posix() == folder and FINDINGS_FILE.fullmatch(PurePosixPath(relative).name)]


def newest_findings(run: Path, data: dict[str, Any], name: str) -> dict[str, Any] | str:
    """A stage's newest findings.json, read; or, as a string, why it cannot be counted."""
    attempts = findings_files(run, data, name)
    body = stored_body(run, data, attempts[-1] if attempts else f'{name}/findings.json')
    if body is None:
        return (f"{name}: no findings.json beside its report; write it even when nothing was found (an empty "
                "findings list, with what could not be checked under not_checked)")
    try:
        record = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"{name}: findings.json is not valid JSON ({exc})"
    if not isinstance(record, dict) or not isinstance(record.get('findings'), list):
        return f"{name}: findings.json has no findings list (an empty list is valid)"
    return record


def findings_problem(run: Path, data: dict[str, Any], name: str) -> str | None:
    """Why a finished stage's newest findings.json cannot be counted; None when it holds a findings list."""
    found = newest_findings(run, data, name)
    return found if isinstance(found, str) else None


def findings_counts(run: Path, data: dict[str, Any], name: str) -> dict[str, int] | None:
    """What a stage's newest findings.json holds, as the progress view counts it: its findings, its proposals
    (`changes`) and the findings only the authors can decide (`decision: true`); None without a readable one."""
    found = newest_findings(run, data, name)
    if isinstance(found, str):
        return None
    changes = found.get('changes')
    return {'findings': len(found['findings']), 'proposals': len(changes) if isinstance(changes, list) else 0,
            'decisions': sum(1 for item in found['findings'] if isinstance(item, dict) and item.get('decision') is True)}


def dashboard_shows(run: Path, data: dict[str, Any]) -> set[tuple[str, str]]:
    """The before/after records the newest rendered dashboard shows as diffs, each as (path, sha256): its
    summary.json lists every evidence file it read with the hash it had, paths relative to manuscript-dashboard/."""
    dashboards = matching(run, DASHBOARD, data)
    body = stored_body(run, data, (PurePosixPath(dashboards[-1]).parent / 'summary.json').as_posix()) if dashboards else None
    try:
        listed = json.loads(body.decode('utf-8')).get('evidence_sha256') if body else None
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        listed = None
    if not isinstance(listed, dict):
        return set()
    return {(posixpath.normpath(f'manuscript-dashboard/{path}'), sha) for path, sha in listed.items()}


def shown_in_dashboard(run: Path, data: dict[str, Any]) -> list[str]:
    """The consequential edits nobody acknowledged as shown in chat that the dashboard shows, as it hands them over."""
    shown = dashboard_shows(run, data)
    return [f"{name}: {change['section']} ({change['path']})" for name, entry in data['skills'].items()
            for change in entry['changes'] if not change['shown_in_chat'] and (change['path'], change['sha256']) in shown]


def improvement_problems(run: Path, data: dict[str, Any]) -> list[str]:
    """What an improvement run owes the authors at the end, unless the dashboard or improve stage recorded why not."""
    stages = data['skills']
    if any(stages.get(name, {}).get('status') in EXCUSED for name in ('manuscript-dashboard', 'manuscript-improve')):
        return []  # its finish --reason says what is missing and why
    owed = ((INVENTORY, "the adjudicated inventory", "collect and adjudicate the stages' findings (collect.py)"),
            (CORRECTED, "the corrected version", "build it with revise.py"),
            (DASHBOARD, "the rendered dashboard", "render it with dashboard.py"),
            (WORD, "the Word version of the dashboard", "export it with export_docx.py"))
    if chosen(data, 'edits') == 'none':  # report only: no corrected version is written
        owed = tuple(item for item in owed if item[0] != CORRECTED)
    return [f"manuscript-improve: {what} is missing ({pattern}); {how}, or finish manuscript-dashboard or "
            "manuscript-improve as partial or blocked with the reason"
            for pattern, what, how in owed
            if not (findings_files(run, data, 'manuscript-dashboard') if pattern == INVENTORY else matching(run, pattern, data))]


def problems(run: Path, data: dict[str, Any], final: bool = False) -> list[str]:
    errors = []
    packed = archived(run, data)
    if data.get('packed') and not packed:
        errors.append(f"Missing or unreadable evidence archive: {data['packed']['archive']}")

    def stored(path: Path) -> str | None:
        """The file's sha256, on disk or in the archive; None when it is in neither."""
        return digest(path) if path.is_file() else packed.get(path.relative_to(run.resolve()).as_posix())

    explained = any(s['changes'] or s.get('routine_only_reason') for s in data['skills'].values())
    # An edit the authors were not there to see in chat (agents ran the stages, the authors were away) reaches them
    # in the dashboard, which shows each recorded edit as a diff with its reason; validate lists those edits.
    in_dashboard = dashboard_shows(run, data) if final else set()
    report_only, immutable = chosen(data, 'edits') == 'none', chosen(data, 'versions') == 'immutable'
    for source in data['inputs']:
        path = within(run, source['snapshot'])
        if stored(path) != source['sha256']:
            errors.append(f"Missing or changed source snapshot: {source['snapshot']}")
        original = Path(source['original'])
        if source.get('remote'):  # a connected document: its reading copy may be exported again or removed
            if original.is_file() and digest(original) != source['sha256'] and not explained:
                errors.append(f"The reading copy of {source['remote']} changed without a change record or "
                              f"routine-only explanation: {original}")
            continue
        if not original.is_file():
            errors.append(f"Authoritative source is missing or no longer a file: {original}")
        elif digest(original) != source['sha256']:
            if report_only:
                errors.append(f"Manuscript changed in a report-only run (edits: none), which changes no file: {original}")
            elif immutable:
                errors.append(f"An earlier version changed although versions are immutable: {original}; the run's "
                              "edits belong in the new version that `runs.py version` makes")
            elif not explained:
                errors.append(f"Manuscript changed without a change record or routine-only explanation: {original}")
    inputs = {source['original'] for source in data['inputs']}
    for item in data.get('versions', []):
        previous, new = Path(item['previous']), Path(item['new'])
        if item['previous'] not in inputs and immutable and (not previous.is_file() or digest(previous) != item['sha256']):
            errors.append(f"An earlier version changed although versions are immutable: {previous}")
        if not new.is_file():
            errors.append(f"The new version is missing: {new}")
        elif digest(new) != item['sha256'] and not explained:
            errors.append(f"The new version changed without a change record or routine-only explanation: {new}")
    for name, entry in data['skills'].items():
        if final and entry['status'] not in TERMINAL:
            errors.append(f"{name}: still {entry['status']}")
        for item in entry['artifacts']:
            try:
                path = within(run, item['path'])
            except ValueError as exc:
                errors.append(f"{name}: {exc}")
                continue
            if stored(path) != item['sha256']:
                errors.append(f"Missing or changed evidence: {item['path']}")
        roles = [item['role'] for item in entry['artifacts']]
        if entry['status'] in TERMINAL - {'not_run'} and 'report' not in roles:
            errors.append(f"{name}: no saved report")
        if entry['status'] in {'completed', 'partial'} and name not in NO_FINDINGS:
            if problem := findings_problem(run, data, name):  # the dashboard counts the run from these files
                errors.append(problem)
        if entry['status'] in {'partial', 'blocked', 'not_run', 'reused'} and not entry.get('reason'):
            errors.append(f"{name}: status needs its reason/coverage or reused source")
        if entry['status'] == 'completed':
            for item in entry['artifacts']:
                if item['role'] in PANEL and item.get('isolation') not in ISOLATION_LABEL:
                    errors.append(f"{name}: {item['path']} does not record whether it ran as a fresh agent (--isolation)")
            if name == 'manuscript-story':
                seats = {item['seat'] for item in entry['artifacts'] if item['role'] == 'reader'}
                if not expected_readers(data) <= seats:
                    errors.append(f"{name}: missing independent reader reports ({', '.join(sorted(expected_readers(data) - seats))})")
            if name == 'manuscript-peer-review':
                if entry.get('review_mode', 'full') == 'quick':
                    seats = {item['seat'] for item in entry['artifacts'] if item['role'] == 'seat'}
                    if not {'desk-editor', 'evidence-statistics'} <= seats or not {'defence', 'adjudication'} <= set(roles):
                        errors.append(f"{name}: quick pass needs desk-editor and evidence-statistics findings, defence and adjudication")
                else:
                    seats = {item['seat'] for item in entry['artifacts'] if item['role'] == 'referee' and item['seat']}
                    if len(seats) < 3 or not {'defence', 'adjudication'} <= set(roles):
                        errors.append(f"{name}: needs three referee reports, defence and adjudication")
            if any(command.get('state') == 'running' for command in entry['commands']):
                errors.append(f"{name}: a command has no recorded completion")
        for change in entry['changes']:
            path = within(run, change['path'])
            if stored(path) != change['sha256']:
                errors.append(f"Missing or changed before/after: {change['path']}")
            if final and not change['shown_in_chat'] and (change['path'], change['sha256']) not in in_dashboard:
                errors.append(f"{name}: consequential change neither acknowledged as shown in chat nor shown in the "
                              f"rendered dashboard: {change['section']}")
    if final and 'manuscript-improve' in data['skills']:
        errors.extend(improvement_problems(run, data))
    return errors


def reading_copies(ctx: dict[str, Any], given: list[Path], versions: list[str]) -> dict[str, dict[str, Any]]:
    """For each connected manuscript, its local reading copy (given here, in the order of the connected sources,
    else saved with project.py configure) and the connected version when one was given."""
    root = Path(ctx['project_root'])
    remote = [location for location in ctx['project']['manuscripts'] if projects.is_remote(location)]
    if len(given) > len(remote) or len(versions) > len(remote):
        raise typer.BadParameter(f"The project has {len(remote)} connected manuscript(s); give at most one "
                                 "--reading-copy and one --connected-version for each, in the order they are listed.")
    saved = ctx['project'].get('reading_copies', {})
    copies = {}
    for number, url in enumerate(remote):
        path = (given[number].expanduser().resolve() if number < len(given)
                else projects.local_path(root, saved[url]) if url in saved else None)
        if path is not None:
            copies[url] = {'path': path} | ({'connected_version': versions[number]} if number < len(versions) else {})
    return copies


@app.command()
def start(target: str, skill: Annotated[list[str], typer.Option("--skill")], project: Path | None = None,
          reports: str | None = None, edits: str | None = None, versions: str | None = None,
          keep: str | None = None, peer_review: str | None = None,
          reading_copy: Annotated[list[Path] | None, typer.Option(
              '--reading-copy', help="A local export of a connected (URL) manuscript, snapshotted in its place; one "
                                     "per connected manuscript, in the project's order; repeat")] = None,
          connected_version: Annotated[list[str] | None, typer.Option(
              '--connected-version', help="The connected document's version or revision the reading copy was "
                                          "exported from, in the same order; repeat")] = None,
          plan: Annotated[list[str] | None, typer.Option(
              '--plan', help="A stage this run means to run, in order: a skill, or one of the coordinator's steps "
                             "(revise, corrected, recheck, handover); repeat")] = None) -> None:
    """Start a unique run under the saved destination. Print its absolute directory; never overwrite a run.

    A connected (URL) manuscript is snapshotted through its reading copy; without one for the main manuscript,
    start creates no run and exits 3. Each --skill starts with the run; --plan names the stages it means to run,
    so a progress view knows how many there are and which are skipped before it reaches them."""
    overrides = {k: v for k, v in {'reports': reports, 'edits': edits, 'versions': versions, 'keep': keep,
                                    'peer_review': peer_review}.items() if v is not None}
    try:
        ctx = projects.context(target, project, overrides)
    except projects.ProjectError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    if ctx['status'] != 'ready':
        typer.echo(json.dumps(ctx, indent=2, ensure_ascii=False))
        raise typer.Exit(3)
    for name in skill:
        skill_name(name)
    stages = planned(list(plan or []))
    manuscripts = ctx['project']['manuscripts']
    copies = reading_copies(ctx, list(reading_copy or []), list(connected_version or []))
    if absent := [f"{copy['path']} (for {url})" for url, copy in copies.items() if not copy['path'].is_file()]:
        typer.echo(f"Reading copy not found: {'; '.join(absent)}. Export the connected document to that file "
                   "first. No run was created.", err=True)
        raise typer.Exit(3)
    if projects.is_remote(manuscripts[0]) and manuscripts[0] not in copies:
        typer.echo(f"The manuscript is a connected document ({manuscripts[0]}) with no local reading copy, so "
                   "the run would have nothing to read or snapshot. Export it (Markdown or plain text keeps the "
                   "dashboard readable) and start again with --reading-copy FILE, adding --connected-version ID "
                   "when the service shows the version, or save where the export is kept with `project.py "
                   "configure PROJECT --reading-copy FILE`. No run was created.", err=True)
        raise typer.Exit(3)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    run = Path(ctx['output_dir']) / run_id
    run.mkdir(parents=True)
    data = {'schema_version': 1, 'run_id': run_id, 'started_at': now(), **({'plan': stages} if stages else {}),
            'context': ctx, 'inputs': [], 'skills': {}}
    for number, location in enumerate(manuscripts, 1):
        extra: dict[str, Any] = {}
        if projects.is_remote(location):
            if location not in copies:  # a connected supplement without a reading copy: said in the run index
                data.setdefault('not_snapshotted', []).append(location)
                continue
            source = copies[location]['path']
            extra = {'remote': location} | {k: v for k, v in copies[location].items() if k == 'connected_version'}
        else:
            source = projects.local_path(Path(ctx['project_root']), location)
        dest = run / 'inputs' / f'{number:02d}-{source.name}'
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, dest)
        data['inputs'].append({'original': source.as_posix(), 'snapshot': dest.relative_to(run).as_posix(),
                               'sha256': digest(dest)} | extra)
    for name in skill:
        ensure_skill(data, name, at=data['started_at'])
    save(run, data)
    typer.echo(str(run))


@app.command()
@serialized
def begin(run: Path, skill: Annotated[str, typer.Option('--skill')],
          plan: Annotated[list[str] | None, typer.Option(
              '--plan', help="Replace the stages this run means to run (as start --plan); repeat")] = None) -> None:
    """Record that a stage starts now, before it has anything to record, so its time is known from its start.

    Idempotent: a stage that already has a start keeps it. --plan, from the coordinator, replaces the run's plan
    once it knows which stages the run will take."""
    run = run.resolve()
    data = read(run)
    try:
        entry = ensure_skill(data, skill)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    entry.setdefault('started_at', now())  # an entry from before start times were recorded
    if plan:
        data['plan'] = planned(plan)
    save(run, data)
    typer.echo(str(run / skill))


@app.command()
@serialized
def add(run: Path, skill: Annotated[str, typer.Option('--skill')],
        file: Annotated[Path, typer.Option('--file')], role: Role = Role.other,
        name: str | None = None, seat: str | None = None, isolation: Isolation | None = None,
        model: Annotated[str | None, typer.Option(help="The model that produced it, e.g. codex/gpt-5.6-sol")] = None) -> None:
    """Retain an actual output with its role. --seat identifies a reader or referee, --isolation says whether it
    ran as a fresh agent and --model which model read it; files cannot be overwritten."""
    run = run.resolve()
    data = read(run)
    if role.value in PANEL and isolation is None:
        raise typer.BadParameter(f"A {role.value} output records how it ran: --isolation fresh-agent (a new agent whose only "
                                 "context was its brief) or --isolation one-agent (the fallback when the host cannot start agents).")
    item = artifact(run, data, skill, file, role.value, name, seat, isolation=isolation.value if isolation else None,
                    model=model.strip() if model and model.strip() else None)
    save(run, data)
    typer.echo(str(run / item['path']))


@app.command('exec', context_settings={'allow_extra_args': True, 'ignore_unknown_options': True})
@serialized
def execute(ctx: typer.Context, run: Path, skill: Annotated[str, typer.Option('--skill')], cwd: Path | None = None) -> None:
    """Capture a real command: exec RUN --skill NAME -- PROGRAM ARGS. Preserve failures and return its exit code.

    The command runs where exec was called, so relative paths mean what they mean to the caller; --cwd
    runs it elsewhere. The directory is recorded with the attempt."""
    if not ctx.args:
        raise typer.BadParameter('Supply a command after --.')
    run = run.resolve()
    data = read(run)
    entry = ensure_skill(data, skill)
    folder = run / skill / 'commands'
    folder.mkdir(parents=True, exist_ok=True)
    known = {item['path'] for item in entry['artifacts']}
    previous = sorted(folder.glob('*.txt'))
    for command in entry['commands']:
        if command.get('state') == 'running':
            command['state'] = 'interrupted'
            entry['issues'].append({'kind': 'interrupted_attempt', 'message': f"Prior command attempt {command['attempt']} has no completion record; its original exit status is unknown.", 'recorded_at': now()})
    for output in previous:
        relative = output.relative_to(run).as_posix()
        if relative not in known:
            artifact(run, data, skill, output, 'check', f'commands/{output.name}', allow_empty=True)
            entry['issues'].append({'kind': 'interrupted_attempt', 'message': f"Recovered an unregistered command log: {relative}; original exit status is unknown.", 'recorded_at': now()})
    numbers = [int(p.name.split('.')[0]) for p in previous if p.name.split('.')[0].isdigit()]
    number = max([len(entry['commands']), *numbers]) + 1
    working = (cwd or Path.cwd()).resolve()
    stdout_path, stderr_path = (folder / f'{number:04d}.{label}.txt' for label in ('stdout', 'stderr'))
    command = {'attempt': number, 'argv': ctx.args, 'cwd': working.as_posix(), 'state': 'running',
               'exit_code': None, 'outputs': [p.relative_to(run).as_posix() for p in (stdout_path, stderr_path)], 'recorded_at': now()}
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        entry['commands'].append(command)
        save(run, data)
        try:
            result = subprocess.run(ctx.args, cwd=working, stdout=stdout, stderr=stderr, check=False)
            code = result.returncode
        except OSError as exc:
            stderr.write(str(exc).encode('utf-8'))
            code = 127
    for output in (stdout_path, stderr_path):
        artifact(run, data, skill, output, 'check', f'commands/{output.name}', allow_empty=True)
    command.update(state='finished', exit_code=code, finished_at=now())
    if code:
        entry['issues'].append({'kind': 'command_failure', 'message': f"Command attempt {number} exited {code}; inspect its saved stdout/stderr.", 'recorded_at': now()})
    save(run, data)
    typer.echo(f"Exit {code}; outputs: {run / skill / 'commands'}")
    raise typer.Exit(code if 0 <= code <= 255 else 1)


@app.command()
@serialized
def isolation(run: Path, skill: Annotated[str, typer.Option('--skill')], path: Annotated[str, typer.Option('--path')],
              isolation: Annotated[Isolation, typer.Option('--isolation')],
              basis: Annotated[str, typer.Option('--basis', help='What shows how it ran: a manifest note, the briefs')]) -> None:
    """Record how a reader, referee, seat or defence output already in the run was produced, for a run registered
    before outputs had to say it. Only a missing record is filled, with its basis and date; one already recorded
    is never changed."""
    data = read(run)
    entry = ensure_skill(data, skill)
    item = next((a for a in entry['artifacts'] if a['path'] == path), None)
    if item is None or item['role'] not in PANEL:
        raise typer.BadParameter(f"{path} is not a reader, referee, seat or defence output of {skill} in this run.")
    if item.get('isolation') in ISOLATION_LABEL:
        raise typer.BadParameter(f"{path} already records how it ran ({ISOLATION_LABEL[item['isolation']]}).")
    item['isolation'] = isolation.value
    item['isolation_recorded'] = {'recorded_at': now(), 'basis': basis}
    entry['issues'].append({'kind': 'isolation_recorded_later', 'recorded_at': now(),
                            'message': f"{path}: recorded later as {ISOLATION_LABEL[isolation.value]}. Basis: {basis}"})
    if isolation == Isolation.one_agent:
        entry['issues'].append({'kind': 'not_independent', 'recorded_at': now(), 'message':
            f"{item.get('seat') or item['role']}: read by one agent in turn, not independent; its agreement with other seats is not corroboration."})
    save(run, data)


@app.command()
@serialized
def issue(run: Path, skill: Annotated[str, typer.Option('--skill')],
          kind: Annotated[str, typer.Option('--kind')], message: Annotated[str, typer.Option('--message')]) -> None:
    """Record a contradiction, blocked source, failed check or later resolution without erasing earlier evidence."""
    data = read(run)
    ensure_skill(data, skill)['issues'].append({'kind': kind, 'message': message, 'recorded_at': now()})
    save(run, data)


@app.command()
@serialized
def change(run: Path, skill: Annotated[str, typer.Option('--skill')],
           section: Annotated[str, typer.Option('--section')], reason: Annotated[str, typer.Option('--reason')], before: Path | None = None,
           after: Path | None = None, shown_in_chat: bool = False,
           comment: Annotated[str, typer.Option(help="A question for the authors about this edit; never put it in the text")] = "") -> None:
    """Save exact consequential before/after text. Omit before for an addition, after for a deletion."""
    if before is None and after is None:
        raise typer.BadParameter('Supply before, after, or both.')
    data = read(run)
    if chosen(data, 'edits') == 'none':
        typer.echo("This run is report only (edits: none): it changes no file, so there is no edit to record. Put the "
                   "fix in the finding instead: the passage, what is wrong and the kind of change.", err=True)
        raise typer.Exit(2)
    entry = ensure_skill(data, skill)
    relative = f"{skill}/changes/{len(entry['changes']) + 1:04d}.md"
    path = within(run, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"# {section}\n\nReason: {reason}\n\n" + (f"Comment: {' '.join(comment.split())}\n\n" if comment.strip() else "") + "## Before\n\n"
    text += before.read_text(encoding='utf-8') if before else '(No previous block.)\n'
    text += '\n\n## After\n\n'
    text += after.read_text(encoding='utf-8') if after else '(Block removed.)\n'
    with path.open('x', encoding='utf-8') as output:
        output.write(text)
    entry['changes'].append({'section': section, 'path': relative, 'sha256': digest(path), 'shown_in_chat': shown_in_chat,
                             'recorded_at': now()})
    save(run, data)
    typer.echo(str(path))


@app.command()
@serialized
def shown(run: Path, skill: Annotated[str, typer.Option('--skill')],
          number: Annotated[int, typer.Option('--number')]) -> None:
    """Attest that an existing before/after was shown in chat; does not itself send a message."""
    data = read(run)
    changes = ensure_skill(data, skill)['changes']
    if not 1 <= number <= len(changes):
        raise typer.BadParameter('No change with that number.')
    changes[number - 1]['shown_in_chat'] = True
    save(run, data)


@app.command()
@serialized
def finish(run: Path, skill: Annotated[str, typer.Option('--skill')],
           status: Annotated[str, typer.Option('--status')], reason: str = '', routine_only_reason: str = '',
           review_mode: str | None = None) -> None:
    """Set honest coverage. Completed requires a report, the skill's reader/referee evidence and, for a
    finding-producing skill, RUN/SKILL/findings.json with a findings list (partial needs it too).

    Records when the stage finished and, from its newest findings.json, how many findings, proposals and
    decisions for the authors it has."""
    if status not in TERMINAL:
        raise typer.BadParameter(f"Choose {', '.join(sorted(TERMINAL))}.")
    data = read(run)
    skipped = status == 'not_run' and skill not in data['skills']
    entry = ensure_skill(data, skill)
    if skipped:  # a stage the run never began has no start
        del entry['started_at']
    if review_mode is not None:
        if skill != 'manuscript-peer-review' or review_mode not in {'full', 'quick', 'invited'}:
            raise typer.BadParameter('review-mode is full, quick or invited and applies only to peer review.')
        entry['review_mode'] = review_mode
    entry.update(status=status, reason=reason, routine_only_reason=routine_only_reason, finished_at=now())
    errors = problems(run, data)
    if errors:
        typer.echo('\n'.join(errors), err=True)
        raise typer.Exit(1)
    if (counted := findings_counts(run, data, skill)) is not None:
        entry['counts'] = counted
    else:
        entry.pop('counts', None)  # none from an earlier finish outlives the findings file it counted
    save(run, data)
    typer.echo(str(run / skill / 'README.md'))


@app.command()
@serialized
def stage(run: Path, name: Annotated[Step, typer.Option('--name')], status: Annotated[StepStatus, typer.Option('--status')],
          reason: Annotated[str, typer.Option(help="Coverage, the obstacle or why it was skipped; needed for "
                                                   "partial, blocked and not_run")] = '') -> None:
    """Record one of the coordinator's own stages (revise, corrected, recheck, handover) under manuscript-improve,
    as the other stages are recorded: running when it starts, then its outcome.

    A stage started again keeps its first start; a skipped one (not_run) needs no start."""
    if status.value in EXCUSED and not reason.strip():
        raise typer.BadParameter(f"A {status.value} stage needs --reason: the coverage, the obstacle or why it was skipped.")
    run = run.resolve()
    data = read(run)
    record = ensure_skill(data, 'manuscript-improve').setdefault('stages', {}).setdefault(
        name.value, {'status': None, 'started_at': None, 'finished_at': None, 'reason': ''})
    if status == StepStatus.running:
        record.update(started_at=record.get('started_at') or now(), finished_at=None)
    else:
        record['finished_at'] = now()
    record.update(status=status.value, reason=' '.join(reason.split()))
    save(run, data)
    typer.echo(f"{name.value}: {status.value}")


@app.command()
@serialized
def wait(run: Path, question: Annotated[list[str], typer.Option(
        '--question', help="A question only the authors can answer; repeat")]) -> None:
    """Record that the run stops for the authors' answers. Asked again while it waits, the new questions are added
    and the time it began waiting stays. `resume` records that it goes on."""
    asked = list(dict.fromkeys(' '.join(text.split()) for text in question if text.strip()))
    if not asked:
        raise typer.BadParameter('Give the question the run waits on with --question TEXT.')
    run = run.resolve()
    data = read(run)
    waiting = data.get('waiting') or {'since': now(), 'questions': []}
    waiting['questions'] += [text for text in asked if text not in waiting['questions']]
    data['waiting'] = waiting
    save(run, data)
    typer.echo(f"Waiting for the authors since {waiting['since']}: {len(waiting['questions'])} question(s).")


@app.command()
@serialized
def resume(run: Path) -> None:
    """Record that the run goes on after waiting for the authors: clears what `wait` recorded."""
    run = run.resolve()
    data = read(run)
    if not data.pop('waiting', None):
        typer.echo('This run was not waiting for the authors; nothing was changed.')
        return
    save(run, data)
    typer.echo('The run goes on.')


@app.command()
@serialized
def validate(run: Path, final: bool = False) -> None:
    """Check evidence and final handover. Scientific correctness and actual chat delivery still need review."""
    data = read(run)
    errors = problems(run, data, final)
    complete = all(s['status'] in {'completed', 'reused'} for s in data['skills'].values())
    report = {'valid': not errors, 'workflow_complete': complete and not errors, 'problems': errors,
              'index': str(run.resolve() / 'README.md')}
    if final and (dashboard_only := shown_in_dashboard(run, data)):
        report['shown_in_dashboard'] = dashboard_only  # not in chat: the authors see these in the dashboard
    typer.echo(json.dumps(report, indent=2))
    if errors:
        raise typer.Exit(1)


def next_version(path: Path) -> Path:
    """Where the next version of PATH goes, beside it and never over an existing file: the authors' own version
    number counted on (paper_v2.docx -> paper_v3.docx, Paper-Rev-04.tex -> Paper-Rev-05.tex), else a first one
    added in the style of the name (paper.md -> paper_v2.md, my-paper.md -> my-paper-v2.md)."""
    stem = path.stem
    if found := VERSION.fullmatch(stem):
        base, number, width = found['base'] + found['tag'] + found['sep'], int(found['number']) + 1, len(found['number'])
    else:
        separator = '-' if '-' in stem and '_' not in stem else ' ' if ' ' in stem and '_' not in stem else '_'
        base, number, width = f'{stem}{separator}v', 2, 1
    while (candidate := path.with_name(f'{base}{number:0{width}d}{path.suffix}')).exists():
        number += 1
    return candidate


def remap(data: dict[str, Any], previous: Path, new: Path) -> str | None:
    """Name the new version in the project's mapping in place of the previous one, so that the next run reads
    it. Returns the project file it changed, or None when PREVIOUS is not one of the project's manuscripts."""
    saved = data.get('context', {}).get('project_file')
    path = Path(saved) if saved else None
    if path is None or not path.is_file():
        return None
    project = projects.read(path)
    sources = project.get('manuscripts', [])
    for number, location in enumerate(sources):
        if not projects.is_remote(location) and projects.local_path(path.parent, location) == previous:
            sources[number] = projects.stored_location(path.parent, str(new))
            projects.write(path, project)
            return path.as_posix()
    return None


@app.command()
@serialized
def version(run: Path, file: Annotated[Path | None, typer.Option(
                help="The file the run is about to change: a supplement or bibliography; default: the manuscript")] = None) -> None:
    """Make the new version this run's edits go into, beside the file and never over one, and print its path.

    For versions: immutable. The file itself stays as it was; asked again for the same file, this prints the same
    new version. The project's mapping then names the new version, so the next run reads it. A report-only run
    (edits: none) changes no file and gets no version."""
    data = read(run)
    if chosen(data, 'edits') == 'none':
        typer.echo("This run is report only (edits: none): it changes no file, so it makes no new version.", err=True)
        raise typer.Exit(2)
    if file is None:
        source = data['inputs'][0] if data['inputs'] else None
        if source is None or source.get('remote'):
            typer.echo("The manuscript is a connected document (or the run has no snapshot of it): its own service "
                       "keeps its versions. Give --file for a local file the run is about to change.", err=True)
            raise typer.Exit(2)
        file = Path(source['original'])
    previous = file.expanduser().resolve()
    if made := next((item['new'] for item in data.get('versions', []) if item['previous'] == previous.as_posix()), None):
        typer.echo(made)
        return
    if not previous.is_file():
        typer.echo(f"Not a file: {previous}", err=True)
        raise typer.Exit(2)
    new = next_version(previous)
    with previous.open('rb') as source_file, new.open('xb') as copy:  # 'x': never over a file that appeared meanwhile
        shutil.copyfileobj(source_file, copy)
    entry = {'previous': previous.as_posix(), 'new': new.as_posix(), 'sha256': digest(previous), 'created_at': now()}
    try:
        if mapped := remap(data, previous, new):
            entry['project_file'] = mapped
    except (projects.ProjectError, OSError) as exc:  # the version stands; the mapping is the authors' to fix
        typer.echo(f"The project's mapping still names {previous.name}: {exc}", err=True)
    data.setdefault('versions', []).append(entry)
    save(run, data)
    typer.echo(new.as_posix())


def write_beside(target: Path, body: bytes, prefix: str) -> None:
    """Write a file whole or not at all: a temporary copy in the same folder, then one rename."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False, prefix=prefix, suffix=target.suffix) as copy:
        copy.write(body)
    try:
        Path(copy.name).replace(target)
    except OSError:
        Path(copy.name).unlink(missing_ok=True)
        raise


def same(path: Path, sha: str) -> bool:
    try:
        return digest(path) == sha
    except OSError:  # open in another program (Windows) and unreadable: not known to be the same
        return False


def deliver(made: Path, folder: Path, name: str, label: str, replace: bool, stamp: str) -> tuple[Path, Path | None, bool]:
    """Copy a deliverable beside the manuscript as NAME + label + its own suffix, never over a different file the
    authors may have worked in unless replace: that file is kept, and this copy goes beside it under a dated name
    (NAME.review.20261024.docx, then -2, -3). Returns the copy, the different file kept (or None) and whether the
    copy was written now (False: an identical copy was already there)."""
    body, extension = made.read_bytes(), made.suffix
    sha = hashlib.sha256(body).hexdigest()
    target = folder / f'{name}{label}{extension}'
    if target.exists() and same(target, sha):
        return target, None, False
    if not target.exists() or replace:
        try:
            write_beside(target, body, f'.{name}-')
            return target, None, True
        except PermissionError:
            if not target.exists():
                raise  # the folder itself cannot be written
            # the file is open in another program (Windows): keep it and write the dated copy beside it
    earlier = sorted(folder.glob(f'{glob.escape(name + label)}.*{glob.escape(extension)}'))
    if found := next((path for path in earlier if same(path, sha)), None):
        return found, target, False  # this run's copy is already there under an earlier dated name
    for number in itertools.count(1):
        dated = folder / f'{name}{label}.{stamp}{"" if number == 1 else f"-{number}"}{extension}'
        if not dated.exists():
            write_beside(dated, body, f'.{name}-')
            return dated, target, True


def report_of(run: Path, data: dict[str, Any], skill: str) -> Path:
    """The registered report of a skill in this run: SKILL/report.md, else the last report registered."""
    try:
        skill_name(skill)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    reports = [item['path'] for item in data['skills'].get(skill, {}).get('artifacts', []) if item['role'] == 'report']
    chosen = f'{skill}/report.md' if f'{skill}/report.md' in reports else reports[-1] if reports else None
    if chosen is None or not (run / chosen).is_file():
        typer.echo(f"{skill} has no saved report in this run to hand over; register it with `runs.py add RUN --skill "
                   f"{skill} --file REPORT --role report --name report.md` first. Nothing was handed over.", err=True)
        raise typer.Exit(1)
    return run / chosen


def destination(run: Path, data: dict[str, Any], to: Path | None, stem: str | None) -> tuple[Path, str]:
    """Where the copies go and their file-name stem: beside the manuscript, named after it. A connected manuscript's
    copies go to the project folder, named after its reading copy."""
    source = data['inputs'][0] if data['inputs'] else None
    if source is None and (to is None or stem is None):
        raise typer.BadParameter('This run has no snapshot of the manuscript; give --to FOLDER and --stem NAME.')
    if source is None:
        return to.resolve(), stem
    original = Path(source['original'])
    root = data.get('context', {}).get('project_root')
    folder = Path(root) if source.get('remote') and root else original.parent
    return (to or folder).resolve(), stem or original.stem


@app.command()
@serialized
def handover(run: Path,
             report: Annotated[list[str] | None, typer.Option(
                 '--report', help="Also hand over this skill's report as STEM.<skill without manuscript->.md, for a "
                                  "focused run; repeat")] = None,
             replace_docx: Annotated[bool, typer.Option(help="Replace an existing, different STEM.review.docx instead "
                                                        "of writing a dated copy beside it")] = False,
             replace_proposed: Annotated[bool, typer.Option(help="Replace an existing, different corrected version "
                                                            "(STEM.proposed.*) instead of writing a dated copy")] = False,
             replace: Annotated[bool, typer.Option(help="Replace every existing, different copy (Word file, corrected "
                                                   "version, report) instead of writing dated copies")] = False,
             to: Annotated[Path | None, typer.Option(help="The folder to hand over to; default: the manuscript's")] = None,
             stem: Annotated[str | None, typer.Option(help="The file-name stem; default: the manuscript's")] = None) -> None:
    """Copy the newest dashboard, its Word version, the changes workbook and the corrected version beside the
    manuscript, as STEM.dashboard.html, STEM.review.docx, STEM.changes.xlsx and STEM.proposed<suffix>, and with
    --report a focused run's report.

    The dashboard is replaced on every run (with versions: immutable, kept like the others); each run's folder
    keeps its own. A Word file, corrected version or report copy already there that differs is kept as it is,
    and this run's copy goes beside it under a dated name; the command says which, and exits 0. Every copy
    written is recorded in the run manifest."""
    run = run.resolve()
    data = read(run)
    immutable = chosen(data, 'versions') == 'immutable'
    if immutable and (replace or replace_docx or replace_proposed):
        typer.echo("This run's versions are immutable: nothing already beside the manuscript is replaced, and this "
                   "run's copies go beside the earlier ones under dated names. Hand over without the --replace "
                   "options. Nothing was handed over.", err=True)
        raise typer.Exit(2)
    folder, name = destination(run, data, to, stem)
    stamp = datetime.now().strftime('%Y%m%d')
    wanted = [(kind, latest(run, pattern), label, (always and not immutable) or replace
               or (kind == 'docx' and replace_docx) or (kind == 'corrected' and replace_proposed))
              for kind, (pattern, label, always) in HANDOVER.items()]
    wanted += [('report', report_of(run, data, skill), f".{skill.removeprefix('manuscript-')}", replace)
               for skill in dict.fromkeys(report or [])]
    handed, kept = [], []
    for kind, made, label, replaces in wanted:
        if made is None:
            continue
        copy, earlier, written = deliver(made, folder, name, label, replaces, stamp)
        handed.append(copy)
        if earlier is not None:
            kept.append({'file': earlier.as_posix(), 'this_run': copy.as_posix(), 'kind': kind})
        if written:
            data.setdefault('handover', []).append(
                {'kind': kind, 'path': copy.as_posix(), 'from': made.relative_to(run).as_posix(),
                 'sha256': digest(copy), 'handed_over_at': now()} | ({'kept': earlier.as_posix()} if earlier else {}))
    if not handed:
        typer.echo('No dashboard, Word file or corrected version in this run to hand over; render them first, or '
                   'name a focused run\'s report with --report SKILL.', err=True)
        raise typer.Exit(1)
    save(run, data)
    typer.echo(json.dumps({'handed_over': [p.as_posix() for p in handed], 'kept': kept}, indent=2, ensure_ascii=False))
    flags = {'docx': '--replace-docx', 'corrected': '--replace-proposed'}
    for item in kept:
        typer.echo(f"{Path(item['file']).name} already exists and differs (the authors may have worked in it): it is "
                   f"kept as it is, and this run's copy is {Path(item['this_run']).name} beside it. To replace it "
                   f"instead, rerun with {flags.get(item['kind'], '--replace')}.", err=True)


def kept(data: dict[str, Any], relative: str, extra: list[str], deliverables: set[str]) -> bool:
    """Whether pack leaves a file in place: the manifest, the generated READMEs, the reports and the newest
    deliverables."""
    names = {'run.json', 'README.md', ARCHIVE, *(f'{name}/README.md' for name in data['skills'])} | deliverables
    names |= {item['path'] for entry in data['skills'].values() for item in entry['artifacts'] if item['role'] == 'report'}
    return relative.startswith('.') or relative in names or any(fnmatch(relative, p) for p in extra)


@app.command()
@serialized
def pack(run: Path, keep: Annotated[list[str] | None, typer.Option(
        '--keep', help="Another file to leave in place, as a path in the run (fnmatch pattern); repeat")] = None) -> None:
    """Pack a finished run's evidence into evidence.zip, leaving the index, the reports, the newest dashboard and
    Word file and the newest corrected version in place. The archive is read back and verified before the loose
    copies are removed; unpack restores them. For the `keep: results` setting; run it last, after validate --final."""
    run = run.resolve()
    data = read(run)
    if data.get('packed'):
        typer.echo(f"Already packed in {ARCHIVE}.")
        return
    errors = problems(run, data, final=True)
    if errors:
        typer.echo('Pack a run only once it validates (runs.py validate RUN --final):\n' + '\n'.join(errors), err=True)
        raise typer.Exit(1)
    files = {}
    deliverables = newest_deliverables(run)
    for path in sorted(p for p in run.rglob('*') if p.is_file()):
        relative = path.relative_to(run).as_posix()
        if not kept(data, relative, keep or [], deliverables):
            files[relative] = digest(path)
    if not files:
        typer.echo('Nothing to pack.')
        return
    partial = run / f'.{ARCHIVE}.partial'
    with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(run / relative, relative)
    with zipfile.ZipFile(partial) as archive:
        if any(hashlib.sha256(archive.read(r)).hexdigest() != sha for r, sha in files.items()):
            partial.unlink()
            typer.echo('The archive did not read back identically; nothing was packed.', err=True)
            raise typer.Exit(1)
    partial.replace(run / ARCHIVE)
    data['packed'] = {'archive': ARCHIVE, 'sha256': digest(run / ARCHIVE), 'packed_at': now(), 'files': files}
    save(run, data)  # the manifest records the archive before any original is removed
    for relative in files:
        (run / relative).unlink()
    for folder in sorted((p for p in run.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    left = sorted(p.relative_to(run).as_posix() for p in run.rglob('*') if p.is_file() and not p.name.startswith('.'))
    typer.echo(f"Packed {len(files)} files into {run / ARCHIVE}; left in place: {', '.join(left)}")


@app.command()
@serialized
def unpack(run: Path) -> None:
    """Restore a packed run's files from evidence.zip, so the run can continue; the archive goes once they are back."""
    run = run.resolve()
    data = read(run)
    packed = data.get('packed')
    if not packed:
        typer.echo('This run is not packed.')
        return
    path = within(run, packed['archive'])
    with zipfile.ZipFile(path) as archive:
        bodies = {relative: archive.read(relative) for relative in packed['files']}
    for relative, body in bodies.items():
        target = within(run, relative)
        if hashlib.sha256(body).hexdigest() != packed['files'][relative]:
            typer.echo(f"{relative} changed inside {ARCHIVE}; nothing was restored.", err=True)
            raise typer.Exit(1)
        if target.exists() and digest(target) != packed['files'][relative]:
            typer.echo(f"{relative} exists with other contents; nothing was restored or overwritten.", err=True)
            raise typer.Exit(1)
    for relative, body in bodies.items():
        target = within(run, relative)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(body)
    del data['packed']
    save(run, data)
    path.unlink()
    typer.echo(f"Restored {len(bodies)} files; the run can continue.")


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):  # UTF-8 whatever the console's code page (Windows)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
