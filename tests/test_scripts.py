"""Offline tests for the plugin's scripts. Run with `uv run pytest`."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # pydantic resolves the deferred annotations through sys.modules
    spec.loader.exec_module(module)
    return module


scan = _load("scan", SKILLS / "manuscript-integrity-check" / "scripts" / "scan.py")
guard = _load("guard", SKILLS / "manuscript-journal-adapt" / "scripts" / "guard.py")
venues = _load("venues", SKILLS / "manuscript-journal-adapt" / "scripts" / "venues.py")

PAPER = """# A Tool

## Abstract

We annotate a genome in 40 s.

## Methods

Certainly, here is the revised methods section. Variants were joined as in earlier work
(Tandy-Connor et al., 2018; O'Daniel et al., 2025; Smith et al., 2019). TODO add numbers.

## Code availability

https://github.com/example/tool, archived at Zenodo (10.5281/zenodo.1).

## Competing interests

None.

## Funding

None.

## Author contributions

A.B. wrote the paper.

## References

Tandy-Connor, S., et al. (2018). False-positive results released by direct-to-consumer genetic tests. Genetics in Medicine.
O’Daniel, J. M., et al. (2025). Direct-to-Consumer Genetic Testing. NEJM Evidence.
Never, C. I. (2020). An entry the text never cites. Journal of Nothing.
"""


@pytest.fixture()
def paper(tmp_path: Path) -> Path:
    p = tmp_path / "paper.md"
    p.write_text(PAPER, encoding="utf-8")
    return p


def _checks(report: scan.Report, check: str) -> list[scan.Finding]:
    return [f for f in report.findings if f.check == check]


def test_chatbot_leftover_is_a_blocker(paper: Path) -> None:
    report = scan.scan(paper, online=False, search_unidentified=False)
    leftovers = _checks(report, "chatbot-leftover")
    assert [f.severity for f in leftovers] == [scan.Severity.blocker]
    assert leftovers[0].line == PAPER.splitlines().index(
        next(l for l in PAPER.splitlines() if l.startswith("Certainly"))) + 1


def test_missing_declarations_are_exactly_the_absent_ones(paper: Path) -> None:
    report = scan.scan(paper, online=False, search_unidentified=False)
    missing = {f.message.split(" statement")[0]: f.severity for f in _checks(report, "declarations")}
    # No sign of AI use in the text or history: a missing AI statement is minor, not a desk-reject trigger.
    assert missing == {"No 'AI-use disclosure'": scan.Severity.minor, "No 'Data availability'": scan.Severity.major}


def test_missing_ai_disclosure_is_a_blocker_when_the_text_mentions_ai(tmp_path: Path) -> None:
    p = tmp_path / "paper.md"
    p.write_text(PAPER.replace("A.B. wrote the paper.", "A.B. wrote the paper with ChatGPT."), encoding="utf-8")
    report = scan.scan(p, online=False, search_unidentified=False)
    ai = [f for f in _checks(report, "declarations") if "AI-use" in f.message]
    assert [f.severity for f in ai] == [scan.Severity.blocker]


def test_latex_bibtex_references_and_cite_keys(tmp_path: Path) -> None:
    (tmp_path / "refs.bib").write_text(
        "@article{lambert2021,\n  author = {Lambert, Samuel A.},\n  title = {The {Polygenic} Score Catalog},\n"
        "  journal = {Nature Genetics},\n  year = {2021},\n  doi = {10.1038/s41588-021-00783-5}\n}\n"
        "@misc{tool2026,\n  author = {Doe, Jane},\n  title = {A tool},\n  year = {2026},\n"
        "  eprint = {2403.19087},\n  archivePrefix = {arXiv}\n}\n", encoding="utf-8")
    tex = tmp_path / "paper.tex"
    tex.write_text("\\section{Intro}\nScores \\citep{lambert2021,missing2020} and a tool \\cite{tool2026}.\n"
                   "\\bibliography{refs}\n", encoding="utf-8")
    report = scan.scan(tex, online=False, search_unidentified=False)
    assert [(r.doi, r.arxiv) for r in report.references] == [("10.1038/s41588-021-00783-5", None), (None, "2403.19087")]
    assert [f.excerpt for f in _checks(report, "citations") if "not in the bibliography" in f.message] == ["missing2020"]
    assert not [f for f in _checks(report, "references") if "No references" in f.message]


def test_citation_consistency_handles_hyphens_and_curly_apostrophes(paper: Path) -> None:
    report = scan.scan(paper, online=False, search_unidentified=False)
    cited_missing = {f.message.split("'")[1] for f in _checks(report, "citations") if "has no bibliography" in f.message}
    never_cited = {f.excerpt.split(",")[0] for f in _checks(report, "citations") if "never cited" in f.message}
    assert cited_missing == {"Smith 2019"}  # Tandy-Connor and O'Daniel/O’Daniel resolve
    assert never_cited == {"Never"}


@pytest.mark.parametrize("venue, words, expected", [
    ("bioinformatics", 6100, scan.Severity.blocker),  # > 1.2 × 5000
    ("bioinformatics", 5500, scan.Severity.major),
    ("bioinformatics", 4000, None),
    ("bioinformatics-note", 2700, scan.Severity.major),  # inherits the rule, own limit 2600
])
def test_venue_body_limits(venue: str, words: int, expected: scan.Severity | None) -> None:
    found = [f for f in scan._venue_findings([], words, 100, venue, "zenodo") if f.check == "venue"]
    assert [f.severity for f in found] == ([expected] if expected else [])


def test_unrecorded_venue_limits_are_not_assessed_not_passed() -> None:
    found = [f for f in scan._venue_findings([], 99999, 9999, "genome-biology", "zenodo") if f.check == "venue"]
    assert len(found) == 1 and found[0].severity == scan.Severity.info and "not checked" in found[0].message


def test_git_ai_trailers_are_counted(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "T")
    f = tmp_path / "paper.md"
    for i, trailer in enumerate(["", "\n\nCo-Authored-By: Claude Opus <noreply@anthropic.com>"]):
        f.write_text(f"v{i}\n", encoding="utf-8")
        git("add", "paper.md")
        git("commit", "-q", "-m", f"edit {i}{trailer}")
    found = scan._git_findings(f)
    assert len(found) == 1 and found[0].message.startswith("1 of 2 commits")


BEFORE = """Annotating a 4.5 GB VCF took 40 s on GRCh38 (Lambert et al., 2021). It is important to note that this matters.

The APOE variant rs429358 is associated with lower longevity in some cohorts, and the effect may not replicate.
"""


def test_guard_passes_a_wording_only_edit() -> None:
    after = BEFORE.replace("It is important to note that this matters.", "This matters.")
    report = guard.compare(BEFORE, after)
    assert report["protected"] == {} and report["watched"] == {}


def test_guard_catches_content_drift() -> None:
    after = ("Annotating a 4.6 GB VCF took 40 s on GRCh38. This matters.\n\n"
             "The APOE variant rs429358 causes lower longevity in cohorts, and the effect replicates.\n")
    report = guard.compare(BEFORE, after)
    assert report["protected"]["numbers"]["added"] == {"4.6 GB": 1}
    assert "(Lambert et al., 2021)" in report["protected"]["citations"]["removed"]
    assert set(report["watched"]["hedges"]["removed"]) == {"some", "may"}
    assert report["watched"]["negations"]["removed"] == {"not": 1}
    assert report["watched"]["causal"]["added"] == {"causes": 1}


def test_guard_ignores_revision_markers() -> None:
    marked = "<!-- @rev N1 rounds=1 by=x:2026-01-01 -->" + BEFORE + "<!-- @/rev N1 -->"
    assert guard.compare(BEFORE, marked)["protected"] == {}


def test_venues_resolve_inheritance_and_have_string_vocabularies() -> None:
    _, resolved = venues.load_venues()
    assert resolved["bioinformatics-note"]["writing_help"] == "banned_drafting"
    assert resolved["bioinformatics-note"]["limits"]["body_words"] == 2600
    for key, v in resolved.items():
        for field in ("writing_help", "prompts", "screening", "tracking"):
            assert v.get(field) is None or isinstance(v[field], str), (key, field)  # YAML 'no' is a boolean
        if v.get("writing_help") is not None:
            assert v["writing_help"] in venues.WRITING_COST, key


def test_friction_orders_the_policy_extremes() -> None:
    _, resolved = venues.load_venues()
    score = {k: venues.friction(v)[0] for k, v in resolved.items()}
    assert score["genome-research"] < score["bioinformatics"] < score["gigascience"]
    assert venues.verdict(resolved["bioinformatics"], venues.AiUse.drafting).startswith("incompatible")


def test_venues_yaml_parses_and_is_dated() -> None:
    raw = yaml.safe_load((SKILLS / "manuscript-integrity-check" / "references" / "venues.yaml").read_text())
    assert raw["checked"] is not None and raw["venues"]


profile = _load("profile", SKILLS / "manuscript-journal-adapt" / "scripts" / "profile.py")

SLOPPY = """# Intro

In recent years, polygenic scores have garnered significant attention. It is important to note that they play a pivotal role in the evolving landscape of precision medicine, highlighting the importance of genetics. Furthermore, they hold great promise. Overall, these findings underscore the importance of further research.

The pipeline annotated 4 genomes in 40 s each (Table 2), using 3.1 GB of memory, and agreed with the reference implementation on 1,204 of 1,206 scores [3].

## References

Smith, J. (2020). It is important to note that this line is a reference and must not be profiled.
"""

AUTHOR_SAMPLE = """We sequenced 12 samples on two flow cells. Coverage was 31x on average (range 24-38x) and we dropped one
sample with a contamination estimate above 3%. The variant caller was run with default settings except for the
minimum base quality, which we raised to 20 because the first run produced 40% more false positives in the
truth-set regions than the vendor reported.

We then compared our calls with the GIAB truth set. Recall was 0.97 for SNVs and 0.91 for indels; most missed
indels were in homopolymers longer than 8 bp, which the short reads could not span."""


def test_profile_ranks_the_sloppy_paragraph_and_skips_references() -> None:
    doc = profile.profile_text(SLOPPY, False, profile.load_smells(), profile.load_kobak())
    paras = doc["paragraphs"]
    assert len(paras) == 2  # the references section is not profiled
    sloppy, clean = paras
    assert sloppy["smells_per_100_words"] > clean["smells_per_100_words"] == 0
    assert {"A1", "A2", "A3", "A8", "A9", "B5", "C5"} <= set(sloppy["hits"])
    assert sloppy["anchors"] == 0 and clean["anchors"] >= 5


def test_profile_counts_latex_citations_as_anchors_and_skips_tables() -> None:
    tex = ("Our method was faster than the baseline \\citep{smith2020} on all genomes.\n\n"
           "\\begin{table}\nIt is important to note that this is inside a table.\n\\end{table}\n")
    doc = profile.profile_text(tex, True, profile.load_smells(), profile.load_kobak())
    assert [p["anchors"] for p in doc["paragraphs"]] == [1]
    assert doc["smell_totals"] == {}


def test_profile_baseline_flags_departures_from_the_authors_own_writing() -> None:
    smells, kobak = profile.load_smells(), profile.load_kobak()
    doc = profile.profile_text(SLOPPY, False, smells, kobak)
    base = profile.profile_text(AUTHOR_SAMPLE, False, smells, kobak)
    departed = {r["measure"] for r in profile.compare(doc, base) if r["departs"]}
    assert {"smells_per_1000_words", "llm_vocabulary_per_1000_words",
            "connector_starts_per_100_sentences"} <= departed


def test_smell_patterns_compile_and_match_the_catalogue_ids() -> None:
    smells = profile.load_smells()
    catalogue = (SKILLS / "manuscript-journal-adapt" / "references" / "llm-smells.md").read_text()
    for sid in smells:
        assert f"### {sid}." in catalogue, sid


@pytest.mark.parametrize("text, flagged", [
    ("Recall was high: 12 of 40 (30%) variants.", False),
    ("Recall was high: 12 of 40 (35%) variants.", True),
    ("We found 1,204/1,206 (99.8%) concordant scores.", False),
    ("We found 1,204/1,206 (99.9%) concordant scores.", True),
    ("Of these, 7 out of 9 samples (77.8 %) passed.", False),
    ("Of these, 7 out of 9 samples (78 %) passed.", False),  # rounds correctly at 0 decimals
    ("Of these, 7 out of 9 samples (77.7 %) passed.", True),
])
def test_percentages_are_recomputed_from_their_counts(text: str, flagged: bool) -> None:
    assert bool(scan._percentages([text])) is flagged


def test_readiness_verdict_names_the_worst_tier(paper: Path) -> None:
    report = scan.scan(paper, online=False, search_unidentified=False)
    blockers = sum(f.severity == scan.Severity.blocker for f in report.findings)
    assert blockers > 0 and f"**Readiness:** not ready: {blockers} desk-reject trigger" in scan.to_markdown(report)


@pytest.mark.parametrize("abstract, severity", [
    ("Across 12 datasets the method found more true variants than the next-best tool and ran about four "
     "times faster (recall 0.94 vs 0.88).", None),
    ("Our method achieved 94.3% recall (95% CI 92.1–96.0), 91.7% precision, an F1 of 0.930 and an AUROC of "
     "0.971 across 12 datasets (n = 48,213), running 4.2× faster (40.1 s vs 168.4 s).", scan.Severity.major),
    ("Recall was 94.3%, precision 91.7%, F1 0.930, AUROC 0.971 and runtime 40.1 s.", None),
    ("Recall was 94.3%, precision 91.7%, F1 0.930, AUROC 0.971, runtime 40.1 s, memory 3.1 GB and 4.2× faster.",
     scan.Severity.minor),
])
def test_abstract_metric_dump(abstract: str, severity: scan.Severity | None) -> None:
    found = scan._abstract_metric_dump(["# Paper", "", "## Abstract", "", abstract, "", "## Introduction"])
    assert [f.severity for f in found] == ([severity] if severity else [])
