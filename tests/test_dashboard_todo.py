"""The dashboard's To-do tab: what a run leaves for the authors, marked approved or redundant, saved beside the
manuscript as STEM.todo.json and read by the next run (collect.py carries the marks, todo.py turns the marked edits
into the list runs.py apply takes, and an item an earlier run's authors marked redundant is not raised again)."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/manuscript-dashboard/scripts"
PAGE = ROOT / "skills/manuscript-dashboard/assets/dashboard.html"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viz = load("dashboard", SCRIPTS / "dashboard.py")
sys.path.insert(0, str(SCRIPTS))
collect = load("collect", SCRIPTS / "collect.py")
export_changes = load("export_changes", SCRIPTS / "export_changes.py")
todo = load("todo", SCRIPTS / "todo.py")
marks = load("rev_marks", ROOT / "skills/manuscript-revision-marks/scripts/rev_marks.py")
runner = CliRunner()
RUN = "R2"
EVIDENCE = "The join key contradicts the code. The runtime differs. The figure is small. Too long."


def inventory(tmp_path: Path, **extra) -> dict:
    (tmp_path / "review.md").write_text(EVIDENCE, encoding="utf-8")
    sources = [{"path": "review.md", "quote": EVIDENCE}]

    def finding(fid: str, severity: str, **more) -> dict:
        return {"id": fid, "category": "Text versus code", "section": "2. Methods", "summary": f"Problem {fid}",
                "severity": severity, "assessment": "confirmed", "resolution": "open", "quote": f"Passage {fid}.",
                "skills": ["manuscript-integrity-check"], "evidence": sources, **more}

    def change(cid: str, status: str, fids: list[str], **more) -> dict:
        return {"id": cid, "kind": "Wording", "section": "2. Methods", "summary": f"Edit {cid}", "status": status,
                "finding_ids": fids, "before": f"Before {cid}.", "after": f"After {cid}.", "evidence": sources, **more}

    return {"schema_version": 2, "title": "Review", "run_id": RUN, "scope": "Test records.", "illustrative": True,
            "coverage": [{"skill": "manuscript-integrity-check", "status": "completed", "note": "All.", "evidence": sources}],
            "findings": [finding("F1", "major"),  # answered by the decision D1
                         finding("F2", "major"),  # answered by the proposal P1
                         finding("F3", "blocker"),  # answered by nothing: a to-do of its own
                         finding("F4", "minor"),  # minor: in the workbook's open problems, not a to-do
                         finding("F5", "major", decision=True),  # a stage's own decision
                         finding("F6", "major", resolution="addressed"),  # addressed by A1
                         finding("F7", "major", assessment="candidate", quote=None, summary="No data statement"),
                         finding("F8", "major", assessment="dismissed", resolution="unknown")],
            "changes": [change("A1", "applied", ["F6"]),  # applied and asking nothing: not a to-do
                        change("A2", "applied", [], comment="Is the new number right?"),
                        change("P1", "proposed", ["F2"], why="The text names the wrong key."),
                        change("P2", "proposed", [], comment="Which wording do you prefer?")],
            "decisions": [{"id": "D1", "summary": "Narrow the claim or rerun the benchmark", "finding_ids": ["F1"]}],
            **extra}


def test_the_to_do_list_is_what_the_word_review_and_the_workbook_put_before_the_authors(tmp_path: Path) -> None:
    data = viz.Inventory.model_validate(inventory(tmp_path))
    items = viz.todo_items(data)
    assert [(i["kind"], i["id"]) for i in items] == [
        ("decision", "D1"), ("decision", "F5"), ("question", "A2"), ("proposal", "P1"), ("proposal", "P2"),
        ("problem", "F3"), ("problem", "F7")]
    assert {i["id"]: i["status"] for i in items if i["kind"] == "proposal"} == {
        "P1": "not in this version", "P2": "waiting for your answer"}
    # Every open blocker or major problem is a to-do or is answered by one, never both and never neither.
    serious = {f.id for f in data.findings if f.assessment != "dismissed" and f.resolution != "addressed"
               and f.severity in viz.NEEDS_AUTHORS}
    listed = {i["id"] for i in items if i["kind"] == "problem"}
    answered = {fid for i in items if i["kind"] != "problem" for fid in i["finding_ids"]}
    assert listed | (answered & serious) == serious and not listed & answered
    # A held proposal is not a to-do: the corrected version says why it left it out.
    held = {"applied": ["A1", "A2"], "proposed_in_this_version": ["P1"], "held": [{"id": "P2", "why": "Another file."}]}
    with_revision = viz.todo_items(data, held)
    assert ("proposal", "P2") not in {(i["kind"], i["id"]) for i in with_revision}
    assert next(i for i in with_revision if i["id"] == "P1")["status"] == "in this version"


def test_the_workbook_s_for_you_sheet_lists_the_to_do_items_but_the_problems(tmp_path: Path) -> None:
    data = viz.Inventory.model_validate(inventory(tmp_path))
    book, counts = export_changes.build(data, None)
    rows = [tuple(c.value for c in row) for row in book["For you"].iter_rows(min_row=2)]
    assert [(kind, cid) for kind, cid, *_ in rows] == [
        ("decision", "D1"), ("decision", "F5"), ("question on an applied edit", "A2"),
        ("proposal not in this version", "P1"), ("proposal waiting for your answer", "P2")]
    assert counts["for_you"] == len([i for i in viz.todo_items(data) if i["kind"] != "problem"])
    assert rows[2][6] == "Question: Is the new number right?" and rows[3][6] == "The text names the wrong key."


def mark(kind: str, item_id: str, verdict: str, run: str = "R1", **more) -> dict:
    return {"run_id": run, "kind": kind, "id": item_id, "mark": verdict, "marked_at": "2026-10-28T10:00:00Z", **more}


@pytest.mark.parametrize(("marked", "item", "same"), [
    # An edit: the same text before and after, an applied edit and a proposal alike.
    ({"kind": "proposal", "before": "Before A.", "after": "After A."}, {"kind": "question", "before": "Before A.", "after": "After  A."}, True),
    ({"kind": "proposal", "before": "Before A.", "after": "After A."}, {"kind": "proposal", "before": "Before A.", "after": "After B."}, False),
    # A problem about a passage: the same passage, with the same category or the same summary.
    ({"kind": "problem", "quote": "We join by rsID.", "category": "Text versus code", "summary": "Old words"},
     {"kind": "problem", "quote": "We join  by rsID.", "category": "text versus code", "summary": "New words"}, True),
    ({"kind": "problem", "quote": "We join by rsID.", "category": "References", "summary": "Old words"},
     {"kind": "problem", "quote": "We join by rsID.", "category": "Text versus code", "summary": "New words"}, False),
    ({"kind": "problem", "quote": "We join by rsID.", "summary": "Join key contradicts the code"},
     {"kind": "problem", "quote": "Another passage.", "category": "", "summary": "Join key contradicts the code"}, False),
    # An absence: the same summary, whatever the case, spacing and final full stop.
    ({"kind": "problem", "quote": None, "summary": "No data availability statement."},
     {"kind": "problem", "quote": None, "category": "", "summary": "no data  availability statement"}, True),
    ({"kind": "decision", "summary": "Narrow the claim"}, {"kind": "decision", "summary": "Narrow the claim."}, True),
    ({"kind": "decision", "summary": "Narrow the claim"}, {"kind": "problem", "quote": None, "summary": "Narrow the claim"}, False),
    ({"kind": "decision", "summary": ""}, {"kind": "decision", "summary": ""}, False),
])
def test_an_item_restates_a_mark_only_word_for_word(marked: dict, item: dict, same: bool) -> None:
    blank = {"before": None, "after": None, "quote": None, "category": "", "summary": ""}
    given = viz.Mark.model_validate({**mark(marked["kind"], "X1", "redundant"), **marked})
    assert viz.restates(given, blank | item) is same


def test_marks_carry_into_the_tab_and_a_redundant_item_is_not_raised_again(tmp_path: Path) -> None:
    raw = inventory(tmp_path)
    raw["todo"] = {"schema_version": 1, "file": "paper.todo.json", "manuscript": "paper.md", "marks": [
        mark("problem", "IC-9", "redundant", quote="Passage F3.", category="Text versus code", reason="Fixed by hand."),
        mark("proposal", "PE-C4", "approved", before="Before P1.", after="After P1."),
        mark("decision", "D7", "redundant", summary="Narrow the claim or rerun the benchmark"),
        mark("decision", "D1", "approved", run=RUN, summary="Narrow the claim or rerun the benchmark"),
        mark("question", "A2", "redundant", run=RUN, reason="Not needed", before="Before A2.", after="After A2.")]}
    data = viz.Inventory.model_validate(raw)
    view = viz.todo_view(data)
    listed = {i["id"]: i for i in view["items"]}
    # F3 restates IC-9, marked redundant in R1: set aside with the reason, never listed again.
    assert [(i["id"], i["earlier"]["reason"]) for i in view["set_aside"]] == [("F3", "Fixed by hand.")]
    # P1 restates an approved proposal: still listed, saying so.
    assert listed["P1"]["earlier"]["id"] == "PE-C4" and listed["P1"]["mark"] is None
    # D1 was marked in this run, which wins over the earlier redundant D7 it restates: it stays, marked.
    assert listed["D1"]["mark"]["mark"] == "approved" and listed["D1"]["earlier"]["id"] == "D7"
    assert listed["A2"]["mark"]["reason"] == "Not needed"
    counts = viz.todo_counts(view)
    assert counts == {"items": 6, "open": 4, "approved": 1, "redundant": 1, "set_aside": 1,
                      "by_kind": {"decision": 2, "question": 1, "proposal": 2, "problem": 1}}
    assert counts["items"] + counts["set_aside"] == len(viz.todo_items(data))


@pytest.mark.parametrize("bad", ["duplicate", "unknown-mark", "unknown-field", "schema"])
def test_a_marks_file_is_refused_when_it_is_not_one_the_tab_writes(bad: str) -> None:
    raw = {"schema_version": 1, "manuscript": "paper.md", "marks": [mark("decision", "D1", "approved")]}
    if bad == "duplicate":
        raw["marks"].append(mark("decision", "D1", "redundant"))
    elif bad == "unknown-mark":
        raw["marks"][0]["mark"] = "maybe"
    elif bad == "unknown-field":
        raw["marks"][0]["colour"] = "green"
    else:
        raw["schema_version"] = 2
    with pytest.raises(ValidationError):
        viz.MarksFile.model_validate(raw)


def test_the_page_writes_every_field_of_a_mark_and_only_those() -> None:
    page = PAGE.read_text(encoding="utf-8")
    written = re.search(r"const markOf = \(t, mark, reason\) => \(\{(.*?)\}\);", page, re.S).group(1)
    keys = {part.split(":")[0].strip() for part in written.split(",")}  # `mark` is written as a shorthand
    assert keys == set(viz.Mark.model_fields)
    assert "schema_version: 1" in page and "showSaveFilePicker" in page and "manuscript-todo:" in page


def test_the_dashboard_embeds_the_to_do_list_and_counts_it(tmp_path: Path) -> None:
    raw = inventory(tmp_path)
    raw["todo"] = {"schema_version": 1, "file": "paper.todo.json", "manuscript": "paper.md",
                   "marks": [mark("problem", "IC-9", "redundant", quote="Passage F3.", category="Text versus code")]}
    data = viz.Inventory.model_validate(raw)
    summary = viz.summarize(data)
    page = viz.dashboard_html(data, summary, tmp_path)
    start = page.index('<script type="application/json" id="inventory">') + len('<script type="application/json" id="inventory">')
    document = json.loads(page[start:page.index("</script>", start)])
    assert [i["id"] for i in document["todo"]["items"]] == ["D1", "F5", "A2", "P1", "P2", "F7"]
    assert [i["id"] for i in document["todo"]["set_aside"]] == ["F3"]
    assert document["inventory"]["todo"]["file"] == "paper.todo.json" and str(tmp_path) not in page
    assert summary["todo"]["open"] == 6 and summary["todo"]["set_aside"] == 1
    assert "['todo', 'To-do'" in page and "openTodo(item)" in page


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_page_script_parses(tmp_path: Path) -> None:
    page = PAGE.read_text(encoding="utf-8")
    script = page[page.index("<script>\n(() =>") + len("<script>"):page.rindex("</script>")]
    (tmp_path / "page.js").write_text(script, encoding="utf-8")
    checked = subprocess.run(["node", "--check", str(tmp_path / "page.js")], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr


def synthetic_run(tmp_path: Path) -> Path:
    paper = tmp_path / "paper.md"
    paper.write_text("# Tool paper\n\n## 2. Methods\n\nWe join by position.\n", encoding="utf-8")
    run = tmp_path / "run"
    (run / "inputs").mkdir(parents=True)
    (run / "inputs/01-paper.md").write_text("# Tool paper\n\n## 2. Methods\n\nWe join by rsID.\n", encoding="utf-8")
    stage = run / "manuscript-integrity-check"
    stage.mkdir()
    (stage / "README.md").write_text("# manuscript-integrity-check\n\nStatus: **completed**. Covered.\n", encoding="utf-8")
    (stage / "report.md").write_text("The join key contradicts the code.", encoding="utf-8")
    (stage / "findings.json").write_text(json.dumps({"findings": [
        {"id": "IC-1", "category": "Text versus code", "section": "2. Methods", "quote": "We join by rsID.",
         "summary": "Join key contradicts the code", "severity": "major", "stage": "now", "confidence": "confirmed",
         "evidence": [{"path": "report.md", "quote": "The join key contradicts the code."}]}]}), encoding="utf-8")
    skills = {"manuscript-integrity-check": {"status": "completed", "reason": "Covered.", "artifacts": [], "issues": [],
                                             "changes": [], "commands": []}}
    (run / "run.json").write_text(json.dumps({"run_id": RUN, "started_at": "2026-10-28T00:00:00+00:00", "skills": skills,
        "inputs": [{"original": str(paper), "snapshot": "inputs/01-paper.md", "sha256": "0" * 64}]}), encoding="utf-8")
    return run


def test_collect_reads_the_marks_beside_the_manuscript_and_names_what_this_run_restates(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path)
    draft = run / "manuscript-dashboard/findings.draft.json"
    # No marks saved yet: the inventory names the file the tab will save, with none in it.
    result = runner.invoke(collect.app, [str(run), "--output", str(draft)])
    assert result.exit_code == 0, result.output
    found = viz.Inventory.model_validate_json(draft.read_text(encoding="utf-8")).todo
    assert (found.file, found.manuscript, found.marks) == ("paper.todo.json", "paper.md", [])
    # The authors marked the same problem redundant in the previous run.
    saved = {"schema_version": 1, "manuscript": "paper.md", "marks": [
        mark("problem", "IC-4", "redundant", quote="We join by rsID.", category="Text versus code", reason="Code changes."),
        mark("decision", "D2", "approved", summary="Something else")]}
    (tmp_path / "paper.todo.json").write_text(json.dumps(saved), encoding="utf-8")
    result = runner.invoke(collect.app, [str(run), "--output", str(run / "manuscript-dashboard/findings.json")])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout[result.stdout.index("{"):])
    assert report["todo"]["marks"] == 2
    assert report["todo"]["restated"] == [{"mark": "R1:problem:IC-4", "is": "redundant", "reason": "Code changes.",
                                           "summary": "", "this_run": ["problem IC-1"]}]
    carried = viz.Inventory.model_validate_json((run / "manuscript-dashboard/findings.json").read_text(encoding="utf-8")).todo
    assert [m.id for m in carried.marks] == ["IC-4", "D2"]
    assert [i["id"] for i in viz.todo_view(viz.Inventory.model_validate_json(
        (run / "manuscript-dashboard/findings.json").read_text(encoding="utf-8")))["set_aside"]] == ["IC-1"]


def test_collect_refuses_a_marks_file_it_cannot_read_and_takes_another_by_name(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path)
    (tmp_path / "paper.todo.json").write_text('{"schema_version": 1, "marks": [{"id": "D1"}]}', encoding="utf-8")
    out = run / "manuscript-dashboard/findings.json"
    result = runner.invoke(collect.app, [str(run), "--output", str(out)])
    assert result.exit_code == 1 and "paper.todo.json" in result.output and not out.exists()
    other = tmp_path / "elsewhere.json"
    other.write_text(json.dumps({"schema_version": 1, "marks": [mark("decision", "D1", "approved")]}), encoding="utf-8")
    result = runner.invoke(collect.app, [str(run), "--output", str(out), "--todo", str(other)])
    assert result.exit_code == 0, result.output
    carried = viz.Inventory.model_validate_json(out.read_text(encoding="utf-8")).todo
    assert carried.file == "elsewhere.json" and carried.manuscript == "paper.md" and len(carried.marks) == 1


TEXT = """# Paper

## Methods

We join by rsID. It runs in 39 seconds.

The tool is fast. It reads a VCF.

Old sentence stays. Old sentence stays.
"""


def test_todo_edits_makes_what_was_approved_and_undoes_what_was_marked_redundant(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(TEXT, encoding="utf-8")
    saved = {"schema_version": 1, "manuscript": "paper.md", "marks": [
        mark("proposal", "P1", "approved", before="We join by rsID.", after="We join by position.", section="Methods"),
        mark("proposal", "P2", "approved", before="It runs in 38 seconds.", after="It runs in 39 seconds."),  # done
        mark("question", "A1", "redundant", before="The tool is slow.", after="The tool is fast.", reason="Keep slow."),
        mark("proposal", "P3", "redundant", before="It reads a VCF.", after="It reads a gVCF."),  # never made
        mark("proposal", "P4", "approved", before=None, after="It needs 2 GB.", anchor="It reads a VCF."),
        mark("proposal", "P5", "approved", before="Old sentence stays.", after="New sentence."),  # twice in the text
        mark("question", "A2", "approved", before="x", after="It runs in 39 seconds.", reason="Yes, 39 is right."),
        mark("decision", "D1", "approved", summary="Narrow the claim", action="Say 'fast enough'."),
        mark("problem", "F9", "redundant", summary="A problem the authors set aside")]}
    marks_file = tmp_path / "paper.todo.json"
    marks_file.write_text(json.dumps(saved), encoding="utf-8")
    out = tmp_path / "todo-edits.json"
    result = runner.invoke(todo.app, ["edits", str(marks_file), "--text", str(paper), "--output", str(out)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    outcome = {o["mark"].split(":")[-1]: o["outcome"].split(":")[0] for o in report["changes"]}
    assert outcome == {"P1": "approved", "P2": "done", "A1": "redundant", "P3": "not made", "P4": "approved",
                       "P5": "not placed", "A2": "kept"}
    assert [(s["kind"], s["mark"].split(":")[-1]) for s in report["for_the_stages"]] == [("question", "A2"), ("decision", "D1")]
    edits = json.loads(out.read_text(encoding="utf-8"))
    assert all(e["reason"].startswith("The authors ") and "run R1" in e["reason"] for e in edits)
    assert edits[1]["reason"].endswith(": Keep slow.")
    # The list is what runs.py apply takes: applied in order, it leaves the text as the marks asked.
    done = marks.apply_edits(TEXT, [marks.Edit(e["before"], e["after"]) for e in edits], marks.Entry("claude", date(2026, 10, 28)))
    assert done.text == TEXT.replace("We join by rsID.", "We join by position.").replace(
        "The tool is fast. It reads a VCF.", "The tool is slow. It reads a VCF. It needs 2 GB.")
    # Run again on that text, nothing is left to do: what was approved is done, what was redundant is undone.
    paper.write_text(done.text, encoding="utf-8")
    again = runner.invoke(todo.app, ["edits", str(marks_file), "--text", str(paper), "--output", str(tmp_path / "again.json")])
    assert json.loads((tmp_path / "again.json").read_text(encoding="utf-8")) == [], again.output
    assert runner.invoke(todo.app, ["edits", str(marks_file), "--text", str(paper), "--output", str(out)]).exit_code != 0


def test_todo_edits_takes_one_run_s_marks_and_undoes_an_addition_with_its_space(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(TEXT.replace("It reads a VCF.", "It reads a VCF. It needs 2 GB."), encoding="utf-8")
    saved = {"schema_version": 1, "marks": [
        mark("question", "A3", "redundant", run="R1", before=None, after="It needs 2 GB.", anchor="It reads a VCF."),
        mark("proposal", "P1", "approved", run="R0", before="We join by rsID.", after="We join by position.")]}
    marks_file = tmp_path / "paper.todo.json"
    marks_file.write_text(json.dumps(saved), encoding="utf-8")
    out = tmp_path / "edits.json"
    result = runner.invoke(todo.app, ["edits", str(marks_file), "--text", str(paper), "--output", str(out), "--run", "R1"])
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text(encoding="utf-8")) == [
        {"before": " It needs 2 GB.", "after": "", "reason": "The authors marked it redundant in the To-do list of run R1.", "section": ""}]
    missing = runner.invoke(todo.app, ["edits", str(marks_file), "--text", str(paper), "--output", str(tmp_path / "x.json"), "--run", "R9"])
    assert missing.exit_code != 0 and "R9" in missing.output
    shown = runner.invoke(todo.app, ["show", str(marks_file)])
    assert shown.exit_code == 0 and "Run R1: 0 approved, 1 redundant" in shown.output
