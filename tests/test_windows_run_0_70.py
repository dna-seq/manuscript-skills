"""0.70.0: what a run on Windows hit (a run of 19 November 2026, plugin 0.69.1, a project folder under OneDrive
whose name has spaces). Change records were written with CRLF and the evidence check read raw bytes; summary.json
named its evidence with "\\"; collect and stage_check read the authors' original file instead of the new version
that versions: immutable puts the edits in."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/manuscript-dashboard/scripts'))
sys.path.insert(0, str(ROOT / 'skills/manuscript-integrity-check/scripts'))

import dashboard  # noqa: E402
import runs  # noqa: E402
import stage_check  # noqa: E402


def test_change_records_are_written_with_lf_on_every_system() -> None:
    """Text mode on Windows writes "\\n" as CRLF unless newline="" is given."""
    source = inspect.getsource(runs.record_change)
    assert "newline=''" in source


def test_evidence_written_with_crlf_is_found_and_hashed_under_a_posix_path(tmp_path: Path) -> None:
    record = tmp_path / 'manuscript-improve' / 'changes'
    record.mkdir(parents=True)
    body = '# Main text\r\n\r\nReason: Clearer.\r\n\r\n## Before\r\n\r\nOne.\r\n\r\nTwo.\r\n\r\n## After\r\n\r\nOne, two.\r\n'
    (record / '0001.md').write_bytes(body.encode('utf-8'))
    windows_path = 'manuscript-improve\\changes\\0001.md' if sys.platform == 'win32' else 'manuscript-improve/changes/0001.md'
    change = dashboard.Change(id='PE-C1', kind='prose', section='Main text', summary='Joined.', status='applied',
                              before='One.\n\nTwo.', after='One, two.',
                              evidence=[dashboard.Evidence(path=windows_path, quote='One.\n\nTwo.')])
    data = SimpleNamespace(coverage=[], findings=[], changes=[change], reference=None)
    hashes = dashboard.verify_evidence(data, tmp_path)
    assert list(hashes) == ['manuscript-improve/changes/0001.md']


def test_validate_reads_a_dashboard_summary_written_with_backslashes(tmp_path: Path) -> None:
    folder = tmp_path / 'manuscript-dashboard' / 'dashboard'
    folder.mkdir(parents=True)
    summary = {'evidence_sha256': {'..\\manuscript-improve\\changes\\0001.md': 'abc'}}
    (folder / 'summary.json').write_text(json.dumps(summary), encoding='utf-8')
    (folder / 'manuscript-dashboard.html').write_text('<html></html>', encoding='utf-8')
    data = {'skills': {'manuscript-dashboard': {'artifacts': [
        {'path': 'manuscript-dashboard/dashboard/manuscript-dashboard.html', 'role': 'check'},
        {'path': 'manuscript-dashboard/dashboard/summary.json', 'role': 'check'}]}}}
    assert runs.dashboard_shows(tmp_path, data) == {('manuscript-improve/changes/0001.md', 'abc')}


def test_the_new_version_is_read_under_immutable_versions(tmp_path: Path) -> None:
    folder = tmp_path / 'Brief Communication final revisions'
    folder.mkdir()
    original, new = folder / 'paper.md', folder / 'paper_v2.md'
    original.write_text('The original sentence.\n', encoding='utf-8')
    new.write_text('The edited sentence.\n', encoding='utf-8')
    run = tmp_path / 'run'
    (run / 'inputs').mkdir(parents=True)
    (run / 'inputs' / '01-paper.md').write_text('The original sentence.\n', encoding='utf-8')
    data = {'inputs': [{'original': original.as_posix(), 'snapshot': 'inputs/01-paper.md'}],
            'versions': [{'previous': original.as_posix(), 'new': new.as_posix()}]}
    assert stage_check.current_file(data, original.as_posix()) == new
    # spelled with "\\" (as Windows prints it), it is the same file
    assert stage_check.current_file(data, original.as_posix().replace('/', '\\')) == new
    # a version made from the new version is followed too
    third = folder / 'paper_v3.md'
    data_twice = {**data, 'versions': [*data['versions'], {'previous': new.as_posix(), 'new': third.as_posix()}]}
    assert stage_check.current_file(data_twice, original.as_posix()) == third
    # without a version the original is the file
    assert stage_check.current_file({'versions': []}, original.as_posix()) == Path(original.as_posix())
    texts = stage_check.input_texts(run, data)
    assert texts[0]['marked'] == ['The original sentence.\n', 'The edited sentence.\n']


def test_collect_reads_the_new_versions_of_the_manuscript_and_its_supplement(tmp_path: Path) -> None:
    import collect
    folder = tmp_path / 'paper folder'
    folder.mkdir()
    run = tmp_path / 'run'
    (run / 'inputs').mkdir(parents=True)
    versions, inputs = [], []
    for n, name in enumerate(('paper', 'supplement'), start=1):
        original, new = folder / f'{name}.md', folder / f'{name}_v2.md'
        original.write_text(f'The {name} as written.\n', encoding='utf-8')
        new.write_text(f'The {name} as edited.\n', encoding='utf-8')
        (run / 'inputs' / f'0{n}-{name}.md').write_text(f'The {name} as written.\n', encoding='utf-8')
        inputs.append({'original': original.as_posix(), 'snapshot': f'inputs/0{n}-{name}.md'})
        versions.append({'previous': original.as_posix(), 'new': new.as_posix()})
    data = {'inputs': inputs, 'versions': versions}
    current = stage_check.current_file(data, inputs[0]['original']).read_text(encoding='utf-8')
    revised, reviewed, others, name = collect.clean_texts(run, data, run / inputs[0]['snapshot'],
                                                          Path(inputs[0]['original']), current)
    assert (revised, reviewed, name) == ('The paper as edited.\n', 'The paper as written.\n', 'paper.md')
    assert others == [('supplement.md', 'The supplement as written.\n', 'The supplement as edited.\n')]
