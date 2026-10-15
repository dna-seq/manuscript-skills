"""Offline tests for manuscript-reporting-check's scripts. Run with `uv run pytest tests/test_reporting_check.py`.

Network code runs against httpx.MockTransport; nothing here touches the internet.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Callable

import httpx
import pytest
import typer
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "manuscript-reporting-check"
FIXTURES = ROOT / "evals" / "fixtures" / "manuscript-reporting-check"
SEEDED = FIXTURES / "seeded-association.md"
CLEAN = FIXTURES / "clean-association.md"
SOFTWARE = FIXTURES / "software-note.md"
ANONYMISED = FIXTURES / "anonymised-tool.tex"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # pydantic resolves the deferred annotations through sys.modules
    spec.loader.exec_module(module)
    return module


ca = _load("check_availability", SKILL / "scripts" / "check_availability.py")
gl = _load("reporting_guidelines", SKILL / "scripts" / "guidelines.py")


def _line_of(path: Path, needle: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    return next(i for i, line in enumerate(lines, 1) if needle in line)


def _checks(report: object, check: str) -> list:
    return [f for f in report.findings if f.check == check]  # type: ignore[attr-defined]


def _extract(text: str) -> list:
    lines = ca.prepare(text, latex=False)
    sections, skip, _ = ca.layout(lines)
    statements = ca.find_statements(lines, skip)
    identifiers = ca.extract(lines, skip, sections, statements)
    ca.analyse_statements(statements, lines, identifiers)
    ca.mark_own(identifiers, statements)
    return identifiers


# ------------------------------------------------------------------------------------- seeded vs clean

PLANTED = {  # check -> the text on the line where the finding must be reported
    "request-only": "Individual-level genotype and phenotype data are available from the corresponding",
    "malformed-identifier": "accession GSE1589O4",
    "code-unversioned": "https://github.com/northfield-genetics/urate-assoc.",
}


@pytest.mark.parametrize("check,needle", PLANTED.items())
def test_each_planted_availability_defect_is_found_once_at_its_line(check: str, needle: str) -> None:
    report = ca.check(SEEDED, online=False, venue="bmj-open")
    found = _checks(report, check)
    assert [f.line for f in found] == [_line_of(SEEDED, needle)]


def test_the_malformed_geo_accession_is_major_and_never_looked_up() -> None:
    report = ca.check(SEEDED, online=False)
    (finding,) = _checks(report, "malformed-identifier")
    assert finding.severity == ca.Severity.major
    (geo,) = [x for x in report.identifiers if x.kind == "geo"]
    assert (geo.value, geo.well_formed, geo.suggested) == ("GSE1589O4", False, "")


def test_the_clean_control_has_none_of_the_planted_defects() -> None:
    report = ca.check(CLEAN, online=False, venue="bmj-open")
    planted_kinds = set(PLANTED) | {"request-route", "no-archive", "empty-statement", "no-statement"}
    assert not [f for f in report.findings if f.check in planted_kinds]
    assert not [f for f in report.findings if f.severity == ca.Severity.major]


def test_seeded_and_clean_differ_only_in_the_planted_findings() -> None:
    seeded = {(f.check, f.severity) for f in ca.check(SEEDED, online=False).findings}
    clean = {(f.check, f.severity) for f in ca.check(CLEAN, online=False).findings}
    assert seeded - clean == {("request-only", ca.Severity.major), ("malformed-identifier", ca.Severity.major),
                              ("code-unversioned", ca.Severity.optional)}
    assert clean - seeded == set()


def test_controlled_access_dbgap_is_extracted_but_never_flagged() -> None:
    for path in (SEEDED, CLEAN):
        report = ca.check(path, online=False)
        dbgap = [x for x in report.identifiers if x.kind == "dbgap"]
        assert [x.value for x in dbgap] == ["phs000007.v35.p16"]
        assert not [f for f in report.findings if "phs000007" in f.excerpt]


def test_the_clean_controls_versioned_code_and_archive_are_read() -> None:
    report = ca.check(CLEAN, online=False)
    github = next(x for x in report.identifiers if x.kind == "github")
    zenodo = next(x for x in report.identifiers if x.kind == "zenodo")
    assert (github.value, github.version, github.in_statement) == ("northfield-genetics/urate-assoc", "1.2.0", True)
    assert zenodo.value == "10.5281/zenodo.1234567"


def test_exit_code_is_one_for_major_findings_and_zero_for_the_clean_control(tmp_path: Path) -> None:
    runner = CliRunner()
    seeded = runner.invoke(ca.app, [str(SEEDED), "--json", str(tmp_path / "s.json")])
    clean = runner.invoke(ca.app, [str(CLEAN), "--md", str(tmp_path / "c.md")])
    assert (seeded.exit_code, clean.exit_code) == (1, 0), seeded.output + clean.output
    data = json.loads((tmp_path / "s.json").read_text())
    assert {f["check"] for f in data["findings"]} >= set(PLANTED)
    assert "Availability check" in (tmp_path / "c.md").read_text()


def test_software_note_for_bioinformatics_needs_an_archived_version() -> None:
    report = ca.check(SOFTWARE, online=False, venue="bioinformatics-note")
    (finding,) = _checks(report, "no-archive")
    assert finding.severity == ca.Severity.major
    assert finding.line == _line_of(SOFTWARE, "https://github.com/varmerge-dev/varmerge")
    assert "venues.yaml" in finding.rule
    # The abstract names the repository, so the in-abstract rule itself is met.
    assert not _checks(report, "abstract-availability")
    assert report.venue.availability_years == 2 and report.venue.in_abstract and report.venue.wants_archive


def test_the_venue_wants_the_software_in_the_abstract(tmp_path: Path) -> None:
    text = SOFTWARE.read_text(encoding="utf-8")
    text = text.replace("https://github.com/varmerge-dev/varmerge under the MIT licence",
                        "our repository under the MIT licence")
    text = text.replace("## Data availability", "## Code availability\n\nhttps://github.com/varmerge-dev/varmerge\n\n"
                                                 "## Data availability")
    p = tmp_path / "note.md"
    p.write_text(text, encoding="utf-8")
    report = ca.check(p, online=False, venue="bioinformatics-note")
    (finding,) = _checks(report, "abstract-availability")
    assert finding.severity == ca.Severity.major and finding.line == _line_of(p, "## Abstract")
    assert not _checks(ca.check(p, online=False, venue="bmj-open"), "abstract-availability")


def test_without_an_archive_rule_the_same_link_is_only_optional_advice() -> None:
    report = ca.check(SOFTWARE, online=False, venue="bmj-open")
    assert not _checks(report, "no-archive")
    assert [f.severity for f in _checks(report, "code-unversioned")] == [ca.Severity.optional]


# ------------------------------------------------------------------------------------- extraction

POSITIVE = [
    ("Deposited in GEO (GSE2034).", "geo", "GSE2034", None),
    ("Sample GSM37027 and platform GPL570.", "geo", "GSM37027", None),
    ("Platform GPL16791 was used.", "geo", "GPL16791", None),
    ("Reads are in SRA (SRR390728).", "insdc", "SRR390728", None),
    ("ENA run ERR1234567 and DDBJ run DRR012345.", "insdc", "ERR1234567", None),
    ("BioProject PRJNA257197 and PRJEB12345.", "insdc", "PRJNA257197", None),
    ("BioSample SAMN02981360.", "insdc", "SAMN02981360", None),
    ("ArrayExpress E-MTAB-513.", "arrayexpress", "E-MTAB-513", None),
    ("BioStudies S-BSST1234.", "biostudies", "S-BSST1234", None),
    ("Through dbGaP (phs000007.v35.p16).", "dbgap", "phs000007.v35.p16", None),
    ("EGA study EGAS00001000001.", "ega", "EGAS00001000001", None),
    ("EGA dataset EGAD00001000001.", "ega", "EGAD00001000001", None),
    ("Structures PDB ID: 4HHB.", "pdb", "4HHB", None),
    ("See https://www.rcsb.org/structure/1a3n for details.", "pdb", "1A3N", None),
    ("Summary statistics: GCST90012345.", "gwas-catalog", "GCST90012345", None),
    ("Score PGS000001 from the PGS Catalog.", "pgs-catalog", "PGS000001", None),
    ("Archived at https://doi.org/10.5281/zenodo.3242074.", "zenodo", "10.5281/zenodo.3242074", None),
    ("Archived at https://zenodo.org/records/3242074.", "zenodo", "10.5281/zenodo.3242074", None),
    ("Figshare 10.6084/m9.figshare.31791691.v2 holds it.", "figshare", "10.6084/m9.figshare.31791691.v2", None),
    ("Dryad doi:10.5061/dryad.2jm63xt6m holds it.", "dryad", "10.5061/dryad.2jm63xt6m", None),
    ("Data on OSF (https://osf.io/abc12).", "osf", "10.17605/OSF.IO/ABC12", None),
    ("Archived as swh:1:rev:309cf2674ee7a0749978cf8265ab91a60aea0f7d.", "swh",
     "swh:1:rev:309cf2674ee7a0749978cf8265ab91a60aea0f7d", None),
    ("Code: https://github.com/samtools/samtools/releases/tag/1.17.", "github", "samtools/samtools", "1.17"),
    ("Code at github.com/a-lab/tool (version 2.1.0).", "github", "a-lab/tool", "2.1.0"),
    ("Code: https://github.com/a/b/tree/0a9e0b4c.", "github", "a/b", "0a9e0b4c"),
    ("Code: https://gitlab.com/group/sub/proj/-/tags/v0.3.", "gitlab", "group/sub/proj", "v0.3"),
    ("Mirror: https://codeberg.org/someone/tool.", "code-other", "codeberg.org/someone/tool", None),
    ("Install with `pip install pysam==0.22.0`.", "pypi", "pysam", "0.22.0"),
    ("On PyPI: https://pypi.org/project/polars/.", "pypi", "polars", None),
    ("R: install.packages(\"ggplot2\").", "cran", "ggplot2", None),
    ("See https://cran.r-project.org/package=data.table for it.", "cran", "data.table", None),
    ("BiocManager::install(\"DESeq2\").", "bioconductor", "DESeq2", None),
    ("See https://bioconductor.org/packages/release/bioc/html/limma.html.", "bioconductor", "limma", None),
    ("`conda install -c bioconda samtools=1.17`", "bioconda", "samtools", "1.17"),
    ("`mamba install bioconda::bcftools`", "bioconda", "bcftools", None),
    ("`docker pull ubuntu:22.04`", "docker", "library/ubuntu", "22.04"),
    ("Image quay.io/biocontainers/samtools:1.17--h00cdaf9_0 was used.", "quay", "biocontainers/samtools",
     "1.17--h00cdaf9_0"),
    ("Image ghcr.io/org/tool:1.0 was used.", "ghcr", "org/tool", "1.0"),
    ("Data: https://huggingface.co/datasets/just-dna-seq/annotators.", "hf-dataset", "just-dna-seq/annotators", None),
    ("Model: https://huggingface.co/meta-llama/Llama-3.2-1B.", "hf-model", "meta-llama/Llama-3.2-1B", None),
    ("ImageJ (RRID:SCR_003070) was used.", "rrid", "RRID:SCR_003070", None),
    ("Antibody RRID: AB_2138153 was used.", "rrid", "RRID:AB_2138153", None),
]


@pytest.mark.parametrize("text,kind,value,version", POSITIVE)
def test_every_identifier_family_is_extracted(text: str, kind: str, value: str, version: str | None) -> None:
    found = [x for x in _extract(text) if x.kind == kind and x.value == value]
    assert len(found) == 1, [(x.kind, x.value) for x in _extract(text)]
    assert found[0].version == version and found[0].well_formed


NEGATIVE = [
    "We ran GSEA on the ranked list.",
    "The tool is licensed under GPL-3.0, GPLv3, GPL 3 or GPL3.",
    "Signal recognition particle genes SRP54 and SRP9, and ERP29, DRP1 and SRA1, were tested.",
    "Funding was requested on form PHS 398.",
    "Files were written in PDB format, and the PDB 2023 snapshot was used.",
    "Please E-MAIL the authors.",
    "Reagents are listed with RRID: not applicable.",
    "See https://github.com/orgs/dna-seq/repositories and https://github.com/topics/genomics.",
    "See https://huggingface.co/papers/2501.12345 for the method.",
    "PGS scores and PRS were computed; phosphate was measured.",
    "The EGAS consortium and EGA archive were consulted.",
    "We used conda to install the tools.",
]


@pytest.mark.parametrize("text", NEGATIVE)
def test_look_alikes_are_not_identifiers(text: str) -> None:
    assert _extract(text) == []


MALFORMED = [
    ("Deposited in GEO (GSE1589O4).", "GSE1589O4", ""),
    ("Deposited in GEO (GSE 12345).", "GSE 12345", "GSE12345"),
    ("Runs in SRA (SRR 1234567).", "SRR 1234567", "SRR1234567"),
    ("dbGaP study phs00007 was used.", "phs00007", ""),
    ("dbGaP study phs 000007 was used.", "phs 000007", "phs000007"),
    ("EGA dataset EGAD0001.", "EGAD0001", ""),
    ("ArrayExpress EMTAB-1234.", "EMTAB-1234", "E-MTAB-1234"),
    ("Antibody RRID AB_2138153.", "RRID AB_2138153", "RRID:AB_2138153"),
]


@pytest.mark.parametrize("text,value,suggested", MALFORMED)
def test_malformed_identifiers_are_flagged_with_a_repair_only_when_obvious(text: str, value: str,
                                                                          suggested: str) -> None:
    found = [x for x in _extract(text) if not x.well_formed]
    assert [(x.value, x.suggested) for x in found] == [(value, suggested)]


def test_the_reference_list_and_comments_are_not_read(tmp_path: Path) -> None:
    text = ("# Paper\n\n## Methods\n\nData in GEO GSE2034.\n<!-- old accession GSE111111 -->\n\n"
            "## References\n\n1. Some data, GSE222222, https://github.com/ref/only\n\n## Supplementary\n\nGSE333333\n")
    values = {x.value for x in _extract(text)}
    assert values == {"GSE2034", "GSE333333"}


def test_latex_statements_urls_and_comments(tmp_path: Path) -> None:
    tex = tmp_path / "paper.tex"
    tex.write_text("\\section{Methods}\nReads: SRR390728. % SRR000999 was a typo\n"
                   "\\section*{Data availability}\nCode: \\url{https://github.com/a/b} (v1.0.2).\n"
                   "\\begin{thebibliography}{9}\n\\bibitem{x} GSE999999\n\\end{thebibliography}\n", encoding="utf-8")
    report = ca.check(tex, online=False)
    assert {x.value for x in report.identifiers} == {"SRR390728", "a/b"}
    assert [s.label for s in report.statements] == ["Data availability"]
    assert next(x for x in report.identifiers if x.kind == "github").version == "1.0.2"


def test_a_version_after_one_link_does_not_version_the_next() -> None:
    found = {x.value: x.version for x in _extract("Code: https://github.com/a/b (v1.0.0) and https://github.com/c/d.")}
    assert found == {"a/b": "1.0.0", "c/d": None}


def test_a_branch_is_not_a_version() -> None:
    (x,) = _extract("Code: https://github.com/a/b/tree/main/src.")
    assert x.version is None


# ------------------------------------------------------------------------------------- statements

@pytest.mark.parametrize("text,label", [
    ("## Data availability\n\nAll in GEO GSE2034.\n", "Data availability"),
    ("## 7. Code and data availability\n\nSee GSE2034.\n", "Code and data availability"),
    ("**Availability and Implementation:** https://github.com/a/b\n", "Availability and Implementation"),
    ("Data Availability Statement: GSE2034.\n", "Data Availability Statement"),
    ("## Availability of data and materials\n\nGSE2034\n", "Availability of data and materials"),
])
def test_statement_forms_are_found(tmp_path: Path, text: str, label: str) -> None:
    p = tmp_path / "p.md"
    p.write_text("# T\n\n" + text, encoding="utf-8")
    assert [s.label for s in ca.check(p).statements] == [label]


def test_prose_that_mentions_availability_is_not_a_statement(tmp_path: Path) -> None:
    p = tmp_path / "p.md"
    p.write_text("# T\n\nData availability is a growing concern in genomics.\n", encoding="utf-8")
    report = ca.check(p)
    assert report.statements == [] and [f.check for f in _checks(report, "no-statement")] == ["no-statement"]


@pytest.mark.parametrize("body,check,severity,line", [
    ("All data are publicly available.", "empty-statement", "major", 3),  # the statement, at its heading
    ("All data are within the article and its Supplementary Information files.", "in-article-only", "optional", 3),
    ("Data are available from the corresponding author on request.", "request-only", "major", 5),  # the sentence
    ("Because consent covers controlled access only, data are available on request to the data access "
     "committee.", "request-route", "optional", 5),
])
def test_statement_content_findings(tmp_path: Path, body: str, check: str, severity: str, line: int) -> None:
    p = tmp_path / "p.md"
    p.write_text(f"# T\n\n## Data availability\n\n{body}\n", encoding="utf-8")
    report = ca.check(p)
    assert [(f.severity.value, f.line) for f in _checks(report, check)] == [(severity, line)]
    others = {"empty-statement", "in-article-only", "request-only", "request-route"} - {check}
    assert not [f for f in report.findings if f.check in others]


def test_not_applicable_statement_is_not_empty(tmp_path: Path) -> None:
    p = tmp_path / "p.md"
    p.write_text("# T\n\n## Data availability\n\nNot applicable: no new data were generated.\n", encoding="utf-8")
    report = ca.check(p)
    assert not [f for f in report.findings if f.severity == ca.Severity.major]


# ------------------------------------------------------------------------------------- venue rules

def _venues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: dict) -> None:
    p = tmp_path / "venues.yaml"
    p.write_text(yaml.safe_dump({"checked": date(2026, 10, 15), "venues": {"j": {"name": "J", "url": "https://j.example",
                                                                                 **entry}}}), encoding="utf-8")
    monkeypatch.setattr(ca, "VENUES_YAML_OVERRIDE", p)


def test_soft_rules_are_not_requirements(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _venues(tmp_path, monkeypatch, {"software": ["Availability and requirements block with archived DOI recommended",
                                                 "open-source licence recommended but not required"]})
    rules = ca.venue_rules("j")
    assert (rules.wants_archive, rules.wants_licence) == (False, False)
    assert len(rules.rules) == 2


def test_hard_rules_set_the_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _venues(tmp_path, monkeypatch, {
        "software": ["OSI licence", "archived version with DOI", "software available for 5 years"],
        "other_desk_rules": ['data and code in a DOI-minting repository ("available upon request" not accepted)',
                             "reporting checklist (e.g. STROBE)", "max 3 figures"]})
    rules = ca.venue_rules("j")
    assert (rules.wants_archive, rules.wants_licence, rules.request_refused, rules.availability_years,
            rules.reporting_checklist) == (True, True, True, 5, True)
    assert "max 3 figures" not in rules.rules


def test_a_venue_that_refuses_request_routes_makes_even_a_reasoned_one_major(tmp_path: Path,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    _venues(tmp_path, monkeypatch, {"other_desk_rules": ['data in a repository ("available upon request" not accepted)']})
    p = tmp_path / "p.md"
    p.write_text("# T\n\n## Data availability\n\nFor consent reasons, data are available on request.\n", encoding="utf-8")
    report = ca.check(p, venue="j")
    (finding,) = _checks(report, "request-only")
    assert finding.severity == ca.Severity.major and "not accepted" in finding.rule


def test_an_unknown_venue_is_a_usage_error() -> None:
    with pytest.raises(typer.BadParameter):
        ca.venue_rules("no-such-venue-key")


def test_record_supplies_the_venue(tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text("venue:\n  key: bioinformatics-note\n", encoding="utf-8")
    assert ca.venue_from_record(record) == "bioinformatics-note"


# ------------------------------------------------------------------------------------- online, mocked

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture()
def mock_http(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[str]]:
    calls: list[str] = []

    def install(handler: Handler) -> list[str]:
        original = httpx.Client

        def respond(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return handler(request)

        monkeypatch.setattr(ca.httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
        monkeypatch.setattr(ca.time, "sleep", lambda _: None)
        return calls

    return install


def _resolve(text: str) -> dict[str, object]:
    identifiers = _extract(text)
    ca.resolve_all(identifiers)
    return {x.value: x for x in identifiers}


def test_geo_public_private_and_missing(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        acc = r.url.params.get("acc")
        if acc == "GSE1":
            return httpx.Response(200, text="^SERIES = GSE1\n!Series_title = A title\n!Series_status = Public on Jan 1 2020\n")
        if acc == "GSE2":
            return httpx.Response(200, text='<html>Accession "GSE2" is currently private and is scheduled to be released '
                                            "on Aug 01, 2030.</html>")
        return httpx.Response(200, text='<html>Could not find a public or private accession "GSE3"</html>')

    mock_http(handler)
    got = _resolve("GEO GSE1, GSE2 and GSE3.")
    assert [(got[k].state, got[k].title) for k in ("GSE1", "GSE2", "GSE3")] == [
        (ca.State.resolves, "A title"), (ca.State.restricted, ""), (ca.State.not_found, "")]
    assert "Aug 01, 2030" in got["GSE2"].detail


def test_ena_falls_back_to_ncbi_before_saying_not_found(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        if "ena/browser" in str(r.url):
            return httpx.Response(200, json={"summaries": [], "total": "0"})
        count = "1" if r.url.params.get("term") == "SRR1111111" else "0"
        return httpx.Response(200, json={"esearchresult": {"count": count}})

    calls = mock_http(handler)
    got = _resolve("Runs SRR1111111 and SRR2222222.")
    assert got["SRR1111111"].state == ca.State.resolves and "NCBI" in got["SRR1111111"].detail
    assert got["SRR2222222"].state == ca.State.not_found
    assert sum("eutils" in c for c in calls) == 2


def test_controlled_access_records_are_restricted(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        u = str(r.url)
        if "eutils" in u:
            return httpx.Response(200, json={"esearchresult": {"count": "12"}})
        if "study.cgi" in u:
            return httpx.Response(302, headers={"location": "study.cgi?study_id=phs000007.v36.p17"})
        if "ega-archive" in u:
            return httpx.Response(200, json={"accession_id": "EGAS00001000001", "title": "T", "is_released": True})
        if "holdings" in u:
            return httpx.Response(200, json={"rcsb_repository_holdings_combined": {"status": "UNRELEASED"}})
        return httpx.Response(200, json={"id": "o/n", "gated": "manual"})

    mock_http(handler)
    got = _resolve("dbGaP phs000007.v35.p16; EGA EGAS00001000001; PDB ID 9ABC; https://huggingface.co/datasets/o/n")
    assert {k: v.state for k, v in got.items()} == {k: ca.State.restricted for k in got}
    assert "v36.p17" in got["phs000007.v35.p16"].detail


def test_answers_that_cannot_tell_private_from_missing_are_not_assessed(
        mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        if "metadata.ega-archive" in str(r.url):
            return httpx.Response(200, content=b"")
        return httpx.Response(401, json={"error": "Invalid username or password."})

    mock_http(handler)
    got = _resolve("https://huggingface.co/datasets/o/n and quay.io/ns/repo:1.0; EGA EGAD00009999999.")
    assert got["o/n"].state == ca.State.not_assessed
    assert got["ns/repo"].state == ca.State.not_assessed
    assert got["EGAD00009999999"].state == ca.State.not_found


def test_a_refused_or_failing_request_is_never_not_found(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        if "pypi" in str(r.url):
            raise httpx.ConnectError("refused", request=r)
        return httpx.Response(503)

    calls = mock_http(handler)
    got = _resolve("`pip install pysam`; GEO GSE2034.")
    assert {x.state for x in got.values()} == {ca.State.not_assessed}
    assert sum("acc.cgi" in c for c in calls) == 3  # retried with backoff, then given up


def test_an_html_page_where_json_was_expected_is_not_assessed(mock_http: Callable[[Handler], list[str]]) -> None:
    mock_http(lambda r: httpx.Response(200, text="<html>Down for maintenance</html>"))
    got = _resolve("`pip install pysam`; https://github.com/a/b; `conda install -c bioconda samtools`")
    assert {x.state for x in got.values()} == {ca.State.not_assessed}


def test_github_rate_limit_stops_further_github_calls(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792080000"},
                              json={"message": "API rate limit exceeded"})

    calls = mock_http(handler)
    got = _resolve("https://github.com/a/one and https://github.com/b/two")
    assert {x.state for x in got.values()} == {ca.State.not_assessed}
    assert "rate limit" in got["b/two"].detail
    assert len(calls) == 1


def test_github_repository_without_licence_or_release(mock_http: Callable[[Handler], list[str]],
                                                      tmp_path: Path) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        path = r.url.path
        if path == "/repos/lab/tool":
            return httpx.Response(200, json={"full_name": "lab/tool", "description": "d", "license": None})
        if path.endswith("/releases") or path.endswith("/tags"):
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"message": "Not Found"})

    mock_http(handler)
    p = tmp_path / "p.md"
    p.write_text("# T\n\n## Code availability\n\nhttps://github.com/lab/tool and https://github.com/lab/gone\n",
                 encoding="utf-8")
    report = ca.check(p, online=True)
    tool = next(x for x in report.identifiers if x.value == "lab/tool")
    assert "no-release" in tool.flags and "no-licence" in tool.flags
    (unversioned,) = [f for f in _checks(report, "code-unversioned") if "lab/tool" in f.message]
    assert "no release or tag at all" in unversioned.message
    assert [f.severity for f in _checks(report, "no-licence")] == [ca.Severity.optional]
    assert [f.line for f in _checks(report, "not-found")] == [5]


def test_github_cited_tag_that_does_not_exist(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/repos/lab/tool":
            return httpx.Response(200, json={"full_name": "lab/tool", "license": {"spdx_id": "MIT"}})
        return httpx.Response(404, json={"message": "Not Found"})

    calls = mock_http(handler)
    got = _resolve("https://github.com/lab/tool/releases/tag/2.0")
    assert got["lab/tool"].flags == ["version-missing"] and got["lab/tool"].licence == "MIT"
    assert any(c.endswith("/git/ref/tags/2.0") for c in calls) and any(c.endswith("/git/ref/tags/v2.0") for c in calls)


def test_packages_versions_and_withdrawals(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        u = str(r.url)
        if u.endswith("/pypi/pysam/json"):
            return httpx.Response(200, json={"info": {"summary": "s", "version": "0.24.1", "license": "MIT"}})
        if "/pypi/pysam/9.9/json" in u:
            return httpx.Response(404)
        if "crandb" in u:
            return httpx.Response(200, json={"archived": True, "latest": "1.6-7", "versions": {"1.6-7": {"License": "GPL"}}})
        if "bioconductor.org/packages/Gone" in u:
            return httpx.Response(302, headers={"location": "https://bioconductor.org/about/removed-packages/"})
        if "bioconductor.org/packages/DESeq2" in u:
            return httpx.Response(302, headers={"location": "https://bioconductor.org/packages/release/bioc/html/DESeq2.html"})
        if "anaconda" in u:
            return httpx.Response(200, json={"versions": ["1.16", "1.17"], "license": "MIT", "latest_version": "1.17"})
        return httpx.Response(404)

    mock_http(handler)
    got = _resolve('`pip install pysam==9.9`; install.packages("rgdal"); BiocManager::install(c("Gone", "DESeq2")); '
                   "`conda install -c bioconda samtools=1.17`")
    assert got["pysam"].flags == ["version-missing"]
    assert got["rgdal"].state == ca.State.resolves and got["rgdal"].flags == ["withdrawn"]
    assert (got["Gone"].state, got["DESeq2"].state) == (ca.State.not_found, ca.State.resolves)
    assert got["samtools"].state == ca.State.resolves and got["samtools"].flags == []


def test_dois_datacite_then_doi_org(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        u = str(r.url)
        if "datacite" in u and "zenodo.1" in u:
            return httpx.Response(200, json={"data": {"attributes": {
                "titles": [{"title": "Tool v1"}], "rightsList": [{"rights": "MIT License"}, {"rights": "Open Access"}],
                "relatedIdentifiers": [{"relationType": "HasVersion", "relatedIdentifier": "10.5281/zenodo.2"}]}}})
        if "datacite" in u:
            return httpx.Response(404)
        if "handles/10.5061" in u:
            return httpx.Response(200, json={"responseCode": 1})
        return httpx.Response(404, json={"responseCode": 100})

    mock_http(handler)
    got = _resolve("Archived at 10.5281/zenodo.1, 10.5281/zenodo.9 and 10.5061/dryad.abc123.")
    assert (got["10.5281/zenodo.1"].state, got["10.5281/zenodo.1"].licence, got["10.5281/zenodo.1"].flags) == (
        ca.State.resolves, "MIT License", ["concept-doi"])
    assert got["10.5281/zenodo.9"].state == ca.State.not_found
    assert got["10.5061/dryad.abc123"].state == ca.State.resolves


def test_malformed_identifiers_are_not_sent_anywhere(mock_http: Callable[[Handler], list[str]]) -> None:
    calls = mock_http(lambda r: httpx.Response(500))
    got = _resolve("GEO GSE1589O4 and EGAD0001.")
    assert calls == [] and all(not x.well_formed for x in got.values())


def test_online_findings_for_the_seeded_fixture(mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        u = str(r.url)
        if "eutils" in u:
            return httpx.Response(200, json={"esearchresult": {"count": "3"}})
        if "study.cgi" in u:
            return httpx.Response(302, headers={"location": "study.cgi?study_id=phs000007.v35.p16"})
        if r.url.path == "/repos/northfield-genetics/urate-assoc":
            return httpx.Response(200, json={"full_name": "northfield-genetics/urate-assoc", "license": {"spdx_id": "MIT"}})
        if r.url.path.endswith(("/releases", "/tags")):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    mock_http(handler)
    report = ca.check(SEEDED, online=True, venue="bmj-open")
    (unversioned,) = _checks(report, "code-unversioned")
    assert "no release or tag at all" in unversioned.message
    dbgap = next(x for x in report.identifiers if x.kind == "dbgap")
    assert dbgap.state == ca.State.restricted
    # The seeded text names the access route ("dbGaP authorized access"), so no access-route finding.
    assert not _checks(report, "access-route")


# ------------------------------------------------------------------------------------- smoke-run regressions
# Minimal excerpts of the two public smoke-test papers (just-dna-lite v0.4, Markdown; the module-authoring
# paper, LaTeX) that triggered each defect.

PAPER1_AVAILABILITY = (
    "# T\n\n"
    "**Availability and implementation:** Source code: https://github.com/dna-seq/just-dna-lite and "
    "https://github.com/dna-seq/just-prs. The two co-author genomes used in the benchmarks are public on Zenodo "
    "(records 18370498 and 19487816).\n\n"
    "## Code Availability\n\n"
    "**GitHub organization:** https://github.com/dna-seq; Table S8 lists the repositories of both generations.\n\n"
    "Annotation modules and reference datasets are published to the just-dna-seq organization on HuggingFace "
    "(annotators, ensembl_variations, clinvar, pgs-catalog, prs-percentiles), which serves as the default source "
    "for module auto-discovery.\n")

PAPER2_AVAILABILITY = (
    "\\section{Introduction}\n"
    "The software is open-source and available at\n"
    "\\url{https://anonymous.4open.science/r/just-dna-registry} (anonymized for review).\n"
    "\\section{Code and data availability}\n"
    "\\begin{itemize}\n"
    "    \\item \\textbf{just-dna-format, just-dna-compiler, and just-dna-enricher}:\n"
    "    \\url{https://anonymous.4open.science/r/just-dna-compiler}\n"
    "    (schema, reference compiler, and enricher).\n"
    "    \\item \\textbf{just-module-creator}:\n"
    "    \\url{https://anonymous.4open.science/r/just-dna-registry}\n"
    "    (MCP server, Claude Code and Codex plugin manifests, skills; MIT).\n"
    "\\end{itemize}\n")


def _write(tmp_path: Path, text: str, name: str = "p.md") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_zenodo_record_numbers_and_hugging_face_names_in_prose_are_extracted(tmp_path: Path) -> None:
    report = ca.check(_write(tmp_path, PAPER1_AVAILABILITY))
    found = {(x.kind, x.value) for x in report.identifiers if x.in_statement}
    assert {("zenodo", "10.5281/zenodo.18370498"), ("zenodo", "10.5281/zenodo.19487816")} <= found
    assert {v for k, v in found if k == "hf-repo"} == {f"just-dna-seq/{n}" for n in (
        "annotators", "ensembl_variations", "clinvar", "pgs-catalog", "prs-percentiles")}
    assert not _checks(report, "archive-unidentified")


@pytest.mark.parametrize("text,expected", [
    ("The VCF of one co-author (Zenodo record 18370498, CC0) was the main input.", {"10.5281/zenodo.18370498"}),
    ("| **Primary (public, Zenodo 18370498)** |  |", {"10.5281/zenodo.18370498"}),
    ("Deposited at Zenodo (records 1234567, 2345678 and 3456789).",
     {"10.5281/zenodo.1234567", "10.5281/zenodo.2345678", "10.5281/zenodo.3456789"}),
    ("Zenodo (2024) hosts many datasets.", set()),
])
def test_zenodo_record_number_forms(text: str, expected: set[str]) -> None:
    assert {x.value for x in _extract(text) if x.kind == "zenodo"} == expected


@pytest.mark.parametrize("text,expected", [
    ("Weights are on the Hugging Face dataset just-dna-seq/annotators.", {("hf-dataset", "just-dna-seq/annotators")}),
    ("We used the Hugging Face models meta-llama/Llama-3.2-1B and Qwen/Qwen2.5-7B.",
     {("hf-model", "meta-llama/Llama-3.2-1B"), ("hf-model", "Qwen/Qwen2.5-7B")}),
    ("Parquet files are downloaded from HuggingFace via fsspec.", set()),
])
def test_hugging_face_repositories_named_in_prose(text: str, expected: set[tuple[str, str]]) -> None:
    assert {(x.kind, x.value) for x in _extract(text) if x.kind.startswith("hf-")} == expected


def test_a_data_deposit_on_zenodo_is_not_the_code_archive(tmp_path: Path) -> None:
    # The genomes on Zenodo must not hide the missing archived software version Bioinformatics asks for.
    report = ca.check(_write(tmp_path, PAPER1_AVAILABILITY), venue="bioinformatics")
    assert [f.severity for f in _checks(report, "no-archive")] == [ca.Severity.major]


def test_an_archive_named_without_an_identifier_is_not_assessed(tmp_path: Path) -> None:
    report = ca.check(_write(tmp_path, "# T\n\n## Data availability\n\nThe modules are published on Hugging Face.\n"))
    (finding,) = _checks(report, "archive-unidentified")
    assert (finding.severity, finding.line) == (ca.Severity.uncertain, 5) and "not assessed" in finding.message


def test_anonymised_review_links_are_extracted_never_looked_up_and_need_an_archive_by_acceptance(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_http: Callable[[Handler], list[str]]) -> None:
    tex = _write(tmp_path, PAPER2_AVAILABILITY, "paper.tex")
    calls = mock_http(lambda r: httpx.Response(401, json={"error": "not_connected"}))
    report = ca.check(tex, online=True)
    anon = [x for x in report.identifiers if x.kind == "anon-review"]
    assert {x.value for x in anon} == {"just-dna-compiler", "just-dna-registry"}
    assert all(x.state == ca.State.not_assessed and "anonymised for review" in x.detail and x.own for x in anon)
    assert calls == []
    (finding,) = _checks(report, "anonymised-code")
    assert finding.severity == ca.Severity.optional and "By acceptance" in finding.suggestion
    assert not _checks(report, "code-unversioned") and not _checks(report, "no-archive")
    _venues(tmp_path, monkeypatch, {"software": ["archived version with DOI"]})
    (strict,) = _checks(ca.check(tex, venue="j"), "anonymised-code")
    assert strict.severity == ca.Severity.major and "venues.yaml" in strict.rule


def test_the_anonymised_fixture_flags_only_the_anonymised_code() -> None:
    # The exomes on Zenodo are a data deposit: they must not count as the code's archive.
    report = ca.check(ANONYMISED)
    assert {f.check for f in report.findings if f.severity != ca.Severity.uncertain} == {"anonymised-code"}
    assert ("zenodo", "10.5281/zenodo.7654321") in {(x.kind, x.value) for x in report.identifiers}
    (finding,) = _checks(report, "anonymised-code")
    assert finding.line == _line_of(ANONYMISED, "anonymous.4open.science/r/varpanel-3F1C")


def test_on_demand_in_an_appendix_is_not_a_request_route(tmp_path: Path) -> None:
    tex = _write(tmp_path, PAPER2_AVAILABILITY + (
        "\\appendix\n\\section{Plugin surface: tools and skills}\n"
        "A Claude Code or Codex plugin is a bundle of two kinds of asset. \\textbf{MCP\n"
        "tools} are typed operations the assistant can call. \\textbf{Skills} are written\n"
        "instructions loaded into the assistant's context on demand; they teach the\n"
        "workflow that the tools serve.\n"), "paper.tex")
    report = ca.check(tex)
    assert not _checks(report, "request-only") and not _checks(report, "request-route")


def test_a_table_cell_offering_another_tool_by_request_is_not_read(tmp_path: Path) -> None:
    report = ca.check(_write(tmp_path, PAPER1_AVAILABILITY + (
        "\n## Supplementary Material\n\n**Table S7.** Comparison with other tools.\n\n"
        "| Tool | Graphical interface | Open source |\n|---|---|---|\n"
        "| **Just-DNA-Lite** | Yes (local web UI) | Yes (AGPL-3.0) |\n"
        "| DeepRare | Hosted web app (by request) | No (CC BY-NC 4.0) |\n")))
    assert not _checks(report, "request-route") and not _checks(report, "request-only")


@pytest.mark.parametrize("text,name,line", [
    ("\\section*{Data availability}\n\\textbf{Code.} The scripts are at \\url{https://github.com/a/b} (v1.0).\n"
     "\\textbf{Data.} Genotypes are available from the\ncorresponding author on request.\n", "p.tex", 3),
    ("# T\n\n## Data availability\n\nGenotype data for the 412 participants of the\nreplication cohort, with their "
     "phenotypes, are available\nfrom the corresponding author upon request.\n", "p.md", 6),
])
def test_a_request_is_reported_at_the_line_of_its_phrase(tmp_path: Path, text: str, name: str, line: int) -> None:
    (finding,) = _checks(ca.check(_write(tmp_path, text, name)), "request-only")
    assert finding.line == line


def test_licence_and_release_checks_are_for_the_authors_own_code_only(
        tmp_path: Path, mock_http: Callable[[Handler], list[str]]) -> None:
    paper = _write(tmp_path, PAPER1_AVAILABILITY + (
        "\n## Supplementary Material\n\nSoftware without a paper (cite as software, accessed 10 October 2026):\n\n"
        "† KarchinLab (2025). OpenCRAVAT MCP server [software]. https://github.com/KarchinLab/oc-mcp.\n\n"
        "† Oak Bioinformatics (2026). OakVar, version 2.13.1 [software]. "
        "https://github.com/rkimoakbioinformatics/oakvar.\n\n"
        "| Repository | Description |\n|---|---|\n"
        "| [just-prs-mcp](https://github.com/dna-seq/just-prs-mcp) | MCP server exposing just-prs |\n"))
    licences = {"dna-seq/just-dna-lite": {"spdx_id": "AGPL-3.0"}, "dna-seq/just-prs": {"spdx_id": "MIT"},
                "dna-seq/just-prs-mcp": None, "KarchinLab/oc-mcp": None,
                "rkimoakbioinformatics/oakvar": {"spdx_id": "NOASSERTION"}}

    def handler(r: httpx.Request) -> httpx.Response:
        path = r.url.path
        repo = path.removeprefix("/repos/")
        if repo in licences:
            return httpx.Response(200, json={"full_name": repo, "license": licences[repo]})
        if path.endswith(("/releases", "/tags")):
            return httpx.Response(200, json=[])
        if "datacite" in str(r.url) or "/api/datasets/" in path:
            return httpx.Response(200, json={"data": {"attributes": {}}})
        return httpx.Response(404, json={"message": "Not Found"})

    calls = mock_http(handler)
    report = ca.check(paper, online=True)
    own = {x.value for x in report.identifiers if x.kind == "github" and x.own}
    assert own == {"dna-seq/just-dna-lite", "dna-seq/just-prs", "dna-seq/just-prs-mcp"}
    assert {f.message.split(" for ")[1].split(";")[0] for f in _checks(report, "no-licence")} == {"dna-seq/just-prs-mcp"}
    assert not _checks(report, "licence-unrecognised") and not _checks(report, "version-not-found")
    assert not [c for c in calls if "KarchinLab" in c and c.endswith("/releases?per_page=1")]
    assert not [c for c in calls if "oakvar" in c and "/git/ref/tags/" in c]


def test_an_identifier_the_text_excludes_is_not_a_major_finding(
        tmp_path: Path, mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        score = r.url.path.rstrip("/").rsplit("/", 1)[-1]
        return httpx.Response(200, json={} if score == "PGS000085" else {"id": score, "name": "n"})

    mock_http(handler)
    report = ca.check(_write(tmp_path, "# T\n\n## Methods\n\nThe 100 scores are PGS000006 to PGS000106, excluding "
                                        "PGS000085; PGS000001 to PGS000003 ran first as a warm-up.\n"), online=True)
    (finding,) = _checks(report, "not-found")
    assert "PGS000085" in finding.message and finding.severity == ca.Severity.optional
    assert "excludes it" in finding.message


def test_a_hugging_face_repository_of_unstated_type_is_tried_as_dataset_model_and_space(
        mock_http: Callable[[Handler], list[str]]) -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/api/models/org/found":
            return httpx.Response(200, json={"id": "org/found"})
        if r.url.path.endswith("/org/private"):
            return httpx.Response(401, json={"error": "Invalid username or password."})
        return httpx.Response(404)

    mock_http(handler)
    got = _resolve("Published to the org organization on Hugging Face (found, gone, private).")
    assert (got["org/found"].state, got["org/gone"].state, got["org/private"].state) == (
        ca.State.resolves, ca.State.not_found, ca.State.not_assessed)
    assert "Hugging Face model" in got["org/found"].detail


# ------------------------------------------------------------------------------------- guidelines.yaml

REQUIRED_IDS = {"strobe", "strobe-mr", "strega", "stard", "tripod-ai", "prisma", "consort", "arrive", "care",
                "prs-rs", "mdar", "minseqe", "miame", "mixs", "dome"}


def test_guidelines_yaml_passes_its_schema() -> None:
    errors, _ = gl.validate_data()
    assert errors == []


def test_every_entry_has_source_licence_checked_date_and_shared_design_keys() -> None:
    keys = set(gl.design_keys())
    assert {"software-tool", "genetic-association", "omics-profiling"} <= keys  # the shared list was parsed
    data = gl.load()
    for g in data["guidelines"]:
        sources = g["sources"]
        assert any(sources.get(k) for k in ("equator", "paper_doi", "checklist_url")), g["id"]
        assert g["licence"] and g["licence_basis"], g["id"]
        assert isinstance(g["checked"], date), g["id"]
        assert set(g["designs"]) <= keys, g["id"]
    assert set(data["design_notes"]) <= keys


def test_the_required_guidelines_are_covered_with_current_versions() -> None:
    index = gl.by_id(gl.load())
    assert REQUIRED_IDS <= set(index)
    assert str(index["consort"]["version"]).startswith("2025")
    assert str(index["prisma"]["version"]).startswith("2020")
    assert str(index["tripod-ai"]["version"]).startswith("2024")
    assert all(index[g]["status"] == "verified" for g in REQUIRED_IDS)


def test_validation_catches_each_kind_of_broken_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = gl.load()
    broken = dict(good)
    entry = dict(next(g for g in good["guidelines"] if g["id"] == "strega"))
    entry.update(id="broken", designs=["genomics"], licence="", base_items=None,
                 items=[{"n": "1", "text": "a"}, {"n": "1", "text": "b"}])
    entry["sources"] = {"equator": None, "paper_doi": "not-a-doi", "checklist_url": "http://insecure.example"}
    sourceless = dict(entry, id="sourceless", designs=["software-tool"], licence="MIT", base_items="interleave",
                      items=[{"n": "1", "text": "a"}], sources={"equator": None, "paper_doi": None, "checklist_url": None})
    broken["guidelines"] = good["guidelines"] + [entry, sourceless]
    p = tmp_path / "guidelines.yaml"
    p.write_text(yaml.safe_dump(broken, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(gl, "GUIDELINES_YAML", p)
    errors, _ = gl.validate_data()
    assert {e for e in errors if e.startswith("broken:")} == {
        "broken: missing licence", "broken: sources.checklist_url is not an https URL",
        "broken: paper_doi 'not-a-doi' is not a DOI", "broken: unknown design key 'genomics'",
        "broken: an extension needs base_items: interleave | append | none", "broken: item 1 repeats"}
    assert [e for e in errors if e.startswith("sourceless:")] == [
        "sourceless: no primary source (equator, paper_doi or checklist_url)"]
    assert not [e for e in errors if not e.startswith(("broken:", "sourceless:"))]


def test_stale_entries_are_warnings_not_errors() -> None:
    errors, warnings = gl.validate_data(max_age_days=365, today=date(2028, 1, 1))
    assert errors == [] and len(warnings) == len(gl.load()["guidelines"])
    assert gl.validate_data(max_age_days=365, today=date(2026, 10, 16))[1] == []


# ------------------------------------------------------------------------------------- selection

def test_genetic_association_brings_strega_and_its_base() -> None:
    sel = gl.select_guidelines(["genetic-association"])
    assert {e["id"] for e in sel["apply"]} == {"strobe", "strega"}
    assert sel["venue_checklists"] == []


def test_a_software_tool_gets_no_invented_guideline() -> None:
    sel = gl.select_guidelines(["software-tool"])
    assert sel["apply"] == []
    assert [e["id"] for e in sel["confirm_first"]] == ["dome"]
    assert "No EQUATOR reporting guideline" in sel["notes"]["software-tool"]


def test_mixed_designs_select_each_part() -> None:
    sel = gl.select_guidelines(["genetic-association", "mendelian-randomization", "polygenic-score"])
    assert {"strobe", "strega", "strobe-mr"} <= {e["id"] for e in sel["apply"]}
    assert "prs-rs" in {e["id"] for e in sel["confirm_first"]}


def test_prs_rs_is_conditional_with_a_note_for_papers_that_only_apply_scores() -> None:
    # Smoke run on a tool paper that applies published PGS Catalog scores: PRS-RS was listed under "Apply".
    sel = gl.select_guidelines(["software-tool", "polygenic-score"])
    assert "prs-rs" not in {e["id"] for e in sel["apply"]}
    (prs,) = [e for e in sel["confirm_first"] if e["id"] == "prs-rs"]
    assert "developed or validated" in prs["applies_if"] and "predictive performance" in prs["applies_if"]
    assert "only applies published scores" in prs["note"]
    md = gl.selection_markdown(sel)
    assert md.index("## Confirm the condition first") < md.index("**PRS-RS") and "only applies published" in md


def test_the_design_keys_are_listed_without_an_error_message() -> None:
    # A runner found the keys only in the error for `--design benchmark`.
    keys = gl.design_keys()
    listing = CliRunner().invoke(gl.app, ["designs"])
    assert listing.exit_code == 0, listing.output
    assert [line.split()[0] for line in listing.output.splitlines()] == keys
    flat = re.sub(r"[│\s]", "", CliRunner().invoke(gl.app, ["select", "--help"]).output)  # rich wraps at spaces
    assert all(k in flat for k in keys)
    with pytest.raises(typer.BadParameter, match="guidelines.py designs"):
        gl.select_guidelines(["benchmark"])


def test_the_items_table_asks_for_answers_keyed_to_item_numbers_not_the_form() -> None:
    text = gl.items_markdown("prs-rs", None)
    assert "keyed by the official item numbers" in text and "never reproduce the form's text" in text
    assert "Complete the official form" not in text


@pytest.mark.parametrize("venue,expected", [
    ("nature-genetics", {"nature-reporting-summary", "nature-editorial-policy-checklist"}),
    ("bioinformatics", set()),
    ("bmj-open", set()),
])
def test_venue_checklists_only_for_their_venue(venue: str, expected: set[str]) -> None:
    sel = gl.select_guidelines(["genetic-association"], venue)
    assert {e["id"] for e in sel["venue_checklists"]} == expected
    assert all(e["withdrawn"] == (e["id"] == "nature-editorial-policy-checklist") for e in sel["venue_checklists"])


def test_the_venue_rule_decides_whether_items_carry_a_cost() -> None:
    required = gl.selection_markdown(gl.select_guidelines(["genetic-association"], "bmj-open"))
    advice = gl.selection_markdown(gl.select_guidelines(["genetic-association"], "bioinformatics"))
    assert "can then cost" in required and "optional advice" in advice


def test_unknown_design_key_is_a_usage_error() -> None:
    with pytest.raises(typer.BadParameter):
        gl.select_guidelines(["genomics"])


def test_strega_items_interleave_with_strobe() -> None:
    index = gl.by_id(gl.load())
    rows = gl.audit_rows("strega")
    assert len(rows) == len(index["strobe"]["items"]) + len(index["strega"]["items"])
    order = [(r["guideline"].split()[0], r["n"]) for r in rows]
    assert order.index(("STROBE", "12e")) < order.index(("STREGA", "12f")) < order.index(("STROBE", "13a"))


def test_a_stand_alone_extension_does_not_pull_its_base() -> None:
    assert {r["guideline"].split()[0] for r in gl.audit_rows("strobe-mr")} == {"STROBE-MR"}


def test_items_table_records_the_manuscript_hash(tmp_path: Path) -> None:
    out = tmp_path / "audit.md"
    result = CliRunner().invoke(gl.app, ["items", "strega", "--manuscript", str(SEEDED), "--md", str(out)])
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "sha256" in text and "| STREGA 2009 | 12h |" in text and "unclear (material not supplied)" in text


def test_select_reads_designs_and_venue_from_the_record(tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text("venue: {key: bmj-open}\nstudy: {designs: [genetic-association]}\n", encoding="utf-8")
    out = tmp_path / "sel.json"
    result = CliRunner().invoke(gl.app, ["select", "--record", str(record), "--json", str(out)])
    assert result.exit_code == 0, result.output
    sel = json.loads(out.read_text())
    assert sel["venue"]["key"] == "bmj-open" and sel["venue"]["reporting_checklist"] is True
