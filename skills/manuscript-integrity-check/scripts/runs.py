#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "filelock>=3"]
# ///
"""Inspectable skill runs: source hashes, per-skill evidence, failures and delivery checks.

Use start once, reuse the returned run directory across companion skills, and add new evidence without
overwriting earlier attempts. exec captures a real command's stdout, stderr and exit status. A successful
command does not establish scientific support. validate checks artifacts, not the truth of a report or
whether an agent really showed a passage in chat.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from pathlib import Path
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
PANEL = {'reader', 'referee', 'seat', 'defence'}


class Isolation(str, Enum):
    fresh_agent = 'fresh-agent'  # a new agent whose whole context was its brief
    one_agent = 'one-agent'  # the fallback: one agent read as each seat in turn; not independent


ISOLATION_LABEL = {'fresh-agent': 'fresh agent', 'one-agent': 'one agent in turn, not independent'}
SKILLS = Path(__file__).resolve().parents[2]
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
    for name, seat in data["skills"].items():
        folder = run / name
        folder.mkdir(exist_ok=True)
        lines = [f"# {name}", "", f"Status: **{seat['status']}**. {seat.get('reason', '')}", ""]
        if name == 'manuscript-peer-review':
            lines.append(f"Review mode: {seat.get('review_mode', 'full')}.\n")
        for item in seat["artifacts"]:
            relative = Path(item["path"]).relative_to(name).as_posix()
            lines.append(f"- {item['role']}: [{relative}]({relative})" + (f" — seat: {item['seat']}" if item.get('seat') else "")
                         + (f" ({ISOLATION_LABEL[item['isolation']]})" if item.get('isolation') in ISOLATION_LABEL else ""))
        for issue in seat["issues"]:
            lines.extend(["", f"- **{issue['kind']}**: {issue['message']}"])
        for number, command in enumerate(seat['commands'], 1):
            paths = [Path(p).relative_to(name).as_posix() for p in command['outputs']]
            links = ', '.join(f'[{Path(p).name}]({p})' for p in paths)
            lines.extend(['', f"- Command {command.get('attempt', number)}: {command.get('state', 'finished')}, exit {command['exit_code']}; {links}"])
        for change in seat["changes"]:
            lines.extend(["", f"- Change: [{change['section']}]({Path(change['path']).relative_to(name).as_posix()}); "
                          f"shown in chat: {change['shown_in_chat']} (agent attestation)."])
        (folder / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        index.append(f"- [{name}]({name}/README.md): **{seat['status']}**; {len(seat['issues'])} recorded issue(s).")
    index.extend(["", "[Run manifest](run.json) contains effective settings, source hashes and all recorded attempts."])
    (run / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


def ensure_skill(data: dict[str, Any], name: str) -> dict[str, Any]:
    skill_name(name)
    return data["skills"].setdefault(name, {"status": "running", "artifacts": [], "issues": [], "changes": [], "commands": []})


def artifact(run: Path, data: dict[str, Any], name: str, source: Path, role: str,
             destination: str | None = None, seat: str | None = None, allow_empty: bool = False,
             isolation: str | None = None) -> dict[str, Any]:
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
    if any(item['path'] == target.relative_to(run.resolve()).as_posix() for item in entry['artifacts']):
        raise ValueError("Evidence is already registered; save the next attempt under a new filename.")
    if target != source.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
    item = {"path": target.relative_to(run.resolve()).as_posix(), "role": role, "seat": seat,
            "sha256": digest(target), "recorded_at": now()}
    if role in PANEL:
        item["isolation"] = isolation
        if isolation == 'one-agent':
            entry['issues'].append({'kind': 'not_independent', 'recorded_at': now(), 'message':
                f"{seat or role}: read by one agent in turn, not independent; its agreement with other seats is not corroboration."})
    entry['artifacts'].append(item)
    return item


def problems(run: Path, data: dict[str, Any], final: bool = False) -> list[str]:
    errors = []
    for source in data['inputs']:
        path = within(run, source['snapshot'])
        if not path.is_file() or digest(path) != source['sha256']:
            errors.append(f"Missing or changed source snapshot: {source['snapshot']}")
        original = Path(source['original'])
        if not original.is_file():
            errors.append(f"Authoritative source is missing or no longer a file: {original}")
        elif digest(original) != source['sha256']:
            if not any(s['changes'] or s.get('routine_only_reason') for s in data['skills'].values()):
                errors.append(f"Manuscript changed without a change record or routine-only explanation: {original}")
    for name, entry in data['skills'].items():
        if final and entry['status'] not in TERMINAL:
            errors.append(f"{name}: still {entry['status']}")
        for item in entry['artifacts']:
            try:
                path = within(run, item['path'])
            except ValueError as exc:
                errors.append(f"{name}: {exc}")
                continue
            if not path.is_file() or digest(path) != item['sha256']:
                errors.append(f"Missing or changed evidence: {item['path']}")
        roles = [item['role'] for item in entry['artifacts']]
        if entry['status'] in TERMINAL - {'not_run'} and 'report' not in roles:
            errors.append(f"{name}: no saved report")
        if entry['status'] in {'partial', 'blocked', 'not_run', 'reused'} and not entry.get('reason'):
            errors.append(f"{name}: status needs its reason/coverage or reused source")
        if entry['status'] == 'completed':
            for item in entry['artifacts']:
                if item['role'] in PANEL and item.get('isolation') not in ISOLATION_LABEL:
                    errors.append(f"{name}: {item['path']} does not record whether it ran as a fresh agent (--isolation)")
            if name == 'manuscript-story':
                seats = {item['seat'] for item in entry['artifacts'] if item['role'] == 'reader'}
                if not {'skimmer', 'potential-user', 'informed-outsider'} <= seats:
                    errors.append(f"{name}: missing independent reader reports")
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
            if not path.is_file() or digest(path) != change['sha256']:
                errors.append(f"Missing or changed before/after: {change['path']}")
            if final and not change['shown_in_chat']:
                errors.append(f"{name}: consequential change not acknowledged as shown in chat: {change['section']}")
    return errors


@app.command()
def start(target: str, skill: Annotated[list[str], typer.Option("--skill")], project: Path | None = None,
          reports: str | None = None, edits: str | None = None, peer_review: str | None = None) -> None:
    """Start a unique run under the saved destination. Print its absolute directory; never overwrite a run."""
    overrides = {k: v for k, v in {'reports': reports, 'edits': edits, 'peer_review': peer_review}.items() if v is not None}
    ctx = projects.context(target, project, overrides)
    if ctx['status'] != 'ready':
        typer.echo(json.dumps(ctx, indent=2))
        raise typer.Exit(3)
    for name in skill:
        skill_name(name)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    run = Path(ctx['output_dir']) / run_id
    run.mkdir(parents=True)
    data = {'schema_version': 1, 'run_id': run_id, 'started_at': now(), 'context': ctx, 'inputs': [], 'skills': {}}
    for number, location in enumerate(ctx['project']['manuscripts'], 1):
        if projects.is_remote(location):
            continue
        source = projects.local_path(Path(ctx['project_root']), location)
        dest = run / 'inputs' / f'{number:02d}-{source.name}'
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, dest)
        data['inputs'].append({'original': str(source), 'snapshot': dest.relative_to(run).as_posix(), 'sha256': digest(source)})
    for name in skill:
        ensure_skill(data, name)
    save(run, data)
    typer.echo(str(run))


@app.command()
@serialized
def add(run: Path, skill: Annotated[str, typer.Option('--skill')],
        file: Annotated[Path, typer.Option('--file')], role: Role = Role.other,
        name: str | None = None, seat: str | None = None, isolation: Isolation | None = None) -> None:
    """Retain an actual output with its role. --seat identifies a reader or referee, and --isolation says whether it
    ran as a fresh agent; files cannot be overwritten."""
    run = run.resolve()
    data = read(run)
    if role.value in PANEL and isolation is None:
        raise typer.BadParameter(f"A {role.value} output records how it ran: --isolation fresh-agent (a new agent whose only "
                                 "context was its brief) or --isolation one-agent (the fallback when the host cannot start agents).")
    item = artifact(run, data, skill, file, role.value, name, seat, isolation=isolation.value if isolation else None)
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
    command = {'attempt': number, 'argv': ctx.args, 'cwd': str(working), 'state': 'running',
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
           after: Path | None = None, shown_in_chat: bool = False) -> None:
    """Save exact consequential before/after text. Omit before for an addition, after for a deletion."""
    if before is None and after is None:
        raise typer.BadParameter('Supply before, after, or both.')
    data = read(run)
    entry = ensure_skill(data, skill)
    relative = f"{skill}/changes/{len(entry['changes']) + 1:04d}.md"
    path = within(run, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"# {section}\n\nReason: {reason}\n\n## Before\n\n"
    text += before.read_text(encoding='utf-8') if before else '(No previous block.)\n'
    text += '\n\n## After\n\n'
    text += after.read_text(encoding='utf-8') if after else '(Block removed.)\n'
    with path.open('x', encoding='utf-8') as output:
        output.write(text)
    entry['changes'].append({'section': section, 'path': relative, 'sha256': digest(path), 'shown_in_chat': shown_in_chat})
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
    """Set honest coverage. Completed requires a report and the skill's reader/referee evidence."""
    if status not in TERMINAL:
        raise typer.BadParameter(f"Choose {', '.join(sorted(TERMINAL))}.")
    data = read(run)
    entry = ensure_skill(data, skill)
    if review_mode is not None:
        if skill != 'manuscript-peer-review' or review_mode not in {'full', 'quick', 'invited'}:
            raise typer.BadParameter('review-mode is full, quick or invited and applies only to peer review.')
        entry['review_mode'] = review_mode
    entry.update(status=status, reason=reason, routine_only_reason=routine_only_reason)
    errors = problems(run, data)
    if errors:
        typer.echo('\n'.join(errors), err=True)
        raise typer.Exit(1)
    save(run, data)
    typer.echo(str(run / skill / 'README.md'))


@app.command()
@serialized
def validate(run: Path, final: bool = False) -> None:
    """Check evidence and final handover. Scientific correctness and actual chat delivery still need review."""
    data = read(run)
    errors = problems(run, data, final)
    complete = all(s['status'] in {'completed', 'reused'} for s in data['skills'].values())
    typer.echo(json.dumps({'valid': not errors, 'workflow_complete': complete and not errors,
                           'problems': errors, 'index': str(run.resolve() / 'README.md')}, indent=2))
    if errors:
        raise typer.Exit(1)


if __name__ == '__main__':
    app()
