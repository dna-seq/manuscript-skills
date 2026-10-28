"""Edits applied to a manuscript that keeps revision marks, 0.46 (docs/run-audit-2026-10.md, items 6 and 9): in the
Paper 1 v0.6 run every editing stage wrote its own script to find a clean before-text in the marked master, change
it, bump or open a segment and record it, and revise.py joined an added reference to the entry before it."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "manuscript-integrity-check" / "scripts"))

import project as projects  # noqa: E402
import runs  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


marks = load("rev_marks", ROOT / "skills/manuscript-revision-marks/scripts/rev_marks.py")
viz = load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
revise = load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")
collect = load("collect", ROOT / "skills/manuscript-dashboard/scripts/collect.py")
runner = CliRunner()
BY = marks.Entry("claude", date(2026, 10, 28))

MARKED = """# Paper

## Introduction

Genomes are cheap. <!-- @rev C1 rounds=1 by=anna:2026-10-01 -->We use HuggingFace for data and Polars for
tables.<!-- @/rev C1 --> It is fast.

Second paragraph has a typo teh here.

Third paragraph has another typo teh too.

<!-- @rev C2 rounds=1 by=anna:2026-10-01 -->
A paragraph held by C2 with its last line
<!-- @/rev C2 -->
running on outside it, with teh last typo.

## Methods

Fourth paragraph, also with teh typo.
"""


def clean(text: str) -> str:
    return marks.strip_marks(text)


def test_an_edit_is_found_in_the_clean_text_and_its_segment_gets_one_round_for_the_pass() -> None:
    """The before-text spans the C1 mark in the marked file; only the changed words are touched, inside C1."""
    edits = [marks.Edit("Genomes are cheap. We use HuggingFace for data", "Genomes are cheap. We use Hugging Face for data"),
             marks.Edit("Polars for\ntables.", "Polars for\nits tables.")]
    done = marks.apply_edits(MARKED, edits, BY)
    assert done.places == ("C1", "C1") and done.bumped == ("C1",) and done.opened == ()
    assert "<!-- @rev C1 rounds=2 by=anna:2026-10-01,claude:2026-10-28 -->" in done.text
    expected = clean(MARKED).replace("HuggingFace", "Hugging Face").replace("for\ntables", "for\nits tables")
    assert clean(done.text) == expected and not marks.parse(done.text).errors


def test_routine_fixes_outside_segments_share_the_section_s_copy_edit_segment() -> None:
    edits = [marks.Edit("a typo teh here", "a typo the here"), marks.Edit("another typo teh too", "another typo the too"),
             marks.Edit("also with teh typo", "also with the typo")]
    done = marks.apply_edits(MARKED, edits, BY)
    # Two fixes in the Introduction share N1, grown to the second paragraph; the Methods fix opens N2.
    assert done.places == ("N1", "N1", "N2") and done.opened == ("N1", "N2") and done.bumped == ()
    found = marks.parse(done.text)
    assert not found.errors
    n1 = found.segment("N1")
    assert "a typo the here" in n1.text and "another typo the too" in n1.text and n1.rounds == 1
    assert done.sections == ("Introduction", "Introduction", "Methods")


def test_an_edit_s_own_segment_id_and_a_segment_it_would_cut_taken_in_whole() -> None:
    done = marks.apply_edits(MARKED, [marks.Edit("with teh last typo", "with the last typo", segment="IC4")], BY)
    found = marks.parse(done.text)
    assert not found.errors and done.opened == ("IC4",)
    ic4, c2 = found.segment("IC4"), found.segment("C2")
    assert ic4.open.start < c2.open.start and c2.close.end < ic4.close.end  # C2 inside, whole


def test_an_inserted_heading_is_marked_on_its_own_lines() -> None:
    done = marks.apply_edits(MARKED, [marks.Edit("## Methods", "## Methods\n\n### Data")], BY)
    found = marks.parse(done.text)
    assert not found.errors and found.segment("N1").text.strip() == "### Data"


@pytest.mark.parametrize("edit, words", [
    (marks.Edit("cheap. We use", "cheap, and we use"), "a revision mark sits inside the words it changes"),
    (marks.Edit("teh", "the"), "occurs 3 times"),  # the first edit already fixed one
    (marks.Edit("not in the paper", "x"), "is not in the clean text"),
    (marks.Edit("", "x"), "no before-text")])
def test_a_refused_edit_changes_nothing_and_says_why(edit, words) -> None:
    with pytest.raises(marks.EditRefused, match=words):
        marks.apply_edits(MARKED, [marks.Edit("a typo teh here", "a typo the here"), edit], BY)


def test_a_manuscript_without_marks_gets_none() -> None:
    plain = clean(MARKED)
    done = marks.apply_edits(plain, [marks.Edit("a typo teh here", "a typo the here")], BY)
    assert "@rev" not in done.text and done.text == plain.replace("a typo teh here", "a typo the here")


def test_rev_marks_apply_writes_the_file(tmp_path: Path) -> None:
    paper, edits = tmp_path / "paper.md", tmp_path / "edits.json"
    paper.write_text(MARKED, encoding="utf-8")
    edits.write_text(json.dumps([{"before": "a typo teh here", "after": "a typo the here"}]), encoding="utf-8")
    assert marks.main(["apply", str(paper), str(edits), "--by", "claude:2026-10-28"]) == 0
    assert "<!-- @rev N1 rounds=1 by=claude:2026-10-28 -->" in paper.read_text(encoding="utf-8")
    edits.write_text(json.dumps([{"before": "teh", "after": "the"}]), encoding="utf-8")
    before = paper.read_text(encoding="utf-8")
    assert marks.main(["apply", str(paper), str(edits), "--by", "claude"]) == 1
    assert paper.read_text(encoding="utf-8") == before


# --- runs.py apply ------------------------------------------------------------------------------------------------

@pytest.fixture()
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path / "global"))
    folder = tmp_path / "paper"
    folder.mkdir()
    (folder / "paper.md").write_text(MARKED, encoding="utf-8")
    (folder / "paper-supplementary.md").write_text("# Supplement\n\nTable S1 lists 412 participants.\n",
                                                    encoding="utf-8")
    assert runner.invoke(projects.app, ["configure", str(folder), "--manuscript", "paper.md", "--manuscript",
                                        "paper-supplementary.md", "--no-code", "--output-dir", "reviews"]).exit_code == 0
    started = runner.invoke(runs.app, ["start", str(folder / "paper.md"), "--skill", "manuscript-prose-edit"])
    assert started.exit_code == 0, started.output
    return Path(started.output.strip())


def apply(run: Path, edits: list[dict], *more: str):
    path = run.parent / "edits.json"
    path.write_text(json.dumps(edits), encoding="utf-8")
    return runner.invoke(runs.app, ["apply", str(run), "--skill", "manuscript-prose-edit", "--edits", str(path),
                                    "--by", "claude", *more])


def test_runs_apply_edits_marks_and_records_in_one_step_and_collect_replays_it(run: Path) -> None:
    paper = run.parents[1] / "paper.md"
    result = apply(run, [
        {"before": "Genomes are cheap. We use HuggingFace for data", "after": "Genomes are cheap. We use Hugging Face for data",
         "reason": "Product name. Hugging Face is two words."},
        {"before": "a typo teh here", "after": "a typo the here", "reason": "Typo.", "comment": "Is this the word?"}])
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["applied"] == 2 and out["segments_bumped"] == ["C1"] and out["segments_opened"] == ["N1"]
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    changes = data["skills"]["manuscript-prose-edit"]["changes"]
    assert [c["section"] for c in changes] == ["Introduction", "Introduction"]
    record = (run / changes[1]["path"]).read_text(encoding="utf-8")
    assert "Comment: Is this the word?" in record and "## Before\n\na typo teh here" in record
    # collect replays the records on the clean copies and counts both applied.
    revised = clean(paper.read_text(encoding="utf-8"))
    replayed = collect.recorded_changes(run, data, run, revised, clean(MARKED))
    assert [r["status"] for r in replayed] == ["applied", "applied"]


def test_runs_apply_to_the_supplement_names_it_and_a_refusal_leaves_everything(run: Path) -> None:
    supplement = run.parents[1] / "paper-supplementary.md"
    done = apply(run, [{"before": "lists 412", "after": "lists the 412", "reason": "Article."}],
                 "--document", "paper-supplementary.md")
    assert done.exit_code == 0, done.output
    assert "lists the 412" in supplement.read_text(encoding="utf-8")
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert data["skills"]["manuscript-prose-edit"]["changes"][0]["document"] == "paper-supplementary.md"
    paper = run.parents[1] / "paper.md"
    refused = apply(run, [{"before": "a typo teh here", "after": "a typo the here", "reason": "Typo."},
                          {"before": "teh", "after": "the", "reason": "Typo."}])
    assert refused.exit_code == 1 and "Nothing was applied or recorded" in refused.output
    assert paper.read_text(encoding="utf-8") == MARKED
    assert len(json.loads((run / "run.json").read_text())["skills"]["manuscript-prose-edit"]["changes"]) == 1
    assert apply(run, [{"before": "a typo teh here", "after": "x"}]).exit_code == 2  # no reason


# --- revise.py: a reference entry added after another -----------------------------------------------------------

def test_a_reference_added_to_a_list_of_one_entry_per_paragraph_is_a_paragraph_of_its_own() -> None:
    original = ("# T\n\nText (Adams, 2020; Baker, 2019).\n\n## References\n\nAdams, A. (2020). One. *J*, 1.\n\n"
                "Cole, C. (2021). Three. *J*, 2.\n")
    evidence = [{"path": "review.md", "quote": "The review."}]
    raw = {"schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
           "coverage": [{"skill": "manuscript-reference-check", "status": "completed", "note": "All.", "evidence": evidence}],
           "findings": [], "manuscript": {"title": "T", "path": "original.md", "sections": []},
           "changes": [{"id": "RF-C1", "kind": "Proposed edit", "section": "References", "summary": "Add Baker",
                        "status": "proposed", "before": None, "after": "Baker, B. (2019). Two. *J*, 3.",
                        "anchor": "Adams, A. (2020). One. *J*, 1.", "evidence": evidence},
                       {"id": "PE-C1", "kind": "Proposed edit", "section": "T", "summary": "A sentence",
                        "status": "proposed", "before": None, "after": "It is local.", "anchor": "Text (Adams, 2020; Baker, 2019).",
                        "evidence": evidence}]}
    document, record = revise.build(original, original, viz.Inventory.model_validate(raw), {})
    assert document.current() == ("# T\n\nText (Adams, 2020; Baker, 2019). It is local.\n\n## References\n\n"
                                  "Adams, A. (2020). One. *J*, 1.\n\nBaker, B. (2019). Two. *J*, 3.\n\n"
                                  "Cole, C. (2021). Three. *J*, 2.\n")
    assert not record["not_placed"]
