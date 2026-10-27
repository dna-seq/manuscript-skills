"""Progress records in run.json (docs/progress-ui.md): when each stage started and finished, the coordinator's own
stages, the run waiting for the authors, the planned stages and each stage's counts. All optional: a run without
them still validates, and every new command takes the writer lock like the others."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/manuscript-integrity-check/scripts'
sys.path.insert(0, str(SCRIPTS))

import project as projects  # noqa: E402
import runs  # noqa: E402

runner = CliRunner()


@pytest.fixture()
def manuscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('MANUSCRIPT_SKILLS_CONFIG', str(tmp_path / 'global'))
    folder = tmp_path / 'paper'
    folder.mkdir()
    path = folder / 'paper.md'
    path.write_text('# A test paper\n\n## Abstract\n\nLocal analysis.\n', encoding='utf-8')
    result = runner.invoke(projects.app, ['configure', str(folder), '--manuscript', path.name, '--no-code',
                                          '--output-dir', 'reviews'])
    assert result.exit_code == 0, result.output
    return path


def invoke(*args: object):
    return runner.invoke(runs.app, [str(a) for a in args])


def start(path: Path, *args: str) -> Path:
    result = invoke('start', path, *args)
    assert result.exit_code == 0, (result.output, result.exception)
    return Path(result.output.strip())


def report(run: Path, skill: str) -> None:
    source = run.parent / f'{skill}-report.md'
    source.write_text('What the stage found, with its coverage.', encoding='utf-8')
    result = invoke('add', run, '--skill', skill, '--file', source, '--role', 'report', '--name', 'report.md')
    assert result.exit_code == 0, result.output


def findings(run: Path, skill: str, body: dict, name: str = 'findings.json') -> None:
    (run / skill).mkdir(parents=True, exist_ok=True)
    (run / skill / name).write_text(json.dumps(body), encoding='utf-8')


def manifest(run: Path) -> dict:
    return runs.read(run)


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


# --- Start and finish times ---------------------------------------------------------------------------------

def test_the_skills_named_at_start_start_with_the_run_and_a_later_stage_with_its_first_record(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    data = manifest(run)
    assert data['skills']['manuscript-improve']['started_at'] == data['started_at']
    report(run, 'manuscript-figures')  # a stage that began without `begin`: its first record starts it
    first = manifest(run)['skills']['manuscript-figures']['started_at']
    assert moment(first) >= moment(data['started_at'])
    result = invoke('issue', run, '--skill', 'manuscript-figures', '--kind', 'note', '--message', 'Later record.')
    assert result.exit_code == 0 and manifest(run)['skills']['manuscript-figures']['started_at'] == first


def test_begin_starts_a_stage_before_it_records_anything_and_keeps_its_first_start(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    result = invoke('begin', run, '--skill', 'manuscript-prose-edit')
    assert result.exit_code == 0, result.output
    assert result.output.strip() == str(run / 'manuscript-prose-edit')
    entry = manifest(run)['skills']['manuscript-prose-edit']
    assert entry['status'] == 'running' and entry['artifacts'] == [] and entry['started_at']
    assert invoke('begin', run, '--skill', 'manuscript-prose-edit').exit_code == 0  # idempotent
    report(run, 'manuscript-prose-edit')
    assert manifest(run)['skills']['manuscript-prose-edit']['started_at'] == entry['started_at']
    assert (run / 'manuscript-prose-edit' / 'README.md').is_file()


def test_begin_refuses_an_unknown_skill_and_changes_nothing(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    before = (run / 'run.json').read_text(encoding='utf-8')
    result = invoke('begin', run, '--skill', 'manuscript-nothing')
    assert result.exit_code == 2 and 'Unknown manuscript skill' in result.output
    assert (run / 'run.json').read_text(encoding='utf-8') == before


def test_finish_records_when_the_stage_finished(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-integrity-check')
    report(run, 'manuscript-integrity-check')
    findings(run, 'manuscript-integrity-check', {'findings': []})
    result = invoke('finish', run, '--skill', 'manuscript-integrity-check', '--status', 'completed')
    assert result.exit_code == 0, result.output
    entry = manifest(run)['skills']['manuscript-integrity-check']
    assert moment(entry['finished_at']) >= moment(entry['started_at'])


def test_a_refused_finish_records_no_finish_time(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-integrity-check')
    report(run, 'manuscript-integrity-check')  # no findings.json: completed is refused
    assert invoke('finish', run, '--skill', 'manuscript-integrity-check', '--status', 'completed').exit_code == 1
    entry = manifest(run)['skills']['manuscript-integrity-check']
    assert entry['status'] == 'running' and 'finished_at' not in entry and 'counts' not in entry


def test_a_stage_skipped_before_it_began_has_no_start(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    result = invoke('finish', run, '--skill', 'manuscript-policy-fit', '--status', 'not_run', '--reason', 'No clinical scope.')
    assert result.exit_code == 0, result.output
    entry = manifest(run)['skills']['manuscript-policy-fit']
    assert entry['status'] == 'not_run' and 'started_at' not in entry and entry['finished_at']


# --- Counts at finish --------------------------------------------------------------------------------------

def test_finish_counts_the_newest_findings_its_proposals_and_the_decisions_for_the_authors(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-integrity-check')
    report(run, 'manuscript-integrity-check')
    findings(run, 'manuscript-integrity-check', {'findings': [{'id': 'ic-1'}]})
    findings(run, 'manuscript-integrity-check', {
        'findings': [{'id': 'ic-1', 'decision': False}, {'id': 'ic-2', 'decision': True}, {'id': 'ic-3', 'decision': 'yes'}],
        'changes': [{'before': 'a', 'after': 'b'}, {'before': 'c', 'after': 'd'}]}, name='findings.2.json')
    findings(run, 'manuscript-integrity-check', {'findings': [{'id': 'x'}] * 9}, name='findings.draft.json')  # never counted
    result = invoke('finish', run, '--skill', 'manuscript-integrity-check', '--status', 'completed')
    assert result.exit_code == 0, result.output
    data = manifest(run)
    assert data['skills']['manuscript-integrity-check']['counts'] == {'findings': 3, 'proposals': 2, 'decisions': 1}
    index = (run / 'README.md').read_text(encoding='utf-8')
    assert '3 finding(s), 2 proposal(s), 1 decision(s) for the authors.' in index


def test_a_stage_without_a_findings_file_gets_no_counts(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-mark-people')
    report(run, 'manuscript-mark-people')
    assert invoke('finish', run, '--skill', 'manuscript-mark-people', '--status', 'completed').exit_code == 0
    assert 'counts' not in manifest(run)['skills']['manuscript-mark-people']


# --- The plan ----------------------------------------------------------------------------------------------

def test_start_records_the_planned_stages_in_order(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve', '--plan', 'manuscript-integrity-check', '--plan', 'revise',
                '--plan', 'manuscript-prose-edit', '--plan', 'revise', '--plan', 'manuscript-dashboard',
                '--plan', 'corrected', '--plan', 'recheck', '--plan', 'handover')
    data = manifest(run)
    assert data['plan'] == ['manuscript-integrity-check', 'revise', 'manuscript-prose-edit', 'manuscript-dashboard',
                            'corrected', 'recheck', 'handover']
    assert list(data['skills']) == ['manuscript-improve']  # planned stages have not begun
    assert 'Planned stages: manuscript-integrity-check, revise,' in (run / 'README.md').read_text(encoding='utf-8')


def test_a_run_without_a_plan_records_none(manuscript: Path) -> None:
    assert 'plan' not in manifest(start(manuscript, '--skill', 'manuscript-story'))


def test_an_unknown_planned_stage_creates_no_run(manuscript: Path) -> None:
    result = invoke('start', manuscript, '--skill', 'manuscript-improve', '--plan', 'polish')
    assert result.exit_code == 2 and 'planned stage' in result.output
    assert not (manuscript.parent / 'reviews').exists()


def test_the_coordinator_replaces_the_plan_when_it_begins(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve', '--plan', 'manuscript-integrity-check')
    result = invoke('begin', run, '--skill', 'manuscript-improve', '--plan', 'manuscript-reference-check', '--plan', 'handover')
    assert result.exit_code == 0, result.output
    assert manifest(run)['plan'] == ['manuscript-reference-check', 'handover']
    assert invoke('begin', run, '--skill', 'manuscript-improve').exit_code == 0  # without --plan the plan stays
    assert manifest(run)['plan'] == ['manuscript-reference-check', 'handover']


# --- The coordinator's own stages ---------------------------------------------------------------------------

def test_stage_records_the_coordinators_steps_with_their_times(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    assert invoke('stage', run, '--name', 'revise', '--status', 'running').exit_code == 0
    record = manifest(run)['skills']['manuscript-improve']['stages']['revise']
    assert record['status'] == 'running' and record['started_at'] and record['finished_at'] is None
    assert record['reason'] == ''
    assert invoke('stage', run, '--name', 'revise', '--status', 'completed').exit_code == 0
    done = manifest(run)['skills']['manuscript-improve']['stages']['revise']
    assert done['status'] == 'completed' and done['started_at'] == record['started_at']
    assert moment(done['finished_at']) >= moment(done['started_at'])
    readme = (run / 'manuscript-improve' / 'README.md').read_text(encoding='utf-8')
    assert 'Status: **running**.' in readme and '- Stage revise: **completed**' in readme


def test_a_stage_started_again_keeps_its_first_start_and_is_running_again(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    for status in ('running', 'completed', 'running'):
        assert invoke('stage', run, '--name', 'corrected', '--status', status).exit_code == 0
    stages = manifest(run)['skills']['manuscript-improve']['stages']
    assert stages['corrected']['status'] == 'running' and stages['corrected']['finished_at'] is None


@pytest.mark.parametrize('status', ['partial', 'blocked', 'not_run'])
def test_an_unfinished_or_skipped_stage_says_why(manuscript: Path, status: str) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    refused = invoke('stage', run, '--name', 'recheck', '--status', status)
    assert refused.exit_code == 2 and '--reason' in refused.output
    assert 'stages' not in manifest(run)['skills']['manuscript-improve']
    result = invoke('stage', run, '--name', 'recheck', '--status', status, '--reason', 'Report only:  no corrected version.')
    assert result.exit_code == 0, result.output
    record = manifest(run)['skills']['manuscript-improve']['stages']['recheck']
    assert record['status'] == status and record['reason'] == 'Report only: no corrected version.'
    assert record['started_at'] is None and record['finished_at']  # never recorded running: its start is unknown


def test_stage_takes_only_the_coordinators_steps_and_statuses(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    assert invoke('stage', run, '--name', 'deslop', '--status', 'running').exit_code == 2
    assert invoke('stage', run, '--name', 'handover', '--status', 'reused').exit_code == 2
    assert 'stages' not in manifest(run)['skills']['manuscript-improve']


def test_the_coordinators_stages_do_not_change_what_final_validation_asks(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    for name in ('revise', 'corrected', 'recheck'):
        assert invoke('stage', run, '--name', name, '--status', 'not_run', '--reason', 'Stopped early.').exit_code == 0
    report(run, 'manuscript-improve')
    assert invoke('finish', run, '--skill', 'manuscript-improve', '--status', 'partial', '--reason', 'Stopped early.').exit_code == 0
    result = invoke('validate', run, '--final')
    assert result.exit_code == 0, result.output


# --- Waiting for the authors --------------------------------------------------------------------------------

def test_wait_records_the_questions_and_resume_clears_them(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    result = invoke('wait', run, '--question', 'Which journal first?', '--question', 'Is the cohort  public?')
    assert result.exit_code == 0, result.output
    waiting = manifest(run)['waiting']
    assert waiting['questions'] == ['Which journal first?', 'Is the cohort public?'] and waiting['since']
    index = (run / 'README.md').read_text(encoding='utf-8')
    assert '**Waiting for the authors**' in index and '- Which journal first?' in index
    again = invoke('wait', run, '--question', 'Is the cohort public?', '--question', 'Keep Figure 4?')
    assert again.exit_code == 0 and '3 question(s)' in again.output
    later = manifest(run)['waiting']
    assert later['since'] == waiting['since']
    assert later['questions'] == ['Which journal first?', 'Is the cohort public?', 'Keep Figure 4?']
    assert invoke('resume', run).exit_code == 0
    assert 'waiting' not in manifest(run)
    assert 'Waiting for the authors' not in (run / 'README.md').read_text(encoding='utf-8')


def test_wait_needs_a_question_and_resume_on_a_running_run_changes_nothing(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    assert invoke('wait', run, '--question', '   ').exit_code == 2
    assert invoke('wait', run).exit_code == 2
    before = (run / 'run.json').read_text(encoding='utf-8')
    result = invoke('resume', run)
    assert result.exit_code == 0 and 'not waiting' in result.output
    assert (run / 'run.json').read_text(encoding='utf-8') == before


# --- Older runs, the lock and a packed run -----------------------------------------------------------------

def test_a_run_from_before_the_progress_records_still_validates_and_takes_them(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-integrity-check')
    report(run, 'manuscript-integrity-check')
    findings(run, 'manuscript-integrity-check', {'findings': []})
    data = manifest(run)
    del data['skills']['manuscript-integrity-check']['started_at']  # as runs.py 0.29 wrote it
    (run / 'run.json').write_text(json.dumps(data), encoding='utf-8')
    assert invoke('validate', run).exit_code == 0
    assert invoke('begin', run, '--skill', 'manuscript-integrity-check').exit_code == 0
    assert manifest(run)['skills']['manuscript-integrity-check']['started_at']
    assert invoke('finish', run, '--skill', 'manuscript-integrity-check', '--status', 'completed').exit_code == 0
    assert invoke('validate', run, '--final').exit_code == 0


@pytest.mark.parametrize('command', [
    ['begin', '--skill', 'manuscript-story'],
    ['stage', '--name', 'revise', '--status', 'running'],
    ['wait', '--question', 'Which journal?'],
    ['resume'],
])
def test_the_progress_commands_wait_for_the_active_writer(manuscript: Path, command: list[str]) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    before = (run / 'run.json').read_text(encoding='utf-8')
    with runs.FileLock(run / '.writer.lock'):
        result = invoke(command[0], run, *command[1:])
    assert result.exit_code == 3 and 'Run is busy' in result.output
    assert (run / 'run.json').read_text(encoding='utf-8') == before


def test_a_packed_run_takes_no_progress_record_until_unpacked(manuscript: Path) -> None:
    run = start(manuscript, '--skill', 'manuscript-improve')
    data = manifest(run)
    data['packed'] = {'archive': runs.ARCHIVE, 'files': {}}
    (run / 'run.json').write_text(json.dumps(data), encoding='utf-8')
    result = invoke('wait', run, '--question', 'Which journal?')
    assert result.exit_code == 3 and 'unpack' in result.output
    assert 'waiting' not in manifest(run)
