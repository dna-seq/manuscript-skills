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
    missing = {f.message for f in _checks(report, "declarations")}
    assert missing == {"No 'AI-use disclosure' statement found.", "No 'Data availability' statement found."}


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
