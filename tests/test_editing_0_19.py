"""Offline tests for the 0.19 editing fixes: the claim guard's story moves, stock phrases, declarations and
paragraph-local terms; the smell check's cluster rule and kept patterns; and the editing skills' texts.

Run with `uv run pytest tests/test_editing_0_19.py -vvv`.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = _load("guard_0_19", SKILLS / "manuscript-prose-edit" / "scripts" / "guard.py")
profile = _load("style_profile_0_19", SKILLS / "manuscript-deslop" / "scripts" / "style_profile.py")
setup = _load("detector_setup_0_19", SKILLS / "manuscript-prose-edit" / "scripts" / "detector_setup.py")
runner = CliRunner()


def _of(report: dict, kind: str) -> list[dict]:
    return [c for c in report["sentence_changes"] if c["kind"] == kind]


def _record(folder: Path, section: str, before: str | None, after: str | None, number: int = 1) -> Path:
    """A change record as `runs.py change` writes it, in RUN/manuscript-story/changes/."""
    path = folder / "changes" / f"{number:04d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {section}\n\nReason: caveat placement\n\n## Before\n\n{before or '(No previous block.)'}\n\n"
                    f"## After\n\n{after or '(Block removed.)'}\n", encoding="utf-8")
    return path


def _final_gate(tmp_path: Path, before: str, after: str, story: Path, requests: list | None = None) -> int:
    """manuscript-improve's final check: guard.py ORIGINAL FINAL --revision --relocated-in RUN/manuscript-story
    --authorised RUN/manuscript-improve/requested-claims.yaml."""
    original, final, requested = tmp_path / "original.md", tmp_path / "final.md", tmp_path / "requested-claims.yaml"
    original.write_text(before, encoding="utf-8")
    final.write_text(after, encoding="utf-8")
    requested.write_text(yaml.safe_dump(requests or []), encoding="utf-8")
    result = runner.invoke(guard.app, [str(original), str(final), "--revision", "--relocated-in", str(story),
                                       "--authorised", str(requested)])
    assert result.exit_code in (0, 1), result.output
    return result.exit_code


# --- story moves: a scope qualifier never leaves the Abstract, a caveat moves only within its section ----------------

MICE = ("# Foo and tumours\n\n## Abstract\n\nIn mice, loss of Foo reduces tumour growth by 40%. Foo is a kinase.\n\n"
        "## Results\n\nTumours were measured weekly.\n\n## Limitations\n\nThe study was small.{extra}\n")


def test_a_model_system_dropped_from_the_abstract_fails_the_final_check_even_when_limitations_state_it(
        tmp_path: Path) -> None:
    before = MICE.format(extra="")
    after = MICE.format(extra=" All experiments were done in mice.").replace(
        "In mice, loss of Foo reduces", "Loss of Foo reduces")
    story = tmp_path / "manuscript-story"
    _record(story, "Abstract", "In mice, loss of Foo reduces tumour growth by 40%.",
            "Loss of Foo reduces tumour growth by 40%.")
    _record(story, "Limitations", "The study was small.", "The study was small. All experiments were done in mice.", 2)
    assert _final_gate(tmp_path, before, after, story) == 1
    report = guard.compare(before, after, relocated=True)
    scope = _of(report, "scope")
    assert [(c["removed"], c["severity"], c["relocated_to"]) for c in scope] == [(["In mice"], "protected", None)]
    assert "stays in its sentence" in scope[0]["note"]
    assert guard.exit_code(report) == 1


def test_a_concessive_aside_may_become_its_own_sentence_of_the_abstract() -> None:
    """Story contract: in the Abstract only a verbal hedge moves, to a sentence of its own that keeps its word."""
    before = ("# P\n\n## Abstract\n\nAnnotation was faster than VEP, albeit on four genomes. TeloKit runs offline."
              "\n\n## Results\n\nIt took a minute.\n")
    after = before.replace("than VEP, albeit on four genomes. TeloKit runs offline.",
                           "than VEP. TeloKit runs offline. The comparison holds, albeit on four genomes.")
    report = guard.compare(before, after, relocated=True)
    assert [(c["kind"], c["severity"]) for c in report["sentence_changes"] if c["kind"] == "limitation"] == [
        ("limitation", "warning")]
    assert guard.exit_code(report) == 0
    moved_out = after.replace(" The comparison holds, albeit on four genomes.", "").replace(
        "It took a minute.", "It took a minute. The comparison holds, albeit on four genomes.")
    assert guard.exit_code(guard.compare(before, moved_out, relocated=True)) == 1  # out of the Abstract: lost


CARRIERS = ("# Paper\n\n## Results\n\nThe variant was observed only in carriers of the risk allele.\n\n"
            "## Methods\n\nWe installed the tool on one laptop.\n")


def test_a_lost_only_does_not_find_a_destination_in_an_unrelated_sentence_of_another_section(tmp_path: Path) -> None:
    after = CARRIERS.replace("observed only in", "observed in").replace("installed the tool", "installed only the tool")
    report = guard.compare(CARRIERS, after, revision=True, relocated=True, authorised=[])
    lost = [c for c in _of(report, "limitation") if c["change"] == "removed"]
    assert [(c["severity"], c["relocated_to"]) for c in lost] == [("protected", None)]
    assert guard.exit_code(report) == 1
    assert _final_gate(tmp_path, CARRIERS, after, tmp_path / "no-story-run") == 1


RESULTS = ("# TeloKit\n\n## Abstract\n\nTeloKit annotates telomere variants offline.\n\n## Results\n\n"
           "{claim} Memory stayed below 2 GB.\n\nThe benchmark used a single laptop for every run. {moved}"
           "Scoring took one minute.\n\n## Discussion\n\nTeloKit is fast.\n")
CLAIM_BEFORE = "Albeit tested on four genomes, the annotation was faster than the Generation I system."
CLAIM_AFTER = "The annotation was faster than the Generation I system."
MOVED = "The annotation speed comparison holds, albeit on four genomes."


def test_a_same_section_story_move_passes_the_final_check_only_inside_the_story_changes(tmp_path: Path) -> None:
    before = RESULTS.format(claim=CLAIM_BEFORE, moved="")
    after = RESULTS.format(claim=CLAIM_AFTER, moved=MOVED + " ")
    story = tmp_path / "manuscript-story"
    _record(story, "Results", CLAIM_BEFORE + " Memory stayed below 2 GB.", CLAIM_AFTER + " Memory stayed below 2 GB.")
    _record(story, "Results", "The benchmark used a single laptop for every run. Scoring took one minute.",
            f"The benchmark used a single laptop for every run. {MOVED} Scoring took one minute.", 2)
    assert _final_gate(tmp_path, before, after, story) == 0
    # the same move, made by another stage: the story records do not hold it, so the caveat counts as lost
    other = tmp_path / "other"
    other.mkdir()
    _record(other, "Discussion", "TeloKit is fast.", "TeloKit is quick.")
    assert _final_gate(tmp_path, before, after, other) == 1
    # the story stage's own gate (no records needed) passes it
    assert guard.exit_code(guard.compare(before, after, relocated=True)) == 0


def test_relocation_passages_read_change_records_findings_and_lists(tmp_path: Path) -> None:
    story = tmp_path / "manuscript-story"
    _record(story, "Results", "Old **text** <!-- @rev A1 -->here.", None)
    (story / "findings.json").write_text(json.dumps({"skill": "manuscript-story", "findings": [], "changes": [
        {"id": "ST-C1", "before": "A proposed   before.", "after": "A proposed after."}]}), encoding="utf-8")
    (story / "report.md").write_text("A report that quotes everything.\n", encoding="utf-8")  # not a change record
    listed = tmp_path / "passages.yaml"
    listed.write_text(yaml.safe_dump([{"passage": "One listed passage."}]), encoding="utf-8")
    passages = guard.relocation_passages([story, listed, tmp_path / "missing"])
    assert sorted(passages) == ["a proposed after.", "a proposed before.", "old **text** here.",
                                "one listed passage."]


SAID_TWICE = ("# Paper\n\n## Abstract\n\nWe annotate genomes offline.{abstract}\n\n## Results\n\n"
              "Annotation took one minute per genome.{results} The run used one laptop.\n\n"
              "All annotation results come from experiments in mice and human cell lines.\n")


@pytest.mark.parametrize("where, passes", [("results", True), ("abstract", False)])
def test_a_repeated_caveat_sentence_may_go_only_where_its_section_still_states_it(where: str, passes: bool) -> None:
    repeat = " The annotation results come from experiments in mice."
    before = SAID_TWICE.format(abstract=repeat if where == "abstract" else "",
                               results=repeat if where == "results" else "")
    after = SAID_TWICE.format(abstract="", results="")
    report = guard.compare(before, after, relocated=True)
    scope = _of(report, "scope")
    assert [c["change"] for c in scope] == ["removed"]
    assert scope[0]["severity"] == ("warning" if passes else "protected")
    if passes:
        assert scope[0]["note"].startswith("The same section still states it, in the Results")
    assert guard.exit_code(report) == (0 if passes else 1)
    assert guard.exit_code(guard.compare(before, after)) == 1  # without --relocated a deleted scope is protected


def test_a_story_deletion_counts_as_its_own_after_an_earlier_stage_reworded_the_sentence(tmp_path: Path) -> None:
    """The story stage records the working copy's wording, which the prose edit may already have changed; the final
    check compares the original, so a sentence with most of its words in a story record lies inside it."""
    before = SAID_TWICE.format(abstract="", results=" The annotation results come from experiments in mice.")
    after = SAID_TWICE.format(abstract="", results="")
    story = tmp_path / "manuscript-story"
    _record(story, "Results", "The annotation results came from experiments in mice.", None)
    assert _final_gate(tmp_path, before, after, story) == 0
    elsewhere = tmp_path / "manuscript-other"
    _record(elsewhere, "Results", "Memory use stayed below two gigabytes on every run.", None)
    assert _final_gate(tmp_path, before, after, elsewhere) == 1


# --- headlines ----------------------------------------------------------------------------------------------------

PARAGRAPH = ("# Paper\n\n## Results\n\n{headline}On the four genomes, local annotation took 33 s against 180 s with "
             "VEP. It was faster on every genome (Table 2).\n\n## Discussion\n\nWe discuss speed.\n")


@pytest.mark.parametrize("headline, passes", [
    ("The benchmarks show that local annotation was faster than VEP. ", True),
    ("The benchmarks show that local annotation was faster than VEP on 4 genomes. ", False),  # a number it lacks
    ("The benchmarks show that local annotation causes faster results than VEP. ", False),  # a stronger relation
    ("The benchmarks prove that local annotation was faster than VEP. ", False),  # more certainty than it has
    ("The benchmarks show that local annotation was faster than all tools, VEP included. ", False),  # "all"
    ("The benchmarks show that local annotation was faster than VEP and ANNOVAR. ", False),  # a term it lacks
])
def test_a_headline_that_restates_its_paragraph_is_a_warning(headline: str, passes: bool) -> None:
    before, after = PARAGRAPH.format(headline=""), PARAGRAPH.format(headline=headline)
    plain = guard.compare(before, after)
    report = guard.compare(before, after, relocated=True)
    assert guard.exit_code(report) == (0 if passes else 1), report["sentence_changes"]
    if passes:
        assert guard.exit_code(plain) == 1  # without --relocated a new claim is protected
        assert any(c["note"].startswith("A headline for the result") for c in report["sentence_changes"])
        assert guard.exit_code(guard.compare(before, after, relocated=True, revision=True, authorised=[])) == 0


def test_a_headline_in_a_paragraph_of_its_own_stays_a_new_claim() -> None:
    before = PARAGRAPH.format(headline="")
    after = before.replace("## Results\n\n", "## Results\n\nThe benchmarks show that local annotation was faster "
                                               "than VEP.\n\n")
    assert guard.exit_code(guard.compare(before, after, relocated=True)) == 1


def test_a_number_moved_to_another_section_stays_protected() -> None:
    before = ("# P\n\n## Results\n\nAnnotation took 33 s per genome on a laptop and kept every file local. Memory "
              "stayed low.\n\n## Discussion\n\nSpeed matters to users. It is quick.\n")
    after = ("# P\n\n## Results\n\nAnnotation kept every file local on a laptop. Memory stayed low.\n\n"
             "## Discussion\n\nSpeed matters to users. Each genome took 33 s on a laptop, which is quick.\n")
    report = guard.compare(before, after, relocated=True)
    assert {(c["change"], c["severity"]) for c in _of(report, "number")} == {("removed", "protected"),
                                                                            ("added", "protected")}


# --- stock phrases, paragraph-local terms, reference builds, LaTeX abstracts ----------------------------------------

def test_a_deleted_sentence_that_only_opens_with_a_stock_phrase_is_listed() -> None:
    kept = "Telomeres shorten with age in this cohort."
    real = "For the purpose of reproducibility, all code and containers are archived alongside the manuscript."
    report = guard.compare(f"{kept} {real}\n", f"{kept}\n")
    [cut] = report["sentence_changes"]
    assert (cut["kind"], cut["change"], cut["severity"]) == ("sentence", "removed", "warning")
    assert cut["note"].startswith("It was cut as a stock phrase (“For the purpose of”)")
    assert guard.exit_code(report) == 0
    assert "cut as a stock phrase" in guard.to_markdown(report)
    filler = "In conclusion, these findings matter."
    assert guard.compare(f"{kept} {filler}\n", f"{kept}\n")["sentence_changes"] == []


def test_a_pronoun_given_its_noun_does_not_change_the_term_counts() -> None:
    before = "# P\n\n## Methods\n\nWe compared our tool with VEP. It needed a server.\n\nThe run took a day.\n"
    after = before.replace("It needed a server.", "VEP needed a server.")
    report = guard.compare(before, after)
    assert report["protected"] == {} and guard.exit_code(report) == 0
    assert report["repeated_in_paragraph"] == {"terms": {"VEP": 1}}
    assert "added again in a paragraph that already had it" in guard.to_markdown(report)
    elsewhere = before.replace("The run took a day.", "The VEP run took a day.")  # a paragraph that lacked it
    assert guard.compare(before, elsewhere)["protected"]["terms"]["added"] == {"VEP": 1}


def test_a_reference_build_is_a_scope_qualifier() -> None:
    before = "# P\n\n## Results\n\nScores were computed on GRCh38 for 120 genomes.\n"
    after = "# P\n\n## Results\n\nScores were computed for 120 genomes.\n"
    scope = _of(guard.compare(before, after), "scope")
    assert [(c["removed"], c["severity"]) for c in scope] == [(["GRCh38"], "protected")]
    assert guard._scope_keys("lifted over from hg38") == [("build:grch38", "hg38")]


def test_a_latex_abstract_environment_is_the_abstract() -> None:
    tex = ("\\documentclass{article}\n\\begin{document}\n\\begin{abstract}\nIn mice, Foo reduces growth.\n"
           "\\end{abstract}\n\\section{Results}\nGrowth fell.\n\\end{document}\n")
    sections = [(s.text, s.section) for s in guard.segment(tex)]
    assert sections == [("In mice, Foo reduces growth.", "Abstract"), ("Growth fell.", "Results")]


def test_the_inventory_counts_its_changes_in_words() -> None:
    report = guard.compare("# P\n\nOne sentence here.\n", "# P\n\nOne sentence here. A new one.\n", revision=True)
    assert "The comparison lists one change, sentence by sentence; check it" in guard.to_markdown(report)


# --- requested changes: a referee comment id -------------------------------------------------------------------------

def test_a_referee_comment_id_says_what_asked_for_a_change_and_a_question_does_not() -> None:
    [entry] = guard.parse_authorisations([{"passage": "lower TERT expression limits repair", "comment": "R2.4"}])
    assert entry["findings"] == ["R2.4"]
    with pytest.raises(ValueError, match="what asked for the change"):
        guard.parse_authorisations([{"before": "lower TERT expression limits repair", "after": "lower TERT limits",
                                     "comment": "Which cohort is meant here?"}])


# --- declarations only the authors can make ------------------------------------------------------------------------

DECLARED = ("# Paper\n\n## Results\n\nThe annotation took a minute.\n\n## Ethics\n\nThe genome is published by its "
            "owner under CC0.\n\n## Competing interests\n\nA.K. is a co-founder of Example Ltd. B.L. declares no "
            "competing interests.\n\n## Author contributions\n\nL.Z. wrote the software and performed the annotation "
            "and benchmarking. A.K. supervised the work.\n")


@pytest.mark.parametrize("old, new, change", [
    # the v0.3 run invented a consent statement
    ("The genome is published by its owner under CC0.",
     "The genome is published by its owner under CC0. Written informed consent for publication of his genome data "
     "was obtained from A.K.", "added"),
    # ... wrote a blanket competing-interests declaration for every author
    ("A.K. is a co-founder of Example Ltd. B.L. declares no competing interests.",
     "The authors declare no competing interests.", "changed"),
    # ... and dropped part of a co-author's credit
    ("performed the annotation and benchmarking.", "performed the annotation.", "changed"),
])
def test_a_declaration_the_run_writes_or_changes_is_protected(tmp_path: Path, old: str, new: str, change: str) -> None:
    after = DECLARED.replace(old, new)
    report = guard.compare(DECLARED, after)
    declared = _of(report, "declaration")
    assert declared and {c["severity"] for c in declared} == {"protected"} and change in {c["change"] for c in declared}
    assert guard.exit_code(report) == 1
    assert "a declaration only the authors can make" in guard.to_markdown(report)
    # in a revision inventory it fails only against the list of requested changes, and an entry covers it
    assert guard.exit_code(guard.compare(DECLARED, after, revision=True)) == 0
    assert _final_gate(tmp_path, DECLARED, after, tmp_path / "no-story-run") == 1
    passage = " ".join(new.split()[-6:])
    assert _final_gate(tmp_path, DECLARED, after, tmp_path / "no-story-run",
                       [{"passage": passage, "finding": "authors' request"}]) == 0
    if change == "changed" and "benchmarking" in old:
        assert declared[0]["removed"] == ["benchmarking"]


def test_a_dropped_declaration_and_a_respelled_one() -> None:
    dropped = DECLARED.replace(" A.K. supervised the work.", "")
    assert [c["change"] for c in _of(guard.compare(DECLARED, dropped), "declaration")] == ["removed"]
    typo = DECLARED.replace("owner under CC0.", "owner under CC0. Fundng was recieved from the DFG.")
    fixed = typo.replace("Fundng was recieved", "Funding was received")
    assert _of(guard.compare(typo, fixed), "declaration") == []
    plain = DECLARED.replace("The annotation took a minute.", "Annotation took one minute.")
    assert _of(guard.compare(DECLARED, plain), "declaration") == []


def test_a_heading_or_methods_sentence_that_only_sounds_like_a_declaration_is_edited_freely() -> None:
    before = ("# P\n\n## Results\n\n### Contribution of rare variants\n\nRare variants explained a small share of "
              "the risk.\n\n## Methods\n\nWe designed the study as a comparison of two cohorts.\n")
    after = before.replace("a small share", "a modest share").replace("as a comparison of", "to compare")
    assert _of(guard.compare(before, after), "declaration") == []


def test_allow_strengthening_never_covers_a_declaration() -> None:
    after = DECLARED.replace("B.L. declares no competing interests.", "B.L. and C.M. declare no competing interests.")
    report = guard.compare(DECLARED, after, allow_strengthening=True)
    assert guard.exit_code(report) == 1 and not any(c["authorised"] for c in _of(report, "declaration"))


# --- the smell check: clusters only where the edit added a use; kept patterns scoped and recorded --------------------

CONNECTED = ("# Paper\n\n## Results\n\nMoreover, the tool annotated thirty genomes in a minute each on the laptop. "
             "Furthermore, it kept every file on that machine during the whole run. Moreover, the scores matched "
             "the reference implementation on every genome we tried.\n\n## Discussion\n\nThe tool is fast enough "
             "for routine use on an ordinary laptop computer in the lab.\n")


LONG_CONNECTED = ("Additionally, it ran offline on the laptop because no network access was needed for any of the "
                  "annotation steps.")


def _doc(text: str) -> dict:
    return profile.profile_text(text, False, profile.load_smells(), profile.load_kobak())


def test_an_edit_is_not_failed_for_a_cluster_the_draft_already_had() -> None:
    edited = CONNECTED.replace("thirty genomes", "30 genomes")
    result = profile.run_check(_doc(edited), _doc(CONNECTED), set())
    assert result["passed"] and result["clusters"] == []
    assert [(c["id"], c["count"]) for c in result["existing_clusters"]] == [("C5", 3)]
    md = profile.check_markdown(result, profile.load_smells(), compared=True)
    assert "the deslop stage's work" in md
    assert "offer one:" in md and "- Sentence-initial connector piles (C5), 3 times in" in md
    added =CONNECTED.replace("Moreover, the scores", "Moreover, the scores also").replace(
        "every genome we tried.", "every genome we tried. " + LONG_CONNECTED)
    judged = profile.run_check(_doc(added), _doc(CONNECTED), set())
    assert not judged["passed"] and [(c["id"], c["count"]) for c in judged["clusters"]] == [("C5", 4)]
    assert profile.run_check(_doc(CONNECTED), None, set())["clusters"]  # without --before, every heading is judged


@pytest.mark.parametrize("keep, section, kept", [
    ({"C5"}, "Results", True),
    ({"C5@Results"}, "Results", True),
    ({"C5@results"}, "Results > Speed", True),  # a heading covers its subsections
    ({"C5@Results > Speed"}, "Results > Speed", True),
    ({"C5@Discussion"}, "5. Discussion > 5.1 Limits", True),  # the title without its number
    ({"C5@5.1 Limits"}, "5. Discussion > 5.1 Limits", True),
    ({"C5@Discussion"}, "Results", False),
    ({"C1@Results"}, "Results", False),
])
def test_a_kept_pattern_can_be_scoped_to_a_heading(keep: set[str], section: str, kept: bool) -> None:
    assert profile.is_kept("C5", section, {profile.normalise_keep(k) for k in keep}) is kept


def test_kept_patterns_are_recorded_by_a_stage_and_read_back_by_the_final_check(tmp_path: Path) -> None:
    before, after = tmp_path / "before.md", tmp_path / "after.md"
    before.write_text(CONNECTED, encoding="utf-8")
    after.write_text(CONNECTED.replace("every genome we tried.", "every genome we tried. " + LONG_CONNECTED),
                     encoding="utf-8")
    base = [str(after), "--before", str(before), "--check"]
    assert runner.invoke(profile.app, base).exit_code == 1
    assert runner.invoke(profile.app, [*base, "--keep", "C5@Discussion"]).exit_code == 1  # kept elsewhere only
    record = tmp_path / "RUN" / "manuscript-prose-edit" / "kept-patterns.txt"
    kept = runner.invoke(profile.app, [*base, "--keep", "c5@Results", "--record-keeps", str(record)])
    assert kept.exit_code == 0, kept.output
    assert "C5@Results" in record.read_text(encoding="utf-8").splitlines()
    runner.invoke(profile.app, [*base, "--keep", "c5@Results", "--record-keeps", str(record)])
    assert record.read_text(encoding="utf-8").count("C5@Results") == 1  # recorded once
    final = runner.invoke(profile.app, [*base, "--keep-file", str(tmp_path / "RUN"),
                                        "--keep-file", str(tmp_path / "missing")])
    assert final.exit_code == 0, final.output
    assert profile.read_keeps([record]) == {"C5@Results"}


def test_the_verdict_names_a_pattern_as_the_catalogue_heading_does() -> None:
    assert profile._pattern("C1", profile.load_smells()) == "negative parallelism"
    assert profile._pattern("A1", profile.load_smells()) == "significance inflation"


# --- detectors and the editing skills' texts -------------------------------------------------------------------------

def test_a_hosted_detector_needs_the_authors_consent_not_a_written_promise() -> None:
    why = setup.DETECTORS["aiornot"]["why"]
    assert "authors agree" in why and "written confirmation" not in why


def test_detector_false_positive_figures_agree_with_their_source() -> None:
    apis = (SKILLS / "manuscript-prose-edit" / "references" / "detector-apis.md").read_text(encoding="utf-8")
    evidence = (SKILLS / "manuscript-prose-edit" / "references" / "detector-evidence.md").read_text(encoding="utf-8")
    for text in (apis, evidence):
        assert "0.1%" in text and "0.0%" in text and "Table 18" in text
    assert "go to the critic" not in apis and "never to the critic" in apis


@pytest.mark.parametrize("rel, absent, present", [
    ("manuscript-story/SKILL.md", ["turned into a decision", "narrative structure"],
     ["uv run --script ../manuscript-prose-edit/scripts/guard.py", "uv run --script ../manuscript-deslop/scripts/style_profile.py",
      "runs.py change", "`ST` prefix", "end-of-stage checklist"]),
    ("manuscript-prose-edit/SKILL.md", ["always exits 0", "Lowered claims and moved tokens are warnings",
                                        "in a critic pass"],
     ["runs.py change", "`PE` prefix", "end-of-stage checklist", "--relocated-in", "at least three\nwords in a row"]),
    ("manuscript-deslop/SKILL.md", [], ["The prose edit's smell check only keeps its own edits from adding patterns",
                                        "`DS` prefix", "end-of-stage checklist"]),
    ("manuscript-story/references/story-contract.md", ['ask for it under "Fix now"'], ['"Then the writing"']),
    ("manuscript-story/references/comparisons.md", ["ask once, if none are named"], ["Search before asking"]),
    ("manuscript-prose-edit/references/prose-edit-contract.md", ["a direct comparison\nagainst `claim-ladders.md` is sufficient"],
     ["A pasted passage gets the same two checks"]),
])
def test_the_editing_skills_say_what_the_scripts_do(rel: str, absent: list[str], present: list[str]) -> None:
    text = (SKILLS / rel).read_text(encoding="utf-8")
    flat = " ".join(text.split())
    for phrase in absent:
        assert " ".join(phrase.split()) not in flat, (rel, phrase)
    for phrase in present:
        assert " ".join(phrase.split()) in flat, (rel, phrase)


@pytest.mark.parametrize("script", [
    "manuscript-prose-edit/scripts/guard.py", "manuscript-prose-edit/scripts/detect.py",
    "manuscript-prose-edit/scripts/detector_setup.py", "manuscript-deslop/scripts/style_profile.py",
    "manuscript-story/scripts/reader_metrics.py",
])
def test_the_editing_scripts_read_write_and_print_utf8(script: str) -> None:
    code = (SKILLS / script).read_text(encoding="utf-8")
    calls = [node for node in ast.walk(ast.parse(code)) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr in ("read_text", "write_text", "open", "run")]
    for call in calls:
        keywords = {k.arg for k in call.keywords}
        if call.func.attr == "run" and "text" not in keywords:
            continue  # subprocess.run without text=True reads bytes
        if isinstance(call.func.value, ast.Name) and call.func.value.id == "webbrowser":
            continue
        assert "encoding" in keywords, (script, call.lineno)
    assert 'reconfigure(encoding="utf-8", errors="replace")' in code, script
