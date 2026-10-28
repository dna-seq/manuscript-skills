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


def test_the_reader_template_names_no_paper_of_its_own() -> None:
    """A filled brief copies the answer format; example values that name a real paper's sections or figures
    tell every reader where to look and what to miss."""
    panel = (ROOT / 'skills/manuscript-story/references/reader-panel.md').read_text(encoding='utf-8')
    block = panel.split('## What each seat returns', 1)[1].split('```', 2)[1]
    assert not re.search(r'section: "\d', block)
    assert not re.search(r'"Figures? \d', block)


def test_the_story_reads_across_paragraph_breaks_and_back_to_the_earliest_version() -> None:
    """Paper 1 v0.6's Introduction turned to longevity with no reason given, its "such extensible annotation tools"
    pointing back at nothing, and a full run let it through: the connected-sentences test read only inside a
    paragraph, the readers' answer format had no stumble for it, and accretion compared only with the previous
    version, which was already broken (evals: story-introduction-turn-seeded)."""
    story = ROOT / 'skills/manuscript-story'
    tests = (story / 'references/story-tests.md').read_text(encoding='utf-8')
    panel = (story / 'references/reader-panel.md').read_text(encoding='utf-8')
    skill = (story / 'SKILL.md').read_text(encoding='utf-8')
    numbers = [int(n) for n in re.findall(r'(?m)^\s*(\d+)\. \*\*', tests)]
    assert numbers == list(range(1, len(numbers) + 1))  # the tests cite each other by number
    assert '**Connected paragraphs.**' in tests and '*Connected paragraphs*' in panel and '*Connected paragraphs*' in skill
    block = panel.split('## What each seat returns', 1)[1].split('```', 2)[1]
    prompt = panel.split('## Prompt for a seat', 1)[1].split('\n## ', 1)[0]
    assert 'why is this here' in block and 'why is this here' in prompt  # a brief copies both
    assert all('earliest version the project holds' in ' '.join(text.split()) for text in (tests, skill))
