"""Evidence identity, honest counting and offline rendering for the review dashboard."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/manuscript-visualize/scripts/dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard", SCRIPT)
visualize = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = visualize
spec.loader.exec_module(visualize)


@pytest.fixture()
def data(tmp_path: Path) -> dict:
    evidence = "The reference is wrong. The claim needs checking. Before A. After A. Before B. After B."
    (tmp_path / "review.md").write_text(evidence)
    sources = [{"path": "review.md", "quote": evidence}]
    def finding(fid, assessment, resolution):
        return {"id": fid, "category": "References", "section": "Discussion", "summary": f"Issue {fid}",
                "severity": "major", "assessment": assessment, "resolution": resolution,
                "skills": ["manuscript-reference-check", "manuscript-integrity-check"], "evidence": sources}
    def change(cid, state, fid, letter):
        return {"id": cid, "kind": "Reference correction", "section": "Discussion", "summary": f"Edit {cid}",
                "status": state, "finding_ids": [fid], "before": f"Before {letter}.", "after": f"After {letter}.",
                "evidence": sources}
    return {"schema_version": 2, "title": "Review findings", "run_id": "test-run", "scope": "Selected test records.",
            "illustrative": True,
            "coverage": [{"skill": skill, "status": "partial", "note": "Selected sections only.", "evidence": sources}
                         for skill in ("manuscript-reference-check", "manuscript-integrity-check")],
            "findings": [finding("F1", "confirmed", "addressed"), finding("F2", "confirmed", "open"),
                         finding("F3", "candidate", "unknown"), finding("F4", "dismissed", "unknown")],
            "changes": [change("C1", "applied", "F1", "A"), change("C2", "applied", "F1", "B"),
                        change("C3", "proposed", "F2", "A")]}


def test_counts_distinguish_edits_findings_attribution_and_candidates(data: dict) -> None:
    summary = visualize.summarize(visualize.Inventory.model_validate(data))
    assert summary["counts"] == {"confirmed_findings": 2, "addressed_findings": 1, "open_findings": 1,
                                 "resolution_unknown": 0, "candidate_findings": 1, "dismissed_flags": 1,
                                 "applied_edits": 2, "proposed_edits": 1}
    assert summary["by_category"] == {"References": 2}  # two reporting skills still count each finding once
    assert summary["by_resolution"] == {"addressed": 1, "open": 1}


@pytest.mark.parametrize("field", ["findings", "changes", "coverage"])
def test_duplicate_ids_are_rejected_instead_of_inflating_counts(data: dict, field: str) -> None:
    data[field].append(copy.deepcopy(data[field][0]))
    with pytest.raises(ValidationError, match="Duplicate"):
        visualize.Inventory.model_validate(data)


@pytest.mark.parametrize("mutation", ["proposal-only", "candidate", "unknown-link", "unknown-skill"])
def test_unsupported_resolution_or_attribution_is_rejected(data: dict, mutation: str) -> None:
    if mutation == "proposal-only":
        for change in data["changes"]:
            change["status"] = "proposed"
    elif mutation == "candidate":
        data["findings"][0]["assessment"] = "candidate"
    elif mutation == "unknown-link":
        data["changes"][0]["finding_ids"] = ["absent"]
    else:
        data["findings"][0]["skills"] = ["absent"]
    with pytest.raises(ValidationError):
        visualize.Inventory.model_validate(data)


def test_evidence_identity_and_applied_passages_are_checked(data: dict, tmp_path: Path) -> None:
    inventory = visualize.Inventory.model_validate(data)
    assert len(visualize.verify_evidence(inventory, tmp_path)["review.md"]) == 64
    inventory.findings[0].evidence[0].quote = "A quote the report never contained."
    with pytest.raises(ValueError, match="quote absent"):
        visualize.verify_evidence(inventory, tmp_path)
    inventory = visualize.Inventory.model_validate(data)
    inventory.changes[0].after = "An edit that was never applied."
    with pytest.raises(ValueError, match="before/after text absent"):
        visualize.verify_evidence(inventory, tmp_path)


def test_invalid_evidence_writes_no_dashboard(data: dict, tmp_path: Path) -> None:
    data["findings"][0]["evidence"] = [{"path": "missing.md", "quote": "No report."}]
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    with pytest.raises(OSError):
        visualize.render(source, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def embedded(document: str) -> dict:
    start = document.index('<script type="application/json" id="inventory">') + len('<script type="application/json" id="inventory">')
    return json.loads(document[start:document.index("</script>", start)])


def test_dashboard_inlines_records_as_inert_data_and_keeps_only_file_names(data: dict, tmp_path: Path) -> None:
    data["title"] = '<script>alert("title")</script>'
    data["findings"][0]["summary"] = '</script><img src=x onerror="alert(1)"><!--'
    data["findings"][0]["evidence"] = [{"path": str(tmp_path / "review.md"), "quote": "The reference is wrong."}]
    inventory = visualize.Inventory.model_validate(data)
    summary = visualize.summarize(inventory)
    summary["evidence_sha256"] = {str(tmp_path / "review.md"): "0" * 64}
    output = visualize.dashboard_html(inventory, summary)
    assert '<script>alert("title")</script>' not in output and "&lt;script&gt;" in output
    assert '</script><img' not in output and "<!--" not in output.split('id="inventory">')[1]
    assert '<script src=' not in output and "https://" not in output
    assert str(tmp_path) not in output
    payload = embedded(output)
    assert payload["inventory"]["findings"][0]["summary"].startswith("</script><img")
    assert payload["inventory"]["findings"][0]["evidence"][0]["path"] == "review.md"
    assert payload["summary"]["counts"]["proposed_edits"] == 1


def test_the_dashboard_is_the_only_rendering(data: dict, tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    summary = visualize.render(source, tmp_path / "out")
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["dashboard.html", "summary.json"]
    assert embedded((tmp_path / "out/dashboard.html").read_text())["summary"]["counts"] == summary["counts"]


def test_only_the_current_schema_is_accepted(data: dict) -> None:
    data["schema_version"] = 1
    with pytest.raises(ValidationError):
        visualize.Inventory.model_validate(data)


def test_an_addition_names_the_passage_it_follows_and_a_replacement_does_not(data: dict) -> None:
    data["changes"][2].update(before=None, anchor="Before A.")
    assert visualize.Inventory.model_validate(data).changes[2].anchor == "Before A."
    data["changes"][2]["before"] = "Before A."
    with pytest.raises(ValidationError, match="only an addition"):
        visualize.Inventory.model_validate(data)


def reference(data: dict) -> dict:
    data["reference"] = {
        "title": "the referee's review", "description": "Comments on the same version.",
        "source": {"path": "review.md", "quote": "The reference is wrong."},
        "items": [{"id": "R1", "origin": "reviewer", "summary": "Wrong reference", "category": "References"},
                  {"id": "R2", "origin": "reviewer", "summary": "Claim unchecked", "category": "Claims and evidence"},
                  {"id": "R3", "origin": "authors", "summary": "Typo", "category": "Writing and clarity", "substantive": False}],
        "matches": [{"reference_id": "R1", "finding_ids": ["F1"], "match": "full", "note": "Same entry."},
                    {"reference_id": "R2", "finding_ids": ["F3"], "match": "partial", "note": "Candidate names part of it."}]}
    return data


def test_reference_comparison_counts_each_item_once(data: dict, tmp_path: Path) -> None:
    inventory = visualize.Inventory.model_validate(reference(data))
    visualize.verify_evidence(inventory, tmp_path)
    bench = visualize.summarize(inventory)["benchmark"]
    assert (bench["items"], bench["full"], bench["partial"], bench["missed"]) == (3, 1, 1, 1)
    assert (bench["substantive"], bench["substantive_caught"]) == (2, 2)
    assert bench["confirmed_without_counterpart"] == 1  # F2 is confirmed and matches nothing
    assert bench["by_category"]["Writing and clarity"] == {"missed": 1}


def test_misses_are_counted_by_reason_and_by_the_skill_that_owns_them(data: dict) -> None:
    data = reference(data)
    data["reference"]["items"][1].update(miss_reason="skill-did-not-look", owner="manuscript-reference-check")
    data["reference"]["items"][2].update(miss_reason="wording-preference")
    bench = visualize.summarize(visualize.Inventory.model_validate(data))["benchmark"]
    assert bench["miss_reasons"] == {"skill-did-not-look": 1, "wording-preference": 1}
    assert bench["missed_by_owner"] == {"manuscript-reference-check": 1}  # the wording item is not substantive
    data["reference"]["items"][0]["miss_reason"] = "input-missing"
    with pytest.raises(ValidationError, match="matched in full"):
        visualize.Inventory.model_validate(data)


@pytest.mark.parametrize("mutation", ["unknown-item", "unknown-finding", "dismissed", "twice"])
def test_reference_matches_must_link_real_records(data: dict, mutation: str) -> None:
    data = reference(data)
    match = data["reference"]["matches"][0]
    if mutation == "unknown-item":
        match["reference_id"] = "R9"
    elif mutation == "unknown-finding":
        match["finding_ids"] = ["F9"]
    elif mutation == "dismissed":
        match["finding_ids"] = ["F4"]
    else:
        data["reference"]["matches"].append(copy.deepcopy(match))
    with pytest.raises(ValidationError):
        visualize.Inventory.model_validate(data)


def test_real_render_preserves_partial_scope_counts_and_previous_attempts(data: dict, tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data))
    output = tmp_path / "rendered"
    summary = visualize.render(source, output)
    payload = embedded((output / "dashboard.html").read_text())
    assert payload["inventory"]["illustrative"] and {c["status"] for c in payload["inventory"]["coverage"]} == {"partial"}
    assert json.loads((output / "summary.json").read_text())["counts"] == summary["counts"]
    original = (output / "dashboard.html").read_bytes()
    with pytest.raises(ValueError, match="already exist"):
        visualize.render(source, output)
    assert (output / "dashboard.html").read_bytes() == original


def test_empty_findings_are_not_mislabeled_as_complete_review(data: dict) -> None:
    data["findings"], data["changes"] = [], []
    inventory = visualize.Inventory.model_validate(data)
    summary = visualize.summarize(inventory)
    assert not any(summary["counts"].values())
    assert {item["status"] for item in summary["coverage"]} == {"partial"}


def test_worked_input_uses_actual_evidence_and_does_not_invent_edits() -> None:
    source = ROOT / "evals/fixtures/manuscript-visualize/reader-review.json"
    inventory = visualize.Inventory.model_validate_json(source.read_text())
    visualize.verify_evidence(inventory, source.parent)
    summary = visualize.summarize(inventory)
    assert summary["counts"]["confirmed_findings"] == 6
    assert summary["counts"]["applied_edits"] == 0
    assert summary["by_severity"] == {"unknown": 6}
    assert inventory.coverage[0].status == "partial" and "Selected" in inventory.scope


COLLECT = ROOT / "skills/manuscript-visualize/scripts/collect.py"
spec = importlib.util.spec_from_file_location("collect", COLLECT)
collect = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = collect
spec.loader.exec_module(collect)


def synthetic_run(tmp_path: Path) -> Path:
    paper = tmp_path / "paper.md"
    paper.write_text("# Tool paper\n\n## Abstract\n\nIt runs in 38.9 seconds.\n\n## 2. Methods\n\nWe join by position.\n")
    run = tmp_path / "run"
    (run / "inputs").mkdir(parents=True)
    (run / "inputs/01-paper.md").write_text("# Tool paper\n\n## Abstract\n\nIt runs in 39 seconds.\n\n## 2. Methods\n\nWe join by rsID.\n")
    skills = {}
    for name, status in (("manuscript-integrity-check", "completed"), ("manuscript-story", "partial"),
                         ("manuscript-prose-edit", "completed")):
        (run / name).mkdir()
        (run / name / "README.md").write_text(f"# {name}\n\nStatus: **{status}**. Covered.\n")
        skills[name] = {"status": status, "reason": "Covered.", "artifacts": [], "issues": [], "changes": [], "commands": []}
    (run / "manuscript-integrity-check/report.md").write_text("The join key contradicts the code. The Abstract figure differs.")
    (run / "manuscript-integrity-check/findings.json").write_text(json.dumps({"findings": [
        {"id": "IC-1", "category": "Text versus code", "section": "2. Methods", "quote": "We join by rsID.",
         "summary": "Join key contradicts the code", "severity": "major", "stage": "now", "confidence": "confirmed",
         "evidence": [{"path": "report.md", "quote": "The join key contradicts the code."}]},
        {"id": "IC-2", "category": "Numbers and statistics", "section": "Abstract", "quote": "It runs in 39 seconds.",
         "summary": "Abstract runtime differs", "severity": "minor", "stage": "now", "confidence": "candidate", "evidence": []}],
        "dismissed": [{"summary": "Superhuman reads as hype", "why": "It is a module name."}],
        "not_checked": [{"check": "Laptop run", "why": "No laptop record", "leaves_open": "The laptop claim"}]}))
    (run / "manuscript-integrity-check/checks").mkdir()
    (run / "manuscript-integrity-check/checks/scan.json").write_text(json.dumps({"findings": [{"check": "ai-use"}, {"check": "ai-use"}, {"check": "references"}]}))
    (run / "manuscript-story/findings.json").write_text(json.dumps({"findings": [
        {"id": "ST-1", "category": "Text versus code", "section": "2 Methods", "quote": "We join by rsID.",
         "summary": "Readers saw two join keys", "severity": "minor", "stage": "writing", "confidence": "candidate", "evidence": []}]}))
    (run / "manuscript-story/readers").mkdir()
    (run / "manuscript-story/readers/skimmer.md").write_text("# Skimmer\n\n```yaml\nseat: skimmer\nstopped_at:\n  section: Methods\n  why: Lost.\n"
                                                             "takeaway: A fast tool.\nstumbles:\n  - quote: rsID\nwanted: []\nnext: stop here\n```\n")
    (run / "manuscript-prose-edit/changes").mkdir()
    for number, (before, after) in enumerate((("It runs in 39 seconds.", "It runs in 38.9 seconds."), ("We join by rsID.", "We join by allele.")), 1):
        (run / f"manuscript-prose-edit/changes/000{number}.md").write_text(f"# Abstract\n\nReason: Fix {number}\n\n## Before\n\n{before}\n\n## After\n\n{after}\n")
        skills["manuscript-prose-edit"]["changes"].append({"section": "Abstract", "path": f"manuscript-prose-edit/changes/000{number}.md"})
    (run / "run.json").write_text(json.dumps({"run_id": "R1", "started_at": "2026-10-22T00:00:00+00:00", "skills": skills,
        "inputs": [{"original": str(paper), "snapshot": "inputs/01-paper.md", "sha256": "0" * 64}]}))
    return run


def test_collect_merges_attributions_checks_edits_and_keeps_every_source(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    run = synthetic_run(tmp_path)
    merges = tmp_path / "merges.json"
    merges.write_text(json.dumps({"merge": [{"keep": "IC-1", "ids": ["ST-1"]}],
                                  "update": [{"id": "IC-2", "assessment": "confirmed"}],
                                  "change_links": [{"change": "prose-edit.C1", "finding_ids": ["IC-2"]}],
                                  "addressed": ["IC-2"]}))
    out = run / "manuscript-visualize/findings.json"
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(out), "--merge", str(merges), "--version", "v0.3"])
    assert result.exit_code == 0, result.output
    inventory = visualize.Inventory.model_validate_json(out.read_text())
    merged = next(f for f in inventory.findings if f.id == "IC-1")
    assert merged.skills == ["manuscript-integrity-check", "manuscript-story"] and merged.severity == "major"
    assert [s.id for s in merged.sources] == ["IC-1", "ST-1"] and merged.stage == "now"
    assert inventory.manuscript.sections == ["Abstract", "2. Methods"] and inventory.manuscript.version == "v0.3"
    assert {c.id: c.status for c in inventory.changes} == {"prose-edit.C1": "applied", "prose-edit.C2": "proposed"}
    assert next(f for f in inventory.findings if f.id == "IC-2").resolution == "addressed"
    assert inventory.dismissed[0].why == "It is a module name." and inventory.not_checked[0].check == "Laptop run"
    assert inventory.panel.readers[0].takeaway == "A fast tool." and inventory.panel.readers[0].stopped_at == "Methods: Lost."
    assert {(s.check, s.count) for s in inventory.signals} >= {("ai-use", 2), ("references", 1), ("reader concerns: skimmer", 1)}
    assert {c.skill: c.status for c in inventory.coverage}["manuscript-story"] == "partial"
    summary = visualize.summarize(inventory)
    assert summary["counts"]["confirmed_findings"] == 2 and summary["found_by_several_skills"] == 1
    again = CliRunner().invoke(collect.app, [str(run), "--output", str(out)])
    assert again.exit_code == 1 and "exists" in again.output


def test_collect_refuses_an_inventory_whose_evidence_is_not_in_its_file(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    run = synthetic_run(tmp_path)
    doc = json.loads((run / "manuscript-integrity-check/findings.json").read_text())
    doc["findings"][0]["evidence"][0]["quote"] = "A sentence the report never wrote."
    (run / "manuscript-integrity-check/findings.json").write_text(json.dumps(doc))
    out = run / "manuscript-visualize/findings.json"
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(out)])
    assert result.exit_code == 1 and not out.exists()


def test_collect_reads_reading_paths_where_readers_left_and_each_panel_round(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    run = synthetic_run(tmp_path)
    (run / "manuscript-story/readers-paths").mkdir()
    (run / "manuscript-story/readers-paths/clinician.md").write_text(
        "# Clinician\n\n```yaml\nseat: clinician\npath:\n  - {section: Abstract, how: read}\n  - {section: 2. Methods, how: skipped}\n"
        "left:\n  section: Abstract\n  quote: It runs.\n  why: Nothing for patients.\ndips: [{section: Abstract, quote: x, why: y}]\n"
        "takeaway: Fast.\nnext: bookmark\n```\n")
    out = run / "manuscript-visualize/findings.json"
    assert CliRunner().invoke(collect.app, [str(run), "--output", str(out)]).exit_code == 0
    readers = {r.seat: r for r in visualize.Inventory.model_validate_json(out.read_text()).panel.readers}
    clinician = readers["clinician"]
    assert clinician.round == "readers-paths" and clinician.left == "Abstract" and clinician.next == "bookmark"
    assert [(s.section, s.how) for s in clinician.path] == [("Abstract", "read"), ("2. Methods", "skipped")]
    assert clinician.stopped_at == "Abstract: Nothing for patients." and clinician.dips == ["Abstract"]
    assert readers["skimmer"].left == "" and readers["skimmer"].round == ""  # the older format records no leaving point


def test_proposals_that_rewrite_the_same_passage_are_grouped_as_alternatives(data: dict) -> None:
    sentence = "There is no open-source platform that combines comprehensive variant annotation with ease of use."
    data["findings"][0]["resolution"] = "open"
    data["changes"] = [
        {"id": f"P{i}", "kind": "Claim correction", "section": "Introduction", "summary": "Narrow", "status": "proposed",
         "before": before, "after": "Narrower.", "evidence": data["findings"][0]["evidence"]}
        for i, before in enumerate([sentence, sentence + " Researchers lack tools.", "An unrelated sentence elsewhere."], 1)]
    summary = visualize.summarize(visualize.Inventory.model_validate(data))
    assert summary["competing_proposals"] == [["P1", "P2"]]


def test_a_proposal_linked_to_a_merged_record_follows_it_to_the_record_kept(tmp_path: Path) -> None:
    """The 2026-10-22 run: a journal proposal still pointed at a finding merged into another."""
    from typer.testing import CliRunner

    run = synthetic_run(tmp_path)
    story = json.loads((run / "manuscript-story/findings.json").read_text())
    story["changes"] = [{"id": "ST-C1", "kind": "Story edit", "section": "2. Methods", "summary": "Say the key", "status": "proposed",
                         "finding_ids": ["ST-1"], "before": "We join by rsID.", "after": "We join by position.", "journal": "Genes",
                         "evidence": [{"path": "../manuscript-integrity-check/report.md", "quote": "The join key contradicts the code."}]}]
    (run / "manuscript-story/findings.json").write_text(json.dumps(story))
    merges = tmp_path / "merges.json"
    merges.write_text(json.dumps({"merge": [{"keep": "IC-1", "ids": ["ST-1"]}],
                                  "decisions": [{"id": "D1", "summary": "Choose the key", "finding_ids": ["ST-1"]}]}))
    out = run / "manuscript-visualize/findings.json"
    result = CliRunner().invoke(collect.app, [str(run), "--output", str(out), "--merge", str(merges)])
    assert result.exit_code == 0, result.output
    inventory = visualize.Inventory.model_validate_json(out.read_text())
    (proposal,) = [c for c in inventory.changes if c.id == "ST-C1"]
    assert proposal.finding_ids == ["IC-1"] and "journal: Genes" in proposal.summary
    assert inventory.decisions[0].finding_ids == ["IC-1"]


def test_collect_reads_each_venue_ai_policy_from_the_ladder_or_the_catalogue(tmp_path: Path) -> None:
    folder = tmp_path / "manuscript-journal-select"
    folder.mkdir()
    header = "ladder,rung,key,name,ai_points,ai_drafting,ai_prompts,ai_records,ai_detection,ai_declaration,ai_counted,ai_extra,ai_reasons,ai_policy_url\n"
    (folder / "p.journal-ladder.csv").write_text(header + "journals,1,strict,Strict,6,red: banned for the whole paper,"
                                                 "red: required in the paper,good: not asked for,good: none named,good: Methods,"
                                                 "unknown: not stated,good: none listed,Six points.,https://strict.example/ai\n")
    (folder / "p.preprint-ladder.csv").write_text("ladder,rung,key,name\npreprints,1,biorxiv,bioRxiv\n")
    rows = {v["key"]: v for v in collect.venues(tmp_path)}
    strict = rows["strict"]["ai_policy"]
    assert strict["aspects"]["drafting"] == {"level": "red", "text": "banned for the whole paper"}
    assert strict["source"] == "the run's ladder" and strict["url"] == "https://strict.example/ai"
    older = rows["biorxiv"]["ai_policy"]  # a ladder from before the AI columns: read from the catalogue
    assert "venue catalogue" in older["source"] and set(older["aspects"]) == set(collect.ASPECTS)
    assert visualize.Venue.model_validate(rows["strict"]).ai_policy.aspects["prompts"].level == "red"


def test_collect_gives_each_reviewer_concerns_with_suggestions_and_links_them_to_the_problems(tmp_path: Path) -> None:
    folder = tmp_path / "manuscript-peer-review"
    folder.mkdir()
    doc = {"reports": [{"seat": "skeptic", "summary": "Sound, but the ratio is undefined.",
                        "recommendations": [{"venue": "genes", "recommendation": "major-revision", "reason": "Ratios."}]}],
           "strengths": [{"seat": "skeptic", "note": "The genome is public."}],
           "findings": [{"id": "SK-1", "seat": "skeptic", "severity": "major", "concern": "The 172-fold ratio is undefined.",
                         "change_my_mind": "Define warm runs.", "route": "fixable-in-text", "verdict": "confirmed",
                         "defence_outcome": "partly answered", "placement": "methods", "cost": "text"}],
           "adjudication": {}}
    (folder / "findings.adjudicated.json").write_text(json.dumps(doc))
    (folder / "findings.merged.json").write_text(json.dumps({**doc, "findings": []}))
    panel = collect.panel(tmp_path)
    (reviewer,) = panel["reviewers"]
    assert reviewer["strengths"] == ["The genome is public."] and reviewer["summary"].startswith("Sound")
    concern = reviewer["concerns"][0]
    assert (concern["suggestion"], concern["verdict"], concern["defence"]) == ("Define warm runs.", "confirmed", "partly answered")
    findings = [{"id": "PR-1", "detail": "Grouped from SK-1 and SM-2.", "summary": "Ratio", "sources": [{"id": "PR-1"}]},
                {"id": "IC-1", "detail": "", "summary": "Ratio", "sources": [{"id": "IC-1"}, {"id": "PR-1"}]}]
    mentions = collect.concern_mentions(findings)
    inventory = {"findings": findings[1:], "panel": panel}  # PR-1 was merged into IC-1
    collect.link_concerns(inventory, mentions)
    assert concern["finding_ids"] == ["IC-1"]
