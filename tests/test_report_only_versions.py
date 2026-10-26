"""0.27.0 run contract: a report-only edit mode (edits: none) that changes no file of the authors, and immutable
versions (versions: immutable), where the run's edits go into a new version file and no earlier one is changed."""

from __future__ import annotations

import json
import sys
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


def invoke(*args: str | Path):
    return runner.invoke(runs.app, [str(a) for a in args])


def start(path: Path, *skills: str, extra: tuple[str, ...] = ()) -> Path:
    result = invoke('start', path, *(x for s in skills for x in ('--skill', s)), *extra)
    assert result.exit_code == 0, (result.output, result.exception)
    return Path(result.output.strip())


def report(run: Path, skill: str) -> None:
    source = run.parent / f'{skill}-report.md'
    source.write_text('What the stage found, with its coverage.', encoding='utf-8')
    assert invoke('add', run, '--skill', skill, '--file', source, '--role', 'report', '--name', 'report.md').exit_code == 0
    (run / skill / 'findings.json').write_text(json.dumps({'skill': skill, 'findings': [], 'not_checked': []}),
                                               encoding='utf-8')


def change(run: Path, text: str = 'A clearer sentence.'):
    after = run.parent / 'after.md'
    after.write_text(text, encoding='utf-8')
    return invoke('change', run, '--skill', 'manuscript-prose-edit', '--section', 'Abstract', '--reason', 'Clearer.',
                  '--after', after, '--shown-in-chat')


def put(run: Path, relative: str, body: str | bytes) -> None:
    path = run / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body if isinstance(body, bytes) else body.encode('utf-8'))


# --- The settings, as the authors are asked them -----------------------------------------------------------------

def test_report_only_and_immutable_versions_are_choices_the_authors_are_asked_once() -> None:
    edits, versions = settings.SETTINGS['edits'], settings.SETTINGS['versions']
    assert edits.default == 'apply' and edits.options['none'].startswith('Report only')
    assert 'no corrected version' in edits.options['none']
    assert list(versions.options) == ['in-place', 'immutable'] and versions.default == 'in-place'
    assert 'never changed' in versions.options['immutable'] and 'new version' in versions.options['immutable']
    assert 'pre-edit' in versions.options['in-place'] and 'immutable' in versions.why
    # Until an unreadable settings file is repaired, nothing is applied and nothing already written is replaced.
    assert settings.WHEN_UNREADABLE == {'edits': 'propose', 'versions': 'immutable'}


def test_a_conversation_override_at_start_holds_for_that_run_only(manuscript: Path) -> None:
    assert configure(manuscript).exit_code == 0
    run = start(manuscript, 'manuscript-prose-edit', extra=('--edits', 'none', '--versions', 'immutable'))
    effective = runs.read(run)['context']['effective']
    assert (effective['edits'], effective['versions']) == ('none', 'immutable')
    later = runs.read(start(manuscript, 'manuscript-prose-edit'))['context']['effective']
    assert (later['edits'], later['versions']) == ('apply', 'in-place')


# --- Report only: no edit, no new version, no corrected version ----------------------------------------------------

def test_a_report_only_run_records_no_edit_and_fails_when_the_manuscript_changed(manuscript: Path) -> None:
    assert configure(manuscript, '--edits', 'none').exit_code == 0
    run = start(manuscript, 'manuscript-prose-edit')
    assert 'Report only (edits: none)' in (run / 'README.md').read_text(encoding='utf-8')
    refused = change(run)
    assert refused.exit_code == 2 and 'report only' in refused.output
    refused = invoke('version', run)
    assert refused.exit_code == 2 and 'no new version' in refused.output
    report(run, 'manuscript-prose-edit')
    assert invoke('finish', run, '--skill', 'manuscript-prose-edit', '--status', 'completed').exit_code == 0
    assert invoke('validate', run, '--final').exit_code == 0
    # A routine-only explanation does not excuse a change in a run that changes no file.
    manuscript.write_text(manuscript.read_text(encoding='utf-8') + '\nAdded.\n', encoding='utf-8')
    result = invoke('finish', run, '--skill', 'manuscript-prose-edit', '--status', 'completed',
                    '--routine-only-reason', 'Spelling only.')
    assert result.exit_code == 1 and 'report-only run' in result.output


def test_a_report_only_improvement_run_owes_no_corrected_version(manuscript: Path) -> None:
    assert configure(manuscript, '--edits', 'none').exit_code == 0
    run = start(manuscript, 'manuscript-improve', 'manuscript-dashboard')
    for skill in ('manuscript-improve', 'manuscript-dashboard'):
        report(run, skill)
        assert invoke('finish', run, '--skill', skill, '--status', 'completed').exit_code == 0
    put(run, 'manuscript-dashboard/findings.json', '{"findings": []}')
    put(run, 'manuscript-dashboard/dashboard/manuscript-dashboard.html', '<html></html>')
    put(run, 'manuscript-dashboard/manuscript-review.docx', b'review')
    result = invoke('validate', run, '--final')
    assert result.exit_code == 0, result.output
    handed = invoke('handover', run)
    assert handed.exit_code == 0 and not list(manuscript.parent.glob('paper.proposed*'))


# --- Immutable versions: the edits go into a new file, the earlier one stays as it was -------------------------------

@pytest.mark.parametrize('name, expected', [
    ('paper.md', 'paper_v2.md'),
    ('paper_v2.docx', 'paper_v3.docx'),
    ('Paper-Rev-04.tex', 'Paper-Rev-05.tex'),
    ('manuscript.v7.md', 'manuscript.v8.md'),
    ('paper version 3.docx', 'paper version 4.docx'),
    ('my-paper.md', 'my-paper-v2.md'),
    ('My Paper.docx', 'My Paper v2.docx'),
    ('paper_final.md', 'paper_final_v2.md'),
    ('scan3.md', 'scan3_v2.md'),  # a number that is not the authors' version number
])
def test_the_next_version_counts_on_the_authors_own_number(tmp_path: Path, name: str, expected: str) -> None:
    assert runs.next_version(tmp_path / name) == tmp_path / expected


def test_the_next_version_never_lands_on_an_existing_file(tmp_path: Path) -> None:
    (tmp_path / 'paper_v3.md').write_text('the authors own later draft')
    assert runs.next_version(tmp_path / 'paper_v2.md') == tmp_path / 'paper_v4.md'
    (tmp_path / 'paper_v2.md').write_text('an earlier draft')
    assert runs.next_version(tmp_path / 'paper.md') == tmp_path / 'paper_v4.md'


def test_immutable_versions_put_the_edits_in_a_new_file_that_the_next_run_reads(manuscript: Path) -> None:
    assert configure(manuscript, '--versions', 'immutable').exit_code == 0
    original = manuscript.read_bytes()
    run = start(manuscript, 'manuscript-prose-edit')
    made = invoke('version', run)
    assert made.exit_code == 0, made.output
    new = Path(made.output.strip())
    assert new == manuscript.parent / 'paper_v2.md' and new.read_bytes() == original
    assert invoke('version', run).output.strip() == new.as_posix()  # asked again: the same new version
    assert sorted(p.name for p in manuscript.parent.glob('paper*.md')) == ['paper.md', 'paper_v2.md']
    new.write_text(new.read_text(encoding='utf-8') + '\nA clearer sentence.\n', encoding='utf-8')
    assert change(run).exit_code == 0
    report(run, 'manuscript-prose-edit')
    assert invoke('finish', run, '--skill', 'manuscript-prose-edit', '--status', 'completed').exit_code == 0
    assert invoke('validate', run, '--final').exit_code == 0
    assert manuscript.read_bytes() == original
    assert 'New version: ' in (run / 'README.md').read_text(encoding='utf-8')
    # The project's mapping names the new version, so the next run starts from it and versions it again.
    saved = yaml.safe_load((manuscript.parent / projects.CONFIG).read_text(encoding='utf-8'))
    assert saved['manuscripts'] == ['paper_v2.md'] and saved['settings'] == {'versions': 'immutable'}
    following = start(new, 'manuscript-prose-edit')
    assert Path(invoke('version', following).output.strip()) == manuscript.parent / 'paper_v3.md'
    assert new.read_text(encoding='utf-8').endswith('A clearer sentence.\n')


def test_an_earlier_version_edited_in_place_fails_even_with_a_change_record(manuscript: Path) -> None:
    assert configure(manuscript, '--versions', 'immutable').exit_code == 0
    run = start(manuscript, 'manuscript-prose-edit')
    manuscript.write_text(manuscript.read_text(encoding='utf-8') + '\nA clearer sentence.\n', encoding='utf-8')
    assert change(run).exit_code == 0
    report(run, 'manuscript-prose-edit')
    result = invoke('finish', run, '--skill', 'manuscript-prose-edit', '--status', 'completed')
    assert result.exit_code == 1 and 'versions are immutable' in result.output and 'runs.py version' in result.output


def test_a_new_version_changed_without_a_record_fails(manuscript: Path) -> None:
    assert configure(manuscript, '--versions', 'immutable').exit_code == 0
    run = start(manuscript, 'manuscript-prose-edit')
    new = Path(invoke('version', run).output.strip())
    new.write_text('Rewritten without a record.\n', encoding='utf-8')
    report(run, 'manuscript-prose-edit')
    result = invoke('finish', run, '--skill', 'manuscript-prose-edit', '--status', 'completed')
    assert result.exit_code == 1 and 'new version changed without a change record' in result.output


def test_a_bibliography_the_run_changes_gets_its_own_new_version(manuscript: Path) -> None:
    assert configure(manuscript, '--versions', 'immutable').exit_code == 0
    bibliography = manuscript.parent / 'refs.bib'
    bibliography.write_text('@article{a, title={A}}\n', encoding='utf-8')
    run = start(manuscript, 'manuscript-reference-check')
    made = invoke('version', run, '--file', bibliography)
    assert Path(made.output.strip()) == manuscript.parent / 'refs_v2.bib'
    saved = yaml.safe_load((manuscript.parent / projects.CONFIG).read_text(encoding='utf-8'))
    assert saved['manuscripts'] == ['paper.md']  # not a manuscript: the mapping is unchanged
    bibliography.write_text('@article{a, title={B}}\n', encoding='utf-8')
    assert 'versions are immutable: ' in invoke('validate', run).output


def test_immutable_handover_replaces_nothing_already_beside_the_manuscript(manuscript: Path) -> None:
    assert configure(manuscript, '--versions', 'immutable').exit_code == 0
    first = start(manuscript, 'manuscript-dashboard')
    put(first, 'manuscript-dashboard/dashboard/manuscript-dashboard.html', '<html>first</html>')
    assert invoke('handover', first).exit_code == 0
    html = manuscript.parent / 'paper.dashboard.html'
    assert html.read_text(encoding='utf-8') == '<html>first</html>'
    second = start(manuscript, 'manuscript-dashboard')
    put(second, 'manuscript-dashboard/dashboard/manuscript-dashboard.html', '<html>second</html>')
    refused = invoke('handover', second, '--replace')
    assert refused.exit_code == 2 and 'immutable' in refused.output
    assert invoke('handover', second).exit_code == 0
    assert html.read_text(encoding='utf-8') == '<html>first</html>'
    [dated] = manuscript.parent.glob('paper.dashboard.*.html')
    assert dated.read_text(encoding='utf-8') == '<html>second</html>'
