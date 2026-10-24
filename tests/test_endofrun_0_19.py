"""The end of a run, 0.19: second attempts, the notes in the text, restored claims, the journal files, the
severity words, the decisions, the referee panel's counts, plain comments, the figures' renders and the
authors' one confirmation of the proposed decisions to referees."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The order matters: each script imports the modules loaded before it under these names.
viz = load("dashboard", SKILLS / "manuscript-dashboard/scripts/dashboard.py")
revise = load("revise", SKILLS / "manuscript-improve/scripts/revise.py")
collect = load("collect", SKILLS / "manuscript-dashboard/scripts/collect.py")
export = load("export_docx", SKILLS / "manuscript-dashboard/scripts/export_docx.py")
figures = load("figures", SKILLS / "manuscript-figures/scripts/figures.py")
cr = load("check_response", SKILLS / "manuscript-reviewer-response/scripts/check_response.py")

ORIGINAL = """# A tool

## 1. Introduction

Genomes are cheap. This tool is the first complete annotator for long reads. We use HuggingFace for data.

## 2. Methods

The pipeline joins by rsID. It is fast.
"""
EVIDENCE = [{"path": "review.md", "quote": "The review."}]


def change(cid: str, status: str, before: str | None, after: str | None, **extra) -> dict:
    return {"id": cid, "kind": "Proposed edit", "section": extra.pop("section", "1. Introduction"), "summary": f"Edit {cid}",
            "status": status, "before": before, "after": after, "evidence": EVIDENCE, **extra}


def inventory(changes: list[dict], findings: list[dict] | None = None, **extra) -> dict:
    return {"schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
            "coverage": [{"skill": s, "status": "completed", "note": "All.", "evidence": EVIDENCE}
                         for s in ("manuscript-improve", "manuscript-integrity-check", "manuscript-figures")],
            "findings": findings or [], "changes": changes,
            "manuscript": {"title": "A tool", "path": "original.md", "sections": ["1. Introduction", "2. Methods"]}, **extra}


def finding(fid: str, **extra) -> dict:
    return {"id": fid, "category": "Claims and evidence", "section": "1. Introduction", "summary": f"Problem {fid}",
            "severity": "major", "assessment": "confirmed", "resolution": "open", "skills": ["manuscript-integrity-check"],
            "evidence": EVIDENCE, **extra}


# ---------- numbered attempts ----------

def test_attempts_are_numbered_before_the_extension_and_after_a_folder_name(tmp_path: Path) -> None:
    assert viz.next_attempt(tmp_path / "findings.json", folder=False).name == "findings.json"
    (tmp_path / "findings.json").write_text("{}")
    (tmp_path / "findings.draft.json").write_text("{}")  # another output, not an attempt
    assert viz.next_attempt(tmp_path / "findings.json", folder=False).name == "findings.2.json"
    (tmp_path / "findings.2.json").write_text("{}")
    assert viz.newest_attempt(tmp_path / "findings.json", folder=False).name == "findings.2.json"
    assert viz.next_attempt(tmp_path / "findings.2.json", folder=False).name == "findings.3.json"
    assert viz.attempt_base(tmp_path / "findings.draft.json", folder=False) == (tmp_path / "findings.draft.json", 1)
    (tmp_path / "revision").mkdir()
    assert viz.next_attempt(tmp_path / "revision", folder=True).name == "revision.2"
    assert viz.next_attempt(tmp_path / "manuscript-review.docx", folder=False).name == "manuscript-review.docx"


def synthetic_run(tmp_path: Path, skills: dict[str, str] | None = None, inputs: bool = True) -> Path:
    paper = tmp_path / "paper.md"
    paper.write_text("# Tool paper\n\n## Abstract\n\nIt runs in 39 seconds.\n\n## 2. Methods\n\nWe join by rsID.\n")
    run = tmp_path / "run"
    (run / "inputs").mkdir(parents=True)
    (run / "inputs/01-paper.md").write_text(paper.read_text())
    seats = {}
    for name, status in (skills or {"manuscript-integrity-check": "completed"}).items():
        (run / name).mkdir()
        (run / name / "README.md").write_text(f"# {name}\n\nStatus: **{status}**. \n")
        seats[name] = {"status": status, "artifacts": [], "issues": [], "changes": [], "commands": []}
    if "manuscript-integrity-check" in seats:
        (run / "manuscript-integrity-check/report.md").write_text("The join key contradicts the code. A new note.")
        (run / "manuscript-integrity-check/findings.json").write_text(json.dumps({"findings": [
            {"id": "IC-1", "category": "Text versus code", "section": "2. Methods", "quote": "We join by rsID.",
             "summary": "Join key contradicts the code", "severity": "optional", "stage": "now", "confidence": "confirmed",
             "evidence": [{"path": "report.md", "quote": "The join key contradicts the code."}]}]}))
    (run / "run.json").write_text(json.dumps({"run_id": "R1", "started_at": "2026-10-24T00:00:00+00:00", "skills": seats,
        "inputs": [{"original": str(paper), "snapshot": "inputs/01-paper.md", "sha256": "0" * 64}] if inputs else []}))
    return run


def test_collect_names_the_next_attempt_and_reads_a_stage_s_newest_findings(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path)
    again = json.loads((run / "manuscript-integrity-check/findings.json").read_text())
    again["findings"][0]["summary"] = "Join key differs from the code, second attempt"
    (run / "manuscript-integrity-check/findings.2.json").write_text(json.dumps(again))
    out = run / "manuscript-dashboard/findings.json"
    assert CliRunner().invoke(collect.app, [str(run), "--output", str(out)]).exit_code == 0
    inventory = viz.Inventory.model_validate_json(out.read_text())
    assert [f.summary for f in inventory.findings] == ["Join key differs from the code, second attempt"]
    refused = CliRunner().invoke(collect.app, [str(run), "--output", str(out)])
    assert refused.exit_code == 1 and "write the next attempt as findings.2.json" in refused.output


def test_collect_without_merge_warns_when_an_adjudication_lies_beside_it(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path)
    (run / "manuscript-dashboard").mkdir()
    (run / "manuscript-dashboard/merges.json").write_text(json.dumps({"dismiss": [{"id": "IC-1", "why": "Fine."}]}))
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(run / "manuscript-dashboard/findings.json")])
    assert result.exit_code == 0 and "merges.json is beside this inventory but --merge was not given" in result.output
    merged = CliRunner().invoke(collect.app, [str(run), "--output", str(run / "manuscript-dashboard/findings.2.json"),
                                              "--merge", str(run / "manuscript-dashboard/merges.json")])
    assert merged.exit_code == 0 and "Warning" not in merged.output


def test_dashboard_revise_and_export_name_the_next_attempt(tmp_path: Path) -> None:
    (tmp_path / "review.md").write_text("The review.")
    (tmp_path / "original.md").write_text(ORIGINAL)
    (tmp_path / "findings.json").write_text(json.dumps(inventory([])))
    viz.render(tmp_path / "findings.json", tmp_path / "dashboard")
    with pytest.raises(ValueError, match=r"render this attempt into dashboard\.2"):
        viz.render(tmp_path / "findings.json", tmp_path / "dashboard")
    args = [str(tmp_path / "original.md"), str(tmp_path / "original.md"), str(tmp_path / "findings.json"),
            "--output-dir", str(tmp_path / "revision")]
    assert CliRunner().invoke(revise.app, args).exit_code == 0
    again = CliRunner().invoke(revise.app, args)
    assert again.exit_code != 0 and "revision.2" in again.output
    out = tmp_path / "manuscript-review.docx"
    assert CliRunner().invoke(export.app, [str(tmp_path / "findings.json"), "--output", str(out)]).exit_code == 0
    refused = CliRunner().invoke(export.app, [str(tmp_path / "findings.json"), "--output", str(out)])
    assert refused.exit_code != 0 and "manuscript-review.2.docx" in refused.output


# ---------- the corrected version: notes, choices, restored claims, file names ----------

def test_notes_from_applied_edits_and_the_authors_own_notes_are_kept_apart(tmp_path: Path) -> None:
    original = ORIGINAL.replace("It is fast.", "It is fast. [AUTHORS: add the timing table]")
    working = original.replace("We use HuggingFace for data.", "We use Hugging Face [AUTHORS: which version?] for data.")
    data = inventory([change("PE.C1", "applied", "We use HuggingFace for data.", "We use Hugging Face [AUTHORS: which version?] for data.")])
    document, record = revise.build(original, working, viz.Inventory.model_validate(data), {})
    assert [n["note"] for n in record["notes_in_text"]] == ["[AUTHORS: add the timing table]"]  # the authors' own
    assert [n["note"] for n in record["notes_in_working_copy"]] == ["[AUTHORS: which version?]"]  # from the applied edit
    (tmp_path / "review.md").write_text("The review.\n" + original + working)  # an applied edit's evidence holds its text
    (tmp_path / "original.md").write_text(original)
    (tmp_path / "working.md").write_text(working)
    (tmp_path / "findings.json").write_text(json.dumps(data))
    result = CliRunner().invoke(revise.app, [str(tmp_path / "original.md"), str(tmp_path / "working.md"),
                                             str(tmp_path / "findings.json"), "--output-dir", str(tmp_path / "revision")])
    assert result.exit_code == 0, result.output
    printed = json.loads(result.output)
    assert printed["notes_in_text"] == 1 and printed["notes_in_working_copy"] == 1
    summary = viz.render(tmp_path / "findings.json", tmp_path / "dashboard", revision=tmp_path / "revision")
    assert summary["revision"]["notes_in_text"] == 1 and summary["revision"]["notes_in_working_copy"] == 1
    page = (tmp_path / "dashboard/manuscript-dashboard.html").read_text()
    assert "from your own draft" in page and "that the run's applied edits left" in page
    assert "from edits already applied to the working manuscript" not in page


@pytest.mark.parametrize("choices, message", [
    ({"hold": [{"id": "ST-C1", "reason": "Wait."}]}, "hold entry 1 needs exactly id"),
    ({"anchor": [{"id": "JA-C1", "text": "It is fast."}]}, "anchor entry 1 needs exactly id"),
    ({"held": [{"id": "ST-C1", "why": "Wait."}]}, "keys revise.py does not read: held"),
    ({"prefer": "ST-C1"}, "prefer is a list of proposal IDs"),
    (["ST-C1"], "must be a JSON object"),
])
def test_a_choices_file_of_the_wrong_shape_says_what_it_should_hold(choices: object, message: str) -> None:
    data = viz.Inventory.model_validate(inventory([change("ST-C1", "proposed", "It is fast.", "It runs in 39 seconds.")]))
    with pytest.raises(ValueError, match=re.escape(message)) as raised:
        revise.build(ORIGINAL, ORIGINAL, data, choices)
    assert "widened claim, wording restored" in str(raised.value)  # the example the message gives


def test_the_command_reports_a_bad_choices_file_without_a_traceback(tmp_path: Path) -> None:
    (tmp_path / "review.md").write_text("The review.")
    (tmp_path / "original.md").write_text(ORIGINAL)
    (tmp_path / "findings.json").write_text(json.dumps(inventory([change("ST-C1", "proposed", "It is fast.", "Fast.")])))
    for text in ('{"hold": [{"id": "ST-C1"}]}', '{"hold": [}'):
        (tmp_path / "choices.json").write_text(text)
        result = CliRunner().invoke(revise.app, [str(tmp_path / "original.md"), str(tmp_path / "original.md"),
                                                 str(tmp_path / "findings.json"), "--choices", str(tmp_path / "choices.json"),
                                                 "--output-dir", str(tmp_path / "revision")])
        assert result.exit_code == 2 and not isinstance(result.exception, (KeyError, json.JSONDecodeError))
        assert "choices.json" in result.output


def test_a_widened_claim_is_held_and_a_restored_applied_edit_cancels_out() -> None:
    """Finding 13: a proposal whose claim widened is held with the reason; an applied edit whose wording a reverse
    runs.py change restored leaves the corrected version as the original had it."""
    claim = "This tool is the first complete annotator for long reads."
    widened = "This tool is the first complete annotator for every sequencing technology."
    working = ORIGINAL.replace("HuggingFace", "Hugging Face")
    data = inventory([
        change("PE.C1", "applied", claim, widened),            # a stage widened the claim
        change("PE.C2", "applied", widened, claim),            # the reverse change that restored it
        change("PE.C3", "applied", "We use HuggingFace for data.", "We use Hugging Face for data."),
        change("ST-C1", "proposed", "It is fast.", "It is fast on every genome ever sequenced."),
    ])
    hold = {"hold": [{"id": "ST-C1", "why": "widened claim, wording restored"}]}
    document, record = revise.build(ORIGINAL, working, viz.Inventory.model_validate(data), hold)
    assert document.previous() == ORIGINAL and document.current() == working
    assert record["held"] == [{"id": "ST-C1", "why": "widened claim, wording restored"}]
    assert sorted(record["restored"][0]["ids"]) == ["PE.C1", "PE.C2"] and record["applied"] == ["PE.C3"]
    assert "ST-C1" not in record["proposed_in_this_version"]


def test_collect_counts_both_the_widening_and_its_reverse_as_applied(tmp_path: Path) -> None:
    claim = "This tool is the first complete annotator for long reads."
    widened = "This tool is the first complete annotator for every sequencing technology."
    for number, (before, after) in enumerate(((claim, widened), (widened, claim)), 1):
        path = tmp_path / "manuscript-prose-edit" / "changes" / f"{number:04d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# 1. Introduction\n\nReason: why {number}\n\n## Before\n\n{before}\n\n## After\n\n{after}\n")
    data = {"skills": {"manuscript-prose-edit": {"changes": [{"path": f"manuscript-prose-edit/changes/000{n}.md"} for n in (1, 2)]}}}
    records = collect.recorded_changes(tmp_path, data, tmp_path, ORIGINAL, ORIGINAL)
    assert [r["status"] for r in records] == ["applied", "applied"]


def test_a_latex_manuscript_gets_a_latex_corrected_version(tmp_path: Path) -> None:
    tex = "\\section{Introduction}\n\nWe use HuggingFace for data.\n\n\\section{Methods}\n\nIt is fast.\n"
    (tmp_path / "review.md").write_text("The review.")
    (tmp_path / "original.tex").write_text(tex)
    (tmp_path / "working.tex").write_text(tex)
    data = inventory([change("PE-C1", "proposed", "It is fast.", "It runs in 39 seconds.", section="Methods")])
    data["manuscript"]["path"] = "original.tex"
    (tmp_path / "findings.json").write_text(json.dumps(data))
    result = CliRunner().invoke(revise.app, [str(tmp_path / "original.tex"), str(tmp_path / "working.tex"),
                                             str(tmp_path / "findings.json"), "--output-dir", str(tmp_path / "revision")])
    assert result.exit_code == 0, result.output
    names = sorted(p.name for p in (tmp_path / "revision").iterdir())
    assert names == ["changes.md", "proposed.tex", "revised.tex", "revision.json"]
    assert "It runs in 39 seconds." in (tmp_path / "revision/proposed.tex").read_text()
    record = json.loads((tmp_path / "revision/revision.json").read_text())
    assert record["files"] == {"revised": "revised.tex", "proposed": "proposed.tex", "changes": "changes.md"}
    assert "{>>Methods: Edit PE-C1 (PE-C1)<<}" in (tmp_path / "revision/changes.md").read_text()
    viz.render(tmp_path / "findings.json", tmp_path / "dashboard", revision=tmp_path / "revision")
    page = (tmp_path / "dashboard/manuscript-dashboard.html").read_text()
    assert '"suffix": ".tex"' in page and "save(R.text, 'corrected' + suffix)" in page


# ---------- severity words, decisions, plain comments ----------

@pytest.mark.parametrize("word, value", [("optional", "info"), ("Optional", "info"), ("uncertain", "unknown"),
                                         ("not assessed", "unknown"), ("not_assessed", "unknown"), ("serious", "blocker"),
                                         ("important", "major"), ("minor", "minor"), (None, "unknown"), ("odd", "unknown")])
def test_every_severity_word_maps_onto_the_one_scale(word: str | None, value: str) -> None:
    assert collect.severity(word) == value


def test_the_dashboard_and_the_word_file_use_the_same_severity_and_stage_words() -> None:
    page = viz.TEMPLATE.read_text(encoding="utf-8")
    assert "info: 'Optional', unknown: 'Could not be checked'" in page
    assert export.SEVERITY["info"] == "Optional" and export.SEVERITY["unknown"] == "Could not be checked"
    for words in ("Once you have chosen the journal", "Before submission, once the code is final"):
        assert words in page and words.lower() in {v.lower() for v in export.WHEN.values()} | {words.lower()}
    assert export.WHEN["journal"] == "once you have chosen the journal"


def test_a_written_decision_never_hides_the_stages_own_decisions() -> None:
    data = inventory([], findings=[finding("IC-1", decision=True), finding("FG-1", decision=True), finding("IC-2")],
                     decisions=[{"id": "D1", "summary": "Narrow the claim or rerun", "finding_ids": ["IC-1"]}])
    checked = viz.Inventory.model_validate(data)
    assert [d["id"] for d in viz.decision_list(checked)] == ["D1", "FG-1"]
    assert viz.summarize(checked)["decisions"] == 2
    page = viz.dashboard_html(checked, viz.summarize(checked))
    start = page.index('id="inventory">') + len('id="inventory">')
    assert [d["id"] for d in json.loads(page[start:page.index("</script>", start)])["decisions"]] == ["D1", "FG-1"]


def test_word_comments_say_what_they_are_about_first_and_never_add_text(tmp_path: Path) -> None:
    (tmp_path / "review.md").write_text("The review.")
    (tmp_path / "original.md").write_text(ORIGINAL.replace("It is fast.", "It is fast.\n\n![Runtime](figures/missing.png)"))
    data = inventory([], findings=[finding("IC-1", quote="The pipeline joins by rsID.", stage="now", severity="info")])
    (tmp_path / "findings.json").write_text(json.dumps(data))
    out = tmp_path / "manuscript-review.docx"
    result = CliRunner().invoke(export.app, [str(tmp_path / "findings.json"), "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["images_not_embedded"] == 1
    with zipfile.ZipFile(out) as docx:
        document, comments = docx.read("word/document.xml").decode(), docx.read("word/comments.xml").decode()
    assert "Image not embedded" not in re.sub(r"<[^>]+>", "", document)
    assert "Image not embedded: missing.png" in comments
    assert "Problem IC-1 (Optional, fix now)." in comments and "(IC-1)" in comments
    assert not re.search(r">IC-1 ·", comments)


# ---------- the run's coverage, the coordinator, a connected document ----------

def test_a_running_stage_is_in_progress_and_the_coordinator_is_left_out(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path, {"manuscript-integrity-check": "completed", "manuscript-story": "running",
                                   "manuscript-improve": "running"})
    out = run / "manuscript-dashboard/findings.json"
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(out)])
    assert result.exit_code == 0, result.output
    inventory = viz.Inventory.model_validate_json(out.read_text())
    rows = {c.skill: c for c in inventory.coverage}
    assert set(rows) == {"manuscript-integrity-check", "manuscript-story"}
    assert rows["manuscript-story"].status == "in_progress" and "Recorded status" not in rows["manuscript-story"].note
    assert "story in progress" in inventory.scope and "running" not in inventory.scope
    # The stage finishes and its README is regenerated: the inventory's evidence still holds.
    (run / "manuscript-story/README.md").write_text("# manuscript-story\n\nStatus: **completed**. \n")
    viz.render(out, run / "manuscript-dashboard/dashboard")


def test_a_manuscript_that_is_only_a_connected_document_needs_a_reading_copy(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path, inputs=False)
    out = run / "manuscript-dashboard/findings.json"
    refused = CliRunner().invoke(collect.app, [str(run), "--output", str(out)])
    assert refused.exit_code == 1 and "--manuscript" in refused.output and not isinstance(refused.exception, IndexError)
    copy = tmp_path / "reading-copy.md"
    copy.write_text((tmp_path / "paper.md").read_text())
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(out), "--manuscript", str(copy)])
    assert result.exit_code == 0, result.output
    assert viz.Inventory.model_validate_json(out.read_text()).manuscript.sections == ["Abstract", "2. Methods"]


# ---------- journal selection's files ----------

LADDER = ("ladder,rung,key,name,ai_points,ai_drafting,ai_prompts,ai_records,ai_detection,ai_declaration,ai_counted,ai_extra\n"
          "journals,1,genes,Genes,1,good: allowed,good: none,good: none,good: none,good: Methods,good: no,good: none\n")


def test_collect_finds_the_ladders_top3_and_the_record_journal_selection_wrote(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path, {"manuscript-integrity-check": "completed", "manuscript-journal-select": "completed"})
    folder = run / "manuscript-journal-select"
    (folder / "paper.journal-ladder.csv").write_text(LADDER.replace("Genes", "Genes, first attempt"))
    (folder / "ladders").mkdir()
    (folder / "ladders/paper.journal-ladder.2.csv").write_text(LADDER)  # the newest attempt, in a subfolder
    (folder / "paper.preprint-ladder.csv").write_text("ladder,rung,key,name,ai_drafting\npreprints,1,biorxiv,bioRxiv,good: allowed\n")
    (folder / "top3.json").write_text(json.dumps([{"key": "genes", "name": "Genes", "article_type": "Article",
                                                    "why": "Fits a tool paper.", "url": "https://genes.example"}]))
    (folder / "manuscript-record.yaml").write_text("venue: genes\n")
    data = json.loads((run / "run.json").read_text())
    files = collect.selection_files(run, data)
    assert files["journals"].name == "paper.journal-ladder.2.csv" and files["record"].name == "manuscript-record.yaml"
    rows = {v["key"]: v for v in collect.venues(run, data)}
    assert rows["genes"]["chosen"] and rows["genes"]["name"] == "Genes" and rows["genes"]["why"] == "Fits a tool paper."
    assert rows["biorxiv"]["ladder"] == "preprints" and collect.ladder_gaps(run, data) == []


def test_collect_reads_registered_ladders_and_the_record_beside_the_manuscript(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path, {"manuscript-integrity-check": "completed", "manuscript-journal-select": "completed"})
    elsewhere = run / "manuscript-integrity-check/venues"
    elsewhere.mkdir()
    (elsewhere / "paper.journal-ladder.csv").write_text(LADDER)
    (tmp_path / "paper.record.yaml").write_text("venue: genes\n")
    data = json.loads((run / "run.json").read_text())
    data["skills"]["manuscript-integrity-check"]["artifacts"].append({"path": "manuscript-integrity-check/venues/paper.journal-ladder.csv"})
    files = collect.selection_files(run, data)
    assert files["journals"] == elsewhere / "paper.journal-ladder.csv" and files["record"] == tmp_path / "paper.record.yaml"
    assert [g["check"] for g in collect.ladder_gaps(run, data)] == ["The preprint ladder in the dashboard"]


def test_a_journal_stage_without_ladders_is_said_not_left_silent(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path, {"manuscript-integrity-check": "completed", "manuscript-journal-select": "completed"})
    out = run / "manuscript-dashboard/findings.json"
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(out)])
    assert result.exit_code == 0, result.output
    inventory = viz.Inventory.model_validate_json(out.read_text())
    assert inventory.venues == []
    (gap,) = [n for n in inventory.not_checked if n.skill == "manuscript-journal-select"]
    assert "did not record its journal and preprint ladders" in gap.why


# ---------- the simulated referees ----------

def peer_review_run(tmp_path: Path) -> Path:
    folder = tmp_path / "manuscript-peer-review"
    (folder / "referees/skeptic").mkdir(parents=True)
    concerns = [{"id": f"SK-{n}", "seat": "skeptic", "severity": sev, "concern": f"Concern {n}.", "route": route,
                 "defence_outcome": outcome, "verdict": "confirmed"}
                for n, (sev, route, outcome) in enumerate([("major", "fixable in text", "partly_answered"),
                                                           ("blocker", "venue", "Premise not supported"),
                                                           ("optional", "policy", "answered")], 1)]
    doc = {"reports": [{"seat": "skeptic", "summary": "Sound.", "recommendations": []}], "findings": concerns}
    for name in ("findings.merged.json", "findings.adjudicated.json"):
        (folder / name).write_text(json.dumps(doc))
    (folder / "check.json").write_text(json.dumps({"findings": [{"check": "quote"}] * 3}))
    (folder / "referees/skeptic/findings.json").write_text(json.dumps(doc))
    return tmp_path


def test_the_funnel_counts_the_referees_proposals_once(tmp_path: Path) -> None:
    run = peer_review_run(tmp_path)
    rows = [r for r in collect.signals(run) if r["skill"] == "manuscript-peer-review"]
    assert sum(r["count"] for r in rows) == 3 and {r["note"] for r in rows} == {"findings.merged.json"}


def test_the_defence_count_and_routes_read_peer_review_s_words(tmp_path: Path) -> None:
    run = peer_review_run(tmp_path)
    (reviewer,) = collect.panel(run)["reviewers"]
    assert [(c["defence"], c["route"]) for c in reviewer["concerns"]] == [
        ("partly answered", "fixable-in-text"), ("premise not supported", "venue"), ("answered", "policy")]
    page = viz.TEMPLATE.read_text(encoding="utf-8")
    assert "['venue', 'A question for the chosen journal']" in page and "['policy', 'Ethics, consent or privacy']" in page
    assert "blocker or major" in page and "optional or uncertain`" not in page
    assert "premise not supported by the text" in page


def test_another_model_s_concern_ids_link_to_the_problems(tmp_path: Path) -> None:
    mentions = collect.concern_mentions([{"id": "PR-1", "summary": "Ratio", "detail": "Grouped from SKX-3, SKx-4 and SK-1."}])
    assert {"SKX-3", "SKx-4", "SK-1"} <= set(mentions)


def test_the_reference_records_who_matched_it_and_the_dashboard_says_so() -> None:
    data = inventory([], findings=[finding("IC-1")])
    data["reference"] = {"title": "the referee's review", "description": "Comments on v1.", "matched_by": "the coordinating agent",
                         "source": {"path": "review.md", "quote": "The review."},
                         "items": [{"id": "R1", "origin": "reviewer", "summary": "Claim", "category": "Claims and evidence"}],
                         "matches": [{"reference_id": "R1", "finding_ids": ["IC-1"], "match": "full", "note": "Same."}]}
    checked = viz.Inventory.model_validate(data)
    assert checked.reference.matched_by == "the coordinating agent"
    assert "Its items were matched to the run's findings by ${R.matched_by}" in viz.TEMPLATE.read_text(encoding="utf-8")


# ---------- figures ----------

def test_ghostscript_is_found_under_its_windows_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(figures.shutil, "which", lambda name: "C:/gs/bin/gswin64c.exe" if name == "gswin64c" else None)
    assert figures.ghostscript() == "C:/gs/bin/gswin64c.exe"
    monkeypatch.setattr(figures.shutil, "which", lambda name: None)
    pages, why = figures.pages_of(Path("figure.eps"), Path("."))
    assert pages == [] and "gswin64c on Windows" in why


def test_a_second_inventory_is_sent_to_the_next_folder(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text("# Paper\n\nNo figures.\n")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures/figures.json").write_text("{}")
    result = CliRunner().invoke(figures.app, ["inventory", str(paper), "--output-dir", str(tmp_path / "figures")])
    assert result.exit_code == 1 and "figures.2" in result.output


def test_the_figures_skill_registers_renders_by_their_paths_and_fits_the_description_limit() -> None:
    text = (SKILLS / "manuscript-figures/SKILL.md").read_text(encoding="utf-8")
    description = yaml.safe_load(text.split("---")[1])["description"]
    assert len(description) < 1000 and "check our figures" in description and "supplement" in description
    assert "--name figures/figure-3/view.png" in text and "gswin64c" in text
    assert "follow the `edits` setting" in text and "decision: true" in text
    dashboard = (SKILLS / "manuscript-dashboard/SKILL.md").read_text(encoding="utf-8")
    assert "--name dashboard/summary.json" in dashboard and "findings.2.json" in dashboard
    assert "--merge RUN/manuscript-dashboard/merges.json --reference RUN/manuscript-dashboard/reference.json" in dashboard


# ---------- reviewer response: one confirmation of the proposed decisions ----------

REVIEWS = """Reviewer 1

1. Please report the spread across runs.
2. Please add a public-data replication of the benchmark.

Reviewer 2

1. Please repeat the benchmark on a second laptop.
2. Please define the speed-up ratio.
"""


def ledger(confirmation: dict | None, named: list[str] | None = None) -> str:
    items = [("R1.1", "Reviewer 1", "Please report the spread across runs.", ["table"], "address"),
             ("R1.2", "Reviewer 1", "Please add a public-data replication of the benchmark.", ["new-analysis"], "address"),
             ("R2.1", "Reviewer 2", "Please repeat the benchmark on a second laptop.", ["new-data"], "decline"),
             ("R2.2", "Reviewer 2", "Please define the speed-up ratio.", ["methods-text"], "address")]
    round_ = {"round": 1, "items": [{"id": i, "referee": r, "comment": c, "evidence": e, "proposed": p, "confirmed": "blanket",
                                     **({"reason": "No second laptop of this class is available to us."} if p == "decline" else {})}
                                    for i, r, c, e, p in items]}
    if confirmation is not None:
        round_["confirmation"] = {**confirmation, "named": named or []}
    return yaml.safe_dump({"mode": "journal", "rounds": [round_]}, sort_keys=False)


def missing(tmp_path: Path, text: str, letter: bool = True) -> set[str]:
    (tmp_path / "reviews.txt").write_text(REVIEWS)
    (tmp_path / "ledger.yaml").write_text(text)
    if letter:
        (tmp_path / "letter.md").write_text("# Response\n")
    report = cr.run(tmp_path / "reviews.txt", tmp_path / "ledger.yaml", tmp_path / "letter.md" if letter else None)
    return {f.item for f in report.findings if f.code == "DECISION_MISSING"}


ASKED = {"asked": "All as proposed?", "answer": "Yes, all as proposed."}


def test_one_confirmation_covers_the_text_changes_only(tmp_path: Path) -> None:
    assert missing(tmp_path, ledger(ASKED)) == {"R1.2", "R2.1"}  # new work and a decline the question did not name


def test_a_decline_and_new_work_named_in_the_question_are_confirmed(tmp_path: Path) -> None:
    named = {"asked": "All as proposed, including declining R2.1 and adding the replication in R1.2?", "answer": "Yes."}
    assert missing(tmp_path, ledger(named, ["R2.1", "R1.2"])) == set()


def test_without_a_recorded_answer_nothing_is_confirmed(tmp_path: Path) -> None:
    assert missing(tmp_path, ledger(None)) == {"R1.1", "R1.2", "R2.1", "R2.2"}
    assert missing(tmp_path, ledger({"asked": "All as proposed?", "answer": ""})) == {"R1.1", "R1.2", "R2.1", "R2.2"}


def test_the_plan_report_says_what_the_confirmation_covers(tmp_path: Path) -> None:
    (tmp_path / "reviews.txt").write_text(REVIEWS)
    (tmp_path / "ledger.yaml").write_text(ledger(ASKED))
    report = cr.run(tmp_path / "reviews.txt", tmp_path / "ledger.yaml")
    assert [u["id"] for u in report.undecided] == ["R1.2", "R2.1"] and report.blocking == 0
    md = cr.to_markdown(report)
    assert "Two decisions come from your one confirmation of the proposed decisions." in md
    assert "Your confirmation of the proposed decisions does not cover it: the proposal involves declining it" in md
    assert "The plan proposes: decline." in md


@pytest.mark.parametrize("field, value, message", [("confirmed", "all", "use blanket"), ("proposed", "maybe", "proposes 'maybe'")])
def test_unknown_confirmation_values_are_input_errors(tmp_path: Path, field: str, value: str, message: str) -> None:
    data = yaml.safe_load(ledger(ASKED))
    data["rounds"][0]["items"][0][field] = value
    (tmp_path / "ledger.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(cr.InputError, match=re.escape(message)):
        cr.load_ledger(tmp_path / "ledger.yaml")


def test_the_reviewer_response_docs_route_statements_and_name_the_requested_claims() -> None:
    skill = (SKILLS / "manuscript-reviewer-response/SKILL.md").read_text(encoding="utf-8")
    verification = (SKILLS / "manuscript-reviewer-response/references/verification.md").read_text(encoding="utf-8")
    assert "$SCRATCH" not in skill + verification
    assert skill.count("--authorised RUN/manuscript-reviewer-response/requested-claims.yaml") == 1
    assert "--authorised RUN/manuscript-reviewer-response/requested-claims.yaml" in verification
    assert '- passage: "' in skill and "finding: R2.3" in skill
    assert "`manuscript-journal-adapt`, which drafts it for the venue" in skill
    assert "run steps 1 and 2 in a fresh subagent" in skill and "run steps 1 and 2 in a fresh" in verification
    assert "`RR-1`" in skill and "findings.json" in skill


# ---------- cross-platform ----------

@pytest.mark.parametrize("path", ["manuscript-dashboard/scripts/collect.py", "manuscript-dashboard/scripts/dashboard.py",
                                  "manuscript-dashboard/scripts/export_docx.py", "manuscript-improve/scripts/revise.py",
                                  "manuscript-figures/scripts/figures.py", "manuscript-reviewer-response/scripts/check_response.py"])
def test_each_script_prints_utf8_and_reads_and_writes_text_as_utf8(path: str) -> None:
    import ast

    source = (SKILLS / path).read_text(encoding="utf-8")
    entry = source[source.index('if __name__ == "__main__":'):]
    assert "utf8_console()" in entry or 'reconfigure(encoding="utf-8"' in entry
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"read_text", "write_text"}:
            assert any(k.arg == "encoding" for k in node.keywords), (path, node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "open" and not (
                isinstance(node.func.value, ast.Name) and node.func.value.id in {"zipfile", "pymupdf", "Image"}):
            mode = next((a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)), "r")
            if "b" not in mode:
                assert any(k.arg == "encoding" for k in node.keywords), (path, node.lineno)
