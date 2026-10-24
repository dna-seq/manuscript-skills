"""Offline tests for manuscript-peer-review: the finding checker, its fixtures and its eval cases."""

from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "manuscript-peer-review"
FIXTURES = ROOT / "evals" / "fixtures" / "manuscript-peer-review"
SEEDED = FIXTURES / "seeded.md"
CLEAN = FIXTURES / "clean.md"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cf = _load("check_findings", SKILL / "scripts" / "check_findings.py")


def _finding(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "F1",
        "seat": "evidence-statistics",
        "location": "Methods, Benchmark",
        "quote": "We assigned ClinVar variants at random to training (80%) and test (20%) sets.",
        "concern": "A variant-level random split puts variants from the same gene on both sides.",
        "claim": "Abstract: held-out performance of VarRank.",
        "consequence": "validity",
        "severity": "major",
        "change_my_mind": "Results on a gene-disjoint split.",
        "route": "author-required",
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def _line_of(path: Path, needle: str) -> int:
    """1-based line of the first line containing needle, computed from the file at test time."""
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return n
    raise AssertionError(f"{needle!r} not in {path.name}")


def _only(report: dict[str, Any]) -> dict[str, Any]:
    assert len(report["findings"]) == 1
    return report["findings"][0]


# --- the planted defects: found in the seeded manuscript, absent from the clean control -----------------

# (key, quote a seat would copy, a substring of the line where the quote starts, of the line where it ends)
PLANTED = [
    ("priority", "VarRank is the first tool to combine evolutionary conservation and population allele frequency",
     "VarRank is the first", "tool to combine evolutionary"),
    ("missing-baseline", "outperformed existing pathogenicity predictors",
     "outperformed existing pathogenicity", "outperformed existing pathogenicity"),
    ("leakage", "We assigned ClinVar variants at random to training (80%) and test (20%) sets.",
     "We assigned ClinVar variants", "We assigned ClinVar variants"),
    ("n-mismatch", "On 4,812 held-out ClinVar missense variants", "On 4,812", "held-out ClinVar missense"),
    ("genome-build", "rs429358 | chr19:45411941", "chr19:45411941", "chr19:45411941"),
    ("causal", "This shows that the variants VarRank prioritises cause elevated LDL cholesterol.",
     "p = 2.1 x 10^-5). This", "shows that the variants VarRank"),
]

# What two different seats might write about each planted defect (no prior-work cue, so no identifier needed).
CONCERNS = {
    "priority": ("The priority statement is wider than any comparison the paper reports.",
                 "Claiming to be first invites a referee to list earlier combined scores."),
    "missing-baseline": ("Superiority is asserted against only two older predictors.",
                         "Only SIFT and PolyPhen-2 appear in Table 1, so 'outperformed' overreaches."),
    "leakage": ("Random assignment by variant lets genes appear in both training and test data.",
                "Gene-level constraint features plus a variant-level split can inflate held-out accuracy."),
    "n-mismatch": ("The Abstract's held-out count disagrees with Methods and Table 1.",
                   "Which test-set size is correct, 4,812 or 4,182?"),
    "genome-build": ("This rs429358 position is the GRCh37 coordinate although Methods states GRCh38.",
                     "Table 2 mixes builds: chr19:45411941 is not the GRCh38 position."),
    "causal": ("A cross-sectional association cannot show that these LDLR variants cause higher LDL.",
               "Causal wording for an observational comparison of 41 carriers."),
}


@pytest.mark.parametrize("key,quote,start,end", PLANTED, ids=[p[0] for p in PLANTED])
def test_planted_quote_is_located_in_seeded_and_absent_from_clean(key: str, quote: str, start: str, end: str) -> None:
    seeded = _only(cf.check([_finding(id=key, quote=quote)], SEEDED))
    assert seeded["contract"] == "pass", seeded["problems"]
    assert seeded["quote"]["line"] == _line_of(SEEDED, start)
    assert seeded["quote"]["end_line"] == _line_of(SEEDED, end)
    assert seeded["quote"]["occurrences"] == 1

    clean = _only(cf.check([_finding(id=key, quote=quote)], CLEAN))
    assert clean["contract"] == "fail"
    assert clean["quote"]["status"] == "not_found"


def test_a_panel_on_the_seeded_paper_groups_each_planted_defect_once() -> None:
    """Two seats per planted defect, quoting different spans of the same text: one group per defect."""
    findings = []
    seats = ["evidence-statistics", "skeptic", "claims-novelty", "genomics", "reproducibility", "human-data-clinical"]
    for n, (key, quote, _, _) in enumerate(PLANTED):
        words = quote.split()
        first, second = CONCERNS[key]
        findings.append(_finding(id=f"{key}-a", seat=seats[n], quote=quote, concern=first))
        findings.append(_finding(id=f"{key}-b", seat=seats[(n + 1) % len(seats)], quote=" ".join(words[1:]),
                                 concern=second))
    report = cf.check(findings, SEEDED)
    assert report["summary"]["fail"] == 0
    groups = report["groups"]
    assert len(groups) == len(PLANTED)
    by_key = {g["findings"][0].rsplit("-", 1)[0]: g for g in groups}
    assert set(by_key) == {p[0] for p in PLANTED}
    for g in groups:
        assert len({f.rsplit("-", 1)[0] for f in g["findings"]}) == 1  # no group mixes two defects
        assert g["n_seats"] == 2


# --- verbatim matching ------------------------------------------------------------------------------------------

def _doc(tmp_path: Path, text: str, name: str = "paper.md") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.mark.parametrize("manuscript_text,quote", [
    ("The so-called “gold standard” set – 1,946 variants – was kept.",
     'The so-called "gold standard" set - 1,946 variants - was kept.'),
    ('The so-called "gold standard" set - 1,946 variants - was kept.',
     "The so-called “gold standard” set — 1,946 variants — was kept."),
    ("We report the authors’ own genome in full.", "We report the authors' own genome in full."),
    ("The ﬁrst model ignores\nline\n   breaks   entirely.", "The first model ignores line breaks entirely."),
    ("TWO Different Cases are matched.", "two different cases are matched."),
])
def test_quotes_match_across_unicode_whitespace_and_case(tmp_path: Path, manuscript_text: str, quote: str) -> None:
    f = _only(cf.check([_finding(quote=quote)], _doc(tmp_path, manuscript_text)))
    assert f["quote"]["status"] == "verified", f["problems"]


LATEX = r"""\section{Introduction}
VarRank is the \emph{first} tool to combine conservation~\cite{kircher2014} and frequency in 12\% of cases.
% VarRank is the only tool that reviewers will accept
As shown in Table~\ref{tab:bench}, accuracy rose ``substantially'' -- from 0.84 to 0.91.
"""


@pytest.mark.parametrize("quote,status,line", [
    ("VarRank is the first tool to combine conservation and frequency in 12% of cases", "verified", 2),
    (r"the \emph{first} tool to combine conservation~\cite{kircher2014}", "verified", 2),
    ('accuracy rose "substantially" – from 0.84 to 0.91', "verified", 4),
    ("As shown in Table, accuracy rose", "verified", 4),
    ("VarRank is the only tool that reviewers will accept", "not_found", None),  # a LaTeX comment
])
def test_latex_markup_is_normalised_and_comments_are_not_quotable(tmp_path: Path, quote: str, status: str,
                                                                  line: int | None) -> None:
    f = _only(cf.check([_finding(quote=quote)], _doc(tmp_path, LATEX, "paper.tex")))
    assert f["quote"]["status"] == status
    if line:
        assert f["quote"]["line"] == line


def test_percent_is_not_a_comment_in_markdown(tmp_path: Path) -> None:
    p = _doc(tmp_path, "In 12% of cases the score was missing for every variant.\n")
    f = _only(cf.check([_finding(quote="In 12% of cases the score was missing")], p))
    assert f["quote"]["status"] == "verified"


def test_html_comments_are_not_quotable() -> None:
    first_line = SEEDED.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("<!--")  # the fixture's note to graders, invisible to readers
    f = _only(cf.check([_finding(quote="Fictional manuscript used to evaluate manuscript-skills")], SEEDED))
    assert f["quote"]["status"] == "not_found"


def test_markdown_markup_is_stripped(tmp_path: Path) -> None:
    p = _doc(tmp_path, "**VarRank** is the [first tool](https://example.org) to `combine` two _scores_ [3].\n")
    f = _only(cf.check([_finding(quote="VarRank is the first tool to combine two scores")], p))
    assert f["quote"]["status"] == "verified" and f["quote"]["view"] == "stripped"


@pytest.mark.parametrize("quote,status", [
    ("We assigned ClinVar variants ... (20%) sets.", "verified"),
    ("We assigned ClinVar variants … test set 4,182 variants", "verified"),
    ("the test set 4,182 variants [...] We assigned ClinVar variants", "not_found"),  # fragments out of order
])
def test_elided_quotes_must_keep_their_order(quote: str, status: str) -> None:
    assert _only(cf.check([_finding(quote=quote)], SEEDED))["quote"]["status"] == status


@pytest.mark.parametrize("quote,ok", [("first", False), ("the first tool", True), ("chr19:45411941", True)])
def test_a_quote_must_be_long_enough_to_anchor_a_finding(quote: str, ok: bool) -> None:
    f = _only(cf.check([_finding(quote=quote)], SEEDED))
    assert (f["contract"] == "pass") is ok
    if not ok:
        assert any("too short" in p for p in f["problems"])


def test_a_misquote_reports_where_the_quote_stops_matching() -> None:
    """The hint quotes the manuscript text that matched, with the line number only in parentheses."""
    f = _only(cf.check([_finding(quote="We assigned ClinVar variants at random to three folds")], SEEDED))
    assert f["contract"] == "fail"
    line = _line_of(SEEDED, "We assigned ClinVar variants")
    hint = next(p for p in f["problems"] if "wording differs" in p)
    assert '"**We assigned ClinVar variants at random to** training (80%) and test (20%) sets."' in hint
    assert f"(line {line})" in hint and f"seeded.md:{line}" not in hint


# --- the contract ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("field", cf.REQUIRED)
def test_each_required_field_is_enforced(field: str) -> None:
    raw = _finding()
    del raw[field]
    f = _only(cf.check([raw], SEEDED))
    assert f["contract"] == "fail"
    assert any(field in p for p in f["problems"])


@pytest.mark.parametrize("override,ok", [
    ({"severity": "critical"}, False),
    ({"consequence": "novelty"}, False),
    ({"route": "rewrite"}, False),
    ({"seat": "reviewer-3"}, False),
    ({"seat": "custom:clinician"}, True),
    ({"seat": "skeptic@codex"}, True),  # the same seat run on another model by manuscript-other-models
    ({"seat": "custom:clinician@gemini"}, True),
    ({"seat": "skeptic@"}, False),
    ({"seat": "reviewer-3@codex"}, False),
    ({"seat": "skeptic@codex/gpt-5.6-sol"}, False),  # the model goes in the run record, not the seat name
    ({"seat": "ai-systems"}, True),  # the domain module added after the Paper 2 smoke run, as its own seat
    ({"triage": "cosmetic"}, False),
    ({"cost": "cheap"}, False),
    ({"hand_to": "manuscript-prose-edit"}, True),
    ({"route": "dropped"}, False),
    ({"route": "dropped", "drop_reason": "No claim depends on it."}, True),
    ({"stage": "final"}, True),
    ({"stage": "later"}, False),
])
def test_allowed_values(override: dict[str, Any], ok: bool) -> None:
    f = _only(cf.check([_finding(**override)], SEEDED))
    assert (f["contract"] == "pass") is ok, f["problems"]


def test_absence_findings_must_say_where_the_seat_looked() -> None:
    missing = _finding(kind="absence", quote=None, concern="The fitting software and version are not stated.")
    assert _only(cf.check([missing], SEEDED))["contract"] == "fail"
    looked = dict(missing, looked_in=["Methods, Model", "Data and code availability"])
    f = _only(cf.check([looked], SEEDED))
    assert f["contract"] == "pass" and f["quote"] is None
    assert _only(cf.check([dict(looked, looked_in=[])], SEEDED))["contract"] == "fail"


def test_a_present_finding_without_a_quote_fails() -> None:
    f = _only(cf.check([_finding(quote=None)], SEEDED))
    assert f["contract"] == "fail" and any("verbatim quote" in p for p in f["problems"])


def test_duplicate_ids_and_non_objects_fail() -> None:
    report = cf.check([_finding(), _finding(seat="skeptic"), "not a finding"], SEEDED)
    assert [f["contract"] for f in report["findings"]] == ["fail", "fail", "fail"]
    assert report["groups"] == []


NOVELTY = "The tool is not novel: prior work already combines conservation and allele frequency."


@pytest.mark.parametrize("prior,external,ok", [
    (None, None, False),
    ([{"citation": "Kircher M et al. Nature Genetics 2014", "status": "unverified"}], None, True),
    ([{"citation": "Kircher M et al. Nature Genetics 2014", "identifier": "10.1038/ng.2892", "status": "verified"}], None, True),
    ([{"citation": "Kircher M et al. 2014", "identifier": "https://doi.org/10.1038/ng.2892", "status": "verified"}], None, True),
    ([{"citation": "Kircher M et al. 2014", "status": "verified"}], None, False),
    ([{"citation": "Kircher M et al. 2014", "identifier": "see Kircher", "status": "verified"}], None, False),
    ([{"citation": "Kircher M et al. 2014", "identifier": "10.1038/ng.2892"}], None, False),
    ([{"identifier": "10.1038/ng.2892", "status": "verified"}], None, False),
    (None, False, True),
])
def test_prior_work_claims_need_an_identifier_or_unverified(prior: Any, external: Any, ok: bool) -> None:
    f = _only(cf.check([_finding(concern=NOVELTY, prior_work=prior, external_claim=external)], SEEDED))
    assert (f["contract"] == "pass") is ok, f["problems"]
    if external is False:
        assert any("external_claim" in w for w in f["warnings"])


@pytest.mark.parametrize("concern", [
    "The benchmark omits existing predictors that referees will expect.",
    "This is the first tool to do so only if CADD is ignored.",
    "Similar scores have previously been published.",
])
def test_prior_work_cues_are_recognised(concern: str) -> None:
    assert _only(cf.check([_finding(concern=concern)], SEEDED))["contract"] == "fail"


def test_a_concern_without_a_prior_work_cue_needs_no_identifier() -> None:
    f = _only(cf.check([_finding(concern="The split lets gene identity leak into the test set.")], SEEDED))
    assert f["contract"] == "pass" and f["warnings"] == []


@pytest.mark.parametrize("concern,lint", [
    ("VarRank is not state of the art on this task.", "state-of-the-art"),
    ("The authors should also run a replication cohort.", "new-work"),
    ("The model is too simple for the task.", "simplicity"),
    ("The score is a trivial extension of CADD to a smaller feature set.", "simplicity"),
    ("The method is trivial and offers little beyond a logistic regression.", "simplicity"),
    ("A simplistic linear model cannot capture epistasis.", "simplicity"),
])
def test_fairness_lints_warn_without_failing(concern: str, lint: str) -> None:
    f = _only(cf.check([_finding(concern=concern)], SEEDED))
    assert f["contract"] == "pass"
    assert any(lint in w for w in f["warnings"])


@pytest.mark.parametrize("concern", [
    # Smoke run on Paper 2 (2026-10-15): a concern about the size of the evidence was flagged as objecting to
    # simplicity because it called perfect scores on one example "near-trivial".
    "With one paper and one reference module, scores of 1.00 are near-trivial and carry no variance.",
    "Reproducing the benchmark is non-trivial without the feature tables.",
    "The effect is trivially small once gene identity is removed.",
])
def test_the_simplicity_lint_ignores_trivial_used_about_results(concern: str) -> None:
    f = _only(cf.check([_finding(concern=concern)], SEEDED))
    assert not any("simplicity" in w for w in f["warnings"]), f["warnings"]


# --- criteria written before reading ---------------------------------------------------------------------------

CRITERIA = """# Criteria, written before reading

C1. A benchmark split that lets test variants share genes with training variants.
2. Not a criterion: a numbered line without the C prefix is ignored.
- **C2:** A comparison with predictors that does not use the same test set.
C3. We assigned ClinVar variants at random to training (80%) and test (20%) sets and the training set grew.

## What I checked
C2: nothing to raise; checked Methods, Benchmark and Table 2.
"""


def test_criteria_are_parsed_with_their_coverage_lines() -> None:
    defined, covered = cf.parse_criteria(CRITERIA)
    assert list(defined) == ["C1", "C2", "C3"] and covered == {"C2"}
    assert defined["C2"] == "A comparison with predictors that does not use the same test set."


def test_findings_are_bound_to_the_criteria_their_seat_wrote_first() -> None:
    findings = [_finding(id="EV-1", criterion="C1"),
                _finding(id="EV-2", criterion="c9", severity="optional"),
                _finding(id="EV-3", off_criterion="the leak only shows in Table 2's gene counts"),
                _finding(id="EV-4")]
    report = cf.check(findings, SEEDED, criteria={"evidence-statistics": CRITERIA})
    by_id = {f["id"]: f for f in report["findings"]}
    assert all(f["contract"] == "pass" for f in by_id.values())  # warnings only: nothing is held back
    assert by_id["EV-1"]["criterion"] == ["C1"] and not by_id["EV-1"]["warnings"]
    assert any("criterion C9, which a simulated referee (evidence-statistics) did not write down" in w
               for w in by_id["EV-2"]["warnings"])
    assert any("for this reason: the leak only shows in Table 2's gene counts." in w for w in by_id["EV-3"]["warnings"])
    assert any("gives no reason; read it as a concern found only while reading" in w for w in by_id["EV-4"]["warnings"])
    seat = report["criteria"]["evidence-statistics"]
    assert [c["findings"] for c in seat["criteria"]] == [["EV-1"], [], []]
    assert seat["unaccounted"] == ["C3"]  # C2 has its coverage line
    assert seat["copied"] == ["C3"]  # it repeats the Benchmark sentence, so it was written after reading
    markdown = cf.to_markdown(report)
    assert ("- A simulated referee (evidence-statistics) wrote down 3 criteria; 1 led to a finding. C3 repeats 12 "
            "words of the manuscript in a row") in markdown
    assert "C3 has neither a finding nor a line saying what was checked" in markdown


def test_without_criteria_the_report_is_unchanged() -> None:
    report = cf.check([_finding(criterion="C1")], SEEDED)
    assert report["criteria"] is None and "set out to check" not in cf.to_markdown(report)


def test_criteria_on_the_command_line(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps({"findings": [_finding(id="EV-1", criterion="C1")]}), encoding="utf-8")
    criteria = tmp_path / "criteria.md"
    criteria.write_text(CRITERIA, encoding="utf-8")
    runner = CliRunner()
    bare = runner.invoke(cf.app, [str(findings), str(SEEDED), "--criteria", str(criteria)])
    assert bare.exit_code == 0, bare.output
    assert "What each referee set out to check" in bare.output
    named = runner.invoke(cf.app, [str(findings), str(SEEDED), "--criteria", f"evidence-statistics={criteria}"])
    assert named.exit_code == 0 and "wrote down 3 criteria" in named.output
    two = tmp_path / "two.json"
    two.write_text(json.dumps([_finding(id="EV-1"), _finding(id="SK-1", seat="skeptic")]), encoding="utf-8")
    ambiguous = runner.invoke(cf.app, [str(two), str(SEEDED), "--criteria", str(criteria)])
    assert ambiguous.exit_code == 2 and "name the seat as SEAT=PATH" in ambiguous.output


# --- adjudicated stage -----------------------------------------------------------------------------------------

DEFENCE = "Features were standardised on the training set."


@pytest.mark.parametrize("override,ok", [
    ({}, False),  # no verdict
    ({"verdict": "confirmed"}, False),  # no triage
    ({"verdict": "confirmed", "triage": "substance"}, False),  # no evidence
    ({"verdict": "confirmed", "triage": "substance", "verdict_evidence": "Methods states the split; no text "
      "elsewhere restricts it by gene."}, True),
    ({"verdict": "downgraded", "triage": "misread-risk"}, False),  # no evidence
    ({"verdict": "downgraded", "triage": "misread-risk", "verdict_evidence": "Narrower than raised."}, True),
    ({"verdict": "refuted", "verdict_evidence": "Methods answers it."}, False),  # no defence quote
    ({"verdict": "refuted", "verdict_evidence": "Methods answers it.",
      "defence_quote": "Features were standardised on the whole dataset."}, False),  # invented defence
    ({"verdict": "refuted", "verdict_evidence": "Methods answers it.", "defence_quote": DEFENCE}, True),
])
def test_adjudicated_findings_need_verdict_fields(override: dict[str, Any], ok: bool) -> None:
    f = _only(cf.check([_finding(**override)], SEEDED, adjudicated=True))
    assert (f["contract"] == "pass") is ok, f["problems"]


def test_seat_stage_does_not_require_a_verdict() -> None:
    assert _only(cf.check([_finding()], SEEDED))["contract"] == "pass"


# Smoke run on Paper 1 (2026-10-15): the defender answered "partly", the finding was confirmed with no
# evidence, and a misreading reached the authors: the Abstract makes no speed claim to qualify.
P1_EXCERPT = """**Results:** We present Just-DNA-Lite, an open-source platform that combines local variant annotation
and polygenic risk score (PRS) computation in a web interface.

## 4.1 Annotation speed

On the primary genome, the median full run took 33.2 s against 6,005.4 s for Generation I, an approximately
181-fold speedup; across the three genomes Generation I ran on, it was 146- to 231-fold. These ratios apply to
these configurations and these inputs, rather than to OakVar generally.
"""
P1_CH1 = {
    "id": "CH-1", "seat": "champion", "location": "Section 4.1, Table 2 and text",
    "quote": "These ratios apply to these configurations and these inputs, rather than to OakVar generally.",
    "concern": "The text already says 'not the same computation'; the Abstract and Conclusion carry no such qualifier.",
    "claim": "Conclusion: the benchmarks 'show faster annotation than the OakVar-based Generation I system'.",
    "consequence": "interpretation", "severity": "optional",
    "change_my_mind": "A sentence in the Abstract scoping the speedup to the full-report workflow.",
    "route": "fixable-in-text", "cost": "text",
}


def test_a_confirmed_finding_needs_verdict_evidence(tmp_path: Path) -> None:
    paper = _doc(tmp_path, P1_EXCERPT)
    as_run = _only(cf.check([dict(P1_CH1, verdict="confirmed", triage="misread-risk")], paper, adjudicated=True))
    assert as_run["contract"] == "fail"
    assert any("verdict_evidence" in p for p in as_run["problems"])
    # The premise test refutes it: the finding's own quote is the qualifier, and the Abstract has no speed claim.
    refuted = dict(P1_CH1, verdict="refuted", defence_quote=P1_CH1["quote"],
                   verdict_evidence="Premise not supported: the Abstract makes no speed claim, and the quoted "
                                    "qualifier sits beside the ratio it qualifies.")
    assert _only(cf.check([refuted], paper, adjudicated=True))["contract"] == "pass"


# --- grouping --------------------------------------------------------------------------------------------------

LEAK = "We assigned ClinVar variants at random to training (80%) and test (20%) sets."
CAUSAL = "This shows that the variants VarRank prioritises cause elevated LDL cholesterol."


def test_overlapping_quotes_group_and_count_distinct_seats() -> None:
    report = cf.check([
        _finding(id="A", seat="evidence-statistics", quote=LEAK, concern="Split leaks genes."),
        _finding(id="B", seat="skeptic", quote="at random to training (80%)", concern="Gene identity leakage."),
        _finding(id="C", seat="skeptic", quote="training (80%) and test (20%) sets", concern="A second skeptic note."),
        _finding(id="D", seat="human-data-clinical", quote=CAUSAL, concern="Causal wording for an association."),
    ], SEEDED)
    groups = {tuple(g["findings"]): g for g in report["groups"]}
    assert set(groups) == {("A", "B", "C"), ("D",)}
    assert groups[("A", "B", "C")]["n_seats"] == 2  # the skeptic counts once
    assert groups[("D",)]["n_seats"] == 1


def test_near_duplicate_concerns_group_across_locations() -> None:
    concern = "The benchmark omits CADD, REVEL and AlphaMissense, the widely used combined predictors."
    report = cf.check([
        _finding(id="A", seat="skeptic", quote="outperformed existing pathogenicity predictors", concern=concern,
                 prior_work=[{"citation": "CADD", "identifier": "10.1038/ng.2892", "status": "verified"}]),
        _finding(id="B", seat="claims-novelty", quote="We compared VarRank with SIFT and",
                 concern="Benchmark omits CADD, REVEL and AlphaMissense, widely used combined predictors.",
                 prior_work=[{"citation": "REVEL", "identifier": "10.1016/j.ajhg.2016.08.016", "status": "verified"}]),
    ], SEEDED)
    assert [g["findings"] for g in report["groups"]] == [["A", "B"]]


def test_unrelated_concerns_stay_apart() -> None:
    report = cf.check([
        _finding(id="A", quote=LEAK, concern="Random split by variant leaks gene identity into the test set."),
        _finding(id="B", quote=CAUSAL, concern="Causal language for a cross-sectional association in one cohort."),
    ], SEEDED)
    assert len(report["groups"]) == 2


@pytest.mark.parametrize("loc_b,grouped", [("Methods,  model", True), ("Data and code availability", False)])
def test_absence_findings_group_by_location(loc_b: str, grouped: bool) -> None:
    common = dict(kind="absence", quote=None, looked_in=["Methods"])
    report = cf.check([
        _finding(id="A", seat="reproducibility", location="Methods, Model", concern="No regularisation stated.", **common),
        _finding(id="B", seat="software-methods", location=loc_b, concern="Fitting library version missing.", **common),
    ], SEEDED)
    assert (len(report["groups"]) == 1) is grouped


def test_group_labels_join_findings_and_failures_stay_out() -> None:
    report = cf.check([
        _finding(id="A", quote=LEAK, concern="Split leaks genes.", group="benchmark"),
        _finding(id="B", quote=CAUSAL, concern="Wording issue.", group="benchmark"),
        _finding(id="C", quote="a sentence that is not in the paper at all", concern="Invented."),
    ], SEEDED)
    assert [g["findings"] for g in report["groups"]] == [["A", "B"]]
    assert report["summary"]["fail"] == 1


# --- supplementary sources ---------------------------------------------------------------------------------------

def test_quotes_from_supplements(tmp_path: Path) -> None:
    supp = _doc(tmp_path, "Table S1 lists 4,182 test variants with their ClinVar accessions.\n", "supp.md")
    report = cf.check([_finding(quote="Table S1 lists 4,182 test variants")], SEEDED, [supp])
    f = _only(report)
    assert f["contract"] == "pass" and f["quote"]["file"] == "supp.md" and f["quote"]["line"] == 1


@pytest.mark.parametrize("supplements,source", [([], "S1.md"), (["S1.xlsx"], "S1.xlsx"), (["S1.bin"], "S1.bin")])
def test_quotes_from_unsupplied_or_unreadable_sources_are_not_assessed(tmp_path: Path, supplements: list[str],
                                                                       source: str) -> None:
    paths = []
    for name in supplements:  # a zip header with NUL bytes, as a real .xlsx has; and bytes that are not UTF-8
        (tmp_path / name).write_bytes(b"PK\x03\x04\x14\x00\x06\x00" if name.endswith(".xlsx") else b"\xff\xfe\xfa")
        paths.append(tmp_path / name)
    f = _only(cf.check([_finding(quote="Table S1 lists 4,182 test variants", source=source)], SEEDED, paths))
    assert f["contract"] == "not_assessed"
    assert f["quote"]["status"] == "not_assessed"


@pytest.mark.parametrize("name, text", [
    ("S4_curation.yaml", "modules:\n  longevitymap:\n    note: Table S1 lists 4,182 test variants\n"),
    ("S1.json", '{"note": "Table S1 lists 4,182 test variants"}\n'),
    ("config.toml", 'note = "Table S1 lists 4,182 test variants"\n'),
    ("refs.bib", "@misc{s1, note = {Table S1 lists 4,182 test variants}}\n"),
    ("page.html", "<p>Table S1 lists 4,182 test variants</p>\n"),
    ("NOTES", "Table S1 lists 4,182 test variants\n"),
])
def test_any_text_file_is_a_supplement_whatever_its_name(tmp_path: Path, name: str, text: str) -> None:
    supp = tmp_path / name
    supp.write_text(text, encoding="utf-8")
    report = cf.check([_finding(quote="Table S1 lists 4,182 test variants", source=name)], SEEDED, [supp])
    assert _only(report)["contract"] == "pass" and report["supplements"] == [name] and report["unreadable"] == {}


def test_an_unreadable_supplement_is_never_reported_as_searched(tmp_path: Path) -> None:
    readable, binary = tmp_path / "S2.yaml", tmp_path / "S1.xlsx"
    readable.write_text("note: something\n", encoding="utf-8")
    binary.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")
    report = cf.check([_finding()], SEEDED, [readable, binary])
    assert report["supplements"] == ["S2.yaml"] and list(report["unreadable"]) == ["S1.xlsx"]
    md = cf.to_markdown(report)
    assert "the check searched S2.yaml." in md and "could not read S1.xlsx" in md


# --- strengths, the CLI and the documentation example ---------------------------------------------------------

def test_strengths_are_quote_checked() -> None:
    data = {"findings": [_finding()], "strengths": [
        {"seat": "champion", "location": "Methods, Model", "quote": DEFENCE, "note": "No leakage from scaling."},
        {"seat": "champion", "location": "Results", "quote": "VarRank was validated in three cohorts", "note": "?"},
    ]}
    report = cf.check(data, SEEDED)
    assert [s["contract"] for s in report["strengths"]] == ["pass", "fail"]
    assert report["summary"]["strengths_not_anchored"] == 1


runner = CliRunner()


def _write_json(tmp_path: Path, data: Any) -> Path:
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_cli_passes_writes_outputs_and_exits_zero(tmp_path: Path) -> None:
    out_json, out_md = tmp_path / "check.json", tmp_path / "check.md"
    result = runner.invoke(cf.app, [str(_write_json(tmp_path, [_finding()])), str(SEEDED),
                                    "--json", str(out_json), "--md", str(out_md)])
    assert result.exit_code == 0, result.output
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["summary"]["pass"] == report["summary"]["findings"] == 1
    assert "Groups" in out_md.read_text(encoding="utf-8")


def test_cli_lists_not_yet_findings_and_exits_one(tmp_path: Path) -> None:
    data = [_finding(), _finding(id="F2", quote="VarRank was validated in three cohorts")]
    result = runner.invoke(cf.app, [str(_write_json(tmp_path, data)), str(SEEDED)])
    assert result.exit_code == 1
    assert "## Not yet findings" in result.output and "**F2**" in result.output


@pytest.mark.parametrize("payload", ["{not json", '"a string"', '{"findings": 3}'])
def test_cli_rejects_malformed_input_with_exit_two(tmp_path: Path, payload: str) -> None:
    p = tmp_path / "findings.json"
    p.write_text(payload, encoding="utf-8")
    assert runner.invoke(cf.app, [str(p), str(SEEDED)]).exit_code == 2


def test_cli_rejects_a_manuscript_that_is_not_text_and_reads_any_that_is(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Length 0 >>\x00")  # a PDF's binary marker line
    result = runner.invoke(cf.app, [str(_write_json(tmp_path, [_finding()])), str(pdf)])
    assert result.exit_code == 2 and "Convert it to Markdown or text" in result.output
    odd = tmp_path / "paper.manuscript"  # text under any name is read
    odd.write_text(SEEDED.read_text(encoding="utf-8"), encoding="utf-8")
    assert runner.invoke(cf.app, [str(_write_json(tmp_path, [_finding()])), str(odd)]).exit_code == 0


# --- the referees' reports: a summary and a recommendation per journal, resting on the referee's own findings ---

def _report(seat: str = "evidence-statistics", **rec: Any) -> dict[str, Any]:
    recommendation = {"venue": "bioinformatics", "recommendation": "major-revision",
                      "reason": "The held-out accuracy rests on a split that can leak gene identity.", "rests_on": ["F1"]}
    recommendation.update(rec)
    return {"seat": seat, "summary": "VarRank ranks missense variants; the benchmark does not yet support its claim.",
            "recommendations": [{k: v for k, v in recommendation.items() if v is not None}]}


def _only_report(report: dict[str, Any]) -> dict[str, Any]:
    assert len(report["reports"]) == 1
    return report["reports"][0]


def test_a_report_resting_on_its_own_findings_passes_and_reads_in_plain_words() -> None:
    report = cf.check({"findings": [_finding()], "reports": [_report()]}, SEEDED)
    assert report["summary"]["reports"] == 1 and report["summary"]["reports_failed"] == 0
    assert report["reports_missing"] == [] and report["venues"] == ["bioinformatics"]
    md = cf.to_markdown(report)
    assert "for bioinformatics: major revision." in md and "major-revision" not in md


@pytest.mark.parametrize("rec, problem", [
    ({"recommendation": "weak accept"}, "not one of accept, minor-revision, major-revision or reject"),
    ({"recommendation": None}, "'None', not one of"),
    ({"reason": None}, "gives no reason"),
    ({"rests_on": []}, "names none of the referee's findings it rests on"),
    ({"rests_on": "F1"}, "must list the ids of the findings it rests on"),
    ({"rests_on": ["F9"]}, "F9, which is not a finding in this file"),
    ({"venue": None}, "does not name the journal it is for"),
])
def test_a_recommendation_without_its_grounds_fails(rec: dict[str, Any], problem: str) -> None:
    r = _only_report(cf.check({"findings": [_finding()], "reports": [_report(**rec)]}, SEEDED))
    assert r["contract"] == "fail" and any(problem in p for p in r["problems"]), r["problems"]


def test_a_recommendation_cannot_rest_on_another_referees_finding() -> None:
    data = {"findings": [_finding(), _finding(id="SK-1", seat="skeptic", quote=CAUSAL,
                                              concern="Causal wording for a cross-sectional association.")],
            "reports": [_report(rests_on=["SK-1"])]}
    r = _only_report(cf.check(data, SEEDED))
    assert r["contract"] == "fail" and any("another referee (skeptic)" in p for p in r["problems"])


def test_accept_needs_no_finding_to_rest_on() -> None:
    r = _only_report(cf.check({"findings": [], "reports": [_report(recommendation="accept", rests_on=None)]}, SEEDED))
    assert r["contract"] == "pass", r["problems"]


def test_a_seats_own_file_gives_one_report_without_naming_the_seat() -> None:
    own = {k: v for k, v in _report().items() if k != "seat"}
    r = _only_report(cf.check({"findings": [_finding()], "report": own}, SEEDED))
    assert (r["seat"], r["contract"]) == ("evidence-statistics", "pass")
    mixed = {"findings": [_finding(), _finding(id="SK-1", seat="skeptic", quote=CAUSAL, concern="Causal wording.")],
             "report": own}
    assert any("which simulated referee wrote it" in p for p in _only_report(cf.check(mixed, SEEDED))["problems"])
    with pytest.raises(ValueError):
        cf.check({"findings": [], "report": own, "reports": [own]}, SEEDED)


def test_one_recommendation_per_journal_and_one_report_per_referee() -> None:
    twice = _report()
    twice["recommendations"] *= 2
    assert any("two recommendations for bioinformatics" in p
               for p in _only_report(cf.check({"findings": [_finding()], "reports": [twice]}, SEEDED))["problems"])
    report = cf.check({"findings": [_finding()], "reports": [_report(), _report()]}, SEEDED)
    assert [r["contract"] for r in report["reports"]] == ["pass", "fail"]
    assert report["summary"]["reports_failed"] == 1


def test_a_referee_without_a_report_is_named_and_none_is_written_for_it() -> None:
    data = {"findings": [_finding(), _finding(id="SK-1", seat="skeptic", quote=CAUSAL, concern="Causal wording.")],
            "reports": [_report()]}
    report = cf.check(data, SEEDED)
    assert report["reports_missing"] == ["skeptic"] and report["summary"]["reports_failed"] == 0
    assert "never write one for them" in cf.to_markdown(report)
    quick = cf.check({"findings": data["findings"]}, SEEDED)  # a quick pass writes no reports: nothing is missing
    assert quick["reports_missing"] == [] and quick["summary"]["reports"] == 0
    assert "holds no referee reports" in cf.to_markdown(quick)


def test_a_ladder_names_the_journal_a_referee_left_out() -> None:
    both = _report()
    both["recommendations"].append({"venue": "bmc-bioinformatics", "recommendation": "minor-revision",
                                    "reason": "The split matters less for a resource paper.", "rests_on": ["F1"]})
    data = {"findings": [_finding(), _finding(id="SK-1", seat="skeptic", quote=CAUSAL, concern="Causal wording.")],
            "reports": [both, _report(seat="skeptic", rests_on=["SK-1"])]}
    report = cf.check(data, SEEDED)
    assert report["venues"] == ["bioinformatics", "bmc-bioinformatics"]
    assert report["venues_missing"] == {"skeptic": ["bmc-bioinformatics"]}
    assert "gave no recommendation for bmc-bioinformatics" in cf.to_markdown(report)


def test_after_adjudication_a_recommendation_resting_on_a_refuted_finding_is_flagged() -> None:
    findings = [_adjudicated("F1", LEAK),
                _adjudicated("F2", "Features were standardised on the training set.", verdict="refuted",
                             defence_quote=DEFENCE, triage=None),
                _adjudicated("F3", CAUSAL, verdict="downgraded", severity="optional")]
    report = cf.check({"findings": findings, "reports": [_report(rests_on=["F1", "F2", "F3"])]}, SEEDED,
                      adjudicated=True)
    rec = _only_report(report)["recommendations"][0]
    assert rec["challenged"] == {"F2": "refuted", "F3": "downgraded"}
    md = cf.to_markdown(report)
    assert "the defence refuted F2" in md and "leave the recommendation as the referee gave it" in md
    before = cf.check({"findings": [_finding()], "reports": [_report()]}, SEEDED)  # nothing to flag before the defence
    assert _only_report(before)["recommendations"][0]["challenged"] == {}


def test_after_adjudication_each_referees_findings_fill_the_sections_of_its_report() -> None:
    findings = [
        _adjudicated("science", LEAK),
        _adjudicated("wording", CAUSAL, severity="optional", triage="misread-risk", route="fixable-in-text"),
        _adjudicated("unsure", "the ClinVar release of 6 January 2025", severity="uncertain"),
        _adjudicated("archive", "VarRank 1.2.0 is available at", stage="final", route="fixable-in-text"),
        _adjudicated("answered", "Features were standardised on the training set.", verdict="refuted",
                     defence_quote=DEFENCE, triage=None),
        _adjudicated("other", "On 4,812 held-out ClinVar missense variants", seat="skeptic"),
    ]
    report = cf.check(findings, SEEDED, adjudicated=True)
    assert report["summary"]["fail"] == 0
    assert report["by_referee"] == {
        "evidence-statistics": {"major": ["science"], "minor": ["wording", "archive"], "questions": ["unsure"]},
        "skeptic": {"major": ["other"], "minor": [], "questions": []},
    }
    assert cf.check(findings, SEEDED)["by_referee"] is None  # only after adjudication
    assert "## What each referee's report contains" in cf.to_markdown(report)


def test_cli_exits_one_when_a_report_fails_its_contract(tmp_path: Path) -> None:
    data = {"findings": [_finding()], "reports": [_report(recommendation="weak accept")]}
    result = runner.invoke(cf.app, [str(_write_json(tmp_path, data)), str(SEEDED)])
    assert result.exit_code == 1 and "Reports that do not meet the contract" in result.output
    data["reports"] = [_report()]
    assert runner.invoke(cf.app, [str(_write_json(tmp_path, data)), str(SEEDED)]).exit_code == 0


# --- the Markdown report: quoted passages, URLs and plain words, never bare line references -----------------

def _no_bare_locations(md: str) -> None:
    """No "L169", no "file.md:12", and every "line N" sits inside parentheses after a quoted passage."""
    assert not re.search(r"\bL\d+\b", md), md
    assert not re.search(r"\b[\w-]+\.(?:md|tex|txt):\d+", md), md
    for m in re.finditer(r"\blines? \d+", md):
        opening = md.rfind("(", 0, m.start())
        assert opening > md.rfind(")", 0, m.start()) and md[:opening].rstrip().endswith('"'), md[m.start() - 80:m.end()]


def test_the_markdown_quotes_each_passage_with_its_section() -> None:
    findings = [_finding(id=key, quote=quote, location=f"Section of {key}", concern=CONCERNS[key][0])
                for key, quote, _, _ in PLANTED]
    report = cf.check(findings, SEEDED)
    md = cf.to_markdown(report)
    _no_bare_locations(md)
    for f in report["findings"]:
        excerpt = f["quote"]["excerpt"]
        assert f'In {f["location"]}, the manuscript reads "{excerpt}" (line {f["quote"]["line"]}).' in md
        # the excerpt shows the quoted words, in bold whenever it also shows some of the sentence around them
        words = cf._squash(f["quote_text"]).strip()
        assert words in excerpt.replace("**", "") or words.split()[0] in excerpt
        assert ("**" in excerpt) is (excerpt.replace("**", "") != words)
    leak = next(f for f in report["findings"] if f["id"] == "leakage")
    assert leak["quote"]["excerpt"] == "We assigned ClinVar variants at random to training (80%) and test (20%) sets."
    count = next(f for f in report["findings"] if f["id"] == "n-mismatch")
    assert count["quote"]["excerpt"].startswith("**On 4,812 held-out ClinVar missense variants**, VarRank reached")
    build = next(f for f in report["findings"] if f["id"] == "genome-build")
    assert build["quote"]["excerpt"].startswith("|") and "**rs429358 | chr19:45411941**" in build["quote"]["excerpt"]


def test_a_long_passage_is_cut_between_words_around_the_quote() -> None:
    before, span, after = "word " * 60, "the quoted part", " more" * 60
    text = cf.cut_around(before, span, after, width=80)
    assert text.startswith("[...] word") and text.endswith("more [...]") and "**the quoted part**" in text
    assert len(text) <= 80 + len("[...] ") + len(" [...]") + 4
    assert cf.cut_around("", "x " * 200, "", width=40).count("[...]") == 1


@pytest.mark.parametrize("identifier,url", [
    ("10.1038/ng.2892", "https://doi.org/10.1038/ng.2892"),
    ("doi:10.1038/ng.2892", "https://doi.org/10.1038/ng.2892"),
    ("https://doi.org/10.1038/ng.2892", "https://doi.org/10.1038/ng.2892"),
    ("PMID: 24487276", "https://pubmed.ncbi.nlm.nih.gov/24487276/"),
    ("24487276", "https://pubmed.ncbi.nlm.nih.gov/24487276/"),
    ("arXiv:2403.19087", "https://arxiv.org/abs/2403.19087"),
    ("2403.19087v2", "https://arxiv.org/abs/2403.19087v2"),
    ("https://github.com/example/varrank", "https://github.com/example/varrank"),
])
def test_prior_work_identifiers_are_rendered_as_urls(identifier: str, url: str) -> None:
    prior = [{"citation": "Kircher M et al. Nature Genetics 2014", "identifier": identifier, "status": "verified"}]
    report = cf.check([_finding(concern=NOVELTY, prior_work=prior)], SEEDED)
    md = cf.to_markdown(report)
    assert f"Kircher M et al. Nature Genetics 2014, {url}. Its identifier resolved to this work" in md
    assert report["findings"][0]["prior_work"][0]["identifier"] == identifier  # the JSON keeps what was given


def test_an_isbn_or_a_missing_identifier_is_named_in_words() -> None:
    prior = [{"citation": "A textbook", "identifier": "978-0-12-345678-9", "status": "unverified"},
             {"citation": "An unpublished tool", "status": "unverified"}]
    md = cf.to_markdown(cf.check([_finding(concern=NOVELTY, prior_work=prior)], SEEDED))
    assert "A textbook (978-0-12-345678-9). Its identity is not confirmed, because the identifier could not" in md
    assert "An unpublished tool, with no identifier. Its identity is not confirmed, because it has no identifier." in md


def test_statuses_are_plain_words_in_the_markdown(tmp_path: Path) -> None:
    findings = [_finding(id="F2", quote="Table S1 lists 4,182 test variants", source="S1.md"),
                _finding(id="F3", quote="VarRank was validated in three cohorts")]
    report = cf.check(findings, SEEDED)
    md = cf.to_markdown(report)
    assert [f["contract"] for f in report["findings"]] == ["not_assessed", "fail"]  # the JSON keeps its tokens
    assert "not_assessed" not in md
    assert "**F2**, raised by a simulated referee (evidence-statistics), could not be checked." in md
    assert "the file S1.md was not supplied" in md
    assert ('**F3**, raised by a simulated referee (evidence-statistics), failed. It quotes "VarRank was validated '
            'in three cohorts"') in md
    _no_bare_locations(md)


def test_seat_names_only_follow_a_plain_description_in_parentheses() -> None:
    """A seat name is the panel's working vocabulary ("Writing for the authors"): in the Markdown it appears only
    in parentheses after "simulated referee", in groups, not-yet findings, warnings and strengths alike."""
    findings = [_finding(id="F1", seat="skeptic"),
                _finding(id="F2", seat="champion", quote=CAUSAL, concern="The method is too simple for the claim."),
                _finding(id="F3", seat="claims-novelty", quote="VarRank was validated in three cohorts")]
    strengths = [{"seat": "reproducibility", "location": "Methods, Model", "note": "A clear model description.",
                  "quote": "VarRank was validated in three cohorts"}]
    report = cf.check({"findings": findings, "strengths": strengths}, SEEDED)
    assert [f["contract"] for f in report["findings"]] == ["pass", "pass", "fail"] and report["findings"][1]["warnings"]
    md = cf.to_markdown(report)
    for seat in ("skeptic", "champion", "claims-novelty", "reproducibility"):
        hits = [m.start() for m in re.finditer(re.escape(seat), md)]
        assert hits, seat
        for at in hits:
            opening = md.rfind("(", 0, at)
            context = md[max(0, opening - 60):at + len(seat) + 10]
            assert opening > md.rfind(")", 0, at), context
            assert md[:opening].rstrip().endswith(("simulated referee", "simulated referees")), context


def _adjudicated(id: str, quote: str, **fields: Any) -> dict[str, Any]:
    base = {"verdict": "confirmed", "triage": "substance", "verdict_evidence": "The quoted text shows it."}
    return _finding(id=id, quote=quote, concern=f"Concern {id} about a separate point entirely.", **{**base, **fields})


def test_after_adjudication_groups_follow_the_order_the_authors_work_in() -> None:
    findings = [
        _adjudicated("venue", "the ClinVar release of 6 January 2025", route="venue", triage="substance",
                     severity="optional"),
        _adjudicated("wording", CAUSAL, triage="misread-risk", route="fixable-in-text"),
        _adjudicated("science", LEAK, route="author-required", cost="reanalysis"),
        _adjudicated("count", "On 4,812 held-out ClinVar missense variants", hand_to="manuscript-integrity-check",
                     route="fixable-in-text"),
        _adjudicated("answered", "Features were standardised on the training set.", verdict="refuted",
                     defence_quote=DEFENCE, triage=None),
    ]
    report = cf.check(findings, SEEDED, adjudicated=True)
    assert report["summary"]["fail"] == 0
    assert [g["stage"] for g in report["groups"]] == ["now", "writing", "journal", "other-checks", "answered"]
    md = cf.to_markdown(report)
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == ["## Fix now: the science and the evidence", "## Then the writing",
                        "## Once you have chosen the journal", "## Also found, belongs to other checks",
                        "## Answered by the paper (refuted by the defence pass)",
                        "## What each referee's report contains"]
    assert "As proposed, it needs new work from the authors, at the cost of a reanalysis of existing data." in md
    assert "It belongs to manuscript-integrity-check; mention it there rather than as a referee concern." in md
    _no_bare_locations(md)


def test_end_stage_packaging_is_never_a_current_concern() -> None:
    """An archive record or declaration is listed for the end, even when it belongs to another check."""
    findings = [
        _adjudicated("archive", "VarRank 1.2.0 is available at", stage="final", hand_to="manuscript-reporting-check",
                     route="fixable-in-text"),
        _adjudicated("science", LEAK, route="author-required"),
    ]
    report = cf.check(findings, SEEDED, adjudicated=True)
    assert [(g["findings"], g["stage"]) for g in report["groups"]] == [(["science"], "now"), (["archive"], "final")]
    md = cf.to_markdown(report)
    assert md.index("## Fix now") < md.index("## Before submission, once the code is final")
    assert "## Also found, belongs to other checks" not in md


def test_points_for_other_checks_come_before_the_end_stage_group() -> None:
    """A number that disagrees is current work for another check; an archive record waits for the end. The
    current-work groups come first ("Order the work by when it can be done"), so the end-stage group is last."""
    findings = [
        _adjudicated("archive", "VarRank 1.2.0 is available at", stage="final", route="fixable-in-text"),
        _adjudicated("count", "On 4,812 held-out ClinVar missense variants", hand_to="manuscript-integrity-check",
                     route="fixable-in-text"),
        _adjudicated("science", LEAK, route="author-required"),
    ]
    report = cf.check(findings, SEEDED, adjudicated=True)
    assert [(g["findings"], g["stage"]) for g in report["groups"]] == [
        (["science"], "now"), (["count"], "other-checks"), (["archive"], "final")]
    md = cf.to_markdown(report)
    assert md.index("## Fix now") < md.index("## Also found, belongs to other checks") < md.index(
        "## Before submission, once the code is final")


def test_a_latex_excerpt_reads_as_the_sentence_a_reader_sees(tmp_path: Path) -> None:
    quote = "VarRank is the first tool to combine conservation and frequency in 12% of cases"
    f = _only(cf.check([_finding(quote=quote)], _doc(tmp_path, LATEX, "paper.tex")))
    assert f["quote"]["excerpt"] == ("**VarRank is the first tool to combine conservation \\cite{kircher2014} and "
                                     "frequency in 12% of cases**.")


def test_the_schema_example_passes_against_the_seeded_fixture() -> None:
    text = (SKILL / "references" / "finding-schema.md").read_text(encoding="utf-8")
    example = json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))
    report = cf.check(example, SEEDED)
    assert report["summary"]["fail"] == report["summary"]["not_assessed"] == 0
    assert report["summary"]["strengths_not_anchored"] == report["summary"]["reports_failed"] == 0
    assert report["summary"]["reports"] == 1


# --- skill files, fixtures and eval cases ---------------------------------------------------------------------

def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def test_relative_links_in_the_skill_resolve_with_their_anchors() -> None:
    for md in SKILL.rglob("*.md"):
        for target in re.findall(r"\]\(([^)\s]+)\)", md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            dest = (md.parent / path).resolve() if path else md
            assert dest.exists(), f"{md.relative_to(ROOT)} links to missing {target}"
            if anchor and dest.suffix == ".md":
                headings = re.findall(r"^#+\s+(.*)$", dest.read_text(encoding="utf-8"), re.M)
                assert anchor in {_slug(h) for h in headings}, f"{md.relative_to(ROOT)}: no #{anchor} in {path}"


def test_the_fixture_pair_is_one_paper_with_the_planted_text_repaired() -> None:
    seeded_text, clean_text = SEEDED.read_text(encoding="utf-8"), CLEAN.read_text(encoding="utf-8")
    ratio = difflib.SequenceMatcher(None, seeded_text.split(), clean_text.split(), autojunk=False).ratio()
    assert ratio > 0.85  # the same paper, not two papers
    seeded_flat, clean_flat = " ".join(seeded_text.split()), " ".join(clean_text.split())
    for key, quote, _, _ in PLANTED:
        assert quote in seeded_flat and quote not in clean_flat, key


@pytest.mark.parametrize("path", ["manuscript-record.yaml", "ladder/manuscript-record.yaml"])
def test_the_record_fixtures_match_the_seeded_manuscript(path: str) -> None:
    record = yaml.safe_load((FIXTURES / path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(SEEDED.read_bytes()).hexdigest()
    assert record["manuscript"] == SEEDED.name
    assert {c["manuscript_sha256"] for c in record["checks"]} == {digest}


def test_the_ladder_fixture_has_no_chosen_venue_and_more_rungs_than_the_panel_reviews_for() -> None:
    """The ladder case expects the top three rungs and not the fourth, each a key the venue catalogue knows."""
    record = yaml.safe_load((FIXTURES / "ladder" / "manuscript-record.yaml").read_text(encoding="utf-8"))
    known = yaml.safe_load((ROOT / "skills" / "manuscript-integrity-check" / "references" / "venues.yaml")
                           .read_text(encoding="utf-8"))["venues"]
    rungs = record["ladders"]["journals"]
    assert "venue" not in record and len(rungs) > 3 and set(rungs) <= set(known)
    with_venue = yaml.safe_load((FIXTURES / "manuscript-record.yaml").read_text(encoding="utf-8"))
    assert {k: v for k, v in with_venue.items() if k != "venue"} == \
        {k: v for k, v in record.items() if k not in ("priorities", "ladders")}  # otherwise the same record


def test_the_adjudication_fixture_quotes_the_seeded_manuscript() -> None:
    """The partly-answered eval case starts from these files: each finding meets the seat-stage contract, the
    defender answered each one once, and every defence quote occurs in seeded.md."""
    folder = FIXTURES / "adjudication"
    findings = json.loads((folder / "findings.json").read_text(encoding="utf-8"))
    defence = json.loads((folder / "defence.json").read_text(encoding="utf-8"))
    report = cf.check(findings, SEEDED)
    assert report["summary"]["pass"] == report["summary"]["findings"] == len(defence)
    assert report["summary"]["strengths_not_anchored"] == 0
    assert [f["id"] for f in findings["findings"]] == [d["id"] for d in defence]
    sources = cf._load_sources(SEEDED, [])
    for d in defence:
        assert d["answer"] in {"answered", "partly answered", "not answered"}, d["id"]
        if d["answer"] == "not answered":
            assert d["looked_in"] and "defence_quote" not in d, d["id"]
        else:
            assert cf._check_quote(d["defence_quote"], None, sources, "defence_quote")["status"] == "verified", d["id"]


def test_eval_cases_are_well_formed() -> None:
    cases = yaml.safe_load((ROOT / "evals" / "manuscript-peer-review.yaml").read_text(encoding="utf-8"))
    assert 3 <= len(cases) <= 7
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert {"id", "skill", "prompt", "files", "rubric", "fail_if"} <= set(case), case["id"]
        assert case["rubric"] and case["fail_if"]
        for f in case["files"]:
            assert (ROOT / "evals" / f).is_file(), f
    used = {f for c in cases for f in c["files"]}
    assert {"fixtures/manuscript-peer-review/seeded.md", "fixtures/manuscript-peer-review/clean.md"} <= used
    seeded_case = next(c for c in cases if c["files"] == ["fixtures/manuscript-peer-review/seeded.md"]
                       and c["skill"] == "manuscript-peer-review" and c["planted"])
    assert len(seeded_case["planted"]) == len(PLANTED)


def test_the_report_template_uses_the_stage_groups_of_the_script_and_the_shared_rule() -> None:
    """output-format.md's template, SKILL.md and check_findings.py name the four stage groups of "Order the work by
    when it can be done" in the same words and order, so a report and the script's working file line up."""
    rule = (ROOT / "skills" / "manuscript-integrity-check" / "references" / "author-priorities.md").read_text(
        encoding="utf-8")
    labels = re.findall(r'"([^"]+)"', " ".join(re.search(r"Label each group in the report \((.*?)\)", rule,
                                                         re.S).group(1).split()))
    titles = [title for key, title in cf.STAGES if key in cf.STAGE_KEYS]
    assert len(labels) == len(titles) == 4
    assert all(title.startswith(label) for label, title in zip(labels, titles)), (labels, titles)
    template = re.search(r"## Template\n\n```markdown\n(.*?)\n```", (SKILL / "references" / "output-format.md")
                         .read_text(encoding="utf-8"), re.S).group(1)
    headings = re.findall(r"^#{2,3} (.+)$", template, re.M)
    assert [h for h in headings if h.startswith(tuple(labels))] == titles
    script_order = [title for _, title in cf.STAGES]
    assert [h for h in headings if h in script_order] == [t for t in script_order if t in headings]
    # The referees' reports come first; the authors' list of what to fix opens with current work.
    part1, part2 = headings.index("Part 1: the referees' reports"), headings.index("Part 2: what to fix, in order")
    assert part1 < part2 and headings.index(titles[0]) == part2 + 1
    referees = [h for h in headings if h.startswith("Referee ")]
    assert len(referees) == 3 and all(part1 < headings.index(h) < part2 for h in referees)
    skill = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
    positions = [skill.find(f'"{title}"') for title in titles]
    assert -1 not in positions and positions == sorted(positions), positions


GATE = re.compile(r"ask(?:s)? the user to confirm|confirm that the user is|do not process the manuscript|"
                  r"\bread\b.{0,80}before opening the manuscript|only when the venue'?s review process|"
                  r"in invited-referee mode it is not allowed", re.IGNORECASE)


def test_reviewing_someone_elses_paper_has_no_authorisation_gate() -> None:
    """The user decides what the skill is applied to (author-priorities.md): no file of the skill asks them to
    confirm their role or makes the venue's reviewer rules a condition, and the eval fails a run that does."""
    for md in SKILL.rglob("*.md"):
        text = " ".join(md.read_text(encoding="utf-8").split())
        assert not GATE.search(text), f"{md.relative_to(ROOT)}: {GATE.search(text).group(0)!r}"
    cases = yaml.safe_load((ROOT / "evals" / "manuscript-peer-review.yaml").read_text(encoding="utf-8"))
    case = next(c for c in cases if c["id"] == "peer-review-invited-referee-01")
    assert not any(re.search(r"\basks? the user to confirm\b", item, re.I) for item in case["rubric"])
    assert any(re.search(r"\bwithout first asking\b", item) for item in case["rubric"])
    assert any(re.search(r"\bAsks the user to confirm\b", item) for item in case["fail_if"])
    assert any(re.search(r"\bat most one short sentence\b", item) for item in case["rubric"])
