"""Project isolation and observable evidence-delivery failures, including actual command execution."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/manuscript-integrity-check/scripts'
sys.path.insert(0, str(SCRIPTS))

import project as projects
import runs

runner = CliRunner()


@pytest.fixture()
def manuscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('MANUSCRIPT_SKILLS_CONFIG', str(tmp_path / 'global'))
    folder = tmp_path / 'paper one'
    folder.mkdir()
    path = folder / 'paper.md'
    path.write_text('# Real test input\n\n## Abstract\n\nLocal analysis.\n')
    return path


def configure(path: Path, *args: str):
    return runner.invoke(projects.app, ['configure', str(path.parent), '--manuscript', path.name,
                                      '--no-code', '--output-dir', 'reviews', *args])


def resolve(path: Path, *args: str):
    return runner.invoke(projects.app, ['resolve', str(path), '--json', *args])


def start(path: Path, skill: str = 'manuscript-prose-edit') -> Path:
    result = runner.invoke(runs.app, ['start', str(path), '--skill', skill])
    assert result.exit_code == 0, (result.output, result.exception)
    return Path(result.output.strip())


def add(run: Path, source: Path, role: str = 'report', skill: str = 'manuscript-prose-edit', *args: str):
    return runner.invoke(runs.app, ['add', str(run), '--skill', skill, '--file', str(source), '--role', role, *args])


def finish(run: Path, skill: str = 'manuscript-prose-edit', status: str = 'completed', *args: str):
    return runner.invoke(runs.app, ['finish', str(run), '--skill', skill, '--status', status, *args])


def write_findings(run: Path, skill: str = 'manuscript-prose-edit') -> Path:
    """The stage's findings.json for the dashboard: nothing found is an empty list, never a missing file."""
    path = run / skill / 'findings.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'skill': skill, 'findings': [], 'not_checked': []}), encoding='utf-8')
    return path


def test_first_use_asks_missing_context_without_writing(manuscript: Path) -> None:
    result = resolve(manuscript)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data['status'] == 'setup_required'
    assert {q['key'] for q in data['questions']} == {'manuscripts', 'code_roots', 'output_dir'}
    output = next(q for q in data['questions'] if q['key'] == 'output_dir')
    assert output['recommended'] == 'reviews' and output['why']
    # The working preferences are asked in the same batch, each with its recommended answer and why.
    assert [(q['key'], q['recommended']) for q in data['preferences']] == [
        ('reports', 'file'), ('edits', 'conservative'), ('versions', 'in-place'), ('keep', 'everything')]
    assert all(q['why'] for q in data['preferences'])
    assert not (manuscript.parent / projects.CONFIG).exists()


def test_preferences_never_block_a_run_and_are_saved_only_as_answers(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    saved = yaml.safe_load((manuscript.parent / projects.CONFIG).read_text())
    assert 'settings' not in saved  # the defaults are not answers
    data = json.loads(resolve(manuscript).output)
    assert data['status'] == 'ready' and {q['key'] for q in data['preferences']} == {'reports', 'edits', 'versions', 'keep'}
    start(manuscript)  # a pending preference never holds up the work
    assert configure(manuscript, '--keep', 'results').exit_code == 0
    data = json.loads(resolve(manuscript).output)
    assert data['effective']['keep'] == 'results' and data['sources']['keep'] == 'project'
    assert {q['key'] for q in data['preferences']} == {'reports', 'edits', 'versions'}


def test_a_new_project_copies_the_choices_saved_globally_and_does_not_ask_them(manuscript: Path) -> None:
    global_file = projects.settings.settings_path()
    global_file.parent.mkdir(parents=True)
    global_file.write_text('keep: results\n')
    assert [q['key'] for q in json.loads(resolve(manuscript).output)['preferences']] == ['reports', 'edits', 'versions']
    assert configure(manuscript).exit_code == 0
    assert yaml.safe_load((manuscript.parent / projects.CONFIG).read_text())['settings'] == {'keep': 'results'}


def test_choices_are_shared_by_skills_and_not_asked_again(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    for _ in range(3):
        data = json.loads(resolve(manuscript).output)
        assert data['status'] == 'ready' and not data['questions']
        assert data['effective'] == {'reports': 'file', 'edits': 'conservative', 'versions': 'in-place',
                                     'keep': 'everything', 'peer_review': 'auto'}
    for skill in ('manuscript-prose-edit', 'manuscript-deslop', 'manuscript-dashboard', 'manuscript-journal-select'):
        run = start(manuscript, skill)
        assert runs.read(run)['context']['project_file'] == str(manuscript.parent / projects.CONFIG)


def test_conversation_override_is_transient_and_project_outlives_global_change(manuscript: Path) -> None:
    assert configure(manuscript, '--reports', 'file', '--edits', 'conservative').exit_code == 0
    original = (manuscript.parent / projects.CONFIG).read_bytes()
    global_file = projects.settings.settings_path()
    global_file.parent.mkdir(parents=True)
    global_file.write_text('reports: chat\nedits: apply\n')
    data = json.loads(resolve(manuscript, '--reports', 'both', '--edits', 'propose').output)
    assert data['effective']['reports'] == 'both' and data['sources']['reports'] == 'conversation'
    assert data['effective']['edits'] == 'propose'
    assert json.loads(resolve(manuscript).output)['effective']['reports'] == 'file'
    assert (manuscript.parent / projects.CONFIG).read_bytes() == original


def test_missing_location_or_misbound_paper_is_a_targeted_conflict(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    other = manuscript.parent / 'different.md'
    other.write_text('Another manuscript.')
    result = resolve(other)
    assert result.exit_code == 3
    assert json.loads(result.output)['issues'][0]['scope'] == 'manuscript'
    manuscript.unlink()
    data = json.loads(resolve(manuscript).output)
    assert data['status'] == 'conflict' and not data['questions']


def test_unknown_code_is_an_answer_and_related_papers_keep_separate_choices(manuscript: Path) -> None:
    other = manuscript.parent.parent / 'paper-two'
    other.mkdir()
    paper = other / 'paper.md'
    paper.write_text('Other paper')
    assert configure(paper, '--reports', 'both').exit_code == 0
    result = runner.invoke(projects.app, ['configure', str(manuscript.parent), '--manuscript', manuscript.name,
        '--unknown-code', '--output-dir', 'reviews', '--related-manuscript', str(paper)])
    assert result.exit_code == 0, result.output
    data = json.loads(resolve(manuscript).output)
    assert data['project']['code_roots'] is None and not data['questions']
    assert data['effective']['reports'] == 'file'
    assert json.loads(resolve(paper).output)['effective']['reports'] == 'both'


@pytest.mark.parametrize('body', ['schema_version: 99\n', '- broken\n', 'schema_version: 1\nsettings: {edits: anything}\n'])
def test_broken_project_is_preserved(manuscript: Path, body: str) -> None:
    config = manuscript.parent / projects.CONFIG
    config.write_text(body)
    assert resolve(manuscript).exit_code == 2
    assert configure(manuscript).exit_code == 2
    assert config.read_text() == body


def test_configure_preserves_unmentioned_choices_and_future_keys(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    config = manuscript.parent / projects.CONFIG
    data = yaml.safe_load(config.read_text()) | {'future': {'retained': True}}
    config.write_text(yaml.safe_dump(data))
    result = runner.invoke(projects.app, ['configure', str(manuscript.parent), '--peer-review', 'on-request'])
    assert result.exit_code == 0
    data = yaml.safe_load(config.read_text())
    assert data['future'] == {'retained': True} and data['code_roots'] == []
    assert data['settings']['peer_review'] == 'on-request'


def test_invalid_override_never_mutates_settings(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    path = manuscript.parent / projects.CONFIG
    before = path.read_bytes()
    assert resolve(manuscript, '--peer-review', 'invented').exit_code == 2
    assert path.read_bytes() == before


def test_unique_runs_snapshots_reports_and_detectable_tampering(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run, another = start(manuscript), start(manuscript)
    assert run != another and run.parent == manuscript.parent / 'reviews'
    report = manuscript.parent / 'report.md'
    report.write_text('Full findings with actual coverage.')
    assert finish(run).exit_code == 1  # a completed thought is not a saved report
    assert add(run, report).exit_code == 0
    refused = finish(run)  # nor is a report without the findings the dashboard counts
    assert refused.exit_code == 1 and 'no findings.json' in refused.output
    write_findings(run)
    assert finish(run).exit_code == 0
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 0
    (run / 'manuscript-prose-edit/report.md').write_text('Silently replaced')
    result = runner.invoke(runs.app, ['validate', str(run), '--final'])
    assert result.exit_code == 1 and 'changed evidence' in result.output


def test_source_readme_can_be_retained_without_replacing_the_generated_index(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    source = manuscript.parent / 'README.md'
    source.write_text('The original scientific module documentation.\n')
    index = run / 'manuscript-prose-edit/README.md'
    generated = index.read_text()
    for name in ('README.md', 'evidence/../README.md'):
        rejected = add(run, source, 'input', 'manuscript-prose-edit', '--name', name)
        assert rejected.exit_code == 1
        assert index.read_text() == generated
    retained = add(run, source, 'input', 'manuscript-prose-edit', '--name', 'evidence/module/README.md')
    assert retained.exit_code == 0, (retained.output, retained.exception)
    assert (run / 'manuscript-prose-edit/evidence/module/README.md').read_bytes() == source.read_bytes()
    assert index.read_text().startswith('# manuscript-prose-edit')
    assert 'evidence/module/README.md' in index.read_text()
    assert runner.invoke(runs.app, ['validate', str(run)]).exit_code == 0


def test_real_failed_command_survives_a_successful_rerun(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    args = ['exec', str(run), '--skill', 'manuscript-prose-edit', '--', sys.executable, '-c']
    bad = runner.invoke(runs.app, [*args, "import sys; print('actual failure'); sys.exit(4)"])
    assert bad.exit_code == 4, (bad.output, bad.exception)
    good = runner.invoke(runs.app, [*args, "print('successful retry')"])
    assert good.exit_code == 0, (good.output, good.exception)
    entry = runs.read(run)['skills']['manuscript-prose-edit']
    assert [c['exit_code'] for c in entry['commands']] == [4, 0]
    assert 'actual failure' in (run / entry['commands'][0]['outputs'][0]).read_text()
    assert 'command_failure' in (run / 'manuscript-prose-edit/README.md').read_text()
    assert len(entry['artifacts']) == 4


def test_a_nonexistent_command_is_retained_as_failure(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    result = runner.invoke(runs.app, ['exec', str(run), '--skill', 'manuscript-prose-edit', '--', str(run/'absent-program')])
    assert result.exit_code == 127
    assert runs.read(run)['skills']['manuscript-prose-edit']['commands'][0]['exit_code'] == 127


def test_reader_and_referee_completion_requires_real_saved_seat_artifacts(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    report = manuscript.parent / 'report.md'
    report.write_text('Unit-test stand-in; this is not the real-manuscript smoke run.')
    run = start(manuscript, 'manuscript-story')
    assert add(run, report, 'report', 'manuscript-story').exit_code == 0
    assert finish(run, 'manuscript-story').exit_code == 1
    for seat in ('skimmer', 'potential-user', 'informed-outsider'):
        assert add(run, report, 'reader', 'manuscript-story', '--seat', seat, '--name', f'readers/{seat}.md', '--isolation', 'fresh-agent').exit_code == 0
    write_findings(run, 'manuscript-story')
    assert finish(run, 'manuscript-story').exit_code == 0
    second = start(manuscript, 'manuscript-peer-review')
    write_findings(second, 'manuscript-peer-review')
    assert add(second, report, 'report', 'manuscript-peer-review').exit_code == 0
    for seat in ('methods', 'skeptic', 'champion'):
        assert add(second, report, 'referee', 'manuscript-peer-review', '--seat', seat, '--name', f'{seat}.md', '--isolation', 'fresh-agent').exit_code == 0
    assert finish(second, 'manuscript-peer-review').exit_code == 1
    assert add(second, report, 'defence', 'manuscript-peer-review', '--name', 'defence.md', '--isolation', 'fresh-agent').exit_code == 0
    assert add(second, report, 'adjudication', 'manuscript-peer-review', '--name', 'adjudication.md').exit_code == 0
    assert finish(second, 'manuscript-peer-review').exit_code == 0


def test_unshown_change_blocks_handover_and_source_edit_is_detected(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    after = manuscript.parent / 'after.txt'
    after.write_text('Proposed paragraph.')
    assert add(run, after, 'report', 'manuscript-prose-edit', '--name', 'report.md').exit_code == 0
    write_findings(run)
    original = manuscript.read_text()
    manuscript.write_text(original + '\nAdded paragraph.\n')
    assert finish(run).exit_code == 1
    args=['change', str(run), '--skill', 'manuscript-prose-edit', '--section', 'Abstract', '--reason', 'Author-approved clarification', '--after', str(after)]
    assert runner.invoke(runs.app, args).exit_code == 0
    assert finish(run).exit_code == 0
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 1
    assert runner.invoke(runs.app, ['shown', str(run), '--skill', 'manuscript-prose-edit', '--number', '1']).exit_code == 0
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 0


def test_an_edit_the_authors_were_away_for_passes_when_the_dashboard_shows_it(manuscript: Path) -> None:
    """An unattended run: no edit could be shown in chat, so the rendered dashboard, which shows each recorded edit
    as a diff, is where the authors see it; validate --final lists it instead of failing, and never attests it."""
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    after = manuscript.parent / 'after.txt'
    after.write_text('Proposed paragraph.')
    assert add(run, after, 'report', 'manuscript-prose-edit', '--name', 'report.md').exit_code == 0
    write_findings(run)
    manuscript.write_text(manuscript.read_text() + '\nAdded paragraph.\n')
    assert runner.invoke(runs.app, ['change', str(run), '--skill', 'manuscript-prose-edit', '--section', 'Abstract',
                                    '--reason', 'Clearer.', '--after', str(after)]).exit_code == 0
    assert finish(run).exit_code == 0
    assert 'nor shown in the rendered dashboard' in runner.invoke(runs.app, ['validate', str(run), '--final']).output
    change = runs.read(run)['skills']['manuscript-prose-edit']['changes'][0]
    rendered = run / 'manuscript-dashboard/dashboard.2'
    rendered.mkdir(parents=True)
    (rendered / 'manuscript-dashboard.html').write_text('<html></html>')
    stale = {'evidence_sha256': {f"../{change['path']}": '0' * 64}}  # rendered before the edit's record changed
    (rendered / 'summary.json').write_text(json.dumps(stale))
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 1
    (rendered / 'summary.json').write_text(json.dumps({'evidence_sha256': {f"../{change['path']}": change['sha256']}}))
    result = runner.invoke(runs.app, ['validate', str(run), '--final'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['shown_in_dashboard'] == ['manuscript-prose-edit: Abstract (manuscript-prose-edit/changes/0001.md)']
    assert runs.read(run)['skills']['manuscript-prose-edit']['changes'][0]['shown_in_chat'] is False


def test_partial_is_a_valid_handover_without_claiming_complete(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    report = manuscript.parent / 'report.md'
    report.write_text('Blocked source; no support verdict.')
    assert add(run, report).exit_code == 0
    write_findings(run)
    assert finish(run, status='partial').exit_code == 1
    assert finish(run, 'manuscript-prose-edit', 'partial', '--reason', 'Source inaccessible').exit_code == 0
    result=runner.invoke(runs.app, ['validate', str(run), '--final'])
    assert result.exit_code == 0 and json.loads(result.output)['workflow_complete'] is False


def test_evidence_paths_cannot_escape_or_overwrite_an_attempt(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    report = manuscript.parent / 'report.md'
    report.write_text('Evidence')
    assert add(run, report, 'check', 'manuscript-prose-edit', '--name', '../../escaped.md').exit_code != 0
    assert not (run.parent/'escaped.md').exists()
    assert add(run, report).exit_code == 0
    assert add(run, report).exit_code != 0
    assert (run/'manuscript-prose-edit/report.md').read_text() == 'Evidence'


def test_concurrent_writer_fails_without_touching_manifest(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    before = (run/'run.json').read_bytes()
    with runs.FileLock(run/'.writer.lock'):
        result = runner.invoke(runs.app, ['issue', str(run), '--skill', 'manuscript-prose-edit', '--kind', 'test', '--message', 'blocked writer'])
    assert result.exit_code == 3 and 'Run is busy' in result.output
    assert (run/'run.json').read_bytes() == before
    assert runner.invoke(runs.app, ['issue', str(run), '--skill', 'manuscript-prose-edit', '--kind', 'test', '--message', 'retry']).exit_code == 0


def test_interrupted_command_logs_survive_the_next_attempt(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    folder = run/'manuscript-prose-edit/commands'
    folder.mkdir()
    orphan = folder/'0001.stdout.txt'
    orphan.write_text('Interrupted attempt evidence')
    result = runner.invoke(runs.app, ['exec', str(run), '--skill', 'manuscript-prose-edit', '--', sys.executable, '-c', "print('retry')"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert orphan.read_text() == 'Interrupted attempt evidence'
    entry = runs.read(run)['skills']['manuscript-prose-edit']
    assert entry['commands'][0]['attempt'] == 2
    assert any(i['kind'] == 'interrupted_attempt' for i in entry['issues'])
    assert any(a['path'].endswith('0001.stdout.txt') for a in entry['artifacts'])


def test_folder_source_is_a_setup_conflict_instead_of_a_startup_crash(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    result = runner.invoke(projects.app, ['configure', str(manuscript.parent), '--manuscript', '.'])
    assert result.exit_code == 0
    result = resolve(manuscript.parent)
    assert result.exit_code == 3 and 'source file inside' in result.output
    result = runner.invoke(runs.app, ['start', str(manuscript.parent), '--skill', 'manuscript-story'])
    assert result.exit_code == 3 and not (manuscript.parent/'reviews').exists()


def test_deleted_source_cannot_silently_pass_final_validation(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    report = manuscript.parent/'report.md'
    report.write_text('Review of source before deletion')
    assert add(run, report).exit_code == 0
    write_findings(run)
    assert finish(run).exit_code == 0
    manuscript.unlink()
    result = runner.invoke(runs.app, ['validate', str(run), '--final'])
    assert result.exit_code == 1 and 'Authoritative source is missing' in result.output


def test_two_seat_quick_pass_retains_findings_without_fabricating_referee_reports(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, 'manuscript-peer-review')
    report=manuscript.parent/'report.md'
    report.write_text('Unit-test payload for a quick-pass findings file.')
    assert add(run, report, 'report', 'manuscript-peer-review').exit_code == 0
    for seat in ('desk-editor', 'evidence-statistics'):
        assert add(run, report, 'seat', 'manuscript-peer-review', '--seat', seat, '--name', f'seats/{seat}.md', '--isolation', 'fresh-agent').exit_code == 0
    assert add(run, report, 'defence', 'manuscript-peer-review', '--name', 'defence.md', '--isolation', 'fresh-agent').exit_code == 0
    assert add(run, report, 'adjudication', 'manuscript-peer-review', '--name', 'adjudication.md').exit_code == 0
    write_findings(run, 'manuscript-peer-review')
    assert finish(run, 'manuscript-peer-review').exit_code == 1
    assert finish(run, 'manuscript-peer-review', 'completed', '--review-mode', 'quick').exit_code == 0
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 0


@pytest.mark.skipif(os.name != 'posix', reason='Uses POSIX process-group termination; ordinary command capture is cross-platform.')
def test_killing_a_real_command_preserves_partial_output_and_attempt_metadata(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    command=[sys.executable, str(SCRIPTS/'runs.py'), 'exec', str(run), '--skill', 'manuscript-prose-edit', '--',
             sys.executable, '-c', "import time; print('partial output', flush=True); time.sleep(30)"]
    process=subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    output=run/'manuscript-prose-edit/commands/0001.stdout.txt'
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and not (output.exists() and 'partial output' in output.read_text()):
        time.sleep(0.01)
    os.killpg(process.pid, signal.SIGKILL)
    process.communicate(timeout=5)
    assert output.read_text() == 'partial output\n'
    entry=runs.read(run)['skills']['manuscript-prose-edit']
    assert entry['commands'][0]['state'] == 'running' and entry['commands'][0]['exit_code'] is None
    result=runner.invoke(runs.app, ['exec', str(run), '--skill', 'manuscript-prose-edit', '--', sys.executable, '-c', "print('retry')"])
    assert result.exit_code == 0, (result.output, result.exception)
    entry=runs.read(run)['skills']['manuscript-prose-edit']
    assert [(c['attempt'],c['state'],c['exit_code']) for c in entry['commands']] == [(1,'interrupted',None),(2,'finished',0)]
    assert output.read_text() == 'partial output\n'


def test_exec_runs_where_it_was_called_so_relative_paths_resolve_for_the_caller(tmp_path, monkeypatch) -> None:
    """The 2026-10-22 run: a relative script path resolved against the project folder and failed."""
    import importlib.util, json, sys
    from typer.testing import CliRunner

    scripts = Path(__file__).resolve().parents[1] / "skills/manuscript-integrity-check/scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("runs_cwd", scripts / "runs.py")
    runs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runs)
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"run_id": "R", "started_at": "now", "inputs": [], "skills": {},
                                              "context": {"project_root": str(tmp_path / "elsewhere")}}))
    caller = tmp_path / "caller"
    caller.mkdir()
    (caller / "hello.txt").write_text("here")
    monkeypatch.chdir(caller)
    result = CliRunner().invoke(runs.app, ["exec", str(run), "--skill", "manuscript-story", "--", sys.executable, "-c",
                                           "print(open('hello.txt', encoding='utf-8').read(), end='')"])
    assert result.exit_code == 0, result.output
    command = json.loads((run / "run.json").read_text())["skills"]["manuscript-story"]["commands"][0]
    assert command["cwd"] == caller.resolve().as_posix() and (run / "manuscript-story/commands/0001.stdout.txt").read_text() == "here"


def test_a_renamed_skill_keeps_its_former_name_in_older_runs() -> None:
    assert runs.skill_name('manuscript-dashboard') == 'manuscript-dashboard'
    assert runs.skill_name('manuscript-visualize') == 'manuscript-visualize'  # runs made before 0.10.0
    with pytest.raises(ValueError, match='Unknown manuscript skill'):
        runs.skill_name('manuscript-nonexistent')


def test_every_reader_and_referee_records_whether_it_ran_as_a_fresh_agent(manuscript: Path) -> None:
    """A panel output without --isolation is refused; one read by one agent in turn is kept, recorded as an issue and
    labelled, and a hand-edited manifest that drops the field fails validation."""
    assert configure(manuscript).exit_code == 0
    report = manuscript.parent / 'report.md'
    report.write_text('Unit-test stand-in for a reader report.')
    run = start(manuscript, 'manuscript-story')
    assert add(run, report, 'report', 'manuscript-story').exit_code == 0
    refused = add(run, report, 'reader', 'manuscript-story', '--seat', 'skimmer', '--name', 'readers/skimmer.md')
    assert refused.exit_code == 2 and 'isolation' in refused.output
    assert add(run, report, 'reader', 'manuscript-story', '--seat', 'skimmer', '--name', 'readers/skimmer.md', '--isolation', 'one-agent').exit_code == 0
    for seat in ('potential-user', 'informed-outsider'):
        assert add(run, report, 'reader', 'manuscript-story', '--seat', seat, '--name', f'readers/{seat}.md', '--isolation', 'fresh-agent').exit_code == 0
    entry = runs.read(run)['skills']['manuscript-story']
    assert [i['kind'] for i in entry['issues']] == ['not_independent'] and 'skimmer' in entry['issues'][0]['message']
    write_findings(run, 'manuscript-story')
    assert finish(run, 'manuscript-story').exit_code == 0
    readme = (run / 'manuscript-story/README.md').read_text()
    assert 'seat: skimmer (one agent in turn, not independent)' in readme and 'seat: potential-user (fresh agent)' in readme
    data = runs.read(run)
    del data['skills']['manuscript-story']['artifacts'][1]['isolation']
    runs.save(run, data)
    assert any('does not record whether it ran as a fresh agent' in e for e in runs.problems(run, runs.read(run)))


def test_other_models_are_a_saved_project_choice_and_each_seat_records_its_model(manuscript: Path) -> None:
    """--other-model saves the models the panels also run on (manuscript-other-models), --one-model forgets them, and
    a referee registered with --model shows it in the manifest and the skill's README."""
    assert configure(manuscript, '--other-model', 'codex/gpt-5.6-sol', '--other-model', 'claude').exit_code == 0
    assert json.loads(resolve(manuscript).output)['project']['other_models'] == ['codex/gpt-5.6-sol', 'claude']
    bad = configure(manuscript, '--other-model', 'Codex CLI')
    assert bad.exit_code == 2 and 'CLI/MODEL' in bad.output
    assert configure(manuscript, '--other-model', 'codex', '--one-model').exit_code == 2
    report = manuscript.parent / 'findings.json'
    report.write_text('[]')
    run = start(manuscript, 'manuscript-peer-review')
    assert add(run, report, 'referee', 'manuscript-peer-review', '--seat', 'skeptic@codex', '--isolation', 'fresh-agent',
               '--model', 'codex/gpt-5.6-sol', '--name', 'referees/skeptic@codex.json').exit_code == 0
    [item] = runs.read(run)['skills']['manuscript-peer-review']['artifacts']
    assert item['model'] == 'codex/gpt-5.6-sol' and item['seat'] == 'skeptic@codex'
    assert 'seat: skeptic@codex (fresh agent), on codex/gpt-5.6-sol' in (run / 'manuscript-peer-review/README.md').read_text()
    assert configure(manuscript, '--one-model').exit_code == 0
    assert 'other_models' not in json.loads(resolve(manuscript).output)['project']
    (manuscript.parent / '.manuscript-skills.yaml').write_text('schema_version: 1\nother_models: codex\n')
    assert resolve(manuscript).exit_code == 2


def test_how_an_earlier_panel_output_ran_is_recorded_once_with_its_basis(manuscript: Path, tmp_path: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, 'manuscript-peer-review')
    data = runs.read(run)
    seat = tmp_path / 'findings.json'
    seat.write_text('{"findings": []}')
    item = runs.artifact(run, data, 'manuscript-peer-review', seat, 'other', 'seats/a/findings.json')
    item['role'] = 'referee'  # registered before outputs had to say how they ran
    runs.save(run, data)
    basis = ['--basis', 'The manifest notes that isolation followed the skill; each seat folder holds only its brief.']
    path = ['--path', 'manuscript-peer-review/seats/a/findings.json']
    ok = CliRunner().invoke(runs.app, ['isolation', str(run), '--skill', 'manuscript-peer-review', *path, '--isolation', 'fresh-agent', *basis])
    assert ok.exit_code == 0, ok.output
    recorded = runs.read(run)['skills']['manuscript-peer-review']
    assert recorded['artifacts'][-1]['isolation'] == 'fresh-agent' and recorded['artifacts'][-1]['isolation_recorded']['basis'].startswith('The manifest')
    assert any(i['kind'] == 'isolation_recorded_later' for i in recorded['issues'])
    again = CliRunner().invoke(runs.app, ['isolation', str(run), '--skill', 'manuscript-peer-review', *path, '--isolation', 'one-agent', *basis])
    assert again.exit_code != 0 and 'already records' in again.output


def test_a_story_stage_expects_the_readers_saved_for_the_project_and_a_critic_records_how_it_ran() -> None:
    assert runs.expected_readers({'context': {}}) == {'skimmer', 'potential-user', 'informed-outsider'}
    saved = {'context': {'project': {'readers': ['clinician: a hospital physician', 'Bio student: a second-year student']}}}
    assert runs.expected_readers(saved) == {'clinician', 'bio-student'}
    assert 'critic' in runs.PANEL and runs.Role('critic')


def _finished_run(manuscript: Path) -> Path:
    """A completed prose-edit run with a report, a command, a before/after, a dashboard and a stray workspace file."""
    assert configure(manuscript, '--keep', 'results').exit_code == 0
    run = start(manuscript)
    report = manuscript.parent / 'report.md'
    report.write_text('Full findings with actual coverage.')
    assert add(run, report).exit_code == 0
    command = runner.invoke(runs.app, ['exec', str(run), '--skill', 'manuscript-prose-edit', '--', sys.executable, '-c', "print('check')"])
    assert command.exit_code == 0, command.output
    assert runner.invoke(runs.app, ['change', str(run), '--skill', 'manuscript-prose-edit', '--section', 'Abstract',
                                    '--reason', 'Clearer.', '--after', str(report), '--shown-in-chat']).exit_code == 0
    (run / 'manuscript-prose-edit/workspace').mkdir()
    (run / 'manuscript-prose-edit/workspace/brief.md').write_text('A seat brief.')
    (run / 'manuscript-dashboard/dashboard').mkdir(parents=True)
    (run / 'manuscript-dashboard/dashboard/manuscript-dashboard.html').write_text('<html></html>')
    write_findings(run)
    assert finish(run).exit_code == 0
    return run


def test_pack_leaves_the_results_and_validates_the_evidence_inside_the_archive(manuscript: Path) -> None:
    run = _finished_run(manuscript)
    result = runner.invoke(runs.app, ['pack', str(run)])
    assert result.exit_code == 0, result.output
    left = sorted(p.relative_to(run).as_posix() for p in run.rglob('*') if p.is_file() and not p.name.startswith('.'))
    assert left == ['README.md', 'evidence.zip', 'manuscript-dashboard/dashboard/manuscript-dashboard.html',
                    'manuscript-prose-edit/README.md', 'manuscript-prose-edit/report.md', 'run.json']
    packed = runs.read(run)['packed']['files']
    assert {'inputs/01-paper.md', 'manuscript-prose-edit/changes/0001.md', 'manuscript-prose-edit/findings.json',
            'manuscript-prose-edit/workspace/brief.md'} <= set(packed)
    assert 'evidence.zip' in (run / 'README.md').read_text()
    assert 'in [evidence.zip](../evidence.zip)' in (run / 'manuscript-prose-edit/README.md').read_text()
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 0
    # A packed run takes no new evidence until it is unpacked.
    refused = add(run, manuscript.parent / 'report.md', 'check', 'manuscript-prose-edit', '--name', 'later.md')
    assert refused.exit_code == 3 and 'unpack' in refused.output
    assert runner.invoke(runs.app, ['unpack', str(run)]).exit_code == 0
    assert not (run / 'evidence.zip').exists() and 'packed' not in runs.read(run)
    assert (run / 'manuscript-prose-edit/workspace/brief.md').read_text() == 'A seat brief.'
    assert runner.invoke(runs.app, ['validate', str(run), '--final']).exit_code == 0
    assert add(run, manuscript.parent / 'report.md', 'check', 'manuscript-prose-edit', '--name', 'later.md').exit_code == 0


def test_pack_refuses_an_unfinished_run_and_a_lost_archive_fails_validation(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript)
    result = runner.invoke(runs.app, ['pack', str(run)])
    assert result.exit_code == 1 and 'still running' in result.output
    assert not (run / 'evidence.zip').exists()
    finished = _finished_run(manuscript)
    assert runner.invoke(runs.app, ['pack', str(finished)]).exit_code == 0
    (finished / 'evidence.zip').unlink()
    result = runner.invoke(runs.app, ['validate', str(finished), '--final'])
    assert result.exit_code == 1 and 'evidence archive' in result.output


def test_handover_puts_the_dashboard_and_word_file_beside_the_manuscript(manuscript: Path) -> None:
    run = _finished_run(manuscript)
    (run / 'manuscript-dashboard/manuscript-review.docx').write_bytes(b'first review')
    result = runner.invoke(runs.app, ['handover', str(run)])
    assert result.exit_code == 0, result.output
    html, docx = manuscript.parent / 'paper.dashboard.html', manuscript.parent / 'paper.review.docx'
    assert html.read_text() == '<html></html>' and docx.read_bytes() == b'first review'
    assert 'paper.dashboard.html' in (run / 'README.md').read_text()
    # The next run replaces the dashboard, but never a Word file the authors may have commented in: its own
    # goes beside it under a dated name, and the command says so without stopping for a question.
    docx.write_bytes(b'first review, with the authors comments')
    second = _finished_run(manuscript)
    (second / 'manuscript-dashboard/dashboard/manuscript-dashboard.html').write_text('<html>second</html>')
    (second / 'manuscript-dashboard/manuscript-review.docx').write_bytes(b'second review')
    result = runner.invoke(runs.app, ['handover', str(second)])
    assert result.exit_code == 0 and '--replace-docx' in result.output and 'kept as it is' in result.output
    assert html.read_text() == '<html>second</html>'
    assert docx.read_bytes() == b'first review, with the authors comments'
    [dated] = manuscript.parent.glob('paper.review.*.docx')
    assert dated.read_bytes() == b'second review'
    assert runner.invoke(runs.app, ['handover', str(second), '--replace-docx']).exit_code == 0
    assert docx.read_bytes() == b'second review'
    # A packed run still hands over: its deliverables stay outside the archive.
    assert runner.invoke(runs.app, ['pack', str(second)]).exit_code == 0
    assert runner.invoke(runs.app, ['handover', str(second)]).exit_code == 0
    assert not list(manuscript.parent.glob('.paper-*'))  # no temporary copy left behind


def test_handover_without_a_dashboard_says_so(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    result = runner.invoke(runs.app, ['handover', str(start(manuscript))])
    assert result.exit_code == 1 and 'render them first' in result.output
    assert not (manuscript.parent / 'paper.dashboard.html').exists()
