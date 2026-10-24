"""journal-adapt's AI-use draft from this run's recorded changes (ai_use.py): idea 9 of the 2026-10-24 comparison with
academic-research-skills."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ai_use = _load("ai_use", ROOT / "skills/manuscript-journal-adapt/scripts/ai_use.py")
WHO = ["--tool", "Claude Code", "--model", "claude-opus-5-5", "--developer", "Anthropic"]


def _seat(status: str = "completed", **extra) -> dict:
    return {"status": status, "artifacts": [], "issues": [], "changes": [], "commands": []} | extra


def _change(run: Path, skill: str, number: int, section: str, reason: str, before: str | None, after: str | None) -> dict:
    relative = f"{skill}/changes/{number:04d}.md"
    path = run / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {section}\n\nReason: {reason}\n\n## Before\n\n{before or '(No previous block.)'}\n\n"
                    f"## After\n\n{after or '(Block removed.)'}\n", encoding="utf-8")
    return {"section": section, "path": relative, "sha256": "x", "shown_in_chat": True}


@pytest.fixture()
def run(tmp_path: Path) -> Path:
    """A run whose stages recorded their edits, without a corrected version."""
    folder = tmp_path / "runs" / "20261020T100000Z-abcd1234"
    folder.mkdir(parents=True)
    skills = {
        "manuscript-prose-edit": _seat(changes=[_change(
            folder, "manuscript-prose-edit", 1, "Abstract", "Shorter sentence. The claim stays as it was.",
            "Our results clearly demonstrate that the method works well.", "Our results show that the method works.")]),
        "manuscript-story": _seat(changes=[_change(
            folder, "manuscript-story", 1, "Discussion > Limitations, paragraph 2", "The limit was missing.", None,
            "The cohort is small and from one site.")]),
        "manuscript-deslop": _seat(routine_only_reason="Removed three stock phrases; no claim or number changed."),
        "manuscript-peer-review": _seat(artifacts=[{"role": "referee", "path": "x.md", "seat": "methods",
                                                    "model": "codex/gpt-5.6-sol"}]),
        "manuscript-reference-check": _seat("reused", reason="From the run of 12 October."),
        "manuscript-figures": _seat("not_run"),
        "manuscript-journal-adapt": _seat("running"),
        "manuscript-dashboard": _seat(),
    }
    (folder / "run.json").write_text(json.dumps({"schema_version": 1, "run_id": folder.name,
                                                 "started_at": "2026-10-20T10:00:00+00:00", "skills": skills}),
                                     encoding="utf-8")
    return folder


def _draft(run: Path, *args: str) -> dict:
    result = CliRunner().invoke(ai_use.app, [str(run), *args])
    assert result.exit_code == 0, result.output
    return json.loads((run / json.loads(result.output)["files"][1]).read_text(encoding="utf-8"))


def test_the_draft_names_each_kind_of_change_with_its_sections_and_the_checks(run: Path) -> None:
    draft = _draft(run, *WHO)
    text = draft["statement"]
    assert text.startswith("Claude Code (claude-opus-5-5, Anthropic), through the manuscript-skills plugin (version ")
    assert "to help draft text in the Discussion, revise passages in the Abstract and edit the language." in text
    assert "It was also used to simulate peer review; this check changed no text." in text
    assert "Some of these readings also ran on codex/gpt-5.6-sol." in text
    assert text.endswith("take full responsibility for the content.") and ai_use.GAP in text
    assert draft["kind"] == "drafting" and draft["source"] == "the edits the stages recorded"
    assert [r["stage"] for r in draft["stages"]] == ["manuscript-prose-edit", "manuscript-story", "manuscript-deslop",
                                                     "manuscript-peer-review"]
    assert draft["not_covered"] == ["the reference check was reused from an earlier run."]
    assert draft["covers"] | {"to": None} == {"run_id": run.name, "from": "2026-10-20", "to": None,
                                             "dates": draft["covers"]["dates"], "scope": "this run only"}


def test_the_report_says_it_covers_this_run_only_and_asks_the_authors_once(run: Path) -> None:
    _draft(run, *WHO)
    md = (run / "manuscript-journal-adapt" / "ai-use.md").read_text(encoding="utf-8")
    assert f"This draft covers run {run.name} (" in md and "It says nothing about AI use before this run" in md
    assert md.count(ai_use.QUESTION) == 1
    assert "| Removing formulaic phrasing | routine edits only: Removed three stock phrases" in md
    assert "- Discussion > Limitations, paragraph 2: The limit was missing. (drafting; story.C1)" in md
    assert "Kind of use, as journal rules name it: **drafting** (the AI wrote new sentences)." in md


def test_the_answer_is_asked_once_and_reused_in_the_same_run_but_never_from_another(run: Path) -> None:
    other = run.parent / "20261001T090000Z-older000" / "manuscript-journal-adapt"
    other.mkdir(parents=True)
    (other / "ai-use.json").write_text(json.dumps({"authors_use": {"answer": "We used a chatbot to translate."}}),
                                       encoding="utf-8")
    first = _draft(run, *WHO)
    assert first["authors_use"]["answer"] is None  # an earlier run's answer is history, not this run's
    _draft(run, *WHO, "--authors-use", "ChatGPT (OpenAI) translated the Methods from German")
    third = _draft(run, *WHO)
    assert third["authors_use"]["answer"] == "ChatGPT (OpenAI) translated the Methods from German"
    assert "ChatGPT (OpenAI) translated the Methods from German. The authors reviewed" in third["statement"]
    assert third["gaps"] == [] and ai_use.GAP not in third["statement"]
    assert sorted(p.name for p in (run / "manuscript-journal-adapt").iterdir()) == [
        "ai-use.2.json", "ai-use.2.md", "ai-use.3.json", "ai-use.3.md", "ai-use.json", "ai-use.md"]


def test_none_adds_nothing_and_never_a_negative_assertion(run: Path) -> None:
    draft = _draft(run, *WHO, "--authors-use", "none")
    assert ai_use.GAP not in draft["statement"] and "no " not in draft["statement"].split("check changed")[0]
    assert "The authors said they used no AI tools outside this run" in (
        run / "manuscript-journal-adapt" / "ai-use.md").read_text(encoding="utf-8")


def test_a_missing_tool_stays_a_marked_gap(run: Path) -> None:
    draft = _draft(run)
    assert draft["statement"].startswith("[tool] ([model id]), through")
    assert draft["gaps"] == ["the tool and model id", "the authors' own use outside this run"]


def test_the_corrected_version_gives_what_changed_when_the_run_built_one(run: Path) -> None:
    (run / "manuscript-story").mkdir(exist_ok=True)
    (run / "manuscript-story" / "findings.json").write_text(json.dumps({"findings": [], "changes": [
        {"id": "ST-C2", "status": "proposed", "section": "Introduction", "summary": "Open with the question.",
         "before": "Ageing is complex.", "after": "Why do some cells age faster?"}]}), encoding="utf-8")
    (run / "manuscript-journal-adapt" / "findings.json").parent.mkdir(exist_ok=True)
    (run / "manuscript-journal-adapt" / "findings.json").write_text(json.dumps({"findings": [], "changes": [
        {"id": "JA-C3", "status": "proposed", "section": "Statements", "summary": "Add the statement.",
         "after": "AI was used."}]}), encoding="utf-8")
    inventory = {"changes": [
        {"id": "prose-edit.C1", "status": "applied", "section": "Abstract", "summary": "Shorter sentence. More.",
         "before": "Our results clearly demonstrate it.", "after": "Our results show it."},
        {"id": "ST-C2", "status": "proposed", "section": "Introduction", "summary": "Open with the question.",
         "before": "Ageing is complex.", "after": "Why do some cells age faster?"},
        {"id": "JA-C3", "status": "proposed", "section": "Statements", "summary": "Add the statement.",
         "after": "AI was used."}]}
    (run / "manuscript-dashboard").mkdir(exist_ok=True)
    (run / "manuscript-dashboard" / "findings.json").write_text(json.dumps(inventory), encoding="utf-8")
    revision = run / "manuscript-improve" / "revision"
    revision.mkdir(parents=True)
    (revision / "revision.json").write_text(json.dumps({
        "applied": ["prose-edit.C1"], "restored": [], "proposed_in_this_version": ["ST-C2"],
        "held": [{"id": "JA-C3", "why": "Waits for the journal."}], "alternatives": [], "not_placed": []}),
        encoding="utf-8")
    draft = _draft(run, *WHO)
    assert draft["source"] == "the corrected version (manuscript-improve/revision)"
    changed = {r["stage"]: [c["id"] for c in r["changes"]] for r in draft["stages"] if r.get("changes")}
    assert changed == {"manuscript-prose-edit": ["prose-edit.C1"], "manuscript-story": ["ST-C2"]}
    assert "revise passages in the Abstract and Introduction" in draft["statement"]
    assert draft["kind"] == "revision" and "help draft" not in draft["statement"]
    assert draft["not_covered"][0].startswith("1 proposal(s) of this run are not in the corrected version")


def test_proposals_left_out_of_the_text_are_named_without_a_corrected_version(run: Path) -> None:
    (run / "manuscript-story" / "findings.json").write_text(json.dumps({"findings": [], "changes": [
        {"id": "ST-C2", "status": "proposed", "section": "Introduction", "summary": "s", "after": "x"}]}),
        encoding="utf-8")
    assert _draft(run, *WHO)["not_covered"][0].startswith("1 proposal(s) of this run are not in the text")


def test_kinds_sections_and_dates() -> None:
    assert ai_use.kind_of(None, "A new sentence.") == "drafting"
    assert ai_use.kind_of("An old sentence.", None) == "revision"
    assert ai_use.kind_of("The effect was large.", "The effect was moderate.") == "revision"
    fresh = " ".join(f"word{n}" for n in range(25))
    assert ai_use.kind_of("The effect was large.", f"The effect was large. {fresh}") == "drafting"
    assert ai_use.section_name("Methods > Statistics, paragraph 2") == "Methods"
    assert ai_use.section_name("Results paragraph 3") == "Results"
    assert ai_use.section_name("3.2 Polygenic Risk Scores") == "Polygenic Risk Scores"
    assert ai_use.section_name("1. Introduction") == "Introduction" and ai_use.section_name("IV. Results") == "Results"
    assert ai_use.sections_phrase(["A", "B", "C", "D"]) == " in the A, B, C and D"
    assert ai_use.sections_phrase(["A", "B", "C", "D", "E", "F"]) == " in 6 sections"
    assert ai_use.dates_phrase(date(2026, 10, 20), date(2026, 10, 20)) == " on 20 October 2026"
    assert ai_use.dates_phrase(date(2026, 10, 20), date(2026, 10, 25)) == " between 20 October 2026 and 25 October 2026"


def test_dates_appear_only_when_asked(run: Path) -> None:
    assert " was used to " in _draft(run, *WHO)["statement"]
    assert " was used between 20 October 2026 and " in _draft(run, *WHO, "--dates")["statement"]


def test_a_check_only_run_says_it_changed_no_text(tmp_path: Path) -> None:
    folder = tmp_path / "r"
    folder.mkdir()
    (folder / "run.json").write_text(json.dumps({"run_id": "r", "started_at": "2026-10-20T10:00:00+00:00", "skills": {
        "manuscript-reference-check": _seat(), "manuscript-integrity-check": _seat("partial")}}), encoding="utf-8")
    draft = _draft(folder, *WHO, "--authors-use", "none")
    assert draft["kind"] is None
    assert ("was used to check the references and whether they support the claims cited to them and check the "
            "numbers, statistics and submission files; it changed no text.") in draft["statement"]


def test_a_folder_that_is_not_a_run_is_refused(tmp_path: Path) -> None:
    assert CliRunner().invoke(ai_use.app, [str(tmp_path)]).exit_code == 2


def test_the_statement_s_own_changes_are_left_out(run: Path) -> None:
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    data["skills"]["manuscript-journal-adapt"]["changes"] = [_change(
        run, "manuscript-journal-adapt", 1, "Use of large language models", "The venue asks for it.", None,
        "Claude Code was used to revise passages.")]
    (run / "run.json").write_text(json.dumps(data), encoding="utf-8")
    draft = _draft(run, *WHO)
    assert "manuscript-journal-adapt" not in [r["stage"] for r in draft["stages"]]
    assert ai_use.disclosure("AI-use statement") and ai_use.disclosure("Declaration of generative AI")
    assert not ai_use.disclosure("Methods") and not ai_use.disclosure("Use of the cohort")
