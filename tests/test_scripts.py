"""Offline tests for the plugin's scripts. Run with `uv run pytest`."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import httpx
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
guard = _load("guard", SKILLS / "manuscript-prose-edit" / "scripts" / "guard.py")
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
    # No evidence of a disclosure obligation: do not ask the author for an unnecessary AI statement.
    assert missing == {"No 'Data availability'": scan.Severity.major}


@pytest.mark.parametrize("context", [
    "A.B. wrote the paper with ChatGPT.",
    "Earlier studies evaluated ChatGPT; this study used no AI tools.",
    "Spelling and grammar were checked with ChatGPT.",
    "<!-- @rev A1 rounds=1 by=claude:2026-01-01 --> A.B. wrote the paper.",
])
def test_ai_context_without_verified_policy_is_informational(tmp_path: Path, context: str) -> None:
    p = tmp_path / "paper.md"
    p.write_text(PAPER.replace("A.B. wrote the paper.", context), encoding="utf-8")
    report = scan.scan(p, online=False, search_unidentified=False)
    assert not [f for f in _checks(report, "declarations") if "AI-use" in f.message]
    ai = _checks(report, "ai-use")
    assert ai and all(f.severity == scan.Severity.info for f in ai)


def test_ai_mention_does_not_block_author_saving_a_draft(tmp_path: Path) -> None:
    """The default hook must not turn contextual AI mentions into an inferred policy violation."""
    from typer.testing import CliRunner

    precommit = _load("precommit", SKILLS / "manuscript-integrity-check" / "scripts" / "precommit.py")
    p = tmp_path / "draft.md"
    p.write_text("# Background\n\nEarlier work evaluated ChatGPT.\n", encoding="utf-8")
    result = CliRunner().invoke(precommit.app, [str(p)])
    assert result.exit_code == 0, result.output


def test_advisory_hook_reports_blockers_without_blocking_a_commit(paper: Path) -> None:
    from typer.testing import CliRunner

    precommit = _load("precommit", SKILLS / "manuscript-integrity-check" / "scripts" / "precommit.py")
    runner = CliRunner()
    gated = runner.invoke(precommit.app, [str(paper)])
    advisory = runner.invoke(precommit.app, [str(paper), "--advisory"])
    assert gated.exit_code == 1, gated.output
    assert advisory.exit_code == 0, advisory.output
    assert "Serious (then the writing): The phrase 'Certainly, here is' is text a chat interface produces" in \
        advisory.output


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
    assert [f.excerpt for f in _checks(report, "citations") if "has no entry in the bibliography file" in f.message] == ["missing2020"]
    assert not [f for f in _checks(report, "references") if "No references" in f.message]


def test_citation_consistency_handles_hyphens_and_curly_apostrophes(paper: Path) -> None:
    report = scan.scan(paper, online=False, search_unidentified=False)
    cited_missing = {f.message.split("'")[1] for f in _checks(report, "citations") if "has no bibliography" in f.message}
    never_cited = {f.excerpt.split(",")[0] for f in _checks(report, "citations") if "never cited" in f.message}
    assert cited_missing == {"Smith 2019"}  # Tandy-Connor and O'Daniel/O’Daniel resolve
    assert never_cited == {"Never"}


def test_focused_reference_check_shares_audit_findings_without_other_checks(paper: Path) -> None:
    focused = scan.check_references(paper, online=False, search_unidentified=False)
    audit = scan.scan(paper, online=False, search_unidentified=False)
    assert focused.references == audit.references
    assert focused.findings == [f for f in audit.findings if f.check in {"references", "citations"}]
    assert focused.findings and all(f.check in {"references", "citations"} for f in focused.findings)
    assert any(f.check == "chatbot-leftover" for f in audit.findings)


def test_references_only_cli_skips_audit_resources_and_exports_focused_report(
    paper: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    # A bibliography check must remain usable without venue records or style vocabulary.
    monkeypatch.setattr(scan, "VENUES_YAML", tmp_path / "no-venue-catalogue.yaml")
    monkeypatch.setattr(scan, "KOBAK_CSV", tmp_path / "no-style-vocabulary.csv")
    json_path, md_path = tmp_path / "references.json", tmp_path / "references.md"
    result = CliRunner().invoke(scan.app, [str(paper), "--references-only", "--json", str(json_path),
                                         "--md", str(md_path)])
    assert result.exit_code == 0, result.output
    report = json.loads(json_path.read_text())
    assert len(report["references"]) == 3
    assert report["online"] is False
    assert {f["check"] for f in report["findings"]} <= {"references", "citations"}
    assert "not assessed (offline mode)" in md_path.read_text()
    assert "Readiness" not in md_path.read_text()


def test_focused_check_accepts_a_standalone_bibliography(tmp_path: Path) -> None:
    bibliography = tmp_path / "refs.bib"
    bibliography.write_text(
        "@article{lambert2021,\n  author = {Lambert, Samuel A.},\n  title = {The Polygenic Score Catalog},\n"
        "  year = {2021},\n  doi = {10.1038/s41588-021-00783-5}\n}\n", encoding="utf-8")
    report = scan.check_references(bibliography, online=False, search_unidentified=False)
    assert [r.doi for r in report.references] == ["10.1038/s41588-021-00783-5"]
    assert report.findings == []


def test_focused_latex_check_ignores_commented_citations(tmp_path: Path) -> None:
    (tmp_path / "refs.bib").write_text(
        "@article{known,\n  author = {Doe, Jane},\n  title = {An existing article},\n  year = {2020}\n}\n",
        encoding="utf-8")
    manuscript = tmp_path / "paper.tex"
    manuscript.write_text("\\cite{known,missing}\n<!-- \\cite{author-note} -->\n\\bibliography{refs}\n",
                          encoding="utf-8")
    report = scan.check_references(manuscript, online=False, search_unidentified=False)
    assert [f.excerpt for f in report.findings if f.check == "citations"] == ["missing"]


def test_focused_check_reports_an_unreadable_bibliography_format(tmp_path: Path) -> None:
    bibliography = tmp_path / "empty.bib"
    bibliography.write_text("% No entries supplied\n", encoding="utf-8")
    report = scan.check_references(bibliography, online=False, search_unidentified=False)
    assert not report.references
    assert len(report.findings) == 1 and "were not checked" in report.findings[0].message


@pytest.mark.parametrize("focused", [True, False])
def test_online_reference_resolution_is_shared_by_focused_checks_and_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, focused: bool,
) -> None:
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Results\n\nEarlier work supports the method (Doe et al., 2020).\n\n## References\n\n"
        "Doe, J. (2020). A reproducible annotation method. doi:10.1234/example\n", encoding="utf-8")
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"message": {
            "title": ["A reproducible annotation method"], "author": [{"family": "Doe"}],
            "issued": {"date-parts": [[2020]]}, "updated-by": [{"type": "retraction"}],
        }})

    original_client = httpx.Client
    monkeypatch.setattr(scan.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(scan.time, "sleep", lambda _: None)
    checker = scan.check_references if focused else scan.scan
    report = checker(manuscript, online=True, search_unidentified=True)
    assert calls == ["https://api.crossref.org/works/10.1234/example"]
    assert report.references[0].status == "retracted"
    assert report.references[0].resolved_first_author == "Doe"
    assert any(f.check == "references" and "retracted" in f.message for f in report.findings)


@pytest.mark.parametrize("venue, words, expected", [
    ("bioinformatics", 6100, scan.Severity.major),  # over the limit; the live page states no return rule
    ("bioinformatics", 5500, scan.Severity.major),
    ("bioinformatics", 4000, None),
    ("bioinformatics-note", 2700, scan.Severity.major),  # own limit 2600
])
def test_venue_body_limits(venue: str, words: int, expected: scan.Severity | None) -> None:
    found = [f for f in scan._venue_findings([], words, 100, venue, "zenodo") if f.check == "venue"]
    assert [f.severity for f in found] == ([expected] if expected else [])


@pytest.mark.parametrize("words, expected", [
    (6100, scan.Severity.blocker),  # > 1.2 × 5000: a recorded return rule makes it a blocker
    (5500, scan.Severity.major),
    (4000, None),
])
def test_a_recorded_return_rule_makes_overlength_a_blocker(
        monkeypatch: pytest.MonkeyPatch, words: int, expected: scan.Severity | None) -> None:
    limits = {"synthetic": {"abstract_words": 150, "body_words": 5000, "over_limit_return": 1.2}}
    monkeypatch.setattr(scan, "load_venue_limits", lambda: limits)
    found = [f for f in scan._venue_findings([], words, 100, "synthetic", "zenodo") if f.check == "venue"]
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


def test_git_trailers_alone_do_not_make_a_missing_disclosure_a_blocker(tmp_path: Path, paper: Path) -> None:
    """A trailer often marks automation (synced comments, formatting), so it prompts a question, not a blocker."""
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(paper.parent), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "T")
    git("add", paper.name)
    git("commit", "-q", "-m", "sync comments\n\nCo-Authored-By: Claude Opus <noreply@anthropic.com>")
    report = scan.scan(paper, online=False, search_unidentified=False, git=True)
    assert [f.message.split(" ")[0] for f in _checks(report, "ai-use") if "commits touching" in f.message] == ["1"]
    ai = [f for f in _checks(report, "declarations") if "AI-use" in f.message]
    assert ai == []


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
    assert venues.verdict(resolved["bioinformatics"], venues.AiUse.drafting).startswith("A conflict for you to weigh")


def test_venues_yaml_parses_and_is_dated() -> None:
    raw = yaml.safe_load((SKILLS / "manuscript-integrity-check" / "references" / "venues.yaml").read_text())
    assert raw["checked"] is not None and raw["venues"]


profile = _load("style_profile", SKILLS / "manuscript-prose-edit" / "scripts" / "style_profile.py")

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
    catalogue = (SKILLS / "manuscript-prose-edit" / "references" / "llm-smells.md").read_text()
    for sid in smells:
        assert f"### {sid}." in catalogue, sid


def _c1(sentence: str) -> list[str]:
    return [m.group(0) for rx in profile.load_smells()["C1"]["patterns"] for m in rx.finditer(sentence)]


@pytest.mark.parametrize("sentence, flagged", [
    ("Just-DNA-Lite is a research tool, not a clinical pipeline.", True),
    ("Heritability is a population-level statistic, not individual determinism.", True),
    ("The platform mitigates this not by gatekeeping but by making provenance visible.", True),
    ("The tool is not only fast but also accurate.", True),
    ("We kept every sample, whether or not it passed the filter.", False),
    ("Many, if not most, samples were sequenced twice.", False),
    ("The caller is fast but not exact.", False),
    ("Several analyses, not least the ancestry check, were rerun.", False),
    ("Support for GRCh37 is planned, not yet implemented.", False),
    ("Table 2 lists 21 tools, not 22.", False),
    ("The effect was not significant.", False),
])
def test_negation_pivot_patterns_catch_the_appositive_contrast(sentence: str, flagged: bool) -> None:
    assert bool(_c1(sentence)) is flagged, _c1(sentence)


DISCUSSION = """# Paper

## 5. Discussion

### 5.1 Limits

Heritability is a population-level statistic, not individual determinism, and estimates change with the cohort. Most reported variants come from association studies and have not been replicated in other ancestries.

The tool annotates a genome in about a minute on a laptop and keeps every file on that machine.

### 5.2 Privacy

Local execution reduces the need to upload a genome to a hosted analysis service before annotation.
"""


def _doc(text: str, report: bool = False) -> dict:
    return profile.profile_text(text, False, profile.load_smells(), profile.load_kobak(), report)


def test_check_reports_a_pattern_the_edit_added_and_not_one_it_kept_or_moved() -> None:
    before = _doc(DISCUSSION)
    moved = DISCUSSION.replace(
        "Heritability is a population-level statistic, not individual determinism, and estimates change with the "
        "cohort. Most reported variants come from association studies and have not been replicated in other "
        "ancestries.",
        "Most reported variants come from association studies and have not been replicated in other ancestries. "
        "Heritability is a population-level statistic, not individual determinism, and estimates change with the "
        "cohort.")
    assert profile.added_hits(before, _doc(moved)) == []
    added = DISCUSSION.replace("on a laptop and keeps", "on a laptop, not a server, and keeps")
    hits = profile.added_hits(before, _doc(added))
    assert [(h["id"], h["text"], h["section"]) for h in hits] == [("C1", "laptop, not a server",
                                                                    "5. Discussion > 5.1 Limits")]


def test_check_judges_clusters_only_under_the_headings_the_edit_changed() -> None:
    three = DISCUSSION.replace(
        "The tool annotates a genome in about a minute on a laptop and keeps every file on that machine.",
        "The tool is a research prototype, not a clinical product. Its modules are drafts, not curated "
        "references, and its scores are estimates, not diagnoses.")
    result = profile.run_check(_doc(three), None, set())
    assert [(c["id"], c["section"], c["count"]) for c in result["clusters"]] == [
        ("C1", "5. Discussion > 5.1 Limits", 4)]
    assert not result["passed"]
    assert profile.run_check(_doc(three), None, {"C1"})["passed"]  # kept on purpose after review
    edited_elsewhere = three.replace("before annotation", "before it is annotated")
    unchanged_section = profile.run_check(_doc(edited_elsewhere), _doc(three), set())
    assert unchanged_section["sections_checked"] == ["5. Discussion > 5.2 Privacy"]
    assert unchanged_section["clusters"] == [] and unchanged_section["passed"]


def test_report_mode_skips_quotations_address_and_questions() -> None:
    report = ("You wrote “Moreover, the tool plays a pivotal role in precision medicine.” in the Discussion. "
              "Which cohort does it mean, and can you give its size? The sentence names no cohort and no number, "
              "so a referee cannot tell what it rests on.")
    as_paper, as_report = _doc(report), _doc(report, report=True)
    paper_hits = {sid for p in as_paper["paragraphs"] for sid in p["hits"]}
    report_hits = {sid for p in as_report["paragraphs"] for sid in p["hits"]}
    assert {"A1", "C7", "G2"} <= paper_hits
    assert report_hits == set()
    assert as_report["paragraphs"][0]["words"] == as_paper["paragraphs"][0]["words"]  # quotes keep their length


def test_reading_list_carries_every_catalogue_entry_once() -> None:
    catalogue = (SKILLS / "manuscript-prose-edit" / "references" / "llm-smells.md").read_text()
    ids = re.findall(r"^### ([A-K]\d+)\. ", catalogue, re.MULTILINE)
    entries = profile.catalogue_entries()
    assert [e["id"] for e in entries] == ids
    assert all(e["watch"] and len(e["watch"]) <= 400 for e in entries)
    listing = profile.reading_list(entries, profile.load_smells(), report=False)
    assert all(f"({sid}" in listing for sid in ids)
    assert "(C1, counted)" in listing and "(D5)" in listing


def test_check_cli_fails_until_the_pattern_is_rewritten_or_kept(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    before, after = tmp_path / "before.md", tmp_path / "after.md"
    before.write_text(DISCUSSION, encoding="utf-8")
    after.write_text(DISCUSSION.replace("on a laptop and keeps", "on a laptop, not a server, and keeps"),
                     encoding="utf-8")
    run = CliRunner().invoke
    plain = run(profile.app, [str(after)])
    assert plain.exit_code == 0 and "Read the text against every pattern" not in plain.output
    failed = run(profile.app, [str(after), "--before", str(before), "--check"])
    assert failed.exit_code == 1, failed.output
    assert "The edit added negation pivot (C1): “laptop, not a server”" in failed.output
    assert "## Read the text against every pattern" in failed.output and "(D5)" in failed.output
    kept = run(profile.app, [str(after), "--before", str(before), "--check", "--keep", "c1"])
    assert kept.exit_code == 0 and "kept after review, and tell the authors" in kept.output
    clean = run(profile.app, [str(before), "--before", str(before), "--check"])
    assert clean.exit_code == 0 and "The edit added no pattern" in clean.output


@pytest.mark.parametrize("rel", [
    "manuscript-prose-edit/SKILL.md",
    "manuscript-prose-edit/references/prose-edit-contract.md",
    "manuscript-integrity-check/references/author-priorities.md",
    "manuscript-integrity-check/SKILL.md",
    "manuscript-peer-review/references/output-format.md",
    "manuscript-journal-adapt/SKILL.md",
    "manuscript-policy-fit/SKILL.md",
    "manuscript-reviewer-response/SKILL.md",
    "manuscript-improve/SKILL.md",
])
def test_every_skill_that_writes_prose_requires_the_smell_check(rel: str) -> None:
    text = " ".join((SKILLS / rel).read_text(encoding="utf-8").split())
    assert re.search(r"style_profile\.py [^`]*--check", text), rel
    assert "required" in text.lower(), rel


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
    assert blockers > 0 and (f"**Readiness:** not ready. {blockers} finding could get the paper returned without "
                             f"review") in scan.to_markdown(report)


@pytest.mark.parametrize("abstract, severity", [
    ("Across 12 datasets the method found more true variants than the next-best tool and ran about four "
     "times faster (recall 0.94 vs 0.88).", None),
    ("Our method achieved 94.3% recall (95% CI 92.1–96.0), 91.7% precision, an F1 of 0.930 and an AUROC of "
     "0.971 across 12 datasets (n = 48,213), running 4.2× faster (40.1 s vs 168.4 s).", scan.Severity.minor),
    ("Recall was 94.3%, precision 91.7%, F1 0.930, AUROC 0.971 and runtime 40.1 s.", None),
    ("Recall was 94.3%, precision 91.7%, F1 0.930, AUROC 0.971, runtime 40.1 s, memory 3.1 GB and 4.2× faster.",
     scan.Severity.minor),
])
def test_abstract_metric_dump(abstract: str, severity: scan.Severity | None) -> None:
    found = scan._abstract_metric_dump(["# Paper", "", "## Abstract", "", abstract, "", "## Introduction"])
    assert [f.severity for f in found] == ([severity] if severity else [])


@pytest.mark.parametrize("paragraph, chained", [
    ("Genomes are sensitive. Cloud tools require uploads. Uploads create risk. Local processing removes it. "
     "Our tool runs locally. It is fast. It is extensible.", True),
    ("Genomes are sensitive personal data, and most annotation services work only after the genome is uploaded "
     "to their servers. Running the annotation locally removes that step, so we built the tool to run on the "
     "user's machine. It still annotates a genome in under a minute, because the join is restricted to "
     "positions that appear in some module.", False),
    ("We sequenced 12 samples. Coverage was 31x. One sample failed QC.", False),  # three sentences: too few
])
def test_declarative_chain_detection(paragraph: str, chained: bool) -> None:
    assert (profile.declarative_chain(profile.sentences(paragraph)) is not None) is chained


def test_guard_change_rate() -> None:
    text = " ".join(f"word{i}" for i in range(100))
    assert guard.change_rate(text, text) == 0.0
    edited = text.replace("word1 ", "changed ", 1).replace("word50 ", "changed ", 1)
    assert 0 < guard.change_rate(text, edited) <= 0.03
    assert guard.change_rate(text, "entirely new text") > 0.9


detect = _load("detect", SKILLS / "manuscript-prose-edit" / "scripts" / "detect.py")
setup = _load("detector_setup", SKILLS / "manuscript-prose-edit" / "scripts" / "detector_setup.py")


def test_detect_windows_merge_short_paragraphs_and_skip_references() -> None:
    para = " ".join(["word"] * 45) + "."
    text = "\n\n".join([para] * 6) + "\n\n## References\n\n" + para
    wins = detect.windows(text, False, detect._load_profile())
    assert [w["words"] for w in wins] == [135, 135]  # three 45-word paragraphs per window; references excluded


def test_detect_three_states_and_threshold() -> None:
    wins = [{"line": 1, "end_line": 1, "words": 200, "text": "a"}, {"line": 5, "end_line": 5, "words": 30, "text": "b"},
            {"line": 9, "end_line": 9, "words": 200, "text": "c"}, {"line": 12, "end_line": 12, "words": 200, "text": "d"}]

    def scorer(t: str) -> float:
        if t == "d":
            raise RuntimeError("model failed")
        return {"a": 0.9, "c": 0.2}[t]

    states = [r["state"] for r in detect.score_windows(wins, scorer, 0.5, False)]
    assert states == ["flagged", "not assessed", "not flagged", "not assessed"]


def test_remote_detector_needs_explicit_consent(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    p = tmp_path / "paper.md"
    p.write_text(PAPER, encoding="utf-8")
    result = CliRunner().invoke(detect.app, [str(p), "--detector", "aiornot"])
    assert result.exit_code != 0 and "allow-remote" in result.output


def test_setup_reports_missing_tokens_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"hf_token": False, "aiornot_key": False, "gpu": None, "ram_gb": 8.0, "hf_cache": "/x",
           "disk_free_gb": 50.0, "can_open_browser": False, "cached": {k: False for k in setup.DETECTORS}}
    rows = {r["key"]: r for r in setup.assess(env)}
    assert rows["modernbert"]["ready"] and rows["tropa"]["ready"]
    assert rows["editlens"]["missing"][0] == "hf-token" and not rows["aiornot"]["ready"]
    assert not rows["binoculars"]["ready"]  # 8 GB RAM and no GPU
    assert "No Hugging Face token" in setup.recommend(list(rows.values()), env)


# --- what the prose-edit scripts print for the authors: places by section, measures and states in words ----------

NUMBERED = """# A Tool for Genomes

## 1. Introduction

In recent years, polygenic scores have garnered significant attention. It is important to note that they play a pivotal role in the evolving landscape of precision medicine, highlighting the importance of genetics. Furthermore, they hold great promise.

## 2. Results

### 2.1 Speed

**Figure 2.** The pipeline annotated 4 genomes in 40 s each (Table 2) and agreed with the reference on 1,204 of 1,206 scores [3].

- Peak memory was 3.1 GB on every genome we ran through the annotation pipeline.
"""


def test_profile_paragraphs_carry_their_section_and_keep_a_bold_opening() -> None:
    doc = profile.profile_text(NUMBERED, False, profile.load_smells(), profile.load_kobak())
    assert [(p["line"], p["section"]) for p in doc["paragraphs"]] == [
        (5, "1. Introduction"), (11, "2. Results > 2.1 Speed"), (13, "2. Results > 2.1 Speed")]
    figure, item = doc["paragraphs"][1]["text"], doc["paragraphs"][2]["text"]
    assert figure.startswith("**Figure 2.** The pipeline") and item.startswith("Peak memory")


def test_profile_report_quotes_paragraphs_by_section_and_names_patterns_in_words() -> None:
    smells = profile.load_smells()
    doc = profile.profile_text(NUMBERED, False, smells, profile.load_kobak())
    md = profile.to_markdown("paper.md", doc, smells, 5, None)
    assert "- In section 1, Introduction (line 5), a paragraph of " in md
    assert "The paragraph begins: “In recent years, polygenic scores" in md
    assert "- Significance inflation (A1): once." in md and "significance inflation (A1) in “play a pivotal role”" in md
    assert re.search(r"\*\*L\d|\bL\d+\b", md) is None  # no bare line references
    assert re.search(r"^- [A-K]\d+ ", md, re.MULTILINE) is None  # no catalogue code before its description
    for internal in ("llm-smells.md", "anchors", "smells per", "n/a", "mtld |"):
        assert internal not in md, internal
    base = profile.profile_text(AUTHOR_SAMPLE, False, smells, profile.load_kobak())
    compared = profile.to_markdown("paper.md", doc, smells, 5, profile.compare(doc, base))
    assert "| Stock phrases and sentence shapes (the patterns listed below), per 1,000 words |" in compared
    assert "at least 1.5 times theirs" in compared


def test_detect_windows_know_their_section() -> None:
    para = " ".join(["word"] * 130) + "."
    wins = detect.windows(f"## 2. Results\n\n### 2.1 Speed\n\n{para}\n", False, detect._load_profile())
    assert [(w["line"], w["section"]) for w in wins] == [(5, "2. Results > 2.1 Speed")]


def test_detect_report_says_what_the_score_measures_and_where_each_passage_is() -> None:
    rows = [{"line": 5, "end_line": 9, "words": 200, "section": "2. Results > 2.1 Speed", "state": "flagged",
             "score": 0.91, "calibrated": False, "excerpt": "The pipeline annotated four genomes."},
            {"line": 12, "end_line": 12, "words": 30, "section": "Discussion", "state": "not assessed",
             "score": None, "reason": "under 50 words", "calibrated": False, "excerpt": "Short."},
            {"line": 14, "end_line": 20, "words": 200, "section": "", "state": "not flagged", "score": 0.12,
             "calibrated": False, "excerpt": "We thank the funders."}]
    md = detect.to_markdown("paper.md", "modernbert", rows, 0.5, False)
    assert ("the detector's estimate that a language model wrote it (the ModernBERT detector, "
            "rasbt/ai-text-detector-modernbert)") in md
    assert "It was not calibrated on the authors' own writing" in md
    assert "- In section 2.1, Speed (lines 5 to 9), the score was 0.910." in md
    assert "- In the Discussion (line 12), the passage has fewer than 50 words, too few to score." in md
    assert "| The text before the first heading (lines 14 to 20) | 0.120 |" in md
    for internal in ("llm-smells.md", "`modernbert`", "| lines |", "not assessed", "not flagged |", "uncalibrated"):
        assert internal not in md, internal
    calibrated = detect.to_markdown("paper.md", "modernbert", rows, 0.8, True)
    assert "the highest score the detector gave to the authors' own earlier writing" in calibrated


def test_setup_report_names_what_is_missing_in_words(monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner
    env = {"hf_token": False, "aiornot_key": False, "gpu": None, "ram_gb": 8.0, "hf_cache": "/x",
           "disk_free_gb": 50.0, "can_open_browser": False, "cached": {k: False for k in setup.DETECTORS}}
    monkeypatch.setattr(setup, "environment", lambda: env)
    out = CliRunner().invoke(setup.app, ["check"]).output
    assert "| a Hugging Face token and access approval from Pangram |" in out
    assert "| an AI or Not API key |" in out and "| on the company's server (the text is sent there) |" in out
    assert ("a graphics card with 30 GB of memory, or 64 GB of memory to run on the processor" in out
            and "about 64 GB of memory" in out)
    assert "- A Hugging Face token (`hf-token`): https://huggingface.co/settings/tokens." in out
    for internal in ("| hf-token", "editlens-access (", "needs ~", "(local", "Recommended: `"):
        assert internal not in out, internal
    raw = json.loads(CliRunner().invoke(setup.app, ["check", "--json"]).output)
    assert raw["detectors"][2]["missing"][0] == "hf-token"  # the JSON keeps the keys other tools read


watch = _load("policy_watch", SKILLS / "manuscript-journal-adapt" / "scripts" / "policy_watch.py")

POLICY_PAGE = """<html><head><script>var ai = "AI tracking pixel";</script></head><body>
<nav><a>AI hub</a> <a>Journals</a></nav>
<h2>Editorial policies</h2>
<p>Manuscripts must be original and not under consideration elsewhere. {filler}</p>
<h2>Use of generative AI</h2>
<p>Authors   must disclose the use of
   large language models in the Methods section.</p>
<ul><li>Spelling and grammar tools need no disclosure.</li><li>AI tools cannot be authors.</li></ul>
<h2>Data availability</h2>
<p>Data must be deposited in a public repository. {filler}</p>
<footer>We use AI to personalise ads.</footer>
</body></html>"""


def _page(**changes: str) -> str:
    page = POLICY_PAGE.replace("{filler}", "Reviewers assess novelty and rigour. " * 12)
    for old, new in changes.items():
        page = page.replace(old, new)
    return page


@pytest.fixture()
def snapshots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(watch, "SNAPSHOTS", tmp_path)
    monkeypatch.setattr(watch, "INDEX", tmp_path / "index.yaml")
    return tmp_path


def test_watch_extracts_ai_passages_under_their_heading_and_skips_page_chrome() -> None:
    body = watch.ai_extract(watch.page_blocks(_page()))
    assert body.split("\n\n") == ["## Use of generative AI",
                                  "Authors must disclose the use of large language models in the Methods section.",
                                  "AI tools cannot be authors."]


def test_watch_round_trip_unchanged_then_changed(snapshots: Path) -> None:
    url = "https://example.org/policy"
    index: dict = {}
    first = watch.compare(url, watch.Fetched("httpx", html=_page()), index, ["x"])
    assert first.result == watch.Result.new
    watch.apply([first], index, watch.date(2026, 10, 15))
    relaid = _page(**{"<p>Authors   must": "<p>\n\tAuthors must"})  # whitespace and layout only
    assert watch.compare(url, watch.Fetched("chrome", html=relaid), index, ["x"]).result == watch.Result.unchanged
    moved = _page(**{"in the Methods section": "in the Methods section and the cover letter, with prompts"})
    changed = watch.compare(url, watch.Fetched("httpx", html=moved), index, ["x"])
    assert changed.result == watch.Result.changed
    assert [l for l in changed.diff if l.startswith("+") and not l.startswith("+++")] == [
        "+Authors must disclose the use of large language models in the Methods section and the cover letter, "
        "with prompts."]


def test_watch_unreadable_pages_are_not_assessed_never_unchanged(snapshots: Path) -> None:
    index: dict = {}
    url = "https://example.org/policy"
    watch.apply([watch.compare(url, watch.Fetched("httpx", html=_page()), index, ["x"])], index,
                watch.date(2026, 10, 15))
    challenge = "<html><title>Just a moment...</title><body>challenge-platform</body></html>"
    assert watch._challenged(challenge)
    stub = watch.compare(url, watch.Fetched("chrome", html="<html><body><p>Loading</p></body></html>"), index, ["x"])
    blocked = watch.compare(url, watch.Fetched(None, reason="httpx: blocked (HTTP 403)"), index, ["x"])
    gone = watch.compare(url, watch.Fetched("httpx", status=404, reason="HTTP 404"), index, ["x"])
    assert [o.result for o in (stub, blocked, gone)] == [watch.Result.not_assessed, watch.Result.not_assessed,
                                                         watch.Result.gone]
    watch.apply([blocked], index, watch.date(2026, 10, 20))
    assert index[url]["read"] == "2026-10-15" and index[url]["last_attempt"]["result"] == "not_assessed"
    never_read: dict = {}
    watch.apply([watch.compare(url, watch.Fetched(None, reason="blocked"), never_read, ["x"])], never_read,
                watch.date(2026, 10, 15))
    assert "file" not in never_read[url]
    first = watch.compare(url, watch.Fetched("httpx", html=_page()), never_read, ["x"])  # read at last
    assert first.result == watch.Result.new
    watch.apply([first], never_read, watch.date(2026, 10, 16))
    assert never_read[url]["read"] == "2026-10-16" and "last_attempt" not in never_read[url]


def test_watch_record_reads_plain_text_like_the_page(snapshots: Path) -> None:
    text = ("Use of generative AI\n\nAuthors must disclose the use of large language models in the Methods "
            "section.\n\nSpelling and grammar tools need no disclosure.\n\nAI tools cannot be authors.\n\n"
            + "Reviewers assess novelty and rigour. " * 15)
    blocks = watch.text_blocks(text)
    assert watch.ai_extract(blocks) == watch.ai_extract(watch.page_blocks(_page()))


def test_every_watched_url_belongs_to_a_venue_and_snapshots_exist_for_indexed_urls() -> None:
    urls = watch.watched_urls()
    assert urls and all(u.startswith("https://") for u in urls), [u for u in urls if not u.startswith("https://")]
    index = watch.load_index()
    assert set(index) <= set(urls), set(index) - set(urls)
    for url, entry in index.items():
        if "file" in entry:
            assert watch.read_snapshot(entry) is not None, url


SYNTHETIC_VENUES = """
checked: 2026-10-15
venues:
  pub:
    kind: publisher
    name: A Publisher (default policy)
    url: https://pub.example/policies
    ai_policy_url: https://pub.example/ai
    writing_help: disclose
    prompts: "no"
    screening: plagiarism
    disclosure_places: [Methods]
    jif: 99
  calm:
    name: Calm Journal
    inherits: pub
    url: https://pub.example/calm
    fields: [aging]
    article_types: [research, review]
    oa: full
    jif: 6.1
  strict:
    name: Strict Journal
    inherits: pub
    url: https://pub.example/strict
    fields: [bioinformatics]
    software_article: true
    writing_help: banned_drafting
    prompts: required
    screening: ai_detector_deployed
    disclosure_places: [cover letter, Methods, supplementary materials]
    disclosure_neutral: false
    oa: hybrid
    jif: 8.0
"""


@pytest.fixture()
def synthetic_venues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "venues.yaml"
    p.write_text(SYNTHETIC_VENUES, encoding="utf-8")
    monkeypatch.setattr(venues, "VENUES_YAML", p)
    monkeypatch.setattr(venues, "SNAPSHOT_INDEX", tmp_path / "none.yaml")
    return p


def test_publisher_defaults_lend_policy_but_not_identity(synthetic_venues: Path) -> None:
    _, resolved = venues.load_venues()
    assert set(venues.journals(resolved)) == {"calm", "strict"}
    calm = resolved["calm"]
    assert calm["writing_help"] == "disclose" and calm["name"] == "Calm Journal" and "kind" not in calm
    assert calm["jif"] == 6.1 and calm["url"] == "https://pub.example/calm"
    assert calm["publisher_policy_url"] == "https://pub.example/ai"
    assert venues.policy_urls(calm) == ["https://pub.example/ai", "https://pub.example/calm"]


def test_burdens_and_tiers_follow_the_policy_fields(synthetic_venues: Path) -> None:
    _, resolved = venues.load_venues()
    assert venues.burdens(resolved["calm"]) == set()
    B = venues.Burden
    assert venues.burdens(resolved["strict"]) == {B.drafting_ban, B.prompts, B.ai_detector, B.supplement,
                                                  B.multi_place, B.disclosure_penalty}
    calm, strict = (venues.friction(resolved[k])[0] for k in ("calm", "strict"))
    assert (venues.tier(calm), venues.tier(strict)) == ("light", "severe")
    assert venues.tier(None) == "?"


@pytest.mark.parametrize("args, shown", [
    ([], {"calm", "strict"}),
    (["--field", "aging"], {"calm"}),
    (["--type", "software"], {"strict"}),
    (["--software"], {"strict"}),
    (["--oa", "full"], {"calm"}),
    (["--min-jif", "7"], {"strict"}),
    (["--refuse", "prompts"], {"calm"}),
    (["--refuse", "disclosure-penalty"], {"calm"}),
    (["--max-friction", "3"], {"calm"}),
    (["--only", "strict"], {"strict"}),
])
def test_rank_filters(synthetic_venues: Path, args: list[str], shown: set[str]) -> None:
    from typer.testing import CliRunner
    result = CliRunner().invoke(venues.app, ["rank", *args])
    assert result.exit_code == 0, result.output
    assert set(re.findall(r"\(`([a-z-]+)`\)", result.output)) == shown


VALIDATION_RULES = [
    {"applies_to": ["public-data", "mr"], "strength": "required",
     "accepted_any": ["independent-cohort", "wet-lab"], "description": "Independent validation required"},
    {"applies_to": ["bibliometric"], "strength": "required",
     "accepted_any": ["multi-database"], "description": "Multi-database alternative"},
]


@pytest.mark.parametrize("study,available,status", [
    (None, {"none"}, "conditional"),
    ("public-data", None, "conditional"),
    ("public-data", {"none"}, "no-go"),
    ("public-data", {"independent-cohort"}, "go"),
    ("public-data", {"wet-lab"}, "go"),
    ("public-data", {"multi-database"}, "no-go"),
    ("bibliometric", {"multi-database"}, "go"),
    ("other", {"wet-lab"}, "unknown"),
])
def test_validation_fit_respects_scope_alternatives_and_unknowns(
    study: str | None, available: set[str] | None, status: str,
) -> None:
    assert venues.validation_fit({"validation_requirements": VALIDATION_RULES}, study, available)[0] == status


def test_conditional_validation_and_missing_policy_are_not_automatic_rejection() -> None:
    v = {"validation_requirements": [{**VALIDATION_RULES[0], "strength": "conditional"}]}
    assert venues.validation_fit(v, "public-data", {"none"})[0] == "conditional"
    assert venues.validation_fit({}, "public-data", {"none"})[0] == "unknown"


def test_explicit_scope_exclusion_is_not_cured_by_available_validation() -> None:
    v = {"validation_requirements": VALIDATION_RULES, "excluded_study_designs": ["bibliometric"]}
    assert venues.validation_fit(v, "bibliometric", {"multi-database"})[0] == "no-go"


def test_ranking_does_not_trade_impossible_validation_for_a_lighter_ai_policy(synthetic_venues: Path) -> None:
    from typer.testing import CliRunner

    data = yaml.safe_load(synthetic_venues.read_text())
    for key, route in [("calm", "wet-lab"), ("strict", "independent-cohort")]:
        data["venues"][key]["validation_requirements"] = [
            {**VALIDATION_RULES[0], "accepted_any": [route]}]
    synthetic_venues.write_text(yaml.safe_dump(data))
    result = CliRunner().invoke(venues.app, [
        "rank", "--study-design", "public-data", "--validation-available", "independent-cohort"])
    assert result.exit_code == 0, result.output
    assert re.findall(r"\(`([a-z-]+)`\)", result.output) == ["strict", "calm"]
    assert "Does not fit. It requires wet-lab experiments, and you have none of these." in result.output


def test_journal_speed_and_editorial_profile_are_not_inherited(synthetic_venues: Path) -> None:
    data = yaml.safe_load(synthetic_venues.read_text())
    data["venues"]["pub"].update(
        review_speed=[{"metric": "first decision", "days": 3}],
        editorial_profile={"summary": "Publisher marketing claim"},
        validation_requirements=VALIDATION_RULES,
    )
    synthetic_venues.write_text(yaml.safe_dump(data))
    _, resolved = venues.load_venues()
    assert resolved["calm"]["validation_requirements"] == VALIDATION_RULES
    assert "review_speed" not in resolved["calm"] and "editorial_profile" not in resolved["calm"]


def test_no_validation_cannot_be_combined_with_an_available_route(synthetic_venues: Path) -> None:
    from typer.testing import CliRunner

    result = CliRunner().invoke(venues.app, [
        "rank", "--validation-available", "none", "--validation-available", "wet-lab"])
    assert result.exit_code != 0


def test_recorded_validation_rules_have_supported_values_and_discoverable_sources() -> None:
    _, resolved = venues.load_venues()
    designs = {item.value for item in venues.StudyDesign}
    alternatives = {item.value for item in venues.Validation} - {"none"}
    for key, venue in resolved.items():
        for rule in venue.get("validation_requirements") or []:
            assert set(rule["applies_to"]) <= designs, key
            assert set(rule.get("accepted_any") or []) <= alternatives, key
            assert rule["strength"] in {"required", "conditional", "recommended"}, key
            assert rule["source"] in venues.policy_urls(venue), key
            assert rule.get("checked"), key


VOCAB = {"fields": {"aging", "bioinformatics", "genomics", "genetics", "systems-biology", "clinical", "general", "data",
                    "software"},
         "article_types": {"research", "methods", "software", "database", "data", "review", "perspective", "letter"}}
SCALARS = {"oa": {None, "full", "hybrid", "subscription"}, "reviewer_ai": {None, "banned", "restricted", "allowed"},
           "disclosure_neutral": {None, True, False}, "kind": {None, "publisher", "preprint"}}


def test_every_venue_entry_uses_the_vocabularies_and_https_sources() -> None:
    _, resolved = venues.load_venues()
    raw = yaml.safe_load(venues.VENUES_YAML.read_text(encoding="utf-8"))["venues"]
    assert {v["inherits"] for v in raw.values() if v.get("inherits")} <= set(raw)
    for key, v in resolved.items():
        for field, allowed in VOCAB.items():
            assert set(v.get(field) or []) <= allowed, (key, field, set(v[field]) - allowed)
        for field, allowed in SCALARS.items():
            assert v.get(field) in allowed, (key, field, v.get(field))
        assert all(u.startswith("https://") for u in venues.policy_urls(v)), key
        if v.get("kind") is None:
            assert v.get("fields"), f"{key} has no fields, so --field filters can never find it"


def test_publisher_defaults_and_preprints_are_never_ranked_as_journals() -> None:
    _, resolved = venues.load_venues()
    ranked = venues.journals(resolved)
    assert not any(v.get("kind") for v in ranked.values())
    assert set(venues.journals(resolved, preprints=True)) >= {"arxiv", "biorxiv", "medrxiv"}


def test_watch_a_stub_page_falls_through_to_the_next_route(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = "<html><body><p>JavaScript is disabled. Enable it to view this page.</p></body></html>"
    monkeypatch.setattr(watch, "fetch_httpx", lambda url: watch.Fetched("httpx", html=stub, status=200))
    monkeypatch.setattr(watch, "fetch_chrome", lambda url: watch.Fetched("chrome", html=_page()))
    got = watch.fetch("https://example.org/policy", ["httpx", "chrome"], None)
    assert got.route == "chrome" and watch.readable(watch.blocks_of(got))
    monkeypatch.setattr(watch, "fetch_chrome", lambda url: watch.Fetched("chrome", reason="blocked (challenge page)"))
    failed = watch.fetch("https://example.org/policy", ["httpx", "chrome"], None)
    assert failed.html is None and failed.reason.startswith("the plain download got a page too short")


def _minimal_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with these lines of Helvetica text; offsets in the xref table are computed, not guessed."""
    ops = "BT /F1 10 Tf 40 760 Td 14 TL " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler's pdftotext")
def test_watch_reads_a_pdf_as_text() -> None:
    lines = ["Use of generative AI", "", "Authors must disclose the use of large language models in Methods.", "",
             *(["Reviewers assess novelty and rigour of every submission they receive."] * 12)]
    text = watch._pdf_text(_minimal_pdf(lines))
    assert text and "large language models in Methods." in text
    got = watch.Fetched("httpx", html=text, plain=True)
    assert watch.readable(watch.blocks_of(got))
    assert "Authors must disclose the use of large language models in Methods." in watch.ai_extract(watch.blocks_of(got))


def test_watch_dates_an_archived_copy_by_its_capture(snapshots: Path) -> None:
    index: dict = {}
    url = "https://example.org/policy"
    o = watch.compare(url, watch.Fetched("wayback:20240617115300", html=_page()), index, ["x"])
    watch.apply([o], index, watch.date(2026, 10, 15))
    assert index[url]["read"] == "2024-06-17"


def test_a_software_paper_is_not_held_to_a_rule_about_bioinformatics_findings() -> None:
    _, resolved = venues.load_venues()
    frontiers = resolved["frontiers-bioinformatics"]
    assert venues.validation_fit(frontiers, "bioinformatics", {"none"})[0] == "no-go"
    assert venues.validation_fit(frontiers, "software", {"none"})[0] != "no-go"
    from typer.testing import CliRunner
    result = CliRunner().invoke(venues.app, ["rank", "--study-design", "software", "--validation-available", "none"])
    assert result.exit_code == 0, result.output  # the option used to reject a software paper outright


@pytest.mark.parametrize("fetched, code", [
    (lambda: watch.Fetched(None, reason="httpx: blocked (HTTP 403)"), 3),  # unread is not a clean pass
    (lambda: watch.Fetched("httpx", html=_page()), 0),
])
def test_watch_check_exit_code_separates_unread_pages_from_unchanged(
        snapshots: Path, monkeypatch: pytest.MonkeyPatch, fetched, code: int) -> None:
    from typer.testing import CliRunner
    url = "https://example.org/policy"
    index: dict = {}
    watch.apply([watch.compare(url, watch.Fetched("httpx", html=_page()), index, ["x"])], index,
                watch.date(2026, 10, 15))
    watch.INDEX.write_text(yaml.safe_dump(index), encoding="utf-8")
    monkeypatch.setattr(watch, "watched_urls", lambda venue=None: {url: ["x"]})
    monkeypatch.setattr(watch, "fetch", lambda url, routes, last: fetched())
    result = CliRunner().invoke(watch.app, ["check"])
    assert result.exit_code == code, result.output


# Readable output: what the authors see from venues.py and policy_watch.py quotes, links and uses plain words.
INTERNAL_TOKENS = ("banned_drafting", "red_line", "disclose_all", "integrity_signals", "ai_detector_deployed",
                   "not_assessed", "no-go", "validation_requirements", "on_request", "JIF", "| OA |")


def test_rank_explains_its_columns_and_links_each_policy_page(synthetic_venues: Path) -> None:
    from typer.testing import CliRunner
    result = CliRunner().invoke(venues.app, ["rank", "--ai-use", "drafting"])
    assert result.exit_code == 0, result.output
    assert "journal impact factor" in result.output and "article processing charge" in result.output
    assert "full open access" in result.output
    rows = [line for line in result.output.splitlines() if line.startswith("| ") and "(`" in line]
    assert {re.search(r"\(`([a-z-]+)`\)", r).group(1) for r in rows} == {"calm", "strict"}
    for row, page in [(r, "https://pub.example/ai") for r in rows]:
        assert f"{page} (read " in row, row
    strict = next(r for r in rows if "(`strict`)" in r)
    assert "A conflict for you to weigh" in strict and "6 or more severe" in result.output
    assert not [t for t in INTERNAL_TOKENS if t in result.output]
    assert not re.search(r"\bL\d+\b", result.output)


def test_show_orders_the_checklist_by_when_the_work_can_be_done(synthetic_venues: Path) -> None:
    from typer.testing import CliRunner
    result = CliRunner().invoke(venues.app, ["show", "strict"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "- **AI policy page:** https://pub.example/ai" in out
    assert out.index("## Now that the journal is chosen") < out.index("## At the end, once the code, data and results")
    assert out.index("## At the end") < out.index("The AI-use statement goes in:")
    assert all(f'(AI use "{use.value}")' in out for use in venues.AiUse)  # every kind of use, when none is given
    assert not [t for t in INTERNAL_TOKENS if t in out]


def test_show_takes_the_ai_use_like_rank(synthetic_venues: Path) -> None:
    # Smoke run 2026-10-15: `show KEY --ai-use drafting` failed with "No such option".
    from typer.testing import CliRunner
    result = CliRunner().invoke(venues.app, ["show", "strict", "--ai-use", "drafting"])
    assert result.exit_code == 0, result.output
    assert '(AI use "drafting")' in result.output and '(AI use "polish")' not in result.output


def test_show_reads_old_failure_reasons_in_words() -> None:
    assert venues.plain_reason("httpx: blocked (HTTP 403); chrome: blocked (challenge page)") == (
        "plain download: blocked (HTTP 403); headless browser: blocked (challenge page)")
    assert venues.route_words("wayback:20240617115300") == "the Internet Archive's copy of 2024-06-17"


def test_peers_finds_a_name_listed_with_a_middle_initial(synthetic_venues: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    # 2026-10-19: `peers "Anton Kulaga"` printed "no OpenAlex author with this name", because OpenAlex lists him as
    # "Anton Y. Kulaga", and offered no id to pass with --author-id; a journal with an unread policy read "not known (?)".
    from typer.testing import CliRunner
    p = synthetic_venues
    p.write_text(SYNTHETIC_VENUES + "  unread:\n    name: Unread Journal\n    url: https://unread.example\n",
                 encoding="utf-8")
    people = {"https://openalex.org/A1": "Anton Y. Kulaga", "https://openalex.org/A2": "Kuzmin Anton",
              "https://openalex.org/A3": "Kim Smith"}
    papers = {"A1": ["Calm Journal", "Unread Journal"], "A3": ["Strict Journal"]}

    def fake_openalex(path: str, **params: object) -> dict:
        if path == "authors":
            words = set(venues._fold(str(params["search"])).split())
            return {"results": [{"id": i, "display_name": n, "works_count": 16, "last_known_institutions": []}
                                for i, n in people.items() if words & set(venues._fold(n).split())]}
        aid = str(params["filter"]).split("author.id:")[1].split(",")[0]
        return {"meta": {"next_cursor": None}, "results": [
            {"primary_location": {"source": {"type": "journal", "id": f"https://openalex.org/S{j}",
                                             "display_name": j}}} for j in papers.get(aid, [])]}

    monkeypatch.setattr(venues, "_openalex", fake_openalex)
    result = CliRunner().invoke(venues.app, ["peers", "Anton Kulaga", "J. Smith", "--since", "2019"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Anton Kulaga: A1 Anton Y. Kulaga (16 works; no institution)" in out
    rows = {r.split(" | ")[1]: r for r in out.splitlines() if r.startswith("| ") and not r.startswith("| Papers")}
    assert set(rows) == {"Calm Journal", "Unread Journal"}  # only the matched person's papers are counted
    score, _ = venues.friction(venues.load_venues()[1]["calm"])
    assert f"| {venues._points(score)} ({venues.tier(score)}) |" in rows["Calm Journal"]
    assert "| not known |" in rows["Unread Journal"] and "?" not in rows["Unread Journal"]
    # A shared surname with a different given name is not the same person; the near miss is named so it can be chosen.
    assert "J. Smith: OpenAlex has no author with this name. The nearest names it found: A3 Kim Smith" in out
    assert "--author-id" in out
    assert venues._same_name("Kulaga, Anton", "Anton Kulaga") and not venues._same_name("A. Kulaga", "Anton Kulaga")


def test_abbreviations_spell_out_only_what_the_text_uses() -> None:
    line = venues.abbreviations("OUP / ISCB journal; LLM help; see https://www.plos.org/APC-page")
    assert line == ("Abbreviations: ISCB, International Society for Computational Biology; LLM, large language "
                    "model; OUP, Oxford University Press.")
    assert venues.abbreviations("If the journal allows it") == ""


def test_watch_report_quotes_the_changed_passage_with_its_page_url(
        snapshots: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner
    url, blocked = "https://example.org/policy", "https://example.org/blocked"
    index: dict = {}
    watch.apply([watch.compare(url, watch.Fetched("httpx", html=_page()), index, ["x"])], index,
                watch.date(2026, 10, 15))
    watch.INDEX.write_text(yaml.safe_dump(index), encoding="utf-8")
    moved = _page(**{"in the Methods section": "in the Methods section and the cover letter, with prompts"})
    monkeypatch.setattr(watch, "watched_urls", lambda venue=None: {url: ["x"], blocked: ["y"]})
    monkeypatch.setattr(watch, "fetch", lambda u, routes, last: watch.Fetched("httpx", html=moved) if u == url
                        else watch.Fetched(None, reason="the plain download was blocked (HTTP 403)"))
    result = CliRunner().invoke(watch.app, ["check"])
    assert result.exit_code == 1, result.output
    out = result.output
    assert f"- {url}\n" in out and f"- {blocked}\n" in out
    assert ('Under the heading "Use of generative AI", the passage that read "Authors must disclose the use of large '
            'language models in the Methods section." now reads "') in out
    assert "**and the cover letter, with prompts**" in out
    assert "## Could not be read (1)" in out and "It could not be read: the plain download was blocked (HTTP 403)." in out
    assert not re.search(r"^\s*(@@|\+\+\+|---) ", out, re.MULTILINE)  # no raw diff
    assert "not_assessed" not in out and not re.search(r"\bL\d+\b", out)


def test_watch_excerpt_keeps_the_change_visible_in_a_long_passage() -> None:
    before = "Authors " + "must follow the editorial rules of the journal " * 8 + "and disclose AI use in Methods."
    after = before.replace("in Methods.", "in Methods and the cover letter.")
    sentence = watch.describe_changes(before, after)[0]
    quoted_after = sentence.split('now reads "', 1)[1]
    assert "**and the cover letter**" in quoted_after and quoted_after.startswith("[...] ")
    assert len(quoted_after) < watch.EXCERPT_CHARS + 30
    removed = watch.describe_changes("## AI\n\nAI tools cannot be authors.", "## AI")
    assert removed == ['Under the heading "AI", the passage "AI tools cannot be authors." was removed.']
