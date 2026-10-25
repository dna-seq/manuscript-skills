"""The integrity check's ledger of the paper's claims about its own software (code_claims.py): one claim per entry,
each cleared or contradicted with its file and line, measurements traced to the code that took them, and the
availability table checked against the dependency files. From the blind v0.3 run, which cleared nine claims on one
line and missed a DuckDB join, a memory tracker and a repository table that the first run had caught."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cc = _load("code_claims", ROOT / "skills/manuscript-integrity-check/scripts/code_claims.py")

PAPER = """# A tool

## Implementation

Joins are performed by rsID (default) or genomic position. Polars streaming joins keep peak memory low; for
datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable memory limits.

## Benchmark

Peak memory stayed below 750 MB.

## Code availability

The schema and compiler are in [just-dna-format](https://example.org/just-dna-format).
"""
JOIN = '''import polars as pl


def annotate_with_module(vcf, module, join_on: str = "position"):
    """Join the VCF with a module's weights."""
    keys = ["chrom", "pos", "genotype"] if join_on == "position" else ["rsid"]
    return vcf.join(module, on=keys)
'''
ENSEMBL = '''import duckdb


def annotate_with_ensembl(vcf, db, memory_limit="8GB"):
    con = duckdb.connect(db)
    con.execute(f"SET memory_limit='{memory_limit}'")
'''
TRACKER = '''import psutil


def track(step):
    before = psutil.Process().memory_info().rss
    step()
    after = psutil.Process().memory_info().rss
    return max(before, after)
'''
PYPROJECT = '''[project]
name = "tool-pipelines"
version = "0.2.5"
dependencies = [
  "polars>=1.0",
  "just-dna-compiler>=0.6.6",
  "just-dna-format>=0.6.6",
  "helper",
]

[tool.uv.sources]
helper = { workspace = true }
'''


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    code = tmp_path / "code"
    (code / "pkg").mkdir(parents=True)
    (code / "pkg" / "join.py").write_text(JOIN, encoding="utf-8")
    (code / "pkg" / "ensembl.py").write_text(ENSEMBL, encoding="utf-8")
    (code / "pkg" / "tracker.py").write_text(TRACKER, encoding="utf-8")
    (code / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (code / "web" / "app.lock").mkdir(parents=True)
    (code / "web" / "app.lock" / "package.json").write_text('{"name": "built"}', encoding="utf-8")
    (code / "requirements-dev.txt").write_text("pytest>=8  # tests\n-e .\n", encoding="utf-8")
    (tmp_path / "paper.md").write_text(PAPER, encoding="utf-8")
    return tmp_path


GOOD = [
    {"id": "CC1", "claim": "Joins are performed by rsID (default) or genomic position.",
     "where": "Implementation: the join of the VCF with each module", "kind": "default", "verdict": "differs",
     "evidence": [{"path": "pkg/join.py", "line": 4, "quote": 'join_on: str = "position"'}],
     "why": "The module join defaults to position."},
    {"id": "CC2", "claim": "for datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable "
     "memory limits.", "where": "Implementation: the module joins", "kind": "behaviour", "verdict": "differs",
     "evidence": [{"path": "pkg/join.py", "line": 7, "quote": "return vcf.join(module, on=keys)"},
                  {"path": "pkg/ensembl.py", "line": 4, "quote": 'def annotate_with_ensembl(vcf, db, memory_limit="8GB"):'}],
     "why": "The module join is Polars only; the DuckDB memory limit belongs to the Ensembl join."},
    {"id": "CC3", "claim": "Peak memory stayed below 750 MB.", "where": "Benchmark: the annotation runs of Table 2",
     "kind": "measurement", "verdict": "differs",
     "evidence": [{"path": "pkg/tracker.py", "line": 5, "quote": "before = psutil.Process().memory_info().rss"}],
     "why": "The tracker reads memory before and after each step, so the figure is not a sampled peak."},
    {"id": "CC4", "claim": "The schema and compiler are in [just-dna-format](https://example.org/just-dna-format).",
     "where": "Code availability table", "kind": "availability", "verdict": "differs",
     "evidence": [{"path": "pyproject.toml", "line": 6, "quote": '"just-dna-compiler>=0.6.6",'}],
     "why": "The compiler is its own package, just-dna-compiler."},
]


def _check(project: Path, claims: list[dict], findings: dict | None = None) -> tuple[int, dict]:
    ledger = project / "code-claims.yaml"
    ledger.write_text(yaml.safe_dump({"claims": claims}, allow_unicode=True), encoding="utf-8")
    args = ["check", str(ledger), "--code", str(project / "code"), "--manuscript", str(project / "paper.md")]
    if findings is not None:
        (project / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
        args += ["--findings", str(project / "findings.json")]
    result = CliRunner().invoke(cc.app, args)
    return result.exit_code, json.loads(result.output)


def test_a_ledger_with_one_claim_per_entry_and_evidence_at_its_line_passes(project: Path) -> None:
    code, out = _check(project, GOOD)
    assert code == 0, out["problems"]
    assert out["by_verdict"] == {"differs": 4, "matches": 0, "not-settled": 0}
    assert out["differs"] == ["CC1", "CC2", "CC3", "CC4"]


def test_a_list_of_topics_cleared_together_is_refused(project: Path) -> None:
    batch = {"id": "CC9", "claim": "Twelve pathway categories, validator, chr stripping, DuckDB memory limit",
             "where": "Section 2", "kind": "behaviour", "verdict": "matches", "evidence": []}
    code, out = _check(project, [batch])
    assert code == 1
    assert "CC9: the claim is not a verbatim quote of the manuscript" in out["problems"][0]
    assert "CC9: a matches verdict needs evidence" in out["problems"][1]


def test_one_entry_holds_one_sentence(project: Path) -> None:
    two = dict(GOOD[1], claim="Joins are performed by rsID (default) or genomic position. Polars streaming joins keep "
               "peak memory low;")
    code, out = _check(project, [two])
    assert any("runs over 2 sentences" in p for p in out["problems"])


def test_evidence_must_be_at_the_line_given(project: Path) -> None:
    (project / "code" / "pkg" / "long.py").write_text("\n" * 14 + JOIN, encoding="utf-8")  # the default on line 18
    moved = dict(GOOD[0], evidence=[{"path": "pkg/long.py", "line": 4, "quote": 'join_on: str = "position"'}])
    missing = dict(GOOD[0], id="CC5", evidence=[{"path": "pkg/join.py", "line": 4, "quote": 'join_on: str = "rsid"'}])
    outside = dict(GOOD[0], id="CC6", evidence=[{"path": "../paper.md", "line": 1, "quote": "A tool"}])
    code, out = _check(project, [moved, missing, outside])
    assert code == 1
    assert 'CC1 evidence 1: the quote is not in pkg/long.py near line 4; it occurs at line 18' in out["problems"]
    assert "CC5 evidence 1: the quote is not in pkg/join.py near line 4; it does not occur in that file" in out["problems"]
    assert "CC6 evidence 1: ../paper.md is not a file in the code" in out["problems"]


def test_the_place_the_text_names_is_required(project: Path) -> None:
    code, out = _check(project, [dict(GOOD[1], where="")])
    assert any(p.startswith("CC2: no `where`") for p in out["problems"])


def test_a_measurement_needs_the_code_that_took_it(project: Path) -> None:
    only_manifest = dict(GOOD[2], evidence=[{"path": "pyproject.toml", "line": 5, "quote": '"polars>=1.0",'}])
    unsettled = dict(GOOD[2], id="CC7", verdict="not-settled", evidence=[], why="No script in the repository took it.")
    code, out = _check(project, [only_manifest, unsettled])
    assert any(p.startswith("CC3: a measurement is settled by the code that took it") for p in out["problems"])
    assert out["measurements_without_code"] == ["CC7"]


def test_an_availability_claim_needs_the_dependency_file(project: Path) -> None:
    code, out = _check(project, [dict(GOOD[3], evidence=GOOD[0]["evidence"])])
    assert any(p.startswith("CC4: an availability claim is settled by the dependency file") for p in out["problems"])


def test_a_differs_or_unsettled_verdict_says_why(project: Path) -> None:
    code, out = _check(project, [dict(GOOD[0], why="")])
    assert "CC1: a differs verdict says why" in out["problems"]


def test_a_code_clearance_in_the_findings_names_its_one_ledger_entry(project: Path) -> None:
    matches = {"id": "CC8", "claim": "Polars streaming joins keep peak memory low;", "where": "Implementation",
               "kind": "behaviour", "verdict": "matches",
               "evidence": [{"path": "pkg/join.py", "line": 1, "quote": "import polars as pl"}]}
    findings = {"findings": [], "dismissed": [
        {"summary": "Twelve pathway categories, chr stripping, DuckDB memory limit",
         "why": "Each matches the code at the draft's commit."},
        {"summary": "Polars joins", "why": "Matches the code.", "claims": ["CC8", "CC1"]},
        {"summary": "Module join default", "why": "Consistent with the code.", "claims": ["CC1"]},
        {"summary": "Polars joins", "why": "Matches the code in pkg/join.py.", "claims": ["CC8"]},
        {"summary": "A spelling flag", "why": "British spelling throughout."}]}
    code, out = _check(project, [*GOOD, matches], findings)
    problems = [p for p in out["problems"] if p.startswith("dismissed")]
    assert len(problems) == 3
    assert "it names none" in problems[0] and "split it, one per claim" in problems[1]
    assert "CC1 does not have the verdict matches" in problems[2]


def test_deps_lists_each_manifest_with_lines_and_sources(project: Path) -> None:
    found = {m["file"]: m for m in cc.manifests(project / "code")}
    assert sorted(found) == ["pyproject.toml", "requirements-dev.txt"]  # the built folder's package.json is skipped
    deps = {d["name"]: d for d in found["pyproject.toml"]["dependencies"]}
    assert deps["just-dna-compiler"]["line"] == 6 and deps["just-dna-format"]["line"] == 7
    assert deps["helper"]["source"] == "workspace member" and deps["polars"]["source"] == "registry"
    assert [d["name"] for d in found["requirements-dev.txt"]["dependencies"]] == ["pytest"]
    result = CliRunner().invoke(cc.app, ["deps", str(project / "code")])
    assert "- just-dna-compiler>=0.6.6 (dependencies; registry; line 6)" in result.output


def test_an_unreadable_ledger_is_a_bad_option(project: Path) -> None:
    (project / "bad.yaml").write_text("claims: [unclosed", encoding="utf-8")
    result = CliRunner().invoke(cc.app, ["check", str(project / "bad.yaml"), "--code", str(project / "code"),
                                         "--manuscript", str(project / "paper.md")])
    assert result.exit_code == 2
