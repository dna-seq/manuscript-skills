"""0.19.0 shared contracts: the adjudicated inventory is never the unmerged draft, a stage's newest findings
attempt is the one counted, and the shared documents agree on the edit modes, the severity scale and the
end-of-stage checklist."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/manuscript-integrity-check/scripts'))

import runs  # noqa: E402

PRIORITIES = ROOT / 'skills/manuscript-integrity-check/references/author-priorities.md'
WORKFLOW = ROOT / 'skills/manuscript-integrity-check/references/project-workflow.md'
STAGE_FINDINGS = ROOT / 'skills/manuscript-dashboard/references/stage-findings.md'


def _write(run: Path, relative: str, body: dict) -> None:
    path = run / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding='utf-8')


def test_an_unmerged_draft_is_not_the_adjudicated_inventory(tmp_path: Path) -> None:
    _write(tmp_path, 'manuscript-dashboard/findings.draft.json', {'findings': []})
    assert runs.findings_files(tmp_path, {}, 'manuscript-dashboard') == []
    _write(tmp_path, 'manuscript-dashboard/findings.json', {'findings': []})
    _write(tmp_path, 'manuscript-dashboard/findings.2.json', {'findings': []})
    assert runs.findings_files(tmp_path, {}, 'manuscript-dashboard') == [
        'manuscript-dashboard/findings.json', 'manuscript-dashboard/findings.2.json']


def test_a_stage_is_judged_by_its_newest_findings_attempt(tmp_path: Path) -> None:
    (tmp_path / 'manuscript-story').mkdir()
    (tmp_path / 'manuscript-story/findings.json').write_text('not json', encoding='utf-8')
    assert 'not valid JSON' in runs.findings_problem(tmp_path, {}, 'manuscript-story')
    _write(tmp_path, 'manuscript-story/findings.2.json', {'findings': []})
    assert runs.findings_problem(tmp_path, {}, 'manuscript-story') is None


def test_the_shared_documents_name_one_severity_scale() -> None:
    table = STAGE_FINDINGS.read_text(encoding='utf-8')
    for value, words in (('blocker', 'Blocker'), ('major', 'Major'), ('minor', 'Minor'), ('info', 'Optional'),
                         ('unknown', 'Could not be checked')):
        assert re.search(rf"\| `{value}` \| {words} \|", table), value
    priorities = PRIORITIES.read_text(encoding='utf-8')
    for words in ('**Blocker:**', '**Major:**', '**Minor:**', '**Optional:**', '**Could not be checked:**'):
        assert words in priorities


def test_fix_everything_and_the_held_decisions_are_defined_once() -> None:
    priorities = PRIORITIES.read_text(encoding='utf-8')
    assert '**"Fix everything".**' in priorities
    assert '**Held decisions, under every setting.**' in priorities
    assert 'grant permission to change everything' not in priorities
    assert 'This is the only per-item mode' in priorities


def test_the_end_of_stage_checklist_is_where_the_skills_point() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')
    assert '### End-of-stage checklist' in workflow
    pointing = [path.parent.name for path in ROOT.glob('skills/*/SKILL.md')
                if 'end-of-stage-checklist' in path.read_text(encoding='utf-8')]
    assert len(pointing) >= 5, pointing
