"""Offline tests for manuscript-reviewer-response/scripts/check_response.py. Run with `uv run pytest`.

The fixtures are the behavioural-eval fixtures: a two-referee decision letter, a review ledger, an original
and a revised manuscript, a clean response letter and a seeded copy with six planted defects.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
FIX = ROOT / "evals" / "fixtures" / "manuscript-reviewer-response"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cr = _load("check_response", SKILLS / "manuscript-reviewer-response" / "scripts" / "check_response.py")

REVIEWS = FIX / "reviews-r1.txt"
LEDGER = FIX / "review-ledger.yaml"
LEDGER_SEEDED = FIX / "review-ledger-seeded.yaml"
CLEAN = FIX / "response-clean.md"
SEEDED = FIX / "response-seeded.md"
V1, V2, V2_SEEDED = FIX / "paper-v1.md", FIX / "paper-v2.md", FIX / "paper-v2-seeded.md"

# What response-seeded.md and review-ledger-seeded.yaml plant, one defect per item.
PLANTED = {
    ("QUOTE_NOT_VERBATIM", "R1.2"),        # the comment is paraphrased
    ("ORDER_MISMATCH", "R1.4a"),           # R1.4b is answered before R1.4a
    ("MISSING_REPLY", "R2.P4"),            # no reply at all
    ("PROMISE_NOT_LANDED", "R2.P1"),       # the ledger says promised; the letter says "we will add"
    ("NUMBER_NOT_IN_MANUSCRIPT", "R1.1"),  # 98.6% in the reply, 97.9% in the manuscript
    ("BLANKET_REPLY", "R1.4b"),            # "We have revised the manuscript accordingly."
}


def _run(letter: Path = CLEAN, ledger: Path = LEDGER, **kw: object) -> "cr.Report":
    kw.setdefault("revised", V2)
    kw.setdefault("original", V1)
    return cr.run(REVIEWS, ledger, letter, **kw)


def _codes(report: "cr.Report") -> list[tuple[str, str]]:
    return [(f.code, f.item) for f in report.findings]


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------------------------------------
# Seeded fixture and clean control
# --------------------------------------------------------------------------------------------------------

def test_clean_control_has_no_finding_and_every_check_ran() -> None:
    report = _run()
    assert report.findings == []
    assert report.items == report.blocks == 12
    states = {c["check"]: c["state"] for c in report.checks}
    assert {k for k, v in states.items() if v != "pass"} == {"guard"}  # no --guard-json given
    assert states["guard"] == "not_assessed"


def test_each_planted_defect_is_found_once_at_its_item_and_nothing_else() -> None:
    report = _run(SEEDED, LEDGER_SEEDED)
    found = _codes(report)
    assert set(found) == PLANTED
    assert len(found) == len(PLANTED)  # each once: no duplicate or consequential finding
    blocking = {(f.code, f.item) for f in report.findings if f.blocking}
    assert blocking == PLANTED - {("NUMBER_NOT_IN_MANUSCRIPT", "R1.1")}
    hint = next(f.message for f in report.findings if f.code == "QUOTE_NOT_VERBATIM")
    assert "report the spread across runs" in hint  # points at the comment the paraphrase replaced


def test_planted_findings_point_at_the_letter_lines_of_their_blocks() -> None:
    text = SEEDED.read_text(encoding="utf-8").splitlines()
    report = _run(SEEDED, LEDGER_SEEDED)
    for f in report.findings:
        if f.line is None:
            assert f.code in {"MISSING_REPLY", "PROMISE_NOT_LANDED"}
            continue
        # the reported line is the item's tag, or its quoted comment just below the tag
        window = "\n".join(text[max(0, f.line - 2):f.line])
        assert f"item: {f.item}" in window, (f, window)


def test_clean_letter_against_a_revision_that_lacks_the_changes() -> None:
    """The letter claims ranges and a revised sentence that paper-v2-seeded.md does not contain."""
    report = _run(revised=V2_SEEDED)
    assert set(_codes(report)) == {("REVISED_QUOTE_NOT_FOUND", "R1.3a"), ("NUMBER_NOT_IN_MANUSCRIPT", "R1.2"),
                                   ("NUMBER_NOT_IN_MANUSCRIPT", "R2.P1")}
    numbers = {f.item: [d["number"] for d in f.details] for f in report.findings
               if f.code == "NUMBER_NOT_IN_MANUSCRIPT"}
    assert {"9.6", "10.1"} <= set(numbers["R1.2"])
    assert "12.3" in numbers["R2.P1"] and "12.6" not in numbers["R2.P1"]  # 12.6 is in the revised manuscript


def test_tags_are_optional_when_quotes_are_verbatim(tmp_path: Path) -> None:
    untagged = re.sub(r"<!-- item: [^>]+ -->\n", "", CLEAN.read_text(encoding="utf-8"))
    assert "<!--" not in untagged
    report = _run(_write(tmp_path, "untagged.md", untagged))
    assert report.findings == []
    assert [row["item"] for row in report.reply_map] == [it.id for it in cr.load_ledger(LEDGER)[0].items]


# --------------------------------------------------------------------------------------------------------
# Quotes, coverage and order
# --------------------------------------------------------------------------------------------------------

def test_typography_and_pdf_hyphenation_do_not_count_as_changed_words(tmp_path: Path) -> None:
    reviews = _write(tmp_path, "r.txt", "Reviewer 1\n\n1. Please add a long-\nread genome; the \u201cbench\u00admark\u201d is "
                                        "narrow.\n")
    ledger = _write(tmp_path, "l.yaml", "items:\n  - id: R1.1\n    comment: Please add a long-read genome\n"
                                        "    decision: address\n    evidence: [answer]\n")
    good = _write(tmp_path, "good.md", "<!-- item: R1.1 -->\n> 1. Please add a long-read genome; the \"benchmark\"\u00a0is "
                                       "narrow.\n\nDone, see Table 1.\n")
    bad = _write(tmp_path, "bad.md", "<!-- item: R1.1 -->\n> 1. Please add a short-read genome; the \"benchmark\" is "
                                     "narrow.\n\nDone, see Table 1.\n")
    assert not [f for f in cr.run(reviews, ledger, good).findings if f.code.startswith("QUOTE")]
    assert [f.code for f in cr.run(reviews, ledger, bad).findings if f.code.startswith("QUOTE")] == [
        "QUOTE_NOT_VERBATIM"]


def test_an_elided_quote_is_advisory_and_a_wrong_segment_is_not_verbatim(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8")
    full = ("> 1. The benchmark compares VarLens only with its own previous release. The authors should compare "
            "runtime\n> and concordance with at least one widely used annotator, such as VEP, on the same genomes.")
    assert full in text
    elided = text.replace(full, "> 1. The benchmark compares VarLens only with its own previous release. [...] "
                                "such as VEP, on the same genomes.")
    elided_path = _write(tmp_path, "e.md", elided)
    report = _run(elided_path)
    assert [(f.code, f.item, f.blocking) for f in report.findings] == [("QUOTE_ELIDED", "R1.1", True)]
    rebuttal = cr.run(REVIEWS, LEDGER, elided_path, mode="rebuttal")
    assert [(f.code, f.item, f.blocking) for f in rebuttal.findings] == [("QUOTE_ELIDED", "R1.1", False)]
    untagged = elided_path.read_text(encoding="utf-8").replace("<!-- item: R1.1 -->\n", "")
    assert _codes(_run(_write(tmp_path, "u.md", untagged))) == [("QUOTE_ELIDED", "R1.1")]
    wrong = text.replace(full, "> 1. The benchmark compares VarLens only with its own previous release. [...] "
                               "such as ANNOVAR, on the same genomes.")
    assert ("QUOTE_NOT_VERBATIM", "R1.1") in _codes(_run(_write(tmp_path, "w.md", wrong)))


def test_a_letter_without_reply_blocks_is_one_root_cause(tmp_path: Path) -> None:
    letter = _write(tmp_path, "empty.md", "# Response\n\nWe thank the reviewers and have revised the paper.\n")
    report = _run(letter)
    assert _codes(report) == [("NO_REPLY_BLOCKS", "letter")]


def test_duplicate_orphan_and_merged_replies(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8")
    # a second block for R1.4a, an orphan tag, and R2.P2a and R2.P2b answered in one untagged block
    dup = "<!-- item: R1.4a -->\n> a) The Abstract gives the memory of the laptop but not the number of cores.\n\nSee " \
          "the Abstract, line 5.\n\n<!-- item: R9.9 -->\n> Something.\n\nAnswered. (Abstract, line 5)\n\n"
    text = text.replace("<!-- item: R1.4b -->", dup + "<!-- item: R1.4b -->")
    start, end = text.index("<!-- item: R2.P2a -->"), text.index("<!-- item: R2.P3 -->")
    merged = ("> The authors also annotate the genome of one of the authors. Was ethics approval obtained for this?\n"
              "> Did the author consent to the publication of their genome?\n\nNo approval was obtained, and the "
              "author consented. (Methods, \"Demonstration genome\", lines 38-40)\n\n")
    text = text[:start] + merged + text[end:]
    found = _codes(_run(_write(tmp_path, "d.md", text)))
    assert ("DUPLICATE_REPLY", "R1.4a") in found
    assert ("ORPHAN_REPLY", "R9.9") in found
    assert ("MERGED_REPLY", "R2.P2b") in found
    assert ("MISSING_REPLY", "R2.P2b") not in found and ("MISSING_REPLY", "R2.P2a") not in found


def test_a_block_moved_far_up_is_the_only_one_reported_out_of_order(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8")
    start, end = text.index("<!-- item: R2.P3 -->"), text.index("<!-- item: R2.P4 -->")
    block = text[start:end]
    text = text[:start] + text[end:]
    text = text.replace("<!-- item: R1.1 -->", block + "<!-- item: R1.1 -->")
    assert [c for c in _codes(_run(_write(tmp_path, "m.md", text))) if c[0] == "ORDER_MISMATCH"] == [
        ("ORDER_MISMATCH", "R2.P3")]


# --------------------------------------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, message", [
    ("items: [", "not valid YAML"),
    ("- just\n- a list\n", "must be a mapping"),
    ("rounds: []\n", "non-empty list"),
    ("items:\n  - id: R1.1\n    decision: address\n", "no `comment:`"),
    ("items:\n  - id: R1.1\n    comment: a\n  - id: R1.1\n    comment: b\n", "duplicate id"),
    ("items:\n  - id: R1.1\n    comment: a\n    decision: adress\n", "is not one of"),
    ("items:\n  - id: 'bad id'\n    comment: a\n", "unusable id"),
])
def test_malformed_ledgers_are_input_errors(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(cr.InputError, match=re.escape(message)):
        cr.load_ledger(_write(tmp_path, "l.yaml", text))


def test_missing_decisions_and_reasons_block_and_are_never_inferred(tmp_path: Path) -> None:
    text = LEDGER.read_text(encoding="utf-8")
    text = text.replace("        decision: address\n        commitments:\n          - change: Add 8 cores",
                        "        commitments:\n          - change: Add 8 cores", 1)
    text = re.sub(r"(        decision: decline\n)        reason: >-\n(?:          .*\n)+", r"\1", text, count=1)
    report = _run(ledger=_write(tmp_path, "l.yaml", text))
    assert {(f.code, f.item) for f in report.findings if f.blocking} == {("DECISION_MISSING", "R1.4a"),
                                                                       ("REASON_MISSING", "R2.P3")}
    assert next(it for it in cr.load_ledger(tmp_path / "l.yaml")[0].items if it.id == "R1.4a").decision == "undecided"


def test_a_ledger_comment_out_of_order_or_not_verbatim(tmp_path: Path) -> None:
    text = LEDGER.read_text(encoding="utf-8")
    text = text.replace("comment: Please state the version of the module tables used in the benchmark.",
                        "comment: Please state which module tables were used.")
    report = _run(ledger=_write(tmp_path, "l.yaml", text))
    assert [c for c in _codes(report) if c[0].startswith("LEDGER")] == [("LEDGER_COMMENT_NOT_VERBATIM", "R1.4b")]

    raw = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    entries = raw["rounds"][0]["items"]
    entries[1], entries[2] = entries[2], entries[1]  # R1.2 listed before R1.1
    report = _run(ledger=_write(tmp_path, "o.yaml", yaml.safe_dump(raw, sort_keys=False)))
    # the ledger's order is wrong, and the letter (in the referees' order) now disagrees with it at one item
    assert {c for c in _codes(report) if c[0] in {"LEDGER_ORDER", "ORDER_MISMATCH"}} == {
        ("LEDGER_ORDER", "R1.1"), ("ORDER_MISMATCH", "R1.2")}


# --------------------------------------------------------------------------------------------------------
# Locations, quoted revised text and numbers
# --------------------------------------------------------------------------------------------------------

def test_named_locations_must_exist(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8").replace("(Abstract, line 5)", "(Abstract, line 5; Table 9)")
    text = text.replace("(Code availability, lines 95-96)", "(Code availability, lines 950-960)")
    text = text.replace('(Methods, "Implementation",\nline 21)', '(Methods, "Software design", line 21)')
    report = _run(_write(tmp_path, "l.md", text))
    unresolved = {f.item: f.message for f in report.findings if f.code == "LOCATION_UNRESOLVED"}
    assert set(unresolved) == {"R1.4a", "Ed.P1", "R1.4b"}
    assert "Table 9" in unresolved["R1.4a"] and "950-960" in unresolved["Ed.P1"]
    assert "Software design" in unresolved["R1.4b"]
    off = _run(_write(tmp_path, "l2.md", text), line_check=False)
    assert {f.item for f in off.findings if f.code == "LOCATION_UNRESOLVED"} == {"R1.4a", "R1.4b"}
    assert any("950-960" in n and "switched off" in n for n in off.not_assessed)


def test_a_landed_location_that_does_not_exist_blocks(tmp_path: Path) -> None:
    text = LEDGER.read_text(encoding="utf-8").replace("landed: Abstract, line 5", "landed: Abstract, line 5; Table 7")
    assert _codes(_run(ledger=_write(tmp_path, "l.yaml", text))) == [("LANDED_UNRESOLVED", "R1.4a")]


def test_quoting_the_original_wording_as_if_revised_is_caught(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8")
    old_sentence = "The concordance with the previous release suggests that the rewrite did not change results."
    stale = text.replace("(Abstract, line 5)", f'(Abstract, line 5). The Discussion now reads: "{old_sentence}"')
    found = [f for f in _run(_write(tmp_path, "s.md", stale)).findings if f.code == "REVISED_QUOTE_NOT_FOUND"]
    assert [(f.item, f.blocking) for f in found] == [("R1.4a", True)]
    assert "original wording" in found[0].message
    replaced = text.replace("(Abstract, line 5)", f'(Abstract, line 5). We replaced "{old_sentence}"')
    assert _run(_write(tmp_path, "r.md", replaced)).findings == []


def test_a_quote_outside_the_cited_lines_is_a_location_mismatch(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8").replace("lines 73-74;\nDiscussion, lines 88-89)",
                                                     "lines 73-74;\nDiscussion, lines 90-91)")
    report = _run(_write(tmp_path, "q.md", text))
    assert _codes(report) == [("LOCATION_MISMATCH", "R1.3a")]
    assert "88-89" in report.findings[0].message and "90-91" in report.findings[0].message


def test_numbers_in_locations_labels_and_citations_are_not_results(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8").replace(
        "(Abstract, line 5)", "(Abstract, line 5; as in our reply to Reviewer 2, comment 3 and R2.P3; Smith et al., "
                              "2020; see Section 4.1; https://example.org/x/77)")
    assert not [f for f in _run(_write(tmp_path, "n.md", text)).findings if f.code == "NUMBER_NOT_IN_MANUSCRIPT"]


def test_a_placeholder_blocks_and_its_numbers_are_not_checked(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8").replace("(Abstract, line 5)",
                                                     "(Abstract, line 5) [TBD: runtime on 64 cores]")
    assert _codes(_run(_write(tmp_path, "t.md", text))) == [("TBD_OPEN", "R1.4a")]


def test_printed_line_numbers_from_a_pdf_export_are_used(tmp_path: Path) -> None:
    lines = V2.read_text(encoding="utf-8").splitlines()
    printed = "\n".join(f"{i + 101} {line}" if line.strip() else "" for i, line in enumerate(lines))
    revised = _write(tmp_path, "revised.txt", printed)
    doc = cr.load_doc(revised)
    assert doc.printed and doc.min_line >= 101
    shifted = re.sub(r"\b(lines?) (\d+)(?:-(\d+))?",
                     lambda m: f"{m.group(1)} {int(m.group(2)) + 100}" + (f"-{int(m.group(3)) + 100}" if m.group(3) else ""),
                     CLEAN.read_text(encoding="utf-8"))
    led = re.sub(r"\b(lines?) (\d+)(?:-(\d+))?",
                 lambda m: f"{m.group(1)} {int(m.group(2)) + 100}" + (f"-{int(m.group(3)) + 100}" if m.group(3) else ""),
                 LEDGER.read_text(encoding="utf-8"))
    report = cr.run(REVIEWS, _write(tmp_path, "l.yaml", led), _write(tmp_path, "r.md", shifted), revised=revised)
    assert report.line_numbering == "printed line numbers"
    assert report.findings == []
    file_lines = cr.run(REVIEWS, LEDGER, CLEAN, revised=revised)
    assert {f.code for f in file_lines.findings} >= {"LOCATION_UNRESOLVED"}


def test_latex_tables_resolve_by_environment_count(tmp_path: Path) -> None:
    tex = _write(tmp_path, "p.tex", "\\section{Results}\n\\begin{table}\\caption{A}\\end{table}\n"
                                    "\\begin{table*}\\caption{B}\\end{table*}\n")
    doc = cr.load_doc(tex)
    states = {}
    for text in ("Table 2", "Table 3", "Results", "Discussion"):
        loc = cr.extract_locations(text)[0]
        cr.resolve(loc, doc, [], True)
        states[text] = loc.state
    assert states == {"Table 2": "resolved", "Table 3": "unresolved", "Results": "resolved",
                      "Discussion": "unresolved"}


# --------------------------------------------------------------------------------------------------------
# Modes, rounds and guard.py
# --------------------------------------------------------------------------------------------------------

def test_rebuttal_mode_allows_promises_and_reports_unchecked_locations() -> None:
    report = cr.run(REVIEWS, LEDGER_SEEDED, CLEAN, mode="rebuttal")
    assert [(f.code, f.item, f.blocking) for f in report.findings] == [("PROMISED", "R2.P1", False)]
    states = {c["check"]: c["state"] for c in report.checks}
    assert states["locations_resolve"] == states["numbers"] == states["revised_quotes"] == "not_assessed"
    journal = cr.run(REVIEWS, LEDGER_SEEDED, CLEAN)
    assert ("PROMISE_NOT_LANDED", "R2.P1") in _codes(journal)
    assert journal.not_assessed[0].startswith("No revised manuscript")


def test_character_limit_per_referee_section() -> None:
    report = cr.run(REVIEWS, LEDGER, CLEAN, mode="rebuttal", max_chars=1500)
    over = {f.item for f in report.findings if f.code == "OVER_LIMIT"}
    assert over == {"Reviewer 1", "Reviewer 2"}
    assert not [f for f in cr.run(REVIEWS, LEDGER, CLEAN, mode="rebuttal", max_chars=10_000).findings
                if f.code == "OVER_LIMIT"]


ROUND2_LETTER = """# Response, round 2

## Reviewer 2

<!-- item: R2.P1 -->
> Please add a genome from a third individual, sequenced on any platform, or limit the claims about
> generalisability in the Abstract and Discussion.

{reply}
"""


def _round2(tmp_path: Path, previous: str, reply: str, landed: str = "Table 1") -> "cr.Report":
    raw = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    raw["rounds"].append({"round": 2, "items": [{
        "id": "R2.P1", "referee": "Reviewer 2", "decision": "address", "previous": [previous],
        "comment": "Please add a genome from a third individual, sequenced on any platform, or limit the claims "
                   "about generalisability in the Abstract and Discussion.",
        "commitments": [{"change": "HG004", "landed": landed}]}]})
    ledger = _write(tmp_path, "l2.yaml", yaml.safe_dump(raw, sort_keys=False))
    letter = _write(tmp_path, "r2.md", ROUND2_LETTER.format(reply=reply))
    return cr.run(FIX / "reviews-r2.txt", ledger, letter, revised=V2)


def test_round_two_links_back_to_round_one(tmp_path: Path) -> None:
    good = _round2(tmp_path, "1:R2.P1", "In the first round we added a long-read callset of HG002. Table 1 now "
                                        "lists every genome. (Table 1)")
    assert good.findings == [] and good.round == 2
    assert {c["check"]: c["state"] for c in good.checks}["rounds"] == "pass"
    invented = _round2(tmp_path, "1:R2.P9", "In the first round we added HG002 HiFi. (Table 1)")
    assert _codes(invented) == [("ROUND_LINK_INVALID", "R2.P1")]
    silent = _round2(tmp_path, "1:R2.P1", "Table 1 now lists every genome. (Table 1)")
    assert _codes(silent) == [("NO_BACK_REFERENCE", "R2.P1")]


def test_an_earlier_round_promise_that_never_landed_blocks_the_next_round(tmp_path: Path) -> None:
    raw = yaml.safe_load(LEDGER_SEEDED.read_text(encoding="utf-8"))
    raw["rounds"].append({"round": 2, "items": [{
        "id": "R2.P1", "decision": "address", "previous": ["1:R2.P1"],
        "comment": "Please add a genome from a third individual, sequenced on any platform, or limit the claims "
                   "about generalisability in the Abstract and Discussion.",
        "commitments": [{"change": "HG004", "landed": "Table 1"}]}]})
    ledger = _write(tmp_path, "l.yaml", yaml.safe_dump(raw, sort_keys=False))
    letter = _write(tmp_path, "r.md", ROUND2_LETTER.format(reply="In the first round we added HG002. (Table 1)"))
    assert _codes(cr.run(FIX / "reviews-r2.txt", ledger, letter, revised=V2)) == [
        ("EARLIER_PROMISE_OPEN", "1:R2.P1")]
    with pytest.raises(cr.InputError, match="no round 3"):
        cr.run(FIX / "reviews-r2.txt", ledger, letter, revised=V2, round_number=3)


guard = _load("guard_for_reviewer_response", SKILLS / "manuscript-prose-edit" / "scripts" / "guard.py")


def test_guard_inventory_changes_are_reconciled_with_the_letters_locations(tmp_path: Path) -> None:
    inventory = guard.compare(V1.read_text(encoding="utf-8"), V2.read_text(encoding="utf-8"), revision=True)
    path = _write(tmp_path, "guard.json", json.dumps(inventory))
    clean = _run(guard_json=path)
    assert clean.findings == []
    assert {c["check"]: c["state"] for c in clean.checks}["guard"] == "pass"
    # without the summary sentence that names the Abstract, its new numbers sit where no reply points
    text = CLEAN.read_text(encoding="utf-8").replace(" The Abstract (lines 5-8) now reports the comparison\nwith VEP "
                                                     "and the long-read genome.", "")
    assert text != CLEAN.read_text(encoding="utf-8")
    report = _run(_write(tmp_path, "nosummary.md", text), guard_json=path)
    unmentioned = [f for f in report.findings if f.code == "UNMENTIONED_CHANGE"]
    assert unmentioned and all(not f.blocking for f in unmentioned)
    places = {(d["section"], d["line"]) for f in unmentioned for d in f.details}
    assert ("the Abstract", 7) in places
    assert not any(line == 5 for _, line in places)  # line 5 is cited by R1.4a
    assert ("In the Abstract (line 7 of the revised manuscript), the number \u201c12.6\u201d is new: "
            "\u201cA long-read genome took 12.6 minutes.\u201d") in cr.to_markdown(report)


def test_a_claim_that_widened_fails_even_where_a_reply_points(tmp_path: Path) -> None:
    """R1.3a's planted change: the challenged Discussion claim went from 'suggests' to 'shows'. Naming the place in
    a reply does not excuse it; a requested change (guard.py --authorised) does."""
    original, seeded = V1.read_text(encoding="utf-8"), V2_SEEDED.read_text(encoding="utf-8")
    path = _write(tmp_path, "guard.json", json.dumps(guard.compare(original, seeded, revision=True)))
    report = _run(revised=V2_SEEDED, guard_json=path)
    widened = [f for f in report.findings if f.code == "CLAIM_WIDENED"]
    assert len(widened) == 1 and widened[0].blocking and widened[0].stage == "now"
    assert [d["after"] for d in widened[0].details] == [
        "The concordance with the previous release shows that the rewrite did not change results."]
    assert ("  - In the Discussion (line 87 of the revised manuscript), the claim became stronger (“suggests” "
            "became “shows”)") in cr.to_markdown(report)
    # the same change, requested: the comparison marks it, and the letter check accepts it
    requested = guard.parse_authorisations([{"passage": "the rewrite did not change results", "finding": "R1.3a"}])
    path = _write(tmp_path, "guard-requested.json",
                  json.dumps(guard.compare(original, seeded, revision=True, authorised=requested)))
    assert not [f for f in _run(revised=V2_SEEDED, guard_json=path).findings if f.code == "CLAIM_WIDENED"]


def test_deleted_text_counts_as_mentioned_when_the_letter_cites_its_section(tmp_path: Path) -> None:
    """A deletion has no line in the revised manuscript; guard.py reports the rewritten Discussion limitation
    of paper-v1.md ("we tested only two genomes") that way, and the letter cites the Discussion lines that
    now carry it."""
    deleted = {"severity": "protected", "kind": "limitation", "change": "removed", "token": None,
               "before_line": 52, "after_line": None, "authorised": False,
               "section": "VarLens: fast annotation of personal genomes on a laptop > Discussion",
               "before": "A limitation is that we tested only two genomes.", "after": ""}
    path = _write(tmp_path, "guard.json", json.dumps({"protected": {}, "sentence_changes": [deleted]}))
    assert _run(guard_json=path).findings == []
    text = re.sub(r";?\s*Discussion, lines \d+-\d+", "", CLEAN.read_text(encoding="utf-8"))
    assert "Discussion, lines" not in text
    report = _run(_write(tmp_path, "nodisc.md", text), guard_json=path)
    found = [f for f in report.findings if f.code == "UNMENTIONED_CHANGE"]
    assert len(found) == 1 and len(found[0].details) == 1
    change = found[0].details[0]
    assert (change["section"], change["line"], change["original_line"], change["kind"]) == (
        "the Discussion", None, 52, "limitation")
    assert ("In the Discussion (a sentence deleted from line 52 of the original), a limiting statement was dropped: "
            "\u201cA limitation is that we tested only two genomes.\u201d") in cr.to_markdown(report)


def test_an_older_guard_report_is_reconciled_by_token(tmp_path: Path) -> None:
    report = {"protected": {"numbers": {"added": {"41.2": 1, "123.4": 1}, "removed": {}}}}
    path = _write(tmp_path, "g.json", json.dumps(report))
    found = [f for f in _run(guard_json=path).findings if f.code == "UNMENTIONED_CHANGE"]
    assert len(found) == 1 and "123.4" in found[0].message and "41.2" not in found[0].message


# --------------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------------

def test_cli_exit_codes_and_outputs(tmp_path: Path) -> None:
    runner = CliRunner()
    base = [str(REVIEWS), str(LEDGER), str(CLEAN), "--revised", str(V2), "--original", str(V1)]
    ok = runner.invoke(cr.app, [*base, "--json", str(tmp_path / "c.json"), "--md", str(tmp_path / "c.md")])
    assert ok.exit_code == 0, ok.output
    data = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert data["summary"]["blocking"] == 0 and {c["state"] for c in data["checks"]} <= {"pass", "not_assessed"}
    assert "A clean run is not a good letter" in (tmp_path / "c.md").read_text(encoding="utf-8")

    seeded = runner.invoke(cr.app, [str(REVIEWS), str(LEDGER_SEEDED), str(SEEDED), "--revised", str(V2)])
    assert seeded.exit_code == 1 and "which is not the referee's wording" in seeded.output
    assert "QUOTE_NOT_VERBATIM" not in seeded.output  # the codes stay in the JSON

    missing_text = runner.invoke(cr.app, [str(REVIEWS), str(LEDGER), str(CLEAN), "--revised", str(V2_SEEDED)])
    assert missing_text.exit_code == 1  # the quoted revised sentence is missing: blocking
    numbers_only = _write(tmp_path, "n.md", CLEAN.read_text(encoding="utf-8").replace("97.9%", "98.6%"))
    lenient = runner.invoke(cr.app, [str(REVIEWS), str(LEDGER), str(numbers_only), "--revised", str(V2)])
    strict = runner.invoke(cr.app, [str(REVIEWS), str(LEDGER), str(numbers_only), "--revised", str(V2), "--strict"])
    assert (lenient.exit_code, strict.exit_code) == (0, 1)

    broken = _write(tmp_path, "broken.yaml", "items: [")
    assert runner.invoke(cr.app, [str(REVIEWS), str(broken), str(CLEAN)]).exit_code == 2
    assert runner.invoke(cr.app, [str(REVIEWS), str(tmp_path / "absent.yaml"), str(CLEAN)]).exit_code == 2
    latin1 = tmp_path / "latin1.md"
    latin1.write_bytes("Caf\xe9".encode("latin-1"))
    assert runner.invoke(cr.app, [str(REVIEWS), str(LEDGER), str(latin1)]).exit_code == 2


# --------------------------------------------------------------------------------------------------------
# Ledger-only check (plan mode), empty letters and checks that could not run
# --------------------------------------------------------------------------------------------------------

# Feedback with no editor and no letter to write (contest feedback, as in the plan-mode smoke run). The review
# is synthetic, written for this test about the VarLens fixture, with the shape that run had to split: a
# referee who numbers within headings (Weaknesses, Suggestions, Questions), one numbered suggestion split into
# sentence fragments, requests repeated under another heading, and an item handed to another skill.
CONTEST_REVIEWS = """Reviewer 2

Weaknesses
1) Only two genomes from one sequencing platform were benchmarked.

Suggestions
1) Please benchmark more genomes. 2) Report the spread over five runs, repeat the benchmark on a second \
laptop, and publish the timing scripts.

Questions
1) Which release of the module tables did the benchmark use?

Reviewer 3

Weaknesses
The report lists variants with possible clinical meaning, and a reader could act on them without seeing a \
clinician. The paper never says who its intended readers are.

Suggestions
The authors should name the intended readers and revise the Introduction for them.
"""

CONTEST_LEDGER = """manuscript: paper-v1.md
rounds:
  - round: 1
    decision: contest feedback, no response letter
    items:
      - id: R2.W1
        referee: Reviewer 2
        label: Weaknesses 1
        comment: Only two genomes from one sequencing platform were benchmarked.
        evidence: [new-analysis]
        decision: address
        commitments:
          - change: Add the public long-read callset of HG002
            target: Results, Performance; Table 1
            landed: ''
      - id: R2.S1
        referee: Reviewer 2
        label: Suggestions 1
        same_as: [R2.W1]
        comment: Please benchmark more genomes.
        evidence: [new-analysis]
      - id: R2.S2a
        referee: Reviewer 2
        label: Suggestions 2
        sentence: R2.S2a
        comment: Report the spread over five runs,
        evidence: [table]
        decision: undecided
      - id: R2.S2b
        referee: Reviewer 2
        label: Suggestions 2
        sentence: R2.S2a
        comment: repeat the benchmark on a second laptop,
        evidence: [new-analysis]
        decision: decline
        reason: No second laptop of this class is available to us; the runtime claim is limited to the one machine.
      - id: R2.S2c
        referee: Reviewer 2
        label: Suggestions 2
        sentence: R2.S2a
        comment: and publish the timing scripts.
        evidence: [statement]
        decision: undecided
      - id: R2.Q1
        referee: Reviewer 2
        label: Questions 1
        comment: Which release of the module tables did the benchmark use?
        evidence: [answer, methods-text]
        decision: address
        commitments:
          - change: State the module table release in the Methods
            target: Methods, Implementation
            landed: ''
      - id: R3.W1a
        referee: Reviewer 3
        label: null
        comment: The report lists variants with possible clinical meaning, and a reader could act on them without
          seeing a clinician.
        evidence: [discussion-text]
        must_fix: true
        hand_to: manuscript-policy-fit
        decision: undecided
      - id: R3.W1b
        referee: Reviewer 3
        label: null
        comment: The paper never says who its intended readers are.
        evidence: [wording]
        decision: address
        commitments:
          - change: Name the intended readers in the Abstract and Introduction
            target: Abstract; Introduction
            landed: ''
      - id: R3.S1
        referee: Reviewer 3
        label: null
        same_as: [R3.W1b]
        comment: The authors should name the intended readers and revise the Introduction for them.
        evidence: [wording]
"""

# Reply-level checks: with no reply block, none of them looked at anything.
REPLY_CHECKS = {"quotes", "order", "locations_named", "blanket", "openings", "locations_resolve", "revised_quotes",
                "numbers"}


def _contest(tmp_path: Path, ledger: str = CONTEST_LEDGER) -> tuple[Path, Path]:
    return _write(tmp_path, "reviews.md", CONTEST_REVIEWS), _write(tmp_path, "ledger.yaml", ledger)


def test_a_plan_ledger_is_checked_alone_and_undecided_items_are_listed_not_failed(tmp_path: Path) -> None:
    reviews, ledger = _contest(tmp_path)
    report = cr.run(reviews, ledger)  # no response letter: plan mode
    assert report.stage == "ledger"
    assert report.findings == [] and report.blocking == 0
    # R2.S1 and R3.S1 repeat earlier items and take their decisions; fragments of one sentence are verbatim,
    # not elisions
    assert [u["id"] for u in report.undecided] == ["R2.S2a", "R2.S2c", "R3.W1a"]
    assert next(u for u in report.undecided if u["id"] == "R3.W1a")["hand_to"] == ["manuscript-policy-fit"]
    # only the ledger's own checks run, and they did run; the letter checks do not apply and the header says so
    assert {c["check"]: c["state"] for c in report.checks} == {"ledger": "pass", "decisions": "pass"}
    assert report.unassessed_checks == 0
    md = cr.to_markdown(report)
    assert "There is no response letter yet" in md
    assert "no reply, no place in the manuscript and no change you committed to was checked" in md


def test_a_plan_ledger_still_blocks_on_its_own_defects(tmp_path: Path) -> None:
    text = (CONTEST_LEDGER.replace("repeat the benchmark on a second laptop,", "repeat the benchmark on another laptop")
            .replace("same_as: [R3.W1b]", "same_as: [R3.W9]"))
    text = re.sub(r"        reason: .*\n", "", text)
    assert text.count("same_as: [R3.W9]") == 1 and "reason:" not in text
    reviews, ledger = _contest(tmp_path, text)
    report = cr.run(reviews, ledger)
    assert {(f.code, f.item) for f in report.findings if f.blocking} == {
        ("LEDGER_COMMENT_NOT_VERBATIM", "R2.S2b"), ("REASON_MISSING", "R2.S2b"), ("LEDGER_LINK_INVALID", "R3.S1")}
    # the broken link means R3.S1 has no decision to take over
    assert "R3.S1" in [u["id"] for u in report.undecided]


def test_a_repeat_takes_its_decision_from_the_item_it_repeats_in_a_letter_check(tmp_path: Path) -> None:
    reviews, ledger = _contest(tmp_path)
    letter = _write(tmp_path, "letter.md", "# Response\n")
    found = _codes(cr.run(reviews, ledger, letter))
    assert ("DECISION_MISSING", "R2.S2a") in found and ("DECISION_MISSING", "R3.W1a") in found
    assert ("DECISION_MISSING", "R3.S1") not in found and ("DECISION_MISSING", "R2.S1") not in found


def test_hand_to_replaces_route_and_old_ledgers_still_load(tmp_path: Path) -> None:
    assert "hand_to: manuscript-policy-fit" in LEDGER.read_text(encoding="utf-8")
    old = _write(tmp_path, "old.yaml", LEDGER.read_text(encoding="utf-8").replace("hand_to:", "route:"))
    new_items = {it.id: it.hand_to for it in cr.load_ledger(LEDGER)[0].items}
    old_items = {it.id: it.hand_to for it in cr.load_ledger(old)[0].items}
    assert new_items == old_items
    assert new_items["R2.P2a"] == new_items["R2.P2b"] == ["manuscript-policy-fit"]
    assert new_items["R1.1"] == []
    assert _run(ledger=old).findings == []


def test_zero_reply_blocks_leave_every_reply_check_not_assessed(tmp_path: Path) -> None:
    letter = _write(tmp_path, "empty.md", "# Response\n\nWe thank the reviewers and have revised the paper.\n")
    report = _run(letter)
    states = {c["check"]: c["state"] for c in report.checks}
    assert states["coverage"] == "fail"
    assert {k for k in REPLY_CHECKS if states[k] != "not_assessed"} == set()
    assert any("no replies the check could pair with a comment" in n for n in report.not_assessed)


def test_without_revised_exit_zero_is_reported_as_not_a_clean_result(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cr.app, [str(REVIEWS), str(LEDGER), str(CLEAN), "--json", str(tmp_path / "c.json")])
    assert result.exit_code == 0, result.output
    assert "landed in the manuscript" not in result.output
    assert ("| Is every change you committed to recorded in the ledger as made, with its place in the manuscript? "
            "| Yes. |") in result.output
    assert "not a clean result" in result.output
    data = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    assert data["summary"]["not_assessed_checks"] == 4  # locations, revised quotes, numbers, guard
    full = runner.invoke(cr.app, [str(REVIEWS), str(LEDGER), str(CLEAN), "--revised", str(V2), "--original", str(V1)])
    assert full.exit_code == 0 and "not a clean result" in full.output  # guard.py report not given


def test_cli_checks_a_plan_ledger_without_a_letter(tmp_path: Path) -> None:
    reviews, ledger = _contest(tmp_path)
    runner = CliRunner()
    ok = runner.invoke(cr.app, [str(reviews), str(ledger), "--md", str(tmp_path / "plan.md")])
    assert ok.exit_code == 0, ok.output
    md = (tmp_path / "plan.md").read_text(encoding="utf-8")
    assert "no response letter" in md and "## Decisions still needed from you" in md and "R3.W1a" in md
    assert runner.invoke(cr.app, [str(reviews), str(ledger), "--revised", str(V2)]).exit_code == 2


# --------------------------------------------------------------------------------------------------------
# The report the authors read: quotes, plain words and the order of the work
# --------------------------------------------------------------------------------------------------------

def _outside_quotes_and_parentheses(md: str) -> str:
    """The report with quotations and parenthesised asides removed: what is left must not point by line alone."""
    text = re.sub("“[^”]*”", "", md)
    while True:
        stripped = re.sub(r"\([^()]*\)", "", text)
        if stripped == text:
            return text
        text = stripped


def test_the_markdown_report_quotes_each_comment_and_shows_no_codes() -> None:
    report = _run(SEEDED, LEDGER_SEEDED)
    md = cr.to_markdown(report)
    # codes, ledger field names and state words stay in the JSON
    for code in {f.code for f in report.findings}:
        assert code not in md, code
    for token in ("not_assessed", "must_fix", "hand_to", "same_as", "undecided", "(resolved)", "| pass |", "| fail |",
                  "letter line"):
        assert token not in _outside_quotes_and_parentheses(md), token
    # a line number only ever follows a description, in parentheses
    assert not re.search(r"\blines? \d|\bL\d+\b", _outside_quotes_and_parentheses(md))
    # each comment is named by the referee's own number and quoted
    assert ("**Reviewer 2** (R2.P4): “I also wonder whether the peak memory of 6.1 GB includes the module tables "
            "loaded into memory.” The response letter has no reply to this comment.") in md
    assert "**Reviewer 1, comment 4b** (R1.4b): “Please state the version of the module tables" in md
    # a misquoted comment is set against the reviews as written, not their case-folded text
    assert ("The closest passage in the reviews reads “2. Table 1 reports medians of 3 runs. Please report the "
            "spread across runs as well.”") in md
    # the reply sentence that carries a wrong number is quoted
    number = next(f for f in report.findings if f.code == "NUMBER_NOT_IN_MANUSCRIPT")
    assert "It reads “VEP took 41.2 and 44.8 minutes, against 9.8 and 10.4 minutes for VarLens" in number.message
    assert [d["number"] for d in number.details] == ["98.6"]
    # an out-of-order reply says which reply it stands after
    order = next(f for f in report.findings if f.code == "ORDER_MISMATCH")
    assert "stands after the reply to Reviewer 1, comment 4b, which comes later in the reviews" in order.message


def test_a_reply_moved_up_names_the_reply_it_now_precedes(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8")
    start, end = text.index("<!-- item: R2.P3 -->"), text.index("<!-- item: R2.P4 -->")
    block = text[start:end]
    text = text[:start] + text[end:]
    text = text.replace("<!-- item: R1.1 -->", block + "<!-- item: R1.1 -->")
    order = [f for f in _run(_write(tmp_path, "m.md", text)).findings if f.code == "ORDER_MISMATCH"]
    assert len(order) == 1 and "stands before the reply to Reviewer 1, comment 1, which comes earlier in the reviews" \
        in order[0].message


def _landed(ledger: str, item: str, landed: str) -> str:
    """The ledger text with the first commitment of one item set to a landed value."""
    head = ledger.index(f"- id: {item}\n")
    k = ledger.index("landed:", head)
    eol = ledger.index("\n", k)
    return ledger[:k] + f"landed: '{landed}'" + ledger[eol:]


def test_findings_are_grouped_by_when_the_work_can_be_done(tmp_path: Path) -> None:
    stages = {(f.code, f.item): f.stage for f in _run(SEEDED, LEDGER_SEEDED).findings}
    assert stages == {("PROMISE_NOT_LANDED", "R2.P1"): "now", ("NUMBER_NOT_IN_MANUSCRIPT", "R1.1"): "now",
                      ("QUOTE_NOT_VERBATIM", "R1.2"): "writing", ("ORDER_MISMATCH", "R1.4a"): "writing",
                      ("MISSING_REPLY", "R2.P4"): "writing", ("BLANKET_REPLY", "R1.4b"): "writing"}
    # a change still to make takes the stage of the evidence it needs: new analysis now, wording with the writing,
    # an availability statement at the end; a venue's length limit once the venue is chosen
    text = LEDGER.read_text(encoding="utf-8")
    for item in ("Ed.P1", "R1.4a", "R2.P1"):
        text = _landed(text, item, "promised")
    report = cr.run(REVIEWS, _write(tmp_path, "l.yaml", text), CLEAN, mode="rebuttal", max_chars=1500)
    by_item = {f.item: f.stage for f in report.findings}
    assert by_item == {"R2.P1": "now", "R1.4a": "writing", "Reviewer 1": "journal", "Reviewer 2": "journal",
                       "Ed.P1": "final"}
    md = cr.to_markdown(report)
    heads = [md.index(f"## {title}") for _, title in cr.STAGES]
    assert heads == sorted(heads)
    final = md[heads[-1]:md.index("\n## ", heads[-1] + 1)]
    assert "Code availability statement" in final and "comment 4a" not in final


def test_the_plan_report_asks_for_decisions_in_plain_words_by_stage(tmp_path: Path) -> None:
    reviews, ledger = _contest(tmp_path)
    md = cr.to_markdown(cr.run(reviews, ledger))
    for token in ("must_fix", "hand_to", "same_as", "undecided", "new-analysis", "discussion-text", "R2.S2a (",
                  "## Undecided items"):
        assert token not in md, token
    decisions = md[md.index("## Decisions still needed from you"):]
    now = decisions.index("### Fix now: the science and the evidence")
    writing = decisions.index("### Then the writing")
    final = decisions.index("### Before submission, once the code is final")
    assert now < writing < final
    assert now < decisions.index("**Reviewer 2, Suggestions 2** (R2.S2a): “Report the spread over five runs”."
                                 " It asks for a new or changed table.") < writing
    essential = decisions.index("**Reviewer 3** (R3.W1a): “The report lists variants with possible clinical")
    assert writing < essential < final
    assert "Draft its reply with manuscript-policy-fit." in decisions[essential:final]
    assert final < decisions.index("(R2.S2c): “and publish the timing scripts.”")


def test_unresolved_places_are_named_in_a_sentence(tmp_path: Path) -> None:
    text = CLEAN.read_text(encoding="utf-8").replace("(Code availability, lines 95-96)",
                                                     "(Code availability, lines 950-960)")
    text = text.replace('(Methods, "Implementation",\nline 21)', '(Methods, "Software design", line 21)')
    report = _run(_write(tmp_path, "l.md", text))
    unresolved = {f.item: f.message for f in report.findings if f.code == "LOCATION_UNRESOLVED"}
    last = len(V2.read_text(encoding="utf-8").splitlines())
    assert unresolved["Ed.P1"] == ("The reply in the response letter (line 13) names lines 950-960, but the line "
                                   f"numbers of the revised manuscript (paper-v2.md) run from 1 to {last}.")
    assert ("names “Software design”, but no heading of the revised manuscript contains these words"
            in unresolved["R1.4b"])


def test_checks_that_did_not_run_are_told_once_per_reason(tmp_path: Path) -> None:
    empty = _run(_write(tmp_path, "empty.md", "# Response\n\nWe thank the reviewers and have revised the paper.\n"))
    no_blocks = [n for n in empty.not_assessed if "no replies the check could pair" in n]
    assert len(no_blocks) == 1
    assert "the order of the replies" in no_blocks[0] and "the numbers in the replies" in no_blocks[0]
    # without a revised manuscript, one sentence says so; no place is listed on its own
    journal = cr.run(REVIEWS, LEDGER, CLEAN)
    assert journal.not_assessed[0].startswith("No revised manuscript was given")
    assert not any(n.startswith("The reply to") for n in journal.not_assessed)
    # a place that could not be checked for another reason is listed by its reply
    off = _run(line_check=False)
    assert any(n.startswith("The reply to the editor's request beginning") and "lines 95-96" in n
               and "the line check was switched off" in n for n in off.not_assessed)


def test_a_guard_report_that_cannot_be_matched_to_printed_lines_is_not_assessed(tmp_path: Path) -> None:
    lines = V2.read_text(encoding="utf-8").splitlines()
    revised = _write(tmp_path, "revised.txt", "\n".join(f"{i + 101} {line}" if line.strip() else ""
                                                        for i, line in enumerate(lines)))
    inventory = guard.compare(V1.read_text(encoding="utf-8"), V2.read_text(encoding="utf-8"), revision=True)
    path = _write(tmp_path, "guard.json", json.dumps(inventory))
    report = cr.run(REVIEWS, LEDGER, CLEAN, revised=revised, line_check=False, guard_json=path)
    state = next(c for c in report.checks if c["check"] == "guard")
    assert state["state"] == "not_assessed" and "printed line numbers" in str(state["detail"])
    assert "not a clean result" in cr.to_markdown(report)


def test_input_errors_read_as_sentences(tmp_path: Path) -> None:
    with pytest.raises(cr.InputError, match=r"^The ledger .*l\.yaml is not valid YAML \(.*\)\.$"):
        cr.load_ledger(_write(tmp_path, "l.yaml", "items: ["))
    with pytest.raises(cr.InputError, match=r"^In the ledger .*, item 1 of round 1 \(R1\.1\) has no `comment:` text\.$"):
        cr.load_ledger(_write(tmp_path, "m.yaml", "items:\n  - id: R1.1\n"))


@pytest.mark.parametrize("section", [
    "VarLens: fast annotation of personal genomes on a laptop > Results > Performance",
    "VarLens: fast annotation of personal genomes on a laptop > 5. Discussion > 5.1 Limitations of Variant Annotation",
    "VarLens: fast annotation of personal genomes on a laptop > Appendix > A.2 Extra runs",
    "VarLens: fast annotation of personal genomes on a laptop",
    "Results > Performance",
])
def test_changes_are_placed_in_guards_own_words(section: str) -> None:
    """The letter check names the place of a change exactly as guard.py's revision report does."""
    title = "VarLens: fast annotation of personal genomes on a laptop"
    assert cr._section_words(section, title) == guard._section({"section": section}, title)


def test_an_unmentioned_change_under_a_numbered_heading_names_the_section_by_number(tmp_path: Path) -> None:
    title = "VarLens: fast annotation of personal genomes on a laptop"
    change = {"severity": "protected", "kind": "number", "change": "added", "token": "4.2", "before_line": None,
              "after_line": 2, "authorised": False, "before": "",
              "section": f"{title} > 5. Discussion > 5.1 Limitations of Variant Annotation",
              "after": "Runtime grew by 4.2 minutes on the slower disk."}
    path = _write(tmp_path, "guard.json", json.dumps({"title": title, "protected": {}, "sentence_changes": [change]}))
    report = _run(guard_json=path)
    assert [d["section"] for f in report.findings for d in f.details] == [
        "section 5.1, Limitations of Variant Annotation"]
    assert ("In section 5.1, Limitations of Variant Annotation (line 2 of the revised manuscript), the number "
            "\u201c4.2\u201d is new: \u201cRuntime grew by 4.2 minutes on the slower disk.\u201d") in cr.to_markdown(report)


def test_a_long_list_of_unmentioned_changes_is_cut_and_says_how_many_more(tmp_path: Path) -> None:
    changes = [{"severity": "protected", "kind": "number", "change": "added", "token": f"{n}.5", "before_line": None,
                "after_line": 2, "authorised": False, "before": "", "section": "Results",
                "after": f"Run {n} took {n}.5 minutes."} for n in range(cr.SHOWN_CHANGES + 2)]
    path = _write(tmp_path, "guard.json", json.dumps({"protected": {}, "sentence_changes": changes}))
    report = _run(guard_json=path)
    found = [f for f in report.findings if f.code == "UNMENTIONED_CHANGE"]
    assert len(found) == 1 and len(found[0].details) == cr.SHOWN_CHANGES + 2
    md = cr.to_markdown(report)
    assert found[0].message.startswith("17 changes to a number, citation or identifier sit where no reply")
    assert md.count("  - In the Results (line 2 of the revised manuscript), the number") == cr.SHOWN_CHANGES
    assert "  - Two more changes of this kind are listed in the comparison of the two versions" in md


# --- paired letters (idea 7 of the 2026-10-24 comparison) ---------------------------------------------------------

PAIRED = ROOT / "evals" / "fixtures" / "manuscript-reviewer-response"


def test_a_confident_letter_gets_the_verdicts_of_the_plain_one() -> None:
    plain, confident = _report("response-clean.md", "paper-v2.md"), _report("response-letter.md", "paper-v2.md")
    assert _verdicts(plain) == _verdicts(confident) == set()
    assert [f["code"] for f in confident["findings"] if not f["blocking"]] == ["OPENING_AGREE"]  # a style note


def test_the_same_letter_gets_other_verdicts_when_the_change_did_not_land() -> None:
    landed, missing = _report("response-clean.md", "paper-v2.md"), _report("response-clean.md", "paper-v2-seeded.md")
    assert _verdicts(landed) == set() and _verdicts(missing) != set()
    assert ("REVISED_QUOTE_NOT_FOUND", "R1.3a") in _verdicts(missing)  # the reply quotes a sentence paper-v2 lacks


def _report(letter: str, revised: str) -> dict:
    out = Path(tempfile.mkdtemp()) / "report.json"
    CliRunner().invoke(cr.app, [str(PAIRED / "reviews-r1.txt"), str(PAIRED / "review-ledger.yaml"), str(PAIRED / letter),
                                "--revised", str(PAIRED / revised), "--original", str(PAIRED / "paper-v1.md"),
                                "--json", str(out)])
    return json.loads(out.read_text(encoding="utf-8"))


def _verdicts(report: dict) -> set[tuple[str, str]]:
    """What blocks the letter, per comment: the verdicts the pair compares."""
    return {(f["code"], f["item"]) for f in report["findings"] if f["blocking"]}
