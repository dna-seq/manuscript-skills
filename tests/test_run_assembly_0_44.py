"""The end of a run without run-local scripts, 0.44 (docs/run-audit-2026-10.md): change records replayed on clean
copies, each on its own file; the reference list drawn from the manuscript's scan and ended where the list ends;
stage findings checked when the stage finishes; the plugin the run started on recorded; a busy run waited for."""
from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
sys.path.insert(0, str(SKILLS / "manuscript-integrity-check" / "scripts"))

import project as projects  # noqa: E402
import runs  # noqa: E402


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Each script imports the modules loaded before it under these names.
viz = load("dashboard", SKILLS / "manuscript-dashboard/scripts/dashboard.py")
stage_check = load("stage_check", SKILLS / "manuscript-dashboard/scripts/stage_check.py")
revise = load("revise", SKILLS / "manuscript-improve/scripts/revise.py")
collect = load("collect", SKILLS / "manuscript-dashboard/scripts/collect.py")
scan = load("scan", SKILLS / "manuscript-integrity-check/scripts/scan.py")
marks = load("rev_marks", SKILLS / "manuscript-revision-marks/scripts/rev_marks.py")
runner = CliRunner()

# The supplement repeats the manuscript's sentence, as Paper 1's Supplement S12 repeated Section 2.1.
SHARED = "The current annotation engine also distinguishes called genotypes from restored ones."
MAIN = f"""# A tool

## 1. Introduction

Genomes are cheap. <!-- @rev C1 rounds=1 by=claude:2026-10-27 -->We use HuggingFace for data.<!-- @/rev C1 --> It is fast.

## 2. Methods

{SHARED}
"""
SUPPLEMENT = f"""# Supplementary Data

**S12. Restoration.** {SHARED}
"""


def record(run: Path, skill: str, number: int, section: str, before: str | None, after: str | None) -> dict:
    path = run / skill / "changes" / f"{number:04d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {section}\n\nReason: why {skill} {number}.\n\n## Before\n\n{before or '(No previous block.)'}"
                    f"\n\n## After\n\n{after or '(Block removed.)'}\n", encoding="utf-8")
    return {"path": f"{skill}/changes/{number:04d}.md", "recorded_at": f"2026-10-27T1{number}:00:00+00:00"}


def clean(text: str) -> str:
    return marks.strip_marks(text)


def test_an_edit_across_a_revision_mark_and_a_supplement_edit_each_replay_on_their_own_clean_file(tmp_path: Path) -> None:
    """Replayed on the marked text, the first edit (its before-text crosses the C1 mark) counted as not applied;
    replayed on the manuscript, the supplement's edit changed the manuscript's copy of the shared sentence."""
    span = "Genomes are cheap. We use HuggingFace for data."
    main_after = clean(MAIN).replace(span, "Genomes are cheap. We use Hugging Face for data.")
    sup_after = clean(SUPPLEMENT).replace(f"**S12. Restoration.** {SHARED}",
                                          "**S12. Restoration.** The current annotation engine distinguishes called "
                                          "genotypes from restored ones.")
    data = {"skills": {
        "manuscript-prose-edit": {"changes": [record(tmp_path, "manuscript-prose-edit", 1, "1. Introduction", span,
                                                     "Genomes are cheap. We use Hugging Face for data.")]},
        "manuscript-deslop": {"changes": [record(tmp_path, "manuscript-deslop", 2, "Supplement S12. Restoration", SHARED,
                                                 "The current annotation engine distinguishes called genotypes from "
                                                 "restored ones.")]}}}
    # The marked texts would not replay: the before-text is not in them.
    assert span not in MAIN
    records = collect.recorded_changes(tmp_path, data, tmp_path, clean(main_after), clean(MAIN),
                                       [("paper-supplementary.md", clean(SUPPLEMENT), sup_after)], "paper.md")
    by_id = {r["id"]: r for r in records}
    assert by_id["prose-edit.C1"]["status"] == "applied" and by_id["prose-edit.C1"]["document"] == ""
    assert by_id["deslop.C1"]["status"] == "applied"
    assert by_id["deslop.C1"]["document"] == "paper-supplementary.md"
    # The corrected version is built from the manuscript and leaves the supplement's edit alone.
    raw = {"schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
           "coverage": [{"skill": "manuscript-improve", "status": "completed", "note": "All.",
                         "evidence": [{"path": "review.md", "quote": "The review."}]}],
           "findings": [], "manuscript": {"title": "A tool", "path": "original.md", "sections": []},
           "changes": [{**r, "kind": r["kind"], "evidence": [{"path": "review.md", "quote": "The review."}]}
                       for r in records]}
    hold_old_style = {"hold": [{"id": "deslop.C1", "why": "Applied to the supplement file."}]}
    document, built = revise.build(clean(MAIN), clean(main_after), viz.Inventory.model_validate(raw), hold_old_style)
    assert document.previous() == clean(MAIN) and document.current() == clean(main_after)
    assert built["applied"] == ["prose-edit.C1"]
    assert built["other_files"] == [{"id": "deslop.C1", "document": "paper-supplementary.md", "status": "applied",
                                     "section": "Supplement S12. Restoration", "summary": "why manuscript-deslop 2."}]


def test_a_record_names_its_file_and_an_unknown_file_is_refused(tmp_path: Path) -> None:
    documents = [("", "Alpha beta gamma.", "Alpha beta gamma."), ("sup.md", "Alpha beta gamma.", "Alpha beta gamma.")]
    assert collect.document_of({"document": "sup.md"}, "1. Introduction", "Alpha", "A", documents, "paper.md") == "sup.md"
    assert collect.document_of({"document": "paper.md"}, "S1", "Alpha", "A", documents, "paper.md") == ""
    with pytest.raises(ValueError, match="not one of the run's inputs"):
        collect.document_of({"document": "other.md"}, "S1", "Alpha", "A", documents, "paper.md")
    # Without a name: the only file holding the text, else a Supplement section's supplement, else the manuscript.
    only = [("", "Alpha.", "Alpha."), ("sup.md", "Delta.", "Delta.")]
    assert collect.document_of({}, "1. Introduction", "Delta.", "Epsilon.", only, "paper.md") == "sup.md"
    assert collect.document_of({}, "Supplement S2", "Alpha beta", "A", documents, "paper.md") == "sup.md"
    assert collect.document_of({}, "2. Methods", "Alpha beta", "A", documents, "paper.md") == ""


def test_an_addition_without_a_before_text_does_not_spoil_the_replay(tmp_path: Path) -> None:
    """An addition cannot be placed by the replay; before 0.44 it made every record fall back to the weaker test,
    which counts an edit a later stage edited again as not applied."""
    start = "# T\n\nOne two three four.\n"
    current = "# T\n\nOne two three five, now.\n\n## Keywords\n\nReads.\n"
    data = {"skills": {
        "manuscript-prose-edit": {"changes": [record(tmp_path, "manuscript-prose-edit", 1, "T", "One two three four.",
                                                     "One two three five.")]},
        "manuscript-story": {"changes": [record(tmp_path, "manuscript-story", 2, "T", "One two three five.",
                                                "One two three five, now.")]},
        "manuscript-journal-adapt": {"changes": [record(tmp_path, "manuscript-journal-adapt", 3, "T", None,
                                                        "## Keywords\n\nReads.")]}}}
    records = collect.recorded_changes(tmp_path, data, tmp_path, current, start)
    assert [r["status"] for r in records] == ["applied", "applied", "applied"]


def test_collect_reads_the_whole_run_on_clean_copies_and_draws_the_manuscript_s_references(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "inputs").mkdir(parents=True)
    paper, sup = tmp_path / "paper.md", tmp_path / "paper-supplementary.md"
    span = "Genomes are cheap. We use HuggingFace for data."
    paper.write_text(MAIN.replace("We use HuggingFace for data.", "We use Hugging Face for data."), encoding="utf-8")
    sup.write_text(SUPPLEMENT, encoding="utf-8")
    (run / "inputs/01-paper.md").write_text(MAIN, encoding="utf-8")
    (run / "inputs/02-paper-supplementary.md").write_text(SUPPLEMENT, encoding="utf-8")
    change = record(run, "manuscript-prose-edit", 1, "1. Introduction", span,
                    "Genomes are cheap. We use Hugging Face for data.")
    (run / "manuscript-prose-edit/stage-report.md").write_text("The prose edit.", encoding="utf-8")
    (run / "manuscript-prose-edit/README.md").write_text("# manuscript-prose-edit\n\nStatus: **completed**.\n",
                                                         encoding="utf-8")
    (run / "manuscript-prose-edit/findings.json").write_text(json.dumps({"skill": "manuscript-prose-edit",
                                                                         "findings": []}), encoding="utf-8")
    # Two scans: the supplement's sorts first and holds a list of its own.
    for name, path, entries in (("references-supplementary.json", "inputs/02-paper-supplementary.md", 9),
                                ("references.json", "inputs/01-paper.md", 2)):
        folder = run / "manuscript-reference-check"
        folder.mkdir(exist_ok=True)
        (folder / name).write_text(json.dumps({"path": str(run / path), "findings": [], "references": [
            {"line": n, "text": f"Author{n}, A. (2020). Work {n}.", "status": "ok"} for n in range(entries)]}))
    data = {"schema_version": 1, "run_id": "r", "started_at": "2026-10-27T12:00:00+00:00", "context": {},
            "inputs": [{"original": str(paper), "snapshot": "inputs/01-paper.md", "sha256": "x"},
                       {"original": str(sup), "snapshot": "inputs/02-paper-supplementary.md", "sha256": "y"}],
            "skills": {"manuscript-prose-edit": {"status": "completed", "changes": [change], "artifacts": [],
                                                 "issues": [], "commands": []}}}
    (run / "run.json").write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(run / "out/findings.draft.json")])
    assert result.exit_code == 0, (result.output, repr(result.exception),
                                   traceback.format_tb(result.exc_info[2]) if result.exc_info else None)
    inventory = json.loads((run / "out/findings.draft.json").read_text(encoding="utf-8"))
    assert [c["status"] for c in inventory["changes"]] == ["applied"]
    assert len(inventory["reference_list"]) == 2
    assert collect.reference_list(run) and len(collect.reference_list(run)) == 9  # without inputs: the old order


def test_a_stage_file_collect_cannot_read_is_named_record_by_record(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "manuscript-policy-fit").mkdir(parents=True)
    (run / "manuscript-policy-fit/findings.json").write_text(json.dumps({"findings": [], "changes": [
        {"id": "PF-C1", "section": "Ethics", "summary": "Say so.", "status": "proposed", "before": "a b c",
         "after": "a b d", "evidence": "The report says so."}]}), encoding="utf-8")
    assert collect.contract_errors(run) == [
        "manuscript-policy-fit/findings.json: change PF-C1: no kind",
        "manuscript-policy-fit/findings.json: change PF-C1: evidence is a sentence; it must be a list of "
        "{\"path\": FILE, \"quote\": \"a verbatim sentence of that file\"} (for the report's sentence, path "
        "stage-report.md)"]


# --- the stage check ----------------------------------------------------------------------------------------------

def inputs(tmp_path: Path) -> list[dict]:
    paper, sup = tmp_path / "paper.md", tmp_path / "paper-supplementary.md"
    paper.write_text(MAIN, encoding="utf-8")
    sup.write_text(SUPPLEMENT, encoding="utf-8")
    return [{"name": p.name, "marked": [p.read_text()] * 2, "clean": [clean(p.read_text())] * 2} for p in (paper, sup)]


def test_the_stage_check_places_quotes_and_proposals_in_their_files(tmp_path: Path) -> None:
    folder = tmp_path / "stage"
    folder.mkdir()
    (folder / "stage-report.md").write_text("The tool is fast. It joins by position.", encoding="utf-8")
    said = [{"path": "stage-report.md", "quote": "The tool is fast."}]
    doc = {"findings": [
        {"id": "IC-1", "summary": "Fine.", "quote": "Genomes are cheap.", "evidence": said},
        {"id": "IC-2", "summary": "Crosses a mark.", "quote": "cheap. We use HuggingFace", "evidence": said},
        {"id": "RC-3", "summary": "Wrong prefix.", "quote": "It is fast.", "evidence": said},
        {"id": "IC-4", "summary": "Not there.", "quote": "a sentence nobody wrote", "evidence":
            [{"path": "stage-report.md", "quote": "not in the report"}]}],
        "changes": [
            {"id": "IC-C1", "kind": "Proposed edit", "section": "S12", "summary": "Supplement.", "status": "proposed",
             "before": "**S12. Restoration.**", "after": "**S12. Restored genotypes.**", "evidence": said},
            {"id": "IC-C2", "kind": "Proposed edit", "section": "S12", "summary": "Named.", "status": "proposed",
             "before": "**S12. Restoration.**", "after": "**S12. Restored.**", "evidence": said,
             "document": "paper-supplementary.md"},
            {"id": "IC-C3", "kind": "Proposed edit", "section": "2", "summary": "Twice.", "status": "proposed",
             "before": SHARED, "after": "x y z", "evidence": said, "document": "paper.md"}]}
    found = stage_check.problems(doc, "manuscript-integrity-check", folder, inputs(tmp_path))
    assert found == [
        "finding RC-3: ids of manuscript-integrity-check start with IC (IC-1, IC-C1)",
        "finding IC-4: its evidence quote is not word for word in stage-report.md: 'not in the report'",
        "finding IC-2: a revision mark sits inside its quote; shorten it to a stretch without one: "
        "'cheap. We use HuggingFace'",
        "finding IC-4: its quote is not word for word in the manuscript: 'a sentence nobody wrote'",
        "change IC-C1: its before-text is in paper-supplementary.md, not the manuscript; add "
        "\"document\": \"paper-supplementary.md\""]


def test_the_stage_check_reads_the_shape_first() -> None:
    assert stage_check.fatal({"changes": []}) == ["no `findings` list (an empty list is valid)"]
    assert stage_check.fatal({"findings": [{"id": "IC-1"}], "changes": [
        {"id": "IC-C1", "kind": "Edit", "section": "A", "summary": "S", "status": "done", "before": "a", "after": "b",
         "anchor": "c", "evidence": [{"path": "r.md"}]}]}) == [
        "finding IC-1: no summary",
        "finding IC-1: neither evidence nor a quote, so nothing shows where it comes from",
        "change IC-C1: status is 'done'; it must be \"proposed\" (or \"applied\")",
        "change IC-C1: evidence item 1 must be {\"path\": ..., \"quote\": ...}, both non-empty",
        "change IC-C1: an anchor belongs only to an addition (before: null)"]


# --- runs.py ------------------------------------------------------------------------------------------------------

@pytest.fixture()
def manuscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path / "global"))
    folder = tmp_path / "paper"
    folder.mkdir()
    path = folder / "paper.md"
    path.write_text("# A test paper\n\n## Abstract\n\nLocal analysis of a genome.\n", encoding="utf-8")
    (folder / "paper-supplementary.md").write_text("# Supplement\n\nMore detail on the genome.\n", encoding="utf-8")
    result = runner.invoke(projects.app, ["configure", str(folder), "--manuscript", path.name, "--manuscript",
                                          "paper-supplementary.md", "--no-code", "--output-dir", "reviews"])
    assert result.exit_code == 0, result.output
    return path


def start(path: Path) -> Path:
    result = runner.invoke(runs.app, ["start", str(path), "--skill", "manuscript-integrity-check"])
    assert result.exit_code == 0, result.output
    return Path(result.output.strip())


def test_finish_refuses_findings_the_dashboard_could_not_use_and_names_each(manuscript: Path, tmp_path: Path) -> None:
    run = start(manuscript)
    report = tmp_path / "stage-report.md"
    report.write_text("The genome is analysed locally.", encoding="utf-8")
    assert runner.invoke(runs.app, ["add", str(run), "--skill", "manuscript-integrity-check", "--file", str(report),
                                    "--role", "report", "--name", "stage-report.md"]).exit_code == 0
    folder = run / "manuscript-integrity-check"
    bad = {"findings": [{"id": "IC-1", "summary": "Local.", "quote": "Local analysis of a genome."}],
           "changes": [{"id": "IC-C1", "section": "Abstract", "summary": "Say offline.", "status": "proposed",
                        "before": "Local analysis", "after": "Offline analysis", "evidence": "It says local."}]}
    (folder / "findings.json").write_text(json.dumps(bad), encoding="utf-8")
    refused = runner.invoke(runs.app, ["finish", str(run), "--skill", "manuscript-integrity-check", "--status", "completed"])
    assert refused.exit_code == 1
    assert "manuscript-integrity-check/findings.json: change IC-C1: no kind" in refused.output
    assert "change IC-C1: evidence is a sentence" in refused.output
    good = {**bad, "changes": [{**bad["changes"][0], "kind": "Proposed edit",
                                "evidence": [{"path": "stage-report.md", "quote": "analysed locally"}]}]}
    (folder / "findings.2.json").write_text(json.dumps(good), encoding="utf-8")
    done = runner.invoke(runs.app, ["finish", str(run), "--skill", "manuscript-integrity-check", "--status", "completed"])
    assert done.exit_code == 0, done.output


def test_a_change_names_its_file_and_the_run_records_its_plugin(manuscript: Path, tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    run = start(manuscript)
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    assert data["plugin"]["version"] == json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    before, after = tmp_path / "before.txt", tmp_path / "after.txt"
    before.write_text("More detail on the genome.", encoding="utf-8")
    after.write_text("More detail on one genome.", encoding="utf-8")
    common = ["change", str(run), "--skill", "manuscript-prose-edit", "--section", "Supplement", "--reason", "Why.",
              "--before", str(before), "--after", str(after)]
    assert runner.invoke(runs.app, [*common, "--document", "nowhere.md"]).exit_code == 2
    assert runner.invoke(runs.app, [*common, "--document", "paper-supplementary.md"]).exit_code == 0
    assert runner.invoke(runs.app, [*common, "--document", "paper.md"]).exit_code == 0
    changes = json.loads((run / "run.json").read_text(encoding="utf-8"))["skills"]["manuscript-prose-edit"]["changes"]
    assert changes[0]["document"] == "paper-supplementary.md" and "document" not in changes[1]
    # The plugin moving under the run is said once on the stage that finished on it.
    monkeypatch.setattr(runs, "plugin_state", lambda: {**data["plugin"], "version": "99.0.0"})
    moved = runs.plugin_moved(json.loads((run / "run.json").read_text(encoding="utf-8")))
    assert moved and "99.0.0" in moved and str(data["plugin"]["version"]) in moved


def test_a_busy_run_is_waited_for_not_refused_at_once() -> None:
    assert runs.LOCK_WAIT >= 30


# --- the scanner ----------------------------------------------------------------------------------------------------

def test_a_reference_list_ends_at_a_bold_section_line_and_skips_revision_marks() -> None:
    lines = ["### References for Table S7", "",
             "<!-- @rev C36b rounds=1 by=claude:2026-10-13 -->",
             "Cariaso, M., & Lennon, G. (2012). SNPedia: a wiki for personal genome annotation. NAR, 40, D1308.",
             "**Kim, R.** (2023). OakVar, version 2.13.1 [software]. https://github.com/rkimoakbioinformatics/oakvar",
             "<!-- @/rev C36b -->", "",
             "**S8. Software repositories.**", "",
             "| Repository | Description | Generation |", "|---|---|---|",
             "**S9. Sex chromosomes in just-prs.** How just-prs scores X, Y and the mitochondrial genome in its runs."]
    [(begin, end, label, entries)] = scan._reference_lists(lines, scan._reference_start(lines))
    assert [text[:12] for _, text in entries] == ["Cariaso, M.,", "**Kim, R.** "]
