"""0.19.0 run contract: what the edit modes mean, the corrected version handed over without overwriting the
authors' files, numbered attempts, findings.json and an improvement run's deliverables at final validation,
connected manuscripts read through a reading copy, and an unreadable settings file that never stops a run."""

from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/manuscript-integrity-check/scripts'
sys.path.insert(0, str(SCRIPTS))

import project as projects  # noqa: E402
import runs  # noqa: E402

settings = projects.settings
runner = CliRunner()
URL = 'https://docs.example.org/document/d/abc123/edit'
TODAY = datetime.now().strftime('%Y%m%d')


@pytest.fixture()
def manuscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('MANUSCRIPT_SKILLS_CONFIG', str(tmp_path / 'global'))
    folder = tmp_path / 'paper one'
    folder.mkdir()
    path = folder / 'paper.md'
    path.write_text('# A test paper\n\n## Abstract\n\nLocal analysis.\n', encoding='utf-8')
    return path


def configure(path: Path, *args: str):
    return runner.invoke(projects.app, ['configure', str(path.parent), '--manuscript', path.name,
                                        '--no-code', '--output-dir', 'reviews', *args])


def invoke(*args: str):
    return runner.invoke(runs.app, [str(a) for a in args])


def start(path: Path, *skills: str) -> Path:
    result = invoke('start', path, *(x for s in skills for x in ('--skill', s)))
    assert result.exit_code == 0, (result.output, result.exception)
    return Path(result.output.strip())


def report(run: Path, skill: str, text: str = 'What the stage found, with its coverage.') -> None:
    source = run.parent / f'{skill}-report.md'
    source.write_text(text, encoding='utf-8')
    result = invoke('add', run, '--skill', skill, '--file', source, '--role', 'report', '--name', 'report.md')
    assert result.exit_code == 0, result.output


def findings(run: Path, skill: str, body: str | None = None) -> None:
    (run / skill).mkdir(parents=True, exist_ok=True)
    (run / skill / 'findings.json').write_text(
        body if body is not None else json.dumps({'skill': skill, 'findings': [], 'not_checked': []}), encoding='utf-8')


def finish(run: Path, skill: str, status: str = 'completed', *args: str):
    return invoke('finish', run, '--skill', skill, '--status', status, *args)


def put(run: Path, relative: str, body: str | bytes, mtime: float | None = None) -> Path:
    path = run / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body if isinstance(body, bytes) else body.encode('utf-8'))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


# --- The edit modes and where reports go, as the authors are asked them (settings.py) ----------------------------

def test_the_default_edit_mode_fixes_what_the_evidence_settles_and_only_propose_asks_one_by_one() -> None:
    edits = settings.SETTINGS['edits']
    assert list(edits.options) == ['conservative', 'propose', 'apply', 'none'] and edits.default == 'conservative'
    conservative = edits.options['conservative']
    assert conservative.startswith('Routine and evidence-backed fixes')
    assert 'confirmed problem settles' in conservative and 'proposals in the corrected version' in conservative
    assert 'never deleted' in conservative and 'only you can decide' in conservative
    assert 'one by one' in edits.options['propose'] and 'one by one' not in conservative
    assert 'substantive improvements' in edits.options['apply'] and 'within your direction' in edits.options['apply']
    assert 'evidence settles' in edits.why and 'without your approval' not in edits.why  # no queue of approvals


def test_reports_stay_in_the_run_and_a_focused_run_also_puts_a_copy_beside_the_manuscript() -> None:
    reports = settings.SETTINGS['reports']
    assert list(reports.options) == ['file', 'chat', 'both'] and reports.default == 'file'
    assert 'run folder' in reports.options['file'] and 'beside the manuscript' in reports.options['file']
    assert 'run folder still keeps it' in reports.options['chat']
    assert 'beside the manuscript' in reports.why and 'dashboard' in reports.why


def test_packing_is_described_as_a_verified_archive_that_unpack_restores() -> None:
    results = settings.SETTINGS['keep'].options['results']
    assert 'verified archive' in results and 'loose copies are removed' in results and 'restores' in results
    assert 'Nothing is deleted' not in results


# --- Handover: the corrected version, numbered attempts, never over the authors' files ---------------------------

def _improvement_run(manuscript: Path) -> Path:
    assert configure(manuscript).exit_code == 0
    return start(manuscript, 'manuscript-improve', 'manuscript-dashboard')


def test_handover_delivers_the_corrected_version_of_the_newest_attempt(manuscript: Path) -> None:
    run = _improvement_run(manuscript)
    put(run, 'manuscript-improve/revision/proposed.md', 'first attempt', mtime=2_000_000_000)
    put(run, 'manuscript-improve/revision.2/proposed.md', 'second attempt', mtime=1_000_000_000)  # older file, newer attempt
    put(run, 'manuscript-dashboard/dashboard/manuscript-dashboard.html', '<html>1</html>', mtime=2_000_000_000)
    put(run, 'manuscript-dashboard/dashboard.2/manuscript-dashboard.html', '<html>2</html>', mtime=1_000_000_000)
    result = invoke('handover', run)
    assert result.exit_code == 0, result.output
    folder = manuscript.parent
    assert (folder / 'paper.proposed.md').read_text(encoding='utf-8') == 'second attempt'
    assert (folder / 'paper.dashboard.html').read_text(encoding='utf-8') == '<html>2</html>'
    recorded = {item['kind']: item for item in runs.read(run)['handover']}
    assert recorded['corrected']['from'] == 'manuscript-improve/revision.2/proposed.md'
    assert recorded['corrected']['path'] == (folder / 'paper.proposed.md').as_posix()
    assert 'paper.proposed.md' in (run / 'README.md').read_text(encoding='utf-8')
    assert json.loads(result.output[:result.output.rindex('}') + 1])['kept'] == []


def test_a_latex_manuscript_gets_its_corrected_version_with_its_own_suffix(manuscript: Path) -> None:
    run = _improvement_run(manuscript)
    put(run, 'manuscript-improve/revision/proposed.tex', '\\section{Corrected}')
    assert invoke('handover', run).exit_code == 0
    assert (manuscript.parent / 'paper.proposed.tex').read_text(encoding='utf-8') == '\\section{Corrected}'


def test_a_different_corrected_version_already_there_is_kept_and_this_runs_goes_beside_it(manuscript: Path) -> None:
    run = _improvement_run(manuscript)
    mine = manuscript.parent / 'paper.proposed.md'
    mine.write_text('the authors edited this copy', encoding='utf-8')
    put(run, 'manuscript-improve/revision/proposed.md', 'this run')
    result = invoke('handover', run)
    assert result.exit_code == 0 and 'kept as it is' in result.output and '--replace-proposed' in result.output
    dated = manuscript.parent / f'paper.proposed.{TODAY}.md'
    assert mine.read_text(encoding='utf-8') == 'the authors edited this copy'
    assert dated.read_text(encoding='utf-8') == 'this run'
    [item] = runs.read(run)['handover']
    assert item['path'] == dated.as_posix() and item['kept'] == mine.as_posix()
    # Handing over again writes nothing new: the dated copy is already there.
    assert invoke('handover', run).exit_code == 0
    assert sorted(p.name for p in manuscript.parent.glob('paper.proposed*')) == [dated.name, mine.name]
    assert len(runs.read(run)['handover']) == 1
    # A later attempt that differs from both gets the next free dated name.
    put(run, 'manuscript-improve/revision.2/proposed.md', 'this run, second attempt')
    assert invoke('handover', run).exit_code == 0
    assert (manuscript.parent / f'paper.proposed.{TODAY}-2.md').read_text(encoding='utf-8') == 'this run, second attempt'
    # Only an explicit replace writes over the authors' copy.
    assert invoke('handover', run, '--replace-proposed').exit_code == 0
    assert mine.read_text(encoding='utf-8') == 'this run, second attempt'
    assert not list(manuscript.parent.glob('.paper-*'))


def test_replace_covers_the_word_file_and_the_corrected_version_together(manuscript: Path) -> None:
    run = _improvement_run(manuscript)
    for name in ('paper.review.docx', 'paper.proposed.md'):
        (manuscript.parent / name).write_bytes(b'the authors version')
    put(run, 'manuscript-dashboard/manuscript-review.docx', b'new review')
    put(run, 'manuscript-improve/revision/proposed.md', 'new corrected version')
    assert invoke('handover', run, '--replace').exit_code == 0
    assert (manuscript.parent / 'paper.review.docx').read_bytes() == b'new review'
    assert (manuscript.parent / 'paper.proposed.md').read_text(encoding='utf-8') == 'new corrected version'
    assert not list(manuscript.parent.glob(f'paper.*.{TODAY}*'))


def test_a_focused_run_hands_over_its_report_beside_the_manuscript(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, 'manuscript-reference-check')
    missing = invoke('handover', run, '--report', 'manuscript-reference-check')
    assert missing.exit_code == 1 and 'no saved report' in missing.output
    assert invoke('handover', run, '--report', 'manuscript-nonexistent').exit_code == 2
    report(run, 'manuscript-reference-check', 'Every reference checked.')
    result = invoke('handover', run, '--report', 'manuscript-reference-check')
    assert result.exit_code == 0, result.output
    copy = manuscript.parent / 'paper.reference-check.md'
    assert copy.read_text(encoding='utf-8') == 'Every reference checked.'
    assert runs.read(run)['handover'][0]['kind'] == 'report'
    # The same collision rule as the other copies: a different file there is kept.
    copy.write_text('Annotated by a co-author.', encoding='utf-8')
    result = invoke('handover', run, '--report', 'manuscript-reference-check')
    assert result.exit_code == 0 and '--replace' in result.output
    assert copy.read_text(encoding='utf-8') == 'Annotated by a co-author.'
    assert (manuscript.parent / f'paper.reference-check.{TODAY}.md').read_text(encoding='utf-8') == 'Every reference checked.'


def test_pack_keeps_the_newest_attempt_of_each_deliverable_and_archives_the_older(manuscript: Path) -> None:
    assert configure(manuscript, '--keep', 'results').exit_code == 0
    run = start(manuscript, 'manuscript-prose-edit')
    report(run, 'manuscript-prose-edit')
    findings(run, 'manuscript-prose-edit')
    for relative in ('manuscript-improve/revision/proposed.md', 'manuscript-improve/revision/changes.md',
                     'manuscript-improve/revision.2/proposed.md', 'manuscript-improve/revision.2/changes.md',
                     'manuscript-improve/revision.2/revision.json',
                     'manuscript-dashboard/dashboard/manuscript-dashboard.html',
                     'manuscript-dashboard/dashboard.2/manuscript-dashboard.html'):
        put(run, relative, relative)
    assert finish(run, 'manuscript-prose-edit').exit_code == 0
    result = invoke('pack', run)
    assert result.exit_code == 0, result.output
    left = {p.relative_to(run).as_posix() for p in run.rglob('*') if p.is_file() and not p.name.startswith('.')}
    assert {'manuscript-improve/revision.2/proposed.md', 'manuscript-improve/revision.2/changes.md',
            'manuscript-dashboard/dashboard.2/manuscript-dashboard.html'} <= left
    packed = set(runs.read(run)['packed']['files'])
    assert {'manuscript-improve/revision/proposed.md', 'manuscript-improve/revision/changes.md',
            'manuscript-improve/revision.2/revision.json',
            'manuscript-dashboard/dashboard/manuscript-dashboard.html'} <= packed
    assert invoke('validate', run, '--final').exit_code == 0  # findings.json is checked inside the archive
    assert invoke('unpack', run).exit_code == 0
    assert (run / 'manuscript-improve/revision/proposed.md').read_text(encoding='utf-8') == 'manuscript-improve/revision/proposed.md'


@pytest.mark.parametrize('relative, number', [
    ('manuscript-improve/revision/proposed.md', 1), ('manuscript-improve/revision.2/proposed.tex', 2),
    ('manuscript-improve/revision-3/proposed.md', 3), ('manuscript-dashboard/manuscript-dashboard.2.html', 2),
    ('manuscript-dashboard/findings.2.json', 2), ('manuscript-improve/revision-20261024/proposed.md', 1),
])
def test_attempt_numbers_come_from_the_numbered_names_never_from_a_date(relative: str, number: int) -> None:
    assert runs.attempt(relative) == number


# --- findings.json, and what an improvement run owes at the end ---------------------------------------------------

def test_a_finished_stage_needs_a_findings_file_with_a_findings_list(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, 'manuscript-integrity-check')
    report(run, 'manuscript-integrity-check')
    for status in ('completed', 'partial'):
        result = finish(run, 'manuscript-integrity-check', status, '--reason', 'Coverage stated.')
        assert result.exit_code == 1 and 'no findings.json' in result.output
    findings(run, 'manuscript-integrity-check', '{"findings": [')
    assert 'not valid JSON' in finish(run, 'manuscript-integrity-check').output
    findings(run, 'manuscript-integrity-check', '{"problems": []}')
    assert 'no findings list' in finish(run, 'manuscript-integrity-check').output
    findings(run, 'manuscript-integrity-check')  # nothing found is an empty list
    assert finish(run, 'manuscript-integrity-check').exit_code == 0
    assert invoke('validate', run, '--final').exit_code == 0
    # A blocked stage owes its reason, not a findings file.
    second = start(manuscript, 'manuscript-reporting-check')
    report(second, 'manuscript-reporting-check', 'The supplement could not be opened.')
    assert finish(second, 'manuscript-reporting-check', 'blocked', '--reason', 'Supplement unreadable.').exit_code == 0


@pytest.mark.parametrize('skill', ['manuscript-dashboard', 'manuscript-other-models', 'manuscript-mark-people'])
def test_the_utilities_that_write_no_findings_finish_without_one(manuscript: Path, skill: str) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, skill)
    report(run, skill)
    assert finish(run, skill).exit_code == 0
    assert invoke('validate', run, '--final').exit_code == 0


def test_an_improvement_run_validates_only_with_its_deliverables_or_a_recorded_reason(manuscript: Path) -> None:
    run = _improvement_run(manuscript)
    for skill in ('manuscript-improve', 'manuscript-dashboard'):
        report(run, skill)
        assert finish(run, skill).exit_code == 0  # finishing a stage does not yet ask for the end-of-run files
    result = invoke('validate', run, '--final')
    assert result.exit_code == 1
    missing = [p for p in json.loads(result.output)['problems'] if p.startswith('manuscript-improve:')]
    assert len(missing) == 4
    for words in ('adjudicated inventory', 'corrected version', 'rendered dashboard', 'Word version'):
        assert any(words in p for p in missing), words
    assert invoke('validate', run).exit_code == 0  # only the final validation asks for them
    assert invoke('pack', run).exit_code == 1
    put(run, 'manuscript-dashboard/findings.json', '{"findings": []}')
    put(run, 'manuscript-improve/revision/proposed.md', 'Corrected.')
    put(run, 'manuscript-dashboard/dashboard/manuscript-dashboard.html', '<html></html>')
    result = invoke('validate', run, '--final')
    assert result.exit_code == 1 and 'Word version' in result.output and 'corrected version' not in result.output
    put(run, 'manuscript-dashboard/manuscript-review.docx', b'review')
    assert invoke('validate', run, '--final').exit_code == 0


@pytest.mark.parametrize('skill, status', [('manuscript-dashboard', 'partial'), ('manuscript-dashboard', 'blocked'),
                                           ('manuscript-improve', 'partial'), ('manuscript-dashboard', 'not_run')])
def test_a_recorded_reason_explains_the_missing_end_of_run_files(manuscript: Path, skill: str, status: str) -> None:
    run = _improvement_run(manuscript)
    for name in ('manuscript-improve', 'manuscript-dashboard'):
        if name != skill or status != 'not_run':
            report(run, name)
        if name != skill:
            assert finish(run, name).exit_code == 0
    assert finish(run, skill, status).exit_code == 1  # the reason is required
    assert finish(run, skill, status, '--reason', 'The Word export failed twice; see its log.').exit_code == 0
    result = invoke('validate', run, '--final')
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)['workflow_complete'] is False


# --- A connected manuscript, read through its reading copy --------------------------------------------------------

@pytest.fixture()
def connected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv('MANUSCRIPT_SKILLS_CONFIG', str(tmp_path / 'global'))
    root = tmp_path / 'project'
    (root / 'exports').mkdir(parents=True)
    (root / 'exports/paper.md').write_text('# Connected paper\n\nExported text.\n', encoding='utf-8')
    result = runner.invoke(projects.app, ['configure', str(root), '--manuscript', URL, '--no-code',
                                          '--output-dir', 'reviews'])
    assert result.exit_code == 0, result.output
    return root


def test_a_connected_manuscript_without_a_reading_copy_creates_no_run(connected: Path) -> None:
    result = invoke('start', URL, '--project', connected, '--skill', 'manuscript-prose-edit')
    assert result.exit_code == 3 and 'reading copy' in result.output and 'No run was created' in result.output
    assert not (connected / 'reviews').exists()
    absent = invoke('start', URL, '--project', connected, '--skill', 'manuscript-prose-edit',
                    '--reading-copy', connected / 'exports/missing.md')
    assert absent.exit_code == 3 and 'Reading copy not found' in absent.output
    extra = invoke('start', URL, '--project', connected, '--skill', 'manuscript-prose-edit',
                   '--reading-copy', connected / 'exports/paper.md', '--reading-copy', connected / 'exports/paper.md')
    assert extra.exit_code == 2 and not (connected / 'reviews').exists()


def test_the_reading_copy_is_snapshotted_with_the_connected_version_and_names_the_handover(connected: Path) -> None:
    copy = connected / 'exports/paper.md'
    result = invoke('start', URL, '--project', connected, '--skill', 'manuscript-improve',
                    '--reading-copy', copy, '--connected-version', 'rev-42')
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    [source] = runs.read(run)['inputs']
    assert source['remote'] == URL and source['connected_version'] == 'rev-42'
    assert source['original'] == copy.as_posix() and (run / source['snapshot']).read_bytes() == copy.read_bytes()
    put(run, 'manuscript-improve/revision/proposed.md', 'Corrected.')
    assert invoke('handover', run).exit_code == 0  # no --to or --stem needed
    assert (connected / 'paper.proposed.md').read_text(encoding='utf-8') == 'Corrected.'
    # The reading copy is an export: removing it later is not a lost manuscript.
    report(run, 'manuscript-improve')
    copy.unlink()
    assert not [p for p in runs.problems(run, runs.read(run), final=False) if 'source' in p]


def test_a_saved_reading_copy_is_used_by_every_run(connected: Path) -> None:
    result = runner.invoke(projects.app, ['configure', str(connected), '--manuscript', URL,
                                          '--reading-copy', 'exports/paper.md'])
    assert result.exit_code == 0, result.output
    saved = yaml.safe_load((connected / projects.CONFIG).read_text(encoding='utf-8'))
    assert saved['reading_copies'] == {URL: 'exports/paper.md'}
    run = start_connected(connected)
    assert runs.read(run)['inputs'][0]['remote'] == URL
    # Naming the saved reading copy instead of the URL finds the same project and source.
    by_copy = invoke('start', connected / 'exports/paper.md', '--skill', 'manuscript-prose-edit')
    assert by_copy.exit_code == 0, by_copy.output
    assert runs.read(Path(by_copy.output.strip()))['inputs'][0]['remote'] == URL
    too_many = runner.invoke(projects.app, ['configure', str(connected), '--reading-copy', 'a.md', '--reading-copy', 'b.md'])
    assert too_many.exit_code == 2 and 'one --reading-copy per URL' in too_many.output


def start_connected(root: Path) -> Path:
    result = invoke('start', URL, '--project', root, '--skill', 'manuscript-prose-edit')
    assert result.exit_code == 0, result.output
    return Path(result.output.strip())


def test_a_connected_supplement_without_a_copy_is_named_in_the_run_index(manuscript: Path) -> None:
    supplement = 'https://docs.example.org/document/d/supp/edit'
    result = runner.invoke(projects.app, ['configure', str(manuscript.parent), '--manuscript', manuscript.name,
                                          '--manuscript', supplement, '--no-code', '--output-dir', 'reviews'])
    assert result.exit_code == 0, result.output
    run = start(manuscript, 'manuscript-prose-edit')
    data = runs.read(run)
    assert [s['snapshot'] for s in data['inputs']] == ['inputs/01-paper.md'] and data['not_snapshotted'] == [supplement]
    assert f'Not snapshotted: {supplement}' in (run / 'README.md').read_text(encoding='utf-8')


# --- An unreadable settings file never stops the run --------------------------------------------------------------

def _break_settings() -> Path:
    path = settings.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('edits: [apply\n', encoding='utf-8')
    return path


def test_an_unreadable_settings_file_gives_a_ready_context_that_proposes(manuscript: Path) -> None:
    broken = _break_settings()
    result = configure(manuscript)  # setup goes on; nothing is copied from the unreadable file
    assert result.exit_code == 0 and 'No global choice was copied' in result.output
    assert 'settings' not in yaml.safe_load((manuscript.parent / projects.CONFIG).read_text(encoding='utf-8'))
    result = runner.invoke(projects.app, ['resolve', str(manuscript), '--json'])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data['status'] == 'ready' and 'fix or delete it' in data['settings_error']
    assert data['effective']['edits'] == 'propose' and data['sources']['edits'] == 'settings_error'
    assert data['effective']['reports'] == 'file' and data['effective']['keep'] == 'everything'
    [decision] = data['decisions']
    assert decision['key'] == 'settings_file' and 'proposes every change' in decision['question']
    run = start(manuscript, 'manuscript-prose-edit')
    context = runs.read(run)['context']
    assert context['effective']['edits'] == 'propose' and context['settings_error']
    assert broken.read_text(encoding='utf-8') == 'edits: [apply\n'


def test_a_choice_saved_for_the_manuscript_still_applies_when_the_global_file_is_unreadable(manuscript: Path) -> None:
    assert configure(manuscript, '--edits', 'apply').exit_code == 0
    _break_settings()
    data = json.loads(runner.invoke(projects.app, ['resolve', str(manuscript), '--json']).output)
    assert data['effective']['edits'] == 'apply' and data['sources']['edits'] == 'project'
    assert 'follows the choices saved for this manuscript' in data['decisions'][0]['question']
    readable = json.loads(runner.invoke(projects.app, ['resolve', str(manuscript), '--json', '--edits', 'conservative']).output)
    assert readable['effective']['edits'] == 'conservative' and readable['sources']['edits'] == 'conversation'


def test_a_readable_settings_file_has_no_error_and_no_decision(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    data = json.loads(runner.invoke(projects.app, ['resolve', str(manuscript), '--json']).output)
    assert data['settings_error'] is None and data['decisions'] == [] and data['effective']['edits'] == 'conservative'


# --- Cross-platform ------------------------------------------------------------------------------------------------

def test_saved_and_recorded_paths_use_forward_slashes(manuscript: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = manuscript.parent
    assert projects.stored_location(root, 'sub/dir/paper.md') == 'sub/dir/paper.md'

    def other_drive(path, start=None):
        raise ValueError('path is on mount D:, start on mount C:')
    monkeypatch.setattr(projects.os.path, 'relpath', other_drive)
    assert projects.stored_location(root, str(root / 'paper.md')) == (root / 'paper.md').as_posix()
    monkeypatch.undo()
    monkeypatch.setenv('MANUSCRIPT_SKILLS_CONFIG', str(root.parent / 'global'))
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, 'manuscript-prose-edit')
    data = runs.read(run)
    assert '\\' not in data['inputs'][0]['original'] and '\\' not in data['context']['project_file']


def test_the_scripts_print_utf8_whatever_the_console(monkeypatch: pytest.MonkeyPatch) -> None:
    streams = [io.TextIOWrapper(io.BytesIO(), encoding='cp1252') for _ in range(2)]
    monkeypatch.setattr(sys, 'stdout', streams[0])
    monkeypatch.setattr(sys, 'stderr', streams[1])
    settings.utf8_streams()
    assert [s.encoding for s in streams] == ['utf-8', 'utf-8']
    for name in ('runs.py', 'project.py', 'settings.py'):
        text = (SCRIPTS / name).read_text(encoding='utf-8')
        assert 'reconfigure(encoding="utf-8", errors="replace")' in text, name
        assert not re.search(r'\bfcntl\b|os\.killpg|SIGKILL|start_new_session', text), name
        assert not re.search(r'\.(read_text|write_text)\(\)', text), name
        assert not [m for m in re.findall(r"open\(([^)]*)\)", text) if "'x'" in m and 'encoding' not in m], name


@pytest.mark.parametrize('platform, env, expected', [
    ('win32', {'HOME': '/c/Users/a', 'USERPROFILE': 'C:/Users/a'}, 'C:/Users/a/AppData/Roaming/manuscript-skills'),
    ('linux', {'HOME': '/home/a', 'XDG_CONFIG_HOME': 'relative/config'}, '/home/a/.config/manuscript-skills'),
])
def test_the_settings_folder_ignores_a_unix_home_on_windows_and_a_relative_xdg_folder(platform, env, expected) -> None:
    assert settings.config_dir(env, platform) == Path(expected)
